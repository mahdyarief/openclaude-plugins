# Full-Text Search Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Menambahkan pencarian teks penuh atas korpus paper yang sudah tersimpan di arsip pencarian, sehingga pengguna bisa menemukan kembali paper berdasarkan kata di judul, abstrak, venue, atau penulis tanpa memanggil provider lagi.

**Architecture:** Modul baru `src/josc/fulltext.py` berisi tiga fungsi murni: `tokenize()` menormalkan teks, `build_index()` membangun inverted index dari daftar dict paper, dan `search_index()` menjalankan kueri AND dengan skor sederhana. `src/josc/corpus.py` memuat paper dari `SearchArchive` yang sudah ada (tanpa jaringan). Tool MCP `search_corpus` merangkai keduanya. Tidak ada database FTS5 baru: indeks dibangun ulang di memori setiap pemanggilan, karena korpus hasil pencarian berukuran kecil (ratusan hingga beberapa ribu record) dan selalu bisa direkonstruksi dari arsip.

**Tech Stack:** Python ≥3.10, pytest ≥8 (`asyncio_mode = "auto"`), ruff (`E4,E7,E9,F`). Tanpa dependensi baru.

## Global Constraints

- Python minimum `>=3.10`; jangan memakai sintaks 3.11+.
- Tidak ada dependensi runtime baru dan tidak ada ekstensi SQLite FTS5.
- Tidak boleh ada panggilan jaringan di test; pemuatan korpus memakai arsip palsu.
- Semua test dijalankan dari root `journal-scout-mcp`; `pythonpath = ["src"]` sudah aktif.
- Gaya kode mengikuti `ruff select = ["E4","E7","E9","F"]`.
- Setiap task berakhir dengan satu commit terpisah.

### Keputusan cakupan yang disengaja

Zotero memakai FTS5 contentless di database terpisah (`fulltext.sqlite`) dengan tokenizer khusus, tabel CJK terpisah, antrean reindex latar belakang, dan normalisasi catatan. Plan ini **tidak** memport itu. Yang diambil hanya idenya: normalisasi teks + indeks yang bisa dibangun ulang. Konsekuensi yang diterima: (a) pencarian hanya mencakup field metadata paper yang sudah tersimpan di arsip, bukan isi PDF; (b) tidak ada stemming atau pencarian frase; (c) korpus dibangun ulang setiap panggilan sehingga biayanya linear terhadap jumlah paper tersimpan. Jika kelak isi PDF perlu dicari, irisan 04 (`extract_pdf_text`) bisa menyuplai teks ke `build_index()` tanpa mengubah mesin pencarian.

---

## File Structure

| File | Tanggung jawab |
|---|---|
| `src/josc/fulltext.py` | `tokenize()`, `build_index()`, `search_index()` — fungsi murni |
| `src/josc/corpus.py` | `load_corpus(archive)` — memuat paper dari arsip, tanpa jaringan |
| `src/josc/server.py` | Tool MCP `search_corpus` |
| `tests/test_fulltext.py` | Semua test untuk irisan ini |

---

### Task 1: Tokenizer, index builder and AND search

**Files:**
- Create: `src/josc/fulltext.py`
- Test: `tests/test_fulltext.py`

**Interfaces:**
- Consumes: hanya standard library (`re`, `typing`).
- Produces:
  - `tokenize(text: str) -> list[str]` — huruf kecil, hanya `[a-z0-9]`, kata dengan panjang ≥3.
  - `build_index(papers: Sequence[dict]) -> dict[str, list[int]]` — memetakan token ke daftar posisi paper.
  - `search_index(index: dict[str, list[int]], papers: Sequence[dict], query: str) -> list[dict]` — paper yang memuat **semua** token kueri, diurutkan berdasarkan jumlah kemunculan lalu judul.

- [x] **Step 1: Write the failing test**

Create `tests/test_fulltext.py`:

