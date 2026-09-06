"""Parts and colors database tools (backed by LDraw catalog)."""

from __future__ import annotations

from brick_mcp._helpers import err, ok
from brick_mcp.catalog import get_part_dims, get_part_info, search_catalog
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
def get_part_footprint(part_number: str) -> dict:
    """Return the bounding-box footprint for a part to aid collision-free placement.

    Use this BEFORE computing brick positions to know exactly how much space each
    part occupies.  The footprint is the axis-aligned bounding box (AABB) of the
    part body in LDU.

    Placement rule for side-by-side bricks:
      center_distance_X = x_half_A + x_half_B
      center_distance_Z = z_half_A + z_half_B

    Args:
        part_number: LDraw part number with or without ".dat" (e.g. "3001" or "3010.dat").

    Returns:
        {
          "part_number": "3001.dat",
          "name": "Brick 2 x 4",
          "x_half": 40.0,   # half-width along X axis in LDU
          "z_half": 20.0,   # half-depth along Z axis in LDU
          "height": 24.0,   # full height along Y axis in LDU
          "x_span": 80.0,   # total width  (= x_half * 2)
          "z_span": 40.0,   # total depth  (= z_half * 2)
          "placement_note": "Two of these placed side-by-side in X need"
                            " center-to-center distance >= 80 LDU (40+40)."
        }
    """
    try:
        from brick_mcp.geometry import shape

        data = shape(part_number)
        lo, hi = data["body_min"], data["body_max"]
        return ok(
            {
                **data,
                "x_half": (hi[0] - lo[0]) / 2,
                "z_half": (hi[2] - lo[2]) / 2,
                "x_span": hi[0] - lo[0],
                "z_span": hi[2] - lo[2],
                "height": hi[1] - lo[1],
                "placement_note": "Use body_min/body_max: a part origin need not be centered.",
            }
        )
    except (ValueError, OSError) as exc:
        return err(str(exc), "GEOMETRY_UNAVAILABLE")


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
