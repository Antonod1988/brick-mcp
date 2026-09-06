"""BrickLink Studio model: in-memory representation of a LEGO model.

Singleton pattern: one active StudioProject at a time, accessed via
get_model() / set_model(). Tools always call get_model() at call-time
(never cache references).

The model wraps LDraw command lists with:
- UUID-keyed part index for O(1) lookup by part ID
- Mutation helpers that keep commands list and _parts index in sync
- Serialization back to LDraw text via ldraw.to_ldraw_text()
"""

from __future__ import annotations

import os
import copy
import uuid
from dataclasses import dataclass, field

from brick_mcp.ldraw import (
    IDENTITY_MATRIX,
    Command,
    MetaCommand,
    PartLine,
    RawLine,
    normalize_part_number,
    parse_ldraw,
    to_ldraw_text,
    to_v2_ldraw_text,
)

# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_model: "StudioProject | None" = None


def get_model() -> "StudioProject":
    """Return the active StudioProject. Raises RuntimeError if none is loaded."""
    if _model is None:
        raise RuntimeError("No model loaded. Call new_model() or open_model() first.")
    return _model


def set_model(m: "StudioProject | None") -> None:
    """Replace the active model (pass None to clear)."""
    global _model
    _model = m


# ---------------------------------------------------------------------------
# Internal submodel container
# ---------------------------------------------------------------------------


@dataclass
class _SubmodelData:
    """One MPD FILE block: an ordered command list plus a UUID→PartLine index."""

    name: str
    commands: list[Command] = field(default_factory=list)
    _parts: dict[str, PartLine] = field(default_factory=dict, repr=False)

    def _rebuild_index(self) -> None:
        """Assign UUIDs to all un-identified PartLines and rebuild _parts."""
        self._parts = {}
        for cmd in self.commands:
            if isinstance(cmd, PartLine):
                if not cmd._id:
                    cmd._id = uuid.uuid4().hex[:12]
                self._parts[cmd._id] = cmd

    def _find_part(self, part_id: str) -> PartLine | None:
        return self._parts.get(part_id)

    def part_count(self) -> int:
        return len(self._parts)


# ---------------------------------------------------------------------------
# Public project class
# ---------------------------------------------------------------------------