```python
from josc.fulltext import build_index, search_index, tokenize


def test_tokenize_lowercases_and_drops_short_tokens():
    assert tokenize("Deep Learning: A Survey!") == ["deep", "learning", "survey"]


def test_tokenize_handles_punctuation_and_numbers():
    assert tokenize("BERT-2 vs GPT3, 2023") == ["bert", "gpt3", "2023"]


def test_tokenize_returns_empty_list_for_blank_input():
    assert tokenize("   ") == []


def test_build_index_maps_tokens_to_paper_positions():
    papers = [
        {"title": "Deep Learning"},
        {"title": "Deep Reinforcement Learning"},
    ]
    index = build_index(papers)
    assert index["deep"] == [0, 1]
    assert index["reinforcement"] == [1]


def test_search_index_requires_every_token():
    papers = [
        {"title": "Deep Learning", "abstract": "neural networks"},
        {"title": "Deep Learning", "abstract": "bayesian inference"},
    ]
    index = build_index(papers)
    hits = search_index(index, papers, "deep bayesian")
    assert len(hits) == 1
    assert hits[0]["abstract"] == "bayesian inference"


def test_search_index_returns_empty_for_unknown_token():
    papers = [{"title": "Deep Learning"}]
    assert search_index(build_index(papers), papers, "quantum") == []


def test_search_index_ranks_more_matches_higher():
    papers = [
        {"title": "Learning", "abstract": "learning learning"},
        {"title": "Learning", "abstract": "learning once"},
    ]
    index = build_index(papers)
    hits = search_index(index, papers, "learning")
    assert hits[0]["abstract"] == "learning learning"
```

- [x] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_fulltext.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'josc.fulltext'`.

- [x] **Step 3: Create `src/josc/fulltext.py`**

```python
"""In-memory full-text search over a paper corpus.

This is a deliberately small replacement for an FTS5 index. It tokenizes the
searchable fields of each paper, builds an inverted index, and answers AND
queries. The index is rebuilt from the stored corpus on demand, so nothing here
needs a schema migration or a background reindex queue.
"""

import re
from typing import Any, Dict, List, Sequence

_TOKEN_PATTERN = re.compile(r"[a-z0-9]+")

_SEARCHABLE_FIELDS = ("title", "abstract", "venue", "tldr")


def tokenize(text: str) -> List[str]:
    """Return lowercase alphanumeric tokens of length three or more."""
    if not text:
        return []
    return [token for token in _TOKEN_PATTERN.findall(text.lower()) if len(token) > 2]


def _paper_tokens(paper: Dict[str, Any]) -> List[str]:
    tokens: List[str] = []
    for field in _SEARCHABLE_FIELDS:
        tokens.extend(tokenize(paper.get(field) or ""))
    for author in paper.get("authors") or []:
        tokens.extend(tokenize(author))
    for keyword in paper.get("keywords") or []:
        tokens.extend(tokenize(keyword))
    return tokens


def build_index(papers: Sequence[Dict[str, Any]]) -> Dict[str, List[int]]:
    """Map each token to the positions of the papers that contain it."""
    index: Dict[str, List[int]] = {}
    for position, paper in enumerate(papers):
        for token in set(_paper_tokens(paper)):
            index.setdefault(token, []).append(position)
    return index


def search_index(
    index: Dict[str, List[int]],
    papers: Sequence[Dict[str, Any]],
    query: str,
) -> List[Dict[str, Any]]:
    """Return papers containing every query token, best match first."""
    query_tokens = tokenize(query)
    if not query_tokens:
        return []

    candidates = set(index.get(query_tokens[0], []))
    for token in query_tokens[1:]:
        candidates &= set(index.get(token, []))
    if not candidates:
        return []

    scored = []
    for position in candidates:
        tokens = _paper_tokens(papers[position])
        score = sum(tokens.count(token) for token in query_tokens)
        scored.append((score, papers[position].get("title") or "", position))
    scored.sort(key=lambda item: (-item[0], item[1]))
    return [papers[position] for _score, _title, position in scored]
```

- [x] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_fulltext.py -v`
Expected: PASS — 7 passed.

- [x] **Step 5: Run the full suite**

