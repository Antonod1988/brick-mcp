"""Shared response helpers for brick-mcp tools.

All tools return a dict with {"ok": bool, ...} envelope.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from typing import Any

from fastmcp.utilities.types import Image


def ok(data: Any = None, message: str = "") -> dict:
    """Standard success response envelope."""
    result: dict = {"ok": True}
    if message:
        result["message"] = message
    if data is not None:
        result["data"] = data
    return result


def err(message: str, code: str = "ERROR") -> dict:
    """Standard error response envelope."""
    return {"ok": False, "error": {"code": code, "message": message}}


def try_render(project: Any, width: int = 800, height: int = 600) -> Image | None:
    """Best-effort render of the current model. Returns Image or None."""
    ldview_bin = shutil.which("ldview")
    if ldview_bin is None:
        return None

    try:
        with tempfile.TemporaryDirectory(prefix="brick-mcp-render-") as tmpdir:
            ldr_path = os.path.join(tmpdir, "model.ldr")
            png_path = os.path.join(tmpdir, "model.png")

            ldr_text = project.to_ldraw_text()
            with open(ldr_path, "w") as fh:
                fh.write(ldr_text)

            cmd = [
                ldview_bin,
                ldr_path,
                f"-SaveSnapshot={png_path}",
                f"-SaveWidth={width}",
                f"-SaveHeight={height}",
                "-DefaultLatLong=30,45",
                "-SaveActualSize=0",
                "-SaveZoomToFit=1",
                "-ShowHighlightLines=1",
                "-EdgeThickness=1.5",
                "-LineSmoothing=1",
                "-ShowErrors=0",
                "-SaveAlpha=0",
            ]

            subprocess.run(cmd, capture_output=True, timeout=30)

            if not os.path.isfile(png_path):
                return None

            with open(png_path, "rb") as fh:
                return Image(data=fh.read(), format="png")
    except Exception:
        return None


def ok_with_render(project: Any, data: Any = None, message: str = "") -> list | dict:
    """Return ok() envelope, appending a rendered PNG if ldview is available."""
    result = ok(data, message)
    img = try_render(project)
    if img is not None:
        return [result, img]
    return result
