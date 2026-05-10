"""``folio-mcp`` — Anthropic-style MCP server for Folio sheets.

Exposes the nine SDK operations as MCP tools so AI agents can operate
sheets through a standard protocol. See ``folio_mcp.server.build_server``.
"""

from .server import build_server

__all__ = ["build_server"]
__version__ = "0.1.0"
