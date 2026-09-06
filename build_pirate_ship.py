"""LEGO adaptation of pirate-ship/pirate_ship.blend, authored through brick MCP."""

import argparse
import asyncio
import json
import math
import time
import tomllib
from pathlib import Path

from fastmcp import Client
from fastmcp.client.transports import StdioTransport

ROOT = Path(__file__).parent
I = [1, 0, 0, 0, 1, 0, 0, 0, 1]
Y90 = [0, 0, -1, 0, 1, 0, 1, 0, 0]
Y180 = [-1, 0, 0, 0, 1, 0, 0, 0, -1]
Y270 = [0, 0, 1, 0, 1, 0, -1, 0, 0]
X90 = [1, 0, 0, 0, 0, -1, 0, 1, 0]
Z90 = [0, -1, 0, 1, 0, 0, 0, 0, 1]
stages = []


def stage(name, model="", preview=False):
    stages.append(dict(name=name, model=model, parts=[], preview=preview))


def add(number, color, x=0, y=0, z=0, r=None):
    stages[-1]["parts"].append(
        dict(
            part_number=str(number), color=color, x=x, y=y, z=z, rotation_matrix=r or I
        )
    )


stage("01 Curved hull sections")
add("2557c01", 70, z=-440)
for z in (-240, -80, 80, 240):
    add("2560", 70, y=72, z=z)
add("2559c01", 70, z=460)

stage("02 Technic keel frame")
for x in (-70, 70):
    for z in (-240, -80, 80, 240):
        for y in (112, 104):
            add("3023", 0, x, y, z, Y90)
    for z in (-160, 160):
        add("3703", 0, x, 80, z, Y90)

stage("03 Lower gun deck")
for x in (-60, 60):
    for z in (-240, -80, 80, 240):
        add("3036", 19, x, 72, z, Y90)

stage("04 Black waterline strake")
for x in (-150, 150):
    for z in (-240, -80, 80, 240):
        add("3008", 0, x, 48, z, Y90)

stage("05 Twelve gunport frames")
for x in (-150, 150):
    for y in (24, 0):
        for z, pn in [
            (-300, "3004"),
            (-210, "3622"),
            (-110, "3622"),
            (0, "3010"),
            (110, "3622"),
            (210, "3622"),
            (300, "3004"),
        ]:
            add(pn, 70, x, y, z, Y90)

stage("06 Lower broadside battery", preview=True)
for x, r in [(90, Y90), (-90, Y270)]:
    for z in (-260, -160, -60, 60, 160, 260):
        add("2527c01", 70, x, 64, z, r)

stage("07 Weather deck and black rim")
for x in (-80, 80):
    for z in (-240, -80, 80, 240):
        add("41539", 19, x, -8, z)
for x in (-150, 150):
    for z in (-240, -80, 80, 240):
        add("3460", 0, x, -16, z, Y90)

stage("08 Four waist guns")
for x, r in [(90, Y90), (-90, Y270)]:
    for z in (-160, 80):
        add("2527c01", 70, x, -16, z, r)

stage("09 Raised forecastle and quarterdeck")
for x in (-60, 60):
    for z in (-280, -400, 240):
        add("3003", 70, x, -32, z)
        for y in (-40, -48):
            add("3022", 70, x, y, z)
    for z in (400, 560):
        for y in (-24, -48):
            add("3003", 70, x, y, z)
    for z in (240, 400, 560):
        add("3036", 19, x, -56, z, Y90)
for x in (-40, 40):
    add("3035", 19, x, -56, -400, Y90)
for z in (-300, -260):
    add("3034", 19, 0, -56, z)

stage("10 Captain cabin and golden stern windows")
for y in (-80, -104, -128):
    for x in (-110, 110):
        for z in (380, 460, 540):
            add("3010", 70, x, y, z, Y90)
    if y == -80:
        for x in (-80, 0, 80):
            add("3010", 70, x, y, 590)
    else:
        for x in (-60, 60):
            add("3010", 46, x, y, 590)
        for x in (-110, -10, 10, 110):
            add("3005", 14, x, y, 590)
    for x in (-70, 70):
        add("3622", 70, x, y, 350)
    add("3010", 308, 0, y, 350)

stage("11 Stern balcony and roof")
for z in (360, 400, 440, 480, 520, 560, 600):
    add("3034", 70, -60, -136, z)
    add("3795", 70, 80, -136, z)
for x in (-130, 130):
    for z in (400, 480, 560):
        add("30055", 14, x, -184, z, Y90)
for x in (-80, 0, 80):
    add("30055", 14, x, -184, 610)

stage("12 Three stern lanterns")
for x in (-100, 0, 100):
    add("3022", 14, x, -192, 600)
    add("3062b", 46, x, -216, 600)
    add("4740", 14, x, -224, 600)

stage("13 Bulwarks and forecastle rails")
for x in (-150, 150):
    for z, pn in [(-210, "3622"), (-40, "6111"), (130, "3622")]:
        add(pn, 70, x, -40, z, Y90)
for x in (-70, 70):
    for z in (-420, -340):
        add("30055", 70, x, -104, z, Y90)
