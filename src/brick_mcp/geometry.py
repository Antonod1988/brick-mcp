"""LDraw geometry shared by footprint checks, connections and previews."""

from __future__ import annotations

import math
import os
import re
from functools import lru_cache
from itertools import product
from pathlib import Path


def transform(point, matrix, offset=(0, 0, 0)):
    return tuple(
        sum(matrix[i * 3 + j] * point[j] for j in range(3)) + offset[i]
        for i in range(3)
    )


def multiply(a, b):
    return tuple(
        sum(a[i * 3 + k] * b[k * 3 + j] for k in range(3))
        for i in range(3)
        for j in range(3)
    )


def validate_transform(x, y, z, matrix):
    if len(matrix) != 9 or not all(math.isfinite(v) for v in (x, y, z, *matrix)):
        raise ValueError("Position and 9 rotation values must be finite")
    if any(
        abs(sum(matrix[k * 3 + i] * matrix[k * 3 + j] for k in range(3)) - (i == j))
        > 1e-5
        for i in range(3)
        for j in range(3)
    ):
        raise ValueError(
            "Placement rotation must be orthonormal; scaling is not a LEGO placement"
        )


def _source(root, name):
    name = name.replace("\\", "/")
    if Path(name).is_absolute() or ".." in name.split("/") or ":" in name:
        raise ValueError("LDraw references must stay inside the parts library")
    for folder in ("parts", "p", "UnOfficial/parts", "UnOfficial/p", ""):
        path = Path(root) / folder / name
        if path.is_file():
            return path
    raise FileNotFoundError(f"LDraw geometry not found: {name}")


@lru_cache(maxsize=512)
def mesh(root, name, ancestors=()):
    """Triangles with inherited LDraw color 16 preserved; fail on missing references."""
    if name.lower() in ancestors or len(ancestors) > 64:
        raise ValueError(f"Cyclic/deep LDraw reference: {name}")
    faces = []
    for line in (
        _source(root, name)
        .read_text(encoding="utf-8-sig", errors="replace")
        .splitlines()
    ):
        f = line.split()
        if not f or f[0] not in ("1", "3", "4"):
            continue
        color = int(f[1])
        values = list(map(float, f[2:14] if f[0] == "1" else f[2:]))
        if not all(math.isfinite(v) for v in values):
            raise ValueError(f"Nonfinite geometry: {name}")
        if f[0] == "1":
            for triangle, child_color in mesh(
                root, " ".join(f[14:]), ancestors + (name.lower(),)
            ):
                faces.append(
                    (
                        tuple(transform(v, values[3:], values[:3]) for v in triangle),
                        color if child_color == 16 else child_color,
                    )
                )
        else:
            vertices = tuple(tuple(values[i : i + 3]) for i in range(0, len(values), 3))
            faces.append((vertices[:3], color))
            if f[0] == "4":
                faces.append(((vertices[0], vertices[2], vertices[3]), color))
    return tuple(faces)


_REGULAR = re.compile(
    r"^(Brick|Plate|Tile|Baseplate)\s+(\d+)\s*x\s*(\d+)(?:\s*x\s*(\d+(?:\.\d+)?))?(?:\s+(?:with Groove|Round))?$",
    re.I,
)


@lru_cache(maxsize=512)
def _shape(root, pn, name):
    regular = _REGULAR.fullmatch(" ".join(name.split()))
    if root:
        triangles = mesh(root, pn)
        if not triangles:
            raise ValueError(f"No triangle geometry for {pn}")
        points = [p for face, _ in triangles for p in face]
        low = tuple(min(p[i] for p in points) for i in range(3))
        high = tuple(max(p[i] for p in points) for i in range(3))
        source = "ldraw_geometry"
    elif regular:
        kind, m, n, h = regular.groups()
        height = (
            4
            if kind.lower() == "baseplate"
            else 8 if kind.lower() in ("plate", "tile") else 24 * float(h or 1)
        )
        low, high = (-int(n) * 10, 0, -int(m) * 10), (int(n) * 10, height, int(m) * 10)
        source = "regular_part_dimensions"
    else:
        raise ValueError(f"Actual geometry is required for this non-regular part: {pn}")
    # Ordinary bricks' studs interlock with the receiver cavity: body overlap excludes studs.
    body_low = (low[0], 0, low[2]) if regular else low
    return {
        "part_number": pn,
        "name": name,
        "geometry_min": low,
        "geometry_max": high,
        "body_min": body_low,
        "body_max": high,
        "source": source,
        "connection_kind": regular.group(1).lower() if regular else "unknown",
        "collision_kind": (
            "regular_body"
            if regular and "round" not in name.lower()
            else "conservative_box"
        ),
    }


def shape(part_number):
    from brick_mcp.catalog import get_part_info

    info = get_part_info(part_number)
    if info is None:
        raise ValueError(f"Part not found: {part_number}")
    return _shape(
        os.environ.get("LDRAW_LIBRARY_PATH", ""), info["part_number"], info["name"]
    )


def world_bounds(part):
    s = shape(part["part_number"])
    points = [
        transform(p, part["rotation"], (part["x"], part["y"], part["z"]))
        for p in product(*zip(s["body_min"], s["body_max"]))
    ]
    return tuple(
        v
        for i in range(3)
        for v in (min(p[i] for p in points), max(p[i] for p in points))
    )


def connectors(part):
    """Verified ordinary vertical stud/receiver grids; unsupported connectors stay unknown."""
    s = shape(part["part_number"])
    r = part["rotation"]
    if s["connection_kind"] == "unknown" or any(
        abs(r[i] - v) > 1e-5 for i, v in ((1, 0), (3, 0), (4, 1), (5, 0), (7, 0))
    ):
        return None
    lo, hi = s["body_min"], s["body_max"]
    nx, nz = round((hi[0] - lo[0]) / 20), round((hi[2] - lo[2]) / 20)
    if nx < 1 or nz < 1:
        return None
    offset = (part["x"], part["y"], part["z"])
    grid = [
        (lo[0] + 10 + 20 * i, lo[2] + 10 + 20 * j) for i in range(nx) for j in range(nz)
    ]
    top = (
        []
        if s["connection_kind"] == "tile"
        else [transform((x, 0, z), r, offset) for x, z in grid]
    )
    bottom = (
        []
        if s["connection_kind"] == "baseplate"
        else [transform((x, hi[1], z), r, offset) for x, z in grid]
    )
    return {"top": top, "bottom": bottom}
