"""brick_mcp — BrickLink Studio MCP server package."""

from brick_mcp import tools as _tools  # noqa: F401 — registers all tools
from brick_mcp.model import get_model, set_model
from brick_mcp.server import mcp

__all__ = ["mcp", "get_model", "set_model"]
