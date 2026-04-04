"""Inspection tools: list parts, bill of materials, building steps."""

from __future__ import annotations

from brick_mcp._helpers import err, ok
from brick_mcp.model import get_model
from brick_mcp.server import mcp


@mcp.tool
def list_parts(submodel: str = "") -> dict:
    """List all part instances in the model (or a named submodel).

    Args:
        submodel: Name of the submodel to inspect. Leave empty for the root model.

    Returns:
        List of part dicts, each with:
        - id: session UUID (use this with move_part, rotate_part, etc.)
        - part_number: LDraw part filename (e.g. "3001.dat")
        - color: LDraw color code
        - color_name: Human-readable color name
        - x, y, z: Position in LDU (y-axis inverted: -y is up)
        - rotation: 9-element row-major 3x3 rotation matrix
    """
    try:
        project = get_model()
    except RuntimeError as e:
        return err(str(e), "NO_MODEL")

    try:
        parts = project.list_parts(submodel or None)
    except KeyError as e:
        return err(str(e), "SUBMODEL_NOT_FOUND")

    return ok(parts)


@mcp.tool
def get_bom(submodel: str = "") -> dict:
    """Return a bill of materials grouped by part number and color.

    Args:
        submodel: Name of the submodel. Leave empty for the root model.

    Returns:
        Dict mapping part_number → {color_code_str → count}.
        Example: {"3001.dat": {"4": 3, "1": 2}, "3003.dat": {"15": 1}}
    """
    try:
        project = get_model()
    except RuntimeError as e:
        return err(str(e), "NO_MODEL")

    try:
        bom = project.get_bom(submodel or None)
    except KeyError as e:
        return err(str(e), "SUBMODEL_NOT_FOUND")

    return ok(bom)


@mcp.tool
def get_steps(submodel: str = "") -> dict:
    """Return building step information for the model.

    Args:
        submodel: Name of the submodel. Leave empty for the root model.

    Returns:
        List of step dicts, each with:
        - step_index: 0-based index
        - parts_in_step: number of parts added in this step
        - cumulative_parts: total parts placed up to and including this step

        A model with no STEP markers returns a single implicit step containing all parts.
        Use add_step() to create new step boundaries.
    """
    try:
        project = get_model()
    except RuntimeError as e:
        return err(str(e), "NO_MODEL")

    try:
        steps = project.get_steps(submodel or None)
    except KeyError as e:
        return err(str(e), "SUBMODEL_NOT_FOUND")

    return ok(steps)
