"""Integration tests for MCP tool functions."""

from __future__ import annotations

import pytest

from brick_mcp.model import get_model, set_model
from brick_mcp.tools.file_ops import get_model_info, new_model, open_model, save_model
from brick_mcp.tools.inspection import get_bom, get_steps, list_parts
from brick_mcp.tools.manipulation import (
    add_part,
    add_step,
    change_color,
    move_part,
    remove_part,
    remove_step,
    rotate_part,
)
from brick_mcp.tools.parts import get_color_info, list_colors, search_parts


class TestNewModel:
    def test_returns_ok(self):
        result = new_model("test")
        assert result["ok"] is True

    def test_creates_model(self):
        new_model("mycastle")
        result = get_model_info()
        assert result["ok"] is True
        assert result["data"]["root_submodel"] == "mycastle.ldr"

    def test_model_starts_empty(self):
        new_model("test")
        result = list_parts()
        assert result["ok"] is True
        assert result["data"] == []

    def test_default_name(self):
        result = new_model()
        assert result["ok"] is True
        assert result["data"]["root_submodel"] == "model.ldr"


class TestGetModelInfo:
    def test_no_model_returns_error(self):
        set_model(None)
        result = get_model_info()
        assert result["ok"] is False
        assert result["error"]["code"] == "NO_MODEL"

    def test_returns_model_info(self):
        new_model("test")
        result = get_model_info()
        assert result["ok"] is True
        data = result["data"]
        assert "root_submodel" in data
        assert "total_part_count" in data
        assert "submodels" in data


class TestOpenModel:
    def test_file_not_found(self, tmp_path):
        result = open_model(str(tmp_path / "nonexistent.ldr"))
        assert result["ok"] is False
        assert result["error"]["code"] == "FILE_NOT_FOUND"

    def test_open_ldr_file(self, tmp_path):
        ldr_path = str(tmp_path / "model.ldr")
        with open(ldr_path, "w") as f:
            f.write("1 4 0 -24 0 1 0 0 0 1 0 0 0 1 3001.dat\n")
        result = open_model(ldr_path)
        assert result["ok"] is True
        assert result["data"]["total_part_count"] == 1

    def test_open_ldr_parts_available(self, tmp_path):
        ldr_path = str(tmp_path / "model.ldr")
        with open(ldr_path, "w") as f:
            f.write("1 4 0 -24 0 1 0 0 0 1 0 0 0 1 3001.dat\n")
        open_model(ldr_path)
        result = list_parts()
        assert result["ok"] is True
        assert len(result["data"]) == 1
        assert result["data"][0]["part_number"] == "3001.dat"

    def test_unsupported_format(self, tmp_path):
        bad_path = str(tmp_path / "model.stl")
        with open(bad_path, "w") as f:
            f.write("solid test\n")
        result = open_model(bad_path)
        assert result["ok"] is False
        assert result["error"]["code"] == "UNSUPPORTED_FORMAT"

    def test_open_io_file(self, tmp_path):
        from brick_mcp.io_file import write_io_file
        io_path = str(tmp_path / "model.io")
        ldr_text = "1 4 0 0 0 1 0 0 0 1 0 0 0 1 3001.dat\n"
        write_io_file(io_path, ldr_text, {})
        result = open_model(io_path)
        assert result["ok"] is True
        assert result["data"]["total_part_count"] == 1


