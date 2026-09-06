"""Longer individually posed tentacles on captured rotating axles; native MCP gates."""

import argparse
import asyncio
import base64
import json
import math
import tomllib
from pathlib import Path
from fastmcp import Client
from fastmcp.client.transports import StdioTransport
from build_articulated_kraken import (
    ROOT,
    PORTS,
    part,
    I,
    Y180,
    multiply,
    located,
    segments,
)

OUT = ROOT / "output/ship-kraken-rotating"
POSES = [
    (1, -260, 30, [30, 50, 70, 90, 112, 138, 166]),
    (1, -60, -18, [22, 45, 68, 92, 118, 145, 172]),
    (1, 260, -32, [32, 57, 82, 107, 132, 157, 182]),
    (-1, -260, -27, [28, 53, 78, 103, 128, 153, 178]),
    (-1, -60, 18, [30, 48, 68, 92, 120, 149, 178]),
    (-1, 260, 35, [25, 48, 73, 99, 124, 149, 174]),
]


def orientation(side, roll):
    a = math.radians(roll)
    c, s = math.cos(a), math.sin(a)
    return multiply(I if side == 1 else Y180, [1, 0, 0, 0, c, -s, 0, s, c])


def collar(side, z, roll):
    r = orientation(side, roll)
    axle_rotation = [0, 0, -1, 0, 1, 0, 1, 0, 0]
    pieces = [part("3737", 0, 140, 10), part("3022", 29, 220, -8)]
    pieces += [part("3713", 72, x, 10, 0, axle_rotation) for x in (50, 130)]
    pieces += [part("32064a", 29, x, 0, 0, axle_rotation) for x in (210, 230)]
    pieces += [part("22890", 29, 220, -16, dz) for dz in (-10, 10)]
    return [located({**p, "y": p["y"] - 10}, (0, 2, z), r) for p in pieces]


def root_wrap(side, z, roll):
    forward = [0, 0, -1, 0, 1, 0, 1, 0, 0]
    backward = [0, 0, 1, 0, 1, 0, -1, 0, 0]
    pieces = [part("30602", 29, 220, -16)]
    pieces += [part("24201", 29, 210, 24, dz, forward) for dz in (-10, 10)]
    pieces += [part("85861", 5, 190, 24, dz) for dz in (-10, 10)]
    pieces += [
        part("3023", 29, 230, 24, 0, forward),
        part("99207", 29, 230, 32, 0, forward),
        part("14769", 29, 252, 20, 0, [0, -1, 0, 1, 0, 0, 0, 0, 1]),
    ]
    pieces += [part("24201", 29, 230, 40, dz, backward) for dz in (-10, 10)]
    pieces += [part("85861", 5, 250, 40, dz) for dz in (-10, 10)]
    return [
        located({**p, "y": p["y"] - 10}, (0, 2, z), orientation(side, roll))
        for p in pieces
    ]


def arms(side, z, roll, angles):
    r = orientation(side, roll)
    return [
        [
            located({**p, "x": p["x"] + 80, "y": p["y"] - 42}, (0, 2, z), r)
            for p in group
        ]
        for group in segments(1, 0, angles, thick_count=4)
    ]


