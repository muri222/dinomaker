"""Versão A: modelo Roblox (.rbxmx) 100% autossuficiente.

Parts (caixas) + placas de detalhe pixel art, rig Motor6D com HumanoidRootPart,
Humanoid, animações embutidas como KeyframeSequence e scripts que tocam as
animações sem precisar publicar nada.
"""
import base64
import math
import os
import struct
from xml.sax.saxutils import escape

import numpy as np

from .genome import hex2rgb
from .mathx import mat4, inv4
from .texture import face_plates, key2rgb

LUA_DIR = os.path.join(os.path.dirname(__file__), "lua")

MATERIAL = {"Plastic": 256, "SmoothPlastic": 272, "Neon": 288}
PRIORITY = {"Idle": 0, "Movement": 1, "Action": 2, "Core": 1000}


# ---------------------------------------------------------------- XML helpers
class Ref:
    n = 0

    @classmethod
    def new(cls):
        cls.n += 1
        return "RBX%08X" % cls.n


def cf_xml(name, M):
    R, t = M[:3, :3], M[:3, 3]
    parts = ["<X>%.5f</X><Y>%.5f</Y><Z>%.5f</Z>" % tuple(t)]
    for i in range(3):
        for j in range(3):
            v = R[i, j]
            parts.append("<R%d%d>%.6f</R%d%d>" % (i, j, 0.0 if abs(v) < 1e-9 else v, i, j))
    return '<CoordinateFrame name="%s">%s</CoordinateFrame>' % (name, "".join(parts))


def v3_xml(name, v):
    return '<Vector3 name="%s"><X>%.5f</X><Y>%.5f</Y><Z>%.5f</Z></Vector3>' % (name, v[0], v[1], v[2])


def color_xml(rgb):
    r, g, b = (int(max(0, min(255, round(c)))) for c in rgb)
    return '<Color3uint8 name="Color3uint8">%d</Color3uint8>' % (0xFF000000 | (r << 16) | (g << 8) | b)


def attrs_xml(attrs):
    """AttributesSerialize: u32 n, (string key, u8 type, value)."""
    buf = struct.pack("<I", len(attrs))
    for k, v in attrs.items():
        kb = k.encode()
        buf += struct.pack("<I", len(kb)) + kb
        if isinstance(v, bool):
            buf += struct.pack("<BB", 0x03, 1 if v else 0)
        elif isinstance(v, (int, float)):
            buf += struct.pack("<Bd", 0x06, float(v))
        else:
            vb = str(v).encode()
            buf += struct.pack("<BI", 0x02, len(vb)) + vb
    return '<BinaryString name="AttributesSerialize">%s</BinaryString>' % base64.b64encode(buf).decode()


class Node:
    def __init__(self, cls, name, props=None):
        self.cls = cls
        self.name = name
        self.ref = Ref.new()
        self.props = props or []
        self.children = []

    def add(self, node):
        self.children.append(node)
        return node

    def xml(self, out, ind=0):
        sp = " " * ind
        out.append('%s<Item class="%s" referent="%s"><Properties>' % (sp, self.cls, self.ref))
        out.append('%s<string name="Name">%s</string>' % (sp, escape(self.name)))
        for p in self.props:
            out.append(sp + (p() if callable(p) else p))
        out.append(sp + "</Properties>")
        for c in self.children:
            c.xml(out, ind + 1)
        out.append(sp + "</Item>")