class TestSaveModel:
    def test_no_model_returns_error(self):
        set_model(None)
        result = save_model("/tmp/model.ldr")
        assert result["ok"] is False
        assert result["error"]["code"] == "NO_MODEL"

    def test_no_path_and_no_source_returns_error(self):
        new_model("test")
        result = save_model()
        assert result["ok"] is False
        assert result["error"]["code"] == "NO_PATH"

    def test_save_ldr(self, tmp_path):
        new_model("test")
        add_part(part_number="3001", color=4, x=0, y=0, z=0)
        ldr_path = str(tmp_path / "saved.ldr")
        result = save_model(ldr_path)
        assert result["ok"] is True
        assert ldr_path in result.get("message", "")
        # Verify file was written
        with open(ldr_path) as f:
            content = f.read()
        assert "3001.dat" in content

    def test_save_io(self, tmp_path):
        from brick_mcp.io_file import read_io_file
        new_model("test")
        add_part(part_number="3001", color=4, x=0, y=0, z=0)
        io_path = str(tmp_path / "saved.io")
        result = save_model(io_path)
        assert result["ok"] is True
        model_bytes, _ = read_io_file(io_path)
        assert b"3001.dat" in model_bytes

    def test_save_clears_dirty_flag(self, tmp_path):
        new_model("test")
        add_part(part_number="3001", color=4, x=0, y=0, z=0)
        p = get_model()
        assert p._dirty is True
        ldr_path = str(tmp_path / "model.ldr")
        save_model(ldr_path)
        assert p._dirty is False


class TestListParts:
    def test_empty_model(self):
        new_model("test")
        result = list_parts()
        assert result["ok"] is True
        assert result["data"] == []

    def test_no_model_returns_error(self):
        set_model(None)
        result = list_parts()
        assert result["ok"] is False

    def test_lists_added_parts(self):
        new_model("test")
        add_part(part_number="3001", color=4, x=0, y=-24, z=0)
        result = list_parts()
        assert result["ok"] is True
        parts = result["data"]
        assert len(parts) == 1
        p = parts[0]
        assert p["part_number"] == "3001.dat"
        assert p["color"] == 4
        assert p["y"] == -24
        assert "id" in p
        assert "rotation" in p
        assert len(p["rotation"]) == 9


class TestGetBOM:
    def test_empty_model(self):
        new_model("t")
        result = get_bom()
        assert result["ok"] is True
        assert result["data"] == {}

    def test_counts_parts(self):
        new_model("t")
        add_part("3001", 4, 0, 0, 0)
        add_part("3001", 4, 20, 0, 0)
        add_part("3001", 1, 40, 0, 0)
        result = get_bom()
        bom = result["data"]
        assert bom["3001.dat"]["4"] == 2
        assert bom["3001.dat"]["1"] == 1


class TestGetSteps:
    def test_no_steps_returns_single_implicit(self):
        new_model("t")
        add_part("3001", 4, 0, 0, 0)
        result = get_steps()
        assert result["ok"] is True
        steps = result["data"]
        assert len(steps) == 1
        assert steps[0]["parts_in_step"] == 1

    def test_with_step_boundary(self):
        new_model("t")
        add_part("3001", 4, 0, 0, 0)
        add_step()
        add_part("3004", 1, 20, -24, 0)
        result = get_steps()
        steps = result["data"]
        assert len(steps) == 2


class TestAddPart:
    def test_returns_part_id(self):
        new_model("t")
        result = add_part("3001", 4, 0, 0, 0)
        assert result["ok"] is True
        assert "part_id" in result["data"] or "id" in result["data"]

    def test_invalid_matrix(self):
        new_model("t")
        result = add_part("3001", 4, 0, 0, 0, rotation_matrix=[1, 0, 0])
        assert result["ok"] is False
        assert result["error"]["code"] == "INVALID_MATRIX"

    def test_part_appears_in_list(self):
        new_model("t")
        add_part("3001", 4, x=0, y=-24, z=0)
        result = list_parts()
        assert len(result["data"]) == 1

    def test_no_model_returns_error(self):
        set_model(None)
        result = add_part("3001", 4, 0, 0, 0)
        assert result["ok"] is False
        assert result["error"]["code"] == "NO_MODEL"


class TestRemovePart:
    def test_removes_existing_part(self):
        new_model("t")
        add_result = add_part("3001", 4, 0, 0, 0)
        pid = add_result["data"]["id"]
        result = remove_part(pid)
        assert result["ok"] is True
        assert list_parts()["data"] == []

    def test_unknown_part_id_returns_error(self):
        new_model("t")
        result = remove_part("nonexistent")
        assert result["ok"] is False
        assert result["error"]["code"] == "PART_NOT_FOUND"


