"""Roda DENTRO do Blender (blender -b -P blender_build.py -- build.json) ou com o
módulo `bpy` do pip. Lê o build.json gerado pelo dinomaker e produz:
  .blend, .fbx (mesh + rig), .fbx por animação, .glb (preview) e renders.
Só usa bpy/mathutils/stdlib (o Python do Blender não tem Pillow).
"""
import json
import math
import os
import sys

import bpy
from mathutils import Matrix, Vector

# Roblox (x, y, z) -> Blender (-x, z, y): frente -Z do Roblox vira -Y no Blender
CONV = Matrix(((-1, 0, 0, 0), (0, 0, 1, 0), (0, 1, 0, 0), (0, 0, 0, 1)))
CONV_INV = CONV.inverted()


def args():
    a = sys.argv
    if "--" in a:
        a = a[a.index("--") + 1:]
    else:
        a = a[1:]
    return a[0]


def to_b(p, s):
    v = CONV @ Vector((p[0], p[1], p[2], 1.0))
    return Vector((v.x * s, v.y * s, v.z * s))


def mat_r(J, s):
    """Matriz 4x4 (lista linha-a-linha, espaço Roblox px) -> Blender (escala s)."""
    M = Matrix([J[0:4], J[4:8], J[8:12], J[12:16]])
    M = CONV @ M @ CONV_INV
    M.translation = M.translation * s
    return M


def clean_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def build_material(name, tex):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    bsdf = nt.nodes.get("Principled BSDF")

    def img(path, colorspace):
        n = nt.nodes.new("ShaderNodeTexImage")
        n.image = bpy.data.images.load(path)
        n.image.colorspace_settings.name = colorspace
        n.interpolation = "Closest"
        return n

    a = img(tex["albedo"], "sRGB")
    nt.links.new(a.outputs["Color"], bsdf.inputs["Base Color"])
    r = img(tex["roughness"], "Non-Color")
    nt.links.new(r.outputs["Color"], bsdf.inputs["Roughness"])
    nrm = img(tex["normal"], "Non-Color")
    nm = nt.nodes.new("ShaderNodeNormalMap")
    nt.links.new(nrm.outputs["Color"], nm.inputs["Color"])
    nt.links.new(nm.outputs["Normal"], bsdf.inputs["Normal"])
    bsdf.inputs["Metallic"].default_value = 0.0
    return mat


def build(data):
    s = data["px_size"]
    name = data["name"]
    clean_scene()
    scene = bpy.context.scene
    scene.render.fps = 30

    # ---------------------------------------------------- armature
    arm_data = bpy.data.armatures.new(name + "_Rig")
    arm = bpy.data.objects.new(name + "_Rig", arm_data)
    scene.collection.objects.link(arm)
    bpy.context.view_layer.objects.active = arm
    arm.select_set(True)
    bpy.ops.object.mode_set(mode="EDIT")
    ebs = {}
    for b in data["bones"]:
        eb = arm_data.edit_bones.new(b["name"])
        head = to_b(b["pos"], s)
        R = Matrix(b["R"])
        d = R @ Vector(b["dir"])
        d = (CONV.to_3x3() @ d).normalized()
        eb.head = head
        eb.tail = head + d * max(b.get("len", 4.0) * s, 0.05)
        eb.roll = 0.0
        ebs[b["name"]] = eb
    for b in data["bones"]:
        if b["parent"]:
            ebs[b["name"]].parent = ebs[b["parent"]]
            ebs[b["name"]].use_connect = False
    bpy.ops.object.mode_set(mode="OBJECT")

    # ---------------------------------------------------- mesh
    verts, faces, uvs, groups = [], [], [], []
    for f in data["faces"]:
        base = len(verts)
        for p in f["verts"]:
            verts.append(to_b(p, s))
        faces.append((base, base + 1, base + 2, base + 3))
        uvs.extend(f["uv"])
        groups.append(f["bone"])
    me = bpy.data.meshes.new(name + "_Mesh")
    me.from_pydata([tuple(v) for v in verts], [], faces)
    uvl = me.uv_layers.new(name="UVMap")
    for li in range(len(me.loops)):
        uvl.data[li].uv = uvs[li]
    me.update()
    obj = bpy.data.objects.new(name, me)
    scene.collection.objects.link(obj)
    mat = build_material(name + "_Mat", data["textures"])
    me.materials.append(mat)
    for bname in {b["name"] for b in data["bones"]}:
        obj.vertex_groups.new(name=bname)
    for fi, bname in enumerate(groups):
        vg = obj.vertex_groups[bname]
        vg.add([fi * 4 + k for k in range(4)], 1.0, "REPLACE")
    obj.parent = arm
    mod = obj.modifiers.new("Armature", "ARMATURE")
    mod.object = arm

    # ---------------------------------------------------- animações
    rest = {b.name: b.matrix_local.copy() for b in arm_data.bones}
    parent = {b["name"]: b["parent"] for b in data["bones"]}
    Rrest = {b["name"]: mat_r(b["Jrest"], s) for b in data["bones"]}
    Q = {n: Rrest[n].inverted() @ rest[n] for n in rest}
    for pb in arm.pose.bones:
        pb.rotation_mode = "QUATERNION"
    arm.animation_data_create()
    actions = {}
    for cname, clip in data["anims"].items():
        act = bpy.data.actions.new(cname)
        act.use_fake_user = True
        arm.animation_data.action = act
        frames = clip["frames"]
        for fi in range(frames):
            pose = {}
            for bn, Js in clip["world"].items():
                pose[bn] = mat_r(Js[fi], s) @ Q[bn]
            for pb in arm.pose.bones:
                n = pb.name
                if n not in pose:
                    continue
                if parent[n]:
                    basis = rest[n].inverted() @ rest[parent[n]] @ pose[parent[n]].inverted() @ pose[n]
                else:
                    basis = rest[n].inverted() @ pose[n]
                pb.matrix_basis = basis
                pb.keyframe_insert("location", frame=fi + 1)
                pb.keyframe_insert("rotation_quaternion", frame=fi + 1)
        actions[cname] = act
    for pb in arm.pose.bones:
        pb.matrix_basis = Matrix.Identity(4)
    if "Idle" in actions:
        arm.animation_data.action = actions["Idle"]
    return arm, obj, actions


