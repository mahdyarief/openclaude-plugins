import re
from typing import List, Optional

from ..config import get_semantic_scholar_key
from ..models import Paper
from ..utils import normalize_doi, parse_year
from .base import ProviderBase

S2_URL = "https://api.semanticscholar.org/graph/v1"
FIELDS = "title,abstract,year,citationCount,authors,externalIds,openAccessPdf,venue,publicationTypes,tldr"
# The relation endpoints reject a few fields the paper endpoints accept
# (``tldr`` among them), so they get their own narrower projection.
RELATION_FIELDS = "title,abstract,year,citationCount,authors,externalIds,openAccessPdf,venue,publicationTypes"
_DOI_URL_PREFIXES = ("https://doi.org/", "http://doi.org/")
_NEW_ARXIV_ID = re.compile(r"\d{4}\.\d{4,5}(v\d+)?")
_S2_PAPER_ID = re.compile(r"[0-9a-f]{40}")
_S2_PREFIXES = frozenset(
    {"doi", "arxiv", "mag", "acl", "pmid", "pmcid", "corpusid", "url"}
)


class SemanticScholarProvider(ProviderBase):
    name = "semanticscholar"
    supports_search = True
    supports_citations = True
    supports_author_search = True
    supports_references = True
    # ``/paper/search`` has a ``venue`` parameter; it has no author filter, so
    # only ``venue`` is advertised.
    supports_filters = frozenset({"venue"})

    def _headers(self):
        key = get_semantic_scholar_key()
        return {"x-api-key": key} if key else None

    @staticmethod
    def _to_paper(item):
        authors = [a.get("name") for a in item.get("authors", []) or [] if a.get("name")]
        external = item.get("externalIds") or {}
        doi = normalize_doi(external.get("DOI"))
        oa = item.get("openAccessPdf") or {}
        ids = {"semanticscholar": item.get("paperId")} if item.get("paperId") else {}
        if doi:
            ids["doi"] = doi
        if external.get("ArXiv"):
            ids["arxiv"] = external["ArXiv"]
        return Paper(
            doi=doi,
            title=item.get("title") or "",
            abstract=item.get("abstract") or (item.get("tldr") or {}).get("text"),
            year=parse_year(item.get("year")),
            authors=authors,
            venue=item.get("venue") or None,
            citation_count=item.get("citationCount"),
            url=f"https://www.semanticscholar.org/paper/{item.get('paperId')}" if item.get("paperId") else None,
            pdf_url=oa.get("url"),
            is_open_access=bool(oa.get("url")),
            type=", ".join(item.get("publicationTypes") or []) or None,
            sources=["semanticscholar"],
            ids=ids,
        )

    @staticmethod
    def _ident(identifier: str) -> Optional[str]:
        if not identifier:
            return None
        value = identifier.strip()
        if value.lower().startswith(_DOI_URL_PREFIXES):
            doi = normalize_doi(value)
            if doi:
                return f"DOI:{doi}"
        if ":" in value:
            scheme = value.split(":", 1)[0].lower()
            if scheme in _S2_PREFIXES:
                return value
            return None
        if value.startswith("10."):
            return f"DOI:{value}"
        if _NEW_ARXIV_ID.fullmatch(value):
            return f"ARXIV:{value}"
        if value.isdigit():
            return f"CorpusId:{value}"
        if _S2_PAPER_ID.fullmatch(value.lower()):
            return value
        return None

    async def search(self, query: str, limit: int, year_from=None, year_to=None, tech_only=False, author=None, venue=None, offset: int = 0) -> List[Paper]:
        params = {"query": query, "limit": limit, "fields": FIELDS}
        if offset:
            params["offset"] = offset
        year_range = self._year_range(year_from, year_to)
        if year_range:
            params["year"] = year_range
        if tech_only:
            params["fieldsOfStudy"] = "Computer Science"
        if venue:
            params["venue"] = venue
        data = await self._fetch_json(f"{S2_URL}/paper/search", params=params, headers=self._headers())
        return [self._to_paper(i) for i in data.get("data", []) or []]

    @staticmethod
    def _year_range(year_from, year_to) -> Optional[str]:
        """S2's ``year=lo-hi`` clause, or ``None`` when no bound was given."""
        if not (year_from or year_to):
            return None
        return f"{year_from or ''}-{year_to or ''}"

    async def search_author(self, author: str, limit: int, year_from=None, year_to=None, venue=None, offset: int = 0) -> List[Paper]:
        """Resolve the name to an author id, then list that author's papers.

        Semantic Scholar's paper search has no author filter, so author
        search is a two-step lookup: ``/author/search`` picks the best
        match, then ``/author/{id}/papers`` lists their output. The papers
        endpoint has no server-side year filter, so the bounds are applied
        to the parsed records.
        """
        found = await self._fetch_json(
            f"{S2_URL}/author/search",
            params={"query": author, "limit": 1, "fields": "authorId"},
            headers=self._headers(),
        )
        matches = found.get("data") or []
        author_id = matches[0].get("authorId") if matches else None
        if not author_id:
            return []
        params = {"limit": limit, "fields": RELATION_FIELDS}
        if offset:
            params["offset"] = offset
        data = await self._fetch_json(
            f"{S2_URL}/author/{author_id}/papers", params=params, headers=self._headers()
        )
        papers = [self._to_paper(p) for p in data.get("data", []) or []]
        if year_from:
            papers = [p for p in papers if not p.year or p.year >= year_from]
        if year_to:
            papers = [p for p in papers if not p.year or p.year <= year_to]
        if venue:
            # The author-papers endpoint has no venue filter; apply it locally.
            needle = venue.lower()
            papers = [p for p in papers if p.venue and needle in p.venue.lower()]
        return papers

    async def get(self, identifier: str) -> Optional[Paper]:
        ident = self._ident(identifier)
        if not ident:
            return None
        data = await self._fetch_json(
            f"{S2_URL}/paper/{ident}", params={"fields": FIELDS}, headers=self._headers()
        )
        return self._to_paper(data) if data and data.get("paperId") else None

    async def citations(self, identifier: str, limit: int) -> List[Paper]:
        ident = self._ident(identifier)
        if not ident:
            return []
        data = await self._fetch_json(
            f"{S2_URL}/paper/{ident}/citations",
            params={"limit": limit, "fields": RELATION_FIELDS},
            headers=self._headers(),
        )
        return [self._to_paper(e.get("citingPaper") or {}) for e in data.get("data", []) or []]

    async def references(self, identifier: str, limit: int) -> List[Paper]:
        ident = self._ident(identifier)
        if not ident:
            return []
        data = await self._fetch_json(
            f"{S2_URL}/paper/{ident}/references",
            params={"limit": limit, "fields": RELATION_FIELDS},
            headers=self._headers(),
        )
        return [self._to_paper(e.get("citedPaper") or {}) for e in data.get("data", []) or []]
