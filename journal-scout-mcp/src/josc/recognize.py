"""Zotero's ``recognizeDocument.js`` tries identifiers before anything else: a DOI
or ISBN that appears anywhere in the document is authoritative, and title-based
matching is only a fallback. This module implements the same ordering for plain
extracted text. It does not parse PDF structure and does not score title
candidates; both are deliberately out of scope.
"""

import re
from typing import Optional

from .utils import normalize_doi

_DOI_PATTERN = re.compile(r"10\.\d{1,9}/[^\s\"<>]+")


def find_doi(text: str) -> Optional[str]:
    if not text:
        return None
    match = _DOI_PATTERN.search(text)
    if not match:
        return None
    return normalize_doi(match.group(0).rstrip(".,;:)]}"))
