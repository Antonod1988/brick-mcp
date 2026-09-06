"""Repair the pirate ship through native-checked MCP steps; resume checkpoints."""

import argparse
import asyncio
import json
import tomllib
from pathlib import Path
from fastmcp import Client
from fastmcp.client.transports import StdioTransport
import build_pirate_ship as old

ROOT = Path(__file__).parent
OUT = ROOT / "output/pirate-ship-checked"
phases = []


def part(pn, color, x=0, y=0, z=0, r=old.I):
    return dict(part_number=pn, color=color, x=x, y=y, z=z, rotation_matrix=r)


def stage(
    name, parts, submodel="", allow_cautions=False, allow_unverified_canvas=False
):
    phases.append(
        dict(
            name=name,
            parts=parts,
            submodel=submodel,
            allow_cautions=allow_cautions,
            allow_unverified_canvas=allow_unverified_canvas,
        )
    )


stage("01 Central hull foundation", [part("2560", 70, y=72, z=-240)])
for index, z in enumerate((-80, 80, 240), 2):
    stage(
        f"{index:02d} Extend and lock hull",
        [part("2560", 70, y=72, z=z)]
        + [part("3034", 0, x, 64, z - 80, old.Y90) for x in (-140, 140)],
    )

stage(
    "05 Complete hull rim plates",
    [part("3020", 0, x, 64, z, old.Y90) for x in (-140, 140) for z in (-280, 280)],
)
stage(
    "06 Continuous structural side beams",
    [
        part("3007", 0, x, 40, z, old.Y90)
        for x in (-140, 140)
        for z in (-240, -80, 80, 240)
    ],
)
stage(
    "07 Lock bow to structural beams",
    [part("2557", 70, z=-440), part("2556", 6, z=-440)]
    + [part("3022", 0, x, 40, -340) for x in (-140, 140)]
    + [part("3034", 0, x, 32, -320, old.Y90) for x in (-140, 140)]
    + [part("3036", 70, x, 88, -320, old.Y90) for x in (-60, 60)],
)
stage(
    "08 Lock stern to structural beams",
    [part("2559", 70, z=460), part("2558", 6, z=460)]
    + [part("3022", 0, x, 40, 340) for x in (-140, 140)]
    + [part("3034", 0, x, 32, 320, old.Y90) for x in (-140, 140)]
    + [part("3028", 70, x, 88, 360, old.Y90) for x in (-60, 60)],
)
stage(
    "09 Floor supports for Technic keel",
    [
        part(pn, 70, x, 88, z, old.Y90)
        for x in (-60, 60)
        for pn, z in [("3034", -160), ("3020", -40), ("3034", 80), ("3020", 200)]
    ],
)
stage(
    "10 Continuous Technic keel beams",
    [part("3703", 0, x, 64, z, old.Y90) for x in (-70, 70) for z in (-160, 160)],
)
for index, z in enumerate((-240, -80, 80, 240), 11):
    stage(
        f"{index:02d} Supported lower gun deck",
        [part("3036", 19, x, 56, z, old.Y90) for x in (-60, 60)],
    )

for index, side in enumerate((-1, 1), 15):
    pieces = []
    r = old.Y270 if side < 0 else old.Y90
    barrel_r = [
        sum(
            r[row * 3 + k]
            * [1, 0, 0, 0, 0.965926, 0.258819, 0, -0.258819, 0.965926][k * 3 + col]
            for k in range(3)
        )
        for row in range(3)
        for col in range(3)
    ]
    for z in (-260, -160, -60, 60, 160, 260):
        pieces += [
            part("2527", 70, side * 80, 48, z, r),
            part("518", 8, side * 80 - 30 * r[2], 20, z - 30 * r[8], barrel_r),
        ]
    stage(f"{index:02d} Attached lower broadside guns", pieces)

stage(
    "17 Strong gunport piers",
    [
        part(pn, 70, x, 16, z, old.Y90)
        for x in (-140, 140)
        for pn, z in [
            ("3002", -210),
            ("3002", -110),
            ("3001", 0),
            ("3002", 110),
            ("3002", 210),
        ]
    ]
    + [part("3003", 70, x, 8, z) for x in (-140, 140) for z in (-300, 300)],
)
stage(
    "18 Gunport upper course",
    [
        part(pn, 70, x, -8, z, old.Y90)
        for x in (-140, 140)
        for pn, z in [
            ("3002", -210),
            ("3002", -110),
            ("3001", 0),
            ("3002", 110),
            ("3002", 210),
        ]
    ]
    + [
        part("3022", 70, x, y, z)
        for x in (-140, 140)
        for z in (-300, 300)
        for y in (0, -8)
    ],
)
for index, z in enumerate((-240, -80, 80, 240), 19):
    stage(
        f"{index:02d} Locked weather deck",
        [part("41539", 19, x, -16, z) for x in (-80, 80)],
    )

