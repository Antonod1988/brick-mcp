"""Run the configured Codex stdio server and verify editing plus file round trips."""

import asyncio
import json
import os
import tempfile
import time
import tomllib
from pathlib import Path

from fastmcp import Client
from fastmcp.client.transports import StdioTransport


async def main():
    config_path = (
        Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")) / "config.toml"
    )
    config = tomllib.loads(config_path.read_text(encoding="utf-8"))["mcp_servers"][
        "brick"
    ]
    transport = StdioTransport(
        command=config["command"], args=config["args"], env=config["env"], keep_alive=False
    )
    output = Path(__file__).parent / "output"
    output.mkdir(exist_ok=True)
    output = Path(tempfile.mkdtemp(prefix="mcp-check-", dir=output))
    started = time.monotonic()
    async with Client(transport, timeout=60) as client:
        tools = await client.list_tools()
        startup_seconds = round(time.monotonic() - started, 2)

        async def call(name, **args):
            result = await client.call_tool(name, args)
            envelope = json.loads(
                next(c.text for c in result.content if c.type == "text")
            )
            assert not result.is_error and envelope["ok"], envelope
            return envelope.get("data")

        assert {"batch", "save_model", "open_model", "check_overlaps"} <= {
            t.name for t in tools
        }
        assert await call("search_parts", query="window", limit=5)
        footprint = await call("get_part_footprint", part_number="3001")
        assert footprint["height"] == 24 and footprint["x_span"] == 80
        # Three 2x4 bodies touch vertically: Y [0,24], [-24,0], [-48,-24].
        build = [{"tool": "new_model", "args": {"name": "mcp_connection_test"}}]
        build += [
            {
                "tool": "add_part",
                "args": {"part_number": "3001", "color": color, "x": 0, "y": y, "z": 0},
            }
            for color, y in [(4, 0), (14, -24), (1, -48)]
        ]
        await call("batch", calls=build)
        parts = await call("list_parts")
        assert len(parts) == 3
        top_id = parts[-1]["id"]
        await call(
            "batch",
            calls=[
                {"tool": "change_color", "args": {"part_id": top_id, "color": 2}},
                {
                    "tool": "move_part",
                    "args": {"part_id": top_id, "x": 20, "y": -48, "z": 0},
                },
                {
                    "tool": "rotate_part",
                    "args": {
                        "part_id": top_id,
                        "rotation_matrix": [-1, 0, 0, 0, 1, 0, 0, 0, -1],
                    },
                },
            ],
        )
        assert (await call("check_overlaps"))["overlap_count"] == 0
        expected_bom = {"3001.dat": {"4": 1, "14": 1, "2": 1}}
        assert await call("get_bom") == expected_bom
        for suffix in ("io", "ldr"):
            path = output / f"mcp_connection_test.{suffix}"
            await call("save_model", path=str(path))
            await call("open_model", path=str(path))
            assert await call("get_bom") == expected_bom
            top = next(p for p in await call("list_parts") if p["color"] == 2)
            assert (top["x"], top["y"], top["rotation"]) == (
                20,
                -48,
                [-1, 0, 0, 0, 1, 0, 0, 0, -1],
            )
        summary = {
            "status": "PASS",
            "tool_count": len(tools),
            "startup_seconds": startup_seconds,
            "checks": "stdio handshake, catalog, batch, recolor, move, rotate, overlaps, BOM, io/ldr reopen",
            "output": str(output),
        }
        (output / "result.json").write_text(
            json.dumps(summary, indent=2), encoding="utf-8"
        )
        print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
