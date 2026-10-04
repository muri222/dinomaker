"""QA da versão A: lê o .rbxmx, resolve o rig Motor6D exatamente como o Roblox
(Part1 = Part0 * C0 * Transform * C1^-1) usando as KeyframeSequences embutidas
e renderiza com o Blender (bpy). Uso:
  python tools/preview_rbx.py modelo.rbxmx saida.png [Clip] [tempo] [vista]
"""
import sys
import xml.etree.ElementTree as ET

import bpy
from mathutils import Matrix, Vector

CONV = Matrix(((-1, 0, 0, 0), (0, 0, 1, 0), (0, 1, 0, 0), (0, 0, 0, 1)))


def cf(el):
    g = {c.tag: float(c.text) for c in el}
    return Matrix(((g["R00"], g["R01"], g["R02"], g["X"]), (g["R10"], g["R11"], g["R12"], g["Y"]),
                   (g["R20"], g["R21"], g["R22"], g["Z"]), (0, 0, 0, 1)))


def props(item):
    out = {}
    for p in item.find("Properties"):
        out[p.get("name")] = p
    return out


def walk(item, parent, acc):
    acc.append((item, parent))
    for ch in item.findall("Item"):
        walk(ch, item, acc)


def main():
    a = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    path, out = a[0], a[1]
    clip = a[2] if len(a) > 2 else "Idle"
    t = float(a[3]) if len(a) > 3 else 0.0
    view = a[4] if len(a) > 4 else "front34"
    tree = ET.parse(path)
    items = []
    for it in tree.getroot().findall("Item"):
        walk(it, None, items)
    parts, joints, kfs = {}, [], {}
    for it, par in items:
        cls = it.get("class")
        P = props(it)
        if cls == "Part":
            col = int(P["Color3uint8"].text)
            parts[it.get("referent")] = dict(
                name=P["Name"].text, cf=cf(P["CFrame"]),
                size=Vector([float(P["size"].find(k).text) for k in "XYZ"]),
                color=(((col >> 16) & 255) / 255, ((col >> 8) & 255) / 255, (col & 255) / 255),
                transp=float(P["Transparency"].text))
        elif cls in ("Motor6D", "Weld"):
            joints.append(dict(cls=cls, p0=P["Part0"].text, p1=P["Part1"].text, C0=cf(P["C0"]), C1=cf(P["C1"])))
        elif cls == "KeyframeSequence":
            keys = []
            for kf in it.findall("Item"):
                kp = props(kf)
                poses = {}
                for sub, _ in [(x, None) for x in kf.iter("Item") if x.get("class") == "Pose"]:
                    sp = props(sub)
                    poses[sp["Name"].text] = cf(sp["CFrame"])
                keys.append((float(kp["Time"].text), poses))
            keys.sort(key=lambda k: k[0])
            kfs[props(it)["Name"].text] = keys

    keys = kfs.get(clip, [])
    pose = {}
    if keys:
        tt = min(t, keys[-1][0])
        lo = max(i for i in range(len(keys)) if keys[i][0] <= tt)
        hi = min(lo + 1, len(keys) - 1)
        span = keys[hi][0] - keys[lo][0]
        al = 0 if span <= 0 else (tt - keys[lo][0]) / span
        for n, m in keys[lo][1].items():
            mb = keys[hi][1].get(n, m)
            q = m.to_quaternion().slerp(mb.to_quaternion(), al)
            tr = m.translation.lerp(mb.translation, al)
            pose[n] = Matrix.Translation(tr) @ q.to_matrix().to_4x4()

    solved = {r: p["cf"] for r, p in parts.items() if p["name"] == "HumanoidRootPart"}
    changed = True
    while changed:
        changed = False
        for j in joints:
            if j["p0"] in solved and j["p1"] not in solved:
                T = pose.get(parts[j["p1"]]["name"], Matrix.Identity(4)) if j["cls"] == "Motor6D" else Matrix.Identity(4)
                solved[j["p1"]] = solved[j["p0"]] @ j["C0"] @ T @ j["C1"].inverted()
                changed = True
    missing = [p["name"] for r, p in parts.items() if r not in solved]
    if missing:
        print("PARTES SEM JUNTA:", missing[:10])

    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    mesh = bpy.data.meshes.new("cube")
    import bmesh
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bm.to_mesh(mesh)
    pts = []
    for r, p in parts.items():
        if p["transp"] >= 1 or r not in solved:
            continue
        o = bpy.data.objects.new(p["name"], mesh)
        sc.collection.objects.link(o)
        M = CONV @ solved[r] @ CONV.inverted()
        o.matrix_world = CONV @ solved[r] @ Matrix.Diagonal((p["size"].x, p["size"].y, p["size"].z, 1.0)) @ CONV.inverted()
        o.color = (*p["color"], 1)
        pts.append(M.translation)
    sc.render.engine = "BLENDER_WORKBENCH"
    sh = sc.display.shading
    sh.light = "STUDIO"
    sh.color_type = "OBJECT"
    sh.show_shadows = True
    sc.render.resolution_x = sc.render.resolution_y = 700
    w = bpy.data.worlds.new("W")
    sc.world = w
    w.color = (0.82, 0.84, 0.86)
    bpy.ops.mesh.primitive_plane_add(size=1000)
    bpy.context.active_object.color = (0.7, 0.72, 0.75, 1)
    cam = bpy.data.objects.new("C", bpy.data.cameras.new("C"))
    sc.collection.objects.link(cam)
    sc.camera = cam
    cam.data.clip_end = 5000
    mn = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    mx = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    c = (mn + mx) / 2
    r = (mx - mn).length
    d = Vector({"front34": (0.9, -1.1, 0.5), "side": (1, 0, 0.08), "top": (0.2, -0.3, 1)}[view]).normalized()
    cam.location = c + d * r * 1.5
    cam.rotation_euler = (c - cam.location).to_track_quat("-Z", "Y").to_euler()
    sc.render.filepath = out
    bpy.ops.render.render(write_still=True)
    print("PREVIEW_OK", len(solved), "partes")


main()
