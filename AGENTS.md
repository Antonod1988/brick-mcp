# AGENTS.md — brick-mcp developer guide for AI coding agents

Primary reference for AI coding agents (Copilot, Claude, etc.) working inside this repository. Read it before making any changes.

---

## What this project is

`brick-mcp` is a [Model Context Protocol](https://modelcontextprotocol.io/) (MCP) server that lets AI assistants create, inspect, and edit LEGO models stored in BrickLink Studio (`.io`) and LDraw (`.ldr`) files. It is built with [FastMCP](https://github.com/jlowin/fastmcp). Tools return JSON envelopes and, when requested, PNG content blocks.

---

## Local 0.3 instruction workflow

- `geometry.py` is shared by bounds, connections and rendering. Do not restore the
  removed hard-coded dimensions table. Unsupported geometry must remain explicit.
- `instructions.py` reads/writes native STUDIOSTEPDESC descriptions and step groups.
- `validation.py` covers ordinary upright studs/receivers and insertion from above;
  it does not prove physical strength or support arbitrary clips/pins/hinges.
- `native_studio.py` drives a dedicated Studio worker through local request files.
  `apply_step` runs native Stability and Connectivity before committing, including
  later prefixes and affected parent assemblies; `edit_step` does likewise.
  Use `inspect_studio_connectors` for actual pin/bar/axle coordinates. No Computer
  Use is involved. Do not replace the native result with an AABB approximation.
- Native red warnings, disconnected sections, instability and transport failures
  roll back. `allow_cautions=True` explicitly accepts soft cautions, retaining them.
  `allow_unverified_canvas=True` is display-only: full and rigid-subset checks run,
  missing-physics sails remain `unverified_canvas`, and release export stays blocked.
- `apply_step(replace_existing=True, insert_at=i)` atomically replaces one step.
  Native reports are bound to each prefix's content; unverified/stale prefixes
  prevent non-draft instruction export. Legacy add_part/batch are candidate edits.
- The bridge source/build/setup are in `native_bridge/`; installed runtime files
  live in ignored `.cache/studio-worker`. Its profile is separate from user Studio.
  `native_bridge/probe.py` exercises the real engine; unit tests stub transport.
- `tools/workflow.py` exposes apply_step, edit_step, create_submodel, undo_last_edit,
  validate_build, render_step and export_instructions. Compound edits snapshot
  memory; error/preview/save failure restores it. Files are replaced atomically.
- `rendering.py` uses real triangles and a software z-buffer. NumPy must initialize
  on the main thread before FastMCP workers. Mixed JSON/image tools explicitly set
  output_schema=None, otherwise FastMCP 3.1 rejects successful PNG responses.
- High-level step tools control preview timing explicitly. Low-level mutation tools
  retain ok_with_render and respect suppress_render / BRICK_MCP_AUTO_RENDER.
- Middleware serializes all MCP tool access to the singleton.
- Colored submodel placements become explicit-color copies with reference color 16.
  Remove the source's old header description from clones: Studio otherwise conflates
  their identity. Variants are independent copies, not live derived views.
- check_workflow_mcp.py tests real stdio/PNG/native step round trips;
  rebuild_cottage_instructions.py tests the complete assembly workflow.

## Repository layout

```
main.py                        Entry point — runs the MCP server over stdio
pyproject.toml                 Package metadata and dependencies
src/
  brick_mcp/
    __init__.py                Imports tools (side-effect: registers them) + re-exports mcp
    server.py                  FastMCP instance + INSTRUCTIONS string shown to the AI agent
    model.py                   StudioProject class, global singleton, get_model()/set_model()
    ldraw.py                   LDraw parser + serializer (type-1 and type-11)
    io_file.py                 .io ZIP read/write (plain + AES fallback)
    colors.py                  LDraw color code database
    _helpers.py                ok()/err()/ok_with_render()/try_render() helpers
    tools/
      __init__.py              Imports all tool sub-modules to trigger @mcp.tool() registration
      file_ops.py              new_model, open_model, save_model, get_model_info
      inspection.py            list_parts, get_bom, get_steps
      manipulation.py          add_part, remove_part, move_part, rotate_part,
                               change_color, add_step, remove_step
      parts.py                 search_parts, list_colors, get_color_info
      render.py                render_model (PNG rendering via LDView)
pkgs/
  ldview.nix                   Nix derivation for LDView headless renderer
tests/
  conftest.py                  Shared fixtures
  test_io_file.py              ZIP read/write tests
  test_ldraw.py                Parser/serializer tests
  test_model.py                StudioProject unit tests
  test_tools.py                MCP tool integration tests
```

---

## Architecture: the model singleton

`model.py` owns a **module-level singleton** of type `StudioProject`. Because `open_model` and `new_model` must replace it with a new object, the singleton is accessed through accessor functions — never through a direct import of the object:

```python
# model.py
def get_model() -> StudioProject: ...   # raises RuntimeError if no model loaded
def set_model(m: StudioProject | None) -> None: ...
```

**Every tool must call `get_model()` at invocation time.** Storing a reference at import time silently breaks after `open_model` is called.

```python
# CORRECT
from brick_mcp.model import get_model as _get_model
project = _get_model()

# WRONG — stale reference after open_model()
from brick_mcp.model import _model  # never do this
```

---

## The `StudioProject` class (`model.py`)

Holds a dict of `_SubmodelData` objects keyed by submodel name. The root submodel is identified by `project.root_submodel`.

### `_SubmodelData`

| Attribute | Type | Purpose |
|---|---|---|
| `name` | `str` | Submodel filename (e.g. `"model.ldr"`) |
| `commands` | `list[Command]` | Ordered list of `PartLine`, `MetaCommand`, `RawLine` |
| `_parts` | `dict[str, PartLine]` | UUID → PartLine index for O(1) lookup |

`_rebuild_index()` assigns UUIDs to all un-identified `PartLine`s on load.

### Key `StudioProject` methods

| Method | Notes |
|---|---|
| `add_part(submodel, part_number, color, x, y, z, matrix) → str` | Appends a PartLine; returns its UUID |
| `remove_part(part_id, submodel) → bool` | Deletes by UUID |
| `move_part(part_id, x, y, z, submodel) → bool` | Sets position in-place |
| `rotate_part(part_id, matrix, submodel) → bool` | Sets rotation matrix in-place |
| `change_color(part_id, color, submodel) → bool` | Sets color code in-place |
| `list_parts(submodel) → list[dict]` | Returns serializable part dicts |
| `get_bom(submodel) → dict` | `{part_number: {color_str: count}}` |
| `get_steps(submodel) → list[dict]` | Step boundaries with part counts |
| `to_ldraw_text() → str` | Serialize to standard LDraw (type-1) |
| `to_v2_ldraw_text() → str` | Serialize to BrickLink Studio v2 (type-11) |

---

## LDraw format (`ldraw.py`)

### Command types

| Class | Line type | Description |
|---|---|---|
| `PartLine` | `1` or `11` | Part placement with color, position, rotation, part file |
| `MetaCommand` | `0` | Comment or META (e.g. `STEP`, `FILE model.ldr`) |
| `RawLine` | `2`–`5` | Geometry primitives, passed through verbatim |

### BrickLink Studio type-11 extension

BrickLink Studio v2 writes `modelv2.ldr` using its own line type `11`:

```
11 <color> <uid> <selected> <group_id> <x> <y> <z> <9-matrix> <part_file>
```

The parser normalizes type-11 lines to `PartLine`, preserving `_uid`, `_group_id`, and `_selected` for round-trip fidelity. `to_v2_ldraw_text()` re-emits type-11 lines — preserving UIDs for existing parts, assigning new sequential UIDs for parts added since loading.

BOM bytes (`\ufeff`) injected by Studio at line start are stripped during parsing.

### Serialization

- `to_ldraw_text(blocks)` — standard LDraw: single block = plain `.ldr`, multiple blocks = MPD with `0 FILE` / `0 NOFILE` wrappers.
- `to_v2_ldraw_text(blocks)` — always wraps in `0 FILE` / `0 NOFILE`; uses type-11 for `PartLine` and falls back to type-0 for everything else.

---

## .io file format (`io_file.py`)

BrickLink Studio `.io` files are ZIP archives.

### Archive contents

| File | Purpose |
|---|---|
| `model.ldr` | Standard LDraw (type-1) — written but not read by Studio |
| `modelv2.ldr` | BrickLink Studio v2 (type-11) — **this is what Studio reads** |
| `model2.ldr` | Verbose extended format — not parsed, excluded from writes |
| `thumbnail.png`, `.info`, `model.ins`, etc. | Preserved verbatim |

### Read strategy (`read_io_file`)

1. Try plain `zipfile.ZipFile` first (newer Studio versions write unencrypted archives).
2. Fall back to `pyzipper.AESZipFile` with password `"soho0909"` for legacy files.
3. Prefer `modelv2.ldr` over `model.ldr` as the primary model source.
4. Return `(model_bytes, other_entries)` — `other_entries` excludes `model.ldr`, `modelv2.ldr`, `model2.ldr`.

### Write strategy (`write_io_file`)

Always writes a **plain (unencrypted) ZIP**:
- `model.ldr` — type-1 LDraw text
- `modelv2.ldr` — type-11 BrickLink v2 text (regenerated from current state)
- All `other_entries` from the original archive (thumbnails, etc.)
- `model2.ldr` is never written back.

---

## `_helpers.py` — tool response helpers

```python
def ok(data=None, message="") -> dict:
    """Return {"ok": True, "data": data, "message": message}."""

def err(message, code="ERROR") -> dict:
    """Return {"ok": False, "error": message, "code": code}."""

def try_render(project, width=800, height=600) -> Image | None:
    """Best-effort render via ldview. Returns Image or None if unavailable."""

def ok_with_render(project, data=None, message="") -> list | dict:
    """Like ok(), but appends a PNG render when ldview is on PATH.
    Returns [dict, Image] when rendering succeeds, plain dict otherwise."""
```

Low-level mutation tools should use `ok_with_render()` so every edit automatically includes a visual preview. Error responses always use `err()`. Read-only inspection tools use plain `ok()`.

---

## Adding a new tool

1. Pick the right sub-module under `src/brick_mcp/tools/` or create a new one.
2. Decorate the function with `@mcp.tool` (import `mcp` from `brick_mcp.server`).
3. Import `get_model` from `brick_mcp.model` — call it at invocation time, never at import time.
4. Return `ok(data, message)` or `err(message, code)`.
   - For **mutation** tools, use `ok_with_render(project, data, message)` instead of `ok()`.
5. If you add a new sub-module, import it in `src/brick_mcp/tools/__init__.py`.
6. Update the `INSTRUCTIONS` string in `server.py` if the tool changes the user-facing workflow.

Minimal template:

```python
from brick_mcp._helpers import err, ok
from brick_mcp.model import get_model
from brick_mcp.server import mcp

@mcp.tool
def my_tool(param: str, submodel: str = "") -> dict:
    """One-line description shown to the agent."""
    try:
        project = get_model()
    except RuntimeError as e:
        return err(str(e), "NO_MODEL")
    result = project.some_method(param, submodel or None)
    return ok(result, f"Done: {result}")
```

---

## Key invariants to maintain

1. **Low-level mutation tools use `ok_with_render()`, read-only tools use `ok()`, errors use `err()`.** `ok_with_render()` returns `[dict, Image]` when ldview is available, plain `dict` otherwise — FastMCP converts both to proper MCP content blocks. `render_model` returns a bare `Image` on success and `err()` on failure. Tools must never return `None`, raise exceptions, or return arbitrary dicts.
2. **`get_model()` — always at call time.** No module-level references to the model object.
3. **UIDs must round-trip.** When serializing to `modelv2.ldr`, existing `_uid` values must be preserved exactly — Studio tracks parts by UID.
4. **`modelv2.ldr` is authoritative.** The MCP reads from it when present (Studio v2 writes here and reads from here). `model.ldr` is also written for compatibility.
5. **`model2.ldr` is never written.** It is a verbose Studio-internal format we don't generate.
6. **Tool registration is by import side-effect.** `@mcp.tool` on the function is sufficient — just make sure the module is imported in `tools/__init__.py`.
7. **Part session IDs reset on `open_model`.** Callers must re-call `list_parts()` after any `open_model` or `new_model` call.

---

## Running and testing

```sh
# Run the MCP server (stdio transport, using project venv)
PYTHONPATH=src .venv/bin/python main.py

# Or with Nix
nix run .

# Count registered tools (quick sanity check)
PYTHONPATH=src .venv/bin/python -c "
import asyncio, brick_mcp
tools = asyncio.run(brick_mcp.mcp.list_tools())
print(len(tools), 'tools:', [t.name for t in tools])
"

# Run the full test suite
PYTHONPATH=src .venv/bin/python -m pytest tests/

# Run with coverage
PYTHONPATH=src .venv/bin/python -m pytest tests/ --cov --cov-report=term-missing
```

Python ≥ 3.14 is required. No system libraries are needed (unlike the old `cairosvg` path).

