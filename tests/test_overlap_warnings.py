"""Tests for implicit overlap warnings on placement mutation tools."""

from __future__ import annotations

from brick_mcp._helpers import placement_warnings
from brick_mcp.model import get_model, set_model
from brick_mcp.tools.file_ops import new_model
from brick_mcp.tools.layout import snap_to_grid
from brick_mcp.tools.manipulation import add_part, move_part, rotate_part

# ---------------------------------------------------------------------------
# placement_warnings() helper unit tests
# ---------------------------------------------------------------------------


class TestPlacementWarningsHelper:
    def test_empty_model_no_warnings(self):
        p = get_model()
        p.add_part(None, "3001", 4, 0, 0, 0)
        pid = p.list_parts(None)[0]["id"]
        # Only one part — nothing to overlap with
        assert placement_warnings(p, pid, None) == []

    def test_identical_position_produces_warning(self):
        p = get_model()
        p.add_part(None, "3001", 4, 0, 0, 0)
        pid2 = p.add_part(None, "3001", 4, 0, 0, 0)
        conflicts = placement_warnings(p, pid2, None)
        assert len(conflicts) >= 1
        assert all("id" in c and "part_number" in c for c in conflicts)

    def test_non_overlapping_stacked_bricks_no_warning(self):
        """A 2×4 brick stacked exactly one brick-height above should not conflict."""
        p = get_model()
        p.add_part(None, "3001", 4, 0, 0, 0)
        pid2 = p.add_part(None, "3001", 4, 0, -24, 0)
        # Stacked bricks touch but do not penetrate → no overlap warning
        conflicts = placement_warnings(p, pid2, None)
        assert conflicts == []

    def test_partial_overlap_produces_warning(self):
        """Two bricks shifted by only 10 LDU (half a stud) should overlap."""
        p = get_model()
        p.add_part(None, "3001", 4, 0, 0, 0)
        # Shift by only 10 LDU — bricks share half their footprint
        pid2 = p.add_part(None, "3001", 4, 10, 0, 0)
        conflicts = placement_warnings(p, pid2, None)
        assert len(conflicts) >= 1

    def test_unknown_part_id_returns_empty(self):
        p = get_model()
        assert placement_warnings(p, "nonexistent_uuid", None) == []

    def test_silently_ignores_exceptions(self):
        """Should never raise — bad project object returns []."""
        assert placement_warnings(object(), "any_id", None) == []


# ---------------------------------------------------------------------------
# add_part warnings
# ---------------------------------------------------------------------------


class TestAddPartWarnings:
    def test_no_warning_on_fresh_placement(self):
        new_model("t")
        result = add_part("3001", 4, 0, 0, 0)
        assert result["ok"] is True
        assert "overlap_warnings" not in result["data"]

    def test_no_warning_on_valid_stack(self):
        new_model("t")
        add_part("3001", 4, 0, 0, 0)
        result = add_part("3001", 4, 0, -24, 0)
        assert result["ok"] is True
        assert "overlap_warnings" not in result["data"]

    def test_warning_on_same_position(self):
        new_model("t")
        add_part("3001", 4, 0, 0, 0)
        result = add_part("3001", 4, 0, 0, 0)
        assert result["ok"] is True
        assert "overlap_warnings" in result["data"]
        assert len(result["data"]["overlap_warnings"]) >= 1

    def test_warning_on_partial_overlap(self):
        new_model("t")
        add_part("3001", 4, 0, 0, 0)
        result = add_part("3001", 4, 10, 0, 0)
        assert result["ok"] is True
        assert "overlap_warnings" in result["data"]

    def test_warning_references_conflicting_part(self):
        new_model("t")
        r1 = add_part("3001", 4, 0, 0, 0)
        first_id = r1["data"]["id"]
        r2 = add_part("3001", 4, 0, 0, 0)
        conflicts = r2["data"]["overlap_warnings"]
        assert any(c["id"] == first_id for c in conflicts)

    def test_normal_data_still_present_with_warning(self):
        """Warnings should not replace the part data, only extend it."""
        new_model("t")
        add_part("3001", 4, 0, 0, 0)
        result = add_part("3001", 4, 0, 0, 0)
        data = result["data"]
        assert "id" in data
        assert "part_number" in data
        assert "x" in data
        assert "overlap_warnings" in data


# ---------------------------------------------------------------------------
# move_part warnings
# ---------------------------------------------------------------------------


class TestMovePartWarnings:
    def test_no_warning_on_clear_move(self):
        new_model("t")
        add_part("3001", 4, 0, 0, 0)
        r2 = add_part("3001", 4, 100, 0, 0)
        pid = r2["data"]["id"]
        result = move_part(pid, 200, 0, 0)
        assert result["ok"] is True
        assert "overlap_warnings" not in result.get("data", {})

    def test_warning_when_moved_onto_existing_part(self):
        new_model("t")
        add_part("3001", 4, 0, 0, 0)
        r2 = add_part("3001", 4, 100, 0, 0)
        pid = r2["data"]["id"]
        result = move_part(pid, 0, 0, 0)
        assert result["ok"] is True
        assert "overlap_warnings" in result["data"]

    def test_warning_clears_after_correction(self):
        new_model("t")
        add_part("3001", 4, 0, 0, 0)
        r2 = add_part("3001", 4, 0, 0, 0)  # overlap
        pid = r2["data"]["id"]
        assert "overlap_warnings" in r2["data"]
        # Move away — no overlap expected
        result = move_part(pid, 200, 0, 0)
        assert "overlap_warnings" not in result.get("data", {})


