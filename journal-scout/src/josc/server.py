import asyncio
import hmac
import json
import os
from typing import Any, Dict, List, Optional

import mcp.types as types
from mcp.server import Server
from mcp.server.stdio import stdio_server

from . import aggregator, config, consensus_key, prompts
from .abstracts import enrich_abstracts, resolve_abstract
from .cache import build_cache
from .corpus import load_corpus
from .exporters import FORMATTERS, format_papers
from .fulltext import build_index, search_index
from .fulltext_fetch import fetch_fulltext
from .search_archive import SearchArchive
from .slr_tools import slr_call, slr_tool_defs
from .http import Fetcher
from .models import ProviderError
from .identify import resolve_document
from .pdf_text import extract_pdf_text
from .providers import build_providers, search_provider_names
from .quota import quota_report
from .store import build_store, cached_call
from .api.state import _store
from .watches import WatchStore, check_watch

UNIFIED_TOOLS = [
    "search_all",
    "search_author",
    "get_paper",
    "get_citations",
    "get_references",
    "get_related_works",
    "build_citation_network",
    "build_research_landscape",
    "compute_metrics",
    "export_results",
    "identify_paper",
    "check_watches",
    "search_corpus",
    "get_paper_abstract",
    "get_abstracts",
    "get_fulltext",
    "batch_lookup",
    "topic_classify",
]
PER_SOURCE_TOOLS = [f"search_{name}" for name in search_provider_names()]
SCOPUS_DETAIL_TOOLS = ["get_abstract_details", "get_author_profile", "get_quota_status"]
SCIVAL_TOOLS = [
    "scival_author_metrics",
    "scival_institution_metrics",
    "scival_author_lookup",
    "scival_institution_lookup",
    "scival_topic_metrics",
]
KEY_TOOLS = ["rotate_consensus_key"]
SLR_TOOL_NAMES = [t.name for t in slr_tool_defs()]
TOOL_NAMES = UNIFIED_TOOLS + PER_SOURCE_TOOLS + SCOPUS_DETAIL_TOOLS + SCIVAL_TOOLS + KEY_TOOLS + SLR_TOOL_NAMES

# MCP hosts reject a single tool result past their token cap (the transcript
# keeps ~100k chars before erroring). Search payloads embed full abstracts and
# topic hierarchies, so a 25-paper page can blow the cap on its own. We keep
# results under this character budget and shrink gracefully instead of failing.
MAX_TOOL_RESULT_CHARS = 80_000

# Dropped in this order when a payload is too large. Heavy, least-essential
# fields go first so titles/years/DOIs (what a landscape pass actually needs)
# survive as long as possible.
_SHRINK_FIELDS = (
    "topic_paths",
    "abstract",
    "keywords",
    "topics",
    "topic_ids",
    "institutions",
    "funders",
    "citations_by_year",
    "ids",
    "url",
    "pdf_url",
)

# Shared by the unified and per-source search tools so the two schemas can
# never drift apart.
_SEARCH_FILTERS = {
    "author": {"type": "string", "description": "Restrict to a specific author (sources that support it)."},
    "venue": {"type": "string", "description": "Restrict to a venue/journal (sources that support it)."},
    "year_from": {"type": "integer", "description": "Earliest publication year."},
    "year_to": {"type": "integer", "description": "Latest publication year."},
    "tech_only": {"type": "boolean", "description": "Restrict to tech/computer-science.", "default": False},
    "offset": {"type": "integer", "description": "Number of results to skip (pagination).", "default": 0},
    "affiliation": {"type": "string", "description": "Restrict to papers with this affiliation."},
    "issn": {"type": "string", "description": "Restrict to a journal by ISSN."},
    "orcid": {"type": "string", "description": "Restrict to papers by author ORCID."},
    "doi": {"type": "string", "description": "Restrict to a specific DOI."},
}

# Lets an agent request only the columns it needs, which is the cheapest way to
# stay under the MCP result budget (see MAX_TOOL_RESULT_CHARS).
_FIELDS_ARG = {
    "fields": {
        "type": "array",
        "items": {"type": "string"},
        "description": (
            "Return only these Paper keys (e.g. ['title','year','doi']). "
            "Omit to include everything; large fields like abstract/topic_paths "
            "are then dropped automatically if the payload nears the size cap."
        ),
    }
}

