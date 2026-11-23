"""Helpers for parsing responses from the Exa MCP endpoint.

The upstream server can answer either as plain JSON-RPC or as a
``text/event-stream`` body containing ``data:`` lines.  Keeping the parsing
separate from the transport makes both shapes easy to exercise in tests.
"""

from __future__ import annotations

import json
from typing import Any, Dict, Optional


def parse_mcp_body(body: str) -> Optional[Dict[str, Any]]:
    """Return the first JSON-RPC payload contained in ``body``, if any."""
    body = body.strip()
    if not body:
        return None

    try:
        parsed = json.loads(body)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass

    # SSE: every event is a ``data: <json>`` line; blank lines separate events.
    for line in body.splitlines():
        line = line.strip()
        if not line.startswith("data:"):
            continue
        data = line[5:].strip()
        if not data or data == "[DONE]":
            continue
        try:
            parsed = json.loads(data)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed
    return None


def content_text(payload: Optional[Dict[str, Any]]) -> str:
    """Collect the textual ``content`` parts from a JSON-RPC result."""
    if not payload:
        return ""
    result = payload.get("result")
    if not isinstance(result, dict):
        return ""
    parts = result.get("content")
    if not isinstance(parts, list):
        text = result.get("text")
        return text.strip() if isinstance(text, str) else ""
    chunks: list[str] = []
    for part in parts:
        if isinstance(part, dict):
            text = part.get("text")
            if isinstance(text, str) and text:
                chunks.append(text)
        elif isinstance(part, str) and part:
            chunks.append(part)
    return "\n".join(chunks).strip()


def parse_payload(payload: Optional[Dict[str, Any]]) -> Any:
    """Decode the MCP result payload into a structured Python value.

    Exa tools generally return a JSON array/object as a single text content
    block.  If the content is not JSON, the plain text is returned as-is so a
    provider can decide how to present it.
    """
    text = content_text(payload)
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text
