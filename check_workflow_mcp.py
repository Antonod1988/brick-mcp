"""Exercise the exact configured stdio MCP, including real PNGs and native steps."""

import asyncio
import json
import tempfile
import tomllib
import zipfile
from pathlib import Path

from fastmcp import Client
from fastmcp.client.transports import StdioTransport


async def main():
    config = tomllib.loads(
        (Path.home() / ".codex/config.toml").read_text(encoding="utf8")
    )["mcp_servers"]["brick"]
    out = Path(
        tempfile.mkdtemp(prefix="workflow-check-", dir=Path(__file__).parent / "output")
    )
    async with Client(
        StdioTransport(
            command=config["command"],
            args=config["args"],
            env=config["env"],
            keep_alive=False,
        ),
        timeout=120,
    ) as client:

        async def call(tool, expect=True, **args):
            response = await client.call_tool(tool, args)
            result = json.loads(
                next(c.text for c in response.content if c.type == "text")
            )
            assert result["ok"] == expect, result
            return result.get("data", result), response

        tools = await client.list_tools()
        for number, canonical in [("3068", "3068b.dat"), ("4073", "6141.dat")]:
            info, _ = await call("get_part_details", part_number=number)
            assert info["part_number"] == canonical
        helmet, _ = await call("get_part_footprint", part_number="3833")
        assert helmet["x_span"] < 40 and helmet["connection_kind"] == "unknown"
        await call("new_model", name="MCP instruction check")
        placed, _ = await call(
            "apply_step",
            name="Основание",
            parts=[dict(part_number="3001", color=4)],
            preview=False,
        )
        before, _ = await call("get_bom")
        bad, _ = await call(
            "apply_step",
            expect=False,
            name="Overlap",
            parts=[dict(part_number="3001", color=4, y=-12)],
            preview=False,
        )
        assert bad["rolled_back"] and (await call("get_bom"))[0] == before
        await call("create_submodel", name="Tower")
        for i in range(2):
            await call(
                "apply_step",
                name=f"Layer {i+1}",
                parts=[dict(part_number="3003", color=14, y=-24 * i)],
                submodel="Tower.ldr",
                preview=False,
            )
        result, response = await call(
            "apply_step",
            name="Установить башню",
            parts=[dict(part_number="Tower.ldr", color=16, x=-20, y=-24)],
            preview=True,
        )
        assert len([c for c in response.content if c.type == "image"]) == 2
        assert all(
            Path(p).read_bytes().startswith(b"\x89PNG") for p in result["preview_paths"]
        )
        await call("edit_step", action="rename", step_index=0, name="Красное основание")
        saved = out / "model.io"
        await call("save_model", path=str(saved))
        await call("open_model", path=str(saved))
        steps, _ = await call("get_steps")
        assert len(steps) == 2 and steps[0]["name"] == "Красное основание"
        with zipfile.ZipFile(saved) as z:
            native = z.read("modelv2.ldr").decode("utf8")
            assert "0 STUDIOSTEPDESC Красное основание" in native
            assert "Tower.ldr.dat" not in native
        validation, _ = await call("validate_build")
        assert validation["status"] == "passed"
        exported, _ = await call(
            "export_instructions", directory=str(out / "instructions"), previews=False
        )
        assert exported["assemblies"] == 2 and Path(exported["studio_file"]).is_file()
        summary = dict(
            status="PASS",
            tool_count=len(tools),
            pngs=result["preview_paths"],
            directory=str(out),
            checks="aliases, real bounds, failed-step rollback, submodels, real previews, native named steps, IO reopen, HTML/MPD export",
        )
        (out / "result.json").write_text(json.dumps(summary, indent=2), encoding="utf8")
        print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
