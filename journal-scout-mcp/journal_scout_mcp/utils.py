import html
import re
from typing import Optional

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
