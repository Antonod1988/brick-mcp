import pytest

from brick_mcp import catalog
from brick_mcp.geometry import shape, world_bounds
from brick_mcp.tools.file_ops import new_model
from brick_mcp.tools.workflow import apply_step, edit_step
from brick_mcp.model import get_model


def test_alias_bounds_and_asymmetric_origin_are_geometry_derived(tmp_path, monkeypatch):
    parts = tmp_path / "parts"
    parts.mkdir()
    # Deliberately asymmetric X origin, no lookup-table dimensions involved.
    (parts / "9001.dat").write_text(
        "0 Helmet\n4 16 30 0 -10 70 0 -10 70 24 10 30 24 10\n"
    )
    monkeypatch.setenv("LDRAW_LIBRARY_PATH", str(tmp_path))
    monkeypatch.setattr(
        catalog,
        "_catalog",
        {
            "old.dat": {
                "part_number": "old.dat",
                "name": "~Moved to 9001",
                "category": "Other",
            },
            "9001.dat": {
                "part_number": "9001.dat",
                "name": "Helmet",
                "category": "Other",
            },
        },
    )
    assert catalog.resolve_part_number("old") == "9001.dat"
    s = shape("old")
    assert s["body_min"] == (30, 0, -10) and s["body_max"] == (70, 24, 10)
    assert s["connection_kind"] == "unknown"
    box = world_bounds(
        dict(part_number="old", x=0, y=0, z=0, rotation=[0, 0, -1, 0, 1, 0, 1, 0, 0])
    )
    assert box == (-10, 10, 0, 24, 30, 70)
    catalog._catalog["9001.dat"]["name"] = "~Moved to old"
    with pytest.raises(ValueError, match="Cyclic"):
        catalog.resolve_part_number("old")


def test_geometry_missing_reference_and_traversal_are_not_silently_ignored(tmp_path):
    from brick_mcp.geometry import mesh

    parts = tmp_path / "parts"
    parts.mkdir()
    (parts / "a.dat").write_text("1 16 0 0 0 1 0 0 0 1 0 0 0 1 missing.dat\n")
    with pytest.raises(FileNotFoundError):
        mesh(str(tmp_path), "a.dat")
    with pytest.raises(ValueError):
        mesh(str(tmp_path), "../secret.dat")


def test_inserted_empty_step_can_be_filled_without_an_extra_empty_step():
    new_model("steps")
    assert apply_step("Base", [dict(part_number="3001", color=4)], preview=False)["ok"]
    assert edit_step("insert", 1, name="Pending")["ok"]
    assert apply_step(
        "Upper", [dict(part_number="3001", color=4, y=-24)], insert_at=1, preview=False
    )["ok"]
    assert [s["parts_in_step"] for s in get_model().get_steps(None)] == [1, 1]


def test_half_stud_offset_is_not_a_connection():
    new_model("misaligned")
    apply_step("Base", [dict(part_number="3001", color=4)], preview=False)
    result = apply_step(
        "Wrong alignment",
        [dict(part_number="3003", color=4, x=10, y=-24)],
        preview=False,
    )
    assert not result["ok"] and result["validation"][0]["floating"]


def test_studio_unofficial_primitive_fallback(tmp_path):
    from brick_mcp.geometry import mesh

    main = tmp_path / "parts"
    main.mkdir()
    extra = tmp_path / "UnOfficial" / "p"
    extra.mkdir(parents=True)
    (main / "test.dat").write_text("1 16 0 0 0 1 0 0 0 1 0 0 0 1 axle.dat\n")
    (extra / "axle.dat").write_text("3 16 0 0 0 1 0 0 0 1 0\n")
    assert len(mesh(str(tmp_path), "test.dat")) == 1


def test_unsupported_insertion_is_unverified_not_a_false_confirmed_block(monkeypatch):
    import brick_mcp.validation as validation

    monkeypatch.setattr(
        validation, "world_bounds", lambda p: (-10, 10, p["y"], p["y"] + 8, -10, 10)
    )
    monkeypatch.setattr(validation, "connectors", lambda p: None)
    monkeypatch.setattr(
        validation, "shape", lambda pn: {"collision_kind": "conservative_box"}
    )
    parts = [
        dict(id="old", part_number="axle", y=-20),
        dict(id="new", part_number="axle", y=0),
    ]
    report = validation.validate_parts(parts, previous=parts[:1])
    assert (
        report["status"] == "unverified"
        and report["unverified_access"]
        and not report["blocked_access"]
    )
