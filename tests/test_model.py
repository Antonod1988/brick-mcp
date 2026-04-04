"""Tests for the StudioProject model and its manipulation methods."""

from __future__ import annotations

import pytest

from brick_mcp.ldraw import IDENTITY_MATRIX, MetaCommand, PartLine, parse_ldraw
from brick_mcp.model import StudioProject, get_model, set_model


class TestNewModel:
    def test_creates_with_ldr_suffix(self):
        p = StudioProject.new("test")
        assert p.root_submodel == "test.ldr"

    def test_preserves_existing_suffix(self):
        p = StudioProject.new("mymodel.ldr")
        assert p.root_submodel == "mymodel.ldr"

    def test_starts_empty(self):
        p = StudioProject.new("test")
        assert p.list_parts(None) == []

    def test_source_path_is_none(self):
        p = StudioProject.new("test")
        assert p.source_path is None

    def test_not_dirty_initially(self):
        p = StudioProject.new("test")
        assert p._dirty is False


class TestSingleton:
    def test_get_model_returns_set_model(self):
        p = StudioProject.new("x")
        set_model(p)
        assert get_model() is p

    def test_get_model_raises_when_none(self):
        set_model(None)
        with pytest.raises(RuntimeError, match="No model loaded"):
            get_model()


class TestFromBlocks:
    def test_single_block(self):
        blocks = parse_ldraw("1 4 0 -24 0 1 0 0 0 1 0 0 0 1 3001.dat\n")
        p = StudioProject.from_blocks(None, blocks, {})
        parts = p.list_parts(None)
        assert len(parts) == 1
        assert parts[0]["part_number"] == "3001.dat"
        assert parts[0]["color"] == 4
        assert parts[0]["y"] == -24

    def test_mpd_two_blocks(self):
        text = (
            "0 FILE main.ldr\n"
            "1 4 0 0 0 1 0 0 0 1 0 0 0 1 3001.dat\n"
            "0 NOFILE\n"
            "0 FILE sub.ldr\n"
            "1 1 20 0 0 1 0 0 0 1 0 0 0 1 3004.dat\n"
            "0 NOFILE\n"
        )
        blocks = parse_ldraw(text)
        p = StudioProject.from_blocks(None, blocks, {})
        assert p.root_submodel == "main.ldr"
        assert "sub.ldr" in p.submodels
        assert len(p.list_parts(None)) == 1
        assert len(p.list_parts("sub.ldr")) == 1

    def test_assigns_uuids(self):
        blocks = parse_ldraw("1 4 0 0 0 1 0 0 0 1 0 0 0 1 3001.dat\n")
        p = StudioProject.from_blocks(None, blocks, {})
        parts = p.list_parts(None)
        assert len(parts[0]["id"]) == 12

    def test_preserves_raw_zip_entries(self):
        blocks = parse_ldraw("")
        raw = {"thumb.png": b"\x89PNG"}
        p = StudioProject.from_blocks("/some/path.io", blocks, raw)
        assert p.raw_zip_entries == raw


class TestAddPart:
    def test_returns_uuid_string(self):
        p = get_model()
        pid = p.add_part(None, "3001", 4, 0, 0, 0)
        assert isinstance(pid, str)
        assert len(pid) == 12

    def test_part_appears_in_list(self):
        p = get_model()
        pid = p.add_part(None, "3001", 4, 0, -24, 0)
        parts = p.list_parts(None)
        assert len(parts) == 1
        assert parts[0]["id"] == pid
        assert parts[0]["part_number"] == "3001.dat"
        assert parts[0]["color"] == 4
        assert parts[0]["y"] == -24

    def test_normalizes_part_number(self):
        p = get_model()
        p.add_part(None, "3001", 4, 0, 0, 0)
        parts = p.list_parts(None)
        assert parts[0]["part_number"] == "3001.dat"

    def test_default_rotation_is_identity(self):
        p = get_model()
        p.add_part(None, "3001", 4, 0, 0, 0)
        parts = p.list_parts(None)
        assert parts[0]["rotation"] == list(IDENTITY_MATRIX)

    def test_custom_rotation(self):
        p = get_model()
        matrix = (-1, 0, 0, 0, 1, 0, 0, 0, -1)
        p.add_part(None, "3001", 4, 0, 0, 0, matrix)
        parts = p.list_parts(None)
        assert parts[0]["rotation"] == list(matrix)

    def test_invalid_matrix_raises(self):
        p = get_model()
        with pytest.raises(ValueError, match="9"):
            p.add_part(None, "3001", 4, 0, 0, 0, (1, 0, 0))

    def test_marks_dirty(self):
        p = get_model()
        assert p._dirty is False
        p.add_part(None, "3001", 4, 0, 0, 0)
        assert p._dirty is True

    def test_multiple_parts(self):
        p = get_model()
        p.add_part(None, "3001", 4, 0, 0, 0)
        p.add_part(None, "3004", 1, 20, 0, 0)
        parts = p.list_parts(None)
        assert len(parts) == 2

    def test_ids_are_unique(self):
        p = get_model()
        ids = {p.add_part(None, "3001", 4, i * 20, 0, 0) for i in range(10)}
        assert len(ids) == 10

    def test_unknown_submodel_raises(self):
        p = get_model()
        with pytest.raises(KeyError):
            p.add_part("nonexistent.ldr", "3001", 4, 0, 0, 0)