Run: `pytest -q`
Expected: PASS — no regression.

- [x] **Step 6: Commit**

```bash
git add src/josc/fulltext.py tests/test_fulltext.py
git commit -m "feat(fulltext): add tokenizer, inverted index and AND search"
```

---

### Task 2: Load the stored corpus without touching the network

**Files:**
- Create: `src/josc/corpus.py`
- Test: `tests/test_fulltext.py` (append)

**Interfaces:**
- Consumes: objek `SearchArchive` dengan `async list_searches(limit: int) -> list[dict]` dan `async get_search(search_id: str) -> dict | None`.
- Produces: `load_corpus(archive, limit: int = 20) -> list[dict]` — async; menggabungkan `results` dari semua arsip yang dimuat, membuang entri duplikat berdasarkan DOI/judul ternormalisasi, dan mempertahankan urutan kemunculan pertama.

- [x] **Step 1: Write the failing test**

Append to `tests/test_fulltext.py`:

```python
from josc.corpus import load_corpus


class FakeArchive:
    def __init__(self, searches):
        self.searches = searches

    async def list_searches(self, limit=20):
        return [
            {"id": search_id, "query": "q", "result_count": len(results)}
            for search_id, results in self.searches.items()
        ][:limit]

    async def get_search(self, search_id):
        if search_id not in self.searches:
            return None
        return {"id": search_id, "results": self.searches[search_id]}


async def test_load_corpus_flattens_and_dedupes_results():
    archive = FakeArchive(
        {
            "s1": [
                {"doi": "10.1/a", "title": "One"},
                {"doi": "10.1/b", "title": "Two"},
            ],
            "s2": [
                {"doi": "https://doi.org/10.1/A", "title": "One (again)"},
                {"title": "Untitled Paper"},
            ],
        }
    )
    corpus = await load_corpus(archive)
    assert len(corpus) == 3
    assert [paper["title"] for paper in corpus] == ["One", "Two", "Untitled Paper"]


async def test_load_corpus_returns_empty_when_archive_is_empty():
    assert await load_corpus(FakeArchive({})) == []
```

- [x] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_fulltext.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'josc.corpus'`.

- [x] **Step 3: Create `src/josc/corpus.py`**

```python
"""Assemble a searchable paper corpus from the local search archive.

The archive already stores the results of every recorded search, so building a
corpus needs no provider calls. Records are deduplicated by DOI when present and
by normalized title otherwise, matching the identity rule used elsewhere.
"""

from typing import Any, Dict, List

from .utils import normalize_doi, normalize_title


def _paper_key(paper: Dict[str, Any]) -> str:
    doi = normalize_doi(paper.get("doi"))
    if doi:
        return f"doi:{doi}"
    return f"title:{normalize_title(paper.get('title'))}"


async def load_corpus(archive: Any, limit: int = 20) -> List[Dict[str, Any]]:
    """Return deduplicated papers from the most recent archived searches."""
    corpus: List[Dict[str, Any]] = []
    seen = set()
    for entry in await archive.list_searches(limit=limit):
        stored = await archive.get_search(entry["id"])
        if not stored:
            continue
        for paper in stored.get("results") or []:
            key = _paper_key(paper)
            if key in seen:
                continue
            seen.add(key)
            corpus.append(paper)
    return corpus
```

- [x] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_fulltext.py -v`
Expected: PASS — 9 passed.

- [x] **Step 5: Run the full suite**

Run: `pytest -q`
Expected: PASS — no regression.

- [x] **Step 6: Commit**

```bash
git add src/josc/corpus.py tests/test_fulltext.py
git commit -m "feat(fulltext): load a deduplicated corpus from the search archive"
```

---

### Task 3: Expose `search_corpus` as an MCP tool

**Files:**
- Modify: `src/josc/server.py` (`UNIFIED_TOOLS`, `_tool_list()`, `build_json`)
- Test: `tests/test_server.py` (append)

