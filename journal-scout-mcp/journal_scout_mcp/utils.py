import html
import re
from typing import Any, Optional

_DOI_PREFIXES = ("https://doi.org/", "http://doi.org/", "doi:")
_NON_ALNUM = re.compile(r"[^a-z0-9\s]")
_WHITESPACE = re.compile(r"\s+")
_TAG = re.compile(r"<[^>]+>")


def normalize_doi(doi: Optional[str]) -> Optional[str]:
    if not doi:
        return None
    value = doi.strip().lower()
    for prefix in _DOI_PREFIXES:
        if value.startswith(prefix):
            value = value[len(prefix):]
    return value or None


def normalize_title(title: Optional[str]) -> str:
    if not title:
        return ""
    value = title.strip().lower()
    value = _NON_ALNUM.sub(" ", value)
    return _WHITESPACE.sub(" ", value).strip()


def strip_jats(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    text = _TAG.sub(" ", value)
    return _WHITESPACE.sub(" ", html.unescape(text)).strip() or None


def first_of(value: Any) -> Any:
    """Return the first item of a list/tuple, otherwise the value unchanged.

    Bibliographic APIs disagree on shape: Crossref wraps ``title`` and
    ``container-title`` in a list while most other sources expose a bare
    string. Callers use this instead of repeating ``(x or [""])[0]``.
    """
    if isinstance(value, (list, tuple)):
        return value[0] if value else None
    return value


def parse_int(value: Any) -> Optional[int]:
    """Coerce an integer-like value (``42`` or ``"42"``) to ``int``.

    Year-like values go through :func:`parse_year`; counters such as citation
    counts are plain integers and must not be truncated to a 4-digit prefix.
    """
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    text = str(value).strip()
    if text.lstrip("-").isdigit():
        return int(text)
    return None


def parse_year(value: Any) -> Optional[int]:
    """Best-effort coercion of a year-like value to ``int``.

    Accepts ints, numeric strings (``"2017"``) and ISO-ish dates such as
    ``"2017-06-12"``; anything else yields ``None``.
    """
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    text = str(value).strip()
    if len(text) >= 4 and text[:4].isdigit():
        return int(text[:4])
    return None
