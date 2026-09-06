"""File operation tools: open, save, create, and inspect models."""

from __future__ import annotations

import os
import tempfile
import json

from fastmcp.utilities.types import Image

from brick_mcp import io_file, ldraw
from brick_mcp._helpers import err, ok, ok_with_render
from brick_mcp.model import StudioProject, get_model, set_model
from brick_mcp.server import mcp


@mcp.tool
def new_model(name: str = "model") -> list | dict | Image:
    """Create a new, empty LEGO model in memory.

    Args:
        name: Base name for the root submodel (e.g. "my_castle").
              The .ldr suffix is added automatically if absent.

    Returns:
        Model info: root_submodel name, submodels list, total_part_count.
    """
    try:
        project = StudioProject.new(name)
    except (ValueError, TypeError) as exc:
        return err(str(exc), "INVALID_NAME")
    set_model(project)
    return ok_with_render(
        project, project.info(), f"Created new model '{project.root_submodel}'"
    )


@mcp.tool
def open_model(path: str) -> list | dict | Image:
    """Open a BrickLink Studio .io file or plain LDraw .ldr / .mpd file.

    Parses the file, assigns session UUIDs to all parts, and loads it as the
    active model. Part IDs reset on each call.

    Args:
        path: Absolute or relative path to a .io, .ldr, or .mpd file.

    Returns:
        Model info on success, or an error dict.
    """
    path = os.path.abspath(path)
    if not os.path.exists(path):
        return err(f"File not found: {path}", "FILE_NOT_FOUND")

    ldr_text: str
    raw_entries: dict[str, bytes] = {}

    ext = os.path.splitext(path)[1].lower()
    if ext == ".io":
        try:
            model_bytes, raw_entries = io_file.read_io_file(path)
            ldr_text = model_bytes.decode("utf-8", errors="replace")
        except Exception as e:
            return err(f"Failed to open .io file: {e}", "IO_READ_ERROR")
    elif ext in (".ldr", ".mpd", ".dat"):
        try:
            with open(path, encoding="utf-8", errors="replace") as f:
                ldr_text = f.read()
        except OSError as e:
            return err(f"Failed to read file: {e}", "READ_ERROR")
    else:
        return err(
            f"Unsupported file extension '{ext}'. Expected .io, .ldr, or .mpd.",
            "UNSUPPORTED_FORMAT",
        )

    try:
        blocks = ldraw.parse_ldraw(ldr_text)
    except Exception as e:
        return err(f"Failed to parse LDraw data: {e}", "PARSE_ERROR")

    project = StudioProject.from_blocks(path, blocks, raw_entries)
    try:
        project.flatten()
    except (ValueError, KeyError) as e:
        return err(str(e), "INVALID_MODEL")
    set_model(project)
    return ok_with_render(project, project.info(), f"Opened {os.path.basename(path)}")


@mcp.tool
def save_model(path: str = "") -> list | dict | Image:
    """Save the active model to disk.

    Args:
        path: Destination path. If empty, saves back to the original source_path.
              Use a .io extension for BrickLink Studio format (encrypted ZIP).
              Use a .ldr extension for plain LDraw text.

    Returns:
        Success message with the saved path, or an error dict.
    """
    try:
        project = get_model()
    except RuntimeError as e:
        return err(str(e), "NO_MODEL")

    save_path = path.strip() if path.strip() else (project.source_path or "")
    if not save_path:
        return err(
            "No path specified and model has no source path. "
            "Pass an explicit path to save_model().",
            "NO_PATH",
        )

    save_path = os.path.abspath(save_path)
    ldr_text = project.to_ldraw_text()
    ext = os.path.splitext(save_path)[1].lower()

    temporary = None
    try:
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        fd, temporary = tempfile.mkstemp(
            prefix=".brick-mcp-", dir=os.path.dirname(save_path)
        )
        os.close(fd)
        if ext == ".io":
            v2_text = project.to_v2_ldraw_text()
            extras = dict(project.raw_zip_entries)
            info = json.loads(extras.get(".info", b"{}"))
            info["total_parts"] = len(project.flatten())
            extras[".info"] = json.dumps(info).encode("utf8")
            io_file.write_io_file(temporary, ldr_text, extras, v2_text)
        elif ext in (".ldr", ".mpd", ".dat"):
            with open(temporary, "w", encoding="utf-8") as f:
                f.write(ldr_text)
        else:
            raise ValueError("Use .io, .ldr or .mpd for saved models")
        os.replace(temporary, save_path)
    except Exception as e:
        return err(f"Failed to save: {e}", "SAVE_ERROR")
    finally:
        if temporary and os.path.exists(temporary):
            os.unlink(temporary)

    project.source_path = save_path
    project._dirty = False
    return ok_with_render(project, message=f"Saved to {save_path}")


@mcp.tool
def get_model_info() -> dict:
    """Return metadata about the currently loaded model.

    Returns:
        Dict with: source_path, filename, root_submodel, submodels (list),
        total_part_count, is_dirty.
    """
    try:
        project = get_model()
    except RuntimeError as e:
        return err(str(e), "NO_MODEL")

    return ok(project.info())
