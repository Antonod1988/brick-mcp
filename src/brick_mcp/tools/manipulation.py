"""Manipulation tools: add, remove, move, rotate, recolor parts and steps."""

from __future__ import annotations

from fastmcp.utilities.types import Image

from brick_mcp._helpers import err, ok, ok_with_render, placement_warnings
from brick_mcp.model import get_model
from brick_mcp.server import mcp


@mcp.tool
def add_part(
    part_number: str,
    color: int,
    x: float = 0.0,
    y: float = 0.0,
    z: float = 0.0,
    rotation_matrix: list[float] | None = None,
    submodel: str = "",
) -> list | dict | Image:
    """Add a part to the model.

    Args:
        part_number: LDraw part number, e.g. "3001" or "3001.dat" (.dat optional).
                     Use search_parts() to find part numbers.
        color: LDraw color code, e.g. 4 for Red. Use list_colors() to find codes.
        x: X position in LDU (20 LDU = 1 stud width).
        y: Y position in LDU (Y-axis inverted: -24 is one brick above y=0).
        z: Z position in LDU.
        rotation_matrix: 9 floats [a,b,c, d,e,f, g,h,i] row-major 3x3.
                         Defaults to identity (no rotation).
        submodel: Name of submodel to add to. Leave empty for root.

    Returns:
        Dict with the new part's id and full part info (part_number, color, x, y, z).
    """
    try:
        project = get_model()
    except RuntimeError as e:
        return err(str(e), "NO_MODEL")

    if rotation_matrix is not None and len(rotation_matrix) != 9:
        return err("rotation_matrix must have exactly 9 values", "INVALID_MATRIX")

    matrix = tuple(rotation_matrix) if rotation_matrix is not None else None

    try:
        pid = project.add_part(submodel or None, part_number, color, x, y, z, matrix)
    except KeyError as e:
        return err(str(e), "SUBMODEL_NOT_FOUND")
    except ValueError as e:
        return err(str(e), "INVALID_VALUE")

    part_dict = project._part_as_dict(pid, submodel or None)
    conflicts = placement_warnings(project, pid, submodel or None)
    if conflicts:
        part_dict = {**part_dict, "overlap_warnings": conflicts}
    return ok_with_render(project, part_dict, f"Added {part_number} (id={pid})")


@mcp.tool
def remove_part(part_id: str, submodel: str = "") -> list | dict | Image:
    """Remove a part from the model by its session UUID.

    Args:
        part_id: Session UUID returned by add_part or list_parts.
        submodel: Name of submodel. Leave empty for root.

    Returns:
        {"removed": true, "part_id": "..."} or an error if not found.
    """
    try:
        project = get_model()
    except RuntimeError as e:
        return err(str(e), "NO_MODEL")

    try:
        removed = project.remove_part(part_id, submodel or None)
    except KeyError as e:
        return err(str(e), "SUBMODEL_NOT_FOUND")

    if not removed:
        return err(f"Part '{part_id}' not found", "PART_NOT_FOUND")
    return ok_with_render(project, {"removed": True, "part_id": part_id})


@mcp.tool
def move_part(
    part_id: str,
    x: float,
    y: float,
    z: float,
    submodel: str = "",
) -> list | dict | Image:
    """Move a part to new absolute coordinates.

    Args:
        part_id: Session UUID of the part to move.
        x: New X position in LDU.
        y: New Y position in LDU (inverted: -24 is one brick above y=0).
        z: New Z position in LDU.
        submodel: Name of submodel. Leave empty for root.

    Returns:
        Updated part dict with new coordinates.
    """
    try:
        project = get_model()
    except RuntimeError as e:
        return err(str(e), "NO_MODEL")

    try:
        moved = project.move_part(part_id, x, y, z, submodel or None)
    except KeyError as e:
        return err(str(e), "SUBMODEL_NOT_FOUND")

    if not moved:
        return err(f"Part '{part_id}' not found", "PART_NOT_FOUND")
    part_dict = project._part_as_dict(part_id, submodel or None)
    conflicts = placement_warnings(project, part_id, submodel or None)
    if conflicts:
        part_dict = {**part_dict, "overlap_warnings": conflicts}
    return ok_with_render(project, part_dict)


