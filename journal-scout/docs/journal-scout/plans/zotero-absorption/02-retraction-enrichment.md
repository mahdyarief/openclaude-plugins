# Retraction Enrichment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Mengubah `Paper.is_retracted` dari boolean telanjang menjadi payload retraksi terstruktur (alasan, DOI notice, tanggal, flag) tanpa memutus kompatibilitas field lama.

**Architecture:** `Paper` mendapat field baru `retraction: RetractionInfo | None`. `RetractionInfo` adalah dataclass murni di `src/josc/retractions.py`, bersama taksonomi 111 kunci alasan Retraction Watch yang diport dari `retractions.js:1048-1160`. Provider Crossref mengisi payload ini dari array `update-to`; `merge_two` memilih payload terlengkap. `is_retracted` tetap ada dan disinkronkan, sehingga pemanggil lama tidak berubah.

**Tech Stack:** Python ≥3.10, pytest ≥8 (`asyncio_mode = "auto"`), ruff (`E4,E7,E9,F`).

## Global Constraints

- Python minimum `>=3.10`; jangan memakai sintaks 3.11+.
- Tidak ada dependensi runtime baru.
- Tidak boleh ada panggilan jaringan di test.
- Semua test dijalankan dari root `journal-scout-mcp`; `pythonpath = ["src"]` sudah aktif.
- Gaya kode mengikuti `ruff select = ["E4","E7","E9","F"]`.
- `Paper.is_retracted: bool | None` tidak boleh dihapus atau diubah tipenya.
- Setiap task berakhir dengan satu commit terpisah.

### Keputusan cakupan yang disengaja

Zotero menyimpan 111 kunci alasan **beserta paragraf penjelasan panjang**. Plan ini hanya memport **kunci** sebagai identifier kanonik dan tidak menyalin paragraf penjelasan ke dalam repo, karena (a) paragraf itu milik Retraction Watch dan berubah mengikuti kebijakan mereka, dan (b) 111 paragraf akan menambah ~16 KB teks statis tanpa dipakai oleh logika apa pun. Konsekuensi yang diterima: `retraction.reasons` berisi kunci kanonik, bukan kalimat penjelasan. Jika kelak UI butuh kalimat penjelasan, tambahkan modul terpisah yang memuat teks dari sumber resmi.

---

## File Structure

| File | Tanggung jawab |
|---|---|
| `src/josc/retractions.py` | `RetractionInfo`, `RETRACTION_REASON_KEYS`, `normalize_reason()` |
| `src/josc/models.py` | Field `Paper.retraction` dan ekspornya di `to_dict()` |
| `src/josc/providers/crossref.py` | Mengisi `RetractionInfo` dari `update-to` |
| `src/josc/merge.py` | Memilih payload retraksi terlengkap saat merge |
| `tests/test_retractions.py` | Semua test untuk irisan ini |

---

### Task 1: Introduce `RetractionInfo` and the reason taxonomy

**Files:**
- Create: `src/josc/retractions.py`
- Test: `tests/test_retractions.py`

**Interfaces:**
- Consumes: hanya standard library (`dataclasses`, `typing`).
- Produces:
  - `RETRACTION_REASON_KEYS: frozenset[str]` — 111 kunci kanonik.
  - `normalize_reason(value: str | None) -> str | None` — kunci kanonik bila cocok case-insensitively, selain itu `None`.
  - `RetractionInfo` dataclass dengan field `reasons: list[str]`, `notice_doi: str | None`, `notice_url: str | None`, `notice_date: str | None`, `source: str | None`.
  - `RetractionInfo.to_dict() -> dict`.

- [x] **Step 1: Write the failing test**

Create `tests/test_retractions.py`:

```python
from josc.retractions import (
    RETRACTION_REASON_KEYS,
    RetractionInfo,
    normalize_reason,
)


def test_taxonomy_matches_zotero_key_count():
    assert len(RETRACTION_REASON_KEYS) == 111


def test_taxonomy_contains_known_zotero_keys():
    assert "Duplication of/in Image" in RETRACTION_REASON_KEYS
    assert "Falsification/Fabrication of Data" in RETRACTION_REASON_KEYS
    assert "Paper Mill" in RETRACTION_REASON_KEYS


def test_normalize_reason_is_case_insensitive():
    assert normalize_reason("paper mill") == "Paper Mill"


def test_normalize_reason_returns_none_for_unknown_values():
    assert normalize_reason("Something Zotero Never Defined") is None
    assert normalize_reason(None) is None


def test_retraction_info_to_dict_is_json_safe():
    info = RetractionInfo(
        reasons=["Paper Mill"],
        notice_doi="10.1/notice",
        notice_url="https://example.test/notice",
        notice_date="2024-03-01",
        source="crossref",
    )
    assert info.to_dict() == {
        "reasons": ["Paper Mill"],
        "notice_doi": "10.1/notice",
        "notice_url": "https://example.test/notice",
        "notice_date": "2024-03-01",
        "source": "crossref",
    }
```

- [x] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_retractions.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'josc.retractions'`.

- [x] **Step 3: Create `src/josc/retractions.py`**

Create the module with this exact content. The key list is the verbatim set of reason names from Zotero 10.0.6 (`retractions.js:1049-1160`).

```python
"""Retraction metadata modelled on Zotero's ``retractions.js``.

Zotero maps each retraction to one or more canonical reason keys from the
Retraction Watch taxonomy. This module ships those keys as identifiers so a
consumer can group, filter or render them; the long human-readable paragraphs
that Zotero also carries are intentionally not vendored here.
"""

from dataclasses import dataclass, field
from typing import List, Optional

RETRACTION_REASON_KEYS = frozenset({
    "Author Unresponsive",
    "Bias Issues or Lack of Balance",
    "Breach of Policy by Author",
    "Cites Retracted Work",
    "Civil Proceedings",
    "Complaints about Author",
    "Complaints about Company/Institution",
    "Complaints about Third Party",
    "Compromised Peer Review",
    "Computer-Aided Content or Computer-Generated Content",
    "Concerns/Issues about Animal Welfare",
    "Concerns/Issues about Article",
    "Concerns/Issues about Authorship/Affiliation",
    "Concerns/Issues about Data",
    "Concerns/Issues about Human Subject Welfare",
    "Concerns/Issues about Image",
    "Concerns/Issues about Methods",
    "Concerns/Issues about Peer Review",
    "Concerns/Issues about Referencing/Attributions",
    "Concerns/Issues about Results and/or Conclusions",
    "Concerns/Issues about Third Party Involvement",
    "Conflict of Interest",
    "Contamination of Cell Lines/Tissues",
    "Contamination of Materials",
    "Copyright Claims",
    "Criminal Proceedings",
    "Date of Article and/or Notice Unknown",
    "Doing the Right Thing",
    "Duplication of Content through Error by Journal/Publisher",
    "Duplication of Data",
    "Duplication of/in Article",
    "Duplication of/in Image",
    "Duplication of Text",
    "EOC Lifted",
    "Error by Journal/Publisher",
    "Error by Third Party",
    "Error in Analyses",
    "Error in Cell Lines/Tissues",
    "Error in Data",
    "Error in Image",
    "Error in Materials",
    "Error in Methods",
    "Error in Results and/or Conclusions",
    "Error in Text",
    "Ethical Violations by Author",
    "Ethical Violations by Company/Institution/Third Party",
    "Euphemisms for Duplication",
    "Euphemisms for Misconduct",
    "Euphemisms for Plagiarism",
    "False/Forged Affiliation",
    "False/Forged Authorship",
    "Falsification/Fabrication of Data",
    "Falsification/Fabrication of Image",
    "Falsification/Fabrication of Results",
    "Hoax Paper",
    "Informed/Patient Consent - None/Withdrawn",
    "Investigation by Company/Institution",
    "Investigation by Journal/Publisher",
    "Investigation by ORI",
    "Investigation by Third Party",
    "Lack of Approval from Author",
    "Lack of Approval from Company/Institution",
    "Lack of Approval from Third Party",
    "Lack of IRB/IACUC Approval and/or Compliance",
    "Legal Reasons and/or Threats",
    "Manipulation of Data",
    "Manipulation of Images",
    "Manipulation of Results",
    "Miscommunication with/by Author",
    "Miscommunication with/by Company/Institution",
    "Miscommunication with/by Journal/Publisher",
    "Miscommunication with/by Third Party",
    "Misconduct by Author",
    "Misconduct by Company/Institution",
    "Misconduct by Third Party",
    "Misconduct - Official Investigation(s) and/or Finding(s)",
    "No Further Action",
    "Nonpayment of Fees and/or Refusal to Pay",
    "Notice - Lack of",
    "Notice - Limited or No Information",
    "Notice - Unable to Access via current resources",
    "Not Presented at Conference",
    "Objections by Author(s)",
    "Objections by Company/Institution",
    "Objections by Third Party",
    "Original Data and/or Images not Provided and/or not Available",
    "Paper Mill",
    "Plagiarism of Data",
    "Plagiarism of Image",
    "Plagiarism of/in Article",
    "Plagiarism of Text",
    "Publishing Ban",
    "Results Not Reproducible",
    "Retract and Replace",
    "Rogue Editor",
    "Sabotage of Materials/Methods",
    "Salami Slicing",
    "Taken from Dissertation/Thesis",
    "Taken via Peer Review",
    "Taken via Translation",
    "Temporary Removal",
    "Transfer of Copyright and/or Ownership",
    "Unreliable Data",
    "Unreliable Image",
    "Unreliable Results and/or Conclusions",
    "Updated to Correction",
    "Updated to Expression of Concern",
    "Updated to Retraction",
    "Upgrade/Update of Prior Notice(s)",
    "Withdrawn as Out of Date",
    "Withdrawn to Publish in Different Journal",
})

