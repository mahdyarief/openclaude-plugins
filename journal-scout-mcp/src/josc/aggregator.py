import asyncio
from typing import Any, Dict, List, Optional

from .graph import _node_id, build_network, compute_metrics as _compute_metrics
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


async def _fan_out(
    calls: Dict[str, Any],
    filter_report: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Run every provider call in parallel and merge the surviving records.

    Partial failures are reported per source instead of aborting the whole
    request, so one flaky source never hides the results the others returned.
    ``filter_report`` is only supplied by the search entry points, which keeps
    the relation lookups (citations/references) output unchanged.
    """
    papers, errors, counts = await _gather(calls)
    merged = merge_papers(papers)
    result = {
        "results": [p.to_dict() for p in merged],
        "errors": errors,
        "counts": counts,
    }
    if filter_report is not None:
        result["filters_applied"] = filter_report.get("applied", {})
        result["filters_ignored"] = filter_report.get("ignored", [])
    return result


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


def _supported_filters(provider: ProviderBase) -> frozenset:
    """Fields a provider advertises through ``supports_filters``."""
    return getattr(provider, "supports_filters", frozenset())


def _route_filters(
    active: List[ProviderBase],
    requested: Dict[str, Any],
    tech_only: bool = False,
):
    """Split requested field filters into per-provider kwargs and a report.

    Only providers that declare a field in ``supports_filters`` receive it, so
    a source never gets a keyword argument its ``search``/``search_author``
    does not understand. The report distinguishes filters that reached at
    least one provider from those no active provider could honour.
    """
    applied: Dict[str, List[str]] = {}
    ignored: List[str] = []
    for field, value in requested.items():
        if not value:
            continue
        supporting = [p for p in active if field in _supported_filters(p)]
        if not supporting:
            ignored.append(field)
        for provider in supporting:
            applied.setdefault(provider.name, []).append(field)
    # ``tech_only`` is boolean, so it is only reported when explicitly asked
    # for; otherwise every default response would list it as ignored.
    if tech_only:
        supporting = [p for p in active if getattr(p, "supports_tech_only", False)]
        if not supporting:
            ignored.append("tech_only")
        for provider in supporting:
            applied.setdefault(provider.name, []).append("tech_only")
    return applied, ignored


def _filter_kwargs(provider: ProviderBase, requested: Dict[str, Any]) -> Dict[str, Any]:
    supported = _supported_filters(provider)
    return {
        field: value
        for field, value in requested.items()
        if value and field in supported
    }


async def search_all(
    providers: List[ProviderBase],
    query: str,
    limit_per_source: int = 5,
    year_from: Optional[int] = None,
    year_to: Optional[int] = None,
    tech_only: bool = False,
    sources: Optional[List[str]] = None,
    offset: int = 0,
    author: Optional[str] = None,
    venue: Optional[str] = None,
) -> Dict[str, Any]:
    active = _select(providers, sources, "supports_search")
    requested = {"author": author, "venue": venue}
    applied, ignored = _route_filters(active, requested, tech_only=tech_only)
    calls = {
        p.name: p.search(
            query=query,
            limit=limit_per_source,
            year_from=year_from,
            year_to=year_to,
            tech_only=tech_only,
            offset=offset,
            **_filter_kwargs(p, requested),
        )
        for p in active
    }
    return await _fan_out(calls, {"applied": applied, "ignored": ignored})


async def search_author(
    providers: List[ProviderBase],
    author: str,
    limit_per_source: int = 5,
    year_from: Optional[int] = None,
    year_to: Optional[int] = None,
    sources: Optional[List[str]] = None,
    offset: int = 0,
    venue: Optional[str] = None,
) -> Dict[str, Any]:
    """Find one author's papers across every author-search-capable source."""
    active = _select(providers, sources, "supports_author_search")
    requested = {"venue": venue}
    applied, ignored = _route_filters(active, requested)
    calls = {
        p.name: p.search_author(
            author=author,
            limit=limit_per_source,
            year_from=year_from,
            year_to=year_to,
            offset=offset,
            **_filter_kwargs(p, requested),
        )
        for p in active
    }
    return await _fan_out(calls, {"applied": applied, "ignored": ignored})


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


async def get_references(
    providers: List[ProviderBase],
    identifier: str,
    limit: int = 20,
) -> Dict[str, Any]:
    """Collect the reference list of one paper from every capable source."""
    active = _select(providers, None, "supports_references")
    calls = {p.name: p.references(identifier, limit) for p in active}
    return await _fan_out(calls)


async def _fetch_papers(
    providers: List[ProviderBase],
    identifier: str,
    limit: int,
    capability: str,
    method: str,
) -> "tuple[List[Paper], Dict[str, str], Dict[str, int]]":
    """Fan out one relation (citations/references) and return merged records."""
    active = _select(providers, None, capability)
    calls = {p.name: getattr(p, method)(identifier, limit) for p in active}
    papers, errors, counts = await _gather(calls)
    return merge_papers(papers), errors, counts


def _relation_identifier(paper: Paper) -> Optional[str]:
    """Identifier usable for a follow-up relation lookup on ``paper``.

    DOI is the only id every provider understands, so it wins; provider ids
    are a fallback for records that lack one.
    """
    if paper.doi:
        return paper.doi
    for key in ("openalex", "scopus", "semanticscholar", "crossref"):
        value = paper.ids.get(key)
        if value:
            return value
    return None


async def build_citation_network(
    providers: List[ProviderBase],
    identifier: str,
    limit: int = 20,
    citing_limit: int = 10,
    max_nodes: int = 200,
    graph_format: str = "json",
) -> Dict[str, Any]:
    """Build a Connected-Papers-style network around one paper.

    Besides the seed's own references and citing papers, the reference lists
    of the top ``citing_limit`` citing papers are fetched so co-citation and
    bibliographic coupling edges can be derived.
    """
    resolved = await get_paper(providers, identifier)
    if not resolved.get("paper"):
        return {
            "error": "Seed paper could not be resolved by any source.",
            "errors": resolved.get("errors", {}),
        }
    seed = Paper(**resolved["paper"])

    references, ref_errors, ref_counts = await _fetch_papers(
        providers, identifier, limit, "supports_references", "references"
    )
    citations, cite_errors, cite_counts = await _fetch_papers(
        providers, identifier, limit, "supports_citations", "citations"
    )

    targets = []
    for citing in citations[:citing_limit]:
        related = _relation_identifier(citing)
        if related:
            targets.append((_node_id(citing), related))

    citing_references: Dict[str, List[Paper]] = {}
    if targets:
        outcomes = await asyncio.gather(
            *[
                _fetch_papers(providers, related, limit, "supports_references", "references")
                for _, related in targets
            ],
            return_exceptions=True,
        )
        for (citing_id, _), outcome in zip(targets, outcomes):
            if isinstance(outcome, Exception):
                continue
            citing_references[citing_id] = outcome[0]

    network = build_network(
        seed, references, citations, citing_references, max_nodes=max_nodes
    )
    network["seed_paper"] = seed.to_dict()
    network["errors"] = {**ref_errors, **cite_errors}
    network["counts"] = {
        "references": ref_counts,
        "citations": cite_counts,
        "citing_references": len(citing_references),
    }

    if graph_format == "graphml":
        from .graph import to_graphml

        return {
            "format": "graphml",
            "graphml": to_graphml(network),
            "stats": network["stats"],
            "errors": network["errors"],
        }
    return network


async def compute_metrics(
    providers: List[ProviderBase],
    author: Optional[str] = None,
    query: Optional[str] = None,
    limit_per_source: int = 50,
    year_from: Optional[int] = None,
    year_to: Optional[int] = None,
    sources: Optional[List[str]] = None,
    mode: str = "basic",
) -> Dict[str, Any]:
    """Compute Publish-or-Perish style metrics for an author or a query."""
    if author:
        result = await search_author(
            providers,
            author,
            limit_per_source=limit_per_source,
            year_from=year_from,
            year_to=year_to,
            sources=sources,
        )
    elif query:
        result = await search_all(
            providers,
            query,
            limit_per_source=limit_per_source,
            year_from=year_from,
            year_to=year_to,
            sources=sources,
        )
    else:
        raise ValueError("compute_metrics needs either 'author' or 'query'.")

    papers = [Paper(**item) for item in result["results"]]
    metrics = _compute_metrics(papers, mode=mode)
    metrics["errors"] = result["errors"]
    metrics["counts"] = result["counts"]
    return metrics
