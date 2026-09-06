"""Pink ship-kraken, assembled and checked through the real Studio MCP."""

import argparse
import asyncio
import base64
import json
import tomllib
from pathlib import Path
from fastmcp import Client
from fastmcp.client.transports import StdioTransport

ROOT = Path(__file__).parent
OUT = ROOT / "output/ship-kraken-pink"
I = [1, 0, 0, 0, 1, 0, 0, 0, 1]
Y90 = [0, 0, -1, 0, 1, 0, 1, 0, 0]
Y270 = [0, 0, 1, 0, 1, 0, -1, 0, 0]
X90 = [1, 0, 0, 0, 0, -1, 0, 1, 0]
X270 = [1, 0, 0, 0, 0, 1, 0, -1, 0]
HORIZONTAL = [0, 0, 1, 1, 0, 0, 0, 1, 0]
PORTS = (-260, -60, 260)


def part(pn, color, x=0, y=0, z=0, r=I):
    return dict(
        part_number=pn,
        color=color,
        x=round(x, 6),
        y=round(y, 6),
        z=round(z, 6),
        rotation_matrix=[round(v, 6) for v in r],
    )


def place(parts, side, z):
    return [
        {
            **p,
            "x": side * p["x"],
            "y": p["y"] - 8,
            "z": z + side * p["z"] - (20 if side < 0 else 0),
            "rotation_matrix": [
                v * (side if i // 3 != 1 else 1)
                for i, v in enumerate(p["rotation_matrix"])
            ],
        }
        for p in parts
    ]


def mount(side, z):
    return place(
        [part("32278", 29, 200, 18, -10, HORIZONTAL)]
        + [
            part("2780", 0, x, 18, 0 if side == 1 else -20, Y90)
            for x in (60, 80, 100, 120, 140)
        ],
        side,
        z,
    )


def chassis(z):
    return (
        [
            part("3006", 70, 0, 32, z),
            part("4282", 70, 0, 24, z),
            part("3703", 29, 0, 0, z + 10),
        ]
        + ([part("3022", 70, x, 32, z) for x in (-140, 140)] if z == -60 else [])
        + mount(1, z)
        + mount(-1, z)
    )


def arm(side, z, tall=False):
    pieces = []
    cups = []

    def curve(x, y, plane, r, joints, free):
        pieces.extend(part("32251", 29, x, y, plane + d, r) for d in (-5, 5))
        pieces.extend(part("2780", 0, a, b, plane + 10, Y90) for a, b in joints)
        cups.extend((a, b, plane) for a, b in free)

    curve(
        420,
        18,
        -30,
        [0, 0, -1, -1, 0, 0, 0, 1, 0],
        [(320, 18), (340, 18)],
        [(380, 18), (420, -2)],
    )
    shift = 200 if tall else 0
    plane = -50
    if tall:
        pieces.append(part("32278", 29, 420, -122, -50, X90))
        pieces.extend(part("2780", 0, 420, y, -40, Y90) for y in (-22, -42))
        cups.extend((420, y, -50) for y in (-82, -142, -182))
        plane -= 20
    curve(
        420,
        -122 - shift,
        plane,
        [-1, 0, 0, 0, 0, 1, 0, 1, 0],
        [(420, -22 - shift), (420, -42 - shift)],
        [(420, -62 - shift), (400, -122 - shift)],
    )
    curve(
        320,
        -122 - shift,
        plane - 20,
        X90,
        [(360, -122 - shift), (380, -122 - shift)],
        [(320, -162 - shift), (320, -202 - shift)],
    )
    cups.extend((x, 18, -10) for x in (180, 220, 260, 300))
    detail = []
    for x, y, zz in cups:
        face = zz - 10 if side == 1 else zz + 10
        detail.extend(
            [
                part("4274", 0, x, y, face, Y270 if side == 1 else Y90),
                part(
                    "85861",
                    5,
                    x,
                    y,
                    face - 8 if side == 1 else face + 8,
                    X90 if side == 1 else X270,
                ),
            ]
        )
    # Curved System shells on the back; pins avoid the suction-cup holes.
    skin = []
    points = [(x, 18, -10, 1, 0) for x in (200, 240, 280)]
    points += [(x, 18, -30, 1, 0) for x in (360, 400)]
    if tall:
        points += [(420, y, -50, 0, -1) for y in (-102, -162)]
    points += [(420, -82 - shift, plane, 0, -1)]
    points += [(320, y - shift, plane - 20, 0, -1) for y in (-142, -182, -222)]
    sign = 1 if side == 1 else -1
    for index, (x, y, zz, ux, uy) in enumerate(points):
        vx, vy = sign * uy, -sign * ux
        rotation = [vx, 0, ux, vy, 0, uy, 0, -sign, 0]
        face = zz + sign * 10
        skin.append(part("4274", 0, x, y, face, Y90 if sign == 1 else Y270))
        if index == len(points) - 1:
            skin.append(part("11477", 29, x + 10 * ux, y + 10 * uy, face, rotation))
        else:
            skin += [
                part("3023", 29, x + 10 * vx, y + 10 * vy, face + sign * 8, rotation),
                part(
                    "15068",
                    29,
                    x + 10 * vx + 10 * ux,
                    y + 10 * vy + 10 * uy,
                    face + sign * 8,
                    rotation,
                ),
            ]
    return place(pieces, side, z), place(detail, side, z), place(skin, side, z)


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--through", type=int, default=99)
    parser.add_argument("--render", action="store_true")
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
    ) as c:

        async def call(tool, **kw):
            r = await c.call_tool(tool, kw)
            return json.loads(next(b.text for b in r.content if b.type == "text"))

        checkpoint = OUT / "checkpoint.io"
        assert (
            await call(
                "open_model",
                path=str(
                    checkpoint
                    if checkpoint.exists()
                    else ROOT / "output/pirate-ship-checked/Pirate Ship - Core.io"
                ),
            )
        )["ok"]

        async def checked(name, parts, **kw):
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
                report = r.get("studio_check", {})
                print(
                    "REJECTED",
                    name,
                    json.dumps(
                        {
                            k: v
                            for k, v in report.items()
                            if k
                            in (
                                "warnings",
                                "cautions",
                                "stability_issues",
                                "detached_parts",
                                "detached_sections",
                            )
                        }
                    ),
                    r.get("error"),
                    flush=True,
                )
                raise SystemExit(1)
            (OUT / (name.replace(":", "") + ".json")).write_text(
                json.dumps(r["data"], indent=2), encoding="utf8"
            )
            check = r["data"]["studio_check"]
            print(
                "CHECKED",
                name,
                check["status"],
                check.get("warnings"),
                check.get("cautions"),
                flush=True,
            )

        completed = {s["name"] for s in (await call("get_steps"))["data"]}
        for side, index in [(1, 15), (-1, 14)]:
            name = (
                "Kraken free starboard ports"
                if side == 1
                else "Kraken reinforced internal chassis"
            )
            if name in completed:
                continue
            steps = (await call("get_steps"))["data"]
            ids = set(steps[index]["part_ids"])
            original = [
                p
                for p in (await call("list_parts"))["data"]
                if p["id"] in ids and p["z"] not in PORTS
            ]
            parts = [
                part(
                    p["part_number"], p["color"], p["x"], p["y"], p["z"], p["rotation"]
                )
                for p in original
            ]
            if side == -1:
                parts.extend(p for z in PORTS for p in chassis(z))
            await checked(name, parts, replace_existing=True, insert_at=index)
        n = 0
        for side in (1, -1):
            for z in PORTS:
                n += 1
                frame, cups, skin = arm(
                    side, z, tall=(z == -60 or (side == -1 and z == 260))
                )
                for label, parts in [
                    ("frame", frame),
                    ("suction cups", cups),
                    ("curved shell", skin),
                ]:
                    name = f"Pink tentacle {n} {label}"
                    if n > args.through:
                        continue
                    if name not in completed:
                        await checked(name, parts)
        await call("save_model", path=str(OUT / "Ship Kraken - Core.io"))
        if args.finish:
            assert args.through >= 6, "Finish requires all six tentacles"
            await call("save_model", path=str(OUT / "Ship Kraken - Core.mpd"))
            core = (await call("get_model_info"))["data"]
            if not (OUT / "core-instructions-v2").exists():
                exported = await call(
                    "export_instructions",
                    directory=str(OUT / "core-instructions-v2"),
                    previews=False,
                    allow_unverified=True,
                )
                assert exported["ok"], exported
            import rebuild_pirate_ship_checked as recipe

            checkpoint = OUT / "display-checkpoint.io"
            for phase in recipe.phases:
                if phase["allow_unverified_canvas"]:
                    await checked(
                        phase["name"], phase["parts"], allow_unverified_canvas=True
                    )
            for ext in ("io", "mpd"):
                await call("save_model", path=str(OUT / ("Ship Kraken - Pink." + ext)))
            display = (await call("get_model_info"))["data"]
            (OUT / "completion.json").write_text(
                json.dumps(dict(core=core, display=display), indent=2), encoding="utf8"
            )
            if not (OUT / "display-instructions-v2").exists():
                exported = await call(
                    "export_instructions",
                    directory=str(OUT / "display-instructions-v2"),
                    previews=False,
                    allow_unverified=True,
                    draft=True,
                )
                assert exported["ok"], exported
        if args.render:
            r = await c.call_tool(
                "render_model", dict(width=1500, height=1200, latitude=25, longitude=60)
            )
            for b in r.content:
                if b.type == "image":
                    (OUT / "preview.png").write_bytes(base64.b64decode(b.data))
        print((await call("get_model_info"))["data"], flush=True)


if __name__ == "__main__":
    asyncio.run(main())
