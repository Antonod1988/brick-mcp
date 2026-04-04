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


@mcp.tool
def batch(calls: list[dict]) -> list | dict | Image:
    """Execute multiple tool calls in a single round-trip.

    Runs each call sequentially.  The state changes from each call (e.g. a part
    added by ``add_part``) are immediately visible to the next call in the list.
    A single optional PNG render is appended at the end when ldview is available,
    instead of one render per mutation.

    Args:
        calls: List of ``{"tool": "<name>", "args": {...}}`` dicts.
               ``"args"`` may be omitted for tools that take no arguments.

    Returns:
        ``{"ok": bool, "results": [...], "executed": N, "error_count": N}``
        followed optionally by a PNG ``Image`` when ldview is available.

        Each entry in ``results`` is the dict response from the corresponding
        call.  The ``"ok"`` top-level key reflects whether ALL calls succeeded;
        individual errors do not halt execution — all calls run regardless.

    Example::

        batch(calls=[
            {"tool": "new_model", "args": {"name": "tower"}},
            {"tool": "add_part",  "args": {"part_number": "3001", "color": 4,
                                           "x": 0, "y": 0, "z": 0}},
            {"tool": "add_part",  "args": {"part_number": "3001", "color": 4,
                                           "x": 0, "y": -24, "z": 0}},
            {"tool": "add_step"},
            {"tool": "save_model", "args": {"path": "/tmp/tower.ldr"}},
        ])
    """
    if not isinstance(calls, list):
        return err("'calls' must be a list of {tool, args} dicts", "INVALID_INPUT")

    dispatch = _dispatch_table()
    results = []
    error_count = 0

    for i, call in enumerate(calls):
        if not isinstance(call, dict):
            entry = err(
                f"Call #{i}: expected a dict, got {type(call).__name__}", "INVALID_CALL"
            )
            results.append(entry)
            error_count += 1
            continue

        tool_name = call.get("tool")
        if not tool_name:
            entry = err(f"Call #{i}: missing 'tool' key", "MISSING_TOOL")
            results.append(entry)
            error_count += 1
            continue

        fn = dispatch.get(tool_name)
        if fn is None:
            entry = err(
                f"Call #{i}: unknown tool '{tool_name}'. "
                f"Available: {sorted(dispatch.keys())}",
                "UNKNOWN_TOOL",
            )
            results.append(entry)
            error_count += 1
            continue

        args: dict = call.get("args") or {}
        try:
            raw = fn(**args)
        except TypeError as exc:
            entry = err(f"Call #{i} ({tool_name}): bad arguments — {exc}", "BAD_ARGS")
            results.append(entry)
            error_count += 1
            continue
        except Exception as exc:
            entry = err(f"Call #{i} ({tool_name}): {exc}", "TOOL_ERROR")
            results.append(entry)
            error_count += 1
            continue

        result_dict = _strip_images(raw)
        results.append(result_dict)
        if not result_dict.get("ok", True):
            error_count += 1

    all_ok = error_count == 0
    summary = ok(
        {
            "results": results,
            "executed": len(calls),
            "error_count": error_count,
        },
        f"Batch: {len(calls)} call(s), {error_count} error(s)",
    )
    summary["ok"] = all_ok

    # Append a single render if the model exists and ldview is available
    try:
        project = get_model()
        img = try_render(project)
    except RuntimeError:
        img = None

    if img is not None:
        return [summary, img]
    return summary
