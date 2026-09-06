"""Real part meshes rendered by the already installed POV-Ray; no GUI automation."""

import math
import os
import re
import subprocess
import tempfile
import json
from pathlib import Path

import numpy as np
from PIL import Image as RasterImage
from PIL import ImageChops, ImageFilter

from brick_mcp.geometry import mesh, shape, transform


def output_directory():
    path = Path(
        os.environ.get(
            "BRICK_MCP_OUTPUT_DIR", str(Path.home() / "Documents" / "Brick MCP")
        )
    )
    path.mkdir(parents=True, exist_ok=True)
    return path


def render_parts(
    parts,
    width=800,
    height=600,
    latitude=30,
    longitude=45,
    muted_ids=(),
    frame_parts=None,
):
    if not 64 <= width <= 2048 or not 64 <= height <= 2048:
        raise ValueError("Image dimensions must be 64–2048 pixels")
    if not all(math.isfinite(v) for v in (latitude, longitude)):
        raise ValueError("Camera angles must be finite")
    if os.environ.get("BRICK_MCP_RENDERER", "software") == "software":
        return _software_preview(
            parts, width, height, latitude, longitude, muted_ids, frame_parts
        )
    exe = os.environ.get("POVRAY_EXECUTABLE", "")
    root = os.environ.get("LDRAW_LIBRARY_PATH", "")
    if not Path(exe).is_file() or not Path(root).is_dir():
        raise ValueError(
            "Configure POVRAY_EXECUTABLE and LDRAW_LIBRARY_PATH for previews"
        )
    if not parts:
        raise ValueError("Cannot render an empty step/model")
    palette = {}
    for line in (
        (Path(root) / "LDConfig.ldr")
        .read_text(encoding="utf8", errors="replace")
        .splitlines()
    ):
        m = re.search(r"CODE\s+(\d+)\s+VALUE\s+#([0-9A-Fa-f]{6})", line)
        if m:
            palette[int(m[1])] = [int(m[2][i : i + 2], 16) / 255 for i in (0, 2, 4)]
    geometry = {p["part_number"]: mesh(root, p["part_number"]) for p in parts}
    points = []
    for p in frame_parts or parts:
        s = shape(p["part_number"])
        from itertools import product

        points += [
            transform(v, p["rotation"], (p["x"], p["y"], p["z"]))
            for v in product(*zip(s["geometry_min"], s["geometry_max"]))
        ]
    low = [min(p[i] for p in points) for i in range(3)]
    high = [max(p[i] for p in points) for i in range(3)]
    target = [(low[i] + high[i]) / 2 for i in range(3)]
    target[1] *= -1
    radius = math.sqrt(sum((high[i] - low[i]) ** 2 for i in range(3))) / 2
    distance = max(
        80, radius / math.sin(math.radians(19)) * 1.1 * max(1, height / width)
    )
    lat, lon = math.radians(latitude), math.radians(longitude)
    direction = (
        math.cos(lat) * math.sin(lon),
        math.sin(lat),
        -math.cos(lat) * math.cos(lon),
    )
    camera = [target[i] + distance * direction[i] for i in range(3)]
    job = Path(tempfile.mkdtemp(prefix="preview-", dir=output_directory()))
    scene, png = job / "scene.pov", job / "preview.png"
    vector = lambda v: "<" + ",".join(f"{x:.7g}" for x in v) + ">"
    muted_ids = set(muted_ids)
    with scene.open("w", encoding="ascii") as out:
        out.write(f"""#version 3.7;
global_settings {{ assumed_gamma 1.0 max_trace_level 12 }}
background {{ color rgb <0.89,0.92,0.94> }}
camera {{ location {vector(camera)} look_at {vector(target)} angle 38 right x*{width/height} }}
light_source {{ <-450,800,-500> color rgb <1.15,1.08,0.98> area_light <200,0,0>,<0,0,200>,4,4 adaptive 1 }}
light_source {{ <500,450,300> color rgb <0.48,0.55,0.7> }}
plane {{ y,{-high[1]-1} pigment {{ color rgb <0.86,0.89,0.91> }} finish {{ diffuse 0.8 ambient 0.15 }} }}
""")
        names = {name: f"P{i}" for i, name in enumerate(geometry)}
        for name, faces in geometry.items():
            out.write(f"#declare {names[name]} = mesh {{\n")
            for face, color in faces:
                # Inherited color 16 is resolved on the instance; printed colors stay in geometry.
                texture = (
                    ""
                    if color in (16, 24)
                    else f" pigment {{ color rgb {vector(palette.get(color,[.5,.5,.5]))} }}"
                )
                out.write(
                    "triangle { " + ",".join(vector(v) for v in face) + texture + " }\n"
                )
            out.write("}\n")
        out.write("union {\n")
        for p in parts:
            m = p["rotation"]
            matrix = [m[i * 3 + j] for j in range(3) for i in range(3)] + [
                p["x"],
                p["y"],
                p["z"],
            ]
            rgb = (
                [0.6, 0.6, 0.6]
                if p["id"] in muted_ids
                else palette.get(p["color"], [0.5, 0.5, 0.5])
            )
            filtered = 0.4 if 32 <= p["color"] <= 47 and p["id"] not in muted_ids else 0
            out.write(
                f"object {{ {names[p['part_number']]} matrix {vector(matrix)} pigment {{ color rgbf {vector(rgb+[filtered])} }} finish {{ diffuse .72 ambient .2 specular .25 roughness .025 }} }}\n"
            )
        out.write("scale <1,-1,1> }\n")
    cmd = [
        exe,
        "/NORESTORE",
        "/EXIT",
        "/RENDER",
        str(scene),
        f"+W{width}",
        f"+H{height}",
        "+FN",
        "-D",
        "+A0.2",
        "+WT4",
        f"+O{png}",
    ]
    kwargs = {}
    if os.name == "nt":
        startup = subprocess.STARTUPINFO()
        startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startup.wShowWindow = subprocess.SW_HIDE
        kwargs["startupinfo"] = startup
    result = subprocess.run(cmd, cwd=job, capture_output=True, timeout=90, **kwargs)
    if result.returncode != 0 or not png.is_file():
        raise RuntimeError(f"POV-Ray failed ({result.returncode}); scene: {scene}")
    if png.read_bytes()[:8] != b"\x89PNG\r\n\x1a\n":
        raise RuntimeError("Renderer did not produce a valid PNG")
    return png


