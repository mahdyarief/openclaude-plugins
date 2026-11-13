"""MCP tool definitions and dispatch for SLR pipeline."""

from __future__ import annotations

from typing import Any, Dict

import mcp.types as types

from . import slr


def slr_tool_defs() -> list[types.Tool]:
    """Return MCP tool definitions for the SLR pipeline."""
    return [
        types.Tool(
            name="slr_import",
            description=(
                "Import records into the SLR review state (deduped by DOI then title). "
                "Pass papers from search results or parse_import output."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "records": {
                        "type": "array",
                        "items": {"type": "object"},
                        "description": "Paper dicts; each needs at least title, ideally doi/year/venue.",
                    },
                    "dedup": {"type": "boolean", "default": True},
                },
                "required": ["records"],
            },
        ),
        types.Tool(
            name="slr_screen",
            description="Record a title/abstract screening decision for one record.",
            inputSchema={
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "decision": {"type": "string", "enum": ["include", "exclude", "unclear"]},
                    "code": {"type": "string", "description": "Exclusion code, e.g. E1."},
                    "reason": {"type": "string"},
                    "reviewer": {"type": "string", "default": "agent"},
                    "where": {"type": "string"},
                },
                "required": ["id", "decision", "code", "reason"],
            },
        ),
        types.Tool(
            name="slr_full_text",
            description="Record a full-text eligibility decision for one record.",
            inputSchema={
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "decision": {"type": "string", "enum": ["include", "exclude"]},
                    "code": {"type": "string"},
                    "why": {"type": "string"},
                    "where": {"type": "string"},
                },
                "required": ["id", "decision", "code", "why"],
            },
        ),
        types.Tool(
            name="slr_appraise",
            description="Record quality appraisal for an included study.",
            inputSchema={
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "class": {"type": "string"},
                    "items": {
                        "type": "object",
                        "description": "Question id -> Y/N (or yes/no/1/0).",
                    },
                    "risk": {"type": "string", "default": "low"},
                },
                "required": ["id", "class", "items"],
            },
        ),
        types.Tool(
            name="slr_extract",
            description="Store extracted fields for an included study.",
            inputSchema={
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "data": {"type": "object"},
                },
                "required": ["id", "data"],
            },
        ),
        types.Tool(
            name="slr_prisma",
            description="PRISMA 2020 flow counts from the current review state.",
            inputSchema={"type": "object", "properties": {}},
        ),
        types.Tool(
            name="slr_summary",
            description="Full SLR snapshot (PRISMA + per-record decisions) or CSV when format=csv.",
            inputSchema={
                "type": "object",
                "properties": {"format": {"type": "string", "enum": ["json", "csv"], "default": "json"}},
            },
        ),
        types.Tool(
            name="slr_reset",
            description="Clear all SLR review state.",
            inputSchema={"type": "object", "properties": {}},
        ),
    ]


async def slr_call(name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Dispatch an SLR tool call."""
    if name == "slr_import":
        return slr.slr_import_records(arguments["records"], dedup=arguments.get("dedup", True))
    if name == "slr_screen":
        return slr.slr_screening(
            arguments["id"],
            arguments["decision"],
            arguments["code"],
            arguments["reason"],
            arguments.get("reviewer", "agent"),
            arguments.get("where"),
        )
    if name == "slr_full_text":
        return slr.slr_full_text(
            arguments["id"],
            arguments["decision"],
            arguments["code"],
            arguments["why"],
            arguments.get("where"),
        )
    if name == "slr_appraise":
        return slr.slr_appraisal(
            arguments["id"],
            arguments["class"],
            arguments["items"],
            arguments.get("risk", "low"),
        )
    if name == "slr_extract":
        return slr.slr_extraction(arguments["id"], arguments["data"])
    if name == "slr_prisma":
        return slr.slr_prisma()
    if name == "slr_summary":
        if arguments.get("format") == "csv":
            return {"format": "csv", "content": slr.slr_csv_summary()}
        return slr.slr_summary()
    if name == "slr_reset":
        slr.slr_reset()
        return {"reset": True}
    raise ValueError(f"Unknown SLR tool: {name}")