class TestMovePart:
    def test_moves_part(self):
        new_model("t")
        add_result = add_part("3001", 4, 0, 0, 0)
        pid = add_result["data"]["id"]
        result = move_part(pid, 20, -24, 0)
        assert result["ok"] is True
        part = result["data"]
        assert part["x"] == 20
        assert part["y"] == -24

    def test_unknown_part_id(self):
        new_model("t")
        result = move_part("bad", 0, 0, 0)
        assert result["ok"] is False
        assert result["error"]["code"] == "PART_NOT_FOUND"


class TestRotatePart:
    def test_rotates_part(self):
        new_model("t")
        add_result = add_part("3001", 4, 0, 0, 0)
        pid = add_result["data"]["id"]
        new_rot = [0, 0, -1, 0, 1, 0, 1, 0, 0]
        result = rotate_part(pid, new_rot)
        assert result["ok"] is True
        assert result["data"]["rotation"] == new_rot

    def test_invalid_matrix(self):
        new_model("t")
        add_result = add_part("3001", 4, 0, 0, 0)
        pid = add_result["data"]["id"]
        result = rotate_part(pid, [1, 0, 0])
        assert result["ok"] is False
        assert result["error"]["code"] == "INVALID_MATRIX"


class TestChangeColor:
    def test_changes_color(self):
        new_model("t")
        add_result = add_part("3001", 4, 0, 0, 0)
        pid = add_result["data"]["id"]
        result = change_color(pid, 1)
        assert result["ok"] is True
        assert result["data"]["color"] == 1


class TestAddRemoveStep:
    def test_add_step(self):
        new_model("t")
        add_part("3001", 4, 0, 0, 0)
        result = add_step()
        assert result["ok"] is True
        assert result["data"]["step_count"] == 1

    def test_remove_step(self):
        new_model("t")
        add_part("3001", 4, 0, 0, 0)
        add_step()
        result = remove_step(0)
        assert result["ok"] is True
        assert result["data"]["step_count"] == 0

    def test_remove_step_invalid_index(self):
        new_model("t")
        result = remove_step(5)
        assert result["ok"] is False
        assert result["error"]["code"] == "STEP_NOT_FOUND"


class TestSearchParts:
    def test_finds_by_name(self):
        result = search_parts("brick 2 x 4")
        assert result["ok"] is True
        parts = result["data"]
        assert any(p["part_number"] == "3001.dat" for p in parts)

    def test_finds_by_number(self):
        result = search_parts("3001")
        assert result["ok"] is True
        parts = result["data"]
        assert any(p["part_number"] == "3001.dat" for p in parts)

    def test_case_insensitive(self):
        result = search_parts("BRICK")
        assert result["ok"] is True
        assert len(result["data"]) > 0

    def test_limit_respected(self):
        result = search_parts("", limit=3)
        assert result["ok"] is True
        assert len(result["data"]) <= 3

    def test_no_results(self):
        result = search_parts("xyznonexistentpart12345")
        assert result["ok"] is True
        assert result["data"] == []


class TestListColors:
    def test_returns_colors(self):
        result = list_colors()
        assert result["ok"] is True
        colors = result["data"]
        assert len(colors) > 10

    def test_colors_have_required_fields(self):
        result = list_colors()
        for color in result["data"]:
            assert "code" in color
            assert "name" in color
            assert "hex" in color

    def test_sorted_by_code(self):
        result = list_colors()
        codes = [c["code"] for c in result["data"]]
        assert codes == sorted(codes)

    def test_includes_common_colors(self):
        result = list_colors()
        codes = {c["code"] for c in result["data"]}
        assert 0 in codes   # Black
        assert 4 in codes   # Red
        assert 15 in codes  # White


class TestGetColorInfo:
    def test_known_color(self):
        result = get_color_info(4)
        assert result["ok"] is True
        data = result["data"]
        assert data["code"] == 4
        assert data["name"] == "Red"
        assert "#" in data["hex"]

    def test_unknown_color(self):
        result = get_color_info(9999)
        assert result["ok"] is False
        assert result["error"]["code"] == "COLOR_NOT_FOUND"
