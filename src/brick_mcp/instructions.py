"""Editable LDraw step boundaries and named subassemblies."""

import json

from brick_mcp.ldraw import MetaCommand, PartLine

NAME = "STUDIOSTEPDESC "
LEGACY_NAME = "!BRICK_MCP STEP_NAME "


def clean_name(name):
    name = name.strip()
    if not name or len(name) > 120 or any(c in name for c in "\r\n\x00"):
        raise ValueError("Name must contain 1–120 characters on one line")
    return name


def groups(sd):
    result = [{"name": "", "commands": []}]
    for cmd in sd.commands:
        if isinstance(cmd, MetaCommand) and cmd.text == "STEP":
            result.append({"name": "", "commands": []})
        elif isinstance(cmd, MetaCommand) and cmd.text.startswith(NAME):
            result[-1]["name"] = cmd.text[len(NAME) :]
        elif isinstance(cmd, MetaCommand) and cmd.text.startswith(LEGACY_NAME):
            result[-1]["name"] = json.loads(cmd.text[len(LEGACY_NAME) :])
        else:
            result[-1]["commands"].append(cmd)
    while len(result) > 1 and not result[-1]["commands"] and not result[-1]["name"]:
        result.pop()
    return result


def write_groups(sd, steps):
    sd.commands = []
    for i, step in enumerate(steps):
        if i:
            sd.commands.append(MetaCommand("STEP"))
        sd.commands.extend(step["commands"])
        if step["name"]:
            sd.commands.append(MetaCommand(NAME + clean_name(step["name"])))
    sd._rebuild_index()


def describe_steps(sd):
    result = []
    cumulative = 0
    for i, group in enumerate(groups(sd)):
        parts = [c for c in group["commands"] if isinstance(c, PartLine)]
        cumulative += len(parts)
        result.append(
            {
                "step_index": i,
                "name": group["name"],
                "parts_in_step": len(parts),
                "cumulative_parts": cumulative,
                "part_ids": [c._id for c in parts],
            }
        )
    return result


def edit(
    project,
    action,
    step_index,
    submodel=None,
    name="",
    target_index=None,
    part_ids=None,
):
    sd = project._submodel(submodel)
    steps = groups(sd)
    if action == "insert":
        if not 0 <= step_index <= len(steps):
            raise ValueError("Step index out of range")
        steps.insert(step_index, {"name": clean_name(name), "commands": []})
    else:
        if not 0 <= step_index < len(steps):
            raise ValueError("Step index out of range")
        if action == "rename":
            steps[step_index]["name"] = clean_name(name)
        elif action == "reorder":
            if target_index is None or not 0 <= target_index < len(steps):
                raise ValueError("Target step index out of range")
            steps.insert(target_index, steps.pop(step_index))
        elif action in ("move_parts", "split"):
            ids = set(part_ids or [])
            available = {
                c._id for s in steps for c in s["commands"] if isinstance(c, PartLine)
            }
            if not ids or not ids <= available or len(ids) != len(part_ids):
                raise ValueError("part_ids must be unique existing parts")
            if action == "split":
                source_ids = {
                    c._id
                    for c in steps[step_index]["commands"]
                    if isinstance(c, PartLine)
                }
                if not ids < source_ids:
                    raise ValueError(
                        "Split must move some, but not all, parts of the source step"
                    )
                target_index = step_index + 1
                steps.insert(target_index, {"name": clean_name(name), "commands": []})
            elif target_index is None or not 0 <= target_index < len(steps):
                raise ValueError("Target step index out of range")
            moved = []
            for group in steps:
                moved += [
                    c
                    for c in group["commands"]
                    if isinstance(c, PartLine) and c._id in ids
                ]
                group["commands"] = [
                    c
                    for c in group["commands"]
                    if not (isinstance(c, PartLine) and c._id in ids)
                ]
            steps[target_index]["commands"].extend(moved)
        elif action == "merge_next":
            if step_index + 1 >= len(steps):
                raise ValueError("No following step to merge")
            steps[step_index]["commands"].extend(steps.pop(step_index + 1)["commands"])
        elif action == "delete_empty":
            if any(isinstance(c, PartLine) for c in steps[step_index]["commands"]):
                raise ValueError("Move the step's parts before deleting it")
            steps.pop(step_index)
        else:
            raise ValueError(
                "Unknown action: use insert, rename, reorder, move_parts, split, merge_next, delete_empty"
            )
    write_groups(sd, steps or [{"name": "", "commands": []}])
    project._dirty = True
    return describe_steps(sd)
