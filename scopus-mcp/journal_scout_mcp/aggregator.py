import asyncio
from typing import Any, Dict, List, Optional

from .merge import merge_papers
from .models import Paper, ProviderError
from .providers.base import ProviderBase

UNPAYWALL_NAME = "unpaywall"


async def _gather(calls: Dict[str, Any]) -> tuple[List[Paper], Dict[str, str], Dict[str, int]]:
    names = list(calls.keys())
    results = await asyncio.gather(*calls.values(), return_exceptions=True)
    papers: List[Paper] = []
    errors: Dict[str, str] = {}
    counts: Dict[str, int] = {}
    for name, outcome in zip(names, results):
        if isinstance(outcome, Exception):
            message = getattr(outcome, "message", str(outcome))
            errors[name] = message
            continue
        counts[name] = len(outcome)
        papers.extend(outcome)
    return papers, errors, counts


def _select(providers: List[ProviderBase], sources: Optional[List[str]], need: str) -> List[ProviderBase]:
    selected = []
    for provider in providers:
        if sources is not None and provider.name not in sources:
            continue
        if need == "search" and not provider.supports_search:
            continue
        selected.append(provider)
    return selected


async def search_all(
    providers: List[ProviderBase],
    query: str,
    limit_per_source: int = 5,
    year_from: Optional[int] = None,
    year_to: Optional[int] = None,
    tech_only: bool = False,
    sources: Optional[List[str]] = None,
) -> Dict[str, Any]:
    active = _select(providers, sources, "search")
    calls = {
        p.name: p.search(query, limit_per_source, year_from, year_to, tech_only)
        for p in active
    }
    papers, errors, counts = await _gather(calls)
    merged = merge_papers(papers)
    return {
        "results": [p.to_dict() for p in merged],
        "errors": errors,
        "counts": counts,
    }


async def _enrich_with_unpaywall(providers: List[ProviderBase], paper: Paper) -> Paper:
    if not paper.doi:
        return paper
    for provider in providers:
        if provider.name != UNPAYWALL_NAME:
            continue
        try:
            oa = await provider.get(paper.doi)
        except ProviderError:
            return paper
        if oa:
            if oa.pdf_url:
                paper.pdf_url = paper.pdf_url or oa.pdf_url
            if oa.url:
                paper.url = paper.url or oa.url
            if oa.is_open_access is not None:
                paper.is_open_access = oa.is_open_access
            if provider.name not in paper.sources:
                paper.sources.append(provider.name)
        return paper
    return paper


async def get_paper(providers: List[ProviderBase], identifier: str) -> Dict[str, Any]:
    active = [p for p in providers if p.name != UNPAYWALL_NAME]
    calls = {p.name: p.get(identifier) for p in active}
    names = list(calls.keys())
    outcomes = await asyncio.gather(*calls.values(), return_exceptions=True)
    papers: List[Paper] = []
    errors: Dict[str, str] = {}
    for name, outcome in zip(names, outcomes):
        if isinstance(outcome, Exception):
            errors[name] = getattr(outcome, "message", str(outcome))
        elif outcome is not None:
            papers.append(outcome)
    merged = merge_papers(papers)
    if not merged:
        return {"paper": None, "errors": errors}
    paper = await _enrich_with_unpaywall(providers, merged[0])
    return {"paper": paper.to_dict(), "errors": errors}


async def get_citations(
    providers: List[ProviderBase],
    identifier: str,
    limit: int = 20,
) -> Dict[str, Any]:
    active = [p for p in providers if p.name in {"scopus", "openalex", "semanticscholar"}]
    calls = {p.name: p.citations(identifier, limit) for p in active}
    papers, errors, counts = await _gather(calls)
    merged = merge_papers(papers)
    return {
        "results": [p.to_dict() for p in merged],
        "errors": errors,
        "counts": counts,
    }
