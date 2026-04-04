"""LDraw file format parser and serializer.

Supports:
- Line type 0 (comments / META commands)
- Line type 1 (part references — the key data)
- Line type 11 (BrickLink Studio v2 extension — normalized to type-1 internally)
- Line types 2-5 (geometry, passed through verbatim)
- MPD (Multi-Part Document) with 0 FILE / 0 NOFILE blocks
"""

from __future__ import annotations

from dataclasses import dataclass, field

# Identity rotation matrix (no rotation / scale)
IDENTITY_MATRIX: tuple[float, ...] = (1, 0, 0, 0, 1, 0, 0, 0, 1)


@dataclass
class PartLine:
    """Line type 1 — a part placement in a model or submodel."""

    color: int
    x: float
    y: float
    z: float
    matrix: tuple[float, ...]  # 9-element row-major 3×3 rotation matrix
    part_file: str  # e.g. "3001.dat"
    # Session UUID — set after parsing, NOT written to file
    _id: str = field(default="", compare=False, repr=False)
    # BrickLink Studio v2 metadata — preserved for round-trip fidelity
    _uid: int = field(default=0, compare=False, repr=False)
    _group_id: int = field(default=0, compare=False, repr=False)
    _selected: bool = field(default=False, compare=False, repr=False)


@dataclass
class MetaCommand:
    """Line type 0 — comment or META command (everything after '0 ')."""

    text: str  # e.g. "STEP", "FILE submodel.ldr", "!COLOUR 4 ..."


@dataclass
class RawLine:
    """Line types 2-5 — geometry primitives, preserved verbatim."""

    raw: str


Command = PartLine | MetaCommand | RawLine


def normalize_part_number(s: str) -> str:
    """Ensure part number is lowercase and ends with .dat."""
    s = s.strip()
    if not s.lower().endswith(".dat"):
        s = s + ".dat"
    return s.lower()


def _fmt(v: float) -> str:
    """Format a float without trailing zeros (1.0 → '1', 0.5 → '0.5')."""
    return f"{v:g}"


def _parse_part_line(tokens: list[str]) -> PartLine:
    """Parse tokens from a line-type-1 line (excluding the leading '1')."""
    # tokens: [color, x, y, z, a, b, c, d, e, f, g, h, i, file...]
    if len(tokens) < 14:
        raise ValueError(f"Malformed type-1 line: too few tokens ({len(tokens)})")
    color = int(tokens[0])
    x, y, z = float(tokens[1]), float(tokens[2]), float(tokens[3])
    matrix = tuple(float(tokens[i]) for i in range(4, 13))
    part_file = " ".join(tokens[13:])
    return PartLine(color=color, x=x, y=y, z=z, matrix=matrix, part_file=part_file)


def _parse_v2_part_line(tokens: list[str]) -> PartLine:
    """Parse tokens from a BrickLink Studio type-11 line (excluding the leading '11').

    Format: color uid selected group_id x y z a b c d e f g h i part_file
    """
    if len(tokens) < 17:
        raise ValueError(f"Malformed type-11 line: need 17+ tokens, got {len(tokens)}")
    color = int(tokens[0])
    uid = int(tokens[1])
    selected = tokens[2].strip().lower() == "true"
    group_id = int(tokens[3])
    x, y, z = float(tokens[4]), float(tokens[5]), float(tokens[6])
    matrix = tuple(float(tokens[i]) for i in range(7, 16))
    part_file = " ".join(tokens[16:])
    return PartLine(
        color=color, x=x, y=y, z=z, matrix=matrix, part_file=part_file,
        _uid=uid, _group_id=group_id, _selected=selected,
    )


def parse_ldraw(text: str) -> list[tuple[str, list[Command]]]:
    """Parse an LDraw file (plain .ldr or MPD) into a list of named blocks.

    Returns:
        A list of (name, commands) tuples. For plain .ldr files the list has
        one entry; for MPD files each 0 FILE block is a separate entry.
        The first entry is always the root/main model.
    """
    blocks: list[tuple[str, list[Command]]] = []
    current_name: str = "model.ldr"
    current_commands: list[Command] = []
    in_explicit_file = False

    for raw_line in text.splitlines():
        line = raw_line.strip().lstrip("\ufeff")  # strip BOM that Studio may inject
        if not line:
            continue

        parts = line.split()
        line_type = parts[0]

        if line_type == "0":
            rest = line[2:].strip() if len(line) > 2 else ""
            rest_upper = rest.upper()

            if rest_upper.startswith("FILE "):
                # Start a new MPD block
                if in_explicit_file or current_commands:
                    blocks.append((current_name, current_commands))
                file_name = rest[5:].strip()
                current_name = file_name
                current_commands = []
                in_explicit_file = True
            elif rest_upper == "NOFILE":
                # End of current MPD block
                blocks.append((current_name, current_commands))
                current_name = "model.ldr"
                current_commands = []
                in_explicit_file = False
            else:
                current_commands.append(MetaCommand(text=rest))

        elif line_type == "1":
            cmd = _parse_part_line(parts[1:])
            current_commands.append(cmd)

        elif line_type == "11":
            # BrickLink Studio v2 extension — normalize to PartLine
            cmd = _parse_v2_part_line(parts[1:])
            current_commands.append(cmd)

        else:
            # Line types 2-5: geometry, pass through
            current_commands.append(RawLine(raw=line))

    # Flush the last (or only) block
    if current_commands or not blocks:
        blocks.append((current_name, current_commands))

    return blocks


