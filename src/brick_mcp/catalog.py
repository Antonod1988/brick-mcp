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
import re
import zipfile

# ---------------------------------------------------------------------------
# Fallback parts table (used when complete.zip is unavailable)
# ---------------------------------------------------------------------------

_FALLBACK: dict[str, str] = {
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
    "3037.dat": "Slope Brick 45 2 x 4",
    "3038.dat": "Slope Brick 45 2 x 3",
    "3039.dat": "Slope Brick 45 2 x 2",
    "3040.dat": "Slope Brick 45 2 x 1",
    "3062b.dat": "Brick Round 1 x 1 Open Stud",
    "3062.dat": "Brick Round 1 x 1",
    "3068b.dat": "Tile 2 x 2",
    "3069b.dat": "Tile 1 x 2",
    "3070b.dat": "Tile 1 x 1",
    "3176.dat": "Plate Special 3 x 2 with 1 Stud",
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
    "87079.dat": "Tile 2 x 4",
    "87580.dat": "Plate Special 2 x 2 with 1 Stud",
    "87609.dat": "Brick Round 2 x 2 Dome Top",
    "92438.dat": "Plate 8 x 16",
    "98283.dat": "Brick Special 1 x 2 with Groove",
    "3855.dat": "Window 1 x 2 x 3",
    "3856.dat": "Window Frame 1 x 4 x 3",
    "15068.dat": "Slope Brick Curved 2 x 2 x 2/3",
    "11477.dat": "Slope Brick Curved 2 x 1 x 2/3",
    "3455.dat": "Arch 1 x 2",
    "3308.dat": "Arch 1 x 4",
    "4490.dat": "Arch 1 x 3",
    "6182.dat": "Arch 1 x 6 x 2",
}

# ---------------------------------------------------------------------------
# Hard-coded precise bounding boxes for common parts.
# (x_half, y_full, z_half) in LDU.
# LDraw origin: centre of TOP face. Body extends DOWN in +Y by y_full.
# "Brick M x N": z_half=M*10, x_half=N*10, y_full=24.  Plates: y_full=8.
# ---------------------------------------------------------------------------

