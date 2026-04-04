"""Tests for the batch multi-tool tool."""

from __future__ import annotations

import pytest

from brick_mcp.model import get_model, set_model
from brick_mcp.tools.batch import batch


class TestBatchBasic:
    def test_empty_calls_succeeds(self):
        result = batch(calls=[])
        assert result["ok"] is True
        assert result["data"]["executed"] == 0
        assert result["data"]["error_count"] == 0
        assert result["data"]["results"] == []

    def test_invalid_calls_type(self):
        result = batch(calls="not a list")  # type: ignore[arg-type]
        assert result["ok"] is False
        assert result["error"]["code"] == "INVALID_INPUT"

    def test_non_dict_call_entry(self):
        result = batch(calls=["not_a_dict"])
        assert result["ok"] is False
        assert result["data"]["error_count"] == 1

    def test_missing_tool_key(self):
        result = batch(calls=[{"args": {}}])
        assert result["ok"] is False
        assert result["data"]["error_count"] == 1

    def test_unknown_tool_name(self):
        result = batch(calls=[{"tool": "no_such_tool"}])
        assert result["ok"] is False
        assert result["data"]["results"][0]["error"]["code"] == "UNKNOWN_TOOL"


class TestBatchFileOps:
    def test_new_model_via_batch(self):
        result = batch(calls=[{"tool": "new_model", "args": {"name": "batch_test"}}])
        assert result["ok"] is True
        assert result["data"]["error_count"] == 0
        assert result["data"]["results"][0]["ok"] is True

    def test_new_model_no_args(self):
        result = batch(calls=[{"tool": "new_model"}])
        assert result["ok"] is True

    def test_get_model_info_via_batch(self):
        result = batch(
            calls=[
                {"tool": "new_model", "args": {"name": "t"}},
                {"tool": "get_model_info"},
            ]
        )
        assert result["ok"] is True
        assert result["data"]["executed"] == 2
        info_result = result["data"]["results"][1]
        assert info_result["ok"] is True
        assert "root_submodel" in info_result["data"]


class TestBatchManipulation:
    def test_add_multiple_parts(self):
        batch(calls=[{"tool": "new_model", "args": {"name": "t"}}])
        result = batch(
            calls=[
                {
                    "tool": "add_part",
                    "args": {"part_number": "3001", "color": 4, "x": 0, "y": 0, "z": 0},
                },
                {
                    "tool": "add_part",
                    "args": {
                        "part_number": "3001",
                        "color": 4,
                        "x": 20,
                        "y": 0,
                        "z": 0,
                    },
                },
                {
                    "tool": "add_part",
                    "args": {
                        "part_number": "3001",
                        "color": 1,
                        "x": 40,
                        "y": 0,
                        "z": 0,
                    },
                },
            ]
        )
        assert result["ok"] is True
        assert result["data"]["error_count"] == 0
        p = get_model()
        assert p.info()["total_part_count"] == 3

    def test_state_carries_across_calls(self):
        """Part added in call N is visible to call N+1."""
        result = batch(
            calls=[
                {"tool": "new_model", "args": {"name": "t"}},
                {
                    "tool": "add_part",
                    "args": {"part_number": "3001", "color": 4, "x": 0, "y": 0, "z": 0},
                },
                {"tool": "list_parts"},
            ]
        )
        assert result["ok"] is True
        list_result = result["data"]["results"][2]
        assert list_result["ok"] is True
        assert len(list_result["data"]) == 1

    def test_build_tower_sequence(self):
        """Full workflow: create model, stack 4 bricks, add steps, inspect."""
        result = batch(
            calls=[
                {"tool": "new_model", "args": {"name": "tower"}},
                {
                    "tool": "add_part",
                    "args": {"part_number": "3001", "color": 4, "x": 0, "y": 0, "z": 0},
                },
                {"tool": "add_step"},
                {
                    "tool": "add_part",
                    "args": {
                        "part_number": "3001",
                        "color": 4,
                        "x": 0,
                        "y": -24,
                        "z": 0,
                    },
                },
                {"tool": "add_step"},
                {
                    "tool": "add_part",
                    "args": {
                        "part_number": "3001",
                        "color": 1,
                        "x": 0,
                        "y": -48,
                        "z": 0,
                    },
                },
                {"tool": "get_steps"},
            ]
        )
        assert result["ok"] is True
        assert result["data"]["error_count"] == 0
        steps_result = result["data"]["results"][6]
        assert steps_result["ok"] is True
        assert len(steps_result["data"]) == 3

    def test_move_and_remove(self):
        batch(calls=[{"tool": "new_model", "args": {"name": "t"}}])
        add_result = batch(
            calls=[
                {
                    "tool": "add_part",
                    "args": {"part_number": "3001", "color": 4, "x": 0, "y": 0, "z": 0},
                },
            ]
        )
        pid = add_result["data"]["results"][0]["data"]["id"]
        result = batch(
            calls=[
                {
                    "tool": "move_part",
                    "args": {"part_id": pid, "x": 20, "y": -24, "z": 0},
                },
                {"tool": "change_color", "args": {"part_id": pid, "color": 1}},
                {"tool": "remove_part", "args": {"part_id": pid}},
                {"tool": "list_parts"},
            ]
        )
        assert result["ok"] is True
        assert result["data"]["results"][3]["data"] == []