class StudioProject:
    """An in-memory BrickLink Studio project."""

    def __init__(
        self,
        source_path: str | None,
        root_submodel: str,
        submodels: dict[str, _SubmodelData],
        raw_zip_entries: dict[str, bytes],
    ) -> None:
        self.source_path = source_path
        self.root_submodel = root_submodel
        self.submodels = submodels
        self.raw_zip_entries = raw_zip_entries
        self._dirty = False
        self._undo = []

    # ------------------------------------------------------------------
    # Constructors
    # ------------------------------------------------------------------

    @classmethod
    def new(cls, name: str) -> "StudioProject":
        """Create a new, empty model with a single empty submodel."""
        from brick_mcp.instructions import clean_name

        name = clean_name(name)
        if any(c in name for c in "/\\:"):
            raise ValueError("Model name must not be a path")
        if not name.lower().endswith(".ldr"):
            name = name + ".ldr"
        sd = _SubmodelData(name=name)
        return cls(
            source_path=None,
            root_submodel=name,
            submodels={name: sd},
            raw_zip_entries={},
        )

    @classmethod
    def from_blocks(
        cls,
        source_path: str | None,
        blocks: list[tuple[str, list[Command]]],
        raw_zip_entries: dict[str, bytes],
    ) -> "StudioProject":
        """Build a StudioProject from parsed LDraw blocks."""
        submodels: dict[str, _SubmodelData] = {}
        for name, commands in blocks:
            sd = _SubmodelData(name=name, commands=commands)
            sd._rebuild_index()
            submodels[name] = sd
        root = blocks[0][0] if blocks else "model.ldr"
        return cls(
            source_path=source_path,
            root_submodel=root,
            submodels=submodels,
            raw_zip_entries=raw_zip_entries,
        )

    # ------------------------------------------------------------------
    # Submodel resolution
    # ------------------------------------------------------------------

    def _submodel(self, submodel: str | None) -> _SubmodelData:
        """Return the named submodel, or root if name is empty/None."""
        if not submodel:
            return self.submodels[self.root_submodel]
        if submodel not in self.submodels:
            raise KeyError(
                f"Submodel '{submodel}' not found. "
                f"Available: {list(self.submodels.keys())}"
            )
        return self.submodels[submodel]

    # ------------------------------------------------------------------
    # Part operations
    # ------------------------------------------------------------------

    def add_part(
        self,
        submodel: str | None,
        part_number: str,
        color: int,
        x: float,
        y: float,
        z: float,
        matrix: tuple[float, ...] | None = None,
    ) -> str:
        """Add a part and return its session UUID."""
        sd = self._submodel(submodel)
        from brick_mcp.catalog import resolve_part_number
        from brick_mcp.geometry import validate_transform
        from brick_mcp.colors import get_color

        if get_color(color) is None and color != 16:
            raise ValueError(f"Unknown color: {color}")

        part_file = (
            part_number
            if part_number in self.submodels
            else resolve_part_number(part_number)
        )
        if matrix is None:
            matrix = IDENTITY_MATRIX
        if len(matrix) != 9:
            raise ValueError("rotation_matrix must have exactly 9 values")
        validate_transform(x, y, z, matrix)
        if part_file in self.submodels:

            def references(name, seen):
                if name == sd.name:
                    return True
                if name in seen:
                    return False
                return any(
                    references(c.part_file, seen | {name})
                    for c in self.submodels[name]._parts.values()
                    if c.part_file in self.submodels
                )

            if references(part_file, set()):
                raise ValueError("Submodel placement would create a cycle")
            if color != 16:
                part_file = self._colored_variant(part_file, color)
                color = 16
        pid = uuid.uuid4().hex[:12]
        uid = 1 + max(
            (
                c._uid
                for model in self.submodels.values()
                for c in model._parts.values()
            ),
            default=0,
        )
        cmd = PartLine(
            color=color,
            x=x,
            y=y,
            z=z,
            matrix=matrix,
            part_file=part_file,
            _id=pid,
            _uid=uid,
        )
        sd.commands.append(cmd)
        sd._parts[pid] = cmd
        self._dirty = True
        return pid

    def _colored_variant(self, source, color):
        """Studio tints whole references: use explicit-color copies for LDraw inheritance."""
        from brick_mcp.colors import get_color
        import json

        marker = "!BRICK_MCP VARIANT " + json.dumps([source, color])
        for name, existing in self.submodels.items():
            if any(
                isinstance(c, MetaCommand) and c.text == marker
                for c in existing.commands
            ):
                return name
        base = (
            source.rsplit(".", 1)[0]
            + " - "
            + get_color(color)["name"].replace("_", " ")
        )
        name, suffix = base + ".ldr", 2
        while name in self.submodels:
            name = f"{base} {suffix}.ldr"
            suffix += 1
        sd = copy.deepcopy(self._submodel(source))
        sd.name = name
        for cmd in sd.commands:
            if isinstance(cmd, PartLine):
                cmd._id, cmd._uid = uuid.uuid4().hex[:12], 0
        sd._rebuild_index()
        self.submodels[name] = sd
        for cmd in sd._parts.values():
            value = color if cmd.color == 16 else cmd.color
            if cmd.part_file in self.submodels:
                if value != 16:
                    cmd.part_file = self._colored_variant(cmd.part_file, value)
                cmd.color = 16
            else:
                cmd.color = value
        for cmd in sd._parts.values():
            cmd._uid = 1 + max(
                (c._uid for m in self.submodels.values() for c in m._parts.values()),
                default=0,
            )
        sd.commands = [
            c
            for c in sd.commands
            if not (
                isinstance(c, MetaCommand)
                and (c.text.startswith("Name:") or c.text == source.rsplit(".", 1)[0])
            )
        ]
        sd.commands[:0] = [
            MetaCommand(base),
            MetaCommand("Name: " + base),
            MetaCommand(marker),
        ]
        return name

    def remove_part(self, part_id: str, submodel: str | None) -> bool:
        """Remove a part by UUID. Returns True if found and removed."""
        sd = self._submodel(submodel)
        cmd = sd._find_part(part_id)
        if cmd is None:
            return False
        sd.commands.remove(cmd)
        del sd._parts[part_id]
        self._dirty = True
        return True

    def move_part(
        self, part_id: str, x: float, y: float, z: float, submodel: str | None
    ) -> bool:
        """Move a part to new absolute coordinates. Returns True if found."""
        sd = self._submodel(submodel)
        cmd = sd._find_part(part_id)
        if cmd is None:
            return False
        from brick_mcp.geometry import validate_transform

        validate_transform(x, y, z, cmd.matrix)
        cmd.x = x
        cmd.y = y
        cmd.z = z
        self._dirty = True
        return True

    def rotate_part(
        self, part_id: str, matrix: tuple[float, ...], submodel: str | None
    ) -> bool:
        """Change a part's rotation matrix. Returns True if found."""
        if len(matrix) != 9:
            raise ValueError("rotation_matrix must have exactly 9 values")
        sd = self._submodel(submodel)
        cmd = sd._find_part(part_id)
        if cmd is None:
            return False
        from brick_mcp.geometry import validate_transform

        validate_transform(cmd.x, cmd.y, cmd.z, matrix)
        cmd.matrix = tuple(matrix)
        self._dirty = True
        return True

    def change_color(self, part_id: str, color: int, submodel: str | None) -> bool:
        """Change a part's color. Returns True if found."""
        sd = self._submodel(submodel)
        cmd = sd._find_part(part_id)
        if cmd is None:
            return False
        cmd.color = color
        self._dirty = True
        return True

    def get_part(self, part_id: str, submodel: str | None) -> PartLine | None:
        """Return the PartLine for a given UUID, or None."""
        return self._submodel(submodel)._find_part(part_id)

    # ------------------------------------------------------------------
    # Step operations
    # ------------------------------------------------------------------

    def add_step(self, submodel: str | None) -> int:
        """Append a STEP marker. Returns the new total step count."""
        sd = self._submodel(submodel)
        sd.commands.append(MetaCommand(text="STEP"))
        self._dirty = True
        return self._count_steps(sd)

    def remove_step(self, step_index: int, submodel: str | None) -> bool:
        """Remove the step boundary at step_index (0-based). Returns True if found."""
        sd = self._submodel(submodel)
        step_cmds = [
            (i, cmd)
            for i, cmd in enumerate(sd.commands)
            if isinstance(cmd, MetaCommand) and cmd.text == "STEP"
        ]
        if step_index < 0 or step_index >= len(step_cmds):
            return False
        cmd_index, _cmd = step_cmds[step_index]
        del sd.commands[cmd_index]
        self._dirty = True
        return True

    @staticmethod
    def _count_steps(sd: _SubmodelData) -> int:
        return sum(
            1
            for cmd in sd.commands
            if isinstance(cmd, MetaCommand) and cmd.text == "STEP"
        )

    # ------------------------------------------------------------------
    # Query operations
    # ------------------------------------------------------------------

    def list_parts(self, submodel: str | None) -> list[dict]:
        """Return all parts as a list of dicts."""
        from brick_mcp.colors import get_color

        sd = self._submodel(submodel)
        result = []
        for cmd in sd.commands:
            if isinstance(cmd, PartLine):
                color_info = get_color(cmd.color)
                result.append(
                    {
                        "id": cmd._id,
                        "part_number": cmd.part_file,
                        "color": cmd.color,
                        "color_name": color_info["name"] if color_info else "Unknown",
                        "x": cmd.x,
                        "y": cmd.y,
                        "z": cmd.z,
                        "rotation": list(cmd.matrix),
                    }
                )
        return result

    def get_bom(self, submodel: str | None) -> dict[str, dict[str, int]]:
        bom = {}
        for part in self.flatten(submodel):
            colors = bom.setdefault(part["part_number"], {})
            color = str(part["color"])
            colors[color] = colors.get(color, 0) + 1
        return bom

    def snapshot(self):
        return copy.deepcopy(
            (
                self.source_path,
                self.root_submodel,
                self.submodels,
                self.raw_zip_entries,
                self._dirty,
            )
        )

    def restore(self, state):
        (
            self.source_path,
            self.root_submodel,
            self.submodels,
            self.raw_zip_entries,
            self._dirty,
        ) = copy.deepcopy(state)

    def remember(self, state):
        self._undo.append(state)
        del self._undo[:-20]

    def flatten(self, submodel=None, through_step=None):
        from brick_mcp.geometry import transform, multiply
        from brick_mcp.instructions import groups

        root = self._submodel(submodel).name
        result = []

        def visit(
            name,
            matrix,
            offset,
            inherited_color,
            path,
            stack,
            limit=None,
            root_step=None,
        ):
            if name in stack or len(stack) >= 32:
                raise ValueError("Cyclic or excessively nested submodels")
            for i, group in enumerate(groups(self._submodel(name))):
                if limit is not None and i > limit:
                    break
                for cmd in group["commands"]:
                    if not isinstance(cmd, PartLine):
                        continue
                    xyz = transform((cmd.x, cmd.y, cmd.z), matrix, offset)
                    rotation = multiply(matrix, cmd.matrix)
                    color = inherited_color if cmd.color == 16 else cmd.color
                    ident = path + cmd._id
                    step = i if root_step is None else root_step
                    if cmd.part_file in self.submodels:
                        visit(
                            cmd.part_file,
                            rotation,
                            xyz,
                            color,
                            ident + "/",
                            stack + (name,),
                            root_step=step,
                        )
                    else:
                        result.append(
                            dict(
                                id=ident,
                                source_id=cmd._id,
                                part_number=cmd.part_file,
                                color=color,
                                x=xyz[0],
                                y=xyz[1],
                                z=xyz[2],
                                rotation=list(rotation),
                                step_index=step,
                            )
                        )

        visit(root, IDENTITY_MATRIX, (0, 0, 0), 16, "", (), through_step)
        return result

    def get_steps(self, submodel: str | None) -> list[dict]:
        from brick_mcp.instructions import describe_steps

        return describe_steps(self._submodel(submodel))

    def info(self) -> dict:
        """Return metadata about the project."""
        total_parts = len(self.flatten())
        return {
            "source_path": self.source_path,
            "filename": (
                os.path.basename(self.source_path) if self.source_path else None
            ),
            "root_submodel": self.root_submodel,
            "submodels": list(self.submodels.keys()),
            "total_part_count": total_parts,
            "is_dirty": self._dirty,
        }

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def to_ldraw_text(self) -> str:
        """Serialize the project to standard LDraw text (type-1 part lines)."""
        blocks = self._export_blocks()
        return to_ldraw_text(blocks)

    def to_v2_ldraw_text(self) -> str:
        """Serialize the project in BrickLink Studio v2 format (type-11 part lines)."""
        blocks = self._export_blocks()
        return to_v2_ldraw_text(blocks)

    def _export_blocks(self):
        from brick_mcp.instructions import groups, write_groups

        result = []
        for sd in self.submodels.values():
            output = copy.deepcopy(sd)
            for cmd in output.commands[:]:
                if isinstance(cmd, MetaCommand) and cmd.text.startswith(
                    "!BRICK_MCP VARIANT "
                ):
                    import json

                    source, _ = json.loads(cmd.text[len("!BRICK_MCP VARIANT ") :])
                    output.commands = [
                        c
                        for c in output.commands
                        if not (
                            isinstance(c, MetaCommand)
                            and c.text == source.rsplit(".", 1)[0]
                        )
                    ]
            write_groups(output, groups(output))
            if not any(
                isinstance(c, MetaCommand) and c.text.startswith("Name:")
                for c in output.commands
            ):
                title = sd.name.rsplit(".", 1)[0]
                output.commands[:0] = [
                    MetaCommand(title),
                    MetaCommand("Name: " + title),
                ]
            result.append((sd.name, output.commands))
        return result

    def _part_as_dict(self, part_id: str, submodel: str | None) -> dict | None:
        """Return part dict for a single part by UUID."""
        from brick_mcp.colors import get_color

        cmd = self.get_part(part_id, submodel)
        if cmd is None:
            return None
        color_info = get_color(cmd.color)
        return {
            "id": cmd._id,
            "part_number": cmd.part_file,
            "color": cmd.color,
            "color_name": color_info["name"] if color_info else "Unknown",
            "x": cmd.x,
            "y": cmd.y,
            "z": cmd.z,
            "rotation": list(cmd.matrix),
        }
