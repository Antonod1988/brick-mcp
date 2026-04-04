"""Tests for .io file reading and writing via pyzipper."""

from __future__ import annotations

import pytest

from brick_mcp.io_file import IO_PASSWORD, read_io_file, write_io_file


class TestWriteReadRoundtrip:
    def test_basic_roundtrip(self, tmp_path):
        path = str(tmp_path / "test.io")
        ldr_text = "1 4 0 -24 0 1 0 0 0 1 0 0 0 1 3001.dat\n"
        write_io_file(path, ldr_text, {})
        model_bytes, others = read_io_file(path)
        assert b"3001.dat" in model_bytes
        assert others == {}

    def test_extra_entries_preserved(self, tmp_path):
        path = str(tmp_path / "test.io")
        ldr_text = "0 test\n"
        extras = {"thumbnail.png": b"\x89PNG\r\n\x1a\n"}
        write_io_file(path, ldr_text, extras)
        _model_bytes, others = read_io_file(path)
        assert "thumbnail.png" in others
        assert others["thumbnail.png"] == b"\x89PNG\r\n\x1a\n"

    def test_ldr_content_roundtrip(self, tmp_path):
        path = str(tmp_path / "model.io")
        ldr_text = (
            "0 My Model\n"
            "1 4 0 0 0 1 0 0 0 1 0 0 0 1 3001.dat\n"
            "0 STEP\n"
            "1 1 20 -24 0 1 0 0 0 1 0 0 0 1 3004.dat\n"
        )
        write_io_file(path, ldr_text, {})
        model_bytes, _ = read_io_file(path)
        recovered = model_bytes.decode("utf-8")
        assert "3001.dat" in recovered
        assert "3004.dat" in recovered
        assert "0 STEP" in recovered

    def test_unicode_content(self, tmp_path):
        path = str(tmp_path / "unicode.io")
        ldr_text = "0 Château de LEGO\n"
        write_io_file(path, ldr_text, {})
        model_bytes, _ = read_io_file(path)
        assert "Château de LEGO" in model_bytes.decode("utf-8")

    def test_multiple_extra_entries(self, tmp_path):
        path = str(tmp_path / "multi.io")
        extras = {
            "scene.xml": b"<scene/>",
            "camera.json": b'{"fov": 60}',
            "thumb.png": b"\x89PNG",
        }
        write_io_file(path, "0 empty\n", extras)
        _, others = read_io_file(path)
        assert set(others.keys()) == {"scene.xml", "camera.json", "thumb.png"}
        assert others["scene.xml"] == b"<scene/>"
        assert others["camera.json"] == b'{"fov": 60}'


class TestReadErrors:
    def test_file_not_found_raises(self):
        with pytest.raises((FileNotFoundError, OSError)):
            read_io_file("/nonexistent/path/model.io")

    def test_missing_model_ldr_raises(self, tmp_path):
        import pyzipper

        path = str(tmp_path / "no_model.io")
        with pyzipper.AESZipFile(
            path,
            "w",
            compression=pyzipper.ZIP_DEFLATED,
            encryption=pyzipper.WZ_AES,
        ) as zf:
            zf.setpassword(IO_PASSWORD)
            zf.writestr("other.txt", b"not a model")

        with pytest.raises(KeyError, match="model.ldr"):
            read_io_file(path)


class TestPassword:
    def test_password_is_bytes(self):
        assert isinstance(IO_PASSWORD, bytes)

    def test_password_value(self):
        assert IO_PASSWORD == b"soho0909"
