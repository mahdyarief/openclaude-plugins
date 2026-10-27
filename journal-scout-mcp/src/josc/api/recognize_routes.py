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
