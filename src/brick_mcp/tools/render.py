"""Render the current model to a PNG image using LDView."""

from __future__ import annotations

import os
import subprocess
import tempfile

from fastmcp.utilities.types import Image

from brick_mcp._helpers import _egl_env, _find_ldview, err
from brick_mcp.model import get_model as _get_model
from brick_mcp.server import mcp


@mcp.tool
def render_model(
    width: int = 800,
    height: int = 600,
    latitude: float = 30,
    longitude: float = 45,
) -> Image | dict:
    """Render the current model to a PNG image.

    Returns a PNG snapshot of the model from the given camera angle.
    Requires `ldview` on PATH or in the Nix store.

    Args:
        width:     Image width in pixels.
        height:    Image height in pixels.
        latitude:  Camera latitude in degrees (default 30 = standard two-thirds view).
        longitude: Camera longitude in degrees (default 45 = standard two-thirds view).
    """
    try:
        project = _get_model()
    except RuntimeError as exc:
        return err(str(exc), "NO_MODEL")

    ldview_bin = _find_ldview()
    if ldview_bin is None:
        return err(
            "ldview binary not found on PATH or in the Nix store. Install the ldview Nix package.",
            "LDVIEW_NOT_FOUND",
        )

    with tempfile.TemporaryDirectory(prefix="brick-mcp-render-") as tmpdir:
        ldr_path = os.path.join(tmpdir, "model.ldr")
        png_path = os.path.join(tmpdir, "model.png")

        # Write current model as standard LDraw text (LDView understands type-1).
        ldr_text = project.to_ldraw_text()
        with open(ldr_path, "w") as fh:
            fh.write(ldr_text)

        cmd = [
            ldview_bin,
            ldr_path,
            f"-SaveSnapshot={png_path}",
            f"-SaveWidth={width}",
            f"-SaveHeight={height}",
            f"-DefaultLatLong={latitude},{longitude}",
            "-SaveActualSize=0",
            "-SaveZoomToFit=1",
            "-ShowHighlightLines=1",
            "-EdgeThickness=1.5",
            "-LineSmoothing=1",
            "-ShowErrors=0",
            "-SaveAlpha=0",
        ]

        env = {**os.environ, **_egl_env()}
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                timeout=120,
                env=env,
            )
        except FileNotFoundError:
            return err("ldview binary not found.", "LDVIEW_NOT_FOUND")
        except subprocess.TimeoutExpired:
            return err("LDView render timed out after 120 s.", "RENDER_TIMEOUT")

        if not os.path.isfile(png_path):
            stderr = (
                result.stderr.decode(errors="replace").strip()
                if result.stderr
                else "(no stderr)"
            )
            return err(
                f"LDView did not produce an image (exit {result.returncode}): {stderr}",
                "RENDER_FAILED",
            )

        with open(png_path, "rb") as fh:
            png_bytes = fh.read()

    return Image(data=png_bytes, format="png")