_REASON_BY_CASEFOLD = {key.casefold(): key for key in RETRACTION_REASON_KEYS}


def normalize_reason(value: Optional[str]) -> Optional[str]:
    """Return the canonical taxonomy key for ``value``, or ``None``."""
    if not value:
        return None
    return _REASON_BY_CASEFOLD.get(value.strip().casefold())


@dataclass
class RetractionInfo:
    """Structured retraction metadata attached to a paper."""

    reasons: List[str] = field(default_factory=list)
    notice_doi: Optional[str] = None
    notice_url: Optional[str] = None
    notice_date: Optional[str] = None
    source: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "reasons": self.reasons,
            "notice_doi": self.notice_doi,
            "notice_url": self.notice_url,
            "notice_date": self.notice_date,
            "source": self.source,
        }
```

- [x] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_retractions.py -v`
Expected: PASS — 5 passed.

- [x] **Step 5: Run the full suite**

Run: `pytest -q`
Expected: PASS — no regression.

- [x] **Step 6: Commit**

```bash
git add src/josc/retractions.py tests/test_retractions.py
git commit -m "feat(retractions): add reason taxonomy and structured payload"
```

---

### Task 2: Attach retraction metadata to `Paper`

**Files:**
- Modify: `src/josc/models.py:4-57`
- Test: `tests/test_retractions.py` (append)

**Interfaces:**
- Consumes: `RetractionInfo` dari `josc.retractions`.
- Produces: `Paper.retraction: RetractionInfo | None`, diekspor `Paper.to_dict()` sebagai kunci `"retraction"` berisi `dict | None`.

- [x] **Step 1: Write the failing test**

Append to `tests/test_retractions.py`:

```python
from josc.models import Paper


def test_paper_defaults_to_no_retraction_payload():
    paper = Paper(title="A Paper")
    assert paper.retraction is None
    assert paper.to_dict()["retraction"] is None


def test_paper_serializes_retraction_payload():
    paper = Paper(
        title="A Paper",
        is_retracted=True,
        retraction=RetractionInfo(reasons=["Paper Mill"], source="crossref"),
    )
    assert paper.to_dict()["retraction"] == {
        "reasons": ["Paper Mill"],
        "notice_doi": None,
        "notice_url": None,
        "notice_date": None,
        "source": "crossref",
    }
```

- [x] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_retractions.py -v`
Expected: FAIL — `TypeError: Paper.__init__() got an unexpected keyword argument 'retraction'`.

- [x] **Step 3: Add the field**

In `src/josc/models.py`, add the import at the top:

```python
from .retractions import RetractionInfo
```

Add the field immediately after `is_retracted`:

```python
    is_retracted: bool | None = None
    retraction: RetractionInfo | None = None
