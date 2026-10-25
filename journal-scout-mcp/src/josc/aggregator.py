import asyncio
import re
from typing import Any, Dict, List, Optional

from .graph import _node_id, build_network, compute_metrics as _compute_metrics
from .merge import merge_papers
from .models import Paper, ProviderError
from .providers.base import ProviderBase
from .query import operator_report, translate_query


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
        and (sources is not None or not getattr(provider, "opt_out", False))
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


_SORT_FIELDS = {"citations": "citation_count", "year": "year", "title": "title"}

# Boolean tokens carry no topical meaning, so they must not earn relevance.
_OPERATOR_TOKENS = {"and", "or", "not"}


def _query_tokens(query: str) -> List[str]:
    return [
        token
        for token in re.findall(r"[a-z0-9]+", (query or "").lower())
        if token not in _OPERATOR_TOKENS
    ]


def _relevance_score(item: Dict[str, Any], tokens: List[str]) -> int:
    """Title matches outweigh abstract matches; each token counts once."""
    title = (item.get("title") or "").lower()
    abstract = (item.get("abstract") or "").lower()
    score = 0
    for token in tokens:
        if token in title:
            score += 3
        elif token in abstract:
            score += 1
    return score


def _filter_by_topic(
    results: List[Dict[str, Any]], topic: Optional[str]
) -> List[Dict[str, Any]]:
    """Keep records whose ``topics`` contain ``topic`` as a case-insensitive substring.

    Topic vocabularies are provider-specific (OpenAlex concepts, Crossref
    subjects, PubMed MeSH), so there is no shared query parameter to push
    down. Filtering the merged set keeps it a single pass with no extra
    network requests.
    """
    needle = (topic or "").strip().lower()
    if not needle:
        return results
    return [
        item
        for item in results
        if any(needle in (value or "").lower() for value in item.get("topics") or [])
    ]


def _sort_results(
    results: List[Dict[str, Any]],
    sort: Optional[str],
    order: str,
    query: str = "",
) -> None:
    """Sort paper dicts in place; records missing the key always come last."""
    if sort == "relevance":
        tokens = _query_tokens(query)
        if not tokens:
            return
        results.sort(
            key=lambda item: _relevance_score(item, tokens),
            reverse=order != "asc",
        )
        return
    field = _SORT_FIELDS.get(sort or "")
    if not field:
        return
    present = [item for item in results if item.get(field) is not None]
    missing = [item for item in results if item.get(field) is None]
    present.sort(key=lambda item: item[field], reverse=order != "asc")
    results[:] = present + missing


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
    affiliation: Optional[str] = None,
    issn: Optional[str] = None,
    orcid: Optional[str] = None,
    doi: Optional[str] = None,
    sort: Optional[str] = None,
    order: str = "desc",
    topic: Optional[str] = None,
) -> Dict[str, Any]:
    active = _select(providers, sources, "supports_search")
    translated = {p.name: translate_query(query, p.name) for p in active}
    requested = {"author": author, "venue": venue, "affiliation": affiliation,
                 "issn": issn, "orcid": orcid, "doi": doi}
    applied, ignored = _route_filters(active, requested, tech_only=tech_only)
    calls = {
        p.name: p.search(
            query=translated[p.name],
            limit=limit_per_source,
            year_from=year_from,
            year_to=year_to,
            tech_only=tech_only,
            offset=offset,
            **_filter_kwargs(p, requested),
        )
        for p in active
    }
    result = await _fan_out(calls, {"applied": applied, "ignored": ignored})
    result["results"] = _filter_by_topic(result["results"], topic)
    _sort_results(result["results"], sort, order, query)
    report = operator_report([p.name for p in active], query)
    result["query_warnings"] = report["warnings"]
    result["query_translated"] = translated
    return result


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


async def get_paper(
    providers: List[ProviderBase],
    identifier: str,
    sources: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Resolve one identifier across providers.

    ``sources`` narrows the lookup when the identifier is only meaningful to
    one provider. A bare numeric id is ambiguous — Semantic Scholar reads any
    digits as a ``CorpusId``, PubMed as a PMID, Scopus as a Scopus id — so a
    caller holding a Garuda document id must say so instead of letting every
    other source guess.
    """
    active = [
        p
        for p in providers
        if not p.enricher and (sources is None or p.name in sources)
    ]
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
    sources: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Collect citing papers for one identifier.

    ``sources`` mirrors :func:`get_paper`: a bare numeric id only means
    something to the provider that issued it, so callers holding a Garuda or
    PubMed id must scope the lookup instead of letting every provider guess.
    """
    active = _select(providers, sources, "supports_citations")
    calls = {p.name: p.citations(identifier, limit) for p in active}
    return await _fan_out(calls)


async def get_references(
    providers: List[ProviderBase],
    identifier: str,
    limit: int = 20,
    sources: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Collect the reference list of one paper from every capable source."""
    active = _select(providers, sources, "supports_references")
    calls = {p.name: p.references(identifier, limit) for p in active}
    return await _fan_out(calls)


async def get_related(
    providers: List[ProviderBase],
    identifier: str,
    limit: int = 20,
    sources: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Collect the related-works list of one paper from every capable source."""
    active = _select(providers, sources, "supports_related")
    calls = {p.name: p.related(identifier, limit) for p in active}
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
    reference_limit: int = 10,
) -> Dict[str, Any]:
    """Build a Connected-Papers-style network around one paper.

    Besides the seed's own references and citing papers, the reference lists
    of the top ``citing_limit`` citing papers are fetched so co-citation and
    bibliographic coupling edges can be derived. The references of the seed's
    own references are fetched too (up to ``reference_limit``), which is what
    produces citation paths that do not pass through the seed.
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

    # Second hop: expand the seed's own references so citation paths can form
    # between non-seed nodes instead of every edge pointing back at the seed.
    ref_targets = []
    for ref in references[:reference_limit]:
        related = _relation_identifier(ref)
        if related:
            ref_targets.append((_node_id(ref), related))

    reference_references: Dict[str, List[Paper]] = {}
    if ref_targets:
        outcomes = await asyncio.gather(
            *[
                _fetch_papers(providers, related, limit, "supports_references", "references")
                for _, related in ref_targets
            ],
            return_exceptions=True,
        )
        for (ref_id, _), outcome in zip(ref_targets, outcomes):
            if isinstance(outcome, Exception):
                continue
            reference_references[ref_id] = outcome[0]

    network = build_network(
        seed,
        references,
        citations,
        citing_references,
        max_nodes=max_nodes,
        reference_references=reference_references,
    )
    network["seed_paper"] = seed.to_dict()
    network["errors"] = {**ref_errors, **cite_errors}
    network["counts"] = {
        "references": ref_counts,
        "citations": cite_counts,
        "citing_references": len(citing_references),
        "reference_references": len(reference_references),
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
