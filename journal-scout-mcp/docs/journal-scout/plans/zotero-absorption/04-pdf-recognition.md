# PDF Metadata Recognition Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Menambahkan kemampuan mengenali metadata paper dari file PDF lokal, sehingga pengguna bisa memberi josc sebuah PDF dan menerima record paper yang sudah ter-resolve ke sumber daring.

**Architecture:** Tiga lapis terpisah. `src/josc/pdf_text.py` mengekstrak teks dari PDF (satu-satunya bagian yang butuh dependensi eksternal, diimpor secara lazy). `src/josc/recognize.py` adalah logika murni yang bekerja pada string teks: mencari DOI lebih dulu, lalu jatuh ke judul. `src/josc/api/recognize_routes.py` + tool MCP `identify_paper` merangkai keduanya ke `aggregator.get_paper`. Karena logika inti tidak menyentuh PDF maupun jaringan, seluruh test berjalan tanpa `pypdf` dan tanpa HTTP.

**Tech Stack:** Python ≥3.10, pytest ≥8 (`asyncio_mode = "auto"`), ruff (`E4,E7,E9,F`), `pypdf>=4.0` sebagai extra opsional `pdf`.

## Global Constraints

- Python minimum `>=3.10`; jangan memakai sintaks 3.11+.
- `pypdf` hanya boleh diimpor di dalam fungsi, tidak di level modul, agar paket tetap bisa dipakai tanpa extra `pdf`.
- Tidak boleh ada panggilan jaringan di test; `recognize_document` diuji dengan provider palsu.
- Tidak boleh ada file PDF biner di repo test; ekstraksi teks diuji dengan menginjeksikan callable.
- Semua test dijalankan dari root `journal-scout-mcp`; `pythonpath = ["src"]` sudah aktif.
- Gaya kode mengikuti `ruff select = ["E4","E7","E9","F"]`.
- Setiap task berakhir dengan satu commit terpisah.

### Keputusan cakupan yang disengaja

Zotero memakai mesin PDF.js penuh plus heuristik `recognizeDocument.js` yang sangat panjang (ekstraksi blok teks, deteksi judul dari ukuran font, pemisahan penulis, pencocokan ke 748 translator). Plan ini **tidak** memport itu. Yang diambil hanya urutan strategi Zotero: DOI dulu, lalu judul. Konsekuensi: PDF hasil scan tanpa lapisan teks tidak akan dikenali, dan PDF tanpa DOI hanya dikenali bila baris judulnya bisa ditemukan secara heuristik sederhana. Batasan ini dicatat di docstring modul.

---

## File Structure

| File | Tanggung jawab |
|---|---|
| `src/josc/pdf_text.py` | `extract_pdf_text(path)` — pembungkus tipis `pypdf` dengan import lazy |
| `src/josc/recognize.py` | `find_doi()`, `guess_title()`, `recognize_document()` — logika murni |
| `src/josc/api/recognize_routes.py` | Handler `POST /api/identify` |
| `src/josc/api/app.py` | Registrasi route |
| `src/josc/api/__init__.py` | Re-export handler |
| `src/josc/server.py` | Tool MCP `identify_paper` |
| `pyproject.toml` | Extra opsional `pdf` |
| `tests/test_recognize.py` | Semua test untuk irisan ini |

---

### Task 1: Extract a DOI from free text

**Files:**
- Create: `src/josc/recognize.py`
- Test: `tests/test_recognize.py`

**Interfaces:**
- Consumes: `normalize_doi()` dari `josc.utils`.
- Produces: `find_doi(text: str) -> str | None` — DOI pertama yang ternormalisasi, atau `None`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_recognize.py`:

```python
from josc.recognize import find_doi


def test_find_doi_reads_a_plain_doi():
    assert find_doi("Available at https://doi.org/10.1109/5.771073 today") == "10.1109/5.771073"


