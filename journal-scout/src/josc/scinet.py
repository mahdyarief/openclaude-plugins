"""Resolve a DOI to a PDF hosted on Sci-Net (``https://sci-net.xyz/<doi>``).

Sci-Net serves one HTML page per DOI. When someone has uploaded the paper, the
page embeds it in an ``<iframe src="/storage/.../<name>.pdf#view=...">``; the
storage path downloads directly, without the DDoS-Guard cookies. An unknown DOI
answers with a redirect, and a requested-but-unfulfilled DOI has no iframe, so
both resolve to ``None``.

This is a non-open-access source, so it is opt-in: see
:func:`josc.config.get_scinet_enabled`.
"""

import re
from typing import Any, Optional
from urllib.parse import quote, urljoin

from .models import ProviderError

SCINET_BASE_URL = "https://sci-net.xyz"
PROVIDER = "scinet"
# A desktop UA: the DDoS-Guard front end is friendlier to it than to httpx's.
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/130.0 Safari/537.36"
    ),
    "Accept": "text/html,application/pdf;q=0.9,*/*;q=0.8",
}

_IFRAME_SRC = re.compile(r"<iframe\b[^>]*?\bsrc\s*=\s*[\"']([^\"']+)[\"']", re.I)
_DOI_PREFIX = re.compile(r"^(?:https?://(?:dx\.)?doi\.org/|doi:)", re.I)
_DOI_SHAPE = re.compile(r"^10\.\d{4,9}/\S+$")


def normalize_doi(value: Optional[str]) -> Optional[str]:
    """Return a bare ``10.xxxx/...`` DOI, or ``None`` if ``value`` is not one."""
    if not value:
        return None
    doi = _DOI_PREFIX.sub("", value.strip())
    return doi if _DOI_SHAPE.match(doi) else None


def page_url(doi: str) -> str:
    # Keep the slash and the usual DOI punctuation literal, as the site does.
    return f"{SCINET_BASE_URL}/{quote(doi, safe='/:;()._-')}"


def extract_pdf_url(html: str, base_url: str = SCINET_BASE_URL) -> Optional[str]:
    """Pull the embedded PDF link out of a Sci-Net article page."""
    for src in _IFRAME_SRC.findall(html or ""):
        path = src.split("#", 1)[0].strip()
        if ".pdf" in path.lower():
            return urljoin(base_url + "/", path)
    return None


async def find_pdf_url(fetcher: Any, doi: str) -> Optional[str]:
    """Look ``doi`` up on Sci-Net; ``None`` when it has no uploaded PDF."""
    doi = normalize_doi(doi)
    if not doi or fetcher is None or not hasattr(fetcher, "get_text"):
        return None
    url = page_url(doi)
    try:
        html = await fetcher.get_text(url, headers=HEADERS, provider=PROVIDER)
    except ProviderError:
        return None
    return extract_pdf_url(html, url)