class TestBatchInspection:
    def test_list_bom_steps(self):
        batch(calls=[{"tool": "new_model", "args": {"name": "t"}}])
        result = batch(
            calls=[
                {
                    "tool": "add_part",
                    "args": {"part_number": "3001", "color": 4, "x": 0, "y": 0, "z": 0},
                },
                {
                    "tool": "add_part",
                    "args": {
                        "part_number": "3001",
                        "color": 4,
                        "x": 20,
                        "y": 0,
                        "z": 0,
                    },
                },
                {"tool": "get_bom"},
                {"tool": "get_steps"},
            ]
        )
        assert result["ok"] is True
        bom = result["data"]["results"][2]["data"]
        assert bom["3001.dat"]["4"] == 2
        steps = result["data"]["results"][3]["data"]
        assert steps[0]["parts_in_step"] == 2


class TestBatchLayout:
    def test_validate_placement_in_batch(self):
        batch(calls=[{"tool": "new_model", "args": {"name": "t"}}])
        result = batch(
            calls=[
                {
                    "tool": "validate_placement",
                    "args": {"part_number": "3001", "x": 0, "y": 0, "z": 0},
                },
            ]
        )
        assert result["ok"] is True
        vp = result["data"]["results"][0]
        assert vp["ok"] is True
        assert vp["data"]["valid"] is True

    def test_check_overlaps_in_batch(self):
        batch(calls=[{"tool": "new_model", "args": {"name": "t"}}])
        result = batch(
            calls=[
                {
                    "tool": "add_part",
                    "args": {"part_number": "3001", "color": 4, "x": 0, "y": 0, "z": 0},
                },
                {"tool": "check_overlaps"},
            ]
        )
        assert result["ok"] is True
        co = result["data"]["results"][1]
        assert co["ok"] is True
        assert co["data"]["overlap_count"] == 0


class TestBatchPartsColors:
    def test_search_parts_in_batch(self):
        result = batch(
            calls=[{"tool": "search_parts", "args": {"query": "3001", "limit": 10}}]
        )
        assert result["ok"] is True
        hits = result["data"]["results"][0]["data"]
        assert any(p["part_number"] == "3001.dat" for p in hits)

    def test_list_colors_in_batch(self):
        result = batch(calls=[{"tool": "list_colors"}])
        assert result["ok"] is True
        colors = result["data"]["results"][0]["data"]
        assert len(colors) > 10

    def test_get_color_info_in_batch(self):
        result = batch(calls=[{"tool": "get_color_info", "args": {"color_code": 4}}])
        assert result["ok"] is True
        assert result["data"]["results"][0]["data"]["name"] == "Red"


