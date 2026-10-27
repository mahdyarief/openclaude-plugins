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
| `src/josc/identify.py` | `resolve_document(text, providers)` — orkestrasi bersama MCP + HTTP |
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

### Task 5: Expose `POST /api/identify` on the HTTP API

**Files:**
- Create: `src/josc/identify.py`
- Modify: `src/josc/pdf_text.py`
- Create: `src/josc/api/recognize_routes.py`
- Modify: `src/josc/api/app.py`
- Modify: `src/josc/api/__init__.py`
- Modify: `src/josc/server.py`
- Test: `tests/test_recognize.py`, `tests/test_api_routes.py`

**Interfaces:**
- Consumes: `josc.recognize.find_doi/guess_title/recognize_document`; `josc.aggregator.get_paper(providers, identifier, sources=None) -> {"paper": dict | None, "errors": dict}`; `josc.pdf_text.extract_pdf_text`.
- Produces:
  - `josc.identify.resolve_document(text: str, providers) -> Dict[str, Any]` returning `{"identifier": str | None, "paper": dict | None}`.
  - `josc.pdf_text.extract_pdf_text_from_bytes(data: bytes) -> str`.
  - `josc.api.identify(request) -> JSONResponse` — handler for `POST /api/identify`.

**Security note (binding):** the HTTP route must NOT accept a server-side filesystem path. It accepts `{"pdf_base64": "<base64 PDF>"}` in the JSON body and decodes it in memory.

- [ ] **Step 1: Write the failing orchestration tests**