for x in (-110, 110):
    add("30055", 70, x, -104, 220, Y90)

stage("14 Helm with Technic axle and gear")
for y in (-80, -104, -128):
    add("3003", 70, 0, y, 220)
add("3700", 0, 0, -152, 220)
add("3706", 0, 0, -140, 220, Y90)
add("4790", 70, 0, -140, 180, X90)
add("3648", 14, 0, -140, 246)
add("3713", 0, 0, -140, 264)

stage("15 Technic anchor windlass")
for x in (-50, 50):
    add("3004", 70, x, -80, -380, Y90)
    add("3700", 0, x, -104, -380, Y90)
add("3708", 0, 0, -92, -380)
for x in (0, 24):
    add("3941", 70, x, -92, -380, Z90)
add("3648", 0, 85, -92, -380, Y90)
add("3713", 14, 107, -92, -380, Y90)
add("32524", 0, -85, -92, -380)
add("2780", 14, -85, -92, -440)

stage("16 Bowsprit and anchors", preview=True)
add("6067", 70, 0, -64, -470)
# Axles follow a rising bowsprit; X-axis of the axle follows negative ship Z.
slope = math.radians(14)
axis = (0, -math.sin(slope), -math.cos(slope))
rod_r = [axis[0], 1, 0, axis[1], 0, -math.cos(slope), axis[2], 0, math.sin(slope)]
for t in (90, 330):
    add("3708", 70, 0, -72 + t * axis[1], -490 + t * axis[2], rod_r)
for t in (210,):
    add(
        "59443",
        0,
        0,
        -72 + t * axis[1],
        -490 + t * axis[2],
        [
            1,
            0,
            0,
            0,
            -math.cos(slope),
            -math.sin(slope),
            0,
            math.sin(slope),
            -math.cos(slope),
        ],
    )
anchor_r = [0, -1, 0, 0, 0, -1, 1, 0, 0]
for side in (-1, 1):
    add("2564", 0, side * 170, -8, -430, anchor_r)


def rig(name, z, deck_y, middle, sails, crow_y, flag_y, flag_part):
    stage(name + " 01 Mast and Technic topmast", name)
    base = deck_y - 8
    add("4844b", 70, 0, base, z)
    top = base - 540 if middle else base - 214
    if middle:
        add("2537", 70, 0, top, z)
    add("2538a", 70, 0, top, z)
    add(
        "3708" if name == "Main Rig" else "3706",
        0,
        0,
        flag_y + (80 if name == "Main Rig" else 48),
        z,
        Z90,
    )
    add("59443", 0, 0, top - 372, z, X90)
    stage(name + " 02 Crow nest and shrouds", name)
    if crow_y:
        for dz in (-40, 40):
            add("3795", 0, 0, crow_y, z + dz)
        for x in (-40, 40):
            add("3022", 0, x, crow_y, z)
        for dz in (-50, 50):
            add("30055", 0, 0, crow_y - 48, z + dz)
        for x in (-50, 50):
            add("30055", 0, x, crow_y - 48, z, Y90)
    for side in (-1, 1):
        a = math.radians(12.5)
        ss = math.sin(a) * side
        cc = math.cos(a)
        rr = [0, -cc, -ss, 0, ss, -cc, 1, 0, 0]
        add("2541", 0, side * 90, deck_y - 274 * cc - 2, z + 40, rr)
    for index, (sail_pn, sy) in enumerate(sails):
        stage(
            name + f" {index+3:02d} Technic yard and sail",
            name,
            preview=index == len(sails) - 1,
        )
        yy, zz = sy - 12, z - 40
        if sail_pn == "64991c01":
            add("32278", 0, -140, yy, zz - 10, Y90)
            add("32278", 0, 140, yy, zz + 10, Y90)
            add("2780", 0, 0, yy, zz, Y90)
        else:
            add("3708", 0, 0, yy, zz)
            for side in (-1, 1):
                add("4519", 0, side * 150, yy, zz)
                add("59443", 0, side * 120, yy, zz, Y90)
        add("6536", 0, 0, yy, zz)
        add(sail_pn, 15, 0, sy, z - 60)
    stage(name + " Flag", name)
    add(flag_part, 0 if "p31" in flag_part else 4, 0, flag_y, z)
    stage("Install " + name, preview=name == "Mizzen Rig")
    add(name + ".ldr", 16)


rig(
    "Main Rig",
    0,
    -8,
    True,
    [("64991c01", -320), ("96714c01", -620), ("96714c01", -900)],
    -564,
    -1104,
    "2525p31",
)
rig(
    "Fore Rig",
    -300,
    -56,
    True,
    [("64991c01", -352), ("96714c01", -625), ("96714c01", -850)],
    -612,
    -1016,
    "2525",
)
rig(
    "Mizzen Rig",
    300,
    -56,
    False,
    [("96714c01", -315), ("96714c01", -590)],
    None,
    -748,
    "2525",
)