def part_node(name, M, size, rgb, material="SmoothPlastic", transparency=0.0, collide=False, studs=False, extra=()):
    props = [
        cf_xml("CFrame", M), v3_xml("size", size), color_xml(rgb),
        '<token name="Material">%d</token>' % MATERIAL[material],
        '<float name="Transparency">%g</float>' % transparency,
        '<bool name="Anchored">false</bool>',
        '<bool name="CanCollide">%s</bool>' % ("true" if collide else "false"),
        '<bool name="CanTouch">%s</bool>' % ("true" if collide else "false"),
        '<bool name="CanQuery">%s</bool>' % ("true" if collide else "false"),
        '<bool name="Massless">%s</bool>' % ("false" if collide else "true"),
        '<token name="shape">1</token>',
    ]
    s = 3 if studs else 0
    for face in ("TopSurface", "BottomSurface", "FrontSurface", "BackSurface", "LeftSurface", "RightSurface"):
        props.append('<token name="%s">%d</token>' % (face, (4 if (studs and face == "BottomSurface") else s)))
    props.extend(extra)
    return Node("Part", name, props)


def joint_node(cls, name, p0, p1, C0, C1):
    return Node(cls, name, [
        lambda: '<Ref name="Part0">%s</Ref>' % p0.ref,
        lambda: '<Ref name="Part1">%s</Ref>' % p1.ref,
        cf_xml("C0", C0), cf_xml("C1", C1),
    ])


def script_node(cls, name, source, run_context=None):
    props = ['<ProtectedString name="Source"><![CDATA[%s]]></ProtectedString>' % source]
    if run_context is not None:
        props.append('<bool name="Disabled">false</bool>')
        props.append('<token name="RunContext">%d</token>' % run_context)
    return Node(cls, name, props)


def _inside(model, bi, p):
    for k, box in enumerate(model.boxes):
        if k == bi:
            continue
        c, R = model.box_world_frame(box)
        q = R.T @ (p - c)
        if np.all(np.abs(q) <= box["size"] / 2 + 1e-6):
            return True
    return False


def _face_hidden(model, bi, f):
    """Face coberta por outras caixas na pose de descanso (amostra 5 pontos)."""
    box = model.boxes[bi]
    c, R = model.box_world_frame(box)
    pts = [(0.5, 0.5), (0.15, 0.15), (0.85, 0.15), (0.15, 0.85), (0.85, 0.85)]
    for a, b in pts:
        p = f["o"] + f["u"] * f["w"] * a + f["v"] * f["h"] * b + f["n"] * 0.3
        if not _inside(model, bi, c + R @ p):
            return False
    return True