Append to `tests/test_recognize.py` (imports go in the file's existing top import block — `import pytest` is already there; add `from josc import identify` at the top):

```python
async def test_resolve_document_returns_identifier_and_paper(monkeypatch):
    async def fake_get_paper(providers, identifier, sources=None):
        return {"paper": {"title": "Resolved", "doi": identifier}, "errors": {}}

    monkeypatch.setattr(identify.aggregator, "get_paper", fake_get_paper)

    result = await identify.resolve_document("doi 10.1/x", [])

    assert result["identifier"] == "10.1/x"
    assert result["paper"]["title"] == "Resolved"


async def test_resolve_document_returns_none_without_identifier():
    result = await identify.resolve_document("", [])

    assert result == {"identifier": None, "paper": None}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/test_recognize.py -v`
Expected: FAIL — `ImportError: cannot import name 'identify' from 'josc'` (or `ModuleNotFoundError: No module named 'josc.identify'`).

- [ ] **Step 3: Write the minimal implementation**

Create `src/josc/identify.py`:

```python
"""Shared orchestration for identifying a paper from document text.

Both the MCP ``identify_paper`` tool and the HTTP ``POST /api/identify`` route
call this, so the two surfaces resolve identifiers through one code path.
"""

from typing import Any, Dict

from . import aggregator
from .recognize import find_doi, guess_title, recognize_document


async def resolve_document(text: str, providers) -> Dict[str, Any]:
    """Return ``{"identifier": ..., "paper": ...}`` for ``text``.

    ``paper`` is the provider record dict, or ``None`` when nothing resolved.
    """
    identifier = find_doi(text) or guess_title(text)
    if not identifier:
        return {"identifier": None, "paper": None}

    async def resolve(candidate: str):
        return (await aggregator.get_paper(providers, candidate)).get("paper")

    paper = await recognize_document(text, resolve)
    return {"identifier": identifier, "paper": paper}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/test_recognize.py -v`
Expected: PASS (12 tests).

- [ ] **Step 5: Write the failing bytes-extraction test**

Append to `tests/test_recognize.py` (add `extract_pdf_text_from_bytes` to the existing `from josc.pdf_text import ...` line at the top):

```python
def test_extract_pdf_text_from_bytes_explains_a_missing_dependency(monkeypatch):
    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "pypdf" or name.startswith("pypdf."):
            raise ImportError("no pypdf")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    with pytest.raises(RuntimeError) as excinfo:
        extract_pdf_text_from_bytes(b"%PDF-1.4")

    assert "journal-scout-mcp[pdf]" in str(excinfo.value)
```

- [ ] **Step 6: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/test_recognize.py::test_extract_pdf_text_from_bytes_explains_a_missing_dependency -v`
Expected: FAIL — `ImportError: cannot import name 'extract_pdf_text_from_bytes'`.

- [ ] **Step 7: Refactor `src/josc/pdf_text.py` to share the lazy reader**

Replace the whole module with:

```python
"""Extract text from a PDF, importing ``pypdf`` only when actually needed.

The package must stay importable without the optional ``pdf`` extra, so the
import lives inside a helper rather than at module level.
"""

import io


def _pdf_reader(source):
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise RuntimeError(
            "PDF support requires the optional extra: "
            "pip install 'journal-scout-mcp[pdf]'"
        ) from exc
    return PdfReader(source)


def _pages_text(reader) -> str:
    pages = [page.extract_text() or "" for page in reader.pages]
    return "\n".join(pages)


def extract_pdf_text(path: str) -> str:
    """Return the concatenated text of every page in ``path``."""
    return _pages_text(_pdf_reader(path))


def extract_pdf_text_from_bytes(data: bytes) -> str:
    """Return the concatenated text of every page in an in-memory PDF."""
    return _pages_text(_pdf_reader(io.BytesIO(data)))
```

- [ ] **Step 8: Run tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/test_recognize.py -v`
Expected: PASS (13 tests) — the existing missing-dependency test must still pass against the shared helper.

- [ ] **Step 9: Write the failing route tests**

Append to `tests/test_api_routes.py` (add `import base64` at the top of the file):

```python
async def test_identify_route_resolves_uploaded_pdf(monkeypatch):
    monkeypatch.setattr(
        api.recognize_routes,
        "extract_pdf_text_from_bytes",
        lambda data: "doi 10.1/x",
    )

    async def fake_get_paper(providers, identifier, sources=None):
        return {"paper": {"title": "Resolved"}, "errors": {}}

    monkeypatch.setattr(api.aggregator, "get_paper", fake_get_paper)

    req = FakeRequest(body={"pdf_base64": base64.b64encode(b"%PDF-1.4").decode()})
    response = await api.identify(req)

    assert response.status_code == 200
    payload = _body(response)
    assert payload["identifier"] == "10.1/x"
    assert payload["paper"]["title"] == "Resolved"


async def test_identify_route_rejects_missing_pdf_base64():
    response = await api.identify(FakeRequest(body={}))

    assert response.status_code == 400
    assert "pdf_base64" in _body(response)["error"]


async def test_identify_route_rejects_invalid_base64():
    response = await api.identify(FakeRequest(body={"pdf_base64": "not base64!!"}))

    assert response.status_code == 400
    assert "base64" in _body(response)["error"]
```

- [ ] **Step 10: Run tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_api_routes.py -k identify -v`
Expected: FAIL — `AttributeError: module 'josc.api' has no attribute 'identify'`.

- [ ] **Step 11: Create the route handler**

Create `src/josc/api/recognize_routes.py`:

```python
"""Route handler for identifying a paper from an uploaded PDF."""

from __future__ import annotations

import base64
import binascii

from starlette.requests import Request
from starlette.responses import JSONResponse

from ..identify import resolve_document
from ..pdf_text import extract_pdf_text_from_bytes
from .responses import _error
from .state import _providers


async def identify(request: Request) -> JSONResponse:
    """Resolve an uploaded PDF to a paper record.

    The body carries base64-encoded bytes, never a server-side path, so a
    remote caller cannot use this route to read arbitrary files.
    """
    try:
        body = await request.json()
    except Exception as exc:  # malformed JSON is a client error
        return _error(exc)
    if not isinstance(body, dict):
        return _error(ValueError("Request body must be a JSON object."))

    encoded = body.get("pdf_base64")
    if not isinstance(encoded, str) or not encoded.strip():
        return _error(ValueError("'pdf_base64' must be a base64-encoded PDF."))
    try:
        data = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError) as exc:
        return _error(ValueError(f"'pdf_base64' is not valid base64: {exc}"))

    try:
        text = extract_pdf_text_from_bytes(data)
    except RuntimeError as exc:
        return _error(exc, status=501)

    try:
        result = await resolve_document(text, _providers())
    except Exception as exc:  # provider failures map to 502 via _error
        return _error(exc)
    return JSONResponse(result)
