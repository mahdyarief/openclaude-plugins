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
