# Paper Quality Grading Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Every merged paper from any source carries an explainable `quality_grade` (high / medium / low / flagged / ungraded) with per-paper signals, plus `sort="quality"` and a `group_by_quality` tool/UI grouping.

**Architecture:** Add fields to `Paper`, map new OpenAlex fields in the provider mapper, grade every merged paper deterministically in a pure `quality` module, enrich post-merge via a batch OpenAlex DOI lookup plus a cached Scopus Serial Title lookup (CiteScore percentile bands → quartile, with Consensus SJR fallback), expose sort + MCP tool + REST, and render grade chips/grouping in the web UI.

**Tech Stack:** Python 3.12 (httpx, no new dependencies), pytest for backend, React 19 + Vite + Tailwind + existing shadcn components in `web/`.

## Global Constraints

- No new Python dependencies.
- Grading runs on the **merged** paper set, so it applies to papers from every source; enrichment is best-effort and never blocks results — failures land in `errors["quality"]`.
- Grade rules are deterministic and documented in `quality.py`; every grade ships with its signal breakdown (`quality_signals`).
- Journal-level metrics (CiteScore quartile) are context signals only, per DORA recommendation 1; they never stand in for article-level evidence.
- Design/study type is context only — it does not bump a grade (GRADE grades bodies of evidence, not single articles).
- Retractions always override everything: `flagged`.
- Quartile scheme is Scopus CiteScore percentile bands; when the SJR fallback is used, the signal says so.
- Cache file lives at `journal-scout/.cache/scopus-serials.json` (gitignored), TTL 90 days.
- Verify live API shapes before mapping (Task 1 and Task 4 step 1); fix the mapping to what the API actually returns, not to assumptions.

## Existing code map

- `src/josc/models.py` — `Paper` dataclass (fields end at `sjr_best_quartile`, `is_preprint`), `RetractionInfo`, `to_dict`.
- `src/josc/providers/openalex.py` — `_to_paper(work)` maps `primary_location.source.display_name` → `venue` (~L140); `cited_by_percentile_year.min` → `cited_by_percentile` (L127); `get_many` (L256) batch-fetches works by DOI chunks.
- `src/josc/providers/scopus.py` — `ScopusProvider`, `http` client with `X-Api-Key` header; content-API methods already present; API base `https://api.elsevier.com`.
- `src/josc/aggregator.py` — `search_all()` fans out, merges via `merge_papers`, then `_sort(result["results"], sort, order)` (`_SORT_FIELDS` at L190).
- `src/josc/api/search_routes.py` — `/search` REST route forwards `sort`, `order`, provider filters.
- `src/josc/server.py` — MCP tool registration (tools incl. `search_all`, `get_quota_status`).
- `web/src/components/PaperTable.tsx` — results table; `web/src/components/search/SearchResults.tsx` — results layout, `Chip`/`Button` available; `web/src/lib/types.ts` — `Paper` TS type.

---

### Task 1: Paper fields + OpenAlex mapping

**Files:**
- Modify: `src/josc/models.py`, `src/josc/providers/openalex.py`
- Test: `tests/test_openalex_mapper.py` (new or extend existing)

**Interfaces:**
- Produces `Paper.issn`, `Paper.citation_normalized_percentile`, `Paper.journal_quartile`, `Paper.journal_cite_score`, `Paper.quality_grade`, `Paper.quality_signals` (all optional, `None` default, included in `to_dict`).

- [ ] **Step 1: Verify the live OpenAlex shape**

Run from `journal-scout/`:

```bash
.venv/bin/python - <<'PY'
import json, urllib.request
url = ("https://api.openalex.org/works?filter=doi:10.1038/nature12351,"
       "10.7554/elife.47338&select=display_name,citation_normalized_percentile,"
       "cited_by_percentile_year,primary_location")
print(json.dumps(json.load(urllib.request.urlopen(url))["results"], indent=1)[:3000])
PY
```

Expected: each work carries `citation_normalized_percentile` (float 0–1, may be absent for very new works) and `primary_location.source.issn`. Record the actual JSON shape (value types, missing keys) — the mapper in Step 3 must match it.

- [ ] **Step 2: Add the model fields**

In `models.py`, add to `Paper` (after `is_preprint`):

```python
    issn: str | None = None
    citation_normalized_percentile: float | None = None
    journal_quartile: int | None = None
    journal_cite_score: float | None = None
    quality_grade: str | None = None
    quality_signals: dict[str, Any] | None = None
```

and include all six in `to_dict`.

