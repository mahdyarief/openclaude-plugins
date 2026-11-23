"""Name, cache and save PDFs produced by :func:`josc.fulltext_fetch.fetch_pdf`.

``get_pdf`` has two delivery paths:

* **stdio** (server on the client's machine): the PDF is written straight to
  ``<client folder>/source/pdf/<file>.pdf``.
* **http** (remote server): the server cannot touch the client's disk, so it
  keeps the bytes in a short in-process cache and returns a ``/api/pdf`` link
  the client downloads into ``source/pdf/`` itself.
"""

import re
import time
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
from urllib.parse import urlencode

DEFAULT_SUBDIR = Path("source") / "pdf"
CACHE_SECONDS = 15 * 60
CACHE_MAX_ITEMS = 32

_UNSAFE = re.compile(r"[^A-Za-z0-9._-]+")
_cache: Dict[str, Tuple[float, Dict[str, Any]]] = {}


def pdf_filename(identifier: str, requested: Optional[str] = None) -> str:
    """A filesystem-safe ``*.pdf`` name: the requested one, else the identifier.

    ``10.1016/j.cosrev.2026.101054`` -> ``10.1016_j.cosrev.2026.101054.pdf``.
    Directory parts of ``requested`` are dropped so it cannot escape the
    target folder.
    """
    raw = Path(requested).name if requested else identifier
    stem = raw[:-4] if raw.lower().endswith(".pdf") else raw
    stem = _UNSAFE.sub("_", stem).strip("._") or "paper"
    return f"{stem[:150]}.pdf"


def save_pdf(data: bytes, directory: Path, filename: str) -> Path:
    directory = Path(directory).expanduser()
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / filename
    path.write_bytes(data)
    return path.resolve()


def _cache_key(identifier: str) -> str:
    return identifier.strip().lower()


def remember(identifier: str, result: Dict[str, Any]) -> None:
    """Keep a found PDF result so ``/api/pdf`` can serve it without refetching."""
    now = time.monotonic()
    for key in [k for k, (expires, _r) in _cache.items() if expires <= now]:
        del _cache[key]
    while len(_cache) >= CACHE_MAX_ITEMS:
        del _cache[min(_cache, key=lambda k: _cache[k][0])]
    _cache[_cache_key(identifier)] = (now + CACHE_SECONDS, result)


def recall(identifier: str) -> Optional[Dict[str, Any]]:
    entry = _cache.get(_cache_key(identifier))
    if entry is None:
        return None
    expires, result = entry
    if expires <= time.monotonic():
        _cache.pop(_cache_key(identifier), None)
        return None
    return result


def clear_cache() -> None:
    _cache.clear()


def download_url(base_url: str, identifier: str, filename: str) -> str:
    query = urlencode({"identifier": identifier, "filename": filename})
    return f"{base_url.rstrip('/')}/api/pdf?{query}"


def public_metadata(result: Dict[str, Any]) -> Dict[str, Any]:
    """The tool-facing part of a fetch result: everything but the raw bytes."""
    return {
        key: value
        for key, value in result.items()
        if key not in ("pdf_bytes", "paper")
    }