@mcp.tool
def rotate_part(
    part_id: str,
    rotation_matrix: list[float],
    submodel: str = "",
) -> list | dict | Image:
    """Change a part's rotation.

    Args:
        part_id: Session UUID of the part to rotate.
        rotation_matrix: 9 floats [a,b,c, d,e,f, g,h,i] row-major 3x3.
            Common values:
              Identity (no rotation): [1,0,0, 0,1,0, 0,0,1]
              90° around Y:           [0,0,-1, 0,1,0, 1,0,0]
              180° around Y:          [-1,0,0, 0,1,0, 0,0,-1]
              270° around Y:          [0,0,1, 0,1,0, -1,0,0]
        submodel: Name of submodel. Leave empty for root.

    Returns:
        Updated part dict with new rotation.
    """
    try:
        project = get_model()
    except RuntimeError as e:
        return err(str(e), "NO_MODEL")

    if len(rotation_matrix) != 9:
        return err("rotation_matrix must have exactly 9 values", "INVALID_MATRIX")

    try:
        rotated = project.rotate_part(part_id, tuple(rotation_matrix), submodel or None)
    except KeyError as e:
        return err(str(e), "SUBMODEL_NOT_FOUND")

    if not rotated:
        return err(f"Part '{part_id}' not found", "PART_NOT_FOUND")
    part_dict = project._part_as_dict(part_id, submodel or None)
    conflicts = placement_warnings(project, part_id, submodel or None)
    if conflicts:
        part_dict = {**part_dict, "overlap_warnings": conflicts}
    return ok_with_render(project, part_dict)


@mcp.tool
def change_color(part_id: str, color: int, submodel: str = "") -> list | dict | Image:
    """Change a part's color.

    Args:
        part_id: Session UUID of the part.
        color: LDraw color code. Use list_colors() to find available codes.
        submodel: Name of submodel. Leave empty for root.

    Returns:
        Updated part dict with new color.
    """
    try:
        project = get_model()
    except RuntimeError as e:
        return err(str(e), "NO_MODEL")

    try:
        changed = project.change_color(part_id, color, submodel or None)
    except KeyError as e:
        return err(str(e), "SUBMODEL_NOT_FOUND")

    if not changed:
        return err(f"Part '{part_id}' not found", "PART_NOT_FOUND")
    part_dict = project._part_as_dict(part_id, submodel or None)
    return ok_with_render(project, part_dict)


@mcp.tool
def add_step(submodel: str = "") -> list | dict | Image:
    """Append a STEP marker at the end of the current submodel.

    STEP markers define building instruction steps. Parts before a STEP belong
    to that step; parts after it belong to the next step.

    Args:
        submodel: Name of submodel. Leave empty for root.

    Returns:
        {"step_count": N} with the new total number of step boundaries.
    """
    try:
        project = get_model()
    except RuntimeError as e:
        return err(str(e), "NO_MODEL")

    try:
        count = project.add_step(submodel or None)
    except KeyError as e:
        return err(str(e), "SUBMODEL_NOT_FOUND")

    return ok_with_render(project, {"step_count": count})


@mcp.tool
def remove_step(step_index: int, submodel: str = "") -> list | dict | Image:
    """Remove a STEP boundary by its 0-based index.

    Parts from the removed step merge into the previous step.

    Args:
        step_index: 0-based index of the STEP marker to remove.
        submodel: Name of submodel. Leave empty for root.

    Returns:
        {"removed_step_index": N, "step_count": M} or an error if not found.
    """
    try:
        project = get_model()
    except RuntimeError as e:
        return err(str(e), "NO_MODEL")

    try:
        removed = project.remove_step(step_index, submodel or None)
    except KeyError as e:
        return err(str(e), "SUBMODEL_NOT_FOUND")

    if not removed:
        return err(f"Step index {step_index} out of range", "STEP_NOT_FOUND")

    from brick_mcp.model import StudioProject as _SP

    sd = project._submodel(submodel or None)
    remaining = _SP._count_steps(sd)
    return ok_with_render(
        project, {"removed_step_index": step_index, "step_count": remaining}
    )