stage(
    "23 Forecastle supports on real hull studs",
    [part("3003", 70, x, y, -520) for x in (-60, 60) for y in (-24, -48)]
    + [part("3022", 70, x, -56, -520) for x in (-60, 60)]
    + [part("3003", 70, x, -40, -280) for x in (-60, 60)]
    + [part("3022", 70, x, y, -280) for x in (-60, 60) for y in (-48, -56)],
)
stage(
    "24 Forecastle platform",
    [
        part("3001", 70, x, y, -360)
        for x in (-40, 40)
        for y in (64, 40, 16, -8, -32, -56)
    ]
    + [part("3035", 19, x, -64, z, old.Y90) for x in (-40, 40) for z in (-480, -320)]
    + [part("3035", 19, x, -72, -400, old.Y90) for x in (-40, 40)],
)
stage(
    "25 Quarterdeck forward supports",
    [part("3003", 70, x, -40, 240) for x in (-100, 100)]
    + [part("3022", 70, x, y, 240) for x in (-100, 100) for y in (-48, -56)],
)
stage(
    "26 Quarterdeck pillars from internal floor",
    [
        part("3003", 70, x, y, 400)
        for x in (-60, 60)
        for y in (64, 40, 16, -8, -32, -56)
    ],
)
stage(
    "27 Quarterdeck aft supports",
    [part("3001", 70, x, y, 560, old.Y90) for x in (-120, 120) for y in (-24, -48)]
    + [part("3020", 70, x, -56, 560, old.Y90) for x in (-120, 120)]
    + [part("41539", 19, x, -64, z) for x in (-80, 80) for z in (240, 400, 560)]
    + [part("41539", 19, x, -72, z) for x in (-80, 80) for z in (320, 480)],
)
stage(
    "28 Level the raised decks",
    [part("3035", 19, x, -72, z) for x in (-80, 80) for z in (200, 600)]
    + [part("3031", 19, x, -72, z) for x in (-40, 40) for z in (-520, -280)],
)
for level, y in enumerate((-96, -120, -144), 29):
    side_rows = (
        [("3001", 400), ("3001", 480), ("3001", 560)]
        if level != 30
        else [("3003", 380), ("3001", 440), ("3001", 520), ("3003", 580)]
    )
    pieces = [
        part(pn, 70, x, y, z, old.Y90) for x in (-100, 100) for pn, z in side_rows
    ]
    if level == 31:
        pieces += [part("6112", 70, 0, y, 350)]
    else:
        pieces += [part("3010", 308, 0, y, 350)] + [
            part("3004", 70, x, y, 350) for x in (-100, -60, 60, 100)
        ]
    if level == 29:
        pieces += [part("3010", 70, x, y, 610) for x in (-80, 0, 80)]
    else:
        pieces += [part("3010", 46, x, y, 610) for x in (-60, 60)] + [
            part("3005", 14, x, y, 610) for x in (-110, -10, 10, 110)
        ]
    stage(f"{level:02d} Interlocked captain cabin", pieces)
