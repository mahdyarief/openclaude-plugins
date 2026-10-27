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