def test_find_doi_reads_a_bare_doi():
    assert find_doi("DOI: 10.1038/nature14539") == "10.1038/nature14539"


def test_find_doi_ignores_trailing_punctuation():
    assert find_doi("See 10.1016/j.jbi.2020.103433.") == "10.1016/j.jbi.2020.103433"


def test_find_doi_returns_none_when_absent():
    assert find_doi("No identifier on this page") is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_recognize.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'josc.recognize'`.

- [ ] **Step 3: Create `src/josc/recognize.py`**

```python
"""Recognize paper metadata from the text of a document.

Zotero's ``recognizeDocument.js`` tries identifiers before anything else: a DOI
or ISBN that appears anywhere in the document is authoritative, and title-based
matching is only a fallback. This module implements the same ordering for plain
extracted text. It does not parse PDF structure and does not score title
candidates; both are deliberately out of scope.
"""

import re
from typing import Optional

from .utils import normalize_doi

_DOI_PATTERN = re.compile(r"10\.\d{4,9}/[^\s\"<>]+")


def find_doi(text: str) -> Optional[str]:
    """Return the first DOI found in ``text``, normalized, or ``None``."""
    if not text:
        return None
    match = _DOI_PATTERN.search(text)
    if not match:
        return None
    return normalize_doi(match.group(0).rstrip(".,;:)]}"))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_recognize.py -v`
Expected: PASS — 4 passed.

- [ ] **Step 5: Run the full suite**

Run: `pytest -q`
Expected: PASS — no regression.

- [ ] **Step 6: Commit**

```bash
git add src/josc/recognize.py tests/test_recognize.py
git commit -m "feat(recognize): extract DOIs from document text"
```

---

### Task 2: Guess a title and resolve a document to a paper

**Files:**
- Modify: `src/josc/recognize.py`
- Test: `tests/test_recognize.py` (append)

**Interfaces:**
- Consumes: `find_doi(text)` dari Task 1; `Paper` dari `josc.models`.
- Produces:
  - `guess_title(text: str) -> str | None` — baris kandidat judul terpanjang di antara 5 baris non-kosong pertama.
  - `recognize_document(text: str, resolver: Callable[[str], Awaitable[Optional[Paper]]]) -> Optional[Paper]` — async; memakai DOI bila ada, selain itu judul.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_recognize.py`:

```python
import pytest

from josc.models import Paper
from josc.recognize import guess_title, recognize_document


def test_guess_title_picks_the_longest_early_line():
    text = "Neural Computation\nLong Short-Term Memory\nSepp Hochreiter\n1997\n"
    assert guess_title(text) == "Long Short-Term Memory"


def test_guess_title_returns_none_for_blank_text():
    assert guess_title("   \n\n  ") is None


async def test_recognize_document_prefers_doi():
    seen = []

    async def resolver(identifier):
        seen.append(identifier)
        return Paper(doi=identifier, title="Resolved")

    paper = await recognize_document("doi 10.1/abc", resolver)
    assert paper is not None
    assert paper.title == "Resolved"
    assert seen == ["10.1/abc"]


async def test_recognize_document_falls_back_to_title():
    seen = []

    async def resolver(identifier):
        seen.append(identifier)
        return None

    await recognize_document("Attention Is All You Need\n2017\n", resolver)
    assert seen == ["Attention Is All You Need"]


async def test_recognize_document_returns_none_without_identifier():
    async def resolver(identifier):
        raise AssertionError("resolver must not be called")

    assert await recognize_document("", resolver) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_recognize.py -v`
Expected: FAIL — `ImportError: cannot import name 'guess_title'`.

- [ ] **Step 3: Extend `src/josc/recognize.py`**

Add these imports at the top:

```python
from typing import Awaitable, Callable, Optional

from .models import Paper
```

(Replace the existing `from typing import Optional` line so `Optional` is not imported twice.)

Then append:

```python
def guess_title(text: str) -> Optional[str]:
    """Return the longest plausible title line from the document opening."""
    if not text:
        return None
    candidates = [line.strip() for line in text.splitlines()[:5] if line.strip()]
    if not candidates:
        return None
    return max(candidates, key=len)


async def recognize_document(
    text: str,
    resolver: Callable[[str], Awaitable[Optional[Paper]]],
) -> Optional[Paper]:
    """Resolve document text to a paper, trying identifiers before the title."""
    identifier = find_doi(text) or guess_title(text)
    if not identifier:
        return None
    return await resolver(identifier)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_recognize.py -v`
Expected: PASS — 9 passed.

- [ ] **Step 5: Run the full suite**

Run: `pytest -q`
Expected: PASS — no regression.

- [ ] **Step 6: Commit**

```bash
git add src/josc/recognize.py tests/test_recognize.py
git commit -m "feat(recognize): resolve document text via DOI then title"
```

---

### Task 3: Extract text from a PDF behind a lazy import

**Files:**
- Create: `src/josc/pdf_text.py`
- Modify: `pyproject.toml` (tambahkan extra `pdf`)
- Test: `tests/test_recognize.py` (append)

**Interfaces:**
- Consumes: `pypdf` (opsional, diimpor di dalam fungsi).
- Produces: `extract_pdf_text(path: str) -> str` — teks gabungan semua halaman; melempar `RuntimeError` bila `pypdf` tidak terpasang.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_recognize.py`:

```python
import builtins

from josc.pdf_text import extract_pdf_text


def test_extract_pdf_text_explains_a_missing_dependency(monkeypatch):
    real_import = builtins.__import__

    def blocked(name, *args, **kwargs):
        if name == "pypdf":
            raise ImportError("no pypdf")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", blocked)

    with pytest.raises(RuntimeError) as excinfo:
        extract_pdf_text("whatever.pdf")
    assert "journal-scout-mcp[pdf]" in str(excinfo.value)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_recognize.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'josc.pdf_text'`.

- [ ] **Step 3: Create `src/josc/pdf_text.py`**

```python
"""Extract text from a PDF, importing ``pypdf`` only when actually needed.

The package must stay importable without the optional ``pdf`` extra, so the
import lives inside the function rather than at module level.
"""


def extract_pdf_text(path: str) -> str:
    """Return the concatenated text of every page in ``path``."""
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise RuntimeError(
            "PDF support requires the optional extra: "
            "pip install 'journal-scout-mcp[pdf]'"
        ) from exc

    reader = PdfReader(path)
    pages = [page.extract_text() or "" for page in reader.pages]
    return "\n".join(pages)
```

- [ ] **Step 4: Add the optional dependency**

In `pyproject.toml`, inside `[project.optional-dependencies]`, add:

```toml
pdf = ["pypdf>=4.0"]
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_recognize.py -v`
Expected: PASS — 10 passed.

- [ ] **Step 6: Run the full suite**

Run: `pytest -q`
Expected: PASS — no regression, dan `import josc.pdf_text` tetap berhasil tanpa `pypdf` terpasang.

- [ ] **Step 7: Commit**

```bash
git add src/josc/pdf_text.py pyproject.toml tests/test_recognize.py
git commit -m "feat(recognize): extract PDF text behind an optional extra"
```

---

### Task 4: Expose `identify_paper` as an MCP tool

**Files:**
- Modify: `src/josc/server.py:20-40` (`UNIFIED_TOOLS`), `src/josc/server.py:256-275` (schema), `src/josc/server.py:374-380` (dispatch)
- Test: `tests/test_server.py` (append)

**Interfaces:**
- Consumes: `extract_pdf_text(path)` dari Task 3; `recognize_document(text, resolver)` dari Task 2; `aggregator.get_paper(providers, identifier, sources=None)` yang sudah ada.
- Produces: tool MCP bernama `identify_paper` dengan argumen `{"path": str}`; hasilnya `{"paper": dict | null, "identifier": str | null}`.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_server.py`:

```python
async def test_identify_paper_tool_is_registered():
    assert "identify_paper" in TOOL_NAMES
    schema = next(tool for tool in _tool_list() if tool.name == "identify_paper").inputSchema
    assert schema["required"] == ["path"]


async def test_identify_paper_dispatches_through_recognize(monkeypatch):
    import josc.server as server

    monkeypatch.setattr(server, "extract_pdf_text", lambda path: "doi 10.1/x")

    async def fake_get_paper(providers, identifier, sources=None):
        return Paper(doi=identifier, title="Resolved")

    monkeypatch.setattr(server.aggregator, "get_paper", fake_get_paper)

    result = await build_json("identify_paper", {"path": "x.pdf"}, [], None)
    assert result["identifier"] == "10.1/x"
    assert result["paper"]["title"] == "Resolved"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_server.py -v`
Expected: FAIL — `assert "identify_paper" in TOOL_NAMES`.

- [ ] **Step 3: Register the tool name**

In `src/josc/server.py`, add `"identify_paper",` to the `UNIFIED_TOOLS` list next to `"export_results",`.

- [ ] **Step 4: Add the tool schema**

Inside `_tool_list()`, append this entry after the `export_results` entry:

```python
        _search_tool(
            "identify_paper",
            "Identify a paper from a local PDF by resolving its DOI or title.",
            {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Absolute path to a PDF file on this machine.",
                    },
                },
                "required": ["path"],
            },
        ),
```

- [ ] **Step 5: Add the imports and the dispatch branch**

At the top of `src/josc/server.py`, add:

```python
from .pdf_text import extract_pdf_text
from .recognize import recognize_document
```

Inside `build_json`, immediately before the `export_results` branch, add:

```python
    if name == "identify_paper":
        text = extract_pdf_text(arguments["path"])

        async def resolve(identifier: str):
            return await aggregator.get_paper(providers, identifier)

        paper = await recognize_document(text, resolve)
        return {
            "identifier": find_doi(text) or guess_title(text),
            "paper": paper.to_dict() if paper else None,
        }
```

Add `find_doi` and `guess_title` to the recognize import:

```python
from .recognize import find_doi, guess_title, recognize_document
```

- [ ] **Step 6: Run test to verify it passes**

Run: `pytest tests/test_server.py -v`
Expected: PASS — `test_identify_paper_tool_is_registered` dan `test_identify_paper_dispatches_through_recognize` hijau.

- [ ] **Step 7: Run the full suite**

Run: `pytest -q`
Expected: PASS — termasuk `test_tool_names_count`, yang sekarang menghitung 26 tool.

- [ ] **Step 8: Update the tool-count assertion**

In `tests/test_server.py`, change `assert len(TOOL_NAMES) == 25` to `assert len(TOOL_NAMES) == 26` and add `assert "identify_paper" in TOOL_NAMES`.

- [ ] **Step 9: Commit**

```bash
git add src/josc/server.py tests/test_server.py
git commit -m "feat(recognize): expose identify_paper MCP tool"
```

---

## Self-review

- **Cakupan:** ekstraksi DOI (Task 1), resolusi DOI-ke-judul (Task 2), ekstraksi PDF dengan dependensi opsional (Task 3), eksposur sebagai tool MCP (Task 4). Urutan strategi Zotero (identifier dulu, judul kemudian) dipertahankan.
- **Placeholder:** tidak ada; setiap step punya kode dan perintah nyata.
- **Konsistensi tipe:** `recognize_document` selalu async dan menerima `Callable[[str], Awaitable[Optional[Paper]]]`; Task 4 mendefinisikan `resolve` dengan bentuk yang sama. `extract_pdf_text` mengembalikan `str` dan di-monkeypatch dengan lambda `str -> str`.
- **Risiko regresi:** penambahan tool mengubah `len(TOOL_NAMES)`, sehingga Task 4 secara eksplisit memperbarui assertion tersebut.
