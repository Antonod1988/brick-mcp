# Brick MCP on this Windows computer

Installed from https://github.com/datakurre/brick-mcp at upstream commit
`90c97bb3a602a81818553c1bf8c56769a1bc7eaf` on 2026-09-06.
Local development branch: `codex/windows-studio-setup`.

- Source: `D:\pythonProject4\brick-mcp`.
- Dedicated runtime: `.venv\Scripts\python.exe` (Python 3.14.7).
- Dependencies: upstream `uv.lock`, FastMCP 3.1.0.
- Codex server name: `brick`, stdio transport, enabled in
  `C:\Users\user\.codex\config.toml`; startup timeout 30 seconds.
- Studio library: `D:\Progs\Studio 2.0\ldraw`, 12,132 catalog entries.
- Fast catalog snapshot: `.cache\studio-catalog.json`.
- Models created by the smoke check: `output\mcp-check-*\`.

The local patch adds `LDRAW_LIBRARY_PATH` directory loading and
`LDRAW_CATALOG_PATH` JSON snapshot loading. The snapshot takes precedence so
each server process need not open 12,132 individual files at first search.
Original Nix ZIP discovery and the fallback table still work when neither
variable is set. This changes search metadata, not the geometry validator.

## Checks

Run from this directory in PowerShell:

```powershell
& '.\.venv\Scripts\python.exe' -m pytest tests -q
& '.\.venv\Scripts\python.exe' check_mcp.py
codex mcp get brick
```

The smoke check launches the exact command and environment saved in Codex,
lists the 24 tools, and checks catalog search, batch creation, recoloring,
movement, rotation, overlaps, BOM, saving and reopening `.io` and `.ldr`.
It uses MCP over stdio and does not call an AI provider.

Verified on 2026-09-06: 204 tests passed; stdio smoke check passed with 24 tools
and 2.67-second startup. The resulting
`output\mcp-check-4ayqe4ac\mcp_connection_test.io` was opened in Studio 2.26.8_1:
three bricks appeared, with the upper brick green and shifted one stud as
requested through MCP. Studio labels this minimal new IO document "Untitled
Model" because full Studio document metadata is not generated.

After updating Studio or its library, refresh the index:

```powershell
& '.\.venv\Scripts\python.exe' refresh_catalog.py
```

Restart the MCP connection afterward to clear its in-memory catalog.
The index contains the main `ldraw\parts` directory; Studio's unofficial and
custom libraries are not merged into it.

## Workflow and current limits

Use `search_parts` / `get_part_details`, plan positions in LDU, then `batch`
for edits. Inspect `check_overlaps` before saving. Batch continues after
individual errors, so check its `error_count` and save in a separate call.
When editing existing user models, save to a new path for the first trials.

The model lives in one MCP server process. It is not a live connection to the
open Studio scene: save the file and open/reopen it in Studio to view changes.
Save before restarting MCP. Part IDs change after opening a model again.

Overlap checks use bounding boxes and approximate dimensions for many parts;
they do not prove valid LEGO connections or structural stability.
LDView is not installed/configured here, so `render_model` and automatic
image previews are not currently available. Studio can display the saved files.

If the current Codex task does not expose `brick` tools after the config change,
reload the MCP connection or restart Codex, then continue the task.
