import json
import pytest
import math
import zipfile
from unittest.mock import patch

from brick_mcp.model import StudioProject, get_model, set_model
from brick_mcp.tools.batch import batch
from brick_mcp.tools.file_ops import new_model, open_model, save_model
from brick_mcp.tools.workflow import (
    apply_step,
    create_submodel,
    edit_step,
    undo_last_edit,
    validate_build,
)


def placement(pn="3001", x=0, y=0, z=0, color=4):
    return dict(part_number=pn, color=color, x=x, y=y, z=z)


def test_allow_unverified_does_not_accept_known_disconnected_submodel():
    new_model("checked")
    assert create_submodel("Loose")["ok"]
    project = get_model()
    project.add_part("Loose.ldr", "3001", 4, 0, 0, 0)
    project.add_part("Loose.ldr", "3001", 4, 200, 0, 0)
    before = project.to_ldraw_text()
    result = apply_step(
        "Install",
        [placement("Loose.ldr", color=16)],
        allow_unverified=True,
        preview=False,
    )
    assert not result["ok"] and project.to_ldraw_text() == before


def test_step_rejection_restores_state_ids_and_undo_history():
    new_model("checked")
    assert apply_step("Bottom", [placement()], preview=False)["ok"]
    p = get_model()
    before = p.to_ldraw_text(), p.list_parts(None), len(p._undo)
    assert not apply_step("Collision", [placement(y=-12)], preview=False)["ok"]
    assert (p.to_ldraw_text(), p.list_parts(None), len(p._undo)) == before
    assert not apply_step("Floating", [placement(x=200, y=-24)], preview=False)["ok"]
    assert apply_step("Top", [placement(y=-24)], preview=False)["ok"]
    assert validate_build()["data"]["status"] == "passed"
    assert undo_last_edit()["ok"] and len(p.flatten()) == 1


def test_preview_and_save_failures_rollback(tmp_path):
    new_model("checked")
    assert apply_step("Base", [placement()], preview=False)["ok"]
    before = get_model().to_ldraw_text()
    with patch(
        "brick_mcp.tools.workflow._images", side_effect=RuntimeError("render failure")
    ):
        assert not apply_step("Top", [placement(y=-24)])["ok"]
    assert get_model().to_ldraw_text() == before
    with patch(
        "brick_mcp.tools.file_ops.os.replace", side_effect=OSError("disk failure")
    ):
        assert not apply_step(
            "Top", [placement(y=-24)], preview=False, save_path=str(tmp_path / "a.io")
        )["ok"]
    assert get_model().to_ldraw_text() == before


def test_save_never_truncates_existing_file(tmp_path):
    new_model("checked")
    target = tmp_path / "existing.io"
    target.write_bytes(b"existing user model")
    with patch(
        "brick_mcp.io_file.write_io_file", side_effect=OSError("failed serialization")
    ):
        assert not save_model(str(target))["ok"]
    assert target.read_bytes() == b"existing user model"
    assert list(tmp_path.iterdir()) == [target]


def test_atomic_batch_stops_and_restores_including_new_model():
    new_model("original")
    apply_step("Base", [placement()], preview=False)
    before = get_model().to_ldraw_text()
    result = batch(
        [
            {"tool": "new_model", "args": {"name": "replacement"}},
            {"tool": "bad_tool"},
            {"tool": "new_model"},
        ]
    )
    assert result["data"]["rolled_back"] and result["data"]["executed"] == 2
    assert get_model().to_ldraw_text() == before
    assert not batch([{"tool": "save_model", "args": {"path": "do-not-write.io"}}])[
        "ok"
    ]


def test_named_step_editing_and_roundtrip(tmp_path):
    new_model("instructions")
    apply_step("Base", [placement()], preview=False)
    apply_step(
        "Pair",
        [placement("3003", x=-20, y=-24), placement("3003", x=20, y=-24)],
        preview=False,
    )
    p = get_model()
    ids = p.get_steps(None)[1]["part_ids"]
    assert edit_step("split", 1, name="Right half", part_ids=[ids[1]])["ok"]
    assert edit_step("rename", 0, name="Основание")["ok"]
    assert edit_step("reorder", 1, target_index=2)["ok"]
    assert edit_step("merge_next", 1)["ok"]
    assert len(p.get_steps(None)) == 2
    p.add_step(None)
    assert len(p.get_steps(None)) == 2  # no trailing phantom step
    path = tmp_path / "stages.io"
    assert save_model(str(path))["ok"] and open_model(str(path))["ok"]
    assert get_model().get_steps(None)[0]["name"] == "Основание"
    assert len(get_model().get_steps(None)) == 2


