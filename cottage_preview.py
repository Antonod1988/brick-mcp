"""Export the saved LDraw model's real triangles to the bundled POV-Ray renderer."""

import re
import sys
from functools import cache
from pathlib import Path

import numpy as np

LIB = Path(r"D:\Progs\Studio 2.0\ldraw")


@cache
def triangles(name):
    name = name.replace("\\", "/")
    source = next((p for p in (LIB / "parts" / name, LIB / "p" / name, LIB / name) if p.is_file()), None)
    if source is None:
        raise FileNotFoundError(name)
    faces = []
    for line in source.read_text(encoding="utf8", errors="replace").splitlines():
        fields = line.split()
        if not fields or fields[0] not in ("1", "3", "4"):
            continue
        if fields[0] == "1":
            values = np.array(list(map(float, fields[2:14])))
            child = triangles(" ".join(fields[14:]))
            faces.extend(child @ values[3:].reshape(3, 3).T + values[:3])
        else:
            vertices = np.array(list(map(float, fields[2:]))).reshape(-1, 3)
            faces.append(vertices[:3])
            if fields[0] == "4":
                faces.append(vertices[[0, 2, 3]])
    return np.array(faces).reshape(-1, 3, 3)


def main():
    source = Path(sys.argv[1]).resolve()
    parts = [line.split() for line in source.read_text(encoding="utf8").splitlines() if line.startswith("1 ")]
    palette = {}
    for line in (LIB / "LDConfig.ldr").read_text(encoding="utf8", errors="replace").splitlines():
        found = re.search(r"CODE\s+(\d+)\s+VALUE\s+#([0-9A-Fa-f]{6})", line)
        if found:
            palette[int(found[1])] = [int(found[2][i:i+2], 16) / 255 for i in (0, 2, 4)]
    geometry = {p[14]: triangles(p[14]) for p in parts}
    bounds = np.concatenate([geometry[p[14]].reshape(-1, 3) @ np.array(list(map(float, p[5:14]))).reshape(3, 3).T
                             + np.array(list(map(float, p[2:5]))) for p in parts])
    assert np.isfinite(bounds).all() and len(parts) == 220
    print("Actual geometry bounds:", bounds.min(axis=0), bounds.max(axis=0), flush=True)
    scene = source.with_name("preview.pov")
    with scene.open("w", encoding="ascii") as out:
        out.write('''#version 3.7;
global_settings { assumed_gamma 1.0 max_trace_level 12 }
background { color rgb <0.89,0.92,0.94> }
camera { location <640,520,-860> look_at <0,85,0> angle 38 right x*1.4 }
light_source { <-450,800,-500> color rgb <1.15,1.08,0.98> area_light <200,0,0>,<0,0,200>,4,4 adaptive 1 }
light_source { <500,450,300> color rgb <0.48,0.55,0.7> }
plane { y,-5 pigment { color rgb <0.86,0.89,0.91> } finish { diffuse 0.8 ambient 0.15 } }
''')
        names = {name: f"Part{i}" for i, name in enumerate(geometry)}
        for name, faces in geometry.items():
            out.write(f"#declare {names[name]} = mesh {{\n")
            for face in faces:
                out.write("triangle { " + ",".join("<" + ",".join(f"{v:.5g}" for v in vertex) + ">" for vertex in face) + " }\n")
            out.write("}\n")
        out.write("union {\n")
        for p in parts:
            matrix = np.array(list(map(float, p[5:14]))).reshape(3, 3).T.flatten().tolist() + list(map(float, p[2:5]))
            color = palette[int(p[1])]
            pigment = "rgbf <" + ",".join(map(str, color + [0.45 if int(p[1]) == 47 else 0])) + ">"
            out.write(f"object {{ {names[p[14]]} matrix <{','.join(map(str,matrix))}> pigment {{ color {pigment} }} finish {{ diffuse 0.72 ambient 0.2 specular 0.25 roughness 0.025 }} }}\n")
        out.write("scale <1,-1,1> }\n")
    print(scene, flush=True)


if __name__ == "__main__":
    main()