- [ ] **Step 3: Map them in `openalex.py` `_to_paper`**

Inside the existing `Paper(...)` construction, add:

```python
            issn=source.get("issn"),
            citation_normalized_percentile=work.get("citation_normalized_percentile"),
```

Guard the float: if OpenAlex ever returns it as a string, coerce with `float(...)` inside a try/except returning `None`. `get_many` (DOI batch) returns works through the same `_to_paper`, so the batch enrichment path gets these fields for free.

- [ ] **Step 4: Write failing mapper tests, then make them pass**

In `tests/test_openalex_mapper.py` (create if missing; follow the fixture style of `tests/test_providers/test_openalex.py`):

```python
def test_maps_issn_and_normalized_percentile():
    work = {
        "doi": "10.1000/xyz",
        "display_name": "T",
        "primary_location": {"source": {"display_name": "J", "issn": "1234-5678"}},
        "citation_normalized_percentile": 0.92,
    }
    p = OpenAlexProvider._to_paper(work)
    assert p.issn == "1234-5678"
    assert p.citation_normalized_percentile == 0.92

def test_missing_fields_stay_none():
    p = OpenAlexProvider._to_paper({"display_name": "T"})
    assert p.issn is None and p.citation_normalized_percentile is None
```

Run: `.venv/bin/python -m pytest tests/test_openalex_mapper.py -v` — RED then GREEN.

- [ ] **Step 5: Commit**

```bash
git add journal-scout/src/josc/models.py journal-scout/src/josc/providers/openalex.py journal-scout/tests/test_openalex_mapper.py
git commit -m "feat(journal-scout): carry ISSN and normalized citation percentile on Paper"
```

---

### Task 2: Pure grading module `quality.py`

**Files:**
- Create: `src/josc/quality.py`
- Test: `tests/test_quality.py`

**Interfaces:**
- Produces `grade_paper(paper: Paper) -> Paper` (fills `quality_grade` + `quality_signals`, returns the same object) and `GRADE_ORDER: dict[str, int]` for sorting.

- [ ] **Step 1: Write failing tests covering every rule**

`tests/test_quality.py` — pure, no network. Helper builds `Paper` instances:

```python
def p(**kw):
    base = dict(title="T", doi="10.1/x")
    base.update(kw)
    return Paper(**base)

def test_retracted_always_flagged():
    assert grade_paper(p(is_retracted=True, citation_normalized_percentile=0.99, journal_quartile=1)).quality_grade == "flagged"

def test_no_signals_ungraded():
    assert grade_paper(p()).quality_grade == "ungraded"

def test_top_decile_high():
    assert grade_paper(p(citation_normalized_percentile=0.95)).quality_grade == "high"

def test_fallback_year_percentile_scales_to_unit():
    assert grade_paper(p(cited_by_percentile=90)).quality_grade == "high"

def test_q1_without_citations_medium():
    assert grade_paper(p(journal_quartile=1)).quality_grade == "medium"

def test_mid_percentile_medium():
    assert grade_paper(p(citation_normalized_percentile=0.8)).quality_grade == "medium"

def test_q2_only_low():
    assert grade_paper(p(journal_quartile=2)).quality_grade == "low"

def test_weak_signals_low():
    assert grade_paper(p(citation_normalized_percentile=0.4, journal_quartile=3)).quality_grade == "low"

def test_signals_document_reasons_and_context():
    out = grade_paper(p(citation_normalized_percentile=0.95, year=2025, is_preprint=True,
                       publication_types=["Randomized controlled trial"]))
    assert out.quality_grade == "high"
    s = out.quality_signals
    assert "pct" in s and "reasons" in s
    assert any("young" in r.lower() or "muda" in r.lower() for r in s["reasons"]) or s.get("young") is True
    assert s["design"]  # context only
```

Run: `.venv/bin/python -m pytest tests/test_quality.py -v` — expect RED (module missing).

- [ ] **Step 2: Implement `quality.py`**

