"""Build the garden cottage using only the configured brick MCP tools."""

import asyncio
import csv
import json
import time
import tomllib
from datetime import datetime
from pathlib import Path

from fastmcp import Client
from fastmcp.client.transports import StdioTransport

ROOT = Path(__file__).parent
IDENTITY = [1, 0, 0, 0, 1, 0, 0, 0, 1]
TURN = [0, 0, -1, 0, 1, 0, 1, 0, 0]
plan = []


def part(phase, number, color, x, y, z, rotated=False):
    plan.append(dict(phase=phase, part_number=str(number), color=color, x=x, y=y, z=z,
                     rotation_matrix=TURN if rotated else IDENTITY))


part("01 Ground and floor", 3334, 2, 0, 0, 0)
for x in (-140, -60, 20):
    for z in (-20, 20, 60, 100):
        part("01 Ground and floor", 3020, 71, x, -8, z)
part("01 Ground and floor", 3020, 71, -60, -8, -60)
for z in (-100, -140):
    part("01 Ground and floor", "3068b", 71, -60, -8, z)

for row in range(6):
    phase = f"02 Walls course {row + 1}"
    y = -32 - 24 * row
    # Front: framed glazing flanks the central two-stud door.
    for center in (-140, 20):
        for x in (center - 30, center + 30):
            part(phase, 3005, 15 if row in (1, 2, 3, 4) else 19, x, y, -30)
        part(phase, 3004, 47 if row in (2, 3) else 15 if row in (1, 4) else 19,
             center, y, -30)
    for x in (-90, -30):
        part(phase, 3005, 19, x, y, -30)
    part(phase, 3004, 70 if row < 3 else 47 if row == 3 else 19, -60, y, -30)
    # Side windows and solid rear wall. Corners belong to the front/rear rows.
    for x in (-170, 50):
        for z in (0, 40, 80):
            part(phase, 3004, 47 if z == 40 and row in (2, 3) else 19, x, y, z, True)
    for x in (-140, -60, 20):
        part(phase, 3010, 19, x, y, 110)

# Five connected plate tiers and smooth edge tiles form the shallow pitched roof.
# Every layer covers the previous layer's centre; tiles fill only exposed ledges.
for level, depth in enumerate((10, 8, 6, 4, 2)):
    phase = f"03 Roof tier {level + 1}"
    y = -160 - 8 * level
    for z in range(40 - depth * 10 + 20, 40 + depth * 10, 40):
        part(phase, 3020, 320, -160, y, z)
        part(phase, 3020, 320, -80, y, z)
        part(phase, 3795, 320, 20, y, z)
    if depth > 2:
        for z in (40 - depth * 10 + 10, 40 + depth * 10 - 10):
            part(phase, 4162, 320, -120, y - 8, z)
            part(phase, 6636, 320, 20, y - 8, z)
    else:
        for x in (-160, -80, 0):
            part(phase, 87079, 320, x, y - 8, 40)
        part(phase, "3068b", 320, 60, y - 8, 40)

# Leave studs exposed under the chimney instead of resting it on a smooth tile.
plan = [p for p in plan if not (p['part_number'] == '87079' and p['x'] == -160)]
part("04 Chimney", 3020, 320, -160, -200, 40)
for y in (-224, -248):
    part("04 Chimney", 3003, 72, -160, y, 40)
part("04 Chimney", 3031, 72, -160, -256, 40)
part("04 Chimney", "3068b", 0, -160, -264, 40)

for y in (-24, -48, -72):
    part("05 Garden tree", 3005, 70, 150, y, 70)
for number, color, y in [(3031, 2, -80), (3001, 10, -104), (3032, 2, -112),
                          (3003, 10, -136), (3031, 2, -144), (3022, 10, -152)]:
    part("05 Garden tree", number, color, 160, y, 80)

part("06 Flowers and bench", 3032, 70, 140, -8, -90)
for i, x in enumerate((90, 130, 170)):
    for j, z in enumerate((-110, -70)):
        part("06 Flowers and bench", 3005, 2, x, -32, z)
        part("06 Flowers and bench", 6141, (14, 15, 13)[(i + j) % 3], x, -40, z)
for x in (130, 190):
    part("06 Flowers and bench", 3005, 70, x, -24, -10)
part("06 Flowers and bench", 3020, 70, 160, -32, 0)
part("06 Flowers and bench", 3010, 70, 160, -56, 10)
part("06 Flowers and bench", 2431, 70, 160, -40, -10)


async def main():
    config = tomllib.loads((Path.home() / ".codex/config.toml").read_text(encoding="utf8"))["mcp_servers"]["brick"]
    output = ROOT / "output" / ("garden-cottage-" + datetime.now().strftime("%Y%m%d-%H%M%S"))
    output.mkdir(parents=True)
    timings = []
    async with Client(StdioTransport(command=config["command"], args=config["args"],
                                      env=config["env"], keep_alive=False), timeout=120) as client:
        async def call(tool_name, **args):
            started = time.monotonic()
            result = await client.call_tool(tool_name, args)
            data = json.loads(next(c.text for c in result.content if c.type == "text"))
            timings.append(dict(tool=tool_name, seconds=round(time.monotonic() - started, 3)))
            assert not result.is_error and data["ok"], data
            return data.get("data")

        footprints = {}
        for pn in sorted({p["part_number"] for p in plan}):
            await call("get_part_details", part_number=pn)
            footprints[pn] = await call("get_part_footprint", part_number=pn)
        for color in sorted({p["color"] for p in plan}):
            await call("get_color_info", color_code=color)
        (output / "footprints.json").write_text(json.dumps(footprints, indent=2), encoding="utf8")
        (output / "placement-plan.json").write_text(json.dumps(plan, indent=2), encoding="utf8")
        with (output / "placement-plan.csv").open("w", newline="", encoding="utf8") as fh:
            writer = csv.DictWriter(fh, fieldnames=plan[0].keys())
            writer.writeheader()
            writer.writerows(plan)
        await call("new_model", name="Garden Cottage")
        for phase in dict.fromkeys(p["phase"] for p in plan):
            calls = [{"tool": "add_part", "args": {k: v for k, v in p.items() if k != "phase"}}
                     for p in plan if p["phase"] == phase]
            result = await call("batch", calls=calls + [{"tool": "add_step"}])
            warnings = [r for r in result["results"] if r.get("data", {}).get("overlap_warnings")]
            assert not warnings, (phase, warnings)
            print(f"{phase}: {len(calls)} parts", flush=True)
        overlaps = await call("check_overlaps")
        assert overlaps["overlap_count"] == 0, overlaps
        parts = await call("list_parts")
        assert len(parts) == len(plan)
        for suffix in ("io", "ldr"):
            await call("save_model", path=str(output / f"Garden Cottage.{suffix}"))
        bom = await call("get_bom")
        await call("open_model", path=str(output / "Garden Cottage.io"))
        assert await call("get_bom") == bom
        report = dict(parts=len(parts), unique_parts=len(footprints), overlaps=overlaps,
                      tools_called=len(timings), timings=timings, bom=bom)
        (output / "build-report.json").write_text(json.dumps(report, indent=2), encoding="utf8")
        print(json.dumps(dict(output=str(output), parts=len(parts), overlaps=0, calls=len(timings))))


if __name__ == "__main__":
    asyncio.run(main())
