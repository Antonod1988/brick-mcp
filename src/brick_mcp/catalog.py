"""LDraw parts catalog: lazy-loads complete.zip bundled with ldview.

Provides:
  - get_catalog()      -- dict of part_number -> {part_number, name, category}
  - search_catalog()   -- substring search over name/number
  - get_part_info()    -- detailed info dict for a single part
  - get_part_dims()    -- (x_half, y_full, z_half) bounding-box half-extents (LDU)
  - part_aabb()        -- world-space AABB for a placed part
  - aabbs_overlap()    -- AABB overlap test

The LDraw complete.zip is bundled in the ldview Nix derivation at
  /nix/store/*-ldview-*/share/ldraw/complete.zip
A fallback hard-coded table of ~100 common parts is used when the zip is absent.
"""

from __future__ import annotations

import glob
import json
import os
import re
import zipfile
import math
from pathlib import Path

# ---------------------------------------------------------------------------
# Fallback parts table (used when complete.zip is unavailable)
# ---------------------------------------------------------------------------

_FALLBACK: dict[str, str] = {
    "3001.dat": "Brick  2 x  4",
    "3002.dat": "Brick  2 x  3",
    "3003.dat": "Brick  2 x  2",
    "3004.dat": "Brick  1 x  2",
    "3005.dat": "Brick  1 x  1",
    "3006.dat": "Brick  2 x 10",
    "3007.dat": "Brick  2 x  8",
    "3008.dat": "Brick  1 x  8",
    "3009.dat": "Brick  1 x  6",
    "3010.dat": "Brick  1 x  4",
    "3011.dat": "Duplo Brick  2 x  4",
    "3012.dat": "Brick 1 x 12",
    "3014.dat": "Brick 1 x 16",
    "3020.dat": "Plate  2 x  4",
    "3021.dat": "Plate  2 x  3",
    "3022.dat": "Plate  2 x  2",
    "3023.dat": "Plate  1 x  2",
    "3024.dat": "Plate  1 x  1",
    "3031.dat": "Plate  4 x  4",
    "3032.dat": "Plate  4 x  6",
    "3033.dat": "Plate  6 x 10",
    "3034.dat": "Plate  2 x  8",
    "3035.dat": "Plate  4 x  8",
    "3037.dat": "Slope Brick 45  2 x  4",
    "3038.dat": "Slope Brick 45  2 x  3",
    "3039.dat": "Slope Brick 45  2 x  2",
    "3040.dat": "~Moved to 3040b",
    "3062b.dat": "Brick  1 x  1 Round with Hollow Stud",
    "3062.dat": "~Moved to 3062b",
    "3068b.dat": "Tile  2 x  2 with Groove",
    "3069b.dat": "Tile  1 x  2 with Groove",
    "3070b.dat": "Tile  1 x  1 with Groove",
    "3176.dat": "Plate  3 x  2 with Hole",
    "3245c.dat": "Brick  1 x  2 x  2 without Understud",
    "3298.dat": "Slope Brick 33  3 x  2",
    "3299.dat": "Slope Brick 33  2 x  4 Double",
    "3461.dat": "Propellor  4 Blade  5 Diameter with Rotor Holder",
    "3460.dat": "Plate  1 x  8",
    "3622.dat": "Brick  1 x  3",
    "3623.dat": "Plate  1 x  3",
    "3660.dat": "Slope Brick 45  2 x  2 Inverted",
    "3665.dat": "~Moved to 3665a",
    "3666.dat": "Plate  1 x  6",
    "3710.dat": "Plate  1 x  4",
    "3747b.dat": "Slope Brick 33  3 x  2 Inverted with Ribs between Studs",
    "3795.dat": "Plate  2 x  6",
    "3832.dat": "Plate  2 x 10",
    "3833.dat": "Minifig Construction Helmet",
    "4070.dat": "Brick  1 x  1 with Headlight",
    "4162.dat": "Tile  1 x  8",
    "4282.dat": "Plate  2 x 16",
    "4287.dat": "~Moved to 4287a",
    "4477.dat": "Plate  1 x 10",
    "6111.dat": "Brick  1 x 10",
    "6112.dat": "Brick  1 x 12",
    "30136.dat": "Brick  1 x  2 Log",
    "30414.dat": "Brick  1 x  4 with Studs on Side",
    "32028.dat": "Plate  1 x  2 with Door Rail",
    "32316.dat": "Technic Beam  5",
    "32524.dat": "Technic Beam  7",
    "41770.dat": "~Moved to 41770a",
    "41771.dat": "Wing 2 x 4 Left",
    "43723.dat": "~Moved to 43723a",
    "43724.dat": "Wing 3 x 6 Left",
    "50950.dat": "Slope Brick Curved  3 x  1",
    "54200.dat": "Slope Brick 31  1 x  1 x  0.667",
    "60479.dat": "Plate  1 x 12",
    "60481.dat": "Slope Brick 65  2 x  1 x  2",
    "63864.dat": "Tile  1 x  3",
    "87079.dat": "Tile  2 x  4",
    "87580.dat": "Plate  2 x  2 with Groove with 1 Centre Stud",
    "87609.dat": "Plate  2 x  6 x  0.667 with Four Studs On Side and Four Raised",
    "92438.dat": "Plate  8 x 16",
    "98283.dat": "Brick  1 x  2 with Embossed Bricks",
    "3855.dat": "~Moved to 3855b",
    "3856.dat": "Window  1 x  2 x  3 Shutter",
    "15068.dat": "Slope Brick Curved  2 x  2 x  0.667",
    "11477.dat": "Slope Brick Curved  2 x  1",
    "3455.dat": "Arch  1 x  6",
    "3308.dat": "~Arch  1 x  8 x  2 (Obsolete)",
    "4490.dat": "Arch  1 x  3",
    "6182.dat": "Arch  1 x  4 x  2",
}

