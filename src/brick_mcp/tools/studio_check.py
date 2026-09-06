"""Native Studio checks and content-bound records for each instruction step."""

import hashlib
import json
from datetime import datetime, timezone

from brick_mcp._helpers import err, ok
from brick_mcp.ldraw import MetaCommand
from brick_mcp.model import get_model, StudioProject
from brick_mcp.native_studio import run_native_check, is_canvas
from brick_mcp.server import mcp

PREFIX = "!BRICK_MCP_STUDIO_CHECK "


def accepted_native(report):
    if report.get("status") == "unverified_canvas":
        return (
            report.get("source") == "native_studio_runtime"
            and report.get("allow_unverified_canvas") is True
            and bool(report.get("unmodelled_parts"))
            and all(is_canvas(p["part_number"]) for p in report["unmodelled_parts"])
            and report.get("structural_check", {}).get("status") != "unverified_canvas"
            and accepted_native(report.get("structural_check", {}))
        )
    return (
        report.get("status") in ("clear", "issues_found", "accepted_with_cautions")
        and report.get("source") == "native_studio_runtime"
        and all(
            report.get(k, -1) == 0
            for k in ("warnings", "stability_issues", "detached_sections")
        )
        and (report.get("cautions") == 0 or report.get("allow_cautions") is True)
    )


def affected_parent_steps(project, submodel):
    changed = project._submodel(submodel).name
    affected = {changed}
    while True:
        parents = {
            name
            for name in project.submodels
            if any(p["part_number"] in affected for p in project.list_parts(name))
        }
        if parents <= affected:
            break
        affected |= parents
    for name in affected - {changed}:
        ids = {
            p["id"] for p in project.list_parts(name) if p["part_number"] in affected
        }
        first = next(
            s["step_index"]
            for s in project.get_steps(name)
            if ids.intersection(s["part_ids"])
        )
        yield name, first


def scope(project, submodel=None, through_step=None):
    name = project._submodel(submodel).name
    steps = project.get_steps(name)
    index = (
        len(steps) - 1 if through_step is None or through_step == -1 else through_step
    )
    if not 0 <= index < len(steps):
        raise ValueError("Step index out of range")
    return name, index


def fingerprint(project, submodel=None, through_step=None):
    name, index = scope(project, submodel, through_step)
    parts = project.flatten(name, index)
    payload = {
        "assembly": "root" if name == project.root_submodel else name,
        "steps": [s["name"] for s in project.get_steps(name)[: index + 1]],
        "parts": [
            {
                k: (
                    [format(v, "g") for v in p[k]]
                    if k == "rotation"
                    else format(p[k], "g") if k in ("x", "y", "z") else p[k]
                )
                for k in (
                    "part_number",
                    "color",
                    "x",
                    "y",
                    "z",
                    "rotation",
                    "step_index",
                )
            }
            for p in parts
        ],
    }
    # Canonical floats survive IO type-11 round trips; session UUIDs are excluded.
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def studio_result(project, submodel=None, through_step=None):
    name, index = scope(project, submodel, through_step)
    for cmd in reversed(project._submodel(None).commands):
        if isinstance(cmd, MetaCommand) and cmd.text.startswith(PREFIX):
            try:
                report = json.loads(cmd.text[len(PREFIX) :])
                owner = "root" if name == project.root_submodel else name
                if report.get("owner") != owner or report.get("step_index") != index:
                    continue
                counts = [
                    report[k]
                    for k in (
                        "warnings",
                        "cautions",
                        "stability_issues",
                        "detached_sections",
                    )
                ]
                if any(type(n) is not int or n < 0 for n in counts):
                    raise ValueError("Invalid counters")
                state = "issues_found" if any(counts) else "clear"
                if any(counts) and accepted_native(report):
                    state = "accepted_with_cautions"
                if report.get("status") in ("unverified_canvas", "unverified_physics"):
                    state = report["status"]
                if report.get("source") != "native_studio_runtime":
                    state = "unverified_source"
                if report["model_sha256"] != fingerprint(project, name, index):
                    state = "stale"
                return {**report, "status": state}
            except ValueError, KeyError, TypeError:
                return {"status": "invalid_report"}
    return {"status": "not_run", "submodel": name, "step_index": index}


