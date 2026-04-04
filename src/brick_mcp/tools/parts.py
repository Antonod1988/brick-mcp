"""Parts and colors database tools."""

from __future__ import annotations

from brick_mcp._helpers import err, ok
from brick_mcp.colors import all_colors, get_color
from brick_mcp.server import mcp

# Bundled parts lookup: LDraw part number → description.
# Covers the most commonly used LEGO parts. Use search_parts() to query.
_PARTS: dict[str, str] = {
    "3001.dat": "Brick 2 x 4",
    "3002.dat": "Brick 2 x 3",
    "3003.dat": "Brick 2 x 2",
    "3004.dat": "Brick 1 x 2",
    "3005.dat": "Brick 1 x 1",
    "3006.dat": "Brick 2 x 10",
    "3007.dat": "Brick 2 x 8",
    "3008.dat": "Brick 1 x 8",
    "3009.dat": "Brick 1 x 6",
    "3010.dat": "Brick 1 x 4",
    "3011.dat": "Brick 1 x 10",
    "3012.dat": "Brick 1 x 12",
    "3014.dat": "Brick 1 x 16",
    "3020.dat": "Plate 2 x 4",
    "3021.dat": "Plate 2 x 3",
    "3022.dat": "Plate 2 x 2",
    "3023.dat": "Plate 1 x 2",
    "3024.dat": "Plate 1 x 1",
    "3031.dat": "Plate 4 x 4",
    "3032.dat": "Plate 4 x 6",
    "3033.dat": "Plate 6 x 8",
    "3034.dat": "Plate 1 x 8",
    "3035.dat": "Plate 4 x 8",
    "3036.dat": "Plate 6 x 8 (old)",
    "3037.dat": "Slope Brick 45 2 x 4",
    "3038.dat": "Slope Brick 45 2 x 3",
    "3039.dat": "Slope Brick 45 2 x 2",
    "3040.dat": "Slope Brick 45 2 x 1",
    "3041.dat": "Slope Brick 31 1 x 1 x 0.667",
    "3042.dat": "Slope Brick 45 2 x 1 Double",
    "3043.dat": "Slope Brick 45 2 x 2 Double",
    "3044.dat": "Slope Brick 18 4 x 2",
    "3045.dat": "Slope Brick 18 2 x 2",
    "3046.dat": "Slope Brick 45 2 x 2 x 2/3",
    "3047.dat": "Slope Brick 31 1 x 2 x 1.333",
    "3062b.dat": "Brick Round 1 x 1 Open Stud",
    "3062.dat": "Brick Round 1 x 1",
    "3068b.dat": "Tile 2 x 2",
    "3069b.dat": "Tile 1 x 2",
    "3070b.dat": "Tile 1 x 1",
    "3176.dat": "Plate Special 3 x 2 with 1 Stud",
    "3185.dat": "Train Window 1 x 2 x 2",
    "3245c.dat": "Brick 1 x 2 x 2",
    "3298.dat": "Slope Brick 33 3 x 2",
    "3299.dat": "Slope Brick 33 3 x 1",
    "3461.dat": "Plate 1 x 10",
    "3460.dat": "Plate 1 x 12",
    "3622.dat": "Brick 1 x 3",
    "3623.dat": "Plate 1 x 3",
    "3660.dat": "Slope Brick 45 2 x 2 Inverted",
    "3665.dat": "Slope Brick 45 2 x 1 Inverted",
    "3666.dat": "Plate 1 x 6",
    "3710.dat": "Plate 1 x 4",
    "3747b.dat": "Slope Brick 33 3 x 2 Inverted",
    "3795.dat": "Plate 2 x 6",
    "3832.dat": "Plate 2 x 10",
    "3833.dat": "Plate 2 x 8",
    "4070.dat": "Brick Special 1 x 1 with Headlight",
    "4162.dat": "Tile 1 x 8",
    "4282.dat": "Plate 2 x 16",
    "4287.dat": "Slope Brick 33 3 x 1 Inverted",
    "4477.dat": "Plate 1 x 10",
    "4623.dat": "Plate 1 x 2 with Groove",
    "6111.dat": "Brick 1 x 10",
    "6112.dat": "Brick 1 x 12",
    "30136.dat": "Brick Round 1 x 2",
    "30414.dat": "Plate Special 1 x 4 with 2 Studs",
    "32028.dat": "Plate Special 1 x 2 with Handle",
    "32316.dat": "Technic Beam 5",
    "32524.dat": "Technic Beam 7",
    "41770.dat": "Wing 2 x 4 Right",
    "41771.dat": "Wing 2 x 4 Left",
    "43723.dat": "Wing 3 x 6 Right",
    "43724.dat": "Wing 3 x 6 Left",
    "50950.dat": "Slope Brick Curved 3 x 1",
    "54200.dat": "Slope Brick 31 1 x 1 x 2/3",
    "60479.dat": "Plate 1 x 12",
    "60481.dat": "Slope Brick 65 2 x 1 x 2",
    "63864.dat": "Tile 1 x 3",
    "64782.dat": "Technic Beam 3 x 0.5",
    "87079.dat": "Tile 2 x 4",
    "87580.dat": "Plate Special 2 x 2 with 1 Stud",
    "87609.dat": "Brick Round 2 x 2 Dome Top",
    "92438.dat": "Plate 8 x 16",
    "98283.dat": "Brick Special 1 x 2 with Groove",
    # Windows, doors
    "3855.dat": "Window 1 x 2 x 3",
    "3856.dat": "Window Frame 1 x 4 x 3",
    # Slopes
    "15068.dat": "Slope Brick Curved 2 x 2 x 2/3",
    "11477.dat": "Slope Brick Curved 2 x 1 x 2/3",
    # Arches
    "3455.dat": "Arch 1 x 2",
    "3308.dat": "Arch 1 x 4",
    "4490.dat": "Arch 1 x 3",
    "6182.dat": "Arch 1 x 6 x 2",
    "3308.dat": "Arch 1 x 4",
}


@mcp.tool
def search_parts(query: str, limit: int = 20) -> dict:
    """Search the parts database by name or part number.

    Args:
        query: Search string (case-insensitive). Can be part of a name
               (e.g. "brick 2x4", "slope", "tile") or a part number
               (e.g. "3001", "3020").
        limit: Maximum number of results to return (default 20).

    Returns:
        List of matching parts: [{"part_number": "3001.dat", "name": "Brick 2 x 4"}, ...]
    """
    query_lower = query.lower().strip()
    results = []
    for part_num, name in _PARTS.items():
        if query_lower in part_num.lower() or query_lower in name.lower():
            results.append({"part_number": part_num, "name": name})
        if len(results) >= limit:
            break
    return ok(results, f"{len(results)} result(s) for '{query}'")


@mcp.tool
def list_colors() -> dict:
    """Return all available LDraw colors.

    Returns:
        List of color dicts: [{"code": 4, "name": "Red", "hex": "#C91A09", "edge": "..."}, ...]
        Sorted by color code.
    """
    return ok(all_colors())


@mcp.tool
def get_color_info(color_code: int) -> dict:
    """Return details for a specific LDraw color code.

    Args:
        color_code: Integer LDraw color code (e.g. 4 for Red, 1 for Blue).

    Returns:
        Color dict: {"code": 4, "name": "Red", "hex": "#C91A09", "edge": "#333333"}
        or an error if the code is not in the database.
    """
    color = get_color(color_code)
    if color is None:
        return err(
            f"Color code {color_code} not found in LDraw color database.",
            "COLOR_NOT_FOUND",
        )
    return ok({"code": color_code, **color})
