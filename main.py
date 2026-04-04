"""Entry point — delegates entirely to the brick_mcp package."""

from brick_mcp import mcp  # noqa: F401 — imports register all tools

if __name__ == "__main__":
    mcp.run(transport="stdio")
