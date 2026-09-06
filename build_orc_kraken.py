"""Orc crew and armoured deck dressing, using actual Studio connection geometry."""

import math
import argparse
import asyncio
import base64
import json
import tomllib
from pathlib import Path
from fastmcp import Client
from fastmcp.client.transports import StdioTransport
from build_articulated_kraken import ROOT, part, I, multiply, located, vector

OUT = ROOT / "output/orc-kraken-ship"


def rx(angle):
    a = math.radians(angle)
    c, s = math.cos(a), math.sin(a)
    return [1, 0, 0, 0, c, -s, 0, s, c]


def rz(angle):
    a = math.radians(angle)
    c, s = math.cos(a), math.sin(a)
    return [c, -s, 0, s, c, 0, 0, 0, 1]


def ry(angle):
    a = math.radians(angle)
    c, s = math.cos(a), math.sin(a)
    return [c, 0, -s, 0, 1, 0, s, 0, c]


def orc(x, floor, z, yaw=0, captain=False, sword=False):
    body = [
        part("3815c01", 308, 0, -40),
        part("973pma", 70, 0, -72),
        part("3626bpm0" if captain else "3626bpma", 2, 0, -96),
    ]
    weapon = []
    for right, shoulder, hinge, angle, wrist in [
        (
            True,
            [-14.58912, 9.07687, 0],
            [1, 0, 0],
            math.degrees(math.atan2(0.169703215, 0.9854952)),
            [-5, 19, -9.5],
        ),
        (
            False,
            [14.58, 9.080009, 0],
            [-1, 0, 0],
            -math.degrees(math.atan2(0.170670629, 0.9853281)),
            [5, 19, -10],
        ),
    ]:
        r = multiply(rz(angle), rx(-45 if right and sword else 0))
        offset = vector(r, hinge)
        origin = [shoulder[j] - offset[j] - (72 if j == 1 else 0) for j in range(3)]
        body.append(part("3818" if right else "3819", 2, *origin, r))
        hand_pos = [origin[j] + vector(r, wrist)[j] for j in range(3)]
        hand_r = multiply(r, rx(45))
        body.append(part("3820", 2, *hand_pos, hand_r))
        if right and sword:
            d = [0, 0.968766034, 0.247976661]
            sword_origin = [0, 4 - 1.5 * d[1], -9 - 1.5 * d[2]]
            weapon.append(
                located(
                    part(
                        "10050",
                        72,
                        *sword_origin,
                        rx(math.degrees(math.atan2(d[2], d[1]))),
                    ),
                    hand_pos,
                    hand_r,
                )
            )
    turn = ry(yaw)
    offset = vector(turn, [0, 0, 1.25])
    origin = [x + offset[0], floor + offset[1], z + offset[2]]
    return [located(p, origin, turn) for p in body], [
        located(p, origin, turn) for p in weapon
    ]


def skull():
    return (
        [part("3005", 72, x, 0, -510) for x in (-30, 30)]
        + [part("3710", 72, x, -8, -540, ry(90)) for x in (-30, 30)]
        + [
            part("3701", 72, 0, -32, -570),
            part("47990", 15, 0, -8, -590),
        ]
    )


