"""VFX da versão A: ParticleEmitters + PointLight com texturas nativas do Roblox
(rbxasset://, não precisa upload). Controlados pelo DinoAnimator via atributos
`VFX` (liga/desliga) e `VFXTheme`.

Nomes que o script procura:
  Aura   (contínuo, corpo/cauda)     Breath (rajada da boca: Roar/Attack)
  Dust   (pés, taxa pela velocidade) Burst  (rajada no corpo: Hit/Death)
  Glow   (PointLight)
"""
import numpy as np

from .genome import hex2rgb
from .mathx import mat4, inv4

SPARK = "rbxasset://textures/particles/sparkles_main.dds"
FIRE = "rbxasset://textures/particles/fire_main.dds"
SMOKE = "rbxasset://textures/particles/smoke_main.dds"

# tema -> parâmetros (cores em hex; None = usa a paleta do dino)
THEMES = {
    "fire": dict(aura=dict(tex=FIRE, colors=["#ffd23a", "#ff5a1f"], size=(0.5, 0.0), life=(0.6, 1.1), rate=14, speed=(1, 3), accel=(0, 4, 0), light=0.8),
                 breath=dict(tex=FIRE, colors=["#fff1a0", "#ff6a1f", "#5a1a0a"], size=(0.8, 2.2), life=(0.5, 0.9), speed=(14, 20), spread=12, light=0.9),
                 glow="#ff7a2a"),
    "ice": dict(aura=dict(tex=SPARK, colors=["#ffffff", "#8fd8ff"], size=(0.35, 0.0), life=(1.0, 1.8), rate=10, speed=(0.5, 1.5), accel=(0, -1.5, 0), light=0.5),
                breath=dict(tex=SMOKE, colors=["#ffffff", "#bfe8ff"], size=(1.0, 3.0), life=(0.7, 1.1), speed=(10, 15), spread=14, light=0.2),
                glow="#8fd8ff"),
    "electric": dict(aura=dict(tex=SPARK, colors=["#ffffff", "#5ef2ff"], size=(0.4, 0.0), life=(0.15, 0.35), rate=22, speed=(4, 8), accel=(0, 0, 0), light=1.0),
                     breath=dict(tex=SPARK, colors=["#ffffff", "#ffe23a"], size=(0.6, 0.1), life=(0.25, 0.45), speed=(18, 28), spread=18, light=1.0),
                     glow="#5ef2ff"),
    "magic": dict(aura=dict(tex=SPARK, colors=["#ffffff", None], size=(0.4, 0.0), life=(1.2, 2.0), rate=12, speed=(0.3, 1.2), accel=(0, 0.8, 0), light=0.8),
                  breath=dict(tex=SPARK, colors=["#ffffff", None], size=(0.7, 0.0), life=(0.6, 1.0), speed=(10, 16), spread=20, light=0.9),
                  glow=None),
    "toxic": dict(aura=dict(tex=SMOKE, colors=["#b8ff5a", "#3a8f1a"], size=(0.3, 0.9), life=(1.0, 1.6), rate=6, speed=(0.5, 1.5), accel=(0, 1.2, 0), light=0.3),
                  breath=dict(tex=SMOKE, colors=["#c8ff6a", "#4a9f2a"], size=(1.0, 3.2), life=(0.8, 1.2), speed=(9, 14), spread=16, light=0.3),
                  glow="#9be02a"),
    "nature": dict(aura=dict(tex=SPARK, colors=["#e8ff9a", "#5fbf3a"], size=(0.3, 0.0), life=(1.4, 2.2), rate=5, speed=(0.3, 1.0), accel=(0, -0.6, 0), light=0.2),
                   breath=dict(tex=SMOKE, colors=["#ffffff", "#d8e8c8"], size=(0.8, 2.0), life=(0.5, 0.8), speed=(8, 12), spread=14, light=0.0),
                   glow=None),
    "water": dict(aura=dict(tex=SPARK, colors=["#ffffff", "#5fd0f0"], size=(0.35, 0.15), life=(1.2, 2.0), rate=9, speed=(0.3, 1.0), accel=(0, 1.5, 0), light=0.3),
                  breath=dict(tex=SMOKE, colors=["#ffffff", "#7fd8f0"], size=(0.8, 2.4), life=(0.5, 0.9), speed=(12, 18), spread=12, light=0.1),
                  glow=None),
    "none": dict(aura=None,
                 breath=dict(tex=SMOKE, colors=["#ffffff", "#e0e0e0"], size=(0.7, 1.8), life=(0.4, 0.7), speed=(7, 10), spread=14, light=0.0),
                 glow=None),
}


