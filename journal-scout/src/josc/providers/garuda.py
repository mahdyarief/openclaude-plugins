"""Garuda (Garba Rujukan Digital) — garuda.kemdiktisaintek.go.id.

Scrapes the HTML search results at ``/documents?q=``. Garuda publishes no
JSON API, so the selectors mirror the live markup: ``div.article-item`` cards
with ``a.title-article``, ``a.author-article`` and ``xmp.subtitle-article``.
"""

from __future__ import annotations

import asyncio
import re
from typing import List, Optional

from bs4 import BeautifulSoup

from ..models import Paper
from .base import ProviderBase

BASE = "https://garuda.kemdiktisaintek.go.id"
PAGE_SIZE = 10

YEAR_RE = re.compile(r"\((\d{4})\)")
# Some records say "SNATI) 2005" with no parentheses at all.
BARE_YEAR_RE = re.compile(r"\b((?:19|20)\d{2})\b")
VOLUME_RE = re.compile(r"\bVol\.?\s*(\d+)\b", re.IGNORECASE)
ISSUE_RE = re.compile(r"\bNo\.?\s*(\d+)\b", re.IGNORECASE)
TRAILING_ID_RE = re.compile(r"/documents/detail/(\d+)")
# Garuda appends " -" to authors that have no linked affiliation page.
AUTHOR_TRAILER_RE = re.compile(r"\s*-\s*$")
WS_RE = re.compile(r"\s+")

# Garuda ANDs every whitespace-separated term, so a long natural-language query
# matches nothing even when every term appears somewhere. The ladder below
# shortens the query until the site returns hits, and always reaches a two-term
# prefix: a six-word query can still match when the index only carries the
# leading topic words.
MAX_FALLBACK_TERMS = 6
FALLBACK_PAUSE_SECONDS = 0.4


