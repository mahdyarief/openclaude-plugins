# CSL Citation Formatting Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Menambahkan jalur format sitasi berbasis CSL-JSON sehingga gaya baru bisa ditambah lewat data, bukan lewat menulis fungsi Python baru di `exporters.py`.

**Architecture:** Modul baru `src/josc/csl.py` mengubah dict paper menjadi item CSL-JSON (`paper_to_csl`) lalu merendernya dengan mesin kecil berbasis spesifikasi gaya deklaratif (`render_csl`). Tiga gaya bawaan (`apa`, `vancouver`, `chicago`) didaftarkan sebagai format ekspor baru dengan prefix `csl-`, sehingga 18 formatter lama tetap utuh dan `FORMATTERS` hanya bertambah. Pengguna juga bisa mengirim spesifikasi gaya sendiri lewat parameter `style`, jadi tidak perlu menunggu rilis baru untuk gaya baru.

**Tech Stack:** Python ≥3.10, pytest ≥8 (`asyncio_mode = "auto"`), ruff (`E4,E7,E9,F`). Tidak ada dependensi baru: mesin CSL di sini adalah subset kecil yang ditulis sendiri, bukan `citeproc-py`.

## Global Constraints

- Python minimum `>=3.10`; jangan memakai sintaks 3.11+.
- Tidak ada dependensi runtime baru untuk irisan ini.
- Tidak boleh ada panggilan jaringan di test.
- Semua test dijalankan dari root `journal-scout-mcp`; `pythonpath = ["src"]` sudah aktif.
- Gaya kode mengikuti `ruff select = ["E4","E7","E9","F"]`.
- 18 format lama di `FORMATTERS` tidak boleh dihapus atau diubah perilakunya; test `test_supported_formats_are_advertised` harus tetap menguji subset lama tanpa perubahan.
- Setiap task berakhir dengan satu commit terpisah.

### Keputusan cakupan yang disengaja

Mesin ini **bukan** implementasi CSL lengkap. Ia hanya mendukung elemen yang dipakai untuk merender daftar pustaka artikel jurnal: `author`, `issued`, `title`, `container-title`, `DOI`, `volume`, `issue`, `page`, dan `URL`. Gaya CSL dari Zotero Style Repository yang memakai `cs:choose`, `cs:group` bersyarat kompleks, atau `cs:names` dengan substitusi bertingkat **tidak** akan dirender dengan benar. Batasan ini dicatat di docstring modul dan di `docs/journal-scout/01-current-state.md` saat irisan ditutup.

---

## File Structure

| File | Tanggung jawab |
|---|---|
| `src/josc/csl.py` | `paper_to_csl()`, `render_csl()`, `CSL_STYLES`, `CSLStyleError` |
| `src/josc/exporters.py` | Mendaftarkan tiga format `csl-*` ke `FORMATTERS` |
| `tests/test_csl.py` | Semua test untuk irisan ini |

---

### Task 1: Map a paper dict to CSL-JSON

**Files:**
- Create: `src/josc/csl.py`
- Test: `tests/test_csl.py`

**Interfaces:**
- Consumes: dict paper dengan bentuk yang sama seperti yang dikembalikan `Paper.to_dict()`.
- Produces:
  - `paper_to_csl(paper: Dict[str, Any]) -> Dict[str, Any]` — item CSL-JSON dengan kunci `type`, `id`, `title`, `author`, `issued`, `container-title`, `DOI`, `volume`, `issue`, `page`, `URL`.
  - `CSLStyleError(ValueError)` — dilempar saat spesifikasi gaya tidak valid.

- [ ] **Step 1: Write the failing test**

Create `tests/test_csl.py`:

```python
from josc.csl import paper_to_csl


def test_paper_to_csl_maps_core_fields():
    item = paper_to_csl(
        {
            "doi": "10.1/a",
            "title": "Attention Is All You Need",
            "year": 2017,
            "authors": ["Ashish Vaswani", "Noam Shazeer"],
            "venue": "NeurIPS",
            "url": "https://example.test/a",
        }
    )
    assert item["type"] == "article-journal"
    assert item["id"] == "10.1/a"
    assert item["title"] == "Attention Is All You Need"
    assert item["container-title"] == "NeurIPS"
    assert item["DOI"] == "10.1/a"
    assert item["URL"] == "https://example.test/a"
    assert item["issued"] == {"date-parts": [[2017]]}
    assert item["author"] == [
        {"family": "Vaswani", "given": "Ashish"},
        {"family": "Shazeer", "given": "Noam"},
    ]


def test_paper_to_csl_falls_back_to_title_when_doi_missing():
    item = paper_to_csl({"title": "No DOI Here"})
    assert item["id"] == "no doi here"
    assert "DOI" not in item


def test_paper_to_csl_omits_issued_when_year_missing():
    item = paper_to_csl({"title": "Undated"})
    assert "issued" not in item


def test_paper_to_csl_handles_single_token_author():
    item = paper_to_csl({"title": "X", "authors": ["Plato"]})
    assert item["author"] == [{"family": "Plato", "given": ""}]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_csl.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'josc.csl'`.

