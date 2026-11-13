from typing import List, Optional

from ..config import get_consensus_key
from ..models import Paper
from ..utils import normalize_doi, parse_year
from .base import ProviderBase

CONSENSUS_URL = "https://api.consensus.app/v1/search"
# The API caps ``page_size``; paging past this is wasted requests.
MAX_PAGE_SIZE = 20


class ConsensusProvider(ProviderBase):
    """Consensus.app search, which returns evidence-grade paper records.

    Beyond bibliographic fields, Consensus annotates each result with a
    plain-language ``takeaway``, a ``study_type`` label, the number of
    underlying studies (for reviews/meta-analyses), and the journal's SJR
    quartile. Those annotations are what make Consensus worth merging in.
    """

    name = "consensus"
    supports_search = True
    supports_filters = frozenset({"year"})

    def _headers(self) -> dict:
        return {"x-api-key": get_consensus_key()}

    @staticmethod
    def _to_paper(item: dict) -> Paper:
        doi = normalize_doi(item.get("doi"))
        url = item.get("url")
        ids = {"consensus": doi or item.get("url") or ""}
        if not ids["consensus"]:
            ids = {}
        study_type = item.get("study_type")
        return Paper(
            doi=doi,
            title=(item.get("title") or "").strip(),
            abstract=item.get("abstract"),
            year=parse_year(item.get("publish_year")),
            authors=[a for a in item.get("authors") or [] if a],
            venue=item.get("journal_name"),
            citation_count=item.get("citation_count"),
            url=url,
            type=study_type,
            sources=["consensus"],
            ids=ids,
            institutions=[i for i in item.get("institutions") or [] if i],
            study_type=study_type,
            takeaway=item.get("takeaway"),
            study_count=item.get("study_count"),
            sjr_best_quartile=item.get("sjr_best_quartile"),
            is_preprint=item.get("is_preprint"),
        )

    async def search(
        self,
        query: str,
        limit: int,
        year_from: Optional[int] = None,
        year_to: Optional[int] = None,
        tech_only: bool = False,
        offset: int = 0,
        **_: object,
    ) -> List[Paper]:
        page_size = max(1, min(MAX_PAGE_SIZE, limit))
        params = {"query": query, "page_size": page_size}
        if year_from:
            params["year_min"] = year_from
        if year_to:
            params["year_max"] = year_to

        papers: List[Paper] = []
        page = 0
        while len(papers) < limit:
            params["page"] = page
            data = await self._fetch_json(
                CONSENSUS_URL, params=params, headers=self._headers(), provider=self.name
            )
            results = data.get("results") or []
            for item in results:
                paper = self._to_paper(item)
                if paper.title:
                    papers.append(paper)
            if data.get("is_end") or not results:
                break
            page += 1
        return papers[:limit]