stage(
    "32 Reinforced cabin roof",
    [part("41539", 70, x, -152, z) for x in (-80, 80) for z in (400, 560)]
    + [part("41539", 70, x, -160, 480) for x in (-80, 80)]
    + [part("3035", 70, x, -160, z) for x in (-80, 80) for z in (360, 600)],
)
stage(
    "33 Golden gallery rails",
    [
        part("30055", 14, x, -208, z, old.Y90)
        for x in (-150, 150)
        for z in (400, 480, 560)
    ]
    + [part("30055", 14, x, -208, z) for x in (-120, -40, 40, 120) for z in (350, 610)],
)
stage(
    "34 Three stern lanterns",
    [
        part(pn, color, x, y, 590)
        for x in (-110, 10, 110)
        for pn, color, y in [
            ("3005", 14, -184),
            ("3062b", 46, -208),
            ("4740", 14, -216),
        ]
    ],
)
for label, z, floor in [("Main Rig", 0, -24), ("Fore Rig", -300, -80)]:
    model = label + ".ldr"
    stage(label + " foundation", [part("41539", 70, 0, floor, z)], model)
    stage(label + " base", [part("4844b", 70, 0, floor - 8, z)], model)
    feet = [
        part("3794b", 0, x, floor - 8, z + dz, old.Y90)
        for x in (-10, 10)
        for dz in (-20, 20)
    ]
    feet += [
        part("60470b", 0, 0, floor - 16, z - 20),
        part("60470b", 0, 0, floor - 16, z + 20, old.Y180),
    ]
    stage(label + " shroud anchors", feet, model)
    stage(
        label + " braced middle section",
        [part("2537", 70, 0, floor - 552, z)]
        + [
            part("2541", 0, 0, floor - 284, z + dz, [1, 0, 0, 0, 0, 1, 0, -1, 0])
            for dz in (-40, 40)
        ],
        model,
        True,
    )
    stage(label + " upper section", [part("2538a", 70, 0, floor - 552, z)], model, True)
    stage("Install " + label, [part(model, 16)], allow_cautions=True)

label, z, floor = "Mizzen Rig", 260, -80
model = label + ".ldr"
stage(label + " foundation", [part("41539", 70, 0, floor, z)], model)
stage(label + " base", [part("4844b", 70, 0, floor - 8, z)], model)
feet = [part("3004", 0, x, floor - 24, z + dz) for x in (-60, 60) for dz in (-10, 10)]
feet += [part("3623", 0, x, floor - 32, z + dz) for x in (-50, 50) for dz in (-10, 10)]
feet += [
    part("60470b", 0, x, floor - 40, z + dz, old.I if dz < 0 else old.Y180)
    for x in (-40, 40)
    for dz in (-10, 10)
]
stage(label + " raised shroud anchors", feet, model)
stage(
    label + " braced upper mast",
    [part("2538a", 70, 0, floor - 215.25, z)]
    + [
        part("2541", 0, 0, floor - 308, z + dz, [1, 0, 0, 0, 0, 1, 0, -1, 0])
        for dz in (-30, 30)
    ],
    model,
    True,
)
stage("Install " + label, [part(model, 16)], allow_cautions=True)
phases[-1]["insert_at"] = 28  # Fit the mizzen base before the cabin roof overhang.

for label, z, floor in [("Main Rig", 0, -24), ("Fore Rig", -300, -80)]:
    model = label + ".ldr"
    y = floor - 374
    pieces = [
        part("48729b", 0, x, y, z - 40, [0, 0, -1, 1, 0, 0, 0, -1, 0])
        for x in (-20, 20)
    ]
    pieces += [part("24122", 0, x, y, z - 79, old.Y270) for x in (-20, 20)]
    pieces += [part("3708", 0, 0, y, z - 79)]
    pieces += [part("59443", 0, x, y, z - 79, old.Y90) for x in (-120, 120)]
    pieces += [part("3707", 0, x, y, z - 79) for x in (-200, 200)]
    stage(label + " lower Technic yard", pieces, model, True)

for label, z, floor in [("Main Rig", 0, -24), ("Fore Rig", -300, -80)]:
    model = label + ".ldr"
    top = floor - 552
    for title, y, bar_y in [
        ("middle", top - 151.2, top - 241.2),
        ("upper", top - 434.48, top - 424.48),
    ]:
        pieces = [
            part("30374", 0, 0, bar_y, z - 30),
            part("24122", 0, 0, y, z - 30, [0, 0, 1, 1, 0, 0, 0, 1, 0]),
            part("50451", 0, 0, y, z - 30),
        ]
        stage(label + " " + title + " Technic yard", pieces, model, True)
    flag_y = top - 454.5
    pieces = [part("63965", 0, 0, top - 344, z)]
    if label == "Main Rig":
        pieces += [
            part("59443", 0, 0, top - 446.5, z, old.X90),
            part("30374", 0, 0, top - 526.5, z),
        ]
        flag_y -= 80
    pieces += [
        part(
            "2525p31" if label == "Main Rig" else "2525",
            0 if label == "Main Rig" else 4,
            0,
            flag_y,
            z,
        )
    ]
    stage(label + " flag on bar fittings", pieces, model, True)