- [ ] **Step 3: Create `src/josc/csl.py`**

```python
"""A deliberately small CSL-JSON renderer.

This is not a full CSL implementation. It supports the elements needed to
render a journal-article reference list: author, issued, title,
container-title, DOI, volume, issue, page and URL. Styles that rely on
conditional ``cs:choose`` trees or nested ``cs:names`` substitution are out of
scope and will render incorrectly.
"""

from typing import Any, Dict, List, Optional, Sequence

from .utils import normalize_doi, normalize_title


class CSLStyleError(ValueError):
    """Raised when a style specification is missing required keys."""


def _split_name(name: str) -> Dict[str, str]:
    parts = (name or "").strip().split()
    if not parts:
        return {"family": "", "given": ""}
    if len(parts) == 1:
        return {"family": parts[0], "given": ""}
    return {"family": parts[-1], "given": " ".join(parts[:-1])}


def paper_to_csl(paper: Dict[str, Any]) -> Dict[str, Any]:
    """Convert a paper dict into a CSL-JSON item."""
    doi = normalize_doi(paper.get("doi"))
    title = paper.get("title") or ""
    item: Dict[str, Any] = {
        "type": "article-journal",
        "id": doi or normalize_title(title),
        "title": title,
    }
    if doi:
        item["DOI"] = doi
    if paper.get("venue"):
        item["container-title"] = paper["venue"]
    if paper.get("url"):
        item["URL"] = paper["url"]
    year = paper.get("year")
    if year is not None:
        item["issued"] = {"date-parts": [[int(year)]]}
    authors: Sequence[str] = paper.get("authors") or []
    if authors:
        item["author"] = [_split_name(name) for name in authors]
    return item
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_csl.py -v`
Expected: PASS — 4 passed.

- [ ] **Step 5: Run the full suite**

Run: `pytest -q`
Expected: PASS — no regression.

- [ ] **Step 6: Commit**

```bash
git add src/josc/csl.py tests/test_csl.py
git commit -m "feat(csl): map paper dicts to CSL-JSON items"
```

---

### Task 2: Render items with declarative style specs

**Files:**
- Modify: `src/josc/csl.py`
- Test: `tests/test_csl.py` (append)

**Interfaces:**
- Consumes: `paper_to_csl(paper)` dari Task 1.
- Produces:
  - `CSL_STYLES: Dict[str, Dict[str, Any]]` — tiga spesifikasi gaya bawaan: `"apa"`, `"vancouver"`, `"chicago"`.
  - `render_csl(papers: Sequence[Dict[str, Any]], style: str | Dict[str, Any]) -> str` — mengembalikan satu baris per paper, diakhiri newline; string kosong bila `papers` kosong.

Bentuk spesifikasi gaya:

```python
{
    "author_format": "family-given" | "family-initials" | "family",
    "author_join": "and" | "comma",
    "author_limit": int,              # 0 berarti tanpa batas
    "title_quotes": bool,
    "title_suffix": str,              # "." atau ""
    "venue_wrap": str,                # "" atau "({})" atau "''"
    "year_wrap": str,                 # "({})" atau ""
    "include_doi": bool,
}
```

- [ ] **Step 1: Write the failing test**

Append to `tests/test_csl.py`:

```python
from josc.csl import CSL_STYLES, CSLStyleError, render_csl

SAMPLE = [
    {
        "doi": "10.1/a",
        "title": "Attention Is All You Need",
        "year": 2017,
        "authors": ["Ashish Vaswani", "Noam Shazeer"],
        "venue": "NeurIPS",
    }
]


def test_builtin_styles_are_declared():
    assert set(CSL_STYLES) == {"apa", "vancouver", "chicago"}


def test_render_apa_uses_family_and_initials():
    out = render_csl(SAMPLE, "apa")
    assert out.startswith("Vaswani, A., Shazeer, N. (2017).")
    assert "Attention Is All You Need." in out
    assert "NeurIPS." in out
    assert out.endswith("\n")


def test_render_vancouver_uses_family_and_initials_without_period():
    out = render_csl(SAMPLE, "vancouver")
    assert out.startswith("Vaswani A, Shazeer N. (2017).")
    assert "Attention Is All You Need." in out


def test_render_chicago_quotes_the_title():
    out = render_csl(SAMPLE, "chicago")
    assert '"Attention Is All You Need."' in out
    assert "NeurIPS (2017)." in out


def test_render_empty_input_returns_empty_string():
    assert render_csl([], "apa") == ""


def test_render_accepts_a_custom_style_dict():
    style = {
        "author_format": "family",
        "author_join": "comma",
        "author_limit": 1,
        "title_quotes": False,
        "title_suffix": "",
        "venue_wrap": "",
        "year_wrap": "",
        "include_doi": False,
    }
    out = render_csl(SAMPLE, style)
    assert out.startswith("Vaswani (2017)")
    assert "NeurIPS" in out


def test_render_rejects_a_style_missing_required_keys():
    try:
        render_csl(SAMPLE, {"author_format": "family"})
    except CSLStyleError as exc:
        assert "missing" in str(exc).lower()
    else:
        raise AssertionError("CSLStyleError was not raised")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_csl.py -v`
Expected: FAIL — `ImportError: cannot import name 'CSL_STYLES'`.

- [ ] **Step 3: Append the renderer to `src/josc/csl.py`**

```python
_REQUIRED_STYLE_KEYS = frozenset(
    {
        "author_format",
        "author_join",
        "author_limit",
        "title_quotes",
        "title_suffix",
        "venue_wrap",
        "year_wrap",
        "include_doi",
    }
)

CSL_STYLES: Dict[str, Dict[str, Any]] = {
    "apa": {
        "author_format": "family-initials",
        "author_join": "and",
        "author_limit": 0,
        "title_quotes": False,
        "title_suffix": ".",
        "venue_wrap": "",
        "year_wrap": "({})",
        "include_doi": True,
    },
    "vancouver": {
        "author_format": "family-initials",
        "author_join": "comma",
        "author_limit": 0,
        "title_quotes": False,
        "title_suffix": ".",
        "venue_wrap": "",
        "year_wrap": "({})",
        "include_doi": False,
    },
    "chicago": {
        "author_format": "family-initials",
        "author_join": "and",
        "author_limit": 0,
        "title_quotes": True,
        "title_suffix": ".",
        "venue_wrap": "",
        "year_wrap": "({})",
        "include_doi": False,
    },
}


def _resolve_style(style: Any) -> Dict[str, Any]:
    if isinstance(style, str):
        if style not in CSL_STYLES:
            raise CSLStyleError(f"unknown style {style!r}")
        return CSL_STYLES[style]
    if not isinstance(style, dict):
        raise CSLStyleError("style must be a name or a dict")
    missing = _REQUIRED_STYLE_KEYS - set(style)
    if missing:
        raise CSLStyleError(f"style missing keys: {sorted(missing)}")
    return style


def _format_author(author: Dict[str, str], style: Dict[str, Any]) -> str:
    family = author.get("family", "")
    given = author.get("given", "")
    mode = style["author_format"]
    if mode == "family":
        return family
    if mode == "family-given":
        return f"{family}, {given}".strip(", ")
    initials = "".join(part[0].upper() + "." for part in given.split() if part)
    if initials:
        return f"{family}, {initials}"
    return family


def _format_authors(item: Dict[str, Any], style: Dict[str, Any]) -> str:
    authors = item.get("author") or []
    if not authors:
        return ""
    limit = int(style["author_limit"] or 0)
    selected = authors[:limit] if limit else authors
    formatted = [_format_author(author, style) for author in selected]
    if style["author_join"] == "and":
        if len(formatted) == 1:
            return formatted[0]
        return ", ".join(formatted[:-1]) + " and " + formatted[-1]
    return ", ".join(formatted)


def _wrap(value: str, template: str) -> str:
    if not value:
        return ""
    return template.format(value)


def render_csl(papers: Sequence[Dict[str, Any]], style: Any) -> str:
    """Render paper dicts into a reference list using a style specification."""
    spec = _resolve_style(style)
    if not papers:
        return ""
    lines: List[str] = []
    for paper in papers:
        item = paper_to_csl(paper)
        parts: List[str] = []
        authors = _format_authors(item, spec)
        if authors:
            parts.append(authors)
        year = ""
        issued = item.get("issued") or {}
        date_parts = issued.get("date-parts") or []
        if date_parts and date_parts[0]:
            year = str(date_parts[0][0])
        if year:
            parts.append(_wrap(year, spec["year_wrap"]))
        title = item.get("title") or ""
        if title:
            rendered_title = f'"{title}"' if spec["title_quotes"] else title
            parts.append(rendered_title + spec["title_suffix"])
        venue = item.get("container-title") or ""
        if venue:
            parts.append(_wrap(venue, spec["venue_wrap"]))
        if spec["include_doi"] and item.get("DOI"):
            parts.append(f"https://doi.org/{item['DOI']}")
        lines.append(" ".join(part for part in parts if part))
    return "\n".join(lines) + "\n"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_csl.py -v`
