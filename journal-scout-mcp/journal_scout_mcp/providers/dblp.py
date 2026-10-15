from typing import List

from ..models import Paper
from ..utils import normalize_doi, parse_year
from .base import ProviderBase

DBLP_URL = "https://dblp.org/search/publ/api"


class DblpProvider(ProviderBase):
    name = "dblp"
    supports_search = True

    @staticmethod
    def _authors(info) -> List[str]:
        authors = []
        raw = (info.get("authors") or {}).get("author") or []
        if isinstance(raw, dict):
            raw = [raw]
        for a in raw:
            text = a.get("text") if isinstance(a, dict) else a
            if text:
                authors.append(text)
        return authors

    @classmethod
    def _to_paper(cls, info):
        title = (info.get("title") or "").rstrip(".").strip()
        return Paper(
            doi=normalize_doi(info.get("doi")),
            title=title,
            year=parse_year(info.get("year")),
            authors=cls._authors(info),
            venue=info.get("venue"),
            url=info.get("ee") or info.get("url"),
            type=info.get("type"),
            sources=["dblp"],
            ids={"dblp": info.get("doi")} if info.get("doi") else {},
        )

    async def search(self, query: str, limit: int, year_from=None, year_to=None, tech_only=False, offset: int = 0) -> List[Paper]:
        # DBLP paginates with ``f`` (first hit index) rather than a page number.
        params = {"q": query, "format": "json", "h": limit, "f": offset}
        data = await self._fetch_json(DBLP_URL, params=params)
        hits = ((data.get("result") or {}).get("hits") or {}).get("hit") or []
        results = []
        for hit in hits:
            paper = self._to_paper(hit.get("info") or {})
            if year_from and paper.year is not None and paper.year < year_from:
                continue
            if year_to and paper.year is not None and paper.year > year_to:
                continue
            results.append(paper)
        return results
