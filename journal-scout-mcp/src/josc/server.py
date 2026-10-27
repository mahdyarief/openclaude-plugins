import asyncio
import json
from typing import Any, Dict, List, Optional

import mcp.types as types
from mcp.server import Server
from mcp.server.stdio import stdio_server

from . import aggregator, config, prompts
from .cache import build_cache
from .exporters import FORMATTERS, format_papers
from .http import Fetcher
from .models import ProviderError
from .identify import resolve_document
from .pdf_text import extract_pdf_text
from .providers import build_providers, search_provider_names
from .quota import quota_report
from .store import build_store, cached_call

UNIFIED_TOOLS = [
    "search_all",
    "search_author",
    "get_paper",
    "get_citations",
    "get_references",
    "get_related_works",
    "build_citation_network",
    "compute_metrics",
    "export_results",
    "identify_paper",
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
TOOL_NAMES = UNIFIED_TOOLS + PER_SOURCE_TOOLS + SCOPUS_DETAIL_TOOLS + SCIVAL_TOOLS

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

_SEARCH_ARGUMENTS = {
    "type": "object",
    "properties": {
        "query": {"type": "string", "description": "Search query."},
        "count": {"type": "integer", "description": "Max results.", "default": 5},
        **_SEARCH_FILTERS,
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
                },
                "required": [],
            },
        ),
        types.Tool(
            name="search_author",
            description="Find one author's papers across every author-search-capable source (Scopus/Crossref/OpenAlex/arXiv/Semantic Scholar), merged and deduped.",
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
            name="get_citations",
            description="Collect the cross-source citation graph (Scopus + OpenAlex + Semantic Scholar) for one paper. Pass sources to disambiguate a bare id that only one provider understands.",
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
            description="Collect the reference list of one paper from every source that exposes references (Scopus/OpenAlex/Semantic Scholar/Crossref), merged and deduped. Pass sources to disambiguate a bare id.",
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
    return tools


async def build_json(name: str, arguments: Dict[str, Any], providers, scopus_provider) -> Dict[str, Any]:
    if name == "search_all":
        return await aggregator.search_all(
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
    if name == "get_paper":
        return await aggregator.get_paper(
            providers, arguments["identifier"], sources=arguments.get("sources")
        )
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
    if name == "export_results":
        fmt = arguments["format"]
        return {
            "format": fmt,
            "content": format_papers(arguments["papers"], fmt),
        }
    if name in PER_SOURCE_TOOLS:
        source = name.removeprefix("search_")
        return await aggregator.search_all(
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
    raise ValueError(f"Unknown tool: {name}")


def start() -> None:
    async def run() -> None:
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
        server = Server("journal-scout-mcp")

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

        async with stdio_server() as (read_stream, write_stream):
            await server.run(read_stream, write_stream, server.create_initialization_options())
        await fetcher.close()
        if store is not None:
            await store.store.close()

    asyncio.run(run())


if __name__ == "__main__":
    start()
