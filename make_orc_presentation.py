"""Export the checked Studio model and its actual step order for presentation renders."""

import gzip
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).parent
OUT = ROOT / "output/orc-kraken-ship/presentation"
sys.path.insert(0, str(ROOT / "src"))
os.environ["LDRAW_LIBRARY_PATH"] = r"D:\Progs\Studio 2.0\ldraw"
os.environ["LDRAW_CATALOG_PATH"] = str(ROOT / ".cache/studio-catalog.json")
from brick_mcp.io_file import read_io_file
from brick_mcp.ldraw import parse_ldraw, PartLine
from brick_mcp.model import StudioProject
from brick_mcp.instructions import groups
from brick_mcp.geometry import mesh, multiply, transform


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    source = ROOT / "output/orc-kraken-ship/Orc Kraken - Red Sails.io"
    data, entries = read_io_file(str(source))
    project = StudioProject.from_blocks(None, parse_ldraw(data.decode("utf8")), entries)
    leaves = project.flatten()
    by_id = {p["id"]: p for p in leaves}
    stages = []
    reveals = {}

    def visit(name, path=""):
        for g in groups(project._submodel(name)):
            direct = []
            has_parts = False
            for p in g["commands"]:
                if not isinstance(p, PartLine):
                    continue
                has_parts = True
                if p.part_file in project.submodels:
                    visit(p.part_file, path + p._id + "/")
                else:
                    direct.append(path + p._id)
            if has_parts:
                stages.append({"assembly": name, "name": g["name"], "parts": direct})
                for id in direct:
                    reveals[id] = len(stages)

    visit(project.root_submodel)
    assert set(reveals) == set(by_id) and len(stages) == 147
    for p in leaves:
        p["reveal"] = reveals[p["id"]]
    palette = {}
    for line in (
        (Path(os.environ["LDRAW_LIBRARY_PATH"]) / "LDConfig.ldr")
        .read_text(encoding="utf8", errors="replace")
        .splitlines()
    ):
        m = re.search(
            r"!COLOUR\s+(.*?)\s+CODE\s+(\d+)\s+VALUE\s+#([\dA-Fa-f]{6})", line
        )
        if not m:
            continue
        alpha = re.search(r"ALPHA\s+(\d+)", line)
        palette[m[2]] = {
            "name": m[1],
            "rgb": [int(m[3][i : i + 2], 16) / 255 for i in (0, 2, 4)],
            "alpha": int(alpha[1]) / 255 if alpha else 1,
        }
    geometry = {}
    total = 0
    for pn in sorted({p["part_number"] for p in leaves}):
        verts = []
        faces = []
        colors = []
        index = {}
        for triangle, color in mesh(os.environ["LDRAW_LIBRARY_PATH"], pn):
            face = []
            for v in triangle:
                key = tuple(round(x, 6) for x in v)
                if key not in index:
                    index[key] = len(verts)
                    verts.append(key)
                face.append(index[key])
            if len(set(face)) == 3:
                faces.append(face)
                colors.append(color)
        geometry[pn] = {"vertices": verts, "faces": faces, "colors": colors}
        total += len(faces)
    payload = {
        "source": str(source),
        "parts": leaves,
        "stages": stages,
        "palette": palette,
        "geometry": geometry,
    }
    with gzip.open(OUT / "model.json.gz", "wt", encoding="utf8") as f:
        json.dump(payload, f, separators=(",", ":"))
    (OUT / "manifest.json").write_text(
        json.dumps(
            {
                "source": str(source),
                "elements": len(leaves),
                "steps": len(stages),
                "unique_parts": len(geometry),
                "unique_mesh_triangles": total,
            },
            indent=2,
        ),
        encoding="utf8",
    )
    print(
        "EXPORTED",
        len(leaves),
        "parts",
        len(stages),
        "stages",
        len(geometry),
        "meshes",
        total,
        "triangles",
        flush=True,
    )


if __name__ == "__main__":
    main()