def export(data, arm, obj, actions):
    out = data["export"]
    scene = bpy.context.scene
    os.makedirs(os.path.dirname(out["blend"]), exist_ok=True)

    def select_rig():
        bpy.ops.object.select_all(action="DESELECT")
        arm.select_set(True)
        obj.select_set(True)
        bpy.context.view_layer.objects.active = arm

    fbx_common = dict(
        use_selection=True, object_types={"ARMATURE", "MESH"}, add_leaf_bones=False,
        armature_nodetype="NULL", use_armature_deform_only=False, mesh_smooth_type="FACE",
        path_mode="STRIP", embed_textures=False, axis_forward="-Z", axis_up="Y",
        apply_scale_options="FBX_SCALE_ALL", global_scale=1.0, bake_anim_simplify_factor=0.0,
    )
    if out.get("fbx"):
        select_rig()
        arm.animation_data.action = None
        for pb in arm.pose.bones:
            pb.matrix_basis = Matrix.Identity(4)
        bpy.ops.export_scene.fbx(filepath=out["fbx"], bake_anim=False, **fbx_common)
    if out.get("fbx_anims"):
        os.makedirs(out["fbx_anims"], exist_ok=True)
        for cname, act in actions.items():
            select_rig()
            arm.animation_data.action = act
            fr = act.frame_range
            scene.frame_start, scene.frame_end = int(fr[0]), int(fr[1])
            bpy.ops.export_scene.fbx(filepath=os.path.join(out["fbx_anims"], "%s_%s.fbx" % (data["name"], cname)),
                                     bake_anim=True, bake_anim_use_all_actions=False, bake_anim_use_nla_strips=False,
                                     bake_anim_force_startend_keying=True, **fbx_common)
    if out.get("glb"):
        select_rig()
        if "Idle" in actions:
            arm.animation_data.action = actions["Idle"]
        bpy.ops.export_scene.gltf(filepath=out["glb"], use_selection=True, export_format="GLB",
                                  export_animation_mode="ACTIONS", export_force_sampling=True)
    if "Idle" in actions:
        arm.animation_data.action = actions["Idle"]
        scene.frame_start, scene.frame_end = 1, int(actions["Idle"].frame_range[1])
    bpy.ops.wm.save_as_mainfile(filepath=out["blend"])


def render_previews(data, arm, obj, actions):
    prev = data["export"].get("previews")
    if not prev:
        return
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_WORKBENCH"
    sh = scene.display.shading
    sh.light = "STUDIO"
    sh.color_type = "TEXTURE"
    sh.show_shadows = True
    scene.display.shadow_focus = 0.6
    scene.render.resolution_x = prev.get("res", 640)
    scene.render.resolution_y = prev.get("res", 640)
    w = bpy.data.worlds.new("W")
    scene.world = w
    w.color = (0.82, 0.84, 0.86)
    bpy.ops.mesh.primitive_plane_add(size=500)
    ground = bpy.context.active_object
    gm = bpy.data.materials.new("Ground")
    gm.diffuse_color = (0.75, 0.77, 0.8, 1)
    ground.data.materials.append(gm)
    sh.color_type = "TEXTURE"

    cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam"))
    scene.collection.objects.link(cam)
    scene.camera = cam
    cam.data.lens = 50
    cam.data.clip_end = 5000

    from mathutils import Vector as V
    bb = [obj.matrix_world @ V(c) for c in obj.bound_box]
    mn = V((min(p.x for p in bb), min(p.y for p in bb), min(p.z for p in bb)))
    mx = V((max(p.x for p in bb), max(p.y for p in bb), max(p.z for p in bb)))
    ctr = (mn + mx) / 2
    rad = (mx - mn).length
    views = prev.get("views", {"front34": (0.9, -1.1, 0.5), "side": (1.0, 0.0, 0.08)})
    jobs = [(c, f, vn, d) for c, f in prev.get("poses", [["Idle", 1]]) for vn, d in views.items()]
    if prev.get("side_idle"):
        jobs.append(("Idle", 1, "side", (1.0, 0.0, 0.08)))
    for clip, frame, vn, d in jobs:
        if clip in actions:
            arm.animation_data.action = actions[clip]
        scene.frame_set(int(frame))
        d = V(d).normalized()
        cam.location = ctr + d * rad * 1.35
        cam.rotation_euler = (ctr - cam.location).to_track_quat("-Z", "Y").to_euler()
        scene.render.filepath = os.path.join(prev["dir"], "%s_%s.png" % (clip.lower(), vn))
        bpy.ops.render.render(write_still=True)


def main():
    with open(args(), encoding="utf-8") as f:
        data = json.load(f)
    arm, obj, actions = build(data)
    export(data, arm, obj, actions)
    render_previews(data, arm, obj, actions)
    print("DINOMAKER_BLENDER_OK")


if __name__ == "__main__":
    main()