def test_submodel_bom_instances_and_attachment(tmp_path):
    new_model("main")
    apply_step("Base", [placement()], preview=False)
    assert create_submodel("Assembly")["ok"]
    assert apply_step(
        "Lower", [placement("3003")], submodel="Assembly.ldr", preview=False
    )["ok"]
    assert apply_step(
        "Upper", [placement("3003", y=-24)], submodel="Assembly.ldr", preview=False
    )["ok"]
    assert apply_step(
        "Install", [placement("Assembly.ldr", x=-20, y=-24, color=16)], preview=False
    )["ok"]
    assert len(get_model().flatten()) == 3
    assert get_model().get_bom(None) == {"3001.dat": {"4": 1}, "3003.dat": {"4": 2}}
    path = tmp_path / "assembly.mpd"
    save_model(str(path))
    open_model(str(path))
    assert len(get_model().flatten()) == 3 and "Assembly.ldr" in get_model().submodels


def test_insertion_access_and_tile_are_not_connections():
    new_model("tiles")
    apply_step("Base", [placement()], preview=False)
    assert apply_step("Tile", [placement("87079", y=-8)], preview=False)["ok"]
    assert not apply_step("On smooth tile", [placement(y=-32)], preview=False)["ok"]
    from brick_mcp.validation import validate_parts

    parts = [
        dict(
            id="old",
            part_number="3001.dat",
            color=4,
            x=0,
            y=-48,
            z=0,
            rotation=[1, 0, 0, 0, 1, 0, 0, 0, 1],
        ),
        dict(
            id="new",
            part_number="3001.dat",
            color=4,
            x=0,
            y=0,
            z=0,
            rotation=[1, 0, 0, 0, 1, 0, 0, 0, 1],
        ),
    ]
    assert validate_parts(parts, previous=parts[:1])["blocked_access"]


def test_unknown_numbers_nonfinite_transforms_and_cycles_are_rejected():
    new_model("validated")
    for p in [placement("nonexistent"), placement(x=math.nan), placement("../3001")]:
        assert not apply_step("Bad", [p], preview=False)["ok"]
        assert get_model().flatten() == []
    create_submodel("loop")
    with pytest.raises(ValueError, match="cycle"):
        get_model().add_part("loop.ldr", "loop.ldr", 16, 0, 0, 0)
    assert not apply_step("Cycle", [placement("loop.ldr")], preview=False)["ok"]


def test_colored_instances_export_explicit_variant_colors_for_studio(tmp_path):
    new_model("garden")
    apply_step("Base", [placement()], preview=False)
    create_submodel("Flower")
    apply_step(
        "Stem", [placement("3005", color=2)], submodel="Flower.ldr", preview=False
    )
    apply_step(
        "Head",
        [placement("3024", y=-8, color=16)],
        submodel="Flower.ldr",
        preview=False,
    )
    prototype = tmp_path / "prototype.io"
    save_model(str(prototype))
    open_model(str(prototype))
    assert apply_step(
        "Plant", [placement("Flower.ldr", x=-10, y=-24, z=-10, color=14)], preview=False
    )["ok"]
    project = get_model()
    reference = project.list_parts(None)[-1]
    assert reference["color"] == 16 and reference["part_number"] != "Flower.ldr"
    from brick_mcp.ldraw import MetaCommand

    assert not any(
        isinstance(c, MetaCommand) and c.text == "Flower"
        for c in project._submodel(reference["part_number"]).commands
    )
    assert {p["color"] for p in project.flatten(reference["part_number"])} == {2, 14}
    path = tmp_path / "variants.io"
    save_model(str(path))
    open_model(str(path))
    assert get_model().get_bom(None)["3005.dat"] == {"2": 1}
    assert get_model().get_bom(None)["3024.dat"] == {"14": 1}
