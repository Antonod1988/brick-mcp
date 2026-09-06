"""The Windows setup must search the installed library, not the fallback table."""

import json

import pytest

from brick_mcp import catalog


def test_installed_library_catalog(tmp_path, monkeypatch):
    monkeypatch.delenv("LDRAW_CATALOG_PATH", raising=False)
    parts = tmp_path / "parts"
    parts.mkdir()
    (parts / "987654.dat").write_text(
        "\ufeff0 Test Window  2 x 4\n0 !CATEGORY Window\n", encoding="utf-8"
    )
    (parts / "invalid.dat").write_text("not an LDraw header\n", encoding="utf-8")
    (parts / "s").mkdir()
    (parts / "s" / "hidden.dat").write_text("0 Subpart\n", encoding="utf-8")
    monkeypatch.setenv("LDRAW_LIBRARY_PATH", str(tmp_path))
    monkeypatch.setattr(catalog, "_catalog", None)
    assert catalog.search_catalog("window 2x4") == [
        {
            "part_number": "987654.dat",
            "name": "Test Window  2 x 4",
            "category": "Window",
        }
    ]
    assert len(catalog.get_catalog()) == 1
    assert catalog.get_part_info("987654") is not None
    snapshot = tmp_path / "catalog.json"
    snapshot.write_text(json.dumps(catalog.get_catalog()), encoding="utf-8")
    monkeypatch.setenv("LDRAW_CATALOG_PATH", str(snapshot))
    monkeypatch.setattr(catalog, "_catalog", None)
    monkeypatch.setenv("LDRAW_LIBRARY_PATH", str(tmp_path / "unavailable"))
    assert catalog.get_part_info("987654")["category"] == "Window"
    monkeypatch.delenv("LDRAW_CATALOG_PATH")
    monkeypatch.setenv("LDRAW_LIBRARY_PATH", str(tmp_path / "missing"))
    monkeypatch.setattr(catalog, "_catalog", None)
    with pytest.raises(FileNotFoundError, match="LDraw parts directory"):
        catalog.get_catalog()
