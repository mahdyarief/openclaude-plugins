import xml.etree.ElementTree as ET
from typing import List, Optional

from ..config import get_polite_email
from ..models import Paper
from ..utils import normalize_doi, parse_year
from .base import ProviderBase

ESEARCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
EFETCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
DEFAULT_TOOL = "journal-scout"


_PLACEHOLDER_TITLES = frozenset(
    {"[not available]", "not available", "n/a", "na", "none", "[no title]", "untitled"}
)


def _text(element) -> Optional[str]:
    if element is None:
        return None
    value = "".join(element.itertext()).strip()
    return value or None


def _usable_title(value: Optional[str]) -> Optional[str]:
    """Return ``value`` unless PubMed used it as an "[Not Available]" placeholder."""
    if not value:
        return None
    text = value.strip()
    if text.lower().rstrip(".").strip() in _PLACEHOLDER_TITLES:
        return None
    return text


class PubMedProvider(ProviderBase):
    name = "pubmed"
    supports_search = True
    supports_author_search = True
    supports_citations = False
    supports_references = False
    # ``author``/``venue`` have dedicated entry points here, so they are not
    # advertised as search filters (that would double up).
    supports_filters = frozenset({"affiliation", "issn", "orcid", "doi"})

    def _common_params(self) -> dict:
        params = {"tool": self.config.get("tool") or DEFAULT_TOOL}
        email = self.config.get("email") or get_polite_email()
        if email:
            params["email"] = email
        return params

    @staticmethod
    def _year_filter(year_from, year_to) -> str:
        if not year_from and not year_to:
            return ""
        lower = str(year_from) if year_from else "1800"
        upper = str(year_to) if year_to else "3000"
        return f'AND ("{lower}"[PDAT] : "{upper}"[PDAT])'

    @classmethod
    def _build_term(cls, term: str, year_from, year_to, affiliation=None, issn=None, orcid=None, doi=None) -> str:
        parts = [term]
        if affiliation:
            parts.append(f'"{affiliation}"[AD]')
        if issn:
            parts.append(f'"{issn}"[IS]')
        if orcid:
            parts.append(f'"{orcid}"[AID]')
        if doi:
            parts.append(f'"{doi}"[DOI]')
        year_filter = cls._year_filter(year_from, year_to)
        parts.append(year_filter)
        return " ".join(p for p in parts if p)

    async def _esearch_ids(self, term: str, limit: int, offset: int) -> List[str]:
        params = {
            "db": "pubmed",
            "term": term,
            "retmax": limit,
            "retstart": offset,
            "sort": "relevance",
            "retmode": "json",
        }
        params.update(self._common_params())
        data = await self._fetch_json(ESEARCH_URL, params=params)
        return ((data or {}).get("esearchresult") or {}).get("idlist") or []

    async def _efetch(self, ids: List[str]) -> List[Paper]:
        if not ids:
            return []
        params = {
            "db": "pubmed",
            "id": ",".join(str(i) for i in ids),
            "retmode": "xml",
        }
        params.update(self._common_params())
        xml_text = await self._fetch_text(EFETCH_URL, params=params)
        return self._parse_xml(xml_text)

    @staticmethod
    def _parse_article(article) -> Optional[Paper]:
        citation = article.find("MedlineCitation")
        if citation is None:
            return None
        pmid = _text(citation.find("PMID"))
        data = citation.find("Article")
        if data is None:
            return None

        # Records with no English title carry the placeholder "[Not Available]."
        # in ArticleTitle and the real title in VernacularTitle.
        title = _usable_title(_text(data.find("ArticleTitle")))
        if not title:
            title = _usable_title(_text(data.find("VernacularTitle"))) or ""

        abstract_parts = []
        for node in data.findall("Abstract/AbstractText"):
            value = _text(node)
            if value:
                abstract_parts.append(value)
        abstract = " ".join(abstract_parts) or None

        pub_date = data.find("Journal/JournalIssue/PubDate")
        year = None
        if pub_date is not None:
            year = parse_year(_text(pub_date.find("Year")))
            if year is None:
                year = parse_year(_text(pub_date.find("MedlineDate")))

        authors = []
        for author in data.findall("AuthorList/Author"):
            last = _text(author.find("LastName"))
            fore = _text(author.find("ForeName"))
            name = " ".join(x for x in [last, fore] if x)
            if name:
                authors.append(name)

        venue = _text(data.find("Journal/Title"))

        doi = None
        for elocation in data.findall("ELocationID"):
            if (elocation.get("EIdType") or "").lower() == "doi":
                doi = _text(elocation)
                break
        if not doi:
            for article_id in article.findall("PubmedData/ArticleIdList/ArticleId"):
                if (article_id.get("IdType") or "").lower() == "doi":
                    doi = _text(article_id)
                    break
        doi = normalize_doi(doi)

        ids = {"pubmed": pmid} if pmid else {}
        return Paper(
            doi=doi,
            title=title,
            abstract=abstract,
            year=year,
            authors=authors,
            venue=venue,
            url=f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else None,
            type="article",
            sources=["pubmed"],
            ids=ids,
        )

    @classmethod
    def _parse_xml(cls, xml_text: Optional[str]) -> List[Paper]:
        if not xml_text or not xml_text.strip():
            return []
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError:
            return []
        papers = []
        for article in root.findall(".//PubmedArticle"):
            paper = cls._parse_article(article)
            if paper is not None:
                papers.append(paper)
        return papers

    async def search(self, query: str, limit: int, year_from=None, year_to=None, tech_only=False, offset: int = 0, affiliation=None, issn=None, orcid=None, doi=None) -> List[Paper]:
        term = self._build_term(
            query, year_from, year_to,
            affiliation=affiliation, issn=issn, orcid=orcid, doi=doi,
        )
        ids = await self._esearch_ids(term, limit, offset)
        return await self._efetch(ids)

    async def search_author(self, author: str, limit: int, year_from=None, year_to=None, offset: int = 0, affiliation=None, issn=None, orcid=None, doi=None) -> List[Paper]:
        term = self._build_term(
            f'"{author}"[Author]', year_from, year_to,
            affiliation=affiliation, issn=issn, orcid=orcid, doi=doi,
        )
        ids = await self._esearch_ids(term, limit, offset)
        return await self._efetch(ids)

    async def get(self, identifier: str) -> Optional[Paper]:
        value = (identifier or "").strip()
        if not value:
            return None
        if value.isdigit():
            papers = await self._efetch([value])
            return papers[0] if papers else None
        doi = normalize_doi(value)
        if not doi:
            return None
        ids = await self._esearch_ids(f'"{doi}"[DOI]', 1, 0)
        papers = await self._efetch(ids)
        return papers[0] if papers else None