_SEARCH_ARGUMENTS = {
    "type": "object",
    "properties": {
        "query": {"type": "string", "description": "Search query."},
        "count": {"type": "integer", "description": "Max results.", "default": 5},
        **_SEARCH_FILTERS,
        **_FIELDS_ARG,
    },
    "required": ["query"],
}

# Author search reuses the year/offset/venue filters but has no ``tech_only``:
# restricting a person's output to computer science is not a meaningful filter.
# ``author`` is excluded because the tool takes it as its required argument.
# The four field filters are excluded because ``aggregator.search_author``
# only routes ``venue``; advertising them would promise what is not honoured.
_AUTHOR_FILTERS = {
    key: value
    for key, value in _SEARCH_FILTERS.items()
    if key not in ("tech_only", "author", "affiliation", "issn", "orcid", "doi")
}

_SCIVAL_METRIC_FILTERS = {
    "year_from": {"type": "integer"},
    "year_to": {"type": "integer"},
}


def _id_metric_schema(id_name: str) -> Dict[str, Any]:
    return {
        "type": "object",
        "properties": {id_name: {"type": "string"}, **_SCIVAL_METRIC_FILTERS},
        "required": [id_name],
    }


def _lookup_schema() -> Dict[str, Any]:
    return {
        "type": "object",
        "properties": {"query": {"type": "string"}, "count": {"type": "integer", "default": 10}},
        "required": ["query"],
    }


def _search_tool(name: str, description: str, schema: Dict[str, Any]) -> types.Tool:
    return types.Tool(name=name, description=description, inputSchema=schema)


# Lets an agent request only the columns it needs, which is the cheapest way to
# stay under the MCP result budget (see MAX_TOOL_RESULT_CHARS).
_FIELDS_ARG = {
    "fields": {
        "type": "array",
        "items": {"type": "string"},
        "description": (
            "Return only these Paper keys (e.g. ['title','year','doi']). "
            "Omit to include everything; large fields like abstract/topic_paths "
            "are then dropped automatically if the payload nears the size cap."
        ),
    }
}


def _finalize_payload(arguments: Dict[str, Any], payload: Dict[str, Any]) -> Dict[str, Any]:
    """Apply the ``fields`` filter and keep the payload under the size budget.

    Returns ``payload`` unchanged when both conditions already hold, so small
    responses are never rebuilt and callers can compare identity if needed.
    """
    results = payload.get("results")
    if not isinstance(results, list):
        return payload

    requested = arguments.get("fields")
    if requested:
        selected = [x for x in requested if isinstance(x, str)]
        payload = {
            **payload,
            "results": [
                {key: paper.get(key) for key in selected} for paper in results
            ],
        }
        return payload

    if len(json.dumps(payload, ensure_ascii=False)) <= MAX_TOOL_RESULT_CHARS:
        return payload

    return _trim_search_payload(payload, results)


