import re
from typing import List, Optional

from ..config import get_semantic_scholar_key
from ..models import Paper
from ..utils import normalize_doi
from .base import ProviderBase

S2_URL = "https://api.semanticscholar.org/graph/v1"
FIELDS = "title,abstract,year,citationCount,authors,externalIds,openAccessPdf,venue,publicationTypes,tldr"
_DOI_URL_PREFIXES = ("https://doi.org/", "http://doi.org/")
_NEW_ARXIV_ID = re.compile(r"\d{4}\.\d{4,5}(v\d+)?")
_S2_PAPER_ID = re.compile(r"[0-9a-f]{40}")
_S2_PREFIXES = frozenset(
    {"doi", "arxiv", "mag", "acl", "pmid", "pmcid", "corpusid", "url"}
)


class SemanticScholarProvider(ProviderBase):
    name = "semanticscholar"
    supports_search = True

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
            year=item.get("year"),
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

    async def search(self, query: str, limit: int, year_from=None, year_to=None, tech_only=False) -> List[Paper]:
        params = {"query": query, "limit": limit, "fields": FIELDS}
        if year_from or year_to:
            lo = year_from or ""
            hi = year_to or ""
            params["year"] = f"{lo}-{hi}"
        if tech_only:
            params["fieldsOfStudy"] = "Computer Science"
        data = await self._fetch_json(f"{S2_URL}/paper/search", params=params, headers=self._headers())
        return [self._to_paper(i) for i in data.get("data", []) or []]

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
            params={"limit": limit, "fields": FIELDS},
            headers=self._headers(),
        )
        return [self._to_paper(e.get("citingPaper") or {}) for e in data.get("data", []) or []]
