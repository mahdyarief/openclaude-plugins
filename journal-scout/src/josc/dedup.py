"""Duplicate guards ported from Zotero's ``duplicates.js``.

Two records that already share a normalized title are only the same work when
no identity field contradicts it. The rules mirror Zotero 10.0.6
(``duplicates.js:345-382``): a conflicting DOI or ISBN is decisive, a year gap
of more than one year is decisive, and creators must overlap on
last name plus first initial.
"""

from typing import Optional, Sequence, Tuple

from .models import Paper
from .utils import normalize_doi, normalize_title


def _creator_key(name: str) -> Optional[Tuple[str, str]]:
    """Return ``(normalized last name, first initial)`` for a display name."""
    parts = (name or "").strip().split()
    if not parts:
        return None
    last = normalize_title(parts[-1])
    initial = parts[0][0].lower() if len(parts) > 1 else ""
    return last, initial


def _creator_keys(authors: Sequence[str]) -> list[Tuple[str, str]]:
    keys = [_creator_key(name) for name in authors]
    return [key for key in keys if key is not None]


def same_work(a: Paper, b: Paper) -> bool:
    """Decide whether two same-titled records describe one work."""
    doi_a, doi_b = normalize_doi(a.doi), normalize_doi(b.doi)
    if doi_a and doi_b and doi_a != doi_b:
        return False

    if a.isbn and b.isbn and a.isbn != b.isbn:
        return False

    if a.year is not None and b.year is not None and abs(a.year - b.year) > 1:
        return False

    creators_a, creators_b = _creator_keys(a.authors), _creator_keys(b.authors)
    if not creators_a and not creators_b:
        return True
    if not creators_a or not creators_b:
        return False

    for last_a, initial_a in creators_a:
        for last_b, initial_b in creators_b:
            if last_a == last_b and initial_a == initial_b:
                return True
    return False