stage("16b Technic forestay and spanker boom")
for t in (120, 360, 600):
    add(
        "3708",
        0,
        0,
        -612 + 0.6 * t,
        -300 - 0.8 * t,
        [0, 1, 0, 0.6, 0, -0.8, -0.8, 0, -0.6],
    )
for t in (240, 480):
    add(
        "59443",
        0,
        0,
        -612 + 0.6 * t,
        -300 - 0.8 * t,
        [1, 0, 0, 0, -0.8, 0.6, 0, -0.6, -0.8],
    )
add("3708", 70, 0, -232, 460, Y90)
add("3706", 70, 0, -232, 640, Y90)
add("59443", 0, 0, -232, 580)

stage("17 Jib and mizzen spanker", preview=True)
add("85651c01", 15, 0, -474, -480)
add("85651c01", 15, 0, -620, 340, Y180)

stage("18 Hinged rudder")
add("3937", 0, 0, -16, 610)
add("3938", 0, 0, -16, 610)
add("32524", 0, 0, 42, 625, X90)
add("3795", 0, 0, 40, 640, [0, 0, 1, 1, 0, 0, 0, 1, 0])
add("3706", 0, 0, -6, 625, Z90)


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--through", type=int, default=999)
    parser.add_argument("--output", default=str(ROOT / "output" / "pirate-ship-lego"))
    args = parser.parse_args()
    out = Path(args.output).resolve()
    out.mkdir(parents=True, exist_ok=True)
    (out / "placement-plan.json").write_text(
        json.dumps(stages, indent=2), encoding="utf8"
    )
    (out / "source.json").write_text(
        json.dumps(
            {
                "blender_file": r"D:\pythonProject4\pirate-ship\pirate_ship.blend",
                "source_objects": 898,
                "source_features": [
                    "three masts",
                    "raised stern",
                    "cream sails",
                    "16 guns",
                    "black strake",
                    "stern lanterns",
                ],
                "target": "58-stud hull, Technic rigging and mechanisms",
                "kraken": "deferred by user",
            },
            indent=2,
        ),
        encoding="utf8",
    )
    config = tomllib.loads(
        (Path.home() / ".codex/config.toml").read_text(encoding="utf8")
    )["mcp_servers"]["brick"]
    log = (
        json.loads((out / "progress.json").read_text())
        if (out / "progress.json").exists()
        else []
    )
    async with Client(
        StdioTransport(
            command=config["command"],
            args=config["args"],
            env=config["env"],
            keep_alive=False,
        ),
        timeout=600,
    ) as client:

        async def call(tool, **kw):
            r = await client.call_tool(tool, kw)
            d = json.loads(next(c.text for c in r.content if c.type == "text"))
            if not d["ok"]:
                (out / "failure.json").write_text(
                    json.dumps({"tool": tool, "args": kw, "result": d}, indent=2),
                    encoding="utf8",
                )
                raise RuntimeError(f"{tool} failed: {out/'failure.json'}")
            return d.get("data")

        if (out / "checkpoint.io").exists():
            await call("open_model", path=str(out / "checkpoint.io"))
        else:
            await call("new_model", name="Pirate Ship LEGO")
        known = set((await call("get_model_info"))["submodels"])
        completed = set()
        for model in known:
            completed.update(
                (model, s["name"]) for s in await call("get_steps", submodel=model)
            )
        palette = {}
        for pn in sorted(
            {
                p["part_number"]
                for s in stages
                for p in s["parts"]
                if not p["part_number"].endswith(".ldr")
            }
        ):
            palette[pn] = await call("get_part_footprint", part_number=pn)
        (out / "part-geometry.json").write_text(
            json.dumps(palette, indent=2), encoding="utf8"
        )
        for i, s in enumerate(stages):
            if i > args.through:
                break
            model = s["model"] + ".ldr" if s["model"] else "Pirate Ship LEGO.ldr"
            if (model, s["name"]) in completed:
                continue
            if model not in known:
                await call("create_submodel", name=s["model"])
                known.add(model)
            t = time.monotonic()
            d = await call(
                "apply_step",
                name=s["name"],
                parts=s["parts"],
                submodel=model,
                allow_unverified=True,
                preview=s["preview"],
                save_path=str(out / "checkpoint.io"),
            )
            v = d["validation"]
            log.append(
                dict(
                    index=i,
                    model=model,
                    name=s["name"],
                    placements=len(s["parts"]),
                    status=v["status"],
                    confirmed_overlaps=len(v["overlaps"]),
                    unknown=len(v["unknown"]),
                    previews=d["preview_paths"],
                    seconds=round(time.monotonic() - t, 2),
                )
            )
            (out / "progress.json").write_text(
                json.dumps(log, indent=2), encoding="utf8"
            )
            print(json.dumps(log[-1]), flush=True)
        await call("save_model", path=str(out / "Pirate Ship.io"))
        await call("save_model", path=str(out / "Pirate Ship.mpd"))
        info = await call("get_model_info")
        (out / "model-info.json").write_text(
            json.dumps(info, indent=2), encoding="utf8"
        )
        print("MODEL " + json.dumps(info), flush=True)


if __name__ == "__main__":
    asyncio.run(main())