label, z, floor = "Mizzen Rig", 260, -80
model = label + ".ldr"
for title, y in [("lower", floor - 278), ("upper", floor - 578)]:
    pieces = [
        part("48729b", 0, x, y, z - 30, [0, 0, -1, 1, 0, 0, 0, -1, 0])
        for x in (-20, 20)
    ]
    pieces += [part("24122", 0, x, y, z - 69, old.Y270) for x in (-20, 20)]
    pieces += [part("50451", 0, 0, y, z - 69)]
    stage(label + " " + title + " Technic yard", pieces, model, True)
top = floor - 215.25
stage(
    label + " flag on bar fitting",
    [part("63965", 0, 0, top - 344, z), part("2525", 4, 0, top - 454.5, z)],
    model,
    True,
)

for side in (-1, 1):
    r = old.Y270 if side < 0 else old.Y90
    barrel_r = [
        sum(
            r[row * 3 + k]
            * [1, 0, 0, 0, 0.965926, 0.258819, 0, -0.258819, 0.965926][k * 3 + col]
            for k in range(3)
        )
        for row in range(3)
        for col in range(3)
    ]
    pieces = []
    for z in (-160, 120):
        pieces += [
            part("2527", 70, side * 80, -24, z, r),
            part("518", 8, side * 80 - 30 * r[2], -52, z - 30 * r[8], barrel_r),
        ]
    stage("Attached waist guns " + str(side), pieces, allow_cautions=True)
stage(
    "Protective deck bulwarks",
    [
        part(pn, 70, x, -40, z, old.Y90)
        for x in (-150, 150)
        for pn, z in [("3008", -160), ("3008", 0), ("3010", 120)]
    ],
    allow_cautions=True,
)
stage(
    "Quarterdeck access stairs",
    [part("3003", 70, 0, y, z) for y, z in [(-40, 100), (-40, 140), (-64, 140)]],
    allow_cautions=True,
)
stage(
    "Forecastle access stairs",
    [part("3003", 70, 0, y, z) for y, z in [(-40, -180), (-40, -220), (-64, -220)]],
    allow_cautions=True,
)
phases[-1]["insert_at"] = 36
stage(
    "Steering wheel with native pin bearing",
    [part("3003", 70, 0, y, 200) for y in (-104, -128)]
    + [part("3700", 0, 0, -152, 190), part("4790", 70, 0, -142, 160, old.X90)],
    allow_cautions=True,
)
stage(
    "Technic bowsprit bearings",
    [part("32064a", 70, 0, -96, z) for z in (-530, -490)],
    allow_cautions=True,
)
stage(
    "Locked Technic bowsprit",
    [part("3708", 70, 0, -86, z, old.Y90) for z in (-590, -830)]
    + [
        part("59443", 0, 0, -86, -710),
        part("3713", 0, 0, -86, -550),
        part("32123a", 0, 0, -86, -475),
    ],
    allow_cautions=True,
)
stage(
    "Anchors on real bar clips",
    [part("60470b", 0, x, -80, -510) for x in (-60, 60)]
    + [part("30374", 0, x, -78, -530, old.Z90) for x in (-40, 120)]
    + [
        part("2564", 0, x, -78, -530, [0, -1, 0, 0, 0, -1, 1, 0, 0])
        for x in (-116, 116)
    ],
    allow_cautions=True,
)
stage(
    "Swivelling stern rudder",
    [part("2335", 0, 0, 72, 596, old.Y90)],
    allow_cautions=True,
)
stage(
    "Technic anchor windlass supports",
    [part("3004", 70, x, -96, -460, old.Y90) for x in (-50, 50)]
    + [part("3700", 0, x, -120, -460, old.Y90) for x in (-50, 50)],
    allow_cautions=True,
)
stage(
    "Technic drum gear and crank",
    [part("3708", 0, 0, -110, -460), part("3941", 70, 12, -110, -460, old.Z90)]
    + [part("3713", 0, x, -110, -460, old.Y90) for x in (-70, 70)]
    + [part("3648b", 8, -95, -110, -460, old.Y90), part("2780", 14, -105, -120, -450)],
    allow_cautions=True,
)