```

Add the serialization immediately after `"is_retracted"` in `to_dict()`:

```python
            "is_retracted": self.is_retracted,
            "retraction": self.retraction.to_dict() if self.retraction else None,
```

- [x] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_retractions.py -v`
Expected: PASS — 7 passed.

- [x] **Step 5: Run the full suite**

Run: `pytest -q`
Expected: PASS — no regression.

- [x] **Step 6: Commit**

```bash
git add src/josc/models.py tests/test_retractions.py
git commit -m "feat(retractions): carry structured retraction payload on Paper"
```

---

### Task 3: Parse Crossref `update-to` into `RetractionInfo`

**Files:**
- Modify: `src/josc/providers/crossref.py`
- Test: `tests/test_retractions.py` (append)

**Interfaces:**
- Consumes: `RetractionInfo`, `normalize_reason()` dari `josc.retractions`; `first_of()` dari `josc.utils`.
- Produces: `build_retraction(item: dict) -> RetractionInfo | None` — fungsi modul-level yang dapat diuji tanpa instance provider.

- [x] **Step 1: Write the failing test**

Append to `tests/test_retractions.py`:

```python
from josc.providers.crossref import build_retraction


def test_build_retraction_returns_none_without_update_to():
    assert build_retraction({"DOI": "10.1/a"}) is None


def test_build_retraction_reads_retraction_notice():
    item = {
        "DOI": "10.1/a",
        "update-to": [
            {
                "type": "retraction",
                "DOI": "10.1/notice",
                "updated": {"date-parts": [[2024, 3, 1]]},
                "label": "Retraction",
                "URL": "https://example.test/notice",
            }
        ],
    }
    info = build_retraction(item)
    assert info is not None
    assert info.notice_doi == "10.1/notice"
    assert info.notice_url == "https://example.test/notice"
    assert info.notice_date == "2024-03-01"
    assert info.source == "crossref"
    assert info.reasons == ["Updated to Retraction"]


def test_build_retraction_ignores_correction_updates():
    item = {"update-to": [{"type": "correction", "DOI": "10.1/fix"}]}
    assert build_retraction(item) is None


def test_build_retraction_ignores_unknown_reason_labels():
    item = {"update-to": [{"type": "retraction", "DOI": "10.1/n", "label": "Mystery"}]}
    info = build_retraction(item)
    assert info is not None
    assert info.reasons == []
```

- [x] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_retractions.py -v`
Expected: FAIL — `ImportError: cannot import name 'build_retraction'`.

- [x] **Step 3: Add the parser**

At the top of `src/josc/providers/crossref.py`, add:

```python
from ..retractions import RetractionInfo, normalize_reason
```

Then add this module-level function above the provider class:

```python
def build_retraction(item: dict) -> Optional[RetractionInfo]:
    """Build structured retraction metadata from a Crossref work record.

    Crossref lists notices under ``update-to``. Only ``retraction`` entries are
    treated as retractions; corrections and expressions of concern are not.
    """
    updates = item.get("update-to") or []
    for update in updates:
        if not isinstance(update, dict) or update.get("type") != "retraction":
            continue
        parts = ((update.get("updated") or {}).get("date-parts") or [[]])[0]
        notice_date = None
        if len(parts) == 3:
            notice_date = f"{int(parts[0]):04d}-{int(parts[1]):02d}-{int(parts[2]):02d}"
        reason = normalize_reason(update.get("label"))
        return RetractionInfo(
            reasons=[reason] if reason else [],
            notice_doi=normalize_doi(update.get("DOI")),
            notice_url=update.get("URL"),
            notice_date=notice_date,
            source="crossref",
        )
    return None
```

- [x] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_retractions.py -v`
Expected: PASS — 11 passed.

- [x] **Step 5: Run the full suite**

Run: `pytest -q`
Expected: PASS — no regression.

- [x] **Step 6: Commit**

```bash
git add src/josc/providers/crossref.py tests/test_retractions.py
git commit -m "feat(retractions): parse Crossref update-to notices"
```

---

### Task 4: Attach the payload in the Crossref provider and merge the richest one

