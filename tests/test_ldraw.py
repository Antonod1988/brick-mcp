"""Tests for the LDraw parser and serializer."""

from __future__ import annotations

import pytest

from brick_mcp.ldraw import (
    IDENTITY_MATRIX,
    MetaCommand,
    PartLine,
    RawLine,
    normalize_part_number,
    parse_ldraw,
    to_ldraw_text,
)


class TestNormalizePartNumber:
    def test_adds_dat_suffix(self):
        assert normalize_part_number("3001") == "3001.dat"

    def test_preserves_existing_suffix(self):
        assert normalize_part_number("3001.dat") == "3001.dat"

    def test_lowercases(self):
        assert normalize_part_number("3001.DAT") == "3001.dat"

    def test_strips_whitespace(self):
        assert normalize_part_number("  3001  ") == "3001.dat"

    def test_mixed_case_name(self):
        assert normalize_part_number("STUD.dat") == "stud.dat"


class TestIdentityMatrix:
    def test_has_nine_elements(self):
        assert len(IDENTITY_MATRIX) == 9

    def test_is_correct(self):
        assert IDENTITY_MATRIX == (1, 0, 0, 0, 1, 0, 0, 0, 1)


class TestParsePartLine:
    def test_basic_part_line(self):
        text = "1 4 0 -24 0 1 0 0 0 1 0 0 0 1 3001.dat\n"
        blocks = parse_ldraw(text)
        assert len(blocks) == 1
        cmds = blocks[0][1]
        assert len(cmds) == 1
        cmd = cmds[0]
        assert isinstance(cmd, PartLine)
        assert cmd.color == 4
        assert cmd.x == 0.0
        assert cmd.y == -24.0
        assert cmd.z == 0.0
        assert cmd.matrix == (1, 0, 0, 0, 1, 0, 0, 0, 1)
        assert cmd.part_file == "3001.dat"

    def test_colored_part(self):
        text = "1 1 20 0 0 1 0 0 0 1 0 0 0 1 3004.dat\n"
        blocks = parse_ldraw(text)
        cmd = blocks[0][1][0]
        assert cmd.color == 1
        assert cmd.x == 20.0

    def test_part_file_with_spaces(self):
        # Part filenames can contain spaces
        text = "1 15 0 0 0 1 0 0 0 1 0 0 0 1 parts with spaces.dat\n"
        blocks = parse_ldraw(text)
        cmd = blocks[0][1][0]
        assert cmd.part_file == "parts with spaces.dat"

    def test_rotation_matrix_parsed(self):
        text = "1 4 0 0 0 -1 0 0 0 1 0 0 0 -1 3001.dat\n"
        blocks = parse_ldraw(text)
        cmd = blocks[0][1][0]
        assert cmd.matrix == (-1, 0, 0, 0, 1, 0, 0, 0, -1)


class TestParseMetaCommands:
    def test_step_command(self):
        text = "0 STEP\n"
        blocks = parse_ldraw(text)
        cmds = blocks[0][1]
        assert len(cmds) == 1
        assert isinstance(cmds[0], MetaCommand)
        assert cmds[0].text == "STEP"

    def test_comment(self):
        text = "0 This is a comment\n"
        blocks = parse_ldraw(text)
        cmd = blocks[0][1][0]
        assert isinstance(cmd, MetaCommand)
        assert cmd.text == "This is a comment"

    def test_empty_meta(self):
        text = "0\n"
        blocks = parse_ldraw(text)
        cmd = blocks[0][1][0]
        assert isinstance(cmd, MetaCommand)
        assert cmd.text == ""


class TestParseRawLines:
    def test_line_type_2(self):
        text = "2 24 0 0 0 10 0 0\n"
        blocks = parse_ldraw(text)
        cmd = blocks[0][1][0]
        assert isinstance(cmd, RawLine)
        assert cmd.raw == "2 24 0 0 0 10 0 0"

    def test_line_type_3(self):
        text = "3 16 0 0 0 10 0 0 5 5 0\n"
        blocks = parse_ldraw(text)
        cmd = blocks[0][1][0]
        assert isinstance(cmd, RawLine)

    def test_line_type_4(self):
        text = "4 16 0 0 0 10 0 0 10 10 0 0 10 0\n"
        blocks = parse_ldraw(text)
        cmd = blocks[0][1][0]
        assert isinstance(cmd, RawLine)