# ---------------------------------------------------------------- export
def export_rbxmx(path, model, genome, faces, clips, meta, detail="medium"):
    Ref.n = 0
    s = genome["px_size"]
    studs = genome.get("studs", False)
    pal = genome["palette"]

    def S(M):
        M = M.copy()
        M[:3, 3] *= s
        return M

    root = Node("Model", genome["name"])

    # ---------------- partes por caixa
    by_box = {}
    for f in faces:
        by_box.setdefault(f["box"], []).append(f)
    main_part = {}
    counters = {}
    parts_out = []
    cands = []
    neon_roles = {"crystal"}
    for bi, box in enumerate(model.boxes):
        c, R = model.box_world_frame(box)
        M = mat4(R, c)
        fl = by_box.get(bi, [])
        # cor base = cor dominante (por área) entre as faces
        tally = {}
        for f in fl:
            base, cnt, _ = face_plates(f)
            tally[base] = tally.get(base, 0) + cnt
        base = max(tally, key=tally.get) if tally else 0x808080
        role = box["role"]
        bone = box["bone"]
        if bone not in main_part:
            name = bone
        else:
            counters[bone] = counters.get(bone, 0) + 1
            name = "%s_%s%d" % (bone, box["tag"], counters[bone])
        mat = "Neon" if role in neon_roles else ("Plastic" if studs else "SmoothPlastic")
        pn = part_node(name, S(M), box["size"] * s, key2rgb(base), mat, studs=studs and role == "skin")
        parts_out.append((bi, pn))
        if bone not in main_part:
            main_part[bone] = (pn, M)
        else:
            mp, MM = main_part[bone]
            C0 = S(inv4(MM) @ M)
            pn.add(joint_node("Weld", "Weld", mp, pn, C0, np.eye(4)))
        # ---------------- candidatos a placas pixel art (detalhes)
        for f in fl:
            if _face_hidden(model, bi, f):
                continue
            b2, _, rects = face_plates(f)
            if b2 != base:
                cands.append((bi, f, (0, 0, f["w"], f["h"], b2, "skin"), 0))
            for r in rects:
                cands.append((bi, f, r, 1))

    # ---------------- seleciona placas pelo orçamento (detalhes de rosto sempre entram)
    budget = {"high": 260, "medium": 140, "low": 60, "none": 0}.get(detail, detail if isinstance(detail, int) else 140)
    must = [c for c in cands if c[2][5] in ("eye", "nostril", "mouth", "crystal")]
    rest = sorted((c for c in cands if c[2][5] not in ("eye", "nostril", "mouth", "crystal")),
                  key=lambda c: -(c[2][2] * c[2][3]))
    rest = [c for c in rest if c[3] == 0] + [c for c in rest if c[3] == 1]
    chosen = must + rest[:max(0, budget - len(must))] if budget else []
    thick = 0.03
    for bi, f, (i, j, w, h, key, prole), layer in chosen:
        box = model.boxes[bi]
        bone = box["bone"]
        c, R = model.box_world_frame(box)
        M = mat4(R, c)
        cl = f["o"] + f["u"] * (i + w / 2) + f["v"] * (j + h / 2)
        Rl = np.column_stack([f["u"], f["v"], f["n"]])
        Mb = M @ mat4(Rl, cl)
        Mb[:3, 3] += (R @ f["n"]) * (thick / 2 + 0.004 + layer * (thick + 0.004)) / s
        counters[bone] = counters.get(bone, 0) + 1
        pmat = "Neon" if prole in ("crystal", "glow") or (prole == "eye" and genome["eyes"]["style"] == "glow") else "SmoothPlastic"
        pp = part_node("%s_px%d" % (bone, counters[bone]), S(Mb), (w * s, h * s, thick), key2rgb(key), pmat,
                       extra=['<bool name="CastShadow">false</bool>'])
        mp, MM = main_part[bone]
        pp.add(joint_node("Weld", "Weld", mp, pp, S(inv4(MM) @ Mb), np.eye(4)))
        parts_out.append((bi, pp))

    # ---------------- HumanoidRootPart
    hmn, hmx = (np.array(v) for v in model.meta["hips"])
    cmn, cmx = (np.array(v) for v in model.meta["chest"])
    hip_floor = hmn[1]
    hrp_size = np.array([max(hmx[0] - hmn[0], cmx[0] - cmn[0]), hmx[1] - hmn[1], hmx[2] - cmn[2]])
    hrp_c = np.array([0, hip_floor + hrp_size[1] / 2, (hmx[2] + cmn[2]) / 2])
    HRP_M = mat4(np.eye(3), hrp_c)
    hrp = part_node("HumanoidRootPart", S(HRP_M), hrp_size * s, (163, 162, 165), "SmoothPlastic",
                    transparency=1.0, collide=True)
    root.props.append(lambda: '<Ref name="PrimaryPart">%s</Ref>' % hrp.ref)
    root.add(hrp)

    # ---------------- Motor6D (dentro da parte filha, como no R15)
    rig_rest = {n: mat4(b["R"], b["pos"]) for n, b in model.bones.items()}
    for n, b in model.bones.items():
        pn, PM = main_part[n]
        J = rig_rest[n]
        if b["parent"]:
            p0, P0M = main_part[b["parent"]]
            mname = n
        else:
            p0, P0M = hrp, HRP_M
            mname = "Root"
        pn.add(joint_node("Motor6D", mname, p0, pn, S(inv4(P0M) @ J), S(inv4(PM) @ J)))

    from .vfx import add_vfx
    theme = add_vfx(Node, model, genome, main_part, s)

    for _, pn in parts_out:
        root.add(pn)

    # ---------------- Humanoid
    hum = Node("Humanoid", "Humanoid", [
        '<float name="HipHeight">%.4f</float>' % (hip_floor * s),
        '<token name="RigType">1</token>',
        '<bool name="RequiresNeck">false</bool>',
        '<bool name="BreakJointsOnDeath">false</bool>',
        '<float name="WalkSpeed">%.3f</float>' % (meta["walk_speed"] * s),
        '<token name="DisplayDistanceType">2</token>',
    ])
    hum.add(Node("Animator", "Animator"))
    root.add(hum)

    # ---------------- animações
    folder = root.add(Node("Folder", "Animations"))
    children = {n: [c for c, b in model.bones.items() if b["parent"] == n] for n in model.bones}

    def pose_tree(local, name, M):
        node = Node("Pose", name, [cf_xml("CFrame", M), '<float name="Weight">1</float>',
                                   '<token name="EasingStyle">0</token>', '<token name="EasingDirection">0</token>'])
        return node

    step = 2  # 15 keyframes/s
    for cname, clip in clips.items():
        kfs = Node("KeyframeSequence", cname, [
            '<bool name="Loop">%s</bool>' % ("true" if clip["loop"] else "false"),
            '<token name="Priority">%d</token>' % PRIORITY[clip["priority"]],
        ])
        nfr = len(clip["local"])
        idx = list(range(0, nfr, step))
        if idx[-1] != nfr - 1:
            idx.append(nfr - 1)
        for fi in idx:
            loc = clip["local"][fi]
            kf = Node("Keyframe", "Keyframe", ['<float name="Time">%.4f</float>' % (fi / 30.0)])
            rootpose = kf.add(Node("Pose", "HumanoidRootPart", [cf_xml("CFrame", np.eye(4)), '<float name="Weight">0</float>',
                                                                   '<token name="EasingStyle">0</token>', '<token name="EasingDirection">0</token>']))

            def rec(parent_node, bname):
                Rl, tl = loc[bname]
                M = mat4(Rl, tl * s)
                pn = parent_node.add(pose_tree(loc, main_part[bname][0].name, M))
                for ch in children[bname]:
                    rec(pn, ch)

            rec(rootpose, "Hips")
            kfs.add(kf)
        folder.add(kfs)

    # ---------------- scripts
    with open(os.path.join(LUA_DIR, "DinoAnimator.lua"), encoding="utf-8") as fh:
        anim_src = fh.read()
    with open(os.path.join(LUA_DIR, "DinoBrain.lua"), encoding="utf-8") as fh:
        brain_src = fh.read()
    with open(os.path.join(LUA_DIR, "DinoAPI.lua"), encoding="utf-8") as fh:
        api_src = fh.read()
    root.add(script_node("Script", "DinoAnimator", anim_src, run_context=2))
    root.add(script_node("Script", "DinoBrain", brain_src, run_context=1))
    root.add(script_node("ModuleScript", "DinoAPI", api_src))

    root.props.append(attrs_xml({
        "DinoName": genome["name"], "Species": genome["species"], "Archetype": genome["archetype"],
        "WalkSpeed": round(meta["walk_speed"] * s, 3), "RunSpeed": round(meta["run_speed"] * s, 3),
        "Wander": False, "WanderRadius": 40.0, "Action": "", "ActionNonce": 0.0,
        "AttackStyle": genome["attack"], "Flying": False,
        "VFX": True, "VFXTheme": theme,
    }))

    out = ['<roblox xmlns:xmime="http://www.w3.org/2005/05/xmlmime" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
           'xsi:noNamespaceSchemaLocation="http://www.roblox.com/roblox.xsd" version="4">',
           "<External>null</External><External>nil</External>"]
    root.xml(out)
    out.append("</roblox>")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(out))
    nparts = sum(1 for _ in parts_out) + 1
    return dict(parts=nparts, bones=len(model.bones), vfx=theme)