def render_step_views(parts, muted_ids, frame_parts, width=800, height=600):
    if os.environ.get("BRICK_MCP_RENDERER", "software") == "software":
        return _software_preview(
            parts, width, height, 30, 45, muted_ids, frame_parts, pair=True
        )
    return [
        render_parts(parts, width, height, frame_parts=frame_parts),
        render_parts(
            parts, width, height, muted_ids=muted_ids, frame_parts=frame_parts
        ),
    ]


def _software_preview(
    parts, width, height, latitude, longitude, muted_ids, frame_parts, pair=False
):
    """Z-buffer rasterization of real LDraw triangles; no GUI or process startup."""
    if not parts:
        raise ValueError("Cannot render an empty model")
    if not 64 <= width <= 2048 or not 64 <= height <= 2048:
        raise ValueError("Image dimensions must be 64–2048 pixels")
    root = os.environ.get("LDRAW_LIBRARY_PATH", "")
    if not Path(root).is_dir():
        raise ValueError("Configure LDRAW_LIBRARY_PATH for previews")
    palette = {}
    for line in (
        (Path(root) / "LDConfig.ldr")
        .read_text(encoding="utf8", errors="replace")
        .splitlines()
    ):
        match = re.search(r"CODE\s+(\d+)\s+VALUE\s+#([0-9A-Fa-f]{6})", line)
        if match:
            palette[int(match[1])] = np.array(
                [int(match[2][i : i + 2], 16) for i in (0, 2, 4)]
            )
    lat, lon = math.radians(latitude), math.radians(longitude)
    right = np.array([math.cos(lon), 0, math.sin(lon)])
    up = np.array(
        [-math.sin(lon) * math.sin(lat), -math.cos(lat), math.cos(lon) * math.sin(lat)]
    )
    depth_axis = np.array(
        [math.sin(lon) * math.cos(lat), -math.sin(lat), -math.cos(lon) * math.cos(lat)]
    )
    frame = []
    from itertools import product

    for p in frame_parts or parts:
        s = shape(p["part_number"])
        frame.extend(
            transform(v, p["rotation"], (p["x"], p["y"], p["z"]))
            for v in product(*zip(s["geometry_min"], s["geometry_max"]))
        )
    frame = np.array(frame)
    fx, fy = frame @ right, frame @ up
    # Two-sample supersampling gives readable studs without changing model geometry.
    factor = 2 if width * height <= 1_000_000 else 1
    w, h = width * factor, height * factor
    scale = min(
        (w - 80) / max(float(np.ptp(fx)), 1), (h - 80) / max(float(np.ptp(fy)), 1)
    )
    cx, cy = (float(fx.min() + fx.max()) / 2, float(fy.min() + fy.max()) / 2)
    pixels = np.empty((h, w, 3), dtype=np.uint8)
    pixels[:] = (235, 240, 242)
    highlighted = pixels.copy() if pair else None
    visible_new = np.zeros((h, w), dtype=bool)
    zbuffer = np.full((h, w), -np.inf, dtype=np.float32)
    muted_ids = set(muted_ids)
    light = np.array([-0.4, -0.8, -0.6])
    light /= np.linalg.norm(light)
    total = 0
    for p in parts:
        faces = mesh(root, p["part_number"])
        vertices = np.array([face for face, _ in faces], dtype=float)
        vertices = vertices @ np.array(p["rotation"]).reshape(3, 3).T + [
            p["x"],
            p["y"],
            p["z"],
        ]
        screen = np.stack(
            (
                (vertices @ right - cx) * scale + w / 2,
                h / 2 - (vertices @ up - cy) * scale,
            ),
            axis=-1,
        )
        depths = vertices @ depth_axis
        normals = np.cross(
            vertices[:, 1] - vertices[:, 0], vertices[:, 2] - vertices[:, 0]
        )
        lengths = np.linalg.norm(normals, axis=1)
        shades = 0.52 + 0.48 * np.abs(normals @ light) / np.maximum(lengths, 1e-12)
        for i in np.argsort(-depths.mean(axis=1)):
            triangle = screen[i]
            if lengths[i] < 1e-9:
                continue
            x0, y0 = triangle[0]
            x1, y1 = triangle[1]
            x2, y2 = triangle[2]
            area = (y1 - y2) * (x0 - x2) + (x2 - x1) * (y0 - y2)
            if abs(area) < 1e-8:
                continue
            left = max(0, int(math.floor(triangle[:, 0].min())))
            right_edge = min(w - 1, int(math.ceil(triangle[:, 0].max())))
            top = max(0, int(math.floor(triangle[:, 1].min())))
            bottom = min(h - 1, int(math.ceil(triangle[:, 1].max())))
            if left > right_edge or top > bottom:
                continue
            block = zbuffer[top : bottom + 1, left : right_edge + 1]
            if depths[i].max() <= block.min():
                continue
            xx, yy = np.meshgrid(
                np.arange(left, right_edge + 1) + 0.5, np.arange(top, bottom + 1) + 0.5
            )
            a = ((y1 - y2) * (xx - x2) + (x2 - x1) * (yy - y2)) / area
            b = ((y2 - y0) * (xx - x2) + (x0 - x2) * (yy - y2)) / area
            c = 1 - a - b
            zz = a * depths[i, 0] + b * depths[i, 1] + c * depths[i, 2]
            block = zbuffer[top : bottom + 1, left : right_edge + 1]
            mask = (a >= -1e-7) & (b >= -1e-7) & (c >= -1e-7) & (zz > block)
            block[mask] = zz[mask]
            visible_new[top : bottom + 1, left : right_edge + 1][mask] = (
                p["id"] not in muted_ids
            )
            color = faces[i][1]
            if color in (16, 24):
                color = p["color"]
            natural = palette.get(color, np.array([155, 155, 155]))
            rgb = (
                np.array([170, 175, 180])
                if p["id"] in muted_ids and not pair
                else natural
            )
            pixels[top : bottom + 1, left : right_edge + 1][mask] = np.clip(
                rgb * shades[i], 0, 255
            ).astype(np.uint8)
            if pair:
                emphasis = (
                    np.array([170, 175, 180]) if p["id"] in muted_ids else natural
                )
                highlighted[top : bottom + 1, left : right_edge + 1][mask] = np.clip(
                    emphasis * shades[i], 0, 255
                ).astype(np.uint8)
            total += 1
    job = Path(tempfile.mkdtemp(prefix="preview-", dir=output_directory()))
    png = job / "preview.png"

    def finish(buffer, outline=False):
        image = RasterImage.fromarray(buffer).resize(
            (width, height), RasterImage.Resampling.LANCZOS
        )
        if outline and muted_ids:
            selection = RasterImage.fromarray(
                visible_new.astype(np.uint8) * 255
            ).resize((width, height), RasterImage.Resampling.NEAREST)
            border = ImageChops.subtract(
                selection.filter(ImageFilter.MaxFilter(5)), selection
            )
            image.paste((0, 155, 185), (0, 0), border)
        return image

    finish(pixels, outline=not pair).save(png)
    if pair:
        emphasis_path = job / "highlighted.png"
        finish(highlighted, outline=True).save(emphasis_path)
    (job / "render.json").write_text(
        json.dumps(
            {
                "backend": "software_zbuffer",
                "parts": len(parts),
                "triangles": total,
                "transparency": "opaque for instruction readability",
                "highlighted": bool(muted_ids),
            }
        ),
        encoding="utf8",
    )
    return [png, emphasis_path] if pair else png