def _trim_search_payload(payload: Dict[str, Any], results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Shrink ``payload`` under the budget without losing the result count.

    Strategy: drop heavy fields one at a time (cheapest first), then, if still
    too large, cut trailing results while preserving ``total_results`` so the
    agent knows what was omitted. Trimming results uses a measured per-item
    size rather than repeated serialisation to stay cheap on large pages.
    """
    working = [dict(paper) for paper in results]
    total = len(working)

    for field in _SHRINK_FIELDS:
        if len(json.dumps({**payload, "results": working}, ensure_ascii=False)) <= MAX_TOOL_RESULT_CHARS:
            break
        for paper in working:
            paper.pop(field, None)

    if len(json.dumps({**payload, "results": working}, ensure_ascii=False)) > MAX_TOOL_RESULT_CHARS:
        base = len(json.dumps({**payload, "results": []}, ensure_ascii=False))
        per_item = max(1, len(json.dumps(working, ensure_ascii=False)) // max(1, len(working)))
        keep = max(1, (MAX_TOOL_RESULT_CHARS - base) // per_item)
        working = working[:keep]

    return {
        **payload,
        "results": working,
        "total_results": total,
        "truncated": True,
        "truncation_note": (
            "Payload exceeded the MCP result size cap; heavy fields were dropped "
            "and/or trailing results omitted. Use the 'fields' argument to request "
            "fewer columns, or a smaller 'count'/'limit_per_source'."
        ),
    }


def _tool_list() -> List[types.Tool]:
    tools = [
        _search_tool(
            "search_all",
            "Search all journal sources in parallel and merge duplicate results by DOI/title.",
            {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "limit_per_source": {"type": "integer", "default": 5},
                    "sources": {"type": "array", "items": {"type": "string"}},
                    "sort": {"type": "string", "enum": ["relevance", "citations", "year", "title"], "description": "Sort the merged result set."},
                    "order": {"type": "string", "enum": ["asc", "desc"], "default": "desc"},
                    "topic": {
                        "type": "string",
                        "description": (
                            "Keep only results whose topics contain this text "
                            "(case-insensitive substring, applied after merge)."
                        ),
                    },
                    "conditions": {
                        "type": "array",
                        "description": (
                            "Field-scoped clauses, compiled per provider. "
                            "Use instead of, or alongside, 'query'. Fields the "
                            "provider cannot scope degrade to free text and are "
                            "reported in query_scoping."
                        ),
                        "items": {
                            "type": "object",
                            "properties": {
                                "field": {
                                    "type": "string",
                                    "enum": [
                                        "title",
                                        "abstract",
                                        "author",
                                        "venue",
                                        "all",
                                    ],
                                },
                                "value": {"type": "string"},
                                "operator": {
                                    "type": "string",
                                    "enum": ["AND", "OR", "NOT"],
                                    "default": "AND",
                                },
                            },
                            "required": ["field", "value"],
                        },
                    },
                    **_SEARCH_FILTERS,
                    **_FIELDS_ARG,
                },
                "required": [],
            },
        ),
        types.Tool(
            name="search_author",
            description="Find one author's papers across every author-search-capable source (Scopus/Crossref/OpenAlex/arXiv), merged and deduped.",
            inputSchema={
                "type": "object",
                "properties": {
                    "author": {"type": "string", "description": "Author name."},
                    "limit_per_source": {"type": "integer", "default": 5},
                    "sources": {"type": "array", "items": {"type": "string"}},
                    **_AUTHOR_FILTERS,
                },
                "required": ["author"],
            },
        ),
        types.Tool(
            name="get_paper",
            description="Resolve a DOI/arXiv/Scopus/OpenAlex id across sources, merge metadata, and attach open-access links. Pass sources to disambiguate a bare id that only one provider understands.",
            inputSchema={
                "type": "object",
                "properties": {
                    "identifier": {"type": "string"},
                    "sources": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["identifier"],
            },
        ),
        types.Tool(
            name="get_paper_abstract",
            description="Resolve the abstract of one paper from every source that can answer a DOI/title lookup. Returns status='not_found' with a null abstract when no source has one; nothing is guessed.",
            inputSchema={
                "type": "object",
                "properties": {
                    "doi": {"type": "string", "description": "DOI of the paper."},
                    "identifier": {"type": "string", "description": "Any other identifier (arXiv/Scopus/OpenAlex id or URL)."},
                    "title": {"type": "string", "description": "Title used for a title search when no identifier resolves."},
                    "sources": {"type": "array", "items": {"type": "string"}},
                    "timeout": {"type": "number", "default": 10.0},
                },
                "required": [],
            },
        ),
        types.Tool(
            name="get_abstracts",
            description="Fill missing abstracts for a list of paper dicts (e.g. search_all results). Keeps input order, never overwrites an existing abstract, and reports status per paper plus a summary.",
            inputSchema={
                "type": "object",
                "properties": {
                    "papers": {
                        "type": "array",
                        "description": "Paper dicts with doi/title/ids fields.",
                        "items": {"type": "object"},
                    },
                    "sources": {"type": "array", "items": {"type": "string"}},
                    "timeout": {"type": "number", "default": 10.0},
                },
                "required": ["papers"],
            },
        ),
        types.Tool(
            name="get_fulltext",
            description=(
                "Fetch the open-access full text of one paper: resolve the identifier "
                "across lookup sources, download the best OA PDF (Unpaywall link or "
                "arXiv PDF), and extract its text. Requires the optional 'pdf' extra "
                "(pypdf) on the server. Returns status='no_oa' for paywalled papers "
                "and status='error' with a message when extraction fails."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "identifier": {
                        "type": "string",
                        "description": "DOI, arXiv id, or other identifier the providers understand.",
                    },
                    "max_chars": {
                        "type": "integer",
                        "default": 20_000,
                        "description": "Cap the returned text length; longer text is truncated with truncated=true.",
                    },
                    "sources": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["identifier"],
            },
        ),
        types.Tool(
            name="batch_lookup",
            description=(
                "Resolve many identifiers (DOIs, arXiv ids, OpenAlex ids) in one call. "
                "OpenAlex and arXiv answer with a single batched request; other "
                "sources are queried per identifier. Results keep the request order, "
                "and identifiers that resolved nothing are listed in not_found."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "identifiers": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Identifiers to resolve; duplicates are ignored.",
                    },
                    "sources": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["identifiers"],
            },
        ),
        types.Tool(
            name="topic_classify",
            description=(
                "Classify free text (a title, abstract, or research question) into "
                "OpenAlex's scholarly taxonomy. Returns ranked candidates with a "
                "relevance score and a domain → field → subfield → topic path. Use "
                "level='subfield', 'field', or 'domain' for a coarser class."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "Title, abstract, or keywords to classify.",
                    },
                    "limit": {
                        "type": "integer",
                        "default": 5,
                        "description": "How many candidates to return, best first.",
                    },
                    "level": {
                        "type": "string",
                        "enum": ["topic", "subfield", "field", "domain"],
                        "default": "topic",
                        "description": "Taxonomy granularity to classify against.",
                    },
                },
                "required": ["text"],
            },
        ),
        types.Tool(
            name="get_citations",
            description="Collect the cross-source citation graph (Scopus + OpenAlex + OpenCitations) for one paper. Pass sources to disambiguate a bare id that only one provider understands.",
            inputSchema={
                "type": "object",
                "properties": {
                    "identifier": {"type": "string"},
                    "limit": {"type": "integer", "default": 20},
                    "sources": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["identifier"],
            },
        ),
        types.Tool(
            name="get_references",
            description="Collect the reference list of one paper from every source that exposes references (Scopus/OpenAlex/Crossref/OpenCitations), merged and deduped. Pass sources to disambiguate a bare id.",
            inputSchema={
                "type": "object",
                "properties": {
                    "identifier": {"type": "string"},
                    "limit": {"type": "integer", "default": 20},
                    "sources": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["identifier"],
            },
        ),
        types.Tool(
            name="get_related_works",
            description="List the works OpenAlex considers related to one paper (Publish or Perish 'Related Works'), merged and deduped. Pass sources to disambiguate a bare id.",
            inputSchema={
                "type": "object",
                "properties": {
                    "identifier": {"type": "string"},
                    "limit": {"type": "integer", "default": 20},
                    "sources": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["identifier"],
            },
        ),
        types.Tool(
            name="build_citation_network",
            description="Build a Connected-Papers-style network around one paper: direct citations, bibliographic coupling and co-citation edges. Use graph_format='graphml' to get a Gephi/VOSviewer file.",
            inputSchema={
                "type": "object",
                "properties": {
                    "identifier": {"type": "string"},
                    "limit": {"type": "integer", "default": 20, "description": "Max references and citations fetched per source."},
                    "citing_limit": {"type": "integer", "default": 10, "description": "How many citing papers get their own reference lists fetched for coupling/co-citation."},
                    "reference_limit": {"type": "integer", "default": 10, "description": "How many seed references get their own reference lists fetched for the second hop."},
                    "max_nodes": {"type": "integer", "default": 200},
                    "graph_format": {"type": "string", "enum": ["json", "graphml"], "default": "json"},
                },
                "required": ["identifier"],
            },
        ),
        types.Tool(
            name="build_research_landscape",
            description=(
                "Search a keyword and cluster the merged corpus into a research "
                "landscape: TF-IDF clustering, c-TF-IDF cluster labels, 2D "
                "coordinates and per-cluster topic/author/venue stats."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "n_clusters": {
                        "type": "integer",
                        "description": "Number of clusters; defaults to sqrt(paper count), capped at 8.",
                    },
                    "limit_per_source": {"type": "integer", "default": 50},
                    "sources": {"type": "array", "items": {"type": "string"}},
                    "year_from": {"type": "integer"},
                    "year_to": {"type": "integer"},
                    "tech_only": {"type": "boolean", "default": False},
                    "topic": {"type": "string"},
                },
                "required": ["query"],
            },
        ),
        types.Tool(
            name="compute_metrics",
            description="Publish-or-Perish style metrics (papers, total citations, h-index, i10, g-index, citation velocity) for an author name or a search query.",
            inputSchema={
                "type": "object",
                "properties": {
                    "author": {"type": "string", "description": "Author name; mutually exclusive with query."},
                    "query": {"type": "string", "description": "Topic query; mutually exclusive with author."},
                    "limit_per_source": {"type": "integer", "default": 50},
                    "sources": {"type": "array", "items": {"type": "string"}},
                    "year_from": {"type": "integer", "description": "Earliest publication year."},
                    "year_to": {"type": "integer", "description": "Latest publication year."},
                    "mode": {"type": "string", "enum": ["basic", "extended"], "default": "basic", "description": "basic returns the classic indicators; extended adds hc/hI/hI_norm/AWCR/AW-index/AWCRpA/hm."},
                },
            },
        ),
        types.Tool(
            name="export_results",
            description="Export a list of paper dicts to a bibliography format (BibTeX, RIS, CSV, EndNote, WoS, citation styles, JSON).",
            inputSchema={
                "type": "object",
                "properties": {
                    "papers": {
                        "type": "array",
                        "items": {"type": "object"},
                        "description": "Paper dicts (the shape search_all/get_paper return).",
                    },
                    "format": {
                        "type": "string",
                        "enum": sorted(FORMATTERS),
                        "description": "Export format.",
                    },
                },
                "required": ["papers", "format"],
            },
        ),
        _search_tool(
            "identify_paper",
            "Identify a paper from a local PDF by resolving its DOI or title.",
            {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Absolute path to a PDF file on this machine.",
                    },
                },
                "required": ["path"],
            },
        ),
        _search_tool(
            "check_watches",
            "Run every saved-search watch and return papers not reported before.",
            {"type": "object", "properties": {}},
        ),
        _search_tool(
            "search_corpus",
            "Search the locally archived search results by title, abstract, venue, author or keyword.",
            {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Whitespace-separated terms; every term must match.",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "How many recent archived searches to include.",
                        "default": 20,
                    },
                },
                "required": ["query"],
            },
        ),
    ]
    for name in PER_SOURCE_TOOLS:
        tools.append(
            _search_tool(
                name,
                f"Search {name.removeprefix('search_')} only.",
                _SEARCH_ARGUMENTS,
            )
        )
    tools.append(types.Tool(name="get_abstract_details", description="Scopus abstract details for a Scopus id.", inputSchema={"type": "object", "properties": {"scopus_id": {"type": "string"}}, "required": ["scopus_id"]}))
    tools.append(types.Tool(name="get_author_profile", description="Scopus author profile.", inputSchema={"type": "object", "properties": {"author_id": {"type": "string"}}, "required": ["author_id"]}))
    tools.append(types.Tool(name="get_quota_status", description="Documented rate limits and quota status for every configured source; includes live Scopus headers when available.", inputSchema={"type": "object", "properties": {}}))
    tools.append(types.Tool(name="scival_author_metrics", description="SciVal author metrics.", inputSchema=_id_metric_schema("author_id")))
    tools.append(types.Tool(name="scival_institution_metrics", description="SciVal institution metrics.", inputSchema=_id_metric_schema("institution_id")))
    tools.append(types.Tool(name="scival_author_lookup", description="SciVal author lookup by name.", inputSchema=_lookup_schema()))
    tools.append(types.Tool(name="scival_institution_lookup", description="SciVal institution lookup by name.", inputSchema=_lookup_schema()))
    tools.append(types.Tool(name="scival_topic_metrics", description="SciVal topic metrics.", inputSchema=_id_metric_schema("topic_id")))
    tools.append(
        types.Tool(
            name="rotate_consensus_key",
            description=(
                "Verify a new Consensus API key against the live API and, only "
                "if accepted, persist it to config.json (consensus_api_key). "
                "The old key survives a failed rotation."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "api_key": {
                        "type": "string",
                        "description": "The new Consensus API key to verify and store.",
                    },
                },
                "required": ["api_key"],
            },
        )
    )
    tools.extend(slr_tool_defs())
    return tools


def _watch_store() -> WatchStore:
    store = _store()
    if store is None:
        raise RuntimeError("Persistent watch store is not configured.")
    return WatchStore(store)


async def build_json(name: str, arguments: Dict[str, Any], providers, scopus_provider) -> Dict[str, Any]:
    if name == "check_watches":
        store = _watch_store()

        async def runner(watch):
            result = await aggregator.search_all(
                providers,
                query=watch["query"],
                sources=watch.get("sources"),
            )
            return result["results"]

        reports = []
        for watch in await store.list():
            result = await check_watch(watch, runner, store)
            reports.append(
                {
                    "id": watch["id"],
                    "checked": result["checked"],
                    "new": result["new"],
                }
            )
        return {"watches": reports}
    if name == "search_all":
        result = await aggregator.search_all(
            providers,
            arguments.get("query") or "",
            limit_per_source=arguments.get("limit_per_source", 5),
            year_from=arguments.get("year_from"),
            year_to=arguments.get("year_to"),
            tech_only=arguments.get("tech_only", False),
            sources=arguments.get("sources"),
            offset=arguments.get("offset", 0),
            author=arguments.get("author"),
            venue=arguments.get("venue"),
            affiliation=arguments.get("affiliation"),
            issn=arguments.get("issn"),
            orcid=arguments.get("orcid"),
            doi=arguments.get("doi"),
            sort=arguments.get("sort"),
            order=arguments.get("order", "desc"),
            topic=arguments.get("topic"),
            conditions=arguments.get("conditions"),
        )
        return _finalize_payload(arguments, result)
    if name == "get_paper":
        return await aggregator.get_paper(
            providers, arguments["identifier"], sources=arguments.get("sources")
        )
    if name == "get_paper_abstract":
        requested = arguments.get("sources")
        selected = [p for p in providers if not requested or p.name in requested]
        return await resolve_abstract(
            selected,
            doi=arguments.get("doi"),
            title=arguments.get("title"),
            paper={"identifier": arguments.get("identifier")},
            timeout=arguments.get("timeout", 10.0),
        )
    if name == "get_abstracts":
        requested = arguments.get("sources")
        selected = [p for p in providers if not requested or p.name in requested]
        return await enrich_abstracts(
            selected,
            arguments["papers"],
            timeout=arguments.get("timeout", 10.0),
        )
    if name == "get_fulltext":
        requested = arguments.get("sources")
        selected = [p for p in providers if not requested or p.name in requested]
        # Clamp to the tool-result budget: a bigger cap would be truncated by
        # the transport anyway, so the server keeps responses deliverable.
        max_chars = min(arguments.get("max_chars", 20_000), MAX_TOOL_RESULT_CHARS)
        return await fetch_fulltext(selected, arguments["identifier"], max_chars=max_chars)
    if name == "batch_lookup":
        return await aggregator.batch_lookup(
            providers,
            arguments["identifiers"],
            sources=arguments.get("sources"),
        )
    if name == "topic_classify":
        level = arguments.get("level", "topic")
        limit = arguments.get("limit", 5)
        classifier = next(
            (
                provider
                for provider in providers
                if callable(getattr(provider, "classify_topics", None))
            ),
            None,
        )
        if classifier is None:
            return {
                "status": "error",
                "error": "openalex provider is not configured; topic classification needs it.",
                "candidates": [],
                "level": level,
                "count": 0,
            }
        candidates = await classifier.classify_topics(
            arguments["text"], limit=limit, level=level
        )
        return {
            "status": "ok",
            "level": level,
            "count": len(candidates),
            "candidates": candidates,
        }
    if name == "search_author":
        return await aggregator.search_author(
            providers,
            arguments["author"],
            limit_per_source=arguments.get("limit_per_source", 5),
            year_from=arguments.get("year_from"),
            year_to=arguments.get("year_to"),
            sources=arguments.get("sources"),
            offset=arguments.get("offset", 0),
            venue=arguments.get("venue"),
        )
    if name == "get_citations":
        return await aggregator.get_citations(
            providers,
            arguments["identifier"],
            limit=arguments.get("limit", 20),
            sources=arguments.get("sources"),
        )
    if name == "get_references":
        return await aggregator.get_references(
            providers,
            arguments["identifier"],
            limit=arguments.get("limit", 20),
            sources=arguments.get("sources"),
        )
    if name == "get_related_works":
        return await aggregator.get_related(
            providers,
            arguments["identifier"],
            limit=arguments.get("limit", 20),
            sources=arguments.get("sources"),
        )
    if name == "build_citation_network":
        return await aggregator.build_citation_network(
            providers,
            arguments["identifier"],
            limit=arguments.get("limit", 20),
            citing_limit=arguments.get("citing_limit", 10),
            max_nodes=arguments.get("max_nodes", 200),
            graph_format=arguments.get("graph_format", "json"),
            reference_limit=arguments.get("reference_limit", 10),
        )
    if name == "build_research_landscape":
        return await aggregator.build_landscape(
            arguments["query"],
            providers=providers,
            n_clusters=arguments.get("n_clusters"),
            limit_per_source=arguments.get("limit_per_source", 50),
            year_from=arguments.get("year_from"),
            year_to=arguments.get("year_to"),
            sources=arguments.get("sources"),
            tech_only=arguments.get("tech_only", False),
            topic=arguments.get("topic"),
        )
    if name == "compute_metrics":
        return await aggregator.compute_metrics(
            providers,
            author=arguments.get("author"),
            query=arguments.get("query"),
            limit_per_source=arguments.get("limit_per_source", 50),
            year_from=arguments.get("year_from"),
            year_to=arguments.get("year_to"),
            sources=arguments.get("sources"),
            mode=arguments.get("mode", "basic"),
        )
    if name == "identify_paper":
        text = extract_pdf_text(arguments["path"])
        return await resolve_document(text, providers)
    if name == "search_corpus":
        store = _store()
        if store is None:
            raise RuntimeError("Persistent archive store is not configured.")
        archive = SearchArchive(store)
        papers = await load_corpus(archive, limit=int(arguments.get("limit") or 20))
        index = build_index(papers)
        hits = search_index(index, papers, arguments["query"])
        return {
            "query": arguments["query"],
            "corpus_size": len(papers),
            "results": hits,
        }
    if name == "export_results":
        fmt = arguments["format"]
        return {
            "format": fmt,
            "content": format_papers(arguments["papers"], fmt),
        }
    if name in PER_SOURCE_TOOLS:
        source = name.removeprefix("search_")
        result = await aggregator.search_all(
            providers,
            arguments.get("query") or "",
            limit_per_source=arguments.get("count", 5),
            year_from=arguments.get("year_from"),
            year_to=arguments.get("year_to"),
            tech_only=arguments.get("tech_only", False),
            sources=[source],
            offset=arguments.get("offset", 0),
            author=arguments.get("author"),
            venue=arguments.get("venue"),
            affiliation=arguments.get("affiliation"),
            issn=arguments.get("issn"),
            orcid=arguments.get("orcid"),
            doi=arguments.get("doi"),
            conditions=arguments.get("conditions"),
        )
        return _finalize_payload(arguments, result)
    if name == "get_abstract_details":
        paper = await scopus_provider.get(arguments["scopus_id"])
        # ``get`` returns a Paper, which is not JSON-serializable; the tool
        # contract is a plain dict, so convert it here.
        return {"paper": paper.to_dict() if paper else None}
    if name == "get_author_profile":
        return await scopus_provider.get_author(arguments["author_id"])
    if name == "get_quota_status":
        report = quota_report(providers)
        try:
            report["scopus_detail"] = await scopus_provider.get_quota_status()
        except Exception:  # noqa: BLE001 - the static report is still useful
            report["scopus_detail"] = None
        return report
    if name == "scival_author_metrics":
        return await scopus_provider.scival_author_metrics(
            arguments["author_id"], arguments.get("year_from"), arguments.get("year_to")
        )
    if name == "scival_institution_metrics":
        return await scopus_provider.scival_institution_metrics(
            arguments["institution_id"], arguments.get("year_from"), arguments.get("year_to")
        )
    if name == "scival_author_lookup":
        return await scopus_provider.scival_author_lookup(
            arguments["query"], arguments.get("count", 10)
        )
    if name == "scival_institution_lookup":
        return await scopus_provider.scival_institution_lookup(
            arguments["query"], arguments.get("count", 10)
        )
    if name == "scival_topic_metrics":
        return await scopus_provider.scival_topic_metrics(
            arguments["topic_id"], arguments.get("year_from"), arguments.get("year_to")
        )
    if name == "rotate_consensus_key":
        return await consensus_key.rotate_consensus_key(arguments["api_key"])
    if name in SLR_TOOL_NAMES:
        return await slr_call(name, arguments)
    raise ValueError(f"Unknown tool: {name}")


async def _build_server():
    """Build the MCP server plus its lifecycle-owned resources.

    Setup (dedup store, HTTP fetcher, provider registry) happens once per
    process. Every MCP session shares these, which is safe because providers
    are stateless and the store is async-safe.
    """
    ttl = config.get_cache_ttl()
    store = build_store(ttl)
    if store is not None:
        try:
            await store.setup()
            await store.purge_expired()
        except Exception:
            await store.store.close()
            store = None
    fetcher = Fetcher(cache=build_cache(ttl))
    try:
        api_key = config.get_api_key()
    except ValueError:
        api_key = None
    providers = build_providers(fetcher, {"api_key": api_key})
    scopus_provider = next(p for p in providers if p.name == "scopus")
    server = Server("journal-scout")

    @server.list_tools()
    async def _list_tools() -> List[types.Tool]:
        return _tool_list()

    @server.call_tool()
    async def _call_tool(tool_name: str, arguments: Dict[str, Any]) -> List[types.TextContent]:
        args = arguments or {}
        key = (tool_name, json.dumps(args, sort_keys=True, default=str))
        try:
            payload = await cached_call(
                store,
                key,
                lambda: build_json(tool_name, args, providers, scopus_provider),
            )
        except ProviderError as e:
            payload = {"error": e.message, "provider": e.provider}
        except Exception as e:  # noqa: BLE001 - surface a readable message to the agent
            payload = {"error": str(e)}
        return [types.TextContent(type="text", text=json.dumps(payload, ensure_ascii=False, indent=2))]

    @server.list_prompts()
    async def _list_prompts() -> List[types.Prompt]:
        return prompts.list_prompts()

    @server.get_prompt()
    async def _get_prompt(name: str, arguments: Optional[Dict[str, Any]]) -> types.GetPromptResult:
        return prompts.render_prompt(name, arguments)

    return server, fetcher, store


async def _run_stdio() -> None:
    server, fetcher, store = await _build_server()
    try:
        async with stdio_server() as (read_stream, write_stream):
            await server.run(read_stream, write_stream, server.create_initialization_options())
    finally:
        await fetcher.close()
        if store is not None:
            await store.store.close()


async def _run_http(host: str, port: int, token: Optional[str]) -> None:
    from contextlib import AsyncExitStack

    from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
    import uvicorn

    from .api import app as web_app

    server, fetcher, store = await _build_server()
    manager = StreamableHTTPSessionManager(app=server, stateless=True)
    web_lifespan = web_app.router.lifespan_context

    async def _send_json(send, status: int, payload: bytes) -> None:
        await send(
            {
                "type": "http.response.start",
                "status": status,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(payload)).encode()),
                ],
            }
        )
        await send({"type": "http.response.body", "body": payload})

    async def app(scope, receive, send) -> None:
        if scope["type"] == "lifespan":
            stack = AsyncExitStack()
            async with stack:
                while True:
                    message = await receive()
                    if message["type"] == "lifespan.startup":
                        try:
                            await stack.enter_async_context(manager.run())
                            await stack.enter_async_context(web_lifespan(web_app))
                            await send({"type": "lifespan.startup.complete"})
                        except Exception as exc:  # noqa: BLE001
                            await send({"type": "lifespan.startup.failed", "message": str(exc)})
                            return
                    elif message["type"] == "lifespan.shutdown":
                        await send({"type": "lifespan.shutdown.complete"})
                        return
        if scope["type"] != "http":
            return
        path = scope.get("path", "")
        if path == "/healthz":
            await _send_json(send, 200, b'{"status":"ok","server":"journal-scout"}')
            return
        if path in ("/mcp", "/mcp/"):
            if token:
                headers = dict(scope.get("headers") or [])
                supplied = headers.get(b"authorization", b"")
                if not hmac.compare_digest(supplied, f"Bearer {token}".encode()):
                    await _send_json(send, 401, b'{"error":"unauthorized"}')
                    return
            await manager.handle_request(scope, receive, send)
            return
        await web_app(scope, receive, send)

    config_obj = uvicorn.Config(app, host=host, port=port, log_level="info")
    try:
        await uvicorn.Server(config_obj).serve()
    finally:
        await fetcher.close()
        if store is not None:
            await store.store.close()


def start() -> None:
    transport = (os.getenv("JOSC_TRANSPORT") or "stdio").strip().lower()
    if transport in ("http", "streamable-http", "remote"):
        host = os.getenv("JOSC_HOST", "0.0.0.0")
        port = int(os.getenv("JOSC_PORT", "8080"))
        token = (os.getenv("JOSC_MCP_TOKEN") or "").strip() or None
        asyncio.run(_run_http(host, port, token))
        return
    asyncio.run(_run_stdio())


if __name__ == "__main__":
    start()
