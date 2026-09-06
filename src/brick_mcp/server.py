"""FastMCP server instance and system instructions for brick-mcp."""

from __future__ import annotations

from fastmcp import FastMCP
from fastmcp.server.middleware import Middleware
import asyncio

INSTRUCTIONS = """Build LEGO models as real assembly instructions, one checked step at a time.

1. Plan the subject and subassemblies; calculate coordinates for the next small step.
2. search_parts/get_part_details resolve canonical numbers. get_part_footprint returns
   actual body_min/body_max: origins are not always centered.
3. create_submodel for a roof, tree, furniture or repeated assembly. Build it with
   apply_step(name, parts, submodel=...). Prefer readable steps of roughly 3–10 parts.
4. apply_step checks the sequence, rolls back failure, and returns accumulated and
   highlighted PNG previews. Inspect them before progressing. Its optional save_path
   writes an atomic checkpoint only after validation and preview succeed.
5. Install a connected assembly with apply_step(part_number='Assembly.ldr',...);
   internal steps stay editable. edit_step inserts, renames, reorders, splits or moves
   parts between steps. undo_last_edit restores memory, not previously written files.
6. validate_build distinguishes passed, failed and unverified. Only ordinary upright
   stud/receiver grids and vertical insertion are supported. Unknown pins, clips,
   hinges and unusual geometry must never be called verified or physically stable.
   apply_step ALSO runs real Studio Stability AND Connectivity automatically via
   the dedicated local native worker. Native issues/timeouts roll back the step;
   allow_unverified does not bypass this. No Computer Use is required.
   check_studio_stability checks existing models/prefixes, all_steps=True audits
   every step of an assembly. Native flagged parts include exact coordinates.
   inspect_studio_connectors returns actual native pin/bar/axle positions.
   allow_cautions=True explicitly accepts soft cautions while keeping the counts.
   allow_unverified_canvas=True tests full and rigid-subset models; missing-physics
   sails stay unverified_canvas and require draft export. Never call them verified.
   Reports persist in IO/MPD, are tied to model/step content, and become stale on edits.
7. render_step shows new pieces against gray previous pieces. Software previews use
   real triangles and display transparent parts as opaque for instruction readability.
8. export_instructions writes Studio IO, MPD, named step/BOM JSON and illustrated HTML.
   Native STUDIOSTEPDESC names and submodel steps are preserved. Open/reopen in Studio;
   live GUI synchronization is not provided.
   Normal export requires current accepted native reports for every prefix. draft=True creates a
   visibly labelled working draft with the missing/stale/failed check exposed.

apply_step defaults to refusing unverified work. allow_unverified=True only accepts
unknown connector cases; confirmed failures still roll back. Legacy batch now defaults
to atomic rollback, stops on first error, and forbids disk writes; save separately.
atomic=False explicitly requests the former best-effort behavior.
apply_step(replace_existing=True, insert_at=i) replaces a step transactionally.
remove_unused_submodel removes only unreferenced prototypes. The native worker
auto-starts when needed; never use GUI clicks as the normal validation path.

One active model is held per server. Save before restart; open_model changes part IDs.
Use new filenames when editing a user's original model. Coordinates are LDU: X/Z studs
20, brick height 24, plate height 8; negative Y is up. Rotation is row-major 3x3.
"""


mcp = FastMCP(
    name="brick-mcp",
    instructions=INSTRUCTIONS,
)


class _SequentialModelAccess(Middleware):
    """One mutable model per server: a tool observes a whole committed state."""

    def __init__(self):
        # ponytail: serialize requests; independent projects should use separate server processes.
        self.lock = asyncio.Lock()

    async def on_call_tool(self, context, call_next):
        async with self.lock:
            return await call_next(context)


mcp.add_middleware(_SequentialModelAccess())


@mcp.prompt(
    name="Work with LEGO model",
    description="Initialise an LLM session for LEGO model editing with brick-mcp.",
)
def lego_model_prompt() -> str:
    """Sets up the LLM with the brick-mcp workflow and coordinate system."""
    return INSTRUCTIONS