def deck_details():
    return [
        (
            "War mark and raiding supplies",
            [part("3068bp13", 0, 0, -168, 560)]
            + [part("2489", 308, x, -112, -400) for x in (-60, 60)],
        ),
        (
            "Weathered planks on fighting decks",
            [part("2431", 70, x, -80, -520, ry(90)) for x in (-30, 30)]
            + [
                part("2431", 70, x, -24, z, ry(90))
                for x in (-110, 110)
                for z in (-220, 40)
            ],
        ),
        (
            "Planked command roof",
            [
                part(pn, 70, x, -168, z, ry(90))
                for pn, x, z in [
                    ("63864", -90, 430),
                    ("63864", -90, 510),
                    ("2431", -50, 420),
                    ("2431", -50, 500),
                    ("2431", 50, 440),
                    ("2431", 50, 520),
                    ("63864", 90, 430),
                    ("63864", 90, 530),
                ]
            ],
        ),
        (
            "Iron grates on command deck",
            [
                part("2412b", 72, x, -168, z, ry(90))
                for x in (-110, 110)
                for z in (400, 560)
            ],
        ),
        (
            "Crew footholds",
            [part("3022", 72, 0, -80, -420), part("3022", 72, 0, -168, 480)]
            + [part("3022", 72, x, -24, -120) for x in (-100, 100)],
        ),
    ]


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--through", type=int, default=999)
    parser.add_argument("--finish", action="store_true")
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
        source = (
            checkpoint
            if checkpoint.exists()
            else ROOT / "output/ship-kraken-rotating/Ship Kraken - Rotating Core.io"
        )
        assert (await call("open_model", path=str(source)))["ok"]
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
            (OUT / (name.replace(":", "") + ".json")).write_text(
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

        if not (OUT / "palette-checked.json").exists():
            edits = []
            for p in (await call("list_parts"))["data"]:
                color = p["color"]
                if color == 19:
                    color = 28
                if p["color"] == 14:
                    color = 72 if p["part_number"] == "30055.dat" else 320
                if (
                    p["color"] == 70
                    and p["y"] in (-152, -160)
                    and p["part_number"] in ("41539.dat", "3035.dat")
                ):
                    color = 308
                if color != p["color"]:
                    edits.append(
                        dict(
                            tool="change_color", args=dict(part_id=p["id"], color=color)
                        )
                    )
            if edits:
                assert (await call("batch", calls=edits))["ok"]
            index = next(
                s["step_index"]
                for s in (await call("get_steps"))["data"]
                if s["name"].startswith("23 Forecastle")
            )
            await checked(
                "Skull figurehead under the bowsprit", skull(), insert_at=index
            )
            for i in range(index):
                r = await call(
                    "check_studio_stability", step_index=i, allow_cautions=True
                )
                assert r["data"]["steps"][-1]["status"] in (
                    "clear",
                    "accepted_with_cautions",
                ), r
            assert (await call("save_model", path=str(checkpoint)))["ok"]
            (OUT / "palette-checked.json").write_text(
                json.dumps(dict(changed_colors=len(edits), early_steps=index))
            )
            print("PALETTE AND FIGUREHEAD CHECKED", flush=True)
        phases = deck_details()
        crew = [
            ("Raid captain", 0, -80, -410, 0, True, True),
            ("Port gunner", -100, -24, -110, 0, False, False),
            ("Starboard gunner", 100, -24, -110, 0, False, True),
            ("Helmsman", -70, -80, 200, 90, False, False),
            ("War lookout", 0, -168, 470, 0, True, True),
        ]
        for name, x, y, z, yaw, captain, sword in crew:
            body, weapon = orc(x, y, z, yaw, captain, sword)
            phases.append((name, body))
            if weapon:
                phases.append((name + " weapon", weapon))
        for index, (name, parts) in enumerate(phases):
            if index > args.through:
                break
            await checked(name, parts)
        from build_rotating_kraken import POSES, platforms, collar, root_wrap

        wrapped_supports = "Wrapped tentacle axle supports"
        if wrapped_supports not in completed:
            existing = (await call("list_parts"))["data"]
            axis = next(
                p
                for p in existing
                if p["part_number"] == "3737.dat" and p["x"] == 140 and p["z"] == -260
            )
            shift = 2 - axis["y"]
            steps = (await call("get_steps"))["data"]
            ids = {
                id
                for s in steps
                if s["name"].startswith("Rotating arm ")
                for id in s["part_ids"]
            }
            if shift:
                edits = [
                    dict(
                        tool="move_part",
                        args=dict(
                            part_id=p["id"], x=p["x"], y=p["y"] + shift, z=p["z"]
                        ),
                    )
                    for p in existing
                    if p["id"] in ids
                ]
                assert (await call("batch", calls=edits))["ok"]
            root_index = 14
            root_ids = set(steps[root_index]["part_ids"])
            guns = [
                p
                for p in existing
                if p["id"] in root_ids and p["part_number"] in ("2527.dat", "518.dat")
            ]
            pieces = [
                part(
                    p["part_number"], p["color"], p["x"], p["y"], p["z"], p["rotation"]
                )
                for p in guns
            ]
            pieces += [p for z in (-260, -60, 260) for p in platforms(z)]
            pieces += [
                p for side, z, roll, angles in POSES for p in collar(side, z, roll)
            ]
            await checked(
                wrapped_supports, pieces, insert_at=root_index, replace_existing=True
            )
        for index, (side, z, roll, angles) in enumerate(POSES, 1):
            name = f"Rounded tentacle root {index}"
            pieces = root_wrap(side, z, roll)
            previous = next(
                (s for s in (await call("get_steps"))["data"] if s["name"] == name),
                None,
            )
            replace = (
                dict(insert_at=previous["step_index"], replace_existing=True)
                if previous and previous["parts_in_step"] != len(pieces)
                else {}
            )
            await checked(name, pieces, **replace)
        assert (await call("save_model", path=str(OUT / "Orc Kraken - Core.io")))["ok"]
        if args.finish:
            assert args.through >= len(phases) - 1
            # Verify the serialized Studio poses, including any older high-precision edits.
            import sys

            sys.path.insert(0, str(ROOT / "src"))
            from brick_mcp.io_file import read_io_file
            from brick_mcp.ldraw import parse_ldraw
            from brick_mcp.model import StudioProject
            from brick_mcp.tools.studio_check import studio_result, accepted_native

            core_path = OUT / "Orc Kraken - Core.io"
            raw, entries = read_io_file(str(core_path))
            saved = StudioProject.from_blocks(
                None, parse_ldraw(raw.decode("utf8")), entries
            )
            stale = [
                (model, s["step_index"])
                for model in saved.submodels
                for s in saved.get_steps(model)
                if s["parts_in_step"]
                and not accepted_native(studio_result(saved, model, s["step_index"]))
            ]
            assert (await call("open_model", path=str(core_path)))["ok"]
            for count, (model, index) in enumerate(stale, 1):
                print(
                    "RECHECKING SAVED STEP",
                    count,
                    "/",
                    len(stale),
                    model,
                    index,
                    flush=True,
                )
                r = await call(
                    "check_studio_stability",
                    submodel=model,
                    step_index=index,
                    allow_cautions=True,
                )
                assert accepted_native(r["data"]["steps"][-1]), r
                if count % 10 == 0:
                    assert (await call("save_model", path=str(core_path)))["ok"]
                    assert (await call("save_model", path=str(checkpoint)))["ok"]
            assert (await call("save_model", path=str(core_path)))["ok"]
            assert (await call("save_model", path=str(checkpoint)))["ok"]
            if not (OUT / "assembly-instructions").exists():
                r = await call(
                    "export_instructions",
                    directory=str(OUT / "assembly-instructions"),
                    previews=False,
                    allow_unverified=True,
                )
                assert r["ok"], r
            from build_rotating_kraken import POSES, collar, arms, root_wrap

            side, z, roll, angles = POSES[0]
            before = (
                collar(side, z, roll)
                + [p for group in arms(side, z, roll, angles) for p in group]
                + root_wrap(side, z, roll)
            )
            after = (
                collar(side, z, -15)
                + [p for group in arms(side, z, -15, angles) for p in group]
                + root_wrap(side, z, -15)
            )
            current = (await call("list_parts"))["data"]
            edits = []
            for a, b in zip(before, after):
                matches = [
                    p
                    for p in current
                    if p["part_number"] == a["part_number"] + ".dat"
                    and all(abs(p[k] - a[k]) < 1e-4 for k in ("x", "y", "z"))
                ]
                assert len(matches) == 1, (a, matches)
                ident = matches[0]["id"]
                edits += [
                    dict(
                        tool="move_part",
                        args=dict(part_id=ident, **{k: b[k] for k in ("x", "y", "z")}),
                    ),
                    dict(
                        tool="rotate_part",
                        args=dict(part_id=ident, rotation_matrix=b["rotation_matrix"]),
                    ),
                ]
            assert (await call("batch", calls=edits))["ok"]
            r = await call("check_studio_stability", allow_cautions=True)
            assert accepted_native(r["data"]["steps"][-1]), r
            (OUT / "rotation-check.json").write_text(
                json.dumps(r, indent=2), encoding="utf8"
            )
            assert (
                await call(
                    "save_model", path=str(OUT / "Orc Kraken - Rotation study.io")
                )
            )["ok"]
            assert (await call("open_model", path=str(core_path)))["ok"]
            print("ORC SHIP ROTATION CHECKED", flush=True)
            checkpoint = OUT / "display-checkpoint.io"
            import rebuild_pirate_ship_checked as recipe

            for phase in recipe.phases:
                if phase["allow_unverified_canvas"]:
                    await checked(
                        phase["name"],
                        [{**p, "color": 4} for p in phase["parts"]],
                        allow_unverified_canvas=True,
                    )
            for ext in ("io", "mpd"):
                assert (
                    await call(
                        "save_model", path=str(OUT / ("Orc Kraken - Red Sails." + ext))
                    )
                )["ok"]
            if not (OUT / "red-sail-instructions").exists():
                r = await call(
                    "export_instructions",
                    directory=str(OUT / "red-sail-instructions"),
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