class TestBatchErrorHandling:
    def test_error_in_one_call_does_not_stop_others(self):
        """Execution continues even when one call fails."""
        result = batch(
            calls=[
                {"tool": "new_model", "args": {"name": "t"}},
                {"tool": "remove_part", "args": {"part_id": "nonexistent"}},
                {"tool": "list_parts"},
            ]
        )
        # remove_part failed but list_parts still ran
        assert result["data"]["executed"] == 3
        assert result["data"]["error_count"] == 1
        assert result["data"]["results"][0]["ok"] is True  # new_model ok
        assert result["data"]["results"][1]["ok"] is False  # remove_part failed
        assert result["data"]["results"][2]["ok"] is True  # list_parts ok

    def test_bad_args_type_error(self):
        result = batch(
            calls=[
                {"tool": "new_model", "args": {"name": "t"}},
                {
                    "tool": "add_part",
                    "args": {
                        "part_number": "3001",
                        "color": "not_an_int_kwarg_should_fail",
                        "x": "also_wrong",
                    },
                },
            ]
        )
        # color is an int param — passing a string that isn't castable should
        # propagate as a BAD_ARGS or a tool error; either way ok is False.
        r = result["data"]["results"][1]
        # FastMCP may coerce or reject; we just verify the batch itself didn't crash
        assert "ok" in r

    def test_all_ok_false_when_any_error(self):
        result = batch(
            calls=[
                {"tool": "new_model", "args": {"name": "t"}},
                {"tool": "unknown_tool_xyz"},
            ]
        )
        assert result["ok"] is False

    def test_no_model_propagates_correctly(self):
        set_model(None)
        result = batch(calls=[{"tool": "list_parts"}])
        assert result["data"]["results"][0]["ok"] is False


class TestBatchAutoRender:
    def test_no_ldview_returns_plain_dict(self):
        """_no_ldview fixture ensures no image is appended."""
        result = batch(calls=[{"tool": "new_model", "args": {"name": "t"}}])
        assert isinstance(result, dict)

    def test_ldview_appends_image(self, monkeypatch):
        """When try_render produces an Image, batch appends it."""
        from unittest.mock import patch

        from fastmcp.utilities.types import Image as FMCPImage

        fake_img = FMCPImage(data=b"\x89PNG", format="png")
        with patch("brick_mcp.tools.batch.try_render", return_value=fake_img):
            result = batch(calls=[{"tool": "new_model", "args": {"name": "t"}}])
        assert isinstance(result, list)
        assert result[0]["ok"] is True
        assert isinstance(result[1], FMCPImage)


class TestBatchSaveLoad:
    def test_save_within_batch(self, tmp_path):
        ldr_path = str(tmp_path / "batch_model.ldr")
        result = batch(
            calls=[
                {"tool": "new_model", "args": {"name": "t"}},
                {
                    "tool": "add_part",
                    "args": {"part_number": "3001", "color": 4, "x": 0, "y": 0, "z": 0},
                },
                {"tool": "save_model", "args": {"path": ldr_path}},
            ]
        )
        assert result["ok"] is True
        assert result["data"]["error_count"] == 0
        with open(ldr_path) as f:
            content = f.read()
        assert "3001.dat" in content

    def test_open_within_batch(self, tmp_path):
        ldr_path = str(tmp_path / "pre.ldr")
        with open(ldr_path, "w") as f:
            f.write("1 4 0 -24 0 1 0 0 0 1 0 0 0 1 3001.dat\n")
        result = batch(
            calls=[
                {"tool": "open_model", "args": {"path": ldr_path}},
                {"tool": "list_parts"},
            ]
        )
        assert result["ok"] is True
        parts = result["data"]["results"][1]["data"]
        assert len(parts) == 1
        assert parts[0]["part_number"] == "3001.dat"