def auto_theme(g):
    pat = g["pattern"]["type"]
    feats = set(g["features"])
    pal = g.get("palette_name", "")
    if pat == "lava" or pal == "volcano":
        return "fire"
    if pat == "galaxy" or "gem" in feats or g["eyes"]["style"] == "glow":
        return "electric" if pal == "midnight" or pat == "zigzag" else "magic"
    if "crystals" in feats or pal in ("frost", "snow"):
        return "ice"
    if pal == "toxic":
        return "toxic"
    if pal in ("lagoon", "ocean"):
        return "water"
    if pal in ("candy", "bubblegum", "grape"):
        return "magic"
    if pal in ("sunset", "desert", "gold", "rust"):
        return "fire"
    if pal == "custom" and "#ff8fc8" in g["palette"].values():
        return "magic"
    return "nature"


# ---------------------------------------------------------------- XML
def _c3(hexc):
    return tuple(v / 255.0 for v in hex2rgb(hexc))


def _cseq(name, cols):
    n = len(cols)
    ks = []
    for i, c in enumerate(cols):
        r, g, b = _c3(c)
        ks.append("%g %g %g %g 0" % (i / (n - 1) if n > 1 else 0, r, g, b))
    if n == 1:
        r, g, b = _c3(cols[0])
        ks.append("1 %g %g %g 0" % (r, g, b))
    return '<ColorSequence name="%s">%s </ColorSequence>' % (name, " ".join(ks))


def _nseq(name, pts):
    return '<NumberSequence name="%s">%s </NumberSequence>' % (name, " ".join("%g %g 0" % p for p in pts))


def _nr(name, a, b):
    return '<NumberRange name="%s">%g %g </NumberRange>' % (name, a, b)


def emitter(Node, name, p, k, accent, enabled, rate=0.0, extra_spread=None):
    cols = [c if c else accent for c in p["colors"]]
    s0, s1 = p["size"]
    sp = p.get("spread", 180) if extra_spread is None else extra_spread
    acc = p.get("accel", (0, 0, 0))
    props = [
        '<bool name="Enabled">%s</bool>' % ("true" if enabled else "false"),
        '<Content name="Texture"><url>%s</url></Content>' % p["tex"],
        _cseq("Color", cols),
        _nseq("Size", [(0, s0 * k), (1, s1 * k)]),
        _nseq("Transparency", [(0, 0.1), (0.7, 0.3), (1, 1)]),
        _nr("Lifetime", *p["life"]),
        _nr("Speed", p["speed"][0] * k, p["speed"][1] * k),
        _nr("Rotation", 0, 360),
        _nr("RotSpeed", -90, 90),
        '<float name="Rate">%g</float>' % (rate if rate else p.get("rate", 0)),
        '<float name="LightEmission">%g</float>' % p.get("light", 0),
        '<Vector2 name="SpreadAngle"><X>%g</X><Y>%g</Y></Vector2>' % (sp, sp),
        '<Vector3 name="Acceleration"><X>%g</X><Y>%g</Y><Z>%g</Z></Vector3>' % tuple(a * k for a in acc),
        '<float name="Drag">1</float>',
    ]
    return Node("ParticleEmitter", name, props)