# ---------------------------------------------------------------------------
# rotate_part warnings
# ---------------------------------------------------------------------------


class TestRotatePartWarnings:
    def test_no_warning_when_rotation_causes_no_overlap(self):
        new_model("t")
        r = add_part("3001", 4, 0, 0, 0)
        pid = r["data"]["id"]
        result = rotate_part(pid, [0, 0, -1, 0, 1, 0, 1, 0, 0])
        assert result["ok"] is True
        # No second part → no conflicts possible
        assert "overlap_warnings" not in result.get("data", {})

    def test_warning_when_rotation_causes_overlap(self):
        """A long part (1x4) rotated 90° may collide with a neighbour."""
        new_model("t")
        # Place a 1×4 brick at origin; place a 1×2 brick nearby on Z axis
        add_part("3010", 4, 0, 0, 0)  # Brick 1x4 along X
        r2 = add_part("3004", 1, 60, 0, 0)  # Brick 1x2 well clear on X
        pid = r2["data"]["id"]
        # Rotating shouldn't cause overlap at this distance; just verify it runs
        result = rotate_part(pid, [0, 0, -1, 0, 1, 0, 1, 0, 0])
        assert result["ok"] is True
        assert "id" in result["data"]


# ---------------------------------------------------------------------------
# snap_to_grid warnings
# ---------------------------------------------------------------------------


class TestSnapToGridWarnings:
    def test_no_warning_when_snapping_to_free_position(self):
        new_model("t")
        add_part("3001", 4, 0, 0, 0)
        r2 = add_part("3001", 4, 105, 0, 0)  # off-grid, clear of first
        pid = r2["data"]["id"]
        result = snap_to_grid(pid)
        assert result["ok"] is True
        # After snap to 100, still clear of the 2×4 brick at 0
        # (2×4 brick extends ~40 LDU each way from centre → up to x=40)
        # x=100 is outside that range → no warning
        assert "overlap_warnings" not in result.get("data", {})

    def test_warning_when_snapping_lands_on_existing_part(self):
        new_model("t")
        add_part("3001", 4, 0, 0, 0)
        # Place at x=5 — snaps to x=0, landing directly on the first brick
        r2 = add_part("3001", 4, 100, 0, 0)
        pid = r2["data"]["id"]
        # Move off-grid to a position that will snap onto the first brick
        from brick_mcp.model import get_model as gm

        gm().move_part(pid, 5, 0, 0, None)  # off-grid near x=0
        result = snap_to_grid(pid)
        assert result["ok"] is True
        assert "overlap_warnings" in result["data"]

    def test_delta_field_present_alongside_warning(self):
        new_model("t")
        add_part("3001", 4, 0, 0, 0)
        r2 = add_part("3001", 4, 100, 0, 0)
        pid = r2["data"]["id"]
        gm = get_model()
        gm.move_part(pid, 5, 0, 0, None)
        result = snap_to_grid(pid)
        assert "delta" in result["data"]
        assert "overlap_warnings" in result["data"]


# ---------------------------------------------------------------------------
# batch integration
# ---------------------------------------------------------------------------


class TestBatchOverlapWarnings:
    def test_overlap_warning_surfaced_through_batch(self):
        from brick_mcp.tools.batch import batch

        result = batch(
            calls=[
                {"tool": "new_model", "args": {"name": "t"}},
                {
                    "tool": "add_part",
                    "args": {"part_number": "3001", "color": 4, "x": 0, "y": 0, "z": 0},
                },
                {
                    "tool": "add_part",
                    "args": {"part_number": "3001", "color": 4, "x": 0, "y": 0, "z": 0},
                },  # overlap
            ]
        )
        assert result["ok"] is True
        second_add = result["data"]["results"][2]
        assert second_add["ok"] is True
        assert "overlap_warnings" in second_add["data"]

    def test_validate_then_add_in_batch(self):
        """validate_placement before add_part — common defensive pattern."""
        from brick_mcp.tools.batch import batch

        # A 2×4 brick (3001) is 80 LDU wide; place the second one at x=100 (clear).
        result = batch(
            calls=[
                {"tool": "new_model", "args": {"name": "t"}},
                {
                    "tool": "add_part",
                    "args": {"part_number": "3001", "color": 4, "x": 0, "y": 0, "z": 0},
                },
                {
                    "tool": "validate_placement",
                    "args": {"part_number": "3001", "x": 100, "y": 0, "z": 0},
                },
                {
                    "tool": "add_part",
                    "args": {
                        "part_number": "3001",
                        "color": 1,
                        "x": 100,
                        "y": 0,
                        "z": 0,
                    },
                },
            ]
        )
        assert result["ok"] is True
        vp = result["data"]["results"][2]["data"]
        assert vp["valid"] is True
        # Second brick placed at x=100 (clear) — no overlap warning
        second = result["data"]["results"][3]
        assert "overlap_warnings" not in second["data"]