# ---------------------------------------------------------------------------
# Catalog loading
# ---------------------------------------------------------------------------

_catalog: dict[str, dict[str, str]] | None = None


def _locate_complete_zip() -> str | None:
    candidates = sorted(
        glob.glob("/nix/store/*-ldview-*/share/ldraw/complete.zip"), reverse=True
    )
    return candidates[0] if candidates else None


def _guess_category(name: str) -> str:
    nl = name.lower()
    for kw, cat in [
        ("plate", "Plate"),
        ("tile", "Tile"),
        ("slope", "Slope"),
        ("arch", "Arch"),
        ("technic", "Technic"),
        ("window", "Window"),
        ("door", "Door"),
        ("minifig", "Minifig"),
        ("wheel", "Wheel"),
        ("tyre", "Tyre"),
        ("axle", "Axle"),
        ("brick", "Brick"),
    ]:
        if kw in nl:
            return cat
    return "Other"


def _load_from_zip(zip_path: str) -> dict[str, dict[str, str]]:
    result: dict[str, dict[str, str]] = {}
    prefix = "ldraw/parts/"
    with zipfile.ZipFile(zip_path) as zf:
        entries = [
            n
            for n in zf.namelist()
            if n.lower().startswith(prefix)
            and n.lower().endswith(".dat")
            and "/" not in n[len(prefix) :]
        ]
        for entry in entries:
            fname = entry.split("/")[-1].lower()
            try:
                with zf.open(entry) as fh:
                    name = ""
                    category = ""
                    for lineno, raw in enumerate(fh):
                        if lineno > 20:
                            break
                        line = raw.decode("utf-8", "replace").lstrip("\ufeff").strip()
                        if lineno == 0:
                            if line.startswith("0 "):
                                name = line[2:].strip()
                        elif line.startswith("0 !CATEGORY "):
                            category = line[12:].strip()
                            break
                    if name:
                        result[fname] = {
                            "part_number": fname,
                            "name": name,
                            "category": category or _guess_category(name),
                        }
            except Exception:
                pass
    return result


def _load_from_directory(library_path: str) -> dict[str, dict[str, str]]:
    """Read the installed Studio/LDraw parts directory without copying its files."""
    parts_dir = Path(library_path) / "parts"
    if not parts_dir.is_dir():
        raise FileNotFoundError(f"LDraw parts directory not found: {parts_dir}")
    result = {}
    for path in sorted(parts_dir.glob("*.dat")):
        with path.open(encoding="utf-8-sig", errors="replace") as fh:
            first_line = fh.readline().strip()
            if not first_line.startswith("0 "):
                continue
            name = first_line[2:].strip()
            category = _guess_category(name)
            for _ in range(20):
                line = fh.readline().strip()
                if line.startswith("0 !CATEGORY "):
                    category = line[12:].strip()
                    break
        result[path.name.lower()] = {
            "part_number": path.name.lower(),
            "name": name,
            "category": category,
        }
    return result


