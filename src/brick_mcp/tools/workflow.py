"""Instruction-first, transactional construction and subassembly tools."""

from copy import deepcopy

from fastmcp.utilities.types import Image

from brick_mcp._helpers import err, ok
from brick_mcp.instructions import (
    clean_name,
    describe_steps,
    edit,
    groups,
    write_groups,
)
from brick_mcp.ldraw import PartLine
from brick_mcp.model import _SubmodelData, get_model
from brick_mcp.server import mcp
from brick_mcp.validation import validate_project, validate_sequence, summary


def _accepted(report, allow_unverified):
    return report["status"] == "passed" or (
        allow_unverified and report["status"] == "unverified"
    )


def _images(project, submodel, step_index, width=800, height=600):
    from brick_mcp.rendering import render_step_views

    parts = project.flatten(submodel, step_index)
    frame = project.flatten(submodel)
    old = {p["id"] for p in parts if p["step_index"] < step_index}
    return render_step_views(parts, old, frame, width, height)


@mcp.tool(output_schema=None)
def apply_step(
    name: str,
    parts: list[dict],
    submodel: str = "",
    insert_at: int = -1,
    allow_unverified: bool = False,
    preview: bool = True,
    save_path: str = "",
) -> list | dict:
    """Add ONE named construction step; validate, preview, save, or roll everything back.

    parts: add_part arguments (part_number, color, x/y/z in LDU, rotation_matrix).
    A part_number may also be an existing submodel name, e.g. 'Roof.ldr'.
    insert_at is zero-based, -1 appends. Ordinary vertical stud connections and
    insertion from above are checked. Unsupported connectors require explicit
    allow_unverified=True and remain labelled unverified. A render/save failure
    also rolls back. Returns state and highlighted PNGs when preview=True.
    """
    project, before = None, None
    try:
        project = get_model()
        before = project.snapshot()
        name = clean_name(name)
        if not parts or len(parts) > 500:
            raise ValueError("A step must contain 1–500 placements")
        sd = project._submodel(submodel)
        steps = groups(sd)
        if (
            len(steps) == 1
            and not any(isinstance(c, PartLine) for c in steps[0]["commands"])
            and not steps[0]["name"]
        ):
            steps = []
        index = len(steps) if insert_at == -1 else insert_at
        if not 0 <= index <= len(steps):
            raise ValueError("Step index out of range")
        if index < len(steps) and not any(
            isinstance(c, PartLine) for c in steps[index]["commands"]
        ):
            steps.pop(index)  # Fill an explicitly inserted empty step.
        old_ids = set(sd._parts)
        for p in parts:
            if not isinstance(p, dict) or set(p) - {
                "part_number",
                "color",
                "x",
                "y",
                "z",
                "rotation_matrix",
            }:
                raise ValueError("Unknown placement arguments")
            from brick_mcp.colors import get_color

            if get_color(p["color"]) is None and p["color"] != 16:
                raise ValueError(f"Unknown color: {p['color']}")
            if p["part_number"] in project.submodels:
                child = validate_project(project, p["part_number"])
                if (
                    not _accepted(child, allow_unverified)
                    or len(child["components"]) != 1
                ):
                    raise ValueError(
                        f"Submodel must be connected before installation: {p['part_number']}"
                    )
            project.add_part(
                submodel or None,
                p["part_number"],
                p["color"],
                p.get("x", 0),
                p.get("y", 0),
                p.get("z", 0),
                p.get("rotation_matrix"),
            )
        added = [
            c for c in sd.commands if isinstance(c, PartLine) and c._id not in old_ids
        ]
        steps.insert(index, {"name": name, "commands": added})
        write_groups(sd, steps)
        reports = validate_sequence(project, submodel)
        bad = [r for r in reports if not _accepted(r, allow_unverified)]
        if bad:
            project.restore(before)
            result = err("Step rejected; model unchanged", "STEP_VALIDATION_FAILED")
            result["validation"] = bad
            result["rolled_back"] = True
            return result
        images = _images(project, submodel, index) if preview else []
        if save_path:
            from brick_mcp.tools.file_ops import save_model
            from brick_mcp._helpers import suppress_render

            with suppress_render():
                saved = save_model(save_path)
            if not saved["ok"]:
                raise ValueError(saved["error"]["message"])
        project.remember(before)
        data = {
            "step": describe_steps(sd)[index],
            "validation": summary(next(r for r in reports if r["step_index"] == index)),
            "preview_paths": [str(p) for p in images],
            "saved_path": save_path or None,
        }
        result = ok(data, f"Committed step {index + 1}: {name}")
        return [result, *[Image(path=str(p)) for p in images]] if images else result
    except Exception as exc:
        if project is not None and before is not None:
            project.restore(before)
        result = err(str(exc), "STEP_FAILED")
        result["rolled_back"] = before is not None
        return result