```

- [ ] **Step 12: Register the route and re-export the handler**

In `src/josc/api/app.py`, add to the relative-import block:

```python
from .recognize_routes import identify
```

and add this line to the `routes` list, immediately after the `/api/export` entry:

```python
    Route("/api/identify", identify, methods=["POST"]),
```

In `src/josc/api/__init__.py`, add to the import block:

```python
from .recognize_routes import identify
```

and add `"identify",` to `__all__` in alphabetical position (between `"health",` and `"import_external",` — `"identify"` sorts before `"import_external"`).

Also add a module-map line to the `__init__.py` docstring:

```
* :mod:`.recognize_routes`  - identify a paper from an uploaded PDF
```

- [ ] **Step 13: Point the MCP tool at the shared orchestration**

In `src/josc/server.py`, replace the imports

```python
from .pdf_text import extract_pdf_text
from .recognize import find_doi, guess_title, recognize_document
```

with

```python
from .identify import resolve_document
from .pdf_text import extract_pdf_text
```

and replace the `identify_paper` dispatch branch with:

```python
    if name == "identify_paper":
        text = extract_pdf_text(arguments["path"])
        return await resolve_document(text, providers)
```

The existing `test_identify_paper_dispatches_through_recognize` must keep passing unchanged: `server.aggregator` and `server.extract_pdf_text` are still the names it monkeypatches, and `identify.aggregator` is the same module object.

- [ ] **Step 14: Run the full suite**

Run: `.venv/Scripts/python.exe -m pytest -q`
Expected: PASS — 516 tests, no regressions (510 at Task 4 head + 6 new: 2 orchestration,
1 bytes-extraction, 3 route).

- [ ] **Step 15: Commit**

```bash
git add src/josc/identify.py src/josc/pdf_text.py src/josc/api/recognize_routes.py src/josc/api/app.py src/josc/api/__init__.py src/josc/server.py tests/test_recognize.py tests/test_api_routes.py
git commit -m "feat(recognize): expose POST /api/identify over the HTTP API"
```

---

## Self-review

- **Cakupan:** ekstraksi DOI (Task 1), resolusi DOI-ke-judul (Task 2), ekstraksi PDF dengan dependensi opsional (Task 3), eksposur sebagai tool MCP (Task 4), dan eksposur sebagai endpoint HTTP `POST /api/identify` (Task 5). Urutan strategi Zotero (identifier dulu, judul kemudian) dipertahankan di kedua permukaan lewat `josc.identify.resolve_document`.
- **Placeholder:** tidak ada; setiap step punya kode dan perintah nyata.
- **Konsistensi tipe:** `recognize_document` selalu async dan menerima `Callable[[str], Awaitable[Optional[Paper]]]`; Task 4 mendefinisikan `resolve` dengan bentuk yang sama. `extract_pdf_text` mengembalikan `str` dan di-monkeypatch dengan lambda `str -> str`. Task 5 menambahkan `extract_pdf_text_from_bytes(data: bytes) -> str` dan `resolve_document(text, providers) -> {"identifier", "paper"}`; resolver internalnya mengembalikan `dict | None`, bukan `Paper`.
- **Risiko regresi:** penambahan tool mengubah `len(TOOL_NAMES)`, sehingga Task 4 secara eksplisit memperbarui assertion tersebut. Task 5 mempertahankan `server.extract_pdf_text` dan `server.aggregator` sebagai nama yang di-monkeypatch test Task 4, jadi test itu tidak perlu diubah.
- **Keamanan:** route HTTP menerima base64 PDF di body, bukan path filesystem, sehingga tidak membuka LFI.
