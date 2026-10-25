from typing import Any, Dict, List, Optional

from ..config import get_api_key
from ..models import Paper, ProviderError
from ..utils import normalize_doi, parse_int, parse_year
from .base import ProviderBase

SCOPUS_BASE = "https://api.elsevier.com/content/"
SCIVAL_BASE = "https://api.elsevier.com/analytics/scival/"
_SCOPUS_ID_PREFIX = "SCOPUS_ID:"
SCIVAL_METRIC_TYPES = "publications,citations,hIndex"
MAX_PAGE_SIZE = 25


class ScopusProvider(ProviderBase):
    name = "scopus"
    supports_search = True
    supports_citations = True
    supports_author_search = True
    supports_references = True
    supports_filters = frozenset({"author", "venue", "affiliation", "issn", "orcid", "doi"})
    supports_tech_only = True

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
    def _author_name(item: Dict[str, Any]) -> str:
        """Best display name for one Elsevier author entry.

        Search results carry ``authname``/``given-name``/``surname`` while
        abstract retrieval nests the names under ``ce:``-prefixed keys (or a
        ``preferred-name`` sub-dict), so accept whichever shape is present.
        """
        if item.get("authname"):
            return str(item["authname"])
        for source in (item.get("preferred-name"), item):
            if not isinstance(source, dict):
                continue
            name = " ".join(
                part for part in [source.get("ce:given-name"), source.get("ce:surname")] if part
            )
            if name:
                return name
        return " ".join(
            part for part in [item.get("given-name"), item.get("surname")] if part
        )

    @staticmethod
    def _authors(entry) -> List[str]:
        """Collect every author Scopus exposes across both response views.

        Search results carry only ``dc:creator`` as a plain string (first
        author); abstract retrieval nests the full list under
        ``dc:creator['author']`` with ``ce:``-prefixed names. Read whichever
        is present instead of dropping co-authors or leaking the raw dict.
        """
        creator = entry.get("dc:creator")
        sources: List[Any] = list(entry.get("author") or [])
        if isinstance(creator, dict):
            sources += list(creator.get("author") or [])
        elif creator:
            sources.append({"authname": creator})

        names: List[str] = []
        for item in sources:
            if not isinstance(item, dict):
                continue
            name = ScopusProvider._author_name(item)
            if name and name not in names:
                names.append(name)
        return names

    @staticmethod
    def _to_paper(entry):
        scopus_id = entry.get("dc:identifier") or entry.get("eid")
        doi = normalize_doi(entry.get("prism:doi") or entry.get("doi"))
        ids = {}
        if scopus_id:
            ids["scopus"] = scopus_id
        if doi:
            ids["doi"] = doi
        return Paper(
            doi=doi,
            title=entry.get("dc:title") or "",
            abstract=entry.get("dc:description"),
            year=parse_year(entry.get("prism:coverDate") or entry.get("prism:coverDisplayDate")),
            authors=ScopusProvider._authors(entry),
            venue=entry.get("prism:publicationName"),
            citation_count=parse_int(entry.get("citedby-count")),
            url=entry.get("prism:url") or entry.get("link"),
            type=entry.get("subtypeDescription"),
            sources=["scopus"],
            ids=ids,
        )

    @staticmethod
    def _reference_authors(entry) -> List[str]:
        """Authors of a ``view=REF`` reference entry.

        Reference records nest the author list under ``author-list.author``
        with the same ``ce:``-prefixed names as abstract retrieval, so they
        cannot go through :meth:`_authors`.
        """
        raw = entry.get("author-list") or {}
        sources = raw.get("author") if isinstance(raw, dict) else None
        names: List[str] = []
        for item in sources or []:
            if not isinstance(item, dict):
                continue
            name = ScopusProvider._author_name(item)
            if name and name not in names:
                names.append(name)
        return names

    @staticmethod
    def _to_reference_paper(entry):
        scopus_id = entry.get("scopus-id")
        doi = normalize_doi(entry.get("prism:doi") or entry.get("doi"))
        ids = {}
        if scopus_id:
            ids["scopus"] = str(scopus_id)
        if doi:
            ids["doi"] = doi
        return Paper(
            doi=doi,
            title=entry.get("title") or "",
            year=parse_year(entry.get("prism:coverDate")),
            authors=ScopusProvider._reference_authors(entry),
            venue=entry.get("sourcetitle"),
            citation_count=parse_int(entry.get("citedby-count")),
            sources=["scopus"],
            ids=ids,
        )

    @staticmethod
    def _year_clause(query: str, year_from, year_to) -> str:
        """Append Scopus PUBYEAR bounds to a query (shared by every search)."""
        if year_from:
            query = f"{query} AND PUBYEAR > {year_from - 1}"
        if year_to:
            query = f"{query} AND PUBYEAR < {year_to + 1}"
        return query

    async def _search_query(self, query: str, limit: int, offset: int) -> List[Paper]:
        # Scopus rejects ``count`` above the API key's service-level maximum
        # (25 for the standard key), so a larger limit is fetched in windows.
        papers: List[Paper] = []
        while len(papers) < limit:
            window = min(MAX_PAGE_SIZE, limit - len(papers))
            params = {"query": query, "count": window, "start": offset + len(papers)}
            data = await self._fetch_json(
                f"{SCOPUS_BASE}search/scopus", params=params, headers=self._headers()
            )
            batch = self._entries_to_papers(data)
            papers.extend(batch)
            if len(batch) < window:
                break
        return papers[:limit]

    async def search(self, query: str, limit: int, year_from=None, year_to=None, tech_only=False, author=None, venue=None, offset: int = 0, affiliation=None, issn=None, orcid=None, doi=None) -> List[Paper]:
        if author:
            query = f"({query}) AND AUTH({author})"
        if venue:
            query = f"({query}) AND SRCTITLE({venue})"
        if affiliation:
            query = f"({query}) AND AFFIL({affiliation})"
        if issn:
            query = f"({query}) AND ISSN({issn})"
        if orcid:
            query = f"({query}) AND ORCID({orcid})"
        if doi:
            query = f"({query}) AND DOI({doi})"
        if tech_only:
            query = f"({query}) AND SUBJAREA(COMP)"
        return await self._search_query(self._year_clause(query, year_from, year_to), limit, offset)

    async def search_author(self, author: str, limit: int, year_from=None, year_to=None, venue=None, offset: int = 0, affiliation=None, issn=None, orcid=None, doi=None) -> List[Paper]:
        # ``AU()`` is not a valid Scopus field; ``AUTH()`` accepts both a
        # surname and a full name ("Harzing, Anne-Wil").
        query = f"AUTH({author})"
        if venue:
            query = f"{query} AND SRCTITLE({venue})"
        if affiliation:
            query = f"{query} AND AFFIL({affiliation})"
        if issn:
            query = f"{query} AND ISSN({issn})"
        if orcid:
            query = f"{query} AND ORCID({orcid})"
        if doi:
            query = f"{query} AND DOI({doi})"
        query = self._year_clause(query, year_from, year_to)
        return await self._search_query(query, limit, offset)

    @staticmethod
    def _entries_to_papers(data) -> List[Paper]:
        entries = (data.get("search-results") or {}).get("entry") or []
        return [
            ScopusProvider._to_paper(e)
            for e in entries
            if isinstance(e, dict) and "error" not in e
        ]

    @staticmethod
    def _scopus_id(identifier: str) -> str:
        ident = (identifier or "").strip()
        if ident.upper().startswith(_SCOPUS_ID_PREFIX):
            ident = ident[len(_SCOPUS_ID_PREFIX):].strip()
        return ident

    @classmethod
    def _identifier_path(cls, identifier: str) -> Optional[str]:
        ident = cls._scopus_id(identifier)
        if ident.isdigit():
            return f"abstract/scopus_id/{ident}"
        doi = normalize_doi(ident)
        if doi and doi.startswith("10."):
            return f"abstract/doi/{doi}"
        return None

    async def _fetch_abstract(self, url: str) -> Dict[str, Any]:
        """Fetch an abstract record at the richest view the key can read.

        ``view=FULL`` is the only view carrying the abstract text, but a key
        without that entitlement answers HTTP 401. Ask for it first, then
        degrade to the default view so callers still receive complete
        metadata instead of a hard error; if the record itself is missing,
        the second attempt's error is the one that surfaces.
        """
        try:
            return await self._fetch_json(url, params={"view": "FULL"}, headers=self._headers())
        except ProviderError:
            return await self._fetch_json(url, headers=self._headers())

    async def get(self, identifier: str) -> Optional[Paper]:
        path = self._identifier_path(identifier)
        if not path:
            return None
        data = await self._fetch_abstract(f"{SCOPUS_BASE}{path}")
        core = (data.get("abstracts-retrieval-response") or {}).get("coredata") or {}
        return self._to_paper(core) if core else None

    async def _resolve_scopus_id(self, identifier: str) -> Optional[str]:
        """Resolve a DOI (or bare id) to the numeric Scopus id.

        ``REF()`` in the search API only accepts the numeric id, so a DOI
        input must first be resolved through abstract retrieval.
        """
        sid = self._scopus_id(identifier)
        if sid.isdigit():
            return sid
        path = self._identifier_path(identifier)
        if not path:
            return None
        data = await self._fetch_abstract(f"{SCOPUS_BASE}{path}")
        core = (data.get("abstracts-retrieval-response") or {}).get("coredata") or {}
        resolved = self._scopus_id(core.get("dc:identifier") or "")
        return resolved if resolved.isdigit() else None

    async def citations(self, identifier: str, limit: int) -> List[Paper]:
        sid = await self._resolve_scopus_id(identifier)
        if not sid:
            return []
        data = await self._fetch_json(
            f"{SCOPUS_BASE}search/scopus",
            params={"query": f"REF({sid})", "count": limit},
            headers=self._headers(),
        )
        return self._entries_to_papers(data)

    async def references(self, identifier: str, limit: int) -> List[Paper]:
        path = self._identifier_path(identifier)
        if not path:
            return []
        data = await self._fetch_json(
            f"{SCOPUS_BASE}{path}",
            params={"view": "REF", "httpAccept": "application/json"},
            headers=self._headers(),
        )
        entries = ((data.get("abstracts-retrieval-response") or {}).get("references") or {}).get("reference") or []
        papers = [
            self._to_reference_paper(e)
            for e in entries
            if isinstance(e, dict) and e.get("title")
        ]
        return papers[:limit]

    def _scival_metric_params(self, year_from=None, year_to=None, metric_types: str = SCIVAL_METRIC_TYPES) -> Dict[str, Any]:
        params: Dict[str, Any] = {"metricTypes": metric_types}
        if year_from:
            params["startYear"] = year_from
        if year_to:
            params["endYear"] = year_to
        return params

    async def scival_author_metrics(self, author_id: str, year_from=None, year_to=None) -> Dict[str, Any]:
        return await self._fetch_json(
            f"{SCIVAL_BASE}author/{author_id}/metrics",
            params=self._scival_metric_params(year_from, year_to),
            headers=self._headers(),
        )

    async def scival_institution_metrics(self, institution_id: str, year_from=None, year_to=None) -> Dict[str, Any]:
        return await self._fetch_json(
            f"{SCIVAL_BASE}institution/{institution_id}/metrics",
            params=self._scival_metric_params(year_from, year_to),
            headers=self._headers(),
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
        return await self._fetch_json(
            f"{SCIVAL_BASE}topic/{topic_id}/metrics",
            params=self._scival_metric_params(year_from, year_to, "publications,citations"),
            headers=self._headers(),
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