@mcp.tool
def edit_step(
    action: str,
    step_index: int,
    submodel: str = "",
    name: str = "",
    target_index: int | None = None,
    part_ids: list[str] | None = None,
    allow_unverified: bool = False,
) -> dict:
    """Edit steps transactionally. Actions: insert, rename, reorder, split,
    move_parts, merge_next, delete_empty. Indexes are zero-based. Split takes
    part_ids and name; move_parts takes part_ids and target_index. Reordered
    instructions are revalidated; failure restores the previous sequence.
    """
    project, before = None, None
    try:
        project = get_model()
        before = project.snapshot()
        result = edit(
            project, action, step_index, submodel, name, target_index, part_ids
        )
        reports = validate_sequence(project, submodel)
        if any(not _accepted(r, allow_unverified) for r in reports):
            project.restore(before)
            return {
                **err(
                    "Edited sequence is not buildable; restored",
                    "STEP_VALIDATION_FAILED",
                ),
                "validation": reports,
                "rolled_back": True,
            }
        project.remember(before)
        return ok({"steps": result, "validation": [summary(r) for r in reports]})
    except Exception as exc:
        if before is not None:
            project.restore(before)
        return err(str(exc), "EDIT_STEP_FAILED")


@mcp.tool
def create_submodel(
    name: str, part_ids: list[str] | None = None, parent: str = ""
) -> dict:
    """Create an empty named assembly, or group selected parent parts in-place.

    A grouped assembly keeps the original coordinates and steps; its parent
    reference has identity transform. Use apply_step(part_number='Name.ldr',...)
    to install an assembly built separately. Cycles and mixed step grouping are rejected.
    """
    project, before = None, None
    try:
        project = get_model()
        before = project.snapshot()
        name = clean_name(name)
        if any(c in name for c in "/\\:"):
            raise ValueError("Submodel name must be a filename, not a path")
        if not name.lower().endswith(".ldr"):
            name += ".ldr"
        if name.casefold() in {n.casefold() for n in project.submodels}:
            raise ValueError("Submodel name already exists")
        child = _SubmodelData(name)
        project.submodels[name] = child
        if part_ids:
            sd = project._submodel(parent)
            ids = set(part_ids)
            if len(ids) != len(part_ids) or not ids <= sd._parts.keys():
                raise ValueError("part_ids must be unique existing parent parts")
            steps = groups(sd)
            selected_steps = [
                i
                for i, g in enumerate(steps)
                if any(isinstance(c, PartLine) and c._id in ids for c in g["commands"])
            ]
            if len(selected_steps) != 1:
                raise ValueError(
                    "Group parts from one parent step; build separate submodels for multi-step assemblies"
                )
            index = selected_steps[0]
            selected = [
                deepcopy(c)
                for c in steps[index]["commands"]
                if isinstance(c, PartLine) and c._id in ids
            ]
            write_groups(child, [{"name": name[:-4], "commands": selected}])
            steps[index]["commands"] = [
                c
                for c in steps[index]["commands"]
                if not (isinstance(c, PartLine) and c._id in ids)
            ]
            reference_id = project.add_part(parent or None, name, 16, 0, 0, 0)
            steps[index]["commands"].append(sd._find_part(reference_id))
            write_groups(sd, steps)
        project.flatten()
        project._dirty = True
        project.remember(before)
        return ok({"submodel": name, "steps": project.get_steps(name)})
    except Exception as exc:
        if before is not None:
            project.restore(before)
        return err(str(exc), "SUBMODEL_FAILED")


@mcp.tool
def undo_last_edit() -> dict:
    """Restore the last successful apply_step/edit_step/create_submodel/atomic batch (up to 20). Disk files are not reverted."""
    try:
        project = get_model()
        if not project._undo:
            return err("No saved edit to undo", "NO_UNDO")
        project.restore(project._undo.pop())
        project._dirty = True
        return ok(project.info(), "Restored previous in-memory model; save when ready")
    except Exception as exc:
        return err(str(exc))


@mcp.tool
def validate_build(
    submodel: str = "", all_steps: bool = True, details: bool = False
) -> dict:
    """Check connections, floating parts, collisions and insertion access. Unsupported geometry is explicitly unverified."""
    try:
        project = get_model()
        reports = (
            validate_sequence(project, submodel)
            if all_steps
            else [validate_project(project, submodel)]
        )
        status = (
            "failed"
            if any(r["status"] == "failed" for r in reports)
            else (
                "unverified"
                if any(r["status"] == "unverified" for r in reports)
                else "passed"
            )
        )
        return ok(
            {
                "status": status,
                "steps": reports if details else [summary(r) for r in reports],
            }
        )
    except Exception as exc:
        return err(str(exc), "VALIDATION_FAILED")


@mcp.tool(output_schema=None)
def render_step(
    step_index: int, submodel: str = "", width: int = 800, height: int = 600
) -> list | dict:
    """Return two real-geometry PNGs: accumulated model and new parts highlighted against gray previous parts."""
    try:
        project = get_model()
        if not 0 <= step_index < len(project.get_steps(submodel)):
            raise ValueError("Step index out of range")
        paths = _images(project, submodel, step_index, width, height)
        return [
            ok(
                {
                    "paths": [str(p) for p in paths],
                    "step": project.get_steps(submodel)[step_index],
                }
            ),
            *[Image(path=str(p)) for p in paths],
        ]
    except Exception as exc:
        return err(str(exc), "RENDER_FAILED")