class TestParseMPD:
    def test_two_file_blocks(self):
        text = (
            "0 FILE main.ldr\n"
            "1 4 0 0 0 1 0 0 0 1 0 0 0 1 3001.dat\n"
            "0 NOFILE\n"
            "0 FILE sub.ldr\n"
            "1 1 20 0 0 1 0 0 0 1 0 0 0 1 3004.dat\n"
            "0 NOFILE\n"
        )
        blocks = parse_ldraw(text)
        assert len(blocks) == 2
        assert blocks[0][0] == "main.ldr"
        assert blocks[1][0] == "sub.ldr"
        assert len(blocks[0][1]) == 1
        assert len(blocks[1][1]) == 1

    def test_root_is_first_block(self):
        text = "0 FILE root.ldr\n" "1 4 0 0 0 1 0 0 0 1 0 0 0 1 3001.dat\n" "0 NOFILE\n"
        blocks = parse_ldraw(text)
        assert blocks[0][0] == "root.ldr"

    def test_plain_ldr_has_one_block(self):
        text = "1 4 0 0 0 1 0 0 0 1 0 0 0 1 3001.dat\n"
        blocks = parse_ldraw(text)
        assert len(blocks) == 1

    def test_empty_text_yields_one_empty_block(self):
        blocks = parse_ldraw("")
        assert len(blocks) == 1
        assert blocks[0][1] == []

    def test_blank_lines_ignored(self):
        text = "\n\n1 4 0 0 0 1 0 0 0 1 0 0 0 1 3001.dat\n\n"
        blocks = parse_ldraw(text)
        assert len(blocks[0][1]) == 1


class TestRoundTrip:
    def test_single_part_roundtrip(self):
        text = "1 4 0 -24 0 1 0 0 0 1 0 0 0 1 3001.dat\n"
        blocks = parse_ldraw(text)
        out = to_ldraw_text(blocks)
        blocks2 = parse_ldraw(out)
        cmd2 = blocks2[0][1][0]
        assert isinstance(cmd2, PartLine)
        assert cmd2.color == 4
        assert cmd2.x == 0
        assert cmd2.y == -24
        assert cmd2.z == 0
        assert cmd2.part_file == "3001.dat"

    def test_step_roundtrip(self):
        text = "1 4 0 0 0 1 0 0 0 1 0 0 0 1 3001.dat\n0 STEP\n"
        blocks = parse_ldraw(text)
        out = to_ldraw_text(blocks)
        blocks2 = parse_ldraw(out)
        cmds = blocks2[0][1]
        assert isinstance(cmds[0], PartLine)
        assert isinstance(cmds[1], MetaCommand)
        assert cmds[1].text == "STEP"

    def test_mpd_roundtrip(self):
        text = (
            "0 FILE main.ldr\n"
            "1 4 0 0 0 1 0 0 0 1 0 0 0 1 3001.dat\n"
            "0 NOFILE\n"
            "\n"
            "0 FILE sub.ldr\n"
            "1 1 20 0 0 1 0 0 0 1 0 0 0 1 3004.dat\n"
            "0 NOFILE\n"
            "\n"
        )
        blocks = parse_ldraw(text)
        out = to_ldraw_text(blocks)
        blocks2 = parse_ldraw(out)
        assert len(blocks2) == 2
        assert blocks2[0][0] == "main.ldr"
        assert blocks2[1][0] == "sub.ldr"

    def test_float_formatting(self):
        # 1.0 should serialize as "1" not "1.0"
        text = "1 4 20 -24 0 1 0 0 0 1 0 0 0 1 3001.dat\n"
        blocks = parse_ldraw(text)
        out = to_ldraw_text(blocks)
        assert " 20 " in out
        assert " -24 " in out
        assert "20.0" not in out
        assert "-24.0" not in out

    def test_fractional_coordinates_preserved(self):
        text = "1 4 0.5 -24.5 0 1 0 0 0 1 0 0 0 1 3001.dat\n"
        blocks = parse_ldraw(text)
        cmd = blocks[0][1][0]
        assert cmd.x == 0.5
        assert cmd.y == -24.5
        out = to_ldraw_text(blocks)
        assert "0.5" in out
        assert "-24.5" in out