def platforms(z):
    return (
        [part("3006", 70, 0, 32, z), part("4282", 70, 0, 24, z)]
        + ([part("3022", 70, x, 32, z) for x in (-140, 140)] if z == -60 else [])
        + [part("3031", 70, side * 80, 16, z) for side in (-1, 1)]
        + [
            part("3701", 72, side * x, -8, z, [0, 0, -1, 0, 1, 0, 1, 0, 0])
            for side in (-1, 1)
            for x in (70, 110)
        ]
    )


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--through", type=int, default=1)
    parser.add_argument("--finish", action="store_true")
    parser.add_argument("--motion-only", action="store_true")
    parser.add_argument("--render", action="store_true")
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
    ) as c:

        async def call(tool, **kw):
            r = await c.call_tool(tool, kw)
            return json.loads(next(b.text for b in r.content if b.type == "text"))

        checkpoint = OUT / "checkpoint.io"
        fresh = not checkpoint.exists()
        source = (
            ROOT / "output/ship-kraken-articulated/Ship Kraken - Articulated Core.io"
            if fresh
            else checkpoint
        )
        assert (await call("open_model", path=str(source)))["ok"]
        if fresh:
            old = [
                s
                for s in (await call("get_steps"))["data"]
                if s["name"].startswith("Flexible arm")
            ]
            assert (
                await call(
                    "batch",
                    calls=[
                        dict(tool="remove_part", args=dict(part_id=id))
                        for s in old
                        for id in s["part_ids"]
                    ],
                )
            )["ok"]
            # Fill the vacated instruction steps below; avoid 36 redundant full audits.
            assert (await call("save_model", path=str(checkpoint)))["ok"]
        completed = {s["name"] for s in (await call("get_steps"))["data"]}

        async def checked(name, parts, **kw):
            if name in completed:
                return
            if "insert_at" not in kw:
                empty = next(
                    (
                        s
                        for s in (await call("get_steps"))["data"]
                        if not s["parts_in_step"]
                    ),
                    None,
                )
                if empty:
                    kw["insert_at"] = empty["step_index"]
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
                n = r.get("studio_check", {})
                print(
                    "REJECTED",
                    name,
                    r.get("error"),
                    {
                        k: n.get(k)
                        for k in (
                            "warnings",
                            "cautions",
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
            n = r["data"]["studio_check"]
            print(
                "CHECKED",
                name,
                n["status"],
                n.get("warnings"),
                n.get("cautions"),
                flush=True,
            )

        root_name = "Captured rotating axles in hull"
        if root_name not in completed:
            oldstep = (await call("get_steps"))["data"][14]
            ids = set(oldstep["part_ids"])
            guns = [
                p
                for p in (await call("list_parts"))["data"]
                if p["id"] in ids and p["part_number"] in ("2527.dat", "518.dat")
            ]
            pieces = [
                part(
                    p["part_number"], p["color"], p["x"], p["y"], p["z"], p["rotation"]
                )
                for p in guns
            ]
            pieces += [p for z in PORTS for p in platforms(z)]
            pieces += [
                p for side, z, roll, angles in POSES for p in collar(side, z, roll)
            ]
            await checked(root_name, pieces, insert_at=14, replace_existing=True)
        for n, (side, z, roll, angles) in enumerate(POSES, 1):
            if n > args.through:
                break
            for i, pieces in enumerate(arms(side, z, roll, angles), 1):
                await checked(f"Rotating arm {n} segment {i:02d}", pieces)
        core = OUT / "Ship Kraken - Rotating Core.io"
        assert (await call("save_model", path=str(core)))["ok"]
        if args.finish:
            assert args.through == 6
            if not args.motion_only and not (OUT / "core-instructions").exists():
                r = await call(
                    "export_instructions",
                    directory=str(OUT / "core-instructions"),
                    previews=False,
                    allow_unverified=True,
                )
                assert r["ok"], r
            # Rotate the first shaft while retaining every joint centre.
            side, z, roll, angles = POSES[0]
            expected = collar(side, z, roll) + [
                p for group in arms(side, z, roll, angles) for p in group
            ]
            changed = collar(side, z, -15) + [
                p for group in arms(side, z, -15, angles) for p in group
            ]
            current = (await call("list_parts"))["data"]
            edits = []
            for a, b in zip(expected, changed):
                matches = [
                    p
                    for p in current
                    if p["part_number"] == a["part_number"] + ".dat"
                    and all(abs(p[k] - a[k]) < 1e-4 for k in ("x", "y", "z"))
                ]
                assert len(matches) == 1, (a, matches)
                id = matches[0]["id"]
                edits += [
                    dict(
                        tool="move_part",
                        args=dict(part_id=id, **{k: b[k] for k in ("x", "y", "z")}),
                    ),
                    dict(
                        tool="rotate_part",
                        args=dict(part_id=id, rotation_matrix=b["rotation_matrix"]),
                    ),
                ]
            assert (await call("batch", calls=edits))["ok"]
            report = await call("check_studio_stability", allow_cautions=True)
            (OUT / "rotation-check.json").write_text(
                json.dumps(report, indent=2), encoding="utf8"
            )
            assert report["data"]["steps"][-1]["status"] in (
                "clear",
                "accepted_with_cautions",
            ), report
            assert (await call("save_model", path=str(OUT / "Rotation study.io")))["ok"]
            print("ROTATION CHECKED", flush=True)
            assert (await call("open_model", path=str(core)))["ok"]
            if args.motion_only:
                return
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
                        path=str(
                            OUT / ("Ship Kraken - Long Rotating Tentacles." + ext)
                        ),
                    )
                )["ok"]
            r = await call(
                "export_instructions",
                directory=str(OUT / "display-instructions"),
                previews=False,
                allow_unverified=True,
                draft=True,
            )
            assert r["ok"], r
        if args.render:
            r = await c.call_tool(
                "render_model", dict(width=1500, height=1150, latitude=25, longitude=60)
            )
            for b in r.content:
                if b.type == "image":
                    (OUT / "preview.png").write_bytes(base64.b64decode(b.data))
        print((await call("get_model_info"))["data"], flush=True)


if __name__ == "__main__":
    asyncio.run(main())
