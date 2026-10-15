import asyncio
import json
from typing import Any, Dict, List, Optional

import mcp.types as types
from mcp.server import Server
from mcp.server.stdio import stdio_server

from . import aggregator, config, prompts
from .cache import build_cache
from .http import Fetcher
from .models import ProviderError
from .providers import build_providers, search_provider_names

UNIFIED_TOOLS = ["search_all", "search_author", "get_paper", "get_citations"]
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
    "year_from": {"type": "integer", "description": "Earliest publication year."},
    "year_to": {"type": "integer", "description": "Latest publication year."},
    "tech_only": {"type": "boolean", "description": "Restrict to tech/computer-science.", "default": False},
    "offset": {"type": "integer", "description": "Number of results to skip (pagination).", "default": 0},
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

# Author search reuses the year/offset filters but has no ``tech_only``:
# restricting a person's output to computer science is not a meaningful filter.
_AUTHOR_FILTERS = {
    key: value for key, value in _SEARCH_FILTERS.items() if key != "tech_only"
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
                    **_SEARCH_FILTERS,
                },
                "required": ["query"],
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
            description="Resolve a DOI/arXiv/Scopus/OpenAlex id across sources, merge metadata, and attach open-access links.",
            inputSchema={
                "type": "object",
                "properties": {"identifier": {"type": "string"}},
                "required": ["identifier"],
            },
        ),
        types.Tool(
            name="get_citations",
            description="Collect the cross-source citation graph (Scopus + OpenAlex + Semantic Scholar) for one paper.",
            inputSchema={
                "type": "object",
                "properties": {
                    "identifier": {"type": "string"},
                    "limit": {"type": "integer", "default": 20},
                },
                "required": ["identifier"],
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
    tools.append(types.Tool(name="get_quota_status", description="Scopus API quota status.", inputSchema={"type": "object", "properties": {}}))
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
            arguments["query"],
            limit_per_source=arguments.get("limit_per_source", 5),
            year_from=arguments.get("year_from"),
            year_to=arguments.get("year_to"),
            tech_only=arguments.get("tech_only", False),
            sources=arguments.get("sources"),
            offset=arguments.get("offset", 0),
        )
    if name == "get_paper":
        return await aggregator.get_paper(providers, arguments["identifier"])
    if name == "search_author":
        return await aggregator.search_author(
            providers,
            arguments["author"],
            limit_per_source=arguments.get("limit_per_source", 5),
            year_from=arguments.get("year_from"),
            year_to=arguments.get("year_to"),
            sources=arguments.get("sources"),
            offset=arguments.get("offset", 0),
        )
    if name == "get_citations":
        return await aggregator.get_citations(
            providers, arguments["identifier"], limit=arguments.get("limit", 20)
        )
    if name in PER_SOURCE_TOOLS:
        source = name.removeprefix("search_")
        return await aggregator.search_all(
            providers,
            arguments["query"],
            limit_per_source=arguments.get("count", 5),
            year_from=arguments.get("year_from"),
            year_to=arguments.get("year_to"),
            tech_only=arguments.get("tech_only", False),
            sources=[source],
            offset=arguments.get("offset", 0),
        )
    if name == "get_abstract_details":
        paper = await scopus_provider.get(arguments["scopus_id"])
        # ``get`` returns a Paper, which is not JSON-serializable; the tool
        # contract is a plain dict, so convert it here.
        return {"paper": paper.to_dict() if paper else None}
    if name == "get_author_profile":
        return await scopus_provider.get_author(arguments["author_id"])
    if name == "get_quota_status":
        return await scopus_provider.get_quota_status()
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
        fetcher = Fetcher(cache=build_cache(config.get_cache_ttl()))
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
            try:
                payload = await build_json(tool_name, arguments or {}, providers, scopus_provider)
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

    asyncio.run(run())


if __name__ == "__main__":
    start()
