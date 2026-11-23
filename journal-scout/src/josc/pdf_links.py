"""Discover a paper's PDF link from what publishers already publish.

Two publisher-agnostic sources, so no per-publisher URL pattern is needed:

* **Crossref** ``/works/<doi>`` lists ``link`` entries the publisher deposited;
  the ``application/pdf`` ones point at the full text (e.g. Springer's
  ``link.springer.com/content/pdf/<doi>.pdf``).
* **The landing page** that ``doi.org/<doi>`` redirects to carries Google
  Scholar's ``<meta name="citation_pdf_url">`` tag on nearly every publisher
  site (Springer, Elsevier, Wiley, IEEE, MDPI, ACM, PeerJ, ...).

Both helpers are best-effort: any HTTP failure yields an empty list, and the
caller moves on to the next route.
"""

import html as html_lib
import re
from typing import Any, List
from urllib.parse import quote, urljoin

from . import curl_fetch
from .config import get_polite_email
from .models import ProviderError

CROSSREF_WORKS_URL = "https://api.crossref.org/works/{doi}"
DOI_RESOLVER_URL = "https://doi.org/{doi}"
LANDING_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/130.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
}

_META_TAG = re.compile(r"<meta\b[^>]*>", re.I)
_LINK_TAG = re.compile(r"<link\b[^>]*>", re.I)
_ATTR = re.compile(r"""([a-zA-Z_:-]+)\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s>]+))""")
# Crossref ``intended-application`` values, most useful first.
_APPLICATION_RANK = {"text-mining": 0, "similarity-checking": 1, "unspecified": 2}


def _attrs(tag: str) -> dict:
    return {
        name.lower(): html_lib.unescape(next(v for v in values if v is not None) or "")
        for name, *values in _ATTR.findall(tag)
    }


def _dedupe(urls: List[str]) -> List[str]:
    seen, unique = set(), []
    for url in urls:
        if url and url not in seen:
            seen.add(url)
            unique.append(url)
    return unique


def crossref_pdf_links(message: dict) -> List[str]:
    """PDF URLs from a Crossref ``message`` object, best first."""
    links = [
        link
        for link in (message or {}).get("link") or []
        if isinstance(link, dict)
        and link.get("URL")
        and (
            "pdf" in (link.get("content-type") or "").lower()
            or link["URL"].lower().split("?", 1)[0].endswith(".pdf")
        )
    ]
    links.sort(key=lambda link: _APPLICATION_RANK.get(link.get("intended-application"), 3))
    return _dedupe([link["URL"] for link in links])


def landing_pdf_links(page_html: str, base_url: str) -> List[str]:
    """``citation_pdf_url`` metas, then ``<link type="application/pdf">``."""
    urls: List[str] = []
    for tag in _META_TAG.findall(page_html or ""):
        attrs = _attrs(tag)
        if attrs.get("name", "").lower() == "citation_pdf_url" and attrs.get("content"):
            urls.append(urljoin(base_url, attrs["content"].strip()))
    for tag in _LINK_TAG.findall(page_html or ""):
        attrs = _attrs(tag)
        if attrs.get("type", "").lower() == "application/pdf" and attrs.get("href"):
            urls.append(urljoin(base_url, attrs["href"].strip()))
    return _dedupe(urls)


def _doi_path(doi: str) -> str:
    return quote(doi, safe="/:;()._-")


async def find_crossref_pdf_links(fetcher: Any, doi: str) -> List[str]:
    if fetcher is None or not hasattr(fetcher, "get_json"):
        return []
    try:
        data = await fetcher.get_json(
            CROSSREF_WORKS_URL.format(doi=_doi_path(doi)),
            params={"mailto": get_polite_email()},
            provider="crossref",
        )
    except (ProviderError, ValueError):
        return []
    return crossref_pdf_links((data or {}).get("message") or {})


async def find_landing_pdf_links(fetcher: Any, doi: str, use_curl: bool = False) -> List[str]:
    """PDF links on the DOI's landing page: curl first, httpx as the fallback."""
    url = DOI_RESOLVER_URL.format(doi=_doi_path(doi))
    if use_curl:
        try:
            final_url, body = await curl_fetch.curl_get(url, LANDING_HEADERS)
            links = landing_pdf_links(body.decode("utf-8", "replace"), final_url)
            if links:
                return links
        except ProviderError:
            pass
    if fetcher is None or not hasattr(fetcher, "get_page"):
        return []
    try:
        final_url, page_html = await fetcher.get_page(
            url, headers=LANDING_HEADERS, provider="landing"
        )
    except (ProviderError, ValueError):
        return []
    return landing_pdf_links(page_html, final_url)
