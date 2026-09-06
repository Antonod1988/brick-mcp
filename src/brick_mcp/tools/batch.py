"""Batch tool — execute multiple tool calls in a single MCP round-trip.

Runs a list of ``{"tool": "<name>", "args": {...}}`` calls sequentially,
collects every result, and returns them all together with a single optional
PNG render at the end.  This is the preferred way to build a model because it
avoids the overhead of one MCP call per operation.
"""

from __future__ import annotations

from typing import Any

from fastmcp.utilities.types import Image

from brick_mcp._helpers import err, ok, ok_with_render, try_render
from brick_mcp.model import get_model
from brick_mcp.server import mcp


def _dispatch_table() -> dict[str, Any]:
    """Build the tool-name → callable mapping (lazy imports break circular deps)."""
    from brick_mcp.tools.file_ops import (
        get_model_info,
        new_model,
        open_model,
        save_model,
    )
    from brick_mcp.tools.inspection import get_bom, get_steps, list_parts
    from brick_mcp.tools.layout import check_overlaps, snap_to_grid, validate_placement
    from brick_mcp.tools.manipulation import (
        add_part,
        add_step,
        change_color,
        move_part,
        remove_part,
        remove_step,
        rotate_part,
    )
    from brick_mcp.tools.parts import (
        get_color_info,
        get_part_details,
        get_part_footprint,
        list_colors,
        search_parts,
    )
    from brick_mcp.tools.render import render_model

    return {
        # File operations
        "new_model": new_model,
        "open_model": open_model,
        "save_model": save_model,
        "get_model_info": get_model_info,
        # Inspection
        "list_parts": list_parts,
        "get_bom": get_bom,
        "get_steps": get_steps,
        # Manipulation
        "add_part": add_part,
        "remove_part": remove_part,
        "move_part": move_part,
        "rotate_part": rotate_part,
        "change_color": change_color,
        "add_step": add_step,
        "remove_step": remove_step,
        # Layout / collision
        "check_overlaps": check_overlaps,
        "validate_placement": validate_placement,
        "snap_to_grid": snap_to_grid,
        # Parts / colors
        "search_parts": search_parts,
        "get_part_details": get_part_details,
        "get_part_footprint": get_part_footprint,
        "list_colors": list_colors,
        "get_color_info": get_color_info,
        # Render (explicit on-demand call; auto-render is handled at the end)
        "render_model": render_model,
    }


def _strip_images(result: Any) -> dict:
    """Extract the dict part of a tool result, discarding any embedded Images."""
    if isinstance(result, list):
        for item in result:
            if isinstance(item, dict):
                return item
        return {"ok": True}
    return result  # type: ignore[return-value]


@mcp.tool(output_schema=None)
def batch(calls: list[dict], atomic: bool = True) -> list | dict | Image:
    """Run memory edits sequentially with one preview. Default atomic=True
    stops at the first error and restores the entire model. Disk writes and
    explicit renders are forbidden in atomic batches; save after success.
    atomic=False preserves legacy best-effort execution without rollback.
    """
    from brick_mcp.model import set_model
    from brick_mcp._helpers import suppress_render

    if not isinstance(calls, list) or len(calls) > 1000:
        return err("calls must be a list of at most 1000 operations", "INVALID_INPUT")
    try:
        original = get_model()
        before = original.snapshot()
    except RuntimeError:
        original, before = None, None
    dispatch, results = _dispatch_table(), []
    with suppress_render():
        for i, call in enumerate(calls):
            try:
                if not isinstance(call, dict):
                    raise ValueError("Expected a {tool, args} object")
                name = call.get("tool")
                if not name:
                    result = err(f"Call #{i}: missing tool", "MISSING_TOOL")
                elif name not in dispatch:
                    result = err(f"Unknown tool: {name}", "UNKNOWN_TOOL")
                elif atomic and name in ("save_model", "render_model"):
                    result = err(
                        "Save/render separately after an atomic batch",
                        "EXTERNAL_EFFECT_IN_BATCH",
                    )
                else:
                    args = call.get("args") or {}
                    result = _strip_images(dispatch[name](**args))
                    if not isinstance(result, dict):
                        result = ok(
                            message="Non-text result omitted from batch summary"
                        )
            except TypeError as exc:
                result = err(str(exc), "BAD_ARGS")
            except Exception as exc:
                result = err(str(exc), "INVALID_CALL")
            results.append(result)
            if atomic and not result.get("ok", False):
                if original is not None:
                    original.restore(before)
                set_model(original)
                break
    errors = sum(not r.get("ok", False) for r in results)
    rolled_back = atomic and bool(errors)
    if atomic and not errors and before is not None:
        get_model().remember(before)
    summary = ok(
        dict(
            results=results,
            executed=len(results),
            error_count=errors,
            rolled_back=rolled_back,
        ),
        f"Batch: {len(results)} call(s), {errors} error(s)",
    )
    summary["ok"] = not errors
    try:
        img = try_render(get_model()) if not rolled_back else None
    except RuntimeError:
        img = None
    return [summary, img] if img is not None else summary
