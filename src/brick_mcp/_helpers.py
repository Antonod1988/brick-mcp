"""Shared response helpers for brick-mcp tools.

All tools return a dict with {"ok": bool, ...} envelope.
"""

from __future__ import annotations

import glob
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


def _find_ldview() -> str | None:
    """Return path to ldview binary, checking PATH then common Nix store paths."""
    found = shutil.which("ldview")
    if found:
        return found
    # Fallback: locate the installed Nix derivation in the store so rendering
    # works even when the devenv PATH is not active (e.g. VS Code MCP subprocess).
    nix_candidates = sorted(glob.glob("/nix/store/*-ldview-*/bin/ldview"), reverse=True)
    return nix_candidates[0] if nix_candidates else None


def _egl_env() -> dict[str, str]:
    """Build the minimal env additions needed for headless EGL on non-NixOS hosts.

    libglvnd looks for EGL vendor ICDs in /run/opengl-driver (NixOS), /etc, and
    /usr/share — none of which exist in a plain dev container.  We point it at
    the Mesa ICD directly, and force Mesa's software rasterizer so that no GPU
    or display server is needed.
    """
    extra: dict[str, str] = {}

    # Surfaceless EGL — no X11 / Wayland display required.
    extra["EGL_PLATFORM"] = "surfaceless"
    extra["DISPLAY"] = ""

    # Force Mesa software rasterizer (llvmpipe/swrast).
    extra["LIBGL_ALWAYS_SOFTWARE"] = "1"
    extra["MESA_LOADER_DRIVER_OVERRIDE"] = "swrast"

    # Point libglvnd at the Mesa EGL ICD when the system paths are absent.
    system_icd_dirs = [
        "/run/opengl-driver/share/glvnd/egl_vendor.d",
        "/etc/glvnd/egl_vendor.d",
        "/usr/share/glvnd/egl_vendor.d",
    ]
    if not any(os.path.isdir(d) for d in system_icd_dirs):
        candidates = sorted(
            glob.glob("/nix/store/*-mesa-*/share/glvnd/egl_vendor.d"), reverse=True
        )
        if candidates:
            extra["__EGL_VENDOR_LIBRARY_DIRS"] = candidates[0]

    return extra


def try_render(project: Any, width: int = 800, height: int = 600) -> Image | None:
    """Best-effort render of the current model. Returns Image or None."""
    ldview_bin = _find_ldview()
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

            env = {**os.environ, **_egl_env()}
            subprocess.run(cmd, capture_output=True, timeout=30, env=env)

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
