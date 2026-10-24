import re
from typing import List, Optional

from ..config import get_polite_email
from ..models import Paper
from ..utils import normalize_doi, parse_year
from .base import ProviderBase

OPENALEX_URL = "https://api.openalex.org/works"
CS_CONCEPT_ID = "C41008148"
_DOI_URL_PREFIXES = ("https://doi.org/", "http://doi.org/")
_OPENALEX_ID = re.compile(r"W\d+")
_OPENALEX_URL_PREFIXES = ("https://openalex.org/", "http://openalex.org/")


def reconstruct_abstract(inverted_index):
    if not inverted_index:
        return None
    positions = []
    for word, idxs in inverted_index.items():
        for i in idxs:
            positions.append((i, word))
    if not positions:
        return None
    positions.sort()
    return " ".join(word for _, word in positions)


class OpenAlexProvider(ProviderBase):
    name = "openalex"
    supports_search = True
    supports_citations = True
    supports_author_search = True
    supports_references = True
    supports_filters = frozenset({"author", "venue"})
    supports_tech_only = True

    @staticmethod
    def _to_paper(work):
        authors = []
        for a in work.get("authorships", []) or []:
            name = (a.get("author") or {}).get("display_name")
            if name:
                authors.append(name)
        primary = work.get("primary_location") or {}
        source = primary.get("source") or {}
        oa = work.get("open_access") or {}
        return Paper(
            doi=normalize_doi(work.get("doi")),
            title=work.get("title") or work.get("display_name") or "",
            abstract=reconstruct_abstract(work.get("abstract_inverted_index")),
            year=parse_year(work.get("publication_year")),
            authors=authors,
            venue=source.get("display_name"),
            citation_count=work.get("cited_by_count"),
            url=primary.get("landing_page_url") or work.get("id"),
            pdf_url=primary.get("pdf_url") or oa.get("oa_url"),
            is_open_access=oa.get("is_oa"),
            type=work.get("type"),
            sources=["openalex"],
            ids={"openalex": work.get("id")} if work.get("id") else {},
        )

    def _filters(self, year_from, year_to, tech_only, author=None, venue=None):
        filters = []
        if author:
            # A comma separates filters in OpenAlex, so a name like
            # "Harzing, Anne-Wil" must be flattened to spaces first.
            name = " ".join(author.replace(",", " ").split())
            filters.append(f"raw_author_name.search:{name}")
        if venue:
            # Same comma constraint as author: a comma would split filters.
            name = " ".join(venue.replace(",", " ").split())
            filters.append(f"primary_location.source.display_name.search:{name}")
        if year_from:
            filters.append(f"from_publication_date:{year_from}-01-01")
        if year_to:
            filters.append(f"to_publication_date:{year_to}-12-31")
        if tech_only:
            filters.append(f"concepts.id:{CS_CONCEPT_ID}")
        return filters

    @staticmethod
    def _page_for(offset: int, limit: int) -> int:
        # OpenAlex paginates by page number alongside per-page, so derive the
        # page that skips ``offset`` records.
        return offset // max(limit, 1) + 1

    async def _search_filtered(self, filters, limit, offset) -> List[Paper]:
        params = {"per-page": limit, "mailto": get_polite_email()}
        if filters:
            params["filter"] = ",".join(filters)
        if offset:
            params["page"] = self._page_for(offset, limit)
        data = await self._fetch_json(OPENALEX_URL, params=params)
        return [self._to_paper(w) for w in data.get("results", []) or []]

    async def search(self, query: str, limit: int, year_from=None, year_to=None, tech_only=False, author=None, venue=None, offset: int = 0) -> List[Paper]:
        params = {"search": query, "per-page": limit, "mailto": get_polite_email()}
        filters = self._filters(year_from, year_to, tech_only, author=author, venue=venue)
        if filters:
            params["filter"] = ",".join(filters)
        if offset:
            params["page"] = self._page_for(offset, limit)
        data = await self._fetch_json(OPENALEX_URL, params=params)
        return [self._to_paper(w) for w in data.get("results", []) or []]

    async def search_author(self, author: str, limit: int, year_from=None, year_to=None, venue=None, offset: int = 0) -> List[Paper]:
        filters = self._filters(year_from, year_to, False, author=author, venue=venue)
        return await self._search_filtered(filters, limit, offset)

    @staticmethod
    def _work_id(identifier: str) -> Optional[str]:
        if not identifier:
            return None
        value = identifier.strip()
        if value.lower().startswith("openalex:"):
            value = value[len("openalex:"):].strip()
        if value.lower().startswith(_DOI_URL_PREFIXES):
            value = normalize_doi(value) or value
        if value.startswith("10."):
            return f"doi:{value}"
        lowered = value.rstrip("/").lower()
        for prefix in _OPENALEX_URL_PREFIXES:
            if lowered.startswith(prefix):
                value = value[len(prefix):]
                break
        if _OPENALEX_ID.fullmatch(value):
            return value
        return None

    async def get(self, identifier: str) -> Optional[Paper]:
        work_id = self._work_id(identifier)
        if not work_id:
            return None
        data = await self._fetch_json(
            f"{OPENALEX_URL}/{work_id}", params={"mailto": get_polite_email()}
        )
        return self._to_paper(data) if data else None

    async def _resolve_work(self, identifier: str) -> Optional[dict]:
        """Fetch the raw work record, resolving DOIs/URLs to an OpenAlex id."""
        work_id = self._work_id(identifier)
        if not work_id:
            return None
        data = await self._fetch_json(
            f"{OPENALEX_URL}/{work_id}", params={"mailto": get_polite_email()}
        )
        return data or None

    @staticmethod
    def _short_id(work_url: str) -> str:
        return (work_url or "").rsplit("/", 1)[-1]

    async def citations(self, identifier: str, limit: int) -> List[Paper]:
        work = await self._resolve_work(identifier)
        if not work or not work.get("id"):
            return []
        # ``cites:`` expects an OpenAlex Work id (W...), never a doi: prefix.
        params = {
            "filter": f"cites:{self._short_id(work['id'])}",
            "per-page": limit,
            "mailto": get_polite_email(),
        }
        data = await self._fetch_json(OPENALEX_URL, params=params)
        return [self._to_paper(w) for w in data.get("results", []) or []]

    async def references(self, identifier: str, limit: int) -> List[Paper]:
        work = await self._resolve_work(identifier)
        if not work:
            return []
        ref_ids = [self._short_id(u) for u in work.get("referenced_works") or []]
        ref_ids = [rid for rid in ref_ids if rid][:limit]
        if not ref_ids:
            return []
        params = {
            "filter": f"openalex:{'|'.join(ref_ids)}",
            "per-page": min(limit, 50),
            "mailto": get_polite_email(),
        }
        data = await self._fetch_json(OPENALEX_URL, params=params)
        return [self._to_paper(w) for w in data.get("results", []) or []]
