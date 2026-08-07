"""Structured error infrastructure for office-mcp.

All tools raise :class:`OfficeMCPError` (or a subclass) on failure.
FastMCP catches it and serializes it as a ``CallToolResult`` with
``isError=True`` and a ``structuredContent`` dict carrying the
error ``code`` and ``details``.

The error codes occupy the JSON-RPC "server error" window
(``-32099``..``-32000``); see :rfc:`server-error`.
"""

from __future__ import annotations

from typing import Any

__all__ = [
    "OfficeMCPError",
    "ERR_FILE_NOT_FOUND",
    "ERR_FILE_LOCKED",
    "ERR_UNSUPPORTED_FMT",
    "ERR_INVALID_PARAMS",
    "ERR_EXPORT_FAILED",
    "ERR_LIBREOFFICE_MISSING",
    "ERR_SHEET_NOT_FOUND",
    "ERR_CELL_PARSE",
    "ERR_DISK_FULL",
]


# ---------------------------------------------------------------------------
# Error code constants
# ---------------------------------------------------------------------------

ERR_FILE_NOT_FOUND: int = -32001
ERR_FILE_LOCKED: int = -32002
ERR_UNSUPPORTED_FMT: int = -32003
ERR_INVALID_PARAMS: int = -32004
ERR_EXPORT_FAILED: int = -32005
ERR_LIBREOFFICE_MISSING: int = -32006
ERR_SHEET_NOT_FOUND: int = -32007
ERR_CELL_PARSE: int = -32008
ERR_DISK_FULL: int = -32009


# ---------------------------------------------------------------------------
# OfficeMCPError
# ---------------------------------------------------------------------------


class OfficeMCPError(Exception):
    """Raised by tools to signal a structured, agent-friendly failure.

    Parameters
    ----------
    code:
        Numeric error code (one of the ``ERR_*`` constants above).
    message:
        Human-readable explanation of the failure.
    details:
        Optional mapping of additional context. Will be returned in the
        ``structuredContent`` of the MCP response.
    """

    def __init__(
        self,
        code: int,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details: dict[str, Any] = dict(details) if details else {}

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serialisable representation of the error."""
        return {
            "code": self.code,
            "message": self.message,
            "details": self.details,
        }

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return (
            f"OfficeMCPError(code={self.code}, message={self.message!r}, "
            f"details={self.details!r})"
        )
