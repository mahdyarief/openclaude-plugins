import re
import xml.etree.ElementTree as ET
from typing import List, Optional

from ..models import Paper
from ..utils import normalize_doi
from .base import ProviderBase

ARXIV_URL = "https://export.arxiv.org/api/query"
ATOM = "{http://www.w3.org/2005/Atom}"
TECH_CATEGORIES = ["cs.AI", "cs.LG", "cs.CL", "cs.CR", "cs.NI", "cs.CV", "cs.SE"]


def _arxiv_id(raw_id: str) -> str:
    if not raw_id:
        return ""
    return raw_id.rstrip("/").rsplit("/", 1)[-1]


class ArxivProvider(ProviderBase):
    name = "arxiv"
    supports_search = True

    @staticmethod
    def _to_paper(entry):
        raw_id = entry.findtext(f"{ATOM}id") or ""
        authors = [a.findtext(f"{ATOM}name") for a in entry.findall(f"{ATOM}author")]
        pdf_url = None
        for link in entry.findall(f"{ATOM}link"):
            if link.get("type") == "application/pdf":
                pdf_url = link.get("href")
        categories = [c.get("term") for c in entry.findall(f"{ATOM}category")]
        if not pdf_url:
            aid = _arxiv_id(raw_id)
            pdf_url = f"https://arxiv.org/pdf/{aid}" if aid else None
        published = entry.findtext(f"{ATOM}published") or ""
        year = int(published[:4]) if published[:4].isdigit() else None
        aid = _arxiv_id(raw_id)
        return Paper(
            title=" ".join((entry.findtext(f"{ATOM}title") or "").split()),
            abstract=" ".join((entry.findtext(f"{ATOM}summary") or "").split()),
            year=year,
            authors=[a for a in authors if a],
            venue=", ".join(c for c in categories if c) or None,
            url=raw_id or None,
            pdf_url=pdf_url,
            type="preprint",
            sources=["arxiv"],
            ids={"arxiv": aid} if aid else {},
        )

    async def search(self, query: str, limit: int, year_from=None, year_to=None, tech_only=False) -> List[Paper]:
        search_query = f"all:{query}"
        if tech_only:
            cats = " OR ".join(f"cat:{c}" for c in TECH_CATEGORIES)
            search_query = f"({search_query}) AND ({cats})"
        params = {
            "search_query": search_query,
            "start": 0,
            "max_results": limit,
            "sortBy": "relevance",
            "sortOrder": "descending",
        }
        text = await self._fetch_text(ARXIV_URL, params=params)
        feed = ET.fromstring(text)
        results = []
        for entry in feed.findall(f"{ATOM}entry"):
            paper = self._to_paper(entry)
            if year_from and paper.year and paper.year < year_from:
                continue
            if year_to and paper.year and paper.year > year_to:
                continue
            results.append(paper)
        return results

    async def get(self, identifier: str) -> Optional[Paper]:
        aid = _arxiv_id(identifier)
        if not aid:
            return None
        text = await self._fetch_text(ARXIV_URL, params={"id_list": aid})
        feed = ET.fromstring(text)
        entries = feed.findall(f"{ATOM}entry")
        return self._to_paper(entries[0]) if entries else None