def _query_variants(query: str) -> List[str]:
    terms = [term for term in WS_RE.split(query.strip()) if term]
    if len(terms) <= 1:
        return [query]

    n = len(terms)
    variants = [query]
    for keep in (n - 1, n // 2, 2, 1):
        if not 1 <= keep < n:
            continue
        candidate = " ".join(terms[:keep])
        if candidate not in variants:
            variants.append(candidate)
        if len(variants) >= MAX_FALLBACK_TERMS:
            break
    return variants


def _text(node) -> str:
    return WS_RE.sub(" ", node.get_text(" ", strip=True)).strip()


def _parse_venue(raw: str) -> tuple[Optional[str], Optional[int], Optional[str], Optional[str]]:
    raw = WS_RE.sub(" ", raw).strip()
    if not raw:
        return None, None, None, None

    year = None
    if m := YEAR_RE.search(raw):
        year = int(m.group(1))
    elif m := BARE_YEAR_RE.search(raw):
        year = int(m.group(1))

    volume = m.group(1) if (m := VOLUME_RE.search(raw)) else None
    issue = m.group(1) if (m := ISSUE_RE.search(raw)) else None

    venue = YEAR_RE.sub("", raw)
    if year is not None and not YEAR_RE.search(raw):
        venue = BARE_YEAR_RE.sub("", venue, count=1)
    venue = VOLUME_RE.sub("", venue)
    venue = ISSUE_RE.sub("", venue)
    venue = re.sub(r"\(\s*\)", "", venue)
    # Garuda joins "venue : full-title (month)" and "venue , : month", so the
    # leftovers arrive as runs of separators. Collapse them to one clean cut.
    venue = re.split(r"\s*[,:]\s*[,:]\s*|\s+:\s+", venue)[0]
    venue = re.sub(r"[,:]+\s*$", "", venue)
    venue = WS_RE.sub(" ", venue).strip(" .,:;-")
    return (venue or None), year, volume, issue


def _to_paper(item) -> Optional[Paper]:
    title_link = item.select_one("a.title-article")
    if title_link is None:
        return None

    title = _text(title_link)
    if not title:
        return None

    url = None
    if href := title_link.get("href"):
        url = href if href.startswith("http") else BASE + href

    authors = [
        cleaned
        for anchor in item.select("a.author-article")
        if (cleaned := AUTHOR_TRAILER_RE.sub("", _text(anchor)))
    ]

    venue = year = None
    subtitles = item.select("xmp.subtitle-article")
    if subtitles:
        venue, year, _, _ = _parse_venue(_text(subtitles[0]))

    paper = Paper(
        title=title,
        authors=authors,
        venue=venue,
        year=year,
        url=url,
        sources=["garuda"],
    )
    if url and (m := TRAILING_ID_RE.search(url)):
        paper.ids["garuda"] = m.group(1)
    return paper


def _document_id(identifier: str) -> Optional[str]:
    """Extract the numeric Garuda document id, rejecting foreign identifiers.

    A bare number is ambiguous across providers (Semantic Scholar treats any
    digits as a CorpusId), so callers that know the source pass a prefixed
    value or the detail URL.
    """
    value = (identifier or "").strip()
    if not value:
        return None
    if m := TRAILING_ID_RE.search(value):
        return m.group(1)
    if value.lower().startswith("garuda:"):
        value = value.split(":", 1)[1].strip()
    return value if value.isdigit() else None


def _to_detail_paper(html: str, document_id: str) -> Optional[Paper]:
    soup = BeautifulSoup(html, "lxml")
    display = soup.select_one("div.article-display")
    if display is None:
        return None

    title = ""
    if header := display.select_one("h3.ui.header"):
        title = _text(header)
    if not title:
        return None

    authors = [
        name
        for anchor in display.select("a[href*='/author/view/']")
        if (name := _text(anchor))
    ]

    # The first two <xmp> blocks of the article wrapper hold the journal name
    # and the "Vol. 1 No. 2 (2024)" line; later ones are title, authors, abstract.
    meta = display.select("div > xmp")
    venue = _text(meta[0]) if len(meta) > 0 else None
    year = None
    if len(meta) > 1:
        _, year, _, _ = _parse_venue(_text(meta[1]))

    abstract = None
    if node := display.select_one(".abstract-article"):
        abstract = _text(node) or None

    # The download link lives in the sidebar segment, outside ``article-display``.
    pdf_url = None
    for anchor in soup.select("a[href]"):
        if "download original" in _text(anchor).lower():
            pdf_url = anchor["href"]
            break

    return Paper(
        title=title,
        authors=authors,
        abstract=abstract,
        venue=venue or None,
        year=year,
        url=f"{BASE}/documents/detail/{document_id}",
        pdf_url=pdf_url,
        sources=["garuda"],
        ids={"garuda": document_id},
    )


class GarudaProvider(ProviderBase):
    """Garuda article search via HTML scraping (no official API).

    Every discipline is indexed, so ``supports_tech_only`` stays False. The
    list page carries no DOI, abstract, or citation count; ``ids["garuda"]``
    keeps the numeric document id so later enrichment can re-locate the record.
    """

    name = "garuda"
    supports_search = True
    supports_citations = False
    supports_author_search = False
    supports_references = False
    supports_related = False
    supports_tech_only = False
    supports_filters = frozenset({"year_from", "year_to"})
    enricher = False

    async def search(
        self,
        query: str,
        limit: int,
        year_from: Optional[int] = None,
        year_to: Optional[int] = None,
        tech_only: bool = False,
        author: Optional[str] = None,
        venue: Optional[str] = None,
        offset: int = 0,
    ) -> List[Paper]:
        page = offset // PAGE_SIZE + 1
        self.last_query_note = None

        used_query = query
        papers: List[Paper] = []
        for attempt, candidate in enumerate(_query_variants(query)):
            if attempt:
                # Garuda throttles rapid repeat queries; a short pause keeps a
                # fallback ladder from tripping the rate limiter.
                await asyncio.sleep(FALLBACK_PAUSE_SECONDS)
            html = await self._fetch_text(
                f"{BASE}/documents",
                params={"q": candidate, "page": page},
            )
            papers = [
                paper
                for item in BeautifulSoup(html, "lxml").select("div.article-item")
                if (paper := _to_paper(item)) is not None
            ]
            used_query = candidate
            if papers:
                break

        if used_query != query:
            self.last_query_note = (
                f"no results for {query!r}; narrowed to {used_query!r}"
            )

        if year_from is not None:
            papers = [p for p in papers if p.year is not None and p.year >= year_from]
        if year_to is not None:
            papers = [p for p in papers if p.year is not None and p.year <= year_to]

        start = offset % PAGE_SIZE
        return papers[start : start + limit]

    async def get(self, identifier: str) -> Optional[Paper]:
        document_id = _document_id(identifier)
        if not document_id:
            return None
        html = await self._fetch_text(f"{BASE}/documents/detail/{document_id}")
        return _to_detail_paper(html, document_id)
