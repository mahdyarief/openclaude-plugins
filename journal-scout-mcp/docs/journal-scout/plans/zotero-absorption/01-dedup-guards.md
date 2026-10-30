# Dedup Guards Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Mencegah `merge_papers` menggabungkan dua karya berbeda yang kebetulan memiliki judul sama, dengan port guard duplikasi Zotero (`duplicates.js:345-382`).

**Architecture:** Guard dipisah ke modul baru `src/josc/dedup.py` berisi fungsi murni `same_work(a, b)`. `merge_papers` diubah dari pencocokan berbasis index menjadi union-find: DOI yang sama selalu menggabungkan, lalu kandidat dikelompokkan per judul ternormalisasi dan disaring `same_work`. Field `isbn` ditambahkan ke `Paper` agar guard ISBN punya sumber data.

**Tech Stack:** Python ≥3.10, pytest ≥8 (`asyncio_mode = "auto"`), ruff (`E4,E7,E9,F`).

## Global Constraints

- Python minimum `>=3.10`; jangan memakai sintaks 3.11+.
- Tidak ada dependensi runtime baru untuk irisan ini.
- Tidak boleh ada panggilan jaringan di test; provider diuji dengan memanggil `_to_paper` langsung.
- Semua test dijalankan dari root `journal-scout-mcp`; `pythonpath = ["src"]` sudah aktif.
- Gaya kode mengikuti `ruff select = ["E4","E7","E9","F"]`.
- Field publik `Paper` yang sudah ada tidak boleh dihapus atau diubah tipenya.
- Setiap task berakhir dengan satu commit terpisah.

---

## File Structure

| File | Tanggung jawab |
|---|---|
| `src/josc/models.py` | Menambah field `isbn` dan mengekspornya di `to_dict()` |
| `src/josc/providers/crossref.py` | Mengisi `isbn` dari payload Crossref |
| `src/josc/dedup.py` | Fungsi murni `same_work()` dan helper kreator |
| `src/josc/merge.py` | Union-find + penyaringan guard di `merge_papers()` |
| `tests/test_dedup.py` | Semua test untuk irisan ini |

---

### Task 1: Add ISBN to the paper model and Crossref mapping

**Files:**
- Modify: `src/josc/models.py:6-57`
- Modify: `src/josc/providers/crossref.py:57-90`
- Test: `tests/test_dedup.py`

**Interfaces:**
- Consumes: `Paper` dataclass; `first_of()` dari `josc.utils`.
- Produces: `Paper.isbn: str | None`, diekspor `Paper.to_dict()` sebagai kunci `"isbn"`.

- [x] **Step 1: Write the failing test**

```python
from josc.models import Paper
from josc.providers.crossref import CrossrefProvider


def test_paper_to_dict_exposes_isbn():
    paper = Paper(title="A Book", isbn="978-3-16-148410-0")
    assert paper.to_dict()["isbn"] == "978-3-16-148410-0"


def test_crossref_reads_isbn_from_book_items():
    provider = CrossrefProvider(None)
    paper = provider._to_paper(
        {
            "DOI": "10.1/book",
            "title": ["A Book"],
            "ISBN": ["9783161484100"],
            "type": "book",
        }
    )
    assert paper.isbn == "9783161484100"
```

- [x] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_dedup.py -v`
Expected: FAIL — `TypeError: Paper.__init__() got an unexpected keyword argument 'isbn'`.

- [x] **Step 3: Add the field to the model**

In `src/josc/models.py`, add `isbn` immediately after `doi`:

```python
    doi: str | None = None
    isbn: str | None = None
```

Then add it to `to_dict()` immediately after `"doi"`:

```python
            "doi": self.doi,
            "isbn": self.isbn,
```

- [x] **Step 4: Populate ISBN in the Crossref provider**

In `src/josc/providers/crossref.py`, inside `_to_paper`, add this line next to the existing `doi = normalize_doi(item.get("DOI"))`:

```python
        isbn = first_of(item.get("ISBN"))
```

Then pass it to the `Paper(...)` constructor immediately after `doi=doi,`:

```python
            isbn=isbn,
```

- [x] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_dedup.py -v`
Expected: PASS — 2 passed.

- [x] **Step 6: Run the full suite**

Run: `pytest -q`
Expected: PASS — no regression.

- [x] **Step 7: Commit**

```bash
git add src/josc/models.py src/josc/providers/crossref.py tests/test_dedup.py
git commit -m "feat(dedup): carry ISBN on papers and Crossref records"
```

---

### Task 2: Implement the Zotero duplicate guard as a pure function

**Files:**
- Create: `src/josc/dedup.py`
- Test: `tests/test_dedup.py` (append)

**Interfaces:**
- Consumes: `Paper` dari `josc.models`; `normalize_doi()` dan `normalize_title()` dari `josc.utils`.
- Produces: `same_work(a: Paper, b: Paper) -> bool` — `True` hanya bila dua record dengan judul ternormalisasi sama benar-benar karya yang sama.

- [x] **Step 1: Write the failing test**

