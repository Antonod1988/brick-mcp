"""Conservative body collision checks and explicit ordinary stud connections."""

from collections import defaultdict

from brick_mcp.catalog import aabbs_overlap
from brick_mcp.geometry import connectors, shape, world_bounds


def summary(report):
    """Keep tool responses compact; full connection graphs remain available on request."""
    return {
        **{k: v for k, v in report.items() if k not in ("connections", "components")},
        "connection_count": len(report.get("connections", [])),
        "component_count": len(report.get("components", [])),
    }


def duplicate_placements(parts):
    """Exact pose duplicates are invalid even when geometry/physics is unknown."""
    seen, duplicates = {}, []
    for p in parts:
        key = (
            p["part_number"].casefold(),
            *(round(v, 6) for v in [p["x"], p["y"], p["z"], *p["rotation"]]),
        )
        duplicates.extend(
            dict(part_a=old, part_b=p, reason="Identical part placements")
            for old in seen.get(key, ())
        )
        seen.setdefault(key, []).append(p)
    return duplicates


def validate_parts(parts, ground_y=None, previous=()):
    if not parts:
        return dict(
            status="passed",
            part_count=0,
            overlaps=[],
            floating=[],
            unknown=[],
            connections=[],
            components=[],
            blocked_access=[],
            ground_y=ground_y,
        )
    boxes, profiles, unknown = {}, {}, []
    for p in parts:
        try:
            boxes[p["id"]] = world_bounds(p)
            profiles[p["id"]] = connectors(p)
            if profiles[p["id"]] is None:
                unknown.append(
                    {
                        "id": p["id"],
                        "reason": "Unsupported connector geometry/orientation",
                    }
                )
        except (ValueError, OSError) as exc:
            unknown.append({"id": p["id"], "reason": str(exc)})
    if ground_y is None and boxes:
        ground_y = max(b[3] for b in boxes.values())
    overlaps = duplicate_placements(parts)
    duplicate_ids = {(p["part_a"]["id"], p["part_b"]["id"]) for p in overlaps}
    potential, blocked, unverified_access = [], [], []
    # ponytail: O(n²) broad phase; add a spatial index when large models become slow.
    for i, a in enumerate(parts):
        for b in parts[i + 1 :]:
            pair = {"part_a": a, "part_b": b}
            if (a["id"], b["id"]) in duplicate_ids:
                continue
            if (
                a["id"] not in boxes
                or b["id"] not in boxes
                or not aabbs_overlap(boxes[a["id"]], boxes[b["id"]])
            ):
                continue
            exact = all(
                shape(p["part_number"])["collision_kind"] == "regular_body"
                and all(abs(v - round(v)) < 1e-5 for v in p["rotation"])
                for p in (a, b)
            )
            (overlaps if exact else potential).append(pair)
    tops, bottoms = defaultdict(set), defaultdict(set)
    for ident, profile in profiles.items():
        if profile is None:
            continue
        for point in profile["top"]:
            tops[tuple(round(v, 3) for v in point)].add(ident)
        for point in profile["bottom"]:
            bottoms[tuple(round(v, 3) for v in point)].add(ident)
    edges = defaultdict(int)
    neighbours = {p["id"]: set() for p in parts}
    for point in tops.keys() & bottoms.keys():
        for a in tops[point]:
            for b in bottoms[point] - {a}:
                edges[tuple(sorted((a, b)))] += 1
                neighbours[a].add(b)
                neighbours[b].add(a)
    roots = {ident for ident, b in boxes.items() if abs(b[3] - ground_y) < 0.1}
    visited, components, floating = set(), [], []
    for ident in neighbours:
        if ident in visited:
            continue
        todo, component = [ident], set()
        while todo:
            current = todo.pop()
            if current in component:
                continue
            component.add(current)
            todo.extend(neighbours[current] - component)
        visited |= component
        components.append(sorted(component))
        if not component & roots:
            floating.extend(sorted(component))
    old_ids = {p["id"] for p in previous}
    for new in parts:
        if new["id"] in old_ids or new["id"] not in boxes:
            continue
        nb = boxes[new["id"]]
        for old in previous:
            ob = boxes.get(old["id"])
            if (
                ob
                and ob[3] <= nb[2] + 0.1
                and min(nb[1], ob[1]) > max(nb[0], ob[0]) + 0.5
                and min(nb[5], ob[5]) > max(nb[4], ob[4]) + 0.5
            ):
                confirmed = all(
                    profiles.get(p["id"]) is not None
                    and shape(p["part_number"])["collision_kind"] == "regular_body"
                    for p in (new, old)
                )
                (blocked if confirmed else unverified_access).append(
                    {
                        "part_id": new["id"],
                        "blocked_by": old["id"],
                        "direction": "from_above",
                    }
                )
    below = [ident for ident, b in boxes.items() if b[3] > ground_y + 0.1]
    status = (
        "failed"
        if overlaps or (floating and not unknown) or blocked or below
        else "unverified" if unknown or potential or unverified_access else "passed"
    )
    return dict(
        status=status,
        part_count=len(parts),
        ground_y=ground_y,
        overlaps=overlaps,
        potential_overlaps=potential,
        floating=floating,
        unknown=unknown,
        below_ground=below,
        connections=[
            dict(part_a=a, part_b=b, studs=count) for (a, b), count in edges.items()
        ],
        components=components,
        blocked_access=blocked,
        unverified_access=unverified_access,
        scope="Ordinary upright studs/receivers; vertical insertion; no clutch-force or structural physics simulation",
    )


def validate_project(project, submodel=None, through_step=None, previous=()):
    first = next(
        (s["step_index"] for s in project.get_steps(submodel) if s["parts_in_step"]), 0
    )
    first_parts = project.flatten(submodel, first)
    ground = max((world_bounds(p)[3] for p in first_parts), default=0)
    return validate_parts(project.flatten(submodel, through_step), ground, previous)


def validate_sequence(project, submodel=None):
    results, previous = [], []
    for step in project.get_steps(submodel):
        if not step["parts_in_step"]:
            continue
        report = validate_project(project, submodel, step["step_index"], previous)
        results.append(dict(step_index=step["step_index"], name=step["name"], **report))
        previous = project.flatten(submodel, step["step_index"])
    return results