_PART_DIMS: dict[str, tuple[float, float, float]] = {
    "3001.dat": (40.0, 24.0, 20.0),
    "3002.dat": (30.0, 24.0, 20.0),
    "3003.dat": (20.0, 24.0, 20.0),
    "3004.dat": (20.0, 24.0, 10.0),
    "3005.dat": (10.0, 24.0, 10.0),
    "3006.dat": (100.0, 24.0, 20.0),
    "3007.dat": (80.0, 24.0, 20.0),
    "3008.dat": (80.0, 24.0, 10.0),
    "3009.dat": (60.0, 24.0, 10.0),
    "3010.dat": (40.0, 24.0, 10.0),
    "3011.dat": (100.0, 24.0, 10.0),
    "3012.dat": (120.0, 24.0, 10.0),
    "3014.dat": (160.0, 24.0, 10.0),
    "3622.dat": (30.0, 24.0, 10.0),
    "6111.dat": (100.0, 24.0, 10.0),
    "6112.dat": (120.0, 24.0, 10.0),
    "3245c.dat": (20.0, 48.0, 10.0),
    "3020.dat": (40.0, 8.0, 20.0),
    "3021.dat": (30.0, 8.0, 20.0),
    "3022.dat": (20.0, 8.0, 20.0),
    "3023.dat": (20.0, 8.0, 10.0),
    "3024.dat": (10.0, 8.0, 10.0),
    "3031.dat": (40.0, 8.0, 40.0),
    "3032.dat": (60.0, 8.0, 40.0),
    "3033.dat": (80.0, 8.0, 60.0),
    "3034.dat": (80.0, 8.0, 10.0),
    "3035.dat": (80.0, 8.0, 40.0),
    "3461.dat": (100.0, 8.0, 10.0),
    "3460.dat": (120.0, 8.0, 10.0),
    "3623.dat": (30.0, 8.0, 10.0),
    "3666.dat": (60.0, 8.0, 10.0),
    "3710.dat": (40.0, 8.0, 10.0),
    "3795.dat": (60.0, 8.0, 20.0),
    "3832.dat": (100.0, 8.0, 20.0),
    "3833.dat": (80.0, 8.0, 20.0),
    "4282.dat": (160.0, 8.0, 20.0),
    "4477.dat": (100.0, 8.0, 10.0),
    "60479.dat": (120.0, 8.0, 10.0),
    "92438.dat": (160.0, 8.0, 80.0),
    "30414.dat": (40.0, 8.0, 10.0),
    "32028.dat": (20.0, 8.0, 10.0),
    "87580.dat": (20.0, 8.0, 20.0),
    "3176.dat": (20.0, 8.0, 30.0),
    "3068b.dat": (20.0, 8.0, 20.0),
    "3069b.dat": (20.0, 8.0, 10.0),
    "3070b.dat": (10.0, 8.0, 10.0),
    "4162.dat": (80.0, 8.0, 10.0),
    "63864.dat": (30.0, 8.0, 10.0),
    "87079.dat": (40.0, 8.0, 20.0),
    "3062.dat": (10.0, 24.0, 10.0),
    "3062b.dat": (10.0, 24.0, 10.0),
    "30136.dat": (20.0, 24.0, 10.0),
    "87609.dat": (20.0, 24.0, 20.0),
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


def get_catalog() -> dict[str, dict[str, str]]:
    """Return the full parts catalog, loading lazily on first call.

    Maps lowercase part filename (e.g. "3001.dat") to
    {"part_number", "name", "category"}.  First call parses ~20 000 parts.
    """
    global _catalog
    if _catalog is None:
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


def get_part_info(part_number: str) -> dict[str, str] | None:
    """Return catalog info for one part, or None if not found."""
    pn = part_number.lower().strip()
    if not pn.endswith(".dat"):
        pn += ".dat"
    return get_catalog().get(pn)


# ---------------------------------------------------------------------------
# Part bounding-box dimensions
# ---------------------------------------------------------------------------

_DIM_PATTERN = re.compile(
    r"(?P<m>\d+)\s*x\s*(?P<n>\d+)(?:\s*x\s*(?P<h>\d+(?:\.\d+)?))?",
    re.IGNORECASE,
)


def _dims_from_name(name: str) -> tuple[float, float, float]:
    nl = name.lower()
    m = _DIM_PATTERN.search(nl)
    if m:
        z_half = float(int(m.group("m")) * 10)
        x_half = float(int(m.group("n")) * 10)
    else:
        x_half = z_half = 10.0
    y_full = 8.0 if any(w in nl for w in ("plate", "tile")) else 24.0
    return (x_half, y_full, z_half)


def get_part_dims(part_number: str) -> tuple[float, float, float]:
    """Return (x_half, y_full, z_half) AABB half-extents in LDU.

    Body occupies:
      X in [x - x_half, x + x_half]
      Y in [y, y + y_full]   (Y inverted; body below LDraw origin)
      Z in [z - z_half, z + z_half]
    """
    pn = part_number.lower().strip()
    if not pn.endswith(".dat"):
        pn += ".dat"
    hard = _PART_DIMS.get(pn)
    if hard:
        return hard
    info = get_part_info(pn)
    if info:
        return _dims_from_name(info["name"])
    return (10.0, 24.0, 10.0)


# ---------------------------------------------------------------------------
# AABB helpers used by layout tools
# ---------------------------------------------------------------------------


def part_aabb(
    x: float,
    y: float,
    z: float,
    rotation: list[float],
    part_number: str,
) -> tuple[float, float, float, float, float, float]:
    """Compute world-space AABB (xmin,xmax,ymin,ymax,zmin,zmax) for a placed part.

    For rotated parts the 8 OBB corners are transformed and their AABB is returned
    (conservative — may over-estimate for highly non-cubic parts at odd angles).
    """
    hx, y_full, hz = get_part_dims(part_number)
    hy = y_full / 2.0
    # LDraw origin is at top face; body centre is hy below in +Y direction
    cx, cy, cz = x, y + hy, z
    r = rotation
    xs: list[float] = []
    ys: list[float] = []
    zs: list[float] = []
    for sx in (-hx, hx):
        for sy in (-hy, hy):
            for sz in (-hz, hz):
                xs.append(cx + r[0] * sx + r[1] * sy + r[2] * sz)
                ys.append(cy + r[3] * sx + r[4] * sy + r[5] * sz)
                zs.append(cz + r[6] * sx + r[7] * sy + r[8] * sz)
    return (min(xs), max(xs), min(ys), max(ys), min(zs), max(zs))


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