def check_and_record(
    project,
    submodel=None,
    through_step=None,
    allow_cautions=False,
    allow_unverified_canvas=False,
):
    name, index = scope(project, submodel, through_step)
    result = run_native_check(project, name, index)
    report = {
        **result,
        "submodel": name,
        "owner": "root" if name == project.root_submodel else name,
        "step_index": index,
        "model_sha256": fingerprint(project, name, index),
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "allow_cautions": allow_cautions,
        "allow_unverified_canvas": allow_unverified_canvas,
    }
    if (
        allow_unverified_canvas
        and result.get("unmodelled_parts")
        and all(is_canvas(p["part_number"]) for p in result["unmodelled_parts"])
    ):
        structural = run_native_check(project, name, index, exclude_canvas=True)
        structural["allow_cautions"] = allow_cautions
        report["structural_check"] = structural
        report["status"] = "unverified_canvas"
    if (
        report["status"] != "unverified_canvas"
        and result["status"] != "clear"
        and accepted_native(report)
    ):
        report["status"] = "accepted_with_cautions"
    commands = project._submodel(None).commands
    for cmd in list(commands):
        if isinstance(cmd, MetaCommand) and cmd.text.startswith(PREFIX):
            old = json.loads(cmd.text[len(PREFIX) :])
            if old.get("owner") == report["owner"] and old.get("step_index") == index:
                commands.remove(cmd)
    # Keep bulky per-part diagnostics in the evidence file, not every IO step.
    stored = {
        k: v for k, v in report.items() if k not in ("clutch_parts", "detached_parts")
    }
    commands.append(MetaCommand(PREFIX + json.dumps(stored, ensure_ascii=True)))
    project._dirty = True
    return report


@mcp.tool
def inspect_studio_connectors(part_number: str) -> dict:
    """Read actual native Studio connector positions/directions for one catalogue part.

    Coordinates are local LDraw LDU at identity placement. An empty list means
    Studio has no connectors for this part/variant; never infer attachments from
    its render mesh alone. Does not change the active MCP model.
    """
    try:
        probe = StudioProject.new("connector-probe")
        probe.add_part(None, part_number, 4, 0, 0, 0)
        result = run_native_check(probe, include_connectors=True)
        return ok({"source": result["source"], "parts": result["connector_parts"]})
    except Exception as exc:
        return err(str(exc), "NATIVE_CONNECTOR_INSPECTION_FAILED")


@mcp.tool
def check_studio_stability(
    submodel: str = "",
    step_index: int = -1,
    all_steps: bool = False,
    allow_cautions: bool = False,
    allow_unverified_canvas: bool = False,
) -> dict:
    """Run actual Studio Stability AND Connectivity through the local worker.

    No Computer Use. Returns native counters and flagged part coordinates.
    all_steps checks every prefix of the chosen assembly; default checks its final
    state. Missing worker, timeout, or mismatched results fail closed. Save to
    persist the reports. This tests Studio's rules, not a physical safety proof.
    """
    try:
        project = get_model()
        name, index = scope(project, submodel, step_index)
        indices = range(index + 1) if all_steps else [index]
        reports = [
            check_and_record(project, name, i, allow_cautions, allow_unverified_canvas)
            for i in indices
            if project.get_steps(name)[i]["parts_in_step"]
        ]
        return ok(
            {
                "status": (
                    "issues_found"
                    if any(r["status"] != "clear" for r in reports)
                    else "clear"
                ),
                "steps": reports,
            }
        )
    except Exception as exc:
        return err(str(exc), "NATIVE_STUDIO_CHECK_FAILED")
