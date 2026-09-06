from unittest.mock import patch
import pytest
from brick_mcp.model import get_model
from brick_mcp.tools.file_ops import save_model, open_model
from brick_mcp.tools.workflow import apply_step, export_instructions
from brick_mcp.tools.studio_check import studio_result


def piece(y=0):
    return {"part_number": "3001", "color": 4, "x": 0, "y": y, "z": 0}


@pytest.mark.parametrize("mode", ["issues", "timeout"])
def test_native_failure_rolls_back_even_with_allow_unverified(mode):
    assert apply_step("Base", [piece()], preview=False)["ok"]
    before = get_model().snapshot()
    kw = (
        {"side_effect": TimeoutError("worker timeout")}
        if mode == "timeout"
        else {"return_value": {"status": "issues_found", "warnings": 1}}
    )
    with patch("brick_mcp.tools.studio_check.run_native_check", **kw):
        result = apply_step("Top", [piece(-24)], allow_unverified=True, preview=False)
    assert not result["ok"] and result["rolled_back"]
    assert get_model().snapshot() == before


@pytest.mark.parametrize("suffix", ["io", "mpd"])
def test_per_step_checks_survive_roundtrip_and_expire_on_edit(tmp_path, suffix):
    assert apply_step("Base", [piece()], preview=False)["ok"]
    assert apply_step("Top", [piece(-24)], preview=False)["ok"]
    path = tmp_path / ("model." + suffix)
    assert save_model(str(path))["ok"] and open_model(str(path))["ok"]
    p = get_model()
    assert studio_result(p, through_step=0)["status"] == "clear"
    assert studio_result(p, through_step=1)["status"] == "clear"
    part = p.list_parts(None)[-1]
    p.move_part(part["id"], 100, -24, 0, None)
    assert studio_result(p, through_step=0)["status"] == "clear"
    assert studio_result(p, through_step=1)["status"] == "stale"
    assert not export_instructions(str(tmp_path / "release"), previews=False)["ok"]


def test_step_calls_native_transport_each_time():
    with patch(
        "brick_mcp.tools.studio_check.run_native_check",
        return_value={
            "source": "native_studio_runtime",
            "status": "clear",
            "warnings": 0,
            "cautions": 0,
            "stability_issues": 0,
            "detached_sections": 0,
        },
    ) as native:
        assert apply_step("Base", [piece()], preview=False)["ok"]
        assert apply_step("Top", [piece(-24)], preview=False)["ok"]
        assert [c.args[2] for c in native.call_args_list] == [0, 1]


def test_caution_opt_in_never_accepts_red_or_detached_parts():
    from brick_mcp.tools.studio_check import accepted_native

    report = dict(
        source="native_studio_runtime",
        status="issues_found",
        warnings=0,
        cautions=2,
        detached_sections=0,
        stability_issues=0,
        allow_cautions=True,
    )
    assert accepted_native(report)
    for field in ("warnings", "detached_sections", "stability_issues"):
        assert not accepted_native({**report, field: 1})
    assert not accepted_native({**report, "allow_cautions": False})
    assert not accepted_native({**report, "status": "stale"})


def test_dat_file_wrapper_is_not_the_catalogue_description(tmp_path):
    from brick_mcp.catalog import _load_from_directory, _load_from_zip
    import zipfile

    (tmp_path / "parts").mkdir()
    data = "0 FILE clip.dat\n0 Bar 1L with Clip\n0 Name: clip.dat\n0 !CATEGORY Other\n"
    (tmp_path / "parts/clip.dat").write_text(data)
    archive = tmp_path / "parts.zip"
    with zipfile.ZipFile(archive, "w") as z:
        z.writestr("ldraw/parts/clip.dat", data)
    assert _load_from_directory(str(tmp_path))["clip.dat"]["name"] == "Bar 1L with Clip"
    assert _load_from_zip(str(archive))["clip.dat"]["name"] == "Bar 1L with Clip"


def test_native_parent_failure_rolls_back_child_edit():
    from brick_mcp.tools.workflow import create_submodel

    assert apply_step("Base", [piece()], preview=False)["ok"]
    assert create_submodel("Module")["ok"]
    p = {**piece(), "part_number": "3003"}
    assert apply_step("Module base", [p], submodel="Module.ldr", preview=False)["ok"]
    assert apply_step(
        "Install",
        [{**p, "part_number": "Module.ldr", "x": -20, "y": -24, "color": 16}],
        preview=False,
    )["ok"]
    before = get_model().snapshot()

    def native(project, submodel, index):
        return dict(
            source="native_studio_runtime",
            status="issues_found" if submodel == project.root_submodel else "clear",
            warnings=int(submodel == project.root_submodel),
            cautions=0,
            stability_issues=0,
            detached_sections=0,
        )

    with patch("brick_mcp.tools.studio_check.run_native_check", side_effect=native):
        result = apply_step(
            "Module taller", [{**p, "y": -24}], submodel="Module.ldr", preview=False
        )
    assert not result["ok"] and result["rolled_back"]
    assert get_model().snapshot() == before


def test_atomic_step_replacement_preserves_later_parts():
    assert apply_step("Base", [piece()], preview=False)["ok"]
    assert apply_step("Top", [piece(-24)], preview=False)["ok"]
    top_id = get_model().list_parts(None)[-1]["id"]
    assert apply_step(
        "Replaced base",
        [{**piece(), "color": 14}],
        insert_at=0,
        replace_existing=True,
        preview=False,
    )["ok"]
    assert len(get_model().flatten()) == 2
    assert get_model().list_parts(None)[-1]["id"] == top_id
    assert studio_result(get_model(), through_step=1)["status"] == "clear"


def test_canvas_policy_cannot_hide_rigid_faults_or_other_unknown_parts():
    from brick_mcp.tools.studio_check import accepted_native

    structural = dict(
        source="native_studio_runtime",
        status="clear",
        warnings=0,
        cautions=0,
        stability_issues=0,
        detached_sections=0,
    )
    report = dict(
        source="native_studio_runtime",
        status="unverified_canvas",
        allow_unverified_canvas=True,
        unmodelled_parts=[{"part_number": "sail.dat"}],
        structural_check=structural,
    )
    with patch(
        "brick_mcp.tools.studio_check.is_canvas",
        side_effect=lambda pn: pn == "sail.dat",
    ):
        assert accepted_native(report)
        assert not accepted_native({**report, "allow_unverified_canvas": False})
        assert not accepted_native(
            {**report, "unmodelled_parts": [{"part_number": "unknown-brick.dat"}]}
        )
        assert not accepted_native(
            {
                **report,
                "structural_check": {
                    **structural,
                    "status": "issues_found",
                    "warnings": 1,
                },
            }
        )
    assert not accepted_native({**structural, "status": "unverified_physics"})


def test_used_submodel_and_root_are_protected_from_removal():
    from brick_mcp.tools.workflow import create_submodel, remove_unused_submodel

    root = get_model().root_submodel
    assert not remove_unused_submodel(root)["ok"]
    assert create_submodel("Unused")["ok"]
    assert remove_unused_submodel("Unused.ldr")["ok"]
    assert create_submodel("Used")["ok"]
    get_model().add_part(None, "Used.ldr", 16, 0, 0, 0)
    assert not remove_unused_submodel("Used.ldr")["ok"]