@mcp.tool
def export_instructions(
    directory: str, previews: bool = True, allow_unverified: bool = False
) -> dict:
    """Export native Studio IO, MPD, step/BOM manifest and an illustrated HTML booklet.

    Includes each subassembly's own steps and native STUDIOSTEPDESC names. Does
    not control or refresh Studio. The destination must be new or empty.
    """
    import html
    import json
    import shutil
    from pathlib import Path
    from brick_mcp.rendering import render_parts
    from brick_mcp.tools.file_ops import save_model
    from brick_mcp._helpers import suppress_render

    try:
        project = get_model()
        target = Path(directory).expanduser().resolve()
        if target.exists() and any(target.iterdir()):
            raise ValueError("Choose a new or empty export directory")
        reports = {name: validate_sequence(project, name) for name in project.submodels}
        if any(
            not _accepted(r, allow_unverified) for rs in reports.values() for r in rs
        ):
            return {
                **err(
                    "Instructions contain invalid/unverified steps",
                    "EXPORT_VALIDATION_FAILED",
                ),
                "validation": reports,
            }
        target.mkdir(parents=True, exist_ok=True)
        ordered, visited = [], set()

        def order(name):
            if name in visited:
                return
            visited.add(name)
            for p in project.list_parts(name):
                if p["part_number"] in project.submodels:
                    order(p["part_number"])
            ordered.append(name)

        order(project.root_submodel)
        manifest = {
            "title": project.root_submodel,
            "bom": project.get_bom(None),
            "assemblies": [],
        }
        page = [
            '<!doctype html><meta charset="utf-8"><title>LEGO assembly instructions</title><style>body{font:16px system-ui;max-width:1000px;margin:40px auto;color:#20242a}section{break-inside:avoid;border-bottom:1px solid #ddd;padding:16px}img{width:100%;max-width:700px}h2{break-before:page}li{margin:4px} @media print{body{margin:0}}</style>',
            "<h1>" + html.escape(project.root_submodel.rsplit(".", 1)[0]) + "</h1>",
        ]
        for a, name in enumerate(ordered):
            assembly = {
                "name": name,
                "steps": project.get_steps(name),
                "validation": reports[name],
            }
            manifest["assemblies"].append(assembly)
            page.append("<h2>" + html.escape(name.rsplit(".", 1)[0]) + "</h2>")
            for step in assembly["steps"]:
                if not step["parts_in_step"]:
                    continue
                index = step["step_index"]
                step_parts = [
                    p for p in project.list_parts(name) if p["id"] in step["part_ids"]
                ]
                step["parts"] = step_parts
                page.append(
                    f'<section><h3>{index+1}. {html.escape(step["name"] or "Assembly step")}</h3>'
                )
                if previews:
                    leaves = project.flatten(name, index)
                    old = {p["id"] for p in leaves if p["step_index"] < index}
                    png = render_parts(
                        leaves,
                        800,
                        600,
                        muted_ids=old,
                        frame_parts=project.flatten(name),
                    )
                    image_name = f"assembly-{a+1}-step-{index+1}.png"
                    shutil.copyfile(png, target / image_name)
                    step["image"] = image_name
                    page.append(f'<img src="{image_name}" alt="Step {index+1}">')
                quantities = {}
                for p in step_parts:
                    key = (p["part_number"], p["color"])
                    quantities[key] = quantities.get(key, 0) + 1
                from brick_mcp.catalog import get_part_info
                from brick_mcp.colors import get_color

                labels = {}
                for pn, color in quantities:
                    if pn in project.submodels:
                        labels[pn, color] = pn.rsplit(".", 1)[0]
                    else:
                        info = get_part_info(pn)
                        color_name = (
                            (get_color(color) or {})
                            .get("name", str(color))
                            .replace("_", " ")
                        )
                        labels[pn, color] = (
                            f"{info['name'] if info else pn} ({pn.removesuffix('.dat')}) · {color_name}"
                        )
                page.append(
                    "<ul>"
                    + "".join(
                        f"<li>{count} × {html.escape(labels[pn,color])}</li>"
                        for (pn, color), count in quantities.items()
                    )
                    + "</ul></section>"
                )
        for extension in ("io", "mpd"):
            with suppress_render():
                result = save_model(str(target / ("model." + extension)))
            if not result["ok"]:
                raise ValueError(result["error"]["message"])
        (target / "instructions.json").write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf8"
        )
        (target / "instructions.html").write_text("\n".join(page), encoding="utf8")
        return ok(
            {
                "directory": str(target),
                "studio_file": str(target / "model.io"),
                "html": str(target / "instructions.html"),
                "assemblies": len(ordered),
                "steps": sum(len(a["steps"]) for a in manifest["assemblies"]),
            }
        )
    except Exception as exc:
        return err(str(exc), "EXPORT_FAILED")
