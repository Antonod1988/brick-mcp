"""Parts and colors database tools (backed by LDraw catalog)."""

from __future__ import annotations

from brick_mcp._helpers import err, ok
from brick_mcp.catalog import get_part_info, search_catalog
from brick_mcp.colors import all_colors, get_color
from brick_mcp.server import mcp


@mcp.tool
def search_parts(query: str, limit: int = 20) -> dict:
    """Search the LDraw parts catalog by name or part number.

    When the LDraw complete.zip is available (bundled with ldview) this
    searches ~20 000 parts.  Otherwise a built-in fallback table of ~100
    common parts is used.

    "2x4" notation is automatically expanded to "2 x 4" to match LDraw names.

    Args:
        query: Search string (case-insensitive substring). Examples:
               "brick 2x4", "slope", "tile 1x2", "3001".
        limit: Maximum number of results (default 20, max 200).

    Returns:
        List of matching parts:
        [{"part_number": "3001.dat", "name": "Brick 2 x 4", "category": "Brick"}, ...]
    """
    limit = min(int(limit), 200)
    results = search_catalog(query, limit)
    return ok(results, f"{len(results)} result(s) for '{query}'")


@mcp.tool
def get_part_details(part_number: str) -> dict:
    """Return catalog details for a single LDraw part.

    Args:
        part_number: LDraw part number with or without ".dat" extension
                     (e.g. "3001" or "3001.dat").

    Returns:
        {"part_number": "3001.dat", "name": "Brick 2 x 4", "category": "Brick"}
        or error if not found.
    """
    info = get_part_info(part_number)
    if info is None:
        pn = part_number.strip()
        return err(f"Part '{pn}' not found in catalog", "PART_NOT_FOUND")
    return ok(info, info["name"])


@mcp.tool
def list_colors() -> dict:
    """Return all available LDraw colors.

    Returns:
        List of color dicts sorted by code:
        [{"code": 4, "name": "Red", "hex": "#C91A09", "edge": "#333333"}, ...]
    """
    return ok(all_colors())


@mcp.tool
def get_color_info(color_code: int) -> dict:
    """Return details for a specific LDraw color code.

    Args:
        color_code: Integer LDraw color code (e.g. 4 for Red, 1 for Blue).

    Returns:
        {"code": 4, "name": "Red", "hex": "#C91A09", "edge": "#333333"}
        or error if not found.
    """
    color = get_color(color_code)
    if color is None:
        return err(
            f"Color code {color_code} not found in LDraw color database.",
            "COLOR_NOT_FOUND",
        )
    return ok({"code": color_code, **color})