Append to `tests/test_dedup.py`:

```python
from josc.dedup import same_work
from josc.models import Paper


def test_same_work_rejects_conflicting_dois():
    a = Paper(doi="10.1/a", title="Same Title")
    b = Paper(doi="10.1/b", title="Same Title")
    assert same_work(a, b) is False


def test_same_work_rejects_conflicting_isbns():
    a = Paper(isbn="9783161484100", title="Same Title")
    b = Paper(isbn="9783161484117", title="Same Title")
    assert same_work(a, b) is False


def test_same_work_rejects_year_gap_greater_than_one():
    a = Paper(title="Same Title", year=2019)
    b = Paper(title="Same Title", year=2022)
    assert same_work(a, b) is False


def test_same_work_accepts_year_gap_of_one():
    a = Paper(title="Same Title", year=2019)
    b = Paper(title="Same Title", year=2020)
    assert same_work(a, b) is True


def test_same_work_matches_when_both_have_no_creators():
    a = Paper(title="Same Title")
    b = Paper(title="Same Title")
    assert same_work(a, b) is True


def test_same_work_rejects_when_only_one_side_has_creators():
    a = Paper(title="Same Title", authors=["Sepp Hochreiter"])
    b = Paper(title="Same Title")
    assert same_work(a, b) is False


def test_same_work_matches_on_last_name_and_first_initial():
    a = Paper(title="Same Title", authors=["Sepp Hochreiter"])
    b = Paper(title="Same Title", authors=["S. Hochreiter", "Jürgen Schmidhuber"])
    assert same_work(a, b) is True


def test_same_work_rejects_disjoint_creator_lists():
    a = Paper(title="Same Title", authors=["Sepp Hochreiter"])
    b = Paper(title="Same Title", authors=["Yann LeCun"])
    assert same_work(a, b) is False
```

- [x] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_dedup.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'josc.dedup'`.

- [x] **Step 3: Create `src/josc/dedup.py`**

```python
"""Duplicate guards ported from Zotero's ``duplicates.js``.

Two records that already share a normalized title are only the same work when
no identity field contradicts it. The rules mirror Zotero 10.0.6
(``duplicates.js:345-382``): a conflicting DOI or ISBN is decisive, a year gap
of more than one year is decisive, and creators must overlap on
last name plus first initial.
"""

from typing import Optional, Sequence, Tuple

from .models import Paper
from .utils import normalize_doi, normalize_title


def _creator_key(name: str) -> Optional[Tuple[str, str]]:
    """Return ``(normalized last name, first initial)`` for a display name."""
    parts = (name or "").strip().split()
    if not parts:
        return None
    last = normalize_title(parts[-1])
    initial = parts[0][0].lower() if len(parts) > 1 else ""
    return last, initial


def _creator_keys(authors: Sequence[str]) -> list[Tuple[str, str]]:
    keys = [_creator_key(name) for name in authors]
    return [key for key in keys if key is not None]


def same_work(a: Paper, b: Paper) -> bool:
    """Decide whether two same-titled records describe one work."""
    doi_a, doi_b = normalize_doi(a.doi), normalize_doi(b.doi)
    if doi_a and doi_b and doi_a != doi_b:
        return False

    if a.isbn and b.isbn and a.isbn != b.isbn:
        return False

    if a.year is not None and b.year is not None and abs(a.year - b.year) > 1:
        return False

    creators_a, creators_b = _creator_keys(a.authors), _creator_keys(b.authors)
    if not creators_a and not creators_b:
        return True
    if not creators_a or not creators_b:
        return False

    for last_a, initial_a in creators_a:
        for last_b, initial_b in creators_b:
            if last_a == last_b and initial_a == initial_b:
                return True
    return False
```

- [x] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_dedup.py -v`
Expected: PASS — 10 passed.

- [x] **Step 5: Run the full suite**

Run: `pytest -q`
Expected: PASS — no regression.

- [x] **Step 6: Commit**

```bash
git add src/josc/dedup.py tests/test_dedup.py
git commit -m "feat(dedup): port Zotero duplicate guards as same_work()"
```

---

### Task 3: Rewrite `merge_papers` as union-find behind the guards

**Files:**
- Modify: `src/josc/merge.py:28-51` (remove `_author_token` and `_match_keys`)
- Modify: `src/josc/merge.py:156-184` (`merge_papers`)
- Test: `tests/test_dedup.py` (append)

**Interfaces:**
- Consumes: `same_work(a: Paper, b: Paper) -> bool` dari `josc.dedup`; `merge_two(a, b) -> Paper` yang sudah ada.
- Produces: `merge_papers(papers: List[Paper]) -> List[Paper]` dengan signature dan urutan sort yang sama persis seperti sebelumnya.

- [x] **Step 1: Write the failing test**

Append to `tests/test_dedup.py`:

```python
from josc.merge import merge_papers


def test_merge_papers_keeps_distinct_works_with_identical_titles():
    papers = [
        Paper(doi="10.1/a", title="Editorial", year=2020, sources=["crossref"]),
        Paper(doi="10.1/b", title="Editorial", year=2020, sources=["scopus"]),
    ]
    merged = merge_papers(papers)
    assert len(merged) == 2


def test_merge_papers_still_folds_matching_doi():
    papers = [
        Paper(doi="10.1/a", title="Editorial", citation_count=1, sources=["crossref"]),
        Paper(doi="10.1/A", title="Editorial", citation_count=9, sources=["scopus"]),
    ]
    merged = merge_papers(papers)
    assert len(merged) == 1
    assert merged[0].citation_count == 9


def test_merge_papers_uses_year_tolerance_within_bucket():
    papers = [
        Paper(title="Untitled", year=2020, authors=["Sepp Hochreiter"]),
        Paper(title="Untitled", year=2021, authors=["S. Hochreiter"]),
        Paper(title="Untitled", year=2024, authors=["Sepp Hochreiter"]),
    ]
    merged = merge_papers(papers)
    assert len(merged) == 2


def test_merge_papers_joins_doi_less_record_to_its_doi_twin():
    papers = [
        Paper(doi="10.1/a", title="A Paper", year=2020, sources=["crossref"]),
        Paper(title="A Paper", year=2020, authors=["Sepp Hochreiter"]),
    ]
    merged = merge_papers(papers)
    assert len(merged) == 1
    assert merged[0].doi == "10.1/a"
```

- [x] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_dedup.py -v`
Expected: FAIL — `test_merge_papers_keeps_distinct_works_with_identical_titles` returns 1 merged record instead of 2.

- [x] **Step 3: Remove the superseded match keys**

Delete `_author_token` and `_match_keys` from `src/josc/merge.py` (the block currently spanning lines 28-51). No other module imports them; verify with:

```bash
grep -rn "_match_keys\|_author_token" src tests
```

Expected: no matches after the deletion.

- [x] **Step 4: Replace `merge_papers`**

Replace the whole body of `merge_papers` in `src/josc/merge.py` with:

```python
def merge_papers(papers: List[Paper]) -> List[Paper]:
    """Merge records that describe the same work.

    Identical normalized DOIs always merge. Everything else is bucketed by
    normalized title and then filtered through :func:`josc.dedup.same_work`, so
    two unrelated works that happen to share a title stay separate.
    """
    parent = list(range(len(papers)))

    def find(index: int) -> int:
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    def union(left: int, right: int) -> None:
        root_left, root_right = find(left), find(right)
        if root_left != root_right:
            parent[root_right] = root_left

    by_doi: Dict[str, int] = {}
    for index, paper in enumerate(papers):
        doi = normalize_doi(paper.doi)
        if not doi:
            continue
        if doi in by_doi:
            union(index, by_doi[doi])
        else:
            by_doi[doi] = index

    by_title: Dict[str, List[int]] = {}
    for index, paper in enumerate(papers):
        title = normalize_title(paper.title)
        if not title:
            continue
        for other in by_title.get(title, []):
            if same_work(papers[index], papers[other]):
                union(index, other)
        by_title.setdefault(title, []).append(index)

    groups: Dict[int, List[int]] = {}
    for index in range(len(papers)):
        groups.setdefault(find(index), []).append(index)

    merged: List[Paper] = []
    for indices in groups.values():
        combined = papers[indices[0]]
        for other in indices[1:]:
            combined = merge_two(combined, papers[other])
        merged.append(combined)

    merged.sort(key=lambda p: (-(p.citation_count or 0), -(p.year or 0), p.title or ""))
    return merged
```

Then add the import at the top of `src/josc/merge.py`:

```python
from .dedup import same_work
```

- [x] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_dedup.py -v`
Expected: PASS — 14 passed.

- [x] **Step 6: Run the full suite**

Run: `pytest -q`
Expected: PASS — `tests/test_merge.py` and `tests/test_api_routes.py` unchanged and green.

- [x] **Step 7: Commit**

```bash
git add src/josc/merge.py tests/test_dedup.py
git commit -m "feat(dedup): guard merge_papers with Zotero duplicate rules"
```

---

## Self-review

- **Cakupan:** field `isbn` (Task 1), guard murni `same_work()` (Task 2), dan integrasi union-find ke `merge_papers` (Task 3). Keempat aturan Zotero yang dirujuk di bagian bukti (`DOI mismatch`, `ISBN mismatch`, `year gap > 1`, `creator matching`) masing-masing punya test sendiri di Task 2.
- **Placeholder:** tidak ada; setiap step punya kode dan perintah nyata.
- **Konsistensi tipe:** `same_work(a: Paper, b: Paper) -> bool` didefinisikan di Task 2 dan dipakai apa adanya di Task 3; `Paper.isbn: str | None` didefinisikan di Task 1 dan dibaca di Task 2.
- **Risiko regresi:** `merge_papers` tetap mengembalikan `List[Paper]` dengan urutan sort yang sama; `tests/test_merge.py` yang sudah ada menjadi jaring pengaman, dan Task 3 Step 6 menjalankan seluruh suite sebelum commit.
