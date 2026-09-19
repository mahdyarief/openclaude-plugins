import asyncio
import json
from typing import Any, Dict, List, Optional

import mcp.types as types
from mcp.server import Server
from mcp.server.stdio import stdio_server

from . import aggregator, config
from .http import Fetcher
from .models import ProviderError
from .providers import build_providers

UNIFIED_TOOLS = ["search_all", "get_paper", "get_citations"]
PER_SOURCE_TOOLS = [
    "search_scopus",
    "search_arxiv",
    "search_openalex",
    "search_semanticscholar",
    "search_crossref",
    "search_dblp",
]
SCOPUS_DETAIL_TOOLS = ["get_abstract_details", "get_author_profile", "get_quota_status"]
SCIVAL_TOOLS = [
    "scival_author_metrics",
    "scival_institution_metrics",
    "scival_author_lookup",
    "scival_institution_lookup",
    "scival_topic_metrics",
]
TOOL_NAMES = UNIFIED_TOOLS + PER_SOURCE_TOOLS + SCOPUS_DETAIL_TOOLS + SCIVAL_TOOLS

_SEARCH_ARGUMENTS = {
    "type": "object",
    "properties": {
        "query": {"type": "string", "description": "Search query."},
        "count": {"type": "integer", "description": "Max results.", "default": 5},
        "year_from": {"type": "integer", "description": "Earliest publication year."},
        "year_to": {"type": "integer", "description": "Latest publication year."},
        "tech_only": {"type": "boolean", "description": "Restrict to tech/computer-science.", "default": False},
    },
    "required": ["query"],
}


def _tool_list() -> List[types.Tool]:
    tools = [
        types.Tool(
            name="search_all",
            description="Search all journal sources in parallel and merge duplicate results by DOI/title.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "limit_per_source": {"type": "integer", "default": 5},
                    "year_from": {"type": "integer"},
                    "year_to": {"type": "integer"},
                    "tech_only": {"type": "boolean", "default": False},
                    "sources": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["query"],
            },
        ),
        types.Tool(
            name="get_paper",
            description="Resolve a DOI/arXiv/Scopus/OpenAlex id or title across sources, merge metadata, and attach open-access links.",
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
        tools.append(types.Tool(name=name, description=f"Search {name.removeprefix('search_')} only.", inputSchema=_SEARCH_ARGUMENTS))
    tools.append(types.Tool(name="get_abstract_details", description="Scopus abstract details for a Scopus id.", inputSchema={"type": "object", "properties": {"scopus_id": {"type": "string"}}, "required": ["scopus_id"]}))
    tools.append(types.Tool(name="get_author_profile", description="Scopus author profile.", inputSchema={"type": "object", "properties": {"author_id": {"type": "string"}}, "required": ["author_id"]}))
    tools.append(types.Tool(name="get_quota_status", description="Scopus API quota status.", inputSchema={"type": "object", "properties": {}}))
    tools.append(types.Tool(name="scival_author_metrics", description="SciVal author metrics.", inputSchema={"type": "object", "properties": {"author_id": {"type": "string"}, "year_from": {"type": "integer"}, "year_to": {"type": "integer"}}, "required": ["author_id"]}))
    tools.append(types.Tool(name="scival_institution_metrics", description="SciVal institution metrics.", inputSchema={"type": "object", "properties": {"institution_id": {"type": "string"}, "year_from": {"type": "integer"}, "year_to": {"type": "integer"}}, "required": ["institution_id"]}))
    tools.append(types.Tool(name="scival_author_lookup", description="SciVal author lookup by name.", inputSchema={"type": "object", "properties": {"query": {"type": "string"}, "count": {"type": "integer", "default": 10}}, "required": ["query"]}))
    tools.append(types.Tool(name="scival_institution_lookup", description="SciVal institution lookup by name.", inputSchema={"type": "object", "properties": {"query": {"type": "string"}, "count": {"type": "integer", "default": 10}}, "required": ["query"]}))
    tools.append(types.Tool(name="scival_topic_metrics", description="SciVal topic metrics.", inputSchema={"type": "object", "properties": {"topic_id": {"type": "string"}, "year_from": {"type": "integer"}, "year_to": {"type": "integer"}}, "required": ["topic_id"]}))
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
        )
    if name == "get_paper":
        return await aggregator.get_paper(providers, arguments["identifier"])
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
        )
    if name == "get_abstract_details":
        return await scopus_provider.get(arguments["scopus_id"])
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
        fetcher = Fetcher()
        providers = build_providers(fetcher, {"api_key": config.get_api_key()})
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

        async with stdio_server() as (read_stream, write_stream):
            await server.run(read_stream, write_stream, server.create_initialization_options())
        await fetcher.close()

    asyncio.run(run())


if __name__ == "__main__":
    start()
