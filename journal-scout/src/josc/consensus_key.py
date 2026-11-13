"""Rotate and verify the Consensus API key.

The key lives in ``config.json`` (``consensus_api_key``) or the
``CONSENSUS_API_KEY`` env var, read by :func:`josc.config.get_consensus_key`.
This module lets an operator swap a leaked/old key for a new one and prove the
new key works against the live API before persisting it, so a bad rotation
never leaves the plugin with a dead key.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

import httpx

from .config import CONFIG_FILE
from .providers.consensus import CONSENSUS_URL

_KEY_PREFIX_LEN = 6


def mask_key(key: str) -> str:
    """Return the key with all but its leading prefix masked for safe display."""
    if not key:
        return ""
    if len(key) <= _KEY_PREFIX_LEN:
        return "*" * len(key)
    return key[:_KEY_PREFIX_LEN] + "*" * (len(key) - _KEY_PREFIX_LEN)


async def verify_consensus_key(
    key: str, client: Optional[httpx.AsyncClient] = None
) -> Dict[str, Any]:
    """Hit the live API once with ``key`` to confirm it is accepted.

    Returns ``{"valid": bool, "status": int | None, "error": str | None}``.
    Network failures are reported as invalid rather than raised, so a rotation
    can decide whether to proceed.
    """
    own_client = client is None
    client = client or httpx.AsyncClient(timeout=30.0)
    try:
        response = await client.get(
            CONSENSUS_URL,
            params={"query": "test", "page_size": 1, "page": 0},
            headers={"x-api-key": key},
        )
        valid = 200 <= response.status_code < 300
        return {
            "valid": valid,
            "status": response.status_code,
            "error": None if valid else f"HTTP {response.status_code}",
        }
    except httpx.HTTPError as exc:
        return {"valid": False, "status": None, "error": str(exc)}
    finally:
        if own_client:
            await client.aclose()


def write_consensus_key(
    key: str, config_path: Optional[Path] = None
) -> Path:
    """Persist ``key`` into ``config.json`` under ``consensus_api_key``.

    Other entries in the file are preserved. Returns the path written.
    """
    path = config_path or CONFIG_FILE
    data: Dict[str, Any] = {}
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            data = {}
    data["consensus_api_key"] = key
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return path


async def rotate_consensus_key(
    new_key: str,
    client: Optional[httpx.AsyncClient] = None,
    config_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """Verify ``new_key`` against the live API, then persist it on success.

    On a failed verification the old key is left untouched. Returns a summary
    with the rotation outcome and a masked hint of the key in play.
    """
    check = await verify_consensus_key(new_key, client=client)
    if not check["valid"]:
        return {
            "rotated": False,
            "valid": False,
            "status": check["status"],
            "error": check["error"],
            "key_hint": mask_key(new_key),
        }
    write_consensus_key(new_key, config_path=config_path)
    return {
        "rotated": True,
        "valid": True,
        "status": check["status"],
        "error": None,
        "key_hint": mask_key(new_key),
    }