def get_catalog() -> dict[str, dict[str, str]]:
    """Return the full parts catalog, loading lazily on first call.

    Maps lowercase part filename (e.g. "3001.dat") to
    {"part_number", "name", "category"}.  First call parses ~20 000 parts.
    """
    global _catalog
    if _catalog is None:
        catalog_path = os.environ.get("LDRAW_CATALOG_PATH")
        if catalog_path:
            # ponytail: explicit catalog snapshot; rebuild after Studio/library updates.
            with open(catalog_path, encoding="utf-8") as fh:
                _catalog = json.load(fh)
            return _catalog
        library_path = os.environ.get("LDRAW_LIBRARY_PATH")
        if library_path:
            _catalog = _load_from_directory(library_path)
            return _catalog
        zip_path = _locate_complete_zip()
        if zip_path:
            _catalog = _load_from_zip(zip_path)
        else:
            _catalog = {
                k: {"part_number": k, "name": v, "category": _guess_category(v)}
                for k, v in _FALLBACK.items()
            }
    return _catalog


def search_catalog(query: str, limit: int = 20) -> list[dict[str, str]]:
    """Search catalog by name or part-number substring (case-insensitive).

    "2x4" is automatically expanded to "2 x 4" for matching LDraw names.
    Runs of whitespace in both query and part names are collapsed to a single
    space before matching (LDraw titles sometimes use double spaces).
    """
    catalog = get_catalog()
    if limit <= 0:
        return []
    q = re.sub(r"\s+", " ", query.lower().strip())
    q_spaced = re.sub(r"(\d)x(\d)", r"\1 x \2", q)
    results: list[dict[str, str]] = []
    for info in catalog.values():
        pn = info["part_number"].lower()
        nm = re.sub(r"\s+", " ", info["name"].lower())
        if q in pn or q in nm or (q_spaced != q and q_spaced in nm):
            results.append(info)
            if len(results) >= limit:
                break
    return results


def resolve_part_number(part_number: str) -> str:
    pn = part_number.lower().strip()
    if not re.fullmatch(r"[a-z0-9_.-]+", pn) or pn.startswith("."):
        raise ValueError("Invalid part number")
    if not pn.endswith(".dat"):
        pn += ".dat"
    seen = set()
    while pn in get_catalog():
        if pn in seen:
            raise ValueError(f"Cyclic part alias: {part_number}")
        seen.add(pn)
        moved = re.match(r"~?Moved to (\S+)", get_catalog()[pn]["name"], re.I)
        if not moved:
            return pn
        pn = moved[1].lower()
        if not pn.endswith(".dat"):
            pn += ".dat"
    raise ValueError(f"Part not found: {pn}")


def get_part_info(part_number: str) -> dict[str, str] | None:
    try:
        canonical = resolve_part_number(part_number)
        return dict(get_catalog()[canonical])
    except ValueError:
        return None


# Part bounding-box dimensions
# ---------------------------------------------------------------------------


def get_part_dims(part_number: str) -> tuple[float, float, float]:
    from brick_mcp.geometry import shape

    s = shape(part_number)
    lo, hi = s["body_min"], s["body_max"]
    return ((hi[0] - lo[0]) / 2, hi[1] - lo[1], (hi[2] - lo[2]) / 2)


def part_aabb(x, y, z, rotation, part_number):
    from brick_mcp.geometry import world_bounds

    return world_bounds(dict(x=x, y=y, z=z, rotation=rotation, part_number=part_number))


def aabbs_overlap(
    a: tuple[float, float, float, float, float, float],
    b: tuple[float, float, float, float, float, float],
    tolerance: float = 0.5,
) -> bool:
    """True if two AABBs penetrate by more than tolerance LDU.

    tolerance=0.5 lets surfaces touch without flagging a collision.
    """
    axmin, axmax, aymin, aymax, azmin, azmax = a
    bxmin, bxmax, bymin, bymax, bzmin, bzmax = b
    return (
        axmin < bxmax - tolerance
        and axmax > bxmin + tolerance
        and aymin < bymax - tolerance
        and aymax > bymin + tolerance
        and azmin < bzmax - tolerance
        and azmax > bzmin + tolerance
    )