```python
"""Deterministic, explainable quality grading for merged papers.

Article-level signals (normalized citation percentile) dominate; journal
quartile is context only (DORA rec. 1); retraction overrides everything.
"""
from __future__ import annotations

from datetime import date

from .models import Paper

# lower value = better rank; flagged and ungraded sort to the bottom
GRADE_ORDER = {"high": 0, "medium": 1, "low": 2, "flagged": 3, "ungraded": 4}

DESIGN_CONTEXT_MARKERS = (
    "meta-analysis", "meta analysis", "systematic review",
    "randomized controlled trial", "randomised controlled trial",
)

def _design(paper: Paper) -> str | None:
    texts = [paper.study_type or ""] + paper.publication_types
    for t in texts:
        low = t.lower()
        hit = [m for m in DESIGN_CONTEXT_MARKERS if m in low]
        if hit:
            return t
    return None

def _young(year, today=None):
    today = today or date.today()
    return year is not None and year >= today.year - 2

def grade_paper(paper: Paper) -> Paper:
    pct = paper.citation_normalized_percentile
    if pct is None and paper.cited_by_percentile is not None:
        pct = paper.cited_by_percentile / 100.0
    q = paper.journal_quartile or paper.sjr_best_quartile

    reasons: list[str] = []
    if paper.is_retracted:
        grade = "flagged"
        reasons.append("retracted")
    elif pct is None and q is None:
        grade = "ungraded"
        reasons.append("no citation or journal signal available")
    elif pct >= 0.90:
        grade = "high"
        reasons.append("top decile of citations for its subfield, type and year")
    elif pct >= 0.75 or q == 1:
        grade = "medium"
        if pct >= 0.75:
            reasons.append("strong field-normalized citations")
        if q == 1:
            reasons.append("journal in best quartile (context signal)")
    else:
        grade = "low"
        reasons.append("no strong article-level or top-quartile journal signal")

    if _young(paper.year):
        reasons.append("recent paper — citation window not yet mature")
    signals = {
        "pct": pct,
        "q": q,
        "q_scheme": "saj" if q is not None and paper.journal_quartile is None else "citescore",
        "design": _design(paper),
        "is_preprint": paper.is_preprint,
        "young": _young(paper.year),
        "reasons": reasons,
    }
    paper.quality_grade = grade
    paper.quality_signals = signals
    return paper
```

- [ ] **Step 3: Run tests until GREEN**

`.venv/bin/python -m pytest tests/test_quality.py -v` — PASS.

- [ ] **Step 4: Commit**

```bash
git add journal-scout/src/josc/quality.py journal-scout/tests/test_quality.py
git commit -m "feat(journal-scout): deterministic explainable paper quality grading"
```

---

### Task 3: CiteScore quartile derivation helper

**Files:**
- Create: `src/josc/quality.py` additions: `quartile_from_cite_score(bands: list[dict]) -> tuple[int | None, float | None]`
- Test: `tests/test_quality.py`

- [ ] **Step 1: Failing test**

```python
def test_best_quartile_from_cite_score_bands():
    # bands: [{"subject_area": "A", "citeScorePercentile": 90.2}, ...]
    # quartile from the best (highest) percentile band
    q, cs = quartile_from_cite_score([{"citeScorePercentile": 12.4}, {"citeScorePercentile": 81.9}])
    assert q == 1 and cs == 81.9

def test_below_75_is_quartile_3():
    q, _ = quartile_from_cite_score([{"citeScorePercentile": 60.0}])
    assert q == 3

def test_no_bands():
    assert quartile_from_cite_score([]) == (None, None)
```

- [ ] **Step 2: Implement** (in `quality.py`)

```python
def quartile_from_cite_score(bands: list[dict]) -> tuple[int | None, float | None]:
    """Q1 top-25% ... Q4 bottom, from CiteScore percentile (per subject area,
    best band wins — multidisciplinary journals belong to several areas)."""
    values = [b["citeScorePercentile"] for b in bands
              if b.get("citeScorePercentile") is not None]
    if not values:
        return None, None
    top = max(values)
    q = 1 if top >= 75.0 else 2 if top >= 50.0 else 3 if top >= 25.0 else 4
    return q, top
```

- [ ] **Step 3: Run tests GREEN, commit**

```bash
git add journal-scout/src/josc/quality.py journal-scout/tests/test_quality.py
git commit -m "feat(journal-scout): derive journal quartile from CiteScore bands"
```

---

### Task 4: Scopus Serial Title client with disk cache

**Files:**
- Modify: `src/josc/providers/scopus.py` (add `SerialTitleClient`), or new `src/josc/scopus_serials.py`
- Test: `tests/test_scopus_serials.py`

**Interfaces:**
- Produces `SerialTitleClient.get(issn: str) -> dict | None` returning `{"title": str, "issn": str, "quartile": int|None, "cite_score": float|None, "bands": [..]}`; transparent disk cache.

- [ ] **Step 1: Verify the live shape**

Using the deployment Scopus key (from `config.json` / `SCOPUS_API_KEY` — never print it), run one request and record the JSON:

