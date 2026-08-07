"""office-mcp — MCP server for managing Word, Excel, and PowerPoint documents.

This package is the implementation core of the office-mcp server. The
``server`` module (at the project root) instantiates a single
``FastMCP("office-mcp")`` instance and imports the tool modules here
(``word_tools``, ``excel_tools``, ``pptx_tools``, ``general_tools``)
to register their ``@mcp.tool()``-decorated functions.
"""

__version__ = "0.1.0"

__all__ = [
    "config",
    "paths",
    "errors",
    "exporters",
]
