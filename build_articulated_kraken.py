"""Replace fixed Technic tentacles with curved System segments on friction balls."""

import argparse
import asyncio
import base64
import json
import math
import tomllib
from pathlib import Path
from fastmcp import Client
from fastmcp.client.transports import StdioTransport
from build_kraken import ROOT, part, I

OUT = ROOT / "output/ship-kraken-articulated"
PORTS = (-260, -60, 260)
Y180 = [-1, 0, 0, 0, 1, 0, 0, 0, -1]


def vector(r, v):
    return [sum(r[i * 3 + j] * v[j] for j in range(3)) for i in range(3)]


def multiply(a, b):
    return [
        sum(a[i * 3 + k] * b[k * 3 + j] for k in range(3))
        for i in range(3)
        for j in range(3)
    ]


def located(p, origin, r):
    v = vector(r, [p["x"], p["y"], p["z"]])
    return {
        **p,
        **dict(zip(("x", "y", "z"), [round(origin[i] + v[i], 6) for i in range(3)])),
        "rotation_matrix": [round(x, 9) for x in multiply(r, p["rotation_matrix"])],
    }


def chassis(z):
    return (
        [part("3006", 70, 0, 32, z), part("4282", 70, 0, 24, z)]
        + ([part("3022", 70, x, 32, z) for x in (-140, 140)] if z == -60 else [])
        + [
            part("22890", 29, side * 140, 16, z + dz, I if side == 1 else Y180)
            for side in (1, -1)
            for dz in (-10, 10)
        ]
    )


