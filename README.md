# brick-mcp

Personal 0.3 edition based on [datakurre/brick-mcp](https://github.com/datakurre/brick-mcp), with the upstream Git history preserved. This is an independent extension, not an official BrickLink Studio integration.

Our additions include atomic construction steps with rollback, subassemblies and illustrated instructions, geometry-based part dimensions, and a native Windows bridge that runs Studio Stability and Connectivity checks on each committed step without Computer Use. See [LOCAL_SETUP.md](LOCAL_SETUP.md) for setup and [native_bridge/README.md](native_bridge/README.md) for the native worker.

The native worker requires a separately installed Studio. Runtime binaries, local caches, generated models and rendered media are excluded from this repository. Fabric sails without physics data remain explicitly unverified; see [UPGRADE_RESULT.md](UPGRADE_RESULT.md) for verification history and limitations.

The repository also preserves the cottage, pirate ship and Orc Kraken build scripts. `make_orc_presentation.py`, `presentation_blender.py` and `finish_orc_presentation.py` export the ship geometry, render stills/assembly stages and package the videos. These are workstation-specific examples: review their local paths and provide the generated model, Blender and FFmpeg before running them.

Verification of this snapshot: **235 tests passed** (`python -m pytest tests/ -q`, 2026-09-06). Native engine integration checks are separate from this unit suite.

An [MCP](https://modelcontextprotocol.io/) server that lets AI assistants create, inspect, and edit LEGO models stored in BrickLink Studio (`.io`) and LDraw (`.ldr`) files. Ask your AI assistant to open a file, move parts around, change colors, add new bricks — then save back to a file that opens directly in BrickLink Studio.

## Features

- Open and save **BrickLink Studio `.io`** files and plain LDraw **`.ldr`** / `.mpd` files
- List parts, inspect the bill of materials, and view building-instruction steps
- Add, remove, move, rotate, and recolor individual parts by session ID
- Search the built-in parts database and look up LDraw color codes
- Create new models from scratch with `new_model()`

## Instruction workflow (0.2)

Use `apply_step` for a named construction step with validation, rollback and two
PNG previews. `edit_step` inserts/renames/reorders/splits steps and moves parts.
`create_submodel` builds independent assemblies; `undo_last_edit` restores memory.
`validate_build` checks ordinary stud connections and vertical insertion access.
`render_step` highlights new parts. `export_instructions` writes native Studio IO,
MPD, an illustrated HTML booklet and a JSON step/BOM manifest.

Aliases resolve to canonical parts and dimensions come from actual LDraw geometry.
Complex connectors remain **unverified**. `batch` defaults to atomic memory edits;
save separately. `atomic=False` enables explicit legacy best-effort execution.

## Requirements

- Python ≥ 3.14
- [Nix](https://nixos.org/) (recommended — handles all dependencies automatically)

Without Nix, install Python dependencies manually:

```sh
pip install "fastmcp>=3.1.0" "pyzipper>=0.3.6" "numpy>=2.4,<3" "pillow>=12,<13"
```

## MCP client configuration

### VS Code

The repository ships a ready-to-use `.vscode/mcp.json` using Nix:

```json
{
  "servers": {
    "bricks": {
      "type": "stdio",
      "command": "nix",
      "args": ["run", "/path/to/brick-mcp"]
    }
  }
}
```

Replace `/path/to/brick-mcp` with the path to your local clone, or use `github:datakurre/brick-mcp` to run directly from GitHub without cloning.

### Claude Desktop (`claude_desktop_config.json`)

```json
{
  "mcpServers": {
    "bricks": {
      "command": "nix",
      "args": ["run", "github:datakurre/brick-mcp"]
    }
  }
}
```

### Without Nix (local Python)

```json
{
  "mcpServers": {
    "bricks": {
      "command": "python",
      "args": ["/path/to/brick-mcp/main.py"]
    }
  }
}
```

## Typical workflow

```
1. open_model("path/to/model.io")   — load a file
2. list_parts()                      — see what's inside
3. change_color("abc123", 4)         — change a part to Red
4. add_part("3001.dat", 4, x=0, y=-24, z=0)  — place a new 2×4 brick
5. save_model()                      — write back to the original file
```

## Tool reference

### File operations

| Tool | Description |
|---|---|
| `new_model(name)` | Create a new empty model in memory. |
| `open_model(path)` | Open a `.io`, `.ldr`, or `.mpd` file. Assigns session IDs to all parts. |
| `save_model(path)` | Save the model. Omit `path` to overwrite the source file. |
| `get_model_info()` | Return filename, submodels, total part count, dirty flag. |

### Inspection

| Tool | Description |
|---|---|
| `list_parts(submodel)` | List all parts with IDs, colors, positions, and rotations. |
| `get_bom(submodel)` | Bill of materials grouped by part number and color. |
| `get_steps(submodel)` | Building-instruction step boundaries and part counts per step. |

### Editing

| Tool | Description |
|---|---|
| `add_part(part_number, color, x, y, z, rotation_matrix, submodel)` | Add a part and return its new session ID. |
| `remove_part(part_id, submodel)` | Delete a part by its session ID. |
| `move_part(part_id, x, y, z, submodel)` | Move a part to new absolute coordinates. |
| `rotate_part(part_id, rotation_matrix, submodel)` | Replace a part's rotation matrix. |
| `change_color(part_id, color, submodel)` | Recolor a part. |
| `add_step(submodel)` | Append a STEP marker (building-instruction boundary). |
| `remove_step(step_index, submodel)` | Remove a STEP marker by index. |

### Parts & colors database

| Tool | Description |
|---|---|
| `search_parts(query)` | Search the built-in parts database by name or number. |
| `list_colors()` | All LDraw color codes with names and hex values. |
| `get_color_info(color_code)` | Details for a specific color code. |

## Coordinate system

LDraw uses **LDU** (LDraw Units). Key measurements:

| Measurement | LDU |
|---|---|
| 1 stud width | 20 |
| 1 brick height | 24 |
| 1 plate height | 8 |

The **Y-axis is inverted**: `y=0` is the build plate, `y=-24` is one brick above it. X and Z are the horizontal plane.

## Common LDraw color codes

| Code | Color |
|---|---|
| 0 | Black |
| 1 | Blue |
| 2 | Green |
| 4 | Red |
| 14 | Yellow |
| 15 | White |
| 71 | Light Bluish Gray |
| 72 | Dark Bluish Gray |

Use `list_colors()` for the full list.

## Common part numbers

| Part | Number |
|---|---|
| Brick 1×1 | 3005 |
| Brick 1×2 | 3004 |
| Brick 1×4 | 3010 |
| Brick 2×2 | 3003 |
| Brick 2×4 | 3001 |
| Plate 1×1 | 3024 |
| Plate 1×2 | 3023 |
| Plate 2×4 | 3020 |

Use `search_parts("brick 2x4")` to find part numbers you don't know.