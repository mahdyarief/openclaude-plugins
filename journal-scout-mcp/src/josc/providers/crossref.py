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
    supports_references = True
    supports_filters = frozenset({"author", "venue", "affiliation", "issn", "doi"})

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
        papers = [self._to_paper(i) for i in items]
        # Crossref returns container records (journal-issue, proceedings, ...)
        # for broad queries. They carry no title and cannot be cited as works.
        return [paper for paper in papers if (paper.title or "").strip()]

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

    async def _works(self, params, year_from, year_to, extra_filters=None) -> List[Paper]:
        """Shared GET against ``/works`` used by both search entry points.

        Crossref carries every restriction in one comma-joined ``filter``
        parameter, so the date bounds are merged with the field filters
        rather than replacing them.
        """
        year_filter = self._year_filter(year_from, year_to)
        filters = [year_filter] + list(extra_filters or [])
        merged = ",".join(f for f in filters if f)
        if merged:
            params["filter"] = merged
        params["mailto"] = get_polite_email()
        data = await self._fetch_json(CROSSREF_URL, params=params)
        return self._items_to_papers(data)

    async def search(self, query: str, limit: int, year_from=None, year_to=None, tech_only=False, author=None, venue=None, offset: int = 0, affiliation=None, issn=None, doi=None) -> List[Paper]:
        params = {"query": query, "rows": limit, "offset": offset}
        if author:
            params["query.author"] = author
        if venue:
            params["query.container-title"] = venue
        if affiliation:
            params["query.affiliation"] = affiliation
        extra_filters = []
        if issn:
            extra_filters.append(f"issn:{issn}")
        if doi:
            extra_filters.append(f"doi:{doi}")
        return await self._works(params, year_from, year_to, extra_filters)

    async def search_author(self, author: str, limit: int, year_from=None, year_to=None, venue=None, offset: int = 0, affiliation=None, issn=None, doi=None) -> List[Paper]:
        params = {"query.author": author, "rows": limit, "offset": offset}
        if venue:
            params["query.container-title"] = venue
        if affiliation:
            params["query.affiliation"] = affiliation
        extra_filters = []
        if issn:
            extra_filters.append(f"issn:{issn}")
        if doi:
            extra_filters.append(f"doi:{doi}")
        return await self._works(params, year_from, year_to, extra_filters)

    async def get(self, identifier: str) -> Optional[Paper]:
        doi = normalize_doi(identifier)
        if not doi:
            return None
        data = await self._fetch_json(f"{CROSSREF_URL}/{doi}", params={"mailto": get_polite_email()})
        message = data.get("message")
        return self._to_paper(message) if message else None

    @staticmethod
    def _to_reference_paper(ref) -> Paper:
        """Build a node from a raw ``message.reference`` entry.

        Crossref references are often only partially structured, so fall
        back to the unstructured string for the title.
        """
        doi = normalize_doi(ref.get("DOI"))
        title = ref.get("article-title") or ref.get("volume-title") or ref.get("unstructured") or ""
        author = ref.get("author")
        authors = [author] if isinstance(author, str) and author else []
        return Paper(
            doi=doi,
            title=title,
            year=parse_year(ref.get("year")),
            authors=authors,
            venue=ref.get("journal-title"),
            sources=["crossref"],
            ids={"crossref": ref["DOI"]} if ref.get("DOI") else {},
        )

    async def references(self, identifier: str, limit: int) -> List[Paper]:
        doi = normalize_doi(identifier)
        if not doi:
            return []
        data = await self._fetch_json(f"{CROSSREF_URL}/{doi}", params={"mailto": get_polite_email()})
        message = data.get("message") or {}
        raw = message.get("reference") or []
        if not raw:
            return []

        fallback = [self._to_reference_paper(r) for r in raw if isinstance(r, dict)]
        known_dois = [p.doi for p in fallback if p.doi][:limit]

        if not known_dois:
            return fallback[:limit]

        # The parent record only carries stub references; batch-fetch the
        # cited works so nodes have citation counts and venue metadata.
        params = {
            "filter": ",".join(f"doi:{d}" for d in known_dois),
            "rows": min(len(known_dois), 100),
            "mailto": get_polite_email(),
        }
        details = await self._fetch_json(CROSSREF_URL, params=params)
        resolved = {p.doi: p for p in self._items_to_papers(details) if p.doi}

        papers: List[Paper] = []
        seen = set()
        for paper in fallback:
            if paper.doi and paper.doi in resolved:
                paper = resolved[paper.doi]
            if paper.doi:
                if paper.doi in seen:
                    continue
                seen.add(paper.doi)
            papers.append(paper)
        return papers[:limit]