def segments(side, z, angles):
    joint = [170.0, 20.0, 0.0]
    mirror = I if side == 1 else Y180
    result = []
    for i, angle in enumerate(angles):
        a = math.radians(angle)
        c, s = math.cos(a), math.sin(a)
        r = [-c, s, 0, s, c, 0, 0, 0, -1]
        offset = vector(r, [30, 4, 0])
        origin = [joint[j] - offset[j] for j in range(3)]
        pieces = [
            part("14418" if i == len(angles) - 1 else "14419", 29, z=dz)
            for dz in ((-10, 10) if i < len(angles) - 2 else (10,))
        ]
        if i < len(angles) - 2:
            pieces.append(part("30602", 29))
        elif i == len(angles) - 2:
            pieces += [part("49307", 29, x, 0, 10) for x in (-10, 10)]
        else:
            pieces += [part("98138", 29, x, -8, 10) for x in (-10, 10)]
        pieces += [part("85861", 5, x, 8, 10) for x in (-10, 10)]
        placed = [located(located(p, origin, r), (0, 0, z), mirror) for p in pieces]
        result.append(placed)
        # A socket and the preceding ball share an exact centre in every pose.
        assert max(abs(origin[j] + offset[j] - joint[j]) for j in range(3)) < 1e-8
        joint = [joint[0] + 60 * c, joint[1] - 60 * s, joint[2]]
    return result


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--through", type=int, default=1)
    parser.add_argument("--render", action="store_true")
    parser.add_argument("--reset-arms", action="store_true")
    parser.add_argument("--repair-roots", action="store_true")
    parser.add_argument("--refine-tips", action="store_true")
    parser.add_argument("--finish", action="store_true")
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    cfg = tomllib.loads(
        (Path.home() / ".codex/config.toml").read_text(encoding="utf8")
    )["mcp_servers"]["brick"]
    async with Client(
        StdioTransport(
            command=cfg["command"], args=cfg["args"], env=cfg["env"], keep_alive=False
        ),
        timeout=1200,
    ) as client:

        async def call(tool, **kw):
            result = await client.call_tool(tool, kw)
            return json.loads(next(c.text for c in result.content if c.type == "text"))

        checkpoint = OUT / "checkpoint.io"
        source = (
            checkpoint
            if checkpoint.exists()
            else ROOT / "output/pirate-ship-checked/Pirate Ship - Core.io"
        )
        assert (await call("open_model", path=str(source)))["ok"]
        if args.reset_arms:
            old = [
                s
                for s in (await call("get_steps"))["data"]
                if s["name"].startswith("Flexible arm")
            ]
            removals = [
                dict(tool="remove_part", args=dict(part_id=id))
                for s in old
                for id in s["part_ids"]
            ]
            if removals:
                assert (await call("batch", calls=removals))["ok"]
            for s in reversed(old):
                result = await call(
                    "edit_step",
                    action="delete_empty",
                    step_index=s["step_index"],
                    allow_unverified=True,
                    allow_cautions=True,
                )
                assert result["ok"], result
            assert (await call("save_model", path=str(checkpoint)))["ok"]
        completed = {s["name"] for s in (await call("get_steps"))["data"]}

        async def checked(name, parts, **kw):
            if name in completed and not kw.get("replace_existing"):
                return
            print("CHECKING", name, flush=True)
            r = await call(
                "apply_step",
                name=name,
                parts=parts,
                preview=False,
                allow_unverified=True,
                allow_cautions=True,
                save_path=str(checkpoint),
                **kw,
            )
            if not r["ok"]:
                (OUT / "failure.json").write_text(
                    json.dumps(r, indent=2), encoding="utf8"
                )
                print("REJECTED", name, r.get("error"), flush=True)
                native = r.get("studio_check", {})
                print(
                    {
                        k: native.get(k)
                        for k in (
                            "warnings",
                            "cautions",
                            "stability_issues",
                            "detached_sections",
                            "detached_parts",
                        )
                    },
                    flush=True,
                )
                raise SystemExit(1)
            (OUT / (name + ".json")).write_text(
                json.dumps(r["data"], indent=2), encoding="utf8"
            )
            report = r["data"]["studio_check"]
            print(
                "CHECKED",
                name,
                report["status"],
                report.get("warnings"),
                report.get("cautions"),
                flush=True,
            )

        for side, index in [(1, 15), (-1, 14)]:
            name = (
                "Clear ports for ball joints"
                if side == 1
                else "Paired ball-joint roots"
            )
            if name in completed and not (side == -1 and args.repair_roots):
                continue
            steps = (await call("get_steps"))["data"]
            ids = set(steps[index]["part_ids"])
            remain = [
                p
                for p in (await call("list_parts"))["data"]
                if p["id"] in ids
                and p["part_number"] in ("2527.dat", "518.dat")
                and p["z"] not in PORTS
            ]
            parts = [
                part(
                    p["part_number"], p["color"], p["x"], p["y"], p["z"], p["rotation"]
                )
                for p in remain
            ]
            if side == -1:
                parts.extend(p for z in PORTS for p in chassis(z))
            await checked(name, parts, replace_existing=True, insert_at=index)
        number = 0
        for side in (1, -1):
            for z in PORTS:
                number += 1
                if number > args.through:
                    continue
                angles = (
                    [30, 60, 90, 120, 150, 180]
                    if z == 260
                    else [25, 50, 75, 100, 125, 150]
                )
                arm_parts = segments(side, z, angles)
                if args.refine_tips:
                    step_map = {
                        s["name"]: s["step_index"]
                        for s in (await call("get_steps"))["data"]
                    }
                    for index in (5, 4):
                        name = f"Flexible arm {number} segment {index+1:02d}"
                        if name in step_map:
                            await checked(
                                name,
                                arm_parts[index],
                                insert_at=step_map[name],
                                replace_existing=True,
                            )
                for i, pieces in enumerate(arm_parts, 1):
                    await checked(f"Flexible arm {number} segment {i:02d}", pieces)
        assert (
            await call(
                "save_model", path=str(OUT / "Ship Kraken - Articulated Core.io")
            )
        )["ok"]
        if args.finish:
            assert args.through >= 6, "Finish requires all six arms"
            core_path = OUT / "Ship Kraken - Articulated Core.io"
            if not (OUT / "core-instructions").exists():
                exported = await call(
                    "export_instructions",
                    directory=str(OUT / "core-instructions"),
                    previews=False,
                    allow_unverified=True,
                )
                assert exported["ok"], exported
            # Move every segment of one arm through its real ball-centre chain.
            steps = (await call("get_steps"))["data"]
            current = {p["id"]: p for p in (await call("list_parts"))["data"]}
            moved = segments(1, PORTS[0], [30, 60, 90, 120, 150, 180])
            edits = []
            for index, pieces in enumerate(moved, 1):
                step = next(
                    s
                    for s in steps
                    if s["name"] == f"Flexible arm 1 segment {index:02d}"
                )
                assert len(step["part_ids"]) == len(pieces)
                for id, p in zip(step["part_ids"], pieces):
                    assert current[id]["part_number"] == p["part_number"] + ".dat"
                    edits += [
                        dict(
                            tool="move_part",
                            args=dict(part_id=id, x=p["x"], y=p["y"], z=p["z"]),
                        ),
                        dict(
                            tool="rotate_part",
                            args=dict(part_id=id, rotation_matrix=p["rotation_matrix"]),
                        ),
                    ]
            assert (await call("batch", calls=edits))["ok"]
            motion = await call("check_studio_stability", allow_cautions=True)
            (OUT / "motion-check.json").write_text(
                json.dumps(motion, indent=2), encoding="utf8"
            )
            report = motion["data"]["steps"][-1]
            assert report["status"] in ("clear", "accepted_with_cautions"), report
            assert (
                await call("save_model", path=str(OUT / "Motion study - curled.io"))
            )["ok"]
            print(
                "MOTION CHECKED",
                report["warnings"],
                report["cautions"],
                report["detached_sections"],
                flush=True,
            )
            assert (await call("open_model", path=str(core_path)))["ok"]
            checkpoint = OUT / "display-checkpoint.io"
            import rebuild_pirate_ship_checked as recipe

            for phase in recipe.phases:
                if phase["allow_unverified_canvas"]:
                    await checked(
                        phase["name"], phase["parts"], allow_unverified_canvas=True
                    )
            for ext in ("io", "mpd"):
                assert (
                    await call(
                        "save_model",
                        path=str(OUT / ("Ship Kraken - Moving Tentacles." + ext)),
                    )
                )["ok"]
            exported = await call(
                "export_instructions",
                directory=str(OUT / "display-instructions"),
                previews=False,
                allow_unverified=True,
                draft=True,
            )
            assert exported["ok"], exported
        if args.render:
            r = await client.call_tool(
                "render_model", dict(width=1400, height=1100, latitude=25, longitude=60)
            )
            for b in r.content:
                if b.type == "image":
                    (OUT / "preview.png").write_bytes(base64.b64decode(b.data))
        print((await call("get_model_info"))["data"], flush=True)


if __name__ == "__main__":
    asyncio.run(main())
