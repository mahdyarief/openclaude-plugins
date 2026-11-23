"""``GET /api/pdf``: download a paper's PDF as a file.

This is the delivery path of the ``get_pdf`` MCP tool on a remote server: the
tool resolves the PDF, the bytes stay in :mod:`josc.pdf_save`'s short cache,
and the client downloads them from here into its own ``source/pdf`` folder.
Called directly (a browser, ``curl``), it resolves the PDF on demand.
"""

from __future__ import annotations

from typing import Optional
from urllib.parse import quote

from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from .. import pdf_save
from ..fulltext_fetch import fetch_pdf
from .responses import _error
from .state import _providers


def _tristate(request: Request, name: str) -> Optional[bool]:
    raw = (request.query_params.get(name) or "").strip().lower()
    if raw in ("1", "true", "yes", "on"):
        return True
    if raw in ("0", "false", "no", "off"):
        return False
    return None


async def pdf_download(request: Request) -> Response:
    identifier = (request.query_params.get("identifier") or "").strip()
    if not identifier:
        return _error(ValueError("Provide 'identifier' (a DOI or arXiv id)."))
    filename = pdf_save.pdf_filename(identifier, request.query_params.get("filename"))
    result = pdf_save.recall(identifier)
    if result is None:
        try:
            result = await fetch_pdf(
                _providers(),
                identifier,
                scinet=_tristate(request, "scinet"),
                curl=_tristate(request, "curl"),
            )
        except Exception as exc:  # noqa: BLE001 - report, never 500
            return _error(exc, status=502)
        if result.get("status") == "found":
            pdf_save.remember(identifier, result)
    if result.get("status") != "found":
        status = 404 if result.get("status") in ("not_found", "no_oa") else 502
        return JSONResponse(pdf_save.public_metadata(result), status_code=status)
    title = ((result.get("paper") or {}).get("title") or "").strip()
    headers = {
        "content-disposition": f'attachment; filename="{filename}"',
        "x-pdf-source": str(result.get("pdf_source") or ""),
        "x-pdf-via": str(result.get("via") or ""),
        # Percent-encoded: HTTP header values must stay latin-1.
        "x-pdf-url": quote(str(result.get("pdf_url") or ""), safe=":/?&=%#+,;@"),
        "x-paper-title": quote(title[:300], safe=""),
        "cache-control": "private, max-age=900",
    }
    return Response(result["pdf_bytes"], media_type="application/pdf", headers=headers)
