"""Layout and collision-detection tools for brick placement."""

from __future__ import annotations

from fastmcp.utilities.types import Image

from brick_mcp._helpers import err, ok, ok_with_render, placement_warnings
from brick_mcp.catalog import aabbs_overlap, part_aabb
from brick_mcp.model import get_model
from brick_mcp.server import mcp

_STUD = 20.0  # X / Z grid spacing in LDU
_PLATE = 8.0  # Y grid spacing in LDU (one plate height)


@mcp.tool
def check_overlaps(submodel: str = "") -> dict:
    """Check the current model for overlapping (colliding) bricks.

    Uses axis-aligned bounding boxes (AABB) for each part.  For rotated parts
    the OBB corners are used to produce a conservative AABB.  Two parts are
    considered overlapping only if they penetrate by more than 0.5 LDU, so
    touching faces are NOT reported as collisions.

    Args:
        submodel: Name of submodel to check. Leave empty for root.

    Returns:
        {
          "overlap_count": N,
          "overlaps": [
            {"part_a": {"id": ..., "part_number": ..., "x": ..., "y": ..., "z": ...},
             "part_b": {...}},
            ...
          ]
        }
    """
    try:
        project = get_model()
    except RuntimeError as e:
        return err(str(e), "NO_MODEL")

    try:
        parts = project.list_parts(submodel or None)
    except KeyError as e:
        return err(str(e), "SUBMODEL_NOT_FOUND")

    aabbs = []
    for p in parts:
        bb = part_aabb(p["x"], p["y"], p["z"], p["rotation"], p["part_number"])
        aabbs.append((p, bb))

    overlaps = []
    for i in range(len(aabbs)):
        pa, ba = aabbs[i]
        for j in range(i + 1, len(aabbs)):
            pb, bb = aabbs[j]
            if aabbs_overlap(ba, bb):
                overlaps.append(
                    {
                        "part_a": {
                            "id": pa["id"],
                            "part_number": pa["part_number"],
                            "x": pa["x"],
                            "y": pa["y"],
                            "z": pa["z"],
                        },
                        "part_b": {
                            "id": pb["id"],
                            "part_number": pb["part_number"],
                            "x": pb["x"],
                            "y": pb["y"],
                            "z": pb["z"],
                        },
                    }
                )

    msg = f"{len(overlaps)} overlap(s) found" if overlaps else "No overlaps detected"
    return ok({"overlap_count": len(overlaps), "overlaps": overlaps}, msg)


@mcp.tool
def validate_placement(
    part_number: str,
    x: float,
    y: float,
    z: float,
    rotation_matrix: list[float] | None = None,
    submodel: str = "",
) -> dict:
    """Check whether placing a part at a position would cause overlaps.

    Call this BEFORE add_part() to confirm a placement is collision-free.
    Does NOT modify the model.

    Args:
        part_number: LDraw part number, e.g. "3001" or "3001.dat".
        x, y, z:    Proposed position in LDU.
        rotation_matrix: 9 floats row-major 3x3. Defaults to identity.
        submodel:   Leave empty for root.

    Returns:
        {"valid": true, "conflict_count": 0, "conflicts": []}  or
        {"valid": false, "conflict_count": N, "conflicts": [...]}
    """
    try:
        project = get_model()
    except RuntimeError as e:
        return err(str(e), "NO_MODEL")

    if rotation_matrix is not None and len(rotation_matrix) != 9:
        return err("rotation_matrix must have exactly 9 values", "INVALID_MATRIX")

    rot = (
        rotation_matrix if rotation_matrix is not None else [1, 0, 0, 0, 1, 0, 0, 0, 1]
    )

    try:
        parts = project.list_parts(submodel or None)
    except KeyError as e:
        return err(str(e), "SUBMODEL_NOT_FOUND")

    pn = part_number.lower().strip()
    if not pn.endswith(".dat"):
        pn += ".dat"

    proposed_bb = part_aabb(x, y, z, rot, pn)
    conflicts = []
    for p in parts:
        existing_bb = part_aabb(p["x"], p["y"], p["z"], p["rotation"], p["part_number"])
        if aabbs_overlap(proposed_bb, existing_bb):
            conflicts.append(
                {
                    "id": p["id"],
                    "part_number": p["part_number"],
                    "x": p["x"],
                    "y": p["y"],
                    "z": p["z"],
                }
            )

    if conflicts:
        return ok(
            {"valid": False, "conflict_count": len(conflicts), "conflicts": conflicts},
            f"Placement invalid: {len(conflicts)} conflict(s)",
        )
    return ok(
        {"valid": True, "conflict_count": 0, "conflicts": []}, "Placement is valid"
    )


@mcp.tool
def snap_to_grid(part_id: str, submodel: str = "") -> list | dict | Image:
    """Snap a part to the nearest standard stud-grid position.

    Rounds X and Z to the nearest multiple of 20 LDU (one stud width) and
    Y to the nearest multiple of 8 LDU (one plate height).  Useful after
    free-form move_part() calls to re-align bricks with the LEGO grid.

    Args:
        part_id: Session UUID of the part to snap.
        submodel: Leave empty for root.

    Returns:
        Updated part dict with snapped coordinates plus
        {"delta": {"dx": ..., "dy": ..., "dz": ...}}.
    """
    try:
        project = get_model()
    except RuntimeError as e:
        return err(str(e), "NO_MODEL")

    try:
        part_line = project.get_part(part_id, submodel or None)
    except KeyError as e:
        return err(str(e), "SUBMODEL_NOT_FOUND")

    if part_line is None:
        return err(f"Part '{part_id}' not found", "PART_NOT_FOUND")

    def _snap(v: float, grid: float) -> float:
        return round(v / grid) * grid

    old_x, old_y, old_z = part_line.x, part_line.y, part_line.z
    new_x = _snap(old_x, _STUD)
    new_y = _snap(old_y, _PLATE)
    new_z = _snap(old_z, _STUD)

    delta = {"dx": new_x - old_x, "dy": new_y - old_y, "dz": new_z - old_z}

    if new_x == old_x and new_y == old_y and new_z == old_z:
        part_dict = project._part_as_dict(part_id, submodel or None)
        return ok({**part_dict, "delta": delta}, "Part already on grid")

    project.move_part(part_id, new_x, new_y, new_z, submodel or None)
    part_dict = project._part_as_dict(part_id, submodel or None)
    conflicts = placement_warnings(project, part_id, submodel or None)
    snapped = {**part_dict, "delta": delta}
    if conflicts:
        snapped["overlap_warnings"] = conflicts
    return ok_with_render(
        project,
        snapped,
        f"Snapped ({old_x},{old_y},{old_z}) -> ({new_x},{new_y},{new_z})",
    )