```bash
.venv/bin/python - <<'PY'
import json, os, urllib.request
key = os.environ.get("SCOPUS_API_KEY") or json.load(open("config.json"))["api_key"]
req = urllib.request.Request(
    "https://api.elsevier.com/content/serial/title/issn/0097-5173?httpAccept=application/json&view=CITESCORE",
    headers={"X-Api-Key": key})
print(json.dumps(json.load(urllib.request.urlopen(req)), indent=1)[:4000])
PY
```

Expected: a serial-title record with a CiteScore section (current metric + percentile per subject area; field names per the docs at dev.elsevier.com/sc_serial_title_views.html). Note the actual key names (e.g. `citeScoreCurrentMetric`, subject-area percentile fields) — the parser in Step 3 must match them. If the endpoint returns 401/403, log the exact error; the client must degrade gracefully (no quartile, warning recorded), not raise.

- [ ] **Step 2: Failing tests**

`tests/test_scopus_serials.py` — mock the HTTP layer at the fetcher boundary (follow the provider test style):

```python
def test_get_parses_and_caches(tmp_path, monkeypatch):
    calls = []
    def fake_fetch(url, headers):
        calls.append(url)
        return {"title": {"displayname": "X"}, "serial_title": {"cite_score": {...}}}
    monkeypatch.setattr("...client._fetch", fake_fetch)
    c = SerialTitleClient(cache_dir=tmp_path)
    out1 = c.get("0097-5173")
    out2 = c.get("0097-5173")
    assert out1["quartile"] == out2["quartile"]
    assert len(calls) == 1  # second call served from cache

def test_http_errors_return_none(tmp_path, monkeypatch):
    def boom(url, headers): raise ProviderError("403")
    monkeypatch.setattr("...client._fetch", boom)
    assert SerialTitleClient(cache_dir=tmp_path).get("1234-5678") is None
```

- [ ] **Step 3: Implement the client**