def _command_to_line(cmd: Command) -> str:
    """Serialize a command object to a single LDraw text line."""
    if isinstance(cmd, MetaCommand):
        if cmd.text:
            return f"0 {cmd.text}"
        return "0"
    if isinstance(cmd, PartLine):
        m = cmd.matrix
        return (
            f"1 {cmd.color} "
            f"{_fmt(cmd.x)} {_fmt(cmd.y)} {_fmt(cmd.z)} "
            f"{_fmt(m[0])} {_fmt(m[1])} {_fmt(m[2])} "
            f"{_fmt(m[3])} {_fmt(m[4])} {_fmt(m[5])} "
            f"{_fmt(m[6])} {_fmt(m[7])} {_fmt(m[8])} "
            f"{cmd.part_file}"
        )
    if isinstance(cmd, RawLine):
        return cmd.raw
    raise TypeError(f"Unknown command type: {type(cmd)}")


def to_ldraw_text(blocks: list[tuple[str, list[Command]]]) -> str:
    """Serialize blocks back to LDraw text.

    Single block → plain .ldr (no FILE/NOFILE wrappers).
    Multiple blocks → MPD format with 0 FILE / 0 NOFILE per block.
    """
    lines: list[str] = []

    if len(blocks) == 1:
        # Plain .ldr
        _name, commands = blocks[0]
        for cmd in commands:
            lines.append(_command_to_line(cmd))
    else:
        # MPD
        for name, commands in blocks:
            lines.append(f"0 FILE {name}")
            for cmd in commands:
                lines.append(_command_to_line(cmd))
            lines.append("0 NOFILE")
            lines.append("")

    return "\n".join(lines) + "\n"


def _fmt6(v: float) -> str:
    """Format a float to 6 decimal places for BrickLink Studio v2 format."""
    return f"{v:.6f}"


def _command_to_v2_line(cmd: Command, uid_iter) -> str:  # type: ignore[type-arg]
    """Serialize a command to a BrickLink Studio type-11 line (for parts)."""
    if isinstance(cmd, PartLine):
        uid = cmd._uid if cmd._uid else next(uid_iter)
        m = cmd.matrix
        selected = "True" if cmd._selected else "False"
        return (
            f"11 {cmd.color} {uid} {selected} {cmd._group_id} "
            f"{_fmt6(cmd.x)} {_fmt6(cmd.y)} {_fmt6(cmd.z)} "
            f"{_fmt6(m[0])} {_fmt6(m[1])} {_fmt6(m[2])} "
            f"{_fmt6(m[3])} {_fmt6(m[4])} {_fmt6(m[5])} "
            f"{_fmt6(m[6])} {_fmt6(m[7])} {_fmt6(m[8])} "
            f"{cmd.part_file}"
        )
    return _command_to_line(cmd)


def to_v2_ldraw_text(blocks: list[tuple[str, list[Command]]]) -> str:
    """Serialize blocks in BrickLink Studio v2 format (type-11 part lines).

    Preserves UIDs from the original load; assigns new sequential UIDs to
    parts that were added since loading (those with _uid == 0).
    """
    import itertools

    max_uid = max(
        (cmd._uid for _, cmds in blocks for cmd in cmds if isinstance(cmd, PartLine) and cmd._uid),
        default=0,
    )
    uid_iter = itertools.count(max_uid + 1)

    lines: list[str] = []

    if len(blocks) == 1:
        name, commands = blocks[0]
        lines.append(f"0 FILE {name}")
        for cmd in commands:
            lines.append(_command_to_v2_line(cmd, uid_iter))
        lines.append("0 NOFILE")
    else:
        for name, commands in blocks:
            lines.append(f"0 FILE {name}")
            for cmd in commands:
                lines.append(_command_to_v2_line(cmd, uid_iter))
            lines.append("0 NOFILE")
            lines.append("")

    return "\n".join(lines) + "\n"
