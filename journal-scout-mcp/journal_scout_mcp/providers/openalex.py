from typing import List, Optional

from ..config import get_polite_email
from ..models import Paper
from ..utils import normalize_doi
from .base import ProviderBase

OPENALEX_URL = "https://api.openalex.org/works"
CS_CONCEPT_ID = "C41008148"
_DOI_URL_PREFIXES = ("https://doi.org/", "http://doi.org/")


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
            year=work.get("publication_year"),
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

    def _filters(self, year_from, year_to, tech_only):
        filters = []
        if year_from:
            filters.append(f"from_publication_date:{year_from}-01-01")
        if year_to:
            filters.append(f"to_publication_date:{year_to}-12-31")
        if tech_only:
            filters.append(f"concepts.id:{CS_CONCEPT_ID}")
        return filters

    async def search(self, query: str, limit: int, year_from=None, year_to=None, tech_only=False) -> List[Paper]:
        params = {"search": query, "per-page": limit, "mailto": get_polite_email()}
        filters = self._filters(year_from, year_to, tech_only)
        if filters:
            params["filter"] = ",".join(filters)
        data = await self._fetch_json(OPENALEX_URL, params=params)
        return [self._to_paper(w) for w in data.get("results", []) or []]

    @staticmethod
    def _work_id(identifier: str) -> str:
        if identifier.lower().startswith(_DOI_URL_PREFIXES):
            identifier = normalize_doi(identifier) or identifier
        return f"doi:{identifier}" if identifier.startswith("10.") else identifier

    async def get(self, identifier: str) -> Optional[Paper]:
        work_id = self._work_id(identifier)
        data = await self._fetch_json(
            f"{OPENALEX_URL}/{work_id}", params={"mailto": get_polite_email()}
        )
        return self._to_paper(data) if data else None

    async def citations(self, identifier: str, limit: int) -> List[Paper]:
        work_id = self._work_id(identifier)
        params = {
            "filter": f"cites:{work_id}",
            "per-page": limit,
            "mailto": get_polite_email(),
        }
        data = await self._fetch_json(OPENALEX_URL, params=params)
        return [self._to_paper(w) for w in data.get("results", []) or []]