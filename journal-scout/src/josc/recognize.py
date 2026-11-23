"""Zotero's ``recognizeDocument.js`` tries identifiers before anything else: a DOI
or ISBN that appears anywhere in the document is authoritative, and title-based
matching is only a fallback. This module implements the same ordering for plain
extracted text. It does not parse PDF structure and does not score title
candidates; both are deliberately out of scope.
"""

import re
from typing import Awaitable, Callable, Optional

from .models import Paper
from .utils import normalize_doi

_DOI_PATTERN = re.compile(r"10\.\d{1,9}/[^\s\"<>]+")


def find_doi(text: str) -> Optional[str]:
    if not text:
        return None
    match = _DOI_PATTERN.search(text)
    if not match:
        return None
    return normalize_doi(match.group(0).rstrip(".,;:)]}"))


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