def _cf(M):
    from .export_rbx import cf_xml
    return cf_xml("CFrame", M)


def add_vfx(Node, model, genome, main_part, s, kit_folder=None):
    """Cria Attachments com emissores nas partes principais. Retorna o tema.
    kit_folder != None (versão B): os Attachments vão para essa pasta com CFrame no
    espaço do modelo (studs) + atributo Bone; o DinoRig os move para os ossos importados."""
    theme = genome.get("vfx", {}).get("theme") or auto_theme(genome)
    T = THEMES.get(theme, THEMES["none"])
    mn, mx = model.bbox()
    k = max(0.6, (mx[1] - mn[1]) * s / 6.0)  # escala dos efeitos pelo tamanho do dino
    accent = genome["palette"]["accent"]

    def attach(bone, world_pt, R=np.eye(3), name="FX"):
        if kit_folder is not None:
            from .export_rbx import attrs_xml
            W = mat4(R, np.array(world_pt, float) * s)
            att = Node("Attachment", name, [_cf(W), attrs_xml({"Bone": bone})])
            kit_folder.add(att)
            return att
        pn, PM = main_part[bone]
        L = inv4(PM) @ mat4(R, world_pt)
        L[:3, 3] *= s
        att = Node("Attachment", name, [_cf(L)])
        pn.add(att)
        return att

    # boca: frente/baixo do focinho, emitindo para frente (-Z => eixo Y do attachment)
    smn, smx = (np.array(v) for v in model.meta["snout"])
    if smn[2] >= model.meta["skull"][0][2]:
        smn, smx = (np.array(v) for v in model.meta["skull"])
    mouth = np.array([0.0, smn[1], smn[2] - 0.5])
    Rf = np.array([[1, 0, 0], [0, 0, 1], [0, -1, 0]], float)  # Y local -> -Z mundo
    a = attach("Head", mouth, Rf, "FX_Mouth")
    a.add(emitter(Node, "Breath", T["breath"], k, accent, False))

    cmn, cmx = (np.array(v) for v in model.meta["chest"])
    hmn, hmx = (np.array(v) for v in model.meta["hips"])
    body = (cmn + hmx) / 2
    a = attach("Chest", body, name="FX_Body")
    burst = dict(tex=SPARK, colors=["#ffffff", "#ffe8a0"], size=(0.6, 0.0), life=(0.3, 0.6), speed=(8, 14), light=0.8)
    a.add(emitter(Node, "Burst", burst, k, accent, False))
    if T["aura"]:
        a.add(emitter(Node, "Aura", T["aura"], k, accent, True))
    glow = T.get("glow") or (accent if theme == "magic" else None)
    if glow:
        r, g, b = _c3(glow)
        a.add(Node("PointLight", "Glow", ['<float name="Brightness">1.6</float>',
                                          '<float name="Range">%g</float>' % (8 * k),
                                          '<Color3 name="Color"><R>%g</R><G>%g</G><B>%g</B></Color3>' % (r, g, b),
                                          '<bool name="Shadows">false</bool>']))
    if T["aura"] and model.meta["tail"]:
        n = len(model.meta["tail"])
        tmn, tmx = (np.array(v) for v in model.meta["tail"][-1])
        a = attach("Tail%d" % n, (tmn + tmx) / 2, name="FX_Tail")
        a.add(emitter(Node, "Aura", dict(T["aura"], rate=T["aura"]["rate"] * 0.5), k * 0.7, accent, True))

    dust = dict(tex=SMOKE, colors=["#d8d0c0", "#a89c88"], size=(0.4, 1.4), life=(0.4, 0.8), speed=(1, 3), accel=(0, 1, 0), light=0)
    for lg in model.legs:
        foot = lg["bones"][2]
        p = lg["ankle"].copy()
        p[1] = 0.3
        a = attach(foot, p, name="FX_Foot")
        a.add(emitter(Node, "Dust", dust, k, accent, True, rate=0.0001, extra_spread=70))
    return theme