**Files:**
- Modify: `src/josc/providers/crossref.py` (inside `_to_paper`)
- Modify: `src/josc/merge.py` (inside `merge_two`)
- Test: `tests/test_retractions.py` (append)

**Interfaces:**
- Consumes: `build_retraction(item)` dari Task 3; `merge_two(a, b)` yang sudah ada.
- Produces: `Paper.retraction` terisi dari Crossref; `merge_two` memilih payload dengan `reasons` terbanyak.

- [x] **Step 1: Write the failing test**

Append to `tests/test_retractions.py`:

```python
from josc.merge import merge_two
from josc.models import Paper


def test_crossref_provider_attaches_retraction_payload():
    from josc.providers.crossref import CrossrefProvider

    provider = CrossrefProvider(None)
    paper = provider._to_paper(
        {
            "DOI": "10.1/a",
            "title": ["A Paper"],
            "update-to": [{"type": "retraction", "DOI": "10.1/n", "label": "Retraction"}],
        }
    )
    assert paper.retraction is not None
    assert paper.retraction.notice_doi == "10.1/n"


def test_merge_two_keeps_the_richest_retraction_payload():
    thin = Paper(
        doi="10.1/a",
        title="P",
        retraction=RetractionInfo(reasons=["Updated to Retraction"], source="crossref"),
    )
    rich = Paper(
        doi="10.1/a",
        title="P",
        retraction=RetractionInfo(
            reasons=["Paper Mill", "Falsification/Fabrication of Data"],
            notice_doi="10.1/n",
            source="crossref",
        ),
    )
    merged = merge_two(thin, rich)
    assert merged.retraction is not None
    assert merged.retraction.notice_doi == "10.1/n"
    assert len(merged.retraction.reasons) == 2


def test_merge_two_syncs_is_retracted_from_payload():
    plain = Paper(doi="10.1/a", title="P")
    flagged = Paper(
        doi="10.1/a",
        title="P",
        retraction=RetractionInfo(reasons=["Paper Mill"], source="crossref"),
    )
    merged = merge_two(plain, flagged)
    assert merged.is_retracted is True
```

- [x] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_retractions.py -v`
Expected: FAIL — `paper.retraction is None`.

- [x] **Step 3: Attach in the provider**

In `src/josc/providers/crossref.py`, inside `_to_paper`, add this line beside the other extracted locals:

```python
        retraction = build_retraction(item)
```

Then pass it to `Paper(...)` immediately after `is_retracted=...`:

```python
            retraction=retraction,
```

If `_to_paper` does not currently set `is_retracted`, add it in the same constructor call:

```python
            is_retracted=True if retraction else None,
```

- [x] **Step 4: Merge the richest payload**

In `src/josc/merge.py`, inside `merge_two`, after the existing field merges and before `return`, add:

```python
    retraction = _richest_retraction(a.retraction, b.retraction)
    if retraction is not None:
        merged.retraction = retraction
        merged.is_retracted = True
```

Then add this helper above `merge_two`:

```python
def _richest_retraction(left, right):
    """Return the retraction payload carrying the most reason keys."""
    if left is None:
        return right
    if right is None:
        return left
    return left if len(left.reasons) >= len(right.reasons) else right
```

- [x] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_retractions.py -v`
Expected: PASS — 14 passed.

- [x] **Step 6: Run the full suite**

Run: `pytest -q`
Expected: PASS — no regression.

- [x] **Step 7: Commit**

```bash
git add src/josc/providers/crossref.py src/josc/merge.py tests/test_retractions.py
git commit -m "feat(retractions): attach and merge structured retraction payloads"
```

---

## Self-review

- **Cakupan:** taksonomi (Task 1), model + serialisasi (Task 2), parser Crossref (Task 3), integrasi provider + merge (Task 4). Semua klaim dari `retractions.js` terpakai.
- **Placeholder:** tidak ada; setiap step punya kode dan perintah nyata.
- **Konsistensi tipe:** `RetractionInfo.reasons: list[str]` dipakai konsisten di Task 1, 2, 3, dan 4; `build_retraction` mengembalikan `Optional[RetractionInfo]` dan dipakai apa adanya.
