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
