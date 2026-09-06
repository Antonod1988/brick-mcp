"""Rebuild the original 220-part diorama through checked, previewed MCP steps."""

import asyncio
import json
import sys
import tempfile
import tomllib
from pathlib import Path

from fastmcp import Client
from fastmcp.client.transports import StdioTransport

ROOT = Path(__file__).parent


async def main():
    from build_cottage import plan as original
    config = tomllib.loads(
        (Path.home() / ".codex/config.toml").read_text(encoding="utf8")
    )["mcp_servers"]["brick"]
    resume = len(sys.argv) > 1
    out = (
        Path(sys.argv[1]).resolve()
        if resume
        else Path(tempfile.mkdtemp(prefix="cottage-instructions-", dir=ROOT / "output"))
    )
    log = (
        json.loads((out / "progress.json").read_text(encoding="utf8")) if resume else []
    )
    existing_models, completed = set(), set()
    async with Client(
        StdioTransport(
            command=config["command"],
            args=config["args"],
            env=config["env"],
            keep_alive=False,
        ),
        timeout=300,
    ) as client:

        async def call(tool, **args):
            if tool == "new_model" and resume:
                return {}
            if tool == "create_submodel" and args["name"] + ".ldr" in existing_models:
                return {"submodel": args["name"] + ".ldr"}
            result = await client.call_tool(tool, args)
            data = json.loads(next(c.text for c in result.content if c.type == "text"))
            if not data["ok"]:
                (out / "failure.json").write_text(
                    json.dumps(data, indent=2, ensure_ascii=False), encoding="utf8"
                )
                raise RuntimeError(f"{tool} failed; details: {out/'failure.json'}")
            return data.get("data")

        async def step(name, parts, model=""):
            if (model or "Garden Cottage.ldr", name) in completed:
                return
            clean = [{k: v for k, v in p.items() if k != "phase"} for p in parts]
            data = await call(
                "apply_step",
                name=name,
                parts=clean,
                submodel=model,
                preview=True,
                save_path=str(out / "checkpoint.io"),
            )
            log.append(dict(assembly=model or "Garden Cottage.ldr", name=name, **data))
            (out / "progress.json").write_text(
                json.dumps(log, indent=2, ensure_ascii=False), encoding="utf8"
            )
            print(
                f"{model or 'Main'} | {name} | {len(parts)} placements | {data['validation']['status']}",
                flush=True,
            )

        def placement(pn, color, x=0, y=0, z=0):
            return dict(part_number=pn, color=color, x=x, y=y, z=z)

        async def chunks(name, parts, model="", size=8):
            for i in range(0, len(parts), size):
                await step(f"{name} {i//size+1}", parts[i : i + size], model)

        if resume:
            await call("open_model", path=str(out / "checkpoint.io"))
            existing_models.update((await call("get_model_info"))["submodels"])
            for model in existing_models:
                completed.update(
                    (model, stage["name"])
                    for stage in await call("get_steps", submodel=model)
                )
            print(f"Resuming {len(completed)} saved steps", flush=True)
        await call("new_model", name="Garden Cottage")
        ground = [p for p in original if p["phase"].startswith("01")]
        await step("Green base", ground[:1])
        await chunks("House floor", ground[1:13], size=6)
        await step("Entrance and path", ground[13:])
        for row in range(6):
            walls = [p for p in original if p["phase"] == f"02 Walls course {row+1}"]
            await chunks(f"Wall course {row+1}", walls, size=9)

        await call("create_submodel", name="Chimney")
        chimney = [p for p in original if p["phase"].startswith("04")]
        await step("Chimney body", chimney[:3], "Chimney.ldr")
        await step("Chimney cap", chimney[3:], "Chimney.ldr")

        await call("create_submodel", name="Roof")
        for level in range(5):
            roof = [
                dict(p) for p in original if p["phase"] == f"03 Roof tier {level+1}"
            ]
            # Alternate plate seams to bond the roof into one connected assembly.
            if level % 2:
                for p in roof:
                    if (
                        p["part_number"] in ("3020", "3795")
                        and p["y"] == -160 - 8 * level
                    ):
                        p["part_number"], p["x"] = {
                            -160: ("3795", -140),
                            -80: ("3020", -40),
                            20: ("3020", 40),
                        }[p["x"]]
            await chunks(f"Roof tier {level+1}", roof, "Roof.ldr", size=8)
        await step("Install chimney", [placement("Chimney.ldr", 16)], "Roof.ldr")
        await step("Install complete roof", [placement("Roof.ldr", 16)])

        await call("create_submodel", name="Tree")
        tree = [p for p in original if p["phase"].startswith("05")]
        await step("Tree trunk", tree[:3], "Tree.ldr")
        await step("Lower canopy", tree[3:6], "Tree.ldr")
        await step("Upper canopy", tree[6:], "Tree.ldr")
        await step("Plant tree", [placement("Tree.ldr", 16)])

        await call("create_submodel", name="Flower")
        await step("Green stem", [placement("3005", 2, y=-24)], "Flower.ldr")
        await step("Flower head", [placement("6141", 16, y=-32)], "Flower.ldr")
        await call("create_submodel", name="Flowerbed")
        await step(
            "Soil plate", [placement("3032", 70, 140, -8, -100)], "Flowerbed.ldr"
        )
        for j, z in enumerate((-130, -90)):
            await step(
                f"Flower row {j+1}",
                [
                    placement("Flower.ldr", (14, 15, 13)[(i + j) % 3], x, -8, z)
                    for i, x in enumerate((90, 130, 170))
                ],
                "Flowerbed.ldr",
            )
        await step("Place flowerbed", [placement("Flowerbed.ldr", 16)])

        await call("create_submodel", name="Bench")
        bench = [p for p in original if p["phase"].startswith("06")][-5:]
        await step("Bench legs and seat", bench[:3], "Bench.ldr")
        await step("Backrest and smooth seat", bench[3:], "Bench.ldr")
        await step("Place bench", [placement("Bench.ldr", 16)])
        info = await call("get_model_info")
        assert info["total_part_count"] == 220, info
        await call("save_model", path=str(out / "Garden Cottage.io"))
        await call("open_model", path=str(out / "Garden Cottage.io"))
        assert (await call("get_model_info"))["total_part_count"] == 220
        check = await call("validate_build")
        assert check["status"] == "passed", check
        print(
            "All construction steps passed. Exporting illustrated booklet...",
            flush=True,
        )
        destination = out / "booklet"
        if destination.exists() and any(destination.iterdir()):
            destination = Path(tempfile.mkdtemp(prefix="booklet-",dir=out))
        exported = await call("export_instructions", directory=str(destination), previews=True, draft=True)
        (out / "result.json").write_text(
            json.dumps(
                dict(
                    status="PASS",
                    parts=220,
                    assemblies=info["submodels"],
                    checked_steps=len(log),
                    export=exported,
                ),
                indent=2,
            ),
            encoding="utf8",
        )
        print(
            json.dumps(
                dict(
                    status="PASS",
                    directory=str(out),
                    checked_steps=len(log),
                    export=exported,
                )
            ),
            flush=True,
        )


if __name__ == "__main__":
    asyncio.run(main())
