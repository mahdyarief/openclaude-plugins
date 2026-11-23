"""Harness readiness for a model-free PaperAssist.

The repository no longer ships an OpenAI-compatible client, credentials,
or a provider registry. Readiness now answers a different question: is the
external AI harness (OpenClaude, Claude Code, Freebuff) able to operate this
workspace, and are the deterministic tools it needs present?
"""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from typing import Any

PLUGIN_MANIFEST = ".claude-plugin/plugin.json"
MCP_MANIFEST = ".mcp.json"
HARNESS_ENV_MARKERS = (
    "CLAUDE_PLUGIN_ROOT",
    "CLAUDE_CODE_ENTRYPOINT",
    "OPENCLAUDE_HOME",
    "FREEBUFF_SESSION_ID",
)
PACK_KINDS = ("ideation", "review", "experiment", "writing")


def plugin_root() -> Path:
    configured = os.environ.get("CLAUDE_PLUGIN_ROOT")
    if configured:
        return Path(configured).expanduser().resolve()
    return Path(__file__).resolve().parent.parent


def _manifest_servers(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    servers = payload.get("mcpServers") if isinstance(payload, dict) else None
    return servers if isinstance(servers, dict) else {}


def _mcp_servers(root: Path) -> dict[str, Any]:
    """MCP servers the plugin declares.

    ``plugin.json`` is authoritative for an installed plugin; a standalone
    ``.mcp.json`` (project-level registration) is merged in when present.
    """

    servers = dict(_manifest_servers(root / MCP_MANIFEST))
    servers.update(_manifest_servers(root / PLUGIN_MANIFEST))
    return servers


def harness_status(workspace: str | Path, *, root: str | Path | None = None) -> dict[str, Any]:
    """Deterministic readiness report; never contacts a network model."""

    workspace_path = Path(workspace).expanduser().resolve()
    plugin_dir = Path(root).expanduser().resolve() if root else plugin_root()
    tools = {
        name: shutil.which(name) is not None
        for name in ("latexmk", "pdflatex", "bibtex", "pdftoppm", "python")
    }
    servers = _mcp_servers(plugin_dir)
    checks = {
        "workspace_exists": workspace_path.is_dir(),
        "workspace_writable": workspace_path.is_dir() and os.access(workspace_path, os.W_OK),
        "plugin_manifest": (plugin_dir / PLUGIN_MANIFEST).is_file(),
        "mcp_manifest": bool(servers),
        "latex_compiler": bool(tools["latexmk"] or tools["pdflatex"]),
        "pdf_renderer": bool(tools["pdftoppm"]),
        "harness_detected": any(os.environ.get(marker) for marker in HARNESS_ENV_MARKERS),
    }
    required = ("workspace_exists", "workspace_writable", "plugin_manifest")
    blocking = [name for name in required if not checks[name]]
    return {
        "writer": "ai-harness",
        "provider": "NOT_APPLICABLE",
        "provider_calls": 0,
        "status": "READY" if not blocking else "DEGRADED",
        "blocking": blocking,
        "checks": checks,
        "tools": tools,
        "mcp_servers": sorted(servers),
        "pack_kinds": list(PACK_KINDS),
        "plugin_root": str(plugin_dir),
        "workspace": str(workspace_path),
    }


__all__ = ["PACK_KINDS", "harness_status", "plugin_root"]