**Interfaces:**
- Consumes: `load_corpus(archive, limit)` dari `josc.corpus`; `build_index()`, `search_index()` dari `josc.fulltext`; `_store()` dari `josc.api.state`; `SearchArchive` dari `josc.search_archive`.
- Produces: tool MCP `search_corpus` dengan argumen `{"query": str, "limit": int}`; hasilnya `{"query": str, "corpus_size": int, "results": list[dict]}`.

- [x] **Step 1: Write the failing test**

Append to `tests/test_server.py`:

```python
async def test_search_corpus_tool_is_registered():
    assert "search_corpus" in TOOL_NAMES
    schema = next(tool for tool in _tool_list() if tool.name == "search_corpus").inputSchema
    assert schema["required"] == ["query"]


async def test_search_corpus_filters_the_archived_corpus(monkeypatch):
    import josc.server as server

    async def fake_load_corpus(archive, limit=20):
        return [
            {"title": "Deep Learning", "abstract": "neural networks"},
            {"title": "Deep Learning", "abstract": "bayesian inference"},
        ]

    monkeypatch.setattr(server, "load_corpus", fake_load_corpus)

    result = await build_json("search_corpus", {"query": "deep bayesian"}, [], None)
    assert result["corpus_size"] == 2
    assert len(result["results"]) == 1
    assert result["results"][0]["abstract"] == "bayesian inference"
```

- [x] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_server.py -v`
Expected: FAIL — `assert "search_corpus" in TOOL_NAMES`.

- [x] **Step 3: Register the tool name and schema**

In `src/josc/server.py`, add `"search_corpus",` to `UNIFIED_TOOLS`. Then inside `_tool_list()`, append:

```python
        _search_tool(
            "search_corpus",
            "Search the locally archived search results by title, abstract, venue, author or keyword.",
            {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Whitespace-separated terms; every term must match.",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "How many recent archived searches to include.",
                        "default": 20,
                    },
                },
                "required": ["query"],
            },
        ),
```

- [x] **Step 4: Add the imports and the dispatch branch**

At the top of `src/josc/server.py`, add:

```python
from .corpus import load_corpus
from .fulltext import build_index, search_index
from .search_archive import SearchArchive
```

Inside `build_json`, before the `export_results` branch, add:

```python
    if name == "search_corpus":
        store = _store()
        if store is None:
            raise RuntimeError("Persistent archive store is not configured.")
        archive = SearchArchive(store)
        papers = await load_corpus(archive, limit=int(arguments.get("limit") or 20))
        index = build_index(papers)
        hits = search_index(index, papers, arguments["query"])
        return {
            "query": arguments["query"],
            "corpus_size": len(papers),
            "results": hits,
        }
```

- [x] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_server.py -v`
Expected: PASS — kedua test baru hijau.

- [x] **Step 6: Update the tool-count assertion**

In `tests/test_server.py`, bump `assert len(TOOL_NAMES) == 27` to `== 28` and add `assert "search_corpus" in TOOL_NAMES` (the count was already 27 after `check_watches` landed).

- [x] **Step 7: Run the full suite**

Run: `pytest -q`
Expected: PASS — semua suite hijau.

- [x] **Step 8: Commit**

```bash
git add src/josc/server.py tests/test_server.py
git commit -m "feat(fulltext): expose search_corpus MCP tool"
```

---

## Self-review

- **Cakupan:** tokenizer + inverted index + AND search (Task 1), pemuatan korpus dari arsip tanpa jaringan (Task 2), eksposur tool MCP (Task 3). Keputusan untuk tidak memakai FTS5 dijelaskan eksplisit di bagian keputusan cakupan.
- **Placeholder:** tidak ada; setiap step punya kode dan perintah nyata.
- **Konsistensi tipe:** `build_index()` dan `search_index()` menerima `Sequence[dict]` dan mengembalikan `dict`/`list[dict]`; `load_corpus()` async dan mengembalikan `list[dict]`; Task 3 memakai keduanya dengan bentuk yang sama.
- **Risiko regresi:** penambahan tool mengubah `len(TOOL_NAMES)`, sehingga Task 3 secara eksplisit memperbarui assertion tersebut.
