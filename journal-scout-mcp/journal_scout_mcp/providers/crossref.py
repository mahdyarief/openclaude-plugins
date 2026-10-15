from typing import List, Optional

from ..config import get_polite_email
from ..models import Paper
from ..utils import first_of, normalize_doi, parse_year, strip_jats
from .base import ProviderBase

CROSSREF_URL = "https://api.crossref.org/works"


class CrossrefProvider(ProviderBase):
    name = "crossref"
    supports_search = True
    supports_author_search = True

    @staticmethod
    def _to_paper(item):
        authors = []
        for a in item.get("author", []) or []:
            name = " ".join(x for x in [a.get("given"), a.get("family")] if x)
            if name:
                authors.append(name)
        year = None
        for key in ("published", "published-print", "published-online"):
            parts = (item.get(key) or {}).get("date-parts") or []
            if parts and parts[0]:
                year = parse_year(parts[0][0])
                break
        doi = normalize_doi(item.get("DOI"))
        return Paper(
            doi=doi,
            title=first_of(item.get("title")) or "",
            abstract=strip_jats(item.get("abstract")),
            year=year,
            authors=authors,
            venue=first_of(item.get("container-title")),
            citation_count=item.get("is-referenced-by-count"),
            url=item.get("URL"),
            type=item.get("type"),
            sources=["crossref"],
            ids={"crossref": item.get("DOI")} if item.get("DOI") else {},
        )

    def _items_to_papers(self, data) -> List[Paper]:
        items = (data.get("message") or {}).get("items") or []
        return [self._to_paper(i) for i in items]

    @staticmethod
    def _year_filter(year_from, year_to) -> str:
        """Crossref's native date filter, or ``""`` when no bounds were given.

        Crossref filters on full dates, so the bounds are expanded to the
        first/last day of the year rather than the bare year.
        """
        bounds = []
        if year_from:
            bounds.append(f"from-pub-date:{year_from}-01-01")
        if year_to:
            bounds.append(f"until-pub-date:{year_to}-12-31")
        return ",".join(bounds)

    async def _works(self, params, year_from, year_to) -> List[Paper]:
        """Shared GET against ``/works`` used by both search entry points."""
        year_filter = self._year_filter(year_from, year_to)
        if year_filter:
            params["filter"] = year_filter
        params["mailto"] = get_polite_email()
        data = await self._fetch_json(CROSSREF_URL, params=params)
        return self._items_to_papers(data)

    async def search(self, query: str, limit: int, year_from=None, year_to=None, tech_only=False, offset: int = 0) -> List[Paper]:
        return await self._works({"query": query, "rows": limit, "offset": offset}, year_from, year_to)

    async def search_author(self, author: str, limit: int, year_from=None, year_to=None, offset: int = 0) -> List[Paper]:
        return await self._works(
            {"query.author": author, "rows": limit, "offset": offset}, year_from, year_to
        )

    async def get(self, identifier: str) -> Optional[Paper]:
        doi = normalize_doi(identifier)
        if not doi:
            return None
        data = await self._fetch_json(f"{CROSSREF_URL}/{doi}", params={"mailto": get_polite_email()})
        message = data.get("message")
        return self._to_paper(message) if message else None
