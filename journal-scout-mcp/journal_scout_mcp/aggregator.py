import asyncio
from typing import Any, Optional

from .merge import merge_papers
from .models import Paper, ProviderError
from .providers.base import ProviderBase


async def _gather(
    calls: dict[str, Any],
) -> "tuple[list[Paper], dict[str, str], dict[str, int]]":
    names = list(calls.keys())
    results = await asyncio.gather(*calls.values(), return_exceptions=True)
    papers: List[Paper] = []
    errors: Dict[str, str] = {}
    counts: Dict[str, int] = {}
    for name, outcome in zip(names, results):
        if isinstance(outcome, Exception):
            errors[name] = getattr(outcome, "message", str(outcome))
            continue
        counts[name] = len(outcome)
        papers.extend(outcome)
    return papers, errors, counts


async def _fan_out(calls: Dict[str, Any]) -> Dict[str, Any]:
    """Run every provider call in parallel and merge the surviving records.

    Partial failures are reported per source instead of aborting the whole
    request, so one flaky source never hides the results the others returned.
    """
    papers, errors, counts = await _gather(calls)
    merged = merge_papers(papers)
    return {
        "results": [p.to_dict() for p in merged],
        "errors": errors,
        "counts": counts,
    }


def _select(providers: List[ProviderBase], sources: Optional[List[str]], capability: str) -> List[ProviderBase]:
    """Route a request to providers advertising ``capability``.

    ``capability`` is the name of a boolean flag on :class:`ProviderBase`
    (``supports_search`` / ``supports_author_search`` / ``supports_citations``).
    Reading the flag — never a hard-coded source name — is what lets a new
    provider plug in without touching the aggregator.
    """
    return [
        provider
        for provider in providers
        if (sources is None or provider.name in sources)
        and getattr(provider, capability, False)
    ]


async def search_all(
    providers: List[ProviderBase],
    query: str,
    limit_per_source: int = 5,
    year_from: Optional[int] = None,
    year_to: Optional[int] = None,
    tech_only: bool = False,
    sources: Optional[List[str]] = None,
    offset: int = 0,
) -> Dict[str, Any]:
    active = _select(providers, sources, "supports_search")
    calls = {
        p.name: p.search(
            query=query,
            limit=limit_per_source,
            year_from=year_from,
            year_to=year_to,
            tech_only=tech_only,
            offset=offset,
        )
        for p in active
    }
    return await _fan_out(calls)


async def search_author(
    providers: List[ProviderBase],
    author: str,
    limit_per_source: int = 5,
    year_from: Optional[int] = None,
    year_to: Optional[int] = None,
    sources: Optional[List[str]] = None,
    offset: int = 0,
) -> Dict[str, Any]:
    """Find one author's papers across every author-search-capable source."""
    active = _select(providers, sources, "supports_author_search")
    calls = {
        p.name: p.search_author(
            author=author,
            limit=limit_per_source,
            year_from=year_from,
            year_to=year_to,
            offset=offset,
        )
        for p in active
    }
    return await _fan_out(calls)


async def _enrich(providers: List[ProviderBase], paper: Paper) -> Paper:
    """Augment a resolved record using every registered enricher.

    Enrichers (``enricher is True``) never participate in a fan-out; they only
    add links/metadata to a record that some other source already resolved.
    Routing by the flag keeps this free of any hard-coded source name.
    """
    if not paper.doi:
        return paper
    for provider in providers:
        if not provider.enricher:
            continue
        try:
            extra = await provider.get(paper.doi)
        except ProviderError:
            continue
        if not extra:
            continue
        paper.pdf_url = paper.pdf_url or extra.pdf_url
        paper.url = paper.url or extra.url
        if extra.is_open_access is not None:
            paper.is_open_access = extra.is_open_access
        if provider.name not in paper.sources:
            paper.sources.append(provider.name)
    return paper


async def get_paper(providers: List[ProviderBase], identifier: str) -> Dict[str, Any]:
    active = [p for p in providers if not p.enricher]
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
    paper = await _enrich(providers, merged[0])
    return {"paper": paper.to_dict(), "errors": errors}


async def get_citations(
    providers: List[ProviderBase],
    identifier: str,
    limit: int = 20,
) -> Dict[str, Any]:
    active = _select(providers, None, "supports_citations")
    calls = {p.name: p.citations(identifier, limit) for p in active}
    return await _fan_out(calls)