for label, z, floor in [
    ("Main Rig", 0, -24),
    ("Fore Rig", -300, -80),
    ("Mizzen Rig", 260, -80),
]:
    model = label + ".ldr"
    mounts = (
        [(floor - 278, z - 69, 100), (floor - 578, z - 69, 100)]
        if label == "Mizzen Rig"
        else [
            (floor - 374, z - 79, 160),
            (floor - 703.2, z - 30, 100),
            (floor - 986.48, z - 30, 100),
        ]
    )
    pieces = []
    for y, zz, half in mounts:
        for x in (-half, half):
            pieces += [
                part("24122", 0, x, y, zz, old.Y90),
                part("48729b", 0, x, y, zz - 39, old.X90),
            ]
    stage(label + " sail mounting pins", pieces, model, True)

for label, z, floor in [
    ("Main Rig", 0, -24),
    ("Fore Rig", -300, -80),
    ("Mizzen Rig", 260, -80),
]:
    sails = (
        [("96714c01", floor - 278, z - 69), ("96714c01", floor - 578, z - 69)]
        if label == "Mizzen Rig"
        else [
            ("64991c01", floor - 374, z - 79),
            ("96714c01", floor - 703.2, z - 30),
            ("96714c01", floor - 986.48, z - 30),
        ]
    )
    for i, (pn, y, zz) in enumerate(sails, 1):
        stage(
            f"Canvas {label} {i}: unverified fabric",
            [part(pn, 15, 0, y, zz - 24)],
            allow_cautions=True,
            allow_unverified_canvas=True,
        )


async def main():
    args = argparse.ArgumentParser()
    args.add_argument("--through", type=int, default=999)
    args.add_argument("--replace-step", action="append", default=[])
    args.add_argument("--with-sails", action="store_true")
    options = args.parse_args()
    limit = options.through
    OUT.mkdir(parents=True, exist_ok=True)
    cfg = tomllib.loads(
        (Path.home() / ".codex/config.toml").read_text(encoding="utf8")
    )["mcp_servers"]["brick"]
    async with Client(
        StdioTransport(
            command=cfg["command"], args=cfg["args"], env=cfg["env"], keep_alive=False
        ),
        timeout=600,
    ) as client:

        async def call(tool, **kw):
            r = await client.call_tool(tool, kw)
            return json.loads(next(c.text for c in r.content if c.type == "text"))

        path = OUT / (
            "display-checkpoint.io" if options.with_sails else "checkpoint.io"
        )
        load_path = path if path.exists() else OUT / "checkpoint.io"
        r = (
            await call("open_model", path=str(load_path))
            if load_path.exists()
            else await call("new_model", name="Pirate Ship checked")
        )
        assert r["ok"], r
        info = (await call("get_model_info"))["data"]
        known = set(info["submodels"])
        completed = set()
        for model in known:
            completed.update(
                (model, s["name"])
                for s in (await call("get_steps", submodel=model))["data"]
            )
        for index, phase in enumerate(phases):
            if index > limit:
                break
            if phase["allow_unverified_canvas"] and not options.with_sails:
                continue
            model = phase["submodel"] or info["root_submodel"]
            if (model, phase["name"]) in completed:
                if phase["name"] not in options.replace_step:
                    continue
                phase = dict(phase)
                existing = (await call("get_steps", submodel=model))["data"]
                phase["insert_at"] = next(
                    s["step_index"] for s in existing if s["name"] == phase["name"]
                )
                phase["replace_existing"] = True
            if model not in known:
                r = await call("create_submodel", name=model)
                assert r["ok"], r
                known.add(model)
            r = await call(
                "apply_step",
                **phase,
                preview=False,
                allow_unverified=True,
                save_path=str(path),
            )
            if not r["ok"]:
                (OUT / "failure.json").write_text(
                    json.dumps(r, indent=2), encoding="utf8"
                )
                print("REJECTED", phase["name"], json.dumps(r)[:1300], flush=True)
                return
            (OUT / f"step-{index+1:02d}.json").write_text(
                json.dumps(r["data"], indent=2), encoding="utf8"
            )
            print(
                "CHECKED",
                phase["name"],
                r["data"]["studio_check"]["status"],
                flush=True,
            )
        stem = (
            "Pirate Ship - with Sails" if options.with_sails else "Pirate Ship - Core"
        )
        for extension in ("io", "mpd"):
            r = await call("save_model", path=str(OUT / (stem + "." + extension)))
            assert r["ok"], r
        print((await call("get_model_info"))["data"], flush=True)


if __name__ == "__main__":
    asyncio.run(main())
