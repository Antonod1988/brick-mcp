"""Render the exact LDraw geometry in an isolated Blender process."""

import bpy, bmesh, gzip, json, math, sys, time
from pathlib import Path
from mathutils import Matrix, Vector

OUT = Path(r"D:\pythonProject4\brick-mcp\output\orc-kraken-ship\presentation")
mode = sys.argv[sys.argv.index("--") + 1] if "--" in sys.argv else "proof"
with gzip.open(OUT / "model.json.gz", "rt", encoding="utf8") as f:
    data = json.load(f)
bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete(use_global=False)
scene = bpy.context.scene
scene.render.engine = "CYCLES"
prefs = bpy.context.preferences.addons["cycles"].preferences
prefs.compute_device_type = "OPTIX"
prefs.get_devices()
for d in prefs.devices:
    d.use = d.type == "OPTIX"
scene.cycles.device = "GPU"
scene.cycles.samples = 48
scene.cycles.use_denoising = True
scene.cycles.max_bounces = 6
scene.cycles.transparent_max_bounces = 6
scene.render.use_persistent_data = False
scene.render.image_settings.file_format = "PNG"
scene.render.image_settings.color_mode = "RGB"
scene.render.film_transparent = False
scene.view_settings.view_transform = "AgX"
scene.view_settings.look = "AgX - Medium High Contrast"
scene.render.resolution_percentage = 100
scene.world.use_nodes = True
scene.world.node_tree.nodes["Background"].inputs["Color"].default_value = (
    0.06,
    0.085,
    0.12,
    1,
)
scene.world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.35
S = 0.0004
C = Matrix(((1, 0, 0), (0, 0, 1), (0, -1, 0)))


