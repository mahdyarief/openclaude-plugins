"""Exa MCP client, with optional round-robin API-key rotation.

The public MCP endpoint works without a key. ``EXA_API_KEYS`` (a comma- or
semicolon-separated list, or a JSON array) is optional; when present, keys are
sent as ``Authorization: Bearer`` and rotated on 401/429. Request bodies are
JSON-RPC ``tools/call`` payloads and both plain-JSON and SSE responses work.
"""

from __future__ import annotations

import asyncio
import json
import os
from typing import Any, Dict, List, Optional

import httpx

from .exa import parse_mcp_body, parse_payload
from .models import ProviderError

EXA_MCP_URL = "https://mcp.exa.ai/mcp"
ROTATE_STATUSES = frozenset({401, 429})
_LOCK = asyncio.Lock()
_INDEX = 0


def _parse_keys(raw: str) -> List[str]:
    text = raw.strip()
    if not text:
        return []
    if text.startswith("["):
        try:
            loaded = json.loads(text)
        except json.JSONDecodeError:
            loaded = None
        if isinstance(loaded, list):
            return [k.strip() for k in loaded if isinstance(k, str) and k.strip()]
    parts = text.replace(";", ",").split(",")
    return [k.strip() for k in parts if k.strip()]


def load_exa_keys() -> List[str]:
    """Load Exa keys from ``EXA_API_KEYS``, falling back to ``EXA_API_KEY``.

    Accepts a comma/semicolon-separated list or a JSON array, and de-duplicates
    keys so a repeated entry is not rotated onto twice.
    """
    keys = _parse_keys(os.getenv("EXA_API_KEYS", ""))
    if not keys:
        keys = _parse_keys(os.getenv("EXA_API_KEY", ""))
    return list(dict.fromkeys(keys))


async def _next_key(keys: List[str]) -> Optional[str]:
    global _INDEX
    if not keys:
        return None
    async with _LOCK:
        index = _INDEX % len(keys)
        _INDEX = (index + 1) % len(keys)
        return keys[index]


def reset_key_index() -> None:
    """Reset the round-robin cursor (used by tests)."""
    global _INDEX
    _INDEX = 0


async def call_exa_mcp(
    tool_name: str,
    arguments: Dict[str, Any],
    client: Optional[httpx.AsyncClient] = None,
    timeout: float = 60.0,
) -> Any:
    """Call an Exa MCP tool, rotating keys on rate-limit/auth failures.

    Returns the decoded result payload (usually a list/dict).  Raises
    :class:`ProviderError` when every key has been exhausted or the endpoint
    reports an error.
    """
    keys = load_exa_keys()
    # With no key configured the public endpoint still serves the request, so
    # there is exactly one attempt rather than an all-keys-exhausted failure.
    attempts = max(1, len(keys))
    owns_client = client is None
    client = client or httpx.AsyncClient(timeout=timeout)
    last_error: Optional[BaseException] = None
    body = json.dumps(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": tool_name, "arguments": arguments},
        }
    )
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }

    try:
        for attempt in range(attempts):
            request_headers = dict(headers)
            key = await _next_key(keys)
            if key:
                request_headers["Authorization"] = f"Bearer {key}"
            try:
                response = await client.post(EXA_MCP_URL, content=body, headers=request_headers)
            except httpx.HTTPError as exc:
                last_error = exc
                continue

            if response.status_code in ROTATE_STATUSES and attempt < attempts - 1:
                last_error = ProviderError(
                    "exa", f"Exa HTTP {response.status_code} on key {attempt + 1}"
                )
                continue
            if not response.is_success:
                raise ProviderError(
                    "exa", f"Exa HTTP {response.status_code}: {response.text[:300]}"
                )

            payload = parse_mcp_body(response.text)
            if payload is None:
                raise ProviderError("exa", "Exa MCP returned an empty response")
            if "error" in payload:
                error = payload["error"] or {}
                message = error.get("message", "Unknown error")
                raise ProviderError("exa", f"Exa MCP error: {message}")
            result = payload.get("result")
            if isinstance(result, dict) and result.get("isError"):
                text = parse_payload(payload)
                raise ProviderError("exa", str(text) if text else "Exa MCP returned an error")
            parsed = parse_payload(payload)
            if parsed is None:
                raise ProviderError("exa", "Exa MCP returned empty content")
            return parsed

        if last_error:
            raise last_error
        raise ProviderError("exa", "Exa MCP request failed after all retries")
    finally:
        if owns_client:
            await client.aclose()
