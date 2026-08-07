"""office-mcp — MCP server entry point.

This is the single entry point for the office-mcp Model Context Protocol
server. It instantiates a ``FastMCP("office-mcp")`` singleton and
imports the per-format tool modules so that their ``@mcp.tool()``
functions are registered with the server before ``mcp.run(stdio)`` is
called.

The server communicates with the agent over **stdio JSON-RPC** (the
standard MCP transport). All logging goes to ``stderr`` — never
``stdout`` — because the JSON-RPC stream must remain clean.

Usage
-----
::

    python server.py
"""

from __future__ import annotations

import logging
import sys

from mcp.server.fastmcp import FastMCP

# Configure logging to stderr BEFORE importing tool modules. This way any
# module-level logging in office_mcp.* also goes to stderr.
logging.basicConfig(
    stream=sys.stderr,
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    force=True,
)

# Suppress the chatty INFO logs from the MCP server itself unless the
# caller has set the log level explicitly via ``OFFICE_MCP_LOG_LEVEL``.
_log_level = logging.INFO
# (We keep INFO here for now; per-milestone tuning can adjust this.)

# ---------------------------------------------------------------------------
# FastMCP singleton
# ---------------------------------------------------------------------------

mcp = FastMCP(
    name="office-mcp",
    instructions=(
        "Manage Word, Excel, and PowerPoint documents. "
        "All tools accept an absolute `path`. If a `folder` is given, "
        "`path` is resolved relative to it. Default folder from the "
        "OFFICE_MCP_DEFAULT_FOLDER env var or the server CWD."
    ),
    log_level="INFO",
)

# When this module is invoked as ``python server.py`` it loads as
# ``__main__`` (not ``server``), so the tool modules'
# ``from server import mcp`` would create a *second* module instance
# and a second FastMCP singleton — silently dropping every tool
# registration. Register this module under both names so the import
# always resolves to the same instance, regardless of how we were
# launched.
sys.modules.setdefault("server", sys.modules[__name__])

# ---------------------------------------------------------------------------
# Tool module imports
#
# Importing each module executes its module body, which calls
# ``@mcp.tool()`` to register the tool functions on the singleton. We
# load them here so that ``python server.py`` fails fast if any module
# is broken. (The underlying ``office_mcp.config`` / ``.errors`` /
# ``.paths`` modules are loaded transitively via the tool modules and
# the test suite; importing them here would be flagged by pyflakes as
# unused.)
#
# We use ``importlib.import_module`` rather than a plain
# ``from office_mcp import word_tools`` to keep the static linter
# (``pyflakes``) happy: side-effect imports of large packages are a
# classic source of false-positive F401 warnings.
# ---------------------------------------------------------------------------

import importlib  # noqa: E402

importlib.import_module("office_mcp.excel_tools")  # noqa: E402
importlib.import_module("office_mcp.general_tools")  # noqa: E402
importlib.import_module("office_mcp.pptx_tools")  # noqa: E402
importlib.import_module("office_mcp.word_tools")  # noqa: E402


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------


def main() -> None:
    """Run the MCP server on stdio JSON-RPC."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
