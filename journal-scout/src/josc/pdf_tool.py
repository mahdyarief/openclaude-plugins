"""The ``get_pdf`` MCP tool: deliver a paper's PDF file to the client.

Where the file lands depends on where the server runs:

* ``stdio``: the server is a child process on the client's machine, so it
  writes ``<folder>/source/pdf/<file>.pdf`` itself. ``<folder>`` is
  ``save_dir`` when given, else the client's first MCP root (the folder the
  client is working in), else ``JOSC_PDF_DIR``, else the process directory.
* ``http``: the server is remote and cannot write to the client's disk. It
  caches the bytes for 15 minutes and returns a ``download_url`` on its own
  ``/api/pdf`` endpoint plus the command that saves it to ``source/pdf/``.
"""

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import unquote, urlparse
from urllib.request import url2pathname

from . import pdf_save
from .fulltext_fetch import fetch_pdf

DESCRIPTION = (
    "Download one paper's PDF FILE (not its text) into the client's working folder "
    "under source/pdf/. Uses the same routes as get_fulltext (OA link, Crossref, "
    "doi.org landing page, publisher patterns, Sci-Net when enabled; curl first, "
    "Python client fallback). On a local (stdio) server the file is saved directly "
    "and 'path' is returned. On a remote server (delivery='download') the server "
    "cannot write to your disk: run the returned 'command' in the working folder to "
    "save 'download_url' to 'save_path' (link valid ~15 minutes)."
)

INPUT_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "identifier": {
            "type": "string",
            "description": "DOI or arXiv id of the paper.",
        },
        "save_dir": {
            "type": "string",
            "description": (
                "Target folder. Default: source/pdf inside the client's working "
                "folder. Relative paths are resolved against that folder."
            ),
        },
        "filename": {
            "type": "string",
            "description": "File name; defaults to the identifier, e.g. 10.1016_j.x.2026.1.pdf.",
        },
        "scinet": {
            "type": "boolean",
            "description": "Override the server's Sci-Net fallback setting for this call.",
        },
        "curl": {
            "type": "boolean",
            "description": "Override the server's curl-first setting for this call.",
        },
        "sources": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["identifier"],
}


def root_paths(root_uris: List[str]) -> List[Path]:
    """Local paths of ``file://`` MCP roots (others are ignored)."""
    paths = []
    for uri in root_uris:
        parsed = urlparse(str(uri))
        if parsed.scheme != "file":
            continue
        raw = unquote(parsed.path)
        if parsed.netloc and parsed.netloc != "localhost":
            raw = f"//{parsed.netloc}{raw}"
        paths.append(Path(url2pathname(raw)))
    return paths


def local_pdf_dir(save_dir: Optional[str], root_uris: List[str]) -> Path:
    roots = root_paths(root_uris)
    configured = os.getenv("JOSC_PDF_DIR")
    if roots:
        base = roots[0]
        default = base / pdf_save.DEFAULT_SUBDIR
    elif configured:
        # An explicit PDF folder is used as is, not nested under source/pdf.
        base = default = Path(configured).expanduser()
    else:
        base = Path(os.getcwd())
        default = base / pdf_save.DEFAULT_SUBDIR
    if not save_dir:
        return default
    target = Path(save_dir).expanduser()
    return target if target.is_absolute() else base / target


def _quote(text: str) -> str:
    return json.dumps(text)


async def get_pdf(
    arguments: Dict[str, Any],
    providers: List[Any],
    transport: str,
    root_uris: Optional[List[str]] = None,
    base_url: Optional[str] = None,
) -> Dict[str, Any]:
    identifier = (arguments.get("identifier") or "").strip()
    if not identifier:
        return {"status": "error", "error": "Provide 'identifier'."}
    requested = arguments.get("sources")
    selected = [p for p in providers if not requested or p.name in requested]
    result = await fetch_pdf(
        selected,
        identifier,
        scinet=arguments.get("scinet"),
        curl=arguments.get("curl"),
    )
    payload = pdf_save.public_metadata(result)
    if result.get("status") != "found":
        return payload
    filename = pdf_save.pdf_filename(identifier, arguments.get("filename"))
    payload["filename"] = filename

    if transport == "stdio":
        directory = local_pdf_dir(arguments.get("save_dir"), root_uris or [])
        path = pdf_save.save_pdf(result["pdf_bytes"], directory, filename)
        payload.update(delivery="saved", path=str(path))
        return payload

    if not base_url:
        payload.update(
            delivery="unavailable",
            error="Remote server has no public URL; set JOSC_PUBLIC_URL.",
        )
        return payload
    pdf_save.remember(identifier, result)
    folder = (arguments.get("save_dir") or str(pdf_save.DEFAULT_SUBDIR)).replace("\\", "/")
    save_path = f"{folder.rstrip('/')}/{filename}"
    url = pdf_save.download_url(base_url, identifier, filename)
    payload.update(
        delivery="download",
        download_url=url,
        save_path=save_path,
        expires_in_seconds=pdf_save.CACHE_SECONDS,
        command=f"mkdir -p {_quote(folder)} && curl -fsSL -o {_quote(save_path)} {_quote(url)}",
    )
    return payload


def public_base_url(headers: Dict[str, str]) -> Optional[str]:
    """``JOSC_PUBLIC_URL``, else the scheme and host the request came in on."""
    configured = (os.getenv("JOSC_PUBLIC_URL") or "").strip()
    if configured:
        return configured.rstrip("/")
    host = headers.get("x-forwarded-host") or headers.get("host")
    if not host:
        return None
    scheme = "https" if '"https"' in headers.get("cf-visitor", "") else None
    scheme = scheme or headers.get("x-forwarded-proto") or "http"
    return f"{scheme.split(',')[0].strip()}://{host.split(',')[0].strip()}"
