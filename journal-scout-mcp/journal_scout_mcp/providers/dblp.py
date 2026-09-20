from typing import List

from ..models import Paper
from ..utils import normalize_doi
from .base import ProviderBase

DBLP_URL = "https://dblp.org/search/publ/api"


class DblpProvider(ProviderBase):
    name = "dblp"
    supports_search = True

    @staticmethod
    def _to_paper(info):
        authors = []
        raw_authors = (info.get("authors") or {}).get("author") or []
        if isinstance(raw_authors, dict):
            raw_authors = [raw_authors]
        for a in raw_authors:
            text = a.get("text") if isinstance(a, dict) else a
            if text:
                authors.append(text)
        year = None
        if info.get("year"):
            try:
                year = int(info["year"])
            except (TypeError, ValueError):
                year = None
        doi = normalize_doi(info.get("doi"))
        title = (info.get("title") or "").rstrip(".").strip()
        return Paper(
            doi=doi,
            title=title,
            year=year,
            authors=authors,
            venue=info.get("venue"),
            url=info.get("ee") or info.get("url"),
            type=info.get("type"),
            sources=["dblp"],
            ids={"dblp": info.get("doi")} if info.get("doi") else {},
        )

    async def search(self, query: str, limit: int, year_from=None, year_to=None, tech_only=False) -> List[Paper]:
        params = {"q": query, "format": "json", "h": limit}
        data = await self._fetch_json(DBLP_URL, params=params)
        hits = ((data.get("result") or {}).get("hits") or {}).get("hit") or []
        results = []
        for hit in hits:
            info = hit.get("info") or {}
            year = None
            if info.get("year"):
                try:
                    year = int(info["year"])
                except (TypeError, ValueError):
                    year = None
            if year_from and year is not None and year < year_from:
                continue
            if year_to and year is not None and year > year_to:
                continue
            results.append(self._to_paper(info))
        return results
