"""Register all tool modules by importing them (side-effect: @mcp.tool() decorators run)."""

from brick_mcp.tools import (
    batch,
    file_ops,
    inspection,
    layout,
    manipulation,
    parts,
    render,
    workflow,
)

__all__ = [
    "batch",
    "file_ops",
    "inspection",
    "layout",
    "manipulation",
    "parts",
    "render",
]
