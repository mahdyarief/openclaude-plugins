from typing import Any, Dict, List, Optional

from ..config import get_api_key
from ..models import Paper
from ..utils import normalize_doi
from .base import ProviderBase

SCOPUS_BASE = "https://api.elsevier.com/content/"
SCIVAL_BASE = "https://api.elsevier.com/analytics/scival/"


def _year_from_date(value: str) -> Optional[int]:
    if value and len(value) >= 4 and value[:4].isdigit():
        return int(value[:4])
    return None


class ScopusProvider(ProviderBase):
    name = "scopus"
    supports_search = True

    def __init__(self, fetcher, config=None):
        super().__init__(fetcher, config)
        self._api_key = (config or {}).get("api_key")

    def _headers(self):
        key = self._api_key or get_api_key()
        return {
            "X-ELS-APIKey": key,
            "Accept": "application/json",
        }

    @staticmethod
    def _to_paper(entry):
        scopus_id = entry.get("dc:identifier") or entry.get("eid")
        doi = normalize_doi(entry.get("prism:doi") or entry.get("doi"))
        creator = entry.get("dc:creator")
        authors = [creator] if creator else []
        year = _year_from_date(entry.get("prism:coverDate") or entry.get("prism:coverDisplayDate") or "")
        cited = entry.get("citedby-count")
        ids = {}
        if scopus_id:
            ids["scopus"] = scopus_id
        if doi:
            ids["doi"] = doi
        return Paper(
            doi=doi,
            title=entry.get("dc:title") or "",
            abstract=entry.get("dc:description"),
            year=year,
            authors=authors,
            venue=entry.get("prism:publicationName"),
            citation_count=int(cited) if cited is not None and str(cited).isdigit() else None,
            url=entry.get("prism:url") or entry.get("link"),
            type=entry.get("subtypeDescription"),
            sources=["scopus"],
            ids=ids,
        )

    async def search(self, query: str, limit: int, year_from=None, year_to=None, tech_only=False) -> List[Paper]:
        q = query
        if tech_only:
            q = f"({q}) AND SUBJAREA(COMP)"
        if year_from:
            q = f"{q} AND PUBYEAR > {year_from - 1}"
        if year_to:
            q = f"{q} AND PUBYEAR < {year_to + 1}"
        params = {"query": q, "count": limit}
        data = await self._fetch_json(
            f"{SCOPUS_BASE}search/scopus", params=params, headers=self._headers()
        )
        entries = (data.get("search-results") or {}).get("entry") or []
        results = []
        for entry in entries:
            if isinstance(entry, dict) and "error" in entry:
                continue
            results.append(self._to_paper(entry))
        return results

    async def get(self, identifier: str) -> Optional[Paper]:
        sid = identifier.replace("SCOPUS_ID:", "")
        data = await self._fetch_json(
            f"{SCOPUS_BASE}abstract/scopus_id/{sid}", headers=self._headers()
        )
        core = (data.get("abstracts-retrieval-response") or {}).get("coredata") or {}
        return self._to_paper(core) if core else None

    async def citations(self, identifier: str, limit: int) -> List[Paper]:
        sid = identifier.replace("SCOPUS_ID:", "")
        data = await self._fetch_json(
            f"{SCOPUS_BASE}search/scopus",
            params={"query": f"REF({sid})", "count": limit},
            headers=self._headers(),
        )
        entries = (data.get("search-results") or {}).get("entry") or []
        return [self._to_paper(e) for e in entries if isinstance(e, dict) and "error" not in e]

    async def scival_author_metrics(self, author_id: str, year_from=None, year_to=None) -> Dict[str, Any]:
        params: Dict[str, Any] = {"metricTypes": "publications,citations,hIndex"}
        if year_from:
            params["startYear"] = year_from
        if year_to:
            params["endYear"] = year_to
        return await self._fetch_json(
            f"{SCIVAL_BASE}author/{author_id}/metrics", params=params, headers=self._headers()
        )

    async def scival_institution_metrics(self, institution_id: str, year_from=None, year_to=None) -> Dict[str, Any]:
        params: Dict[str, Any] = {"metricTypes": "publications,citations,hIndex"}
        if year_from:
            params["startYear"] = year_from
        if year_to:
            params["endYear"] = year_to
        return await self._fetch_json(
            f"{SCIVAL_BASE}institution/{institution_id}/metrics", params=params, headers=self._headers()
        )

    async def scival_author_lookup(self, query: str, count: int = 10) -> Dict[str, Any]:
        return await self._fetch_json(
            f"{SCIVAL_BASE}author", params={"query": query, "count": count}, headers=self._headers()
        )

    async def scival_institution_lookup(self, query: str, count: int = 10) -> Dict[str, Any]:
        return await self._fetch_json(
            f"{SCIVAL_BASE}institution", params={"query": query, "count": count}, headers=self._headers()
        )

    async def scival_topic_metrics(self, topic_id: str, year_from=None, year_to=None) -> Dict[str, Any]:
        params: Dict[str, Any] = {"metricTypes": "publications,citations"}
        if year_from:
            params["startYear"] = year_from
        if year_to:
            params["endYear"] = year_to
        return await self._fetch_json(
            f"{SCIVAL_BASE}topic/{topic_id}/metrics", params=params, headers=self._headers()
        )

    async def get_author(self, author_id: str) -> Dict[str, Any]:
        return await self._fetch_json(
            f"{SCOPUS_BASE}author/author_id/{author_id}", headers=self._headers()
        )

    async def get_quota_status(self) -> Dict[str, Any]:
        return {
            "note": "Elsevier does not expose a quota endpoint. Quota is tracked "
            "via the X-RateLimit-* and X-ELS-Status response headers on actual "
            "API calls; a 429 with QUOTA_EXCEEDED means the weekly quota is spent.",
        }