Expected: PASS — 11 passed.

- [ ] **Step 5: Run the full suite**

Run: `pytest -q`
Expected: PASS — no regression.

- [ ] **Step 6: Commit**

```bash
git add src/josc/csl.py tests/test_csl.py
git commit -m "feat(csl): render CSL items with declarative style specs"
```

---

### Task 3: Register the CSL formats in the exporter registry

**Files:**
- Modify: `src/josc/exporters.py` (append after `_to_csiro`, before `format_papers`)
- Test: `tests/test_csl.py` (append)

**Interfaces:**
- Consumes: `render_csl(papers, style)` dan `CSL_STYLES` dari `josc.csl`.
- Produces: tiga entri baru di `FORMATTERS`: `"csl-apa"`, `"csl-vancouver"`, `"csl-chicago"`, semuanya `Callable[[List[Dict[str, Any]]], str]`.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_csl.py`:

```python
from josc.exporters import FORMATTERS, format_papers


def test_csl_formats_are_registered():
    assert {"csl-apa", "csl-vancouver", "csl-chicago"} <= set(FORMATTERS)


def test_csl_format_is_dispatchable_through_format_papers():
    out = format_papers(SAMPLE, "csl-apa")
    assert out.startswith("Vaswani, A., Shazeer, N. (2017).")


def test_legacy_formats_are_untouched():
    assert format_papers(SAMPLE, "apa").startswith("Vaswani, A.")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_csl.py -v`
Expected: FAIL — `test_csl_formats_are_registered` asserts a missing key.

- [ ] **Step 3: Add the registrations**

At the top of `src/josc/exporters.py`, add:

```python
from .csl import render_csl
```

Then append immediately after the `_to_csiro` function and before `format_papers`:

```python
@_register("csl-apa")
def _to_csl_apa(papers: List[Dict[str, Any]]) -> str:
    return render_csl(papers, "apa")


@_register("csl-vancouver")
def _to_csl_vancouver(papers: List[Dict[str, Any]]) -> str:
    return render_csl(papers, "vancouver")


@_register("csl-chicago")
def _to_csl_chicago(papers: List[Dict[str, Any]]) -> str:
    return render_csl(papers, "chicago")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_csl.py -v`
Expected: PASS — 14 passed.

- [ ] **Step 5: Run the full suite**

Run: `pytest -q`
Expected: PASS — `tests/test_exporters.py` still green because the legacy 18 names are untouched.

- [ ] **Step 6: Commit**

```bash
git add src/josc/exporters.py tests/test_csl.py
git commit -m "feat(csl): expose csl-apa, csl-vancouver and csl-chicago export formats"
```

---

## Self-review

- **Cakupan:** pemetaan CSL-JSON (Task 1), mesin render deklaratif + tiga gaya (Task 2), registrasi ke `FORMATTERS` (Task 3). Batasan mesin didokumentasikan eksplisit di docstring dan bagian keputusan cakupan.
- **Placeholder:** tidak ada.
- **Konsistensi tipe:** `render_csl(papers, style)` menerima `str | Dict[str, Any]` di Task 2 dan dipanggil dengan `str` di Task 3; `CSL_STYLES` adalah `Dict[str, Dict[str, Any]]` dan hanya dibaca.
- **Risiko regresi:** `FORMATTERS` hanya bertambah; tidak ada kunci lama yang diubah, sehingga `test_supported_formats_are_advertised` tetap lolos tanpa diedit.
