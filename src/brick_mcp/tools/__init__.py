"""Register all tool modules by importing them (side-effect: @mcp.tool() decorators run)."""

from brick_mcp.tools import file_ops, inspection, manipulation, parts, render

__all__ = ["file_ops", "inspection", "manipulation", "parts", "render"]