- Base: `https://api.elsevier.com/content/serial/title/issn/{issn}` with `X-Api-Key` (reuse the provider's key plumbing) and `httpAccept=application/json`, `view=CITESCORE` (add the extra view only if Step 1 shows the fields are absent without it).
- Parse per Step 1's recorded shape → `quartile`, `cite_score` via `quartile_from_cite_score` from Task 3.
- Cache: `journal-scout/.cache/scopus-serials.json` — `{"<ISSN upper>": {"ts": <epoch>, "data": {...}}}`, TTL 90 days (7,776,000 s), write-through; add `journal-scout/.cache/` to `.gitignore` if not present.
- All 4xx/5xx and network errors → `None` (caller records the warning); never raise.
- Concurrency: wrap the file cache in `asyncio.Lock`; cap parallel lookups at 5 (like the existing provider concurrency patterns).

- [ ] **Step 4: Tests GREEN, commit**

```bash
git add journal-scout/src/josc/ journal-scout/tests/test_scopus_serials.py
git commit -m "feat(journal-scout): cached Scopus Serial Title CiteScore client"
```

---

### Task 5: Post-merge enrichment + `sort="quality"`

**Files:**
- Modify: `src/josc/aggregator.py`, `src/josc/providers/openalex.py` (expose a DOI-batch helper if `get_many` is provider-internal)
- Test: `tests/test_aggregator_quality.py`

- [ ] **Step 1: Failing tests**

```python
def test_enrichment_assigns_grades_to_merged_papers(fake_providers):
    # fake providers return papers; OpenAlex mock returns normalized pct;
    # scopus client mock returns a Q1 band
    result = asyncio.run(search_all(provs, "x", quality=True))
    assert all(p["quality_grade"] in {"high","medium","low","flagged","ungraded"}
               for p in result["results"])

def test_enrichment_failures_do_not_block_results(fake_providers, broken_openalex):
    result = asyncio.run(search_all(provs, "x", quality=True))
    assert result["results"] and "quality" in result.get("errors", {})
```

- [ ] **Step 2: Implement**

In `search_all`, after merge/sort is available and before returning:

```python
    if quality:
        _enrich_quality(papers, providers, errors)
        for paper in papers:
            grade_paper(paper)
        if sort == "quality":
            _SORT_FIELDS["quality"] = ...  # GRADE_ORDER then pct desc
```

`_enrich_quality`: collect DOIs not yet carrying `citation_normalized_percentile` → chunk ≤ 100 → OpenAlex works `filter=doi:...` (one request per chunk, select only the needed fields) → backfill `citation_normalized_percentile` onto matching merged papers by DOI. Collect distinct `issn` → `SerialTitleClient.get` (cache handles repeats) → backfill `journal_quartile`/`journal_cite_score`. Any provider-level failure → `errors["quality"] = "<what failed, N papers may be missing signals>"` and continue.

Add `"quality"` to `_SORT_FIELDS` mapping to `(GRADE_ORDER[grade or "ungraded"], -(pct or 0))`.

- [ ] **Step 3: Tests GREEN; commit**

```bash
git add journal-scout/src/josc/aggregator.py journal-scout/tests/test_aggregator_quality.py
git commit -m "feat(journal-scout): quality enrichment and sort for search_all"
```

---

### Task 6: MCP tool + REST surface

**Files:**
- Modify: `src/josc/server.py`, `src/josc/api/search_routes.py` (or the metrics routes module that hosts grouping helpers)
- Test: `tests/test_group_by_quality.py`

- [ ] **Step 1: Failing test**

```python
def test_group_by_quality_returns_groups(fake_search):
    out = asyncio.run(group_by_quality(provs, "x"))
    assert set(out["groups"]) <= {"high","medium","low","flagged","ungraded"}
    assert out["groups"]["high"]["count"] == len(out["groups"]["high"]["papers"])
```

- [ ] **Step 2: Implement**

- `group_by_quality(providers, query, **search_kwargs)` in the aggregator: run `search_all(..., quality=True)`, bucket results by `quality_grade`, return `{groups: {grade: {count, papers, dominant_signals}}}` where `dominant_signals` summarizes the most common reasons/quartiles in that bucket (max 3).
- Register MCP tool `group_by_quality` in `server.py` (docstring: returns papers grouped by explainable quality class; article-level signals dominate, journal quartile is context, retracted papers are always in `flagged`).
- REST: forward `sort="quality"` through the existing `/search` route (add it to the accepted values), and add `GET /search/groups/quality?query=...` mirroring the tool.

- [ ] **Step 3: Tests GREEN; commit**

```bash
git add journal-scout/src/josc/server.py journal-scout/src/josc/api/ journal-scout/tests/test_group_by_quality.py
git commit -m "feat(journal-scout): group_by_quality tool and quality sort"
```

---

### Task 7: Web UI — grade chips, grouping, sort

**Files:**
- Modify: `web/src/lib/types.ts` (extend `Paper` with `issn`, `citation_normalized_percentile`, `journal_quartile`, `journal_cite_score`, `quality_grade`, `quality_signals`), `web/src/components/PaperTable.tsx`, `web/src/components/search/SearchResults.tsx`, `web/src/components/search/SearchForm.tsx` (if that's where sort lives)
- Verify: `npm run typecheck && npm run build` in `web/`

- [ ] **Step 1: Types + chip**

`quality_grade` → colored chip (high=emerald, medium=sky, low=amber, flagged=rose, ungraded=slate) using the existing `Chip` component + `cn`; tooltip (native `title` + a hover panel if one already exists in `ui.tsx`) listing `quality_signals` reasons, `pct`, `q` (+scheme), design context, preprint/young flags. Retained papers show a "retracted" badge, not a normal chip.

- [ ] **Step 2: Grouping toggle**

In `SearchResults`, a toggle "Kelompokkan per kelas kualitas": when on, render results under per-grade section headers with counts (client-side bucketing of the same data — no extra request needed for the current search; the grouping tool exists for programmatic use).

- [ ] **Step 3: Sort option**

Add "Kualitas" to the sort control, mapping to `sort=quality`; when most visible results carry the young flag, show one small notice: "Sebagian paper masih baru — data sitasi belum matang."

- [ ] **Step 4: Verify and commit**

```bash
cd journal-scout/web && npm run typecheck && npm run build
git add journal-scout/web/src
git commit -m "feat(web): show paper quality grades with grouping and sort"
```

---

### Task 8: Final verification

- [ ] **Step 1: Full test suite** — `.venv/bin/python -m pytest` (all green; pre-existing Starlette/httpx warnings acceptable).
- [ ] **Step 2: End-to-end smoke** — run the server locally, `search_all` on a real query, confirm: grades present on cross-source results, `sort=quality` orders correctly, retracted paper (if any in results) lands in `flagged`, and a search with Scopus key removed degrades gracefully with `errors["quality"]`.
- [ ] **Step 3: Web review** — open the search page, verify chips, grouping, sort at ~1280px and ~390px.
- [ ] **Step 4: Trail check + commit any fixes**

```bash
trail check
git add -p && git commit -m "polish(journal-scout): quality grading fixes from e2e review"
```