class TestRemovePart:
    def test_removes_existing_part(self):
        p = get_model()
        pid = p.add_part(None, "3001", 4, 0, 0, 0)
        assert p.remove_part(pid, None) is True
        assert p.list_parts(None) == []

    def test_returns_false_for_unknown_id(self):
        p = get_model()
        assert p.remove_part("nonexistent", None) is False

    def test_marks_dirty(self):
        p = get_model()
        pid = p.add_part(None, "3001", 4, 0, 0, 0)
        p._dirty = False
        p.remove_part(pid, None)
        assert p._dirty is True

    def test_removes_from_both_list_and_index(self):
        p = get_model()
        pid = p.add_part(None, "3001", 4, 0, 0, 0)
        p.remove_part(pid, None)
        sd = p._submodel(None)
        assert pid not in sd._parts
        for cmd in sd.commands:
            if isinstance(cmd, PartLine):
                assert cmd._id != pid


class TestMovePart:
    def test_moves_to_new_coords(self):
        p = get_model()
        pid = p.add_part(None, "3001", 4, 0, 0, 0)
        assert p.move_part(pid, 20, -24, 0, None) is True
        parts = p.list_parts(None)
        assert parts[0]["x"] == 20
        assert parts[0]["y"] == -24
        assert parts[0]["z"] == 0

    def test_returns_false_for_unknown_id(self):
        p = get_model()
        assert p.move_part("bad", 0, 0, 0, None) is False

    def test_marks_dirty(self):
        p = get_model()
        pid = p.add_part(None, "3001", 4, 0, 0, 0)
        p._dirty = False
        p.move_part(pid, 20, 0, 0, None)
        assert p._dirty is True


class TestRotatePart:
    def test_changes_rotation(self):
        p = get_model()
        pid = p.add_part(None, "3001", 4, 0, 0, 0)
        new_matrix = (0, 0, -1, 0, 1, 0, 1, 0, 0)
        assert p.rotate_part(pid, new_matrix, None) is True
        parts = p.list_parts(None)
        assert parts[0]["rotation"] == list(new_matrix)

    def test_returns_false_for_unknown_id(self):
        p = get_model()
        assert p.rotate_part("bad", IDENTITY_MATRIX, None) is False

    def test_invalid_matrix_raises(self):
        p = get_model()
        pid = p.add_part(None, "3001", 4, 0, 0, 0)
        with pytest.raises(ValueError):
            p.rotate_part(pid, (1, 0), None)


class TestChangeColor:
    def test_changes_color(self):
        p = get_model()
        pid = p.add_part(None, "3001", 4, 0, 0, 0)
        assert p.change_color(pid, 1, None) is True
        parts = p.list_parts(None)
        assert parts[0]["color"] == 1

    def test_returns_false_for_unknown_id(self):
        p = get_model()
        assert p.change_color("bad", 1, None) is False