def srgb(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


materials = {}


def material(code, kind="plastic"):
    key = (code, kind)
    if key in materials:
        return materials[key]
    info = data["palette"].get(str(code), {})
    rgb = info.get(
        "rgb",
        (
            [(code >> 16 & 255) / 255, (code >> 8 & 255) / 255, (code & 255) / 255]
            if code >= 0x2000000
            else [0.4, 0.4, 0.4]
        ),
    )
    mat = bpy.data.materials.new(f"{kind}_{code}")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = tuple(srgb(c) for c in rgb) + (1,)
    bsdf.inputs["Roughness"].default_value = 0.74 if kind == "cloth" else 0.25
    bsdf.inputs["IOR"].default_value = 1.46
    bsdf.inputs["Coat Weight"].default_value = 0 if kind == "cloth" else 0.25
    bsdf.inputs["Coat Roughness"].default_value = 0.2
    if kind == "cloth":
        bsdf.inputs["Sheen Weight"].default_value = 0.05
        bsdf.inputs["Specular IOR Level"].default_value = 0.15
    if info.get("alpha", 1) < 1:
        bsdf.inputs["Transmission Weight"].default_value = 0.55
        bsdf.inputs["Roughness"].default_value = 0.12
    materials[key] = mat
    return mat


meshes = {}
slots = {}
for pn, g in data["geometry"].items():
    kind = "cloth" if pn in ("64991c01.dat", "96714c01.dat") else "plastic"
    me = bpy.data.meshes.new(pn)
    me.from_pydata(
        [(v[0] * S, v[2] * S, -v[1] * S) for v in g["vertices"]], [], g["faces"]
    )
    me.update()
    colors = [16] + sorted(set(g["colors"]) - {16, 24})
    slot = {c: i for i, c in enumerate(colors)}
    for c in colors:
        me.materials.append(material(71 if c == 16 else c, kind))
    for poly, c in zip(me.polygons, g["colors"]):
        poly.material_index = slot.get(c, 0)
        poly.use_smooth = True
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    for e in bm.edges:
        e.smooth = len(e.link_faces) == 2 and e.calc_face_angle() < math.radians(32)
    bm.to_mesh(me)
    bm.free()
    me.update()
    meshes[pn] = me
objects = []
by_id = {}
for i, p in enumerate(data["parts"]):
    obj = bpy.data.objects.new(f'{i:04d}_{p["part_number"]}', meshes[p["part_number"]])
    scene.collection.objects.link(obj)
    r = p["rotation"]
    r = Matrix((r[:3], r[3:6], r[6:9]))
    obj.matrix_world = (C @ r @ C.inverted()).to_4x4()
    obj.location = (p["x"] * S, p["z"] * S, -p["y"] * S)
    obj.material_slots[0].link = "OBJECT"
    obj.material_slots[0].material = material(
        p["color"],
        "cloth" if p["part_number"] in ("64991c01.dat", "96714c01.dat") else "plastic",
    )
    obj["reveal"] = p["reveal"]
    obj["part_number"] = p["part_number"]
    objects.append(obj)
    by_id[p["id"]] = obj
bpy.context.view_layer.update()

floor_z = (
    min((o.matrix_world @ Vector(c)).z for o in objects for c in o.bound_box) - 0.0006
)
bpy.ops.mesh.primitive_plane_add(size=20, location=(0, 0, floor_z))
floor = bpy.context.object
floor.name = "Studio floor"
floor_mat = bpy.data.materials.new("Charcoal stage")
floor_mat.use_nodes = True
b = floor_mat.node_tree.nodes.get("Principled BSDF")
b.inputs["Base Color"].default_value = (0.014, 0.022, 0.032, 1)
b.inputs["Roughness"].default_value = 0.38
floor.data.materials.append(floor_mat)


def light(name, location, power, size, color):
    l = bpy.data.lights.new(name, "AREA")
    l.energy = power
    l.shape = "DISK"
    l.size = size
    l.color = color
    o = bpy.data.objects.new(name, l)
    scene.collection.objects.link(o)
    o.location = location
    o.rotation_euler = (
        (Vector((0, -0.03, 0.17)) - o.location).to_track_quat("-Z", "Y").to_euler()
    )


light("Large warm key", (-0.48, -0.55, 0.95), 16, 0.65, (1, 0.88, 0.76))
light("Cool fill", (0.65, -0.25, 0.5), 11, 0.5, (0.68, 0.81, 1))
light("Rim", (0.15, 0.6, 0.8), 22, 0.5, (1, 0.80, 0.65))
light("Low hull fill", (0, -0.65, 0.15), 2, 0.7, (0.7, 0.8, 1))
bpy.ops.object.camera_add()
camera = bpy.context.object
camera.name = "Product camera"
scene.camera = camera
camera.data.type = "ORTHO"
camera.data.clip_start = 0.001
camera.data.clip_end = 30
camera.data.sensor_fit = "HORIZONTAL"


def view(lat, lon, width, height, frame_objects=None, padding=1.14):
    frame_objects = frame_objects or objects
    points = [o.matrix_world @ Vector(v) for o in frame_objects for v in o.bound_box]
    lo = Vector(tuple(min(p[j] for p in points) for j in range(3)))
    hi = Vector(tuple(max(p[j] for p in points) for j in range(3)))
    target = (lo + hi) / 2
    a, b = math.radians(lat), math.radians(lon)
    direction = Vector(
        (math.sin(b) * math.cos(a), -math.cos(b) * math.cos(a), math.sin(a))
    )
    camera.location = target + direction * 2
    camera.rotation_euler = (
        (target - camera.location).to_track_quat("-Z", "Y").to_euler()
    )
    rot = camera.rotation_euler.to_matrix().transposed()
    pp = [rot @ (p - target) for p in points]
    sx = max(p.x for p in pp) - min(p.x for p in pp)
    sy = max(p.y for p in pp) - min(p.y for p in pp)
    camera.data.ortho_scale = max(sx, sy * (width / height)) * padding
    scene.render.resolution_x = width
    scene.render.resolution_y = height
    bpy.context.view_layer.update()


def render(path):
    if mode.startswith("shot-") and not path.name.startswith(mode[5:]):
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    scene.render.filepath = str(path)
    start = time.time()
    bpy.ops.render.render(write_still=True)
    print("RENDERED", path.name, round(time.time() - start, 2), flush=True)


if mode in ("proof", "proof-eevee"):
    if mode == "proof-eevee":
        scene.render.engine = "BLENDER_EEVEE_NEXT"
        scene.eevee.taa_render_samples = 32
    scene.cycles.samples = 24
    view(22, 55, 1000, 1000)
    render(OUT / (mode + ".png"))
    if mode == "proof":
        bpy.ops.wm.save_as_mainfile(
            filepath=str(OUT / "Orc Kraken - Presentation.blend")
        )
elif mode == "stills" or mode.startswith("shot-"):
    scene.cycles.samples = 48
    shots = [
        ("01-hero-front", 22, 55, 2048, 2048),
        ("02-port-bow", 25, -55, 2048, 2048),
        ("03-stern", 28, 140, 2048, 2048),
        ("04-broadside", 12, 90, 2048, 2048),
        ("05-hero-wide", 22, 55, 2560, 1440),
    ]
    for name, lat, lon, w, h in shots:
        view(lat, lon, w, h)
        render(OUT / "renders" / (name + ".png"))
    # Closeups retain the full scene; camera framing alone selects the detail.
    prow = [
        o
        for o, p in zip(objects, data["parts"])
        if p["z"] < -400
        and p["y"] > -210
        and p["part_number"] not in ("3708.dat", "59443.dat")
    ]
    view(18, 35, 2048, 2048, prow, 1.18)
    render(OUT / "renders/06-skull-and-captain.png")
    roots = [
        o
        for o, p in zip(objects, data["parts"])
        if p["x"] > 150 and -340 < p["z"] < -210 and -130 < p["y"] < 90
    ]
    view(20, 110, 2048, 2048, roots, 1.3)
    render(OUT / "renders/07-tentacle-closeup.png")
    roof = [
        o
        for o, p in zip(objects, data["parts"])
        if p["z"] > 330 and -290 < p["y"] < -140
    ]
    view(36, 135, 2048, 2048, roof, 1.25)
    render(OUT / "renders/08-command-deck.png")
    for o in objects:
        o.hide_render = False
    view(22, 55, 2048, 2048)
    # Leave an editable assembly timeline in the delivered Blender scene.
    for o in objects:
        o.hide_render = True
        o.keyframe_insert(data_path="hide_render", frame=0)
        o.hide_render = False
        o.keyframe_insert(data_path="hide_render", frame=int(o["reveal"]))
        if o.animation_data and o.animation_data.action:
            for curve in o.animation_data.action.fcurves:
                for key in curve.keyframe_points:
                    key.interpolation = "CONSTANT"
    scene.frame_start = 1
    scene.frame_end = len(data["stages"])
    scene.render.fps = 8
    scene.frame_set(scene.frame_end)
    bpy.ops.wm.save_as_mainfile(filepath=str(OUT / "Orc Kraken - Presentation.blend"))
elif mode == "build":
    scene.render.engine = "BLENDER_EEVEE_NEXT"
    scene.eevee.taa_render_samples = 64
    view(22, 55, 1080, 1080, objects, 1.23)
    camera.data.shift_y = 0.025
    for step in range(1, len(data["stages"]) + 1):
        target = OUT / "build-frames" / f"{step:04d}.png"
        if target.exists():
            continue
        for o in objects:
            o.hide_render = o["reveal"] > step
        render(target)
    for o in objects:
        o.hide_render = False
    render(OUT / "build-final.png")
print("DONE", mode, flush=True)