class TestSteps:
    def test_no_steps_returns_single_implicit_step(self):
        p = get_model()
        p.add_part(None, "3001", 4, 0, 0, 0)
        steps = p.get_steps(None)
        assert len(steps) == 1
        assert steps[0]["step_index"] == 0
        assert steps[0]["parts_in_step"] == 1
        assert steps[0]["cumulative_parts"] == 1

    def test_add_step_creates_boundary(self):
        p = get_model()
        p.add_part(None, "3001", 4, 0, 0, 0)
        count = p.add_step(None)
        assert count == 1
        p.add_part(None, "3004", 1, 20, 0, 0)
        steps = p.get_steps(None)
        assert len(steps) == 2
        assert steps[0]["parts_in_step"] == 1
        assert steps[1]["parts_in_step"] == 1
        assert steps[1]["cumulative_parts"] == 2

    def test_remove_step_by_index(self):
        p = get_model()
        p.add_part(None, "3001", 4, 0, 0, 0)
        p.add_step(None)
        p.add_part(None, "3004", 1, 20, 0, 0)
        assert p.remove_step(0, None) is True
        steps = p.get_steps(None)
        assert len(steps) == 1

    def test_remove_step_invalid_index(self):
        p = get_model()
        assert p.remove_step(5, None) is False

    def test_empty_model_has_one_empty_step(self):
        p = get_model()
        steps = p.get_steps(None)
        assert len(steps) == 1
        assert steps[0]["parts_in_step"] == 0


class TestBOM:
    def test_empty_bom(self):
        p = get_model()
        bom = p.get_bom(None)
        assert bom == {}

    def test_single_part(self):
        p = get_model()
        p.add_part(None, "3001", 4, 0, 0, 0)
        bom = p.get_bom(None)
        assert bom == {"3001.dat": {"4": 1}}

    def test_multiple_same_part_same_color(self):
        p = get_model()
        p.add_part(None, "3001", 4, 0, 0, 0)
        p.add_part(None, "3001", 4, 20, 0, 0)
        bom = p.get_bom(None)
        assert bom["3001.dat"]["4"] == 2

    def test_multiple_colors(self):
        p = get_model()
        p.add_part(None, "3001", 4, 0, 0, 0)
        p.add_part(None, "3001", 1, 20, 0, 0)
        bom = p.get_bom(None)
        assert bom["3001.dat"]["4"] == 1
        assert bom["3001.dat"]["1"] == 1

    def test_multiple_part_types(self):
        p = get_model()
        p.add_part(None, "3001", 4, 0, 0, 0)
        p.add_part(None, "3004", 4, 20, 0, 0)
        bom = p.get_bom(None)
        assert "3001.dat" in bom
        assert "3004.dat" in bom


class TestInfo:
    def test_info_structure(self):
        p = get_model()
        info = p.info()
        assert "source_path" in info
        assert "filename" in info
        assert "root_submodel" in info
        assert "submodels" in info
        assert "total_part_count" in info
        assert "is_dirty" in info

    def test_part_count(self):
        p = get_model()
        p.add_part(None, "3001", 4, 0, 0, 0)
        p.add_part(None, "3004", 1, 20, 0, 0)
        assert p.info()["total_part_count"] == 2

    def test_is_dirty_reflects_mutations(self):
        p = get_model()
        assert p.info()["is_dirty"] is False
        p.add_part(None, "3001", 4, 0, 0, 0)
        assert p.info()["is_dirty"] is True


class TestSerialization:
    def test_roundtrip_single_part(self):
        p = get_model()
        p.add_part(None, "3001.dat", 4, 0, -24, 0)
        ldr_text = p.to_ldraw_text()
        assert "3001.dat" in ldr_text
        # Re-parse and verify
        blocks = parse_ldraw(ldr_text)
        p2 = StudioProject.from_blocks(None, blocks, {})
        parts = p2.list_parts(None)
        assert len(parts) == 1
        assert parts[0]["color"] == 4
        assert parts[0]["y"] == -24

    def test_roundtrip_with_step(self):
        p = get_model()
        p.add_part(None, "3001.dat", 4, 0, 0, 0)
        p.add_step(None)
        p.add_part(None, "3004.dat", 1, 20, -24, 0)
        ldr_text = p.to_ldraw_text()
        assert "0 STEP" in ldr_text
        blocks = parse_ldraw(ldr_text)
        p2 = StudioProject.from_blocks(None, blocks, {})
        steps = p2.get_steps(None)
        assert len(steps) == 2
