"""Constrói o modelo (ossos + caixas) a partir dos parâmetros resolvidos do genoma.

Espaço: Roblox (X direita, Y cima, frente = -Z), unidade = pixel de textura.
Cada osso tem posição de junta e rotação de descanso no mundo; cada caixa vive
no espaço local de um osso. Decals e zonas usam coordenadas locais do osso.
"""
import math
import numpy as np

from .mathx import rx, ry, rz

I3 = np.eye(3)


def ri(v):
    return max(1, int(round(v)))


def dvec(a):
    """Direção 'para baixo' girada em X por a (a > 0 aponta para frente)."""
    return np.array([0.0, -math.cos(a), -math.sin(a)])


class Model:
    def __init__(self, P, features):
        self.P = P
        self.features = set(features)
        self.bones = {}
        self.boxes = []
        self.legs = []
        self.arms = []
        self.meta = {}

    # ------------------------------------------------------------ ossos
    def bone(self, name, parent, pos, R=None, kind="body", direction=(0, 0, -1)):
        self.bones[name] = dict(
            name=name, parent=parent, pos=np.array(pos, float),
            R=I3.copy() if R is None else np.array(R, float), kind=kind,
            dir=np.array(direction, float),
        )
        return self.bones[name]

    def children(self, name):
        return [b for b in self.bones.values() if b["parent"] == name]

    # ------------------------------------------------------------ caixas
    def box_local(self, bone, center, size, role="skin", R=None, **kw):
        b = dict(
            bone=bone, c=np.array(center, float),
            size=np.array([ri(s) for s in size], float),
            R=I3.copy() if R is None else np.array(R, float), role=role,
            zones=kw.pop("zones", []), decals=kw.pop("decals", []),
            face_roles=kw.pop("face_roles", {}), tag=kw.pop("tag", role),
        )
        b.update(kw)
        self.boxes.append(b)
        return b

    def box_world(self, bone, mn, mx, role="skin", **kw):
        B = self.bones[bone]
        mn, mx = np.array(mn, float), np.array(mx, float)
        size = np.array([ri(s) for s in (mx - mn)], float)
        c = (mn + mx) / 2
        Rb = B["R"]
        return self.box_local(bone, Rb.T @ (c - B["pos"]), size, role, R=Rb.T, **kw)

    def box_world_frame(self, box):
        B = self.bones[box["bone"]]
        R = B["R"] @ box["R"]
        c = B["pos"] + B["R"] @ box["c"]
        return c, R

    def bbox(self):
        pts = []
        for b in self.boxes:
            c, R = self.box_world_frame(b)
            h = b["size"] / 2
            for sx in (-1, 1):
                for sy in (-1, 1):
                    for sz in (-1, 1):
                        pts.append(c + R @ (h * np.array([sx, sy, sz])))
        pts = np.array(pts)
        return pts.min(0), pts.max(0)


# ================================================================ construção
def build_model(genome):
    P = genome["params"]
    feats = set(genome["features"])
    m = Model(P, feats)
    biped = P["stance"] == "biped"
    winged = "wings" in feats

    # ---------------------------------------------------------- tronco
    a1, a2 = math.radians(P["knee_ang"]), math.radians(P["shin_ang"])
    L1, L2, fh = P["thigh"], P["shin"], P["foot_h"]
    hip_y = L1 * math.cos(a1) + L2 * math.cos(a2) + fh
    bw, bh, hl, cl = P["body_w"], P["body_h"], P["hips_len"], P["chest_len"]
    cw, ch = P["chest_w"], P["chest_h"]
    hips_bot = hip_y - bh * 0.35

    m.bone("Hips", None, (0, hip_y, 0), kind="root")
    m.box_world("Hips", (-bw / 2, hips_bot, -hl / 2), (bw / 2, hips_bot + bh, hl / 2), "skin", tag="body")
    m.meta["hips"] = ((-bw / 2, hips_bot, -hl / 2), (bw / 2, hips_bot + bh, hl / 2))

    chest_bot = hips_bot + P["chest_dy"]
    chest_front = -hl / 2 - cl
    chest_top = chest_bot + ch
    m.bone("Chest", "Hips", (0, chest_bot + ch * 0.5, -hl / 2))
    m.box_world("Chest", (-cw / 2, chest_bot, chest_front), (cw / 2, chest_top, -hl / 2), "skin", tag="body")
    m.meta["chest"] = ((-cw / 2, chest_bot, chest_front), (cw / 2, chest_top, -hl / 2))

    # ---------------------------------------------------------- pescoço
    nw, nh = P["neck_w"], P["neck_h"]
    jy = chest_top - nh * 0.55
    jz = chest_front
    parent, pw, ph = "Chest", cw, ch
    m.meta["neck"] = []
    for k in range(int(P["neck_segs"])):
        name = "Neck%d" % (k + 1)
        m.bone(name, parent, (0, jy, jz))
        w = ri(nw * (1 - P["neck_taper"] * k))
        h = ri(nh * (1 - P["neck_taper"] * k))
        L, rise = P["neck_len"], P["neck_rise"]
        ov = min(4.0, max(1.0, L * 0.4)) if (w < pw and h < ph) else 0
        hx = abs(rise) * 0.5
        mn = (-w / 2, jy - h / 2 + rise * 0.5 - hx / 2, jz - L)
        mx = (w / 2, jy + h / 2 + rise * 0.5 + hx / 2, jz + ov)
        m.box_world(name, mn, mx, "skin", tag="neck")
        m.meta["neck"].append((mn, mx))
        jz -= L
        jy += rise
        parent, pw, ph = name, w, h

    # ---------------------------------------------------------- cabeça
    sl, sh, sw = P["skull_len"], P["skull_h"], P["skull_w"]
    nl, snh, snw = P["snout_len"], P["snout_h"], P["snout_w"]
    m.bone("Head", parent, (0, jy, jz), kind="head")
    skull_bot = jy - sh * 0.45
    skull_back = jz + 2
    skull_front = skull_back - sl
    skull_top = skull_bot + sh
    snout_front = skull_front - nl
    jw = max(snw - 2, 2)
    jh = P["jaw_h"]
    jaw_back = skull_back - sl * 0.45
    hx, hy, hz = 0.0, jy, jz  # posição do osso Head

    def H(p):  # mundo -> local do osso Head (rotação identidade)
        return np.array(p, float) - np.array([hx, hy, hz])

    eye_y = skull_bot + sh * 0.68
    eye_z = skull_front + sl * 0.32
    eye_size = P.get("eye", 3)
    decals = [dict(kind="eye", pos=H((0, eye_y, eye_z)), size=eye_size, faces=("+X", "-X"))]
    m.meta["eye"] = (eye_y, eye_z, eye_size)
    mouth_zone = dict(role="mouth", faces=("-Y",), x=(-jw / 2, jw / 2), z=(H((0, 0, snout_front))[2] - 1, H((0, 0, jaw_back))[2]))
    beak_zone = None
    if "beak" in feats:
        bk = max(2, nl * 0.35)
        beak_zone = dict(role="beak", z=(-999, H((0, 0, snout_front + bk))[2]))

    skull = m.box_world("Head", (-sw / 2, skull_bot, skull_front), (sw / 2, skull_top, skull_back), "skin",
                        tag="head", decals=decals, zones=[mouth_zone])
    snout_zones = [mouth_zone] + ([beak_zone] if beak_zone else [])
    nostrils = [dict(kind="nostril", pos=H((s * (snw / 2 - 1.5), skull_bot + snh, snout_front + 1.5)), size=1, faces=("+Y",)) for s in (-1, 1)]
    if snout_front < skull_front:
        m.box_world("Head", (-snw / 2, skull_bot, snout_front), (snw / 2, skull_bot + snh, skull_front), "skin",
                    tag="head", zones=snout_zones, decals=nostrils)
    m.meta.update(skull=((-sw / 2, skull_bot, skull_front), (sw / 2, skull_top, skull_back)),
                  snout=((-snw / 2, skull_bot, snout_front), (snw / 2, skull_bot + snh, skull_front)))

    m.bone("Jaw", "Head", (0, skull_bot, jaw_back), kind="jaw")
    jzones = [dict(role="mouth", faces=("+Y",))]
    if beak_zone:
        jzones.append(dict(role="beak", z=(-999, snout_front + max(2, nl * 0.35) - jaw_back)))
    m.box_world("Jaw", (-jw / 2, skull_bot - jh, snout_front + 0.5), (jw / 2, skull_bot, jaw_back), "skin", tag="head", zones=jzones)
    m.meta["jaw"] = ((-jw / 2, skull_bot - jh, snout_front + 0.5), (jw / 2, skull_bot, jaw_back))

    if "teeth" in feats and "beak" not in feats:
        z = snout_front + 1.5
        while z < min(skull_front + sl * 0.3, jaw_back - 1):
            xw = snw if z < skull_front else min(sw, snw + 2)
            for s in (-1, 1):
                x = s * (xw / 2 - 0.5)
                m.box_world("Head", (x - 0.5, skull_bot - 2, z - 0.5), (x + 0.5, skull_bot, z + 0.5), "tooth", tag="tooth")
            z += 2
        x = -snw / 2 + 2.5
        while x < snw / 2 - 2:
            m.box_world("Head", (x - 0.5, skull_bot - 2, snout_front), (x + 0.5, skull_bot, snout_front + 1), "tooth", tag="tooth")
            x += 2

    # ---------------------------------------------------------- cauda
    tw, th = P["tail_w"], P["tail_h"]
    jy = hips_bot + bh * 0.58
    jz = hl / 2
    parent, pw, ph = "Hips", bw, bh
    m.meta["tail"] = []
    nseg = int(P["tail_segs"])
    for k in range(nseg):
        name = "Tail%d" % (k + 1)
        m.bone(name, parent, (0, jy, jz), kind="tail", direction=(0, 0, 1))
        f = P["tail_taper"] ** k
        w, h = ri(tw * f), ri(th * f)
        L = ri(P["tail_len"] * (0.94 ** k))
        rise = P["tail_rise"]
        ov = min(4.0, max(1.0, L * 0.4)) if (w < pw and h < ph) else 0
        mn = (-w / 2, jy - h / 2 + rise * 0.5, jz - ov)
        mx = (w / 2, jy + h / 2 + rise * 0.5, jz + L)
        m.box_world(name, mn, mx, "skin", tag="tail")
        m.meta["tail"].append((mn, mx))
        jz += L
        jy += rise
        parent, pw, ph = name, w, h

    # ---------------------------------------------------------- pernas traseiras
    thw, thd, shw = P["thigh_w"], P["thigh_d"], P["shin_w"]
    fl, fw = P["foot_len"], P["foot_w"]
    for s, side in ((1, "R"), (-1, "L")):
        if biped:
            lx = s * (bw / 2 + thw / 2 - 2)
        else:
            lx = s * (bw / 2 - thw / 2 + 1)
        hip = np.array([lx, hip_y, hl * 0.1])
        knee = hip + L1 * dvec(a1)
        ankle = knee + L2 * dvec(a2)
        _leg(m, side, s, "Hips", hip, knee, ankle, a1, a2, (thw, thd), (shw, shw), (fw, fh, fl),
             P["toes"], names=("Thigh", "Shin", "Foot"), group="hind", sickle="sickle_claw" in feats)

    # ---------------------------------------------------------- pernas dianteiras / braços
    if not biped:
        fwid = P.get("front_w", thw)
        b1, b2 = math.radians(P.get("front_ang1", 0)), math.radians(P.get("front_ang2", 0))
        shoulder_y = chest_bot + ch * 0.3
        V = shoulder_y - fh
        U = V * 0.5 / math.cos(b1)
        F = (V - U * math.cos(b1)) / math.cos(b2)
        for s, side in ((1, "R"), (-1, "L")):
            if winged:
                fx = s * (cw / 2 + fwid / 2)
            else:
                fx = s * (cw / 2 - fwid / 2 + 1)
            sh_ = np.array([fx, shoulder_y, chest_front + cl * 0.3])
            el = sh_ + U * dvec(b1)
            wr = el + F * dvec(b2)
            _leg(m, side, s, "Chest", sh_, el, wr, b1, b2, (fwid, fwid), (max(fwid - 1, 2), max(fwid - 1, 2)),
                 (fwid + 1, fh, max(fwid, 4)), P["toes"], names=("UpperArm", "Forearm", "Hand"), group="front")
            if winged:
                depth = hl + cl + 4
                m.box_local("UpperArm" + side, (0, -U / 2, depth / 2), (1, U, depth), "wing", tag="wing")
                m.box_local("Forearm" + side, (0, -F / 2, depth * 0.35), (1, F, depth * 0.7), "wing", tag="wing")
                m.meta["wing_span"] = U + F
    else:
        _arms(m, P, feats, cw, chest_bot, ch, chest_front)

    # ---------------------------------------------------------- features
    _features(m, P, feats)
    fix_coplanar(m, eps=min(0.15, max(0.05, 0.03 / float(genome.get("px_size", 0.14)))))
    return m


def coplanar_conflicts(m, tol=1e-3):
    """Pares de caixas (mesma rotação) com faces no mesmo plano, mesma direção e
    área sobreposta -> z-fighting. Retorna (i, j, eixo, lado)."""
    out = []
    W = [m.box_world_frame(b) for b in m.boxes]
    for i, a in enumerate(m.boxes):
        ca, Ra = W[i]
        ha = a["size"] / 2
        for j in range(i + 1, len(m.boxes)):
            b = m.boxes[j]
            cb, Rb = W[j]
            if not np.allclose(Ra, Rb, atol=1e-6):
                continue
            d = Ra.T @ (cb - ca)
            hb = b["size"] / 2
            for ax in range(3):
                o = [k for k in range(3) if k != ax]
                if not all(min(d[k] + hb[k], ha[k]) - max(d[k] - hb[k], -ha[k]) > tol for k in o):
                    continue
                for sgn in (1, -1):
                    if abs((d[ax] + sgn * hb[ax]) - sgn * ha[ax]) < tol:
                        out.append((i, j, ax, sgn))
    return out


def fix_coplanar(m, eps=0.2, passes=4):
    """Recua a face da caixa menor (eps px) em cada conflito de z-fighting."""
    for _ in range(passes):
        conf = coplanar_conflicts(m)
        if not conf:
            return
        done = set()
        for i, j, ax, sgn in conf:
            a, b = m.boxes[i], m.boxes[j]
            cands = sorted([(i, a, sgn), (j, b, sgn)], key=lambda t: np.prod(t[1]["size"]))
            pick = None
            for k, box, sg in cands:
                orig = box.setdefault("size0", box["size"].copy())
                if box["size"][ax] - eps >= max(0.5, 0.6 * orig[ax]):
                    pick = (k, box, sg)
                    break
            if pick is None:
                continue
            k, box, sgn = pick
            if (k, ax, sgn) in done:
                continue
            done.add((k, ax, sgn))
            box["size"] = box["size"].copy()
            box["size"][ax] -= eps
            # move o centro para a face oposta ficar no lugar (eixo local da caixa)
            box["c"] = box["c"] - box["R"][:, ax] * (sgn * eps / 2)


def _leg(m, side, s, parent, hip, knee, ankle, a1, a2, upper_wd, lower_wd, foot_whl, toes, names, group, sickle=False):
    n1, n2, n3 = (n + side for n in names)
    L1 = np.linalg.norm(knee - hip)
    L2 = np.linalg.norm(ankle - knee)
    m.bone(n1, parent, hip, R=rx(a1), kind="leg", direction=(0, -1, 0))
    m.box_local(n1, (0, -L1 / 2, 0), (upper_wd[0], L1 + 2, upper_wd[1]), "skin", tag="leg")
    m.bone(n2, n1, knee, R=rx(a2), kind="leg", direction=(0, -1, 0))
    m.box_local(n2, (0, -L2 / 2, 0), (lower_wd[0], L2 + 1, lower_wd[1]), "skin", tag="leg")
    fw, fh, fl = foot_whl
    heel = min(2.0, fl * 0.25)
    m.bone(n3, n2, ankle, kind="foot", direction=(0, 0, -1))
    m.box_local(n3, (0, -fh / 2, -fl / 2 + heel), (fw, fh, fl), "skin", tag="foot")
    nt = int(toes)
    xs = np.linspace(-fw / 2 + 1, fw / 2 - 1, nt) if nt > 1 else [0.0]
    for x in xs:
        m.box_local(n3, (round(x * 2) / 2, -fh + 1, -fl + heel - 1), (1, 2, 2), "claw", tag="claw")
    if sickle:
        m.box_local(n3, (-s * (fw / 2 - 0.5), -fh + 2.5, -1), (1, 3, 2), "claw", R=rx(math.radians(25)), tag="claw")
    # sinal do joelho: + quando o joelho fica à frente da linha quadril-tornozelo
    base = math.atan2(-(ankle - hip)[2], -(ankle - hip)[1])
    m.legs.append(dict(
        side=s, group=group, parent=parent, bones=[n1, n2, n3],
        hip=hip.copy(), ankle=ankle.copy(), L1=float(L1), L2=float(L2), a1=a1, a2=a2,
        knee_sign=1.0 if a1 - base >= 0 else -1.0,
    ))


def _arms(m, P, feats, cw, chest_bot, ch, chest_front):
    aw = P["arm_w"]
    up, fo, ha = P["arm"], P["fore"], P["hand"]
    style = P.get("arm_style", "tiny")
    ang = {"tiny": (35, 80, 70), "medium": (25, 60, 40), "long": (20, 70, 50)}[style]
    for s, side in ((1, "R"), (-1, "L")):
        sh_ = np.array([s * (cw / 2 + aw / 2 - 0.5), chest_bot + ch * 0.35, chest_front + 3])
        A1, A2, A3 = (math.radians(a) for a in ang)
        el = sh_ + up * dvec(A1)
        wr = el + fo * dvec(A2)
        m.bone("UpperArm" + side, "Chest", sh_, R=rx(A1), kind="arm", direction=(0, -1, 0))
        m.box_local("UpperArm" + side, (0, -up / 2, 0), (aw, up + 1, aw + 1), "skin", tag="arm")
        m.bone("Forearm" + side, "UpperArm" + side, el, R=rx(A2), kind="arm", direction=(0, -1, 0))
        m.box_local("Forearm" + side, (0, -fo / 2, 0), (max(aw - 1, 1) if aw > 2 else aw, fo + 1, aw), "skin", tag="arm")
        m.bone("Hand" + side, "Forearm" + side, wr, R=rx(A3), kind="hand", direction=(0, -1, 0))
        m.box_local("Hand" + side, (0, -ha / 2, 0), (aw + 1, ha, max(aw - 1, 1)), "skin", tag="arm")
        big = "big_claws" in feats
        for x in ((-1, 0, 1) if aw + 1 >= 3 else (0,)):
            if big:
                m.box_local("Hand" + side, (x * 1.0, -ha - 2.5, 0.5), (1, 5, 1), "claw", R=rx(math.radians(-20)), tag="claw")
            else:
                m.box_local("Hand" + side, (x * 1.0, -ha - 0.5, 0.5), (1, 2, 1), "claw", tag="claw")
        if "thumb_spike" in feats:
            m.box_local("Hand" + side, (0, -1, -1.5), (1, 1, 3), "horn", tag="horn")
        if "feathers" in feats:
            m.box_local("Forearm" + side, (0, -fo / 2, 1.5), (1, fo, 3), "feather", tag="feather")
        m.arms.append(dict(side=s, bones=["UpperArm" + side, "Forearm" + side, "Hand" + side]))


def _top_boxes(m):
    """Lista (osso, mn, mx) dos segmentos da coluna para features dorsais."""
    out = []
    for i, (mn, mx) in enumerate(m.meta["neck"]):
        out.append(("Neck%d" % (i + 1), mn, mx))
    out.append(("Chest",) + m.meta["chest"])
    out.append(("Hips",) + m.meta["hips"])
    for i, (mn, mx) in enumerate(m.meta["tail"]):
        out.append(("Tail%d" % (i + 1), mn, mx))
    return out


def _wb(m, bone, mn, mx, role, **kw):
    return m.box_world(bone, mn, mx, role, **kw)


def _features(m, P, feats):
    smn, smx = (np.array(v) for v in m.meta["skull"])
    sw = smx[0] - smn[0]
    sl = smx[2] - smn[2]
    top = smx[1]
    eye_y, eye_z, _ = m.meta["eye"]
    nmn, nmx = (np.array(v) for v in m.meta["snout"])
    spine = _top_boxes(m)
    rnd = np.random.RandomState(int(P.get("seed", 0)) % (2 ** 31))

    if "horns_brow" in feats:
        for s in (-1, 1):
            x = s * (sw / 2 - 1.5)
            _wb(m, "Head", (x - 1, top, eye_z - 1), (x + 1, top + 3, eye_z + 1), "horn", tag="horn")
            _wb(m, "Head", (x - 0.5 + s * 0.5, top + 3, eye_z - 0.5), (x + 0.5 + s * 0.5, top + 4, eye_z + 0.5), "horn", tag="horn")
    if "horns_long" in feats:
        for s in (-1, 1):
            x = s * (sw / 2 - 2)
            for k in range(3):
                _wb(m, "Head", (x - 1, top + k * 2, eye_z - 1 - k * 2), (x + 1, top + 2 + k * 2, eye_z + 1 - k * 2), "horn", tag="horn")
    if "horn_nose" in feats:
        z = nmn[2] + 3
        _wb(m, "Head", (-1, nmx[1], z - 1), (1, nmx[1] + 3, z + 1), "horn", tag="horn")
        _wb(m, "Head", (-0.5, nmx[1] + 3, z - 1.5), (0.5, nmx[1] + 4, z - 0.5), "horn", tag="horn")
    if "frill" in feats or "frill_spikes" in feats:
        fwid = ri(sw * 1.7)
        fhh = ri((smx[1] - smn[1]) * 1.25)
        hp = m.bones["Head"]["pos"]
        Rf = rx(math.radians(28))
        c = np.array([0, smn[1] + fhh * 0.55, smx[2] + 0.5])
        m.box_local("Head", c - hp, (fwid, fhh, 2), "frill", R=Rf, tag="frill")
        m.box_local("Head", c - hp + Rf @ np.array([0, fhh / 2 + 1, 0]), (ri(fwid * 0.6), 2, 2), "frill", R=Rf, tag="frill")
        if "frill_spikes" in feats:
            for k, x in enumerate(np.linspace(-fwid / 2 + 1.5, fwid / 2 - 1.5, 5)):
                hgt = 5 if k in (1, 3) else 4
                p = c + Rf @ np.array([x, fhh / 2 + hgt / 2 + (2 if k == 2 else 0), 0])
                m.box_local("Head", p - hp, (2, hgt, 1), "horn", R=Rf, tag="horn")
    if "dome" in feats:
        _wb(m, "Head", (-sw / 2, top - 1, smn[2]), (sw / 2, top + 2, smx[2]), "dome", tag="dome")
        _wb(m, "Head", (-sw / 2 + 1.5, top + 2, smn[2] + 1.5), (sw / 2 - 1.5, top + 4, smx[2] - 1.5), "dome", tag="dome")
        for x in np.linspace(-sw / 2 + 1, sw / 2 - 1, 4):
            _wb(m, "Head", (x - 0.5, top, smx[2]), (x + 0.5, top + 2, smx[2] + 1), "horn", tag="horn")
    if "crest_tube" in feats:
        for k in range(3):
            z0 = smx[2] - 4 + k * 4
            _wb(m, "Head", (-1.5, top + k * 2, z0), (1.5, top + 3 + k * 2, z0 + 4), "crest", tag="crest")
    if "crest_fan" in feats:
        _wb(m, "Head", (-1, top, smn[2] + 1), (1, top + 6, smn[2] + 1 + sl * 0.8), "crest", tag="crest")
    if "crest_double" in feats:
        for s in (-1, 1):
            x = s * (sw / 2 - 1)
            _wb(m, "Head", (x - 0.5, top, nmn[2] + 2), (x + 0.5, top + 4, smx[2] - 2), "crest", tag="crest")
    if "crest_small" in feats:
        for s in (-1, 1):
            x = s * (sw / 2 - 1.5)
            _wb(m, "Head", (x - 1, top, eye_z - 1.5), (x + 1, top + 1, eye_z + 1.5), "crest", tag="crest")
    if "crest_head" in feats:
        _wb(m, "Head", (-1, top - 1, smx[2] - 2), (1, top + 2, smx[2] + sl * 0.7), "crest", tag="crest")
        _wb(m, "Head", (-0.5, top + 1, smx[2] + sl * 0.5), (0.5, top + 3, smx[2] + sl * 1.1), "crest", tag="crest")
    if "antlers" in feats:
        for s in (-1, 1):
            x = s * (sw / 2 - 2)
            _wb(m, "Head", (x - 0.5, top, eye_z), (x + 0.5, top + 4, eye_z + 1), "horn", tag="horn")
            _wb(m, "Head", (x - 0.5 + s * 1, top + 3, eye_z), (x + 0.5 + s * 1, top + 4, eye_z + 1), "horn", tag="horn")
            _wb(m, "Head", (x - 0.5 + s * 2, top + 3, eye_z), (x + 0.5 + s * 2, top + 7, eye_z + 1), "horn", tag="horn")
            _wb(m, "Head", (x - 0.5, top + 4, eye_z + 1), (x + 0.5, top + 7, eye_z + 2), "horn", tag="horn")
    if "gem" in feats:
        z = smn[2] + 1
        _wb(m, "Head", (-1, top - 3, z - 1.5), (1, top - 1, z - 0.5), "crystal", tag="crystal")
    if "tusks" in feats:
        jmn, jmx = (np.array(v) for v in m.meta["jaw"])
        jaw_b = m.bones["Jaw"]["pos"]
        for s in (-1, 1):
            x = s * (jmx[0] - 0.5)
            m.box_world("Jaw", (x - 0.5, jmx[1], jmn[2] + 1), (x + 0.5, jmx[1] + 3, jmn[2] + 2), "tooth", tag="tooth")

    # ------------------------------------------------ dorsais
    if "plates" in feats:
        plist = [b for b in spine if b[0].startswith(("Chest", "Hips", "Tail1", "Tail2", "Neck"))]
        total = len(plist)
        for i, (bone, mn, mx) in enumerate(plist):
            L = mx[2] - mn[2]
            n = max(1, int(L // 5))
            for k in range(n):
                z = mn[2] + (k + 0.5) * L / n
                t = (i + (k + 0.5) / n) / total
                hgt = ri(3 + 6 * math.sin(math.pi * min(max(t, 0.05), 0.95)) * P.get("plate_scale", 1.0))
                x = 1.0 if (k + i) % 2 else -1.0
                _wb(m, bone, (x - 1, mx[1] - 1, z - 2), (x + 1, mx[1] + hgt, z + 2), "plate", tag="plate")
    if "sail" in feats:
        slist = [b for b in spine if b[0] in ("Chest", "Hips")]
        z0, z1 = min(b[1][2] for b in slist), max(b[2][2] for b in slist)
        hmax = P.get("sail_h", P["body_h"] * 1.0)
        for bone, mn, mx in slist:
            z = mn[2]
            while z < mx[2] - 0.5:
                z2 = min(z + 3, mx[2])
                t = ((z + z2) / 2 - z0) / (z1 - z0)
                hgt = ri(2 + hmax * math.sin(math.pi * t))
                _wb(m, bone, (-1, mx[1] - 1, z), (1, mx[1] + hgt, z2), "sail", tag="sail")
                z = z2
    if "hump" in feats:
        mn, mx = m.meta["hips"]
        _wb(m, "Hips", (mn[0] * 0.5, mx[1], mn[2] * 0.6), (mx[0] * 0.5, mx[1] + 4, mx[2] * 0.9), "skin", tag="body")
    if "back_spikes" in feats:
        for bone, mn, mx in spine:
            L = mx[2] - mn[2]
            n = max(1, int(L // 4))
            for k in range(n):
                z = mn[2] + (k + 0.5) * L / n
                _wb(m, bone, (-0.5, mx[1], z - 0.5), (0.5, mx[1] + 2, z + 0.5), "horn", tag="horn")
    if "neck_spikes" in feats:
        for i, (mn, mx) in enumerate(m.meta["neck"]):
            for s in (-1, 1):
                _wb(m, "Neck%d" % (i + 1), (s * 1.5 - 0.5, mx[1], (mn[2] + mx[2]) / 2 - 0.5),
                    (s * 1.5 + 0.5, mx[1] + 6, (mn[2] + mx[2]) / 2 + 0.5), "horn", tag="horn")
    if "crystals" in feats:
        for bone, mn, mx in spine:
            if bone.startswith("Neck") and bone != "Neck1":
                continue
            L = mx[2] - mn[2]
            n = max(1, int(L // 6))
            for k in range(n):
                z = mn[2] + (k + 0.5) * L / n
                hgt = 3 + int(rnd.randint(0, 4))
                c = np.array([0, mx[1] + hgt / 2 - 1, z])
                B = m.bones[bone]
                tilt = rx(math.radians(rnd.uniform(-20, 20))) @ rz(math.radians(rnd.uniform(-15, 15)))
                m.box_local(bone, B["R"].T @ (c - B["pos"]), (2, hgt, 2), "crystal", R=B["R"].T @ tilt, tag="crystal")
    if "armor" in feats:
        for bone, mn, mx in spine:
            if bone.startswith("Neck"):
                continue
            w = mx[0] - mn[0]
            L = mx[2] - mn[2]
            nx, nz = max(1, int(w // 5)), max(1, int(L // 5))
            for ix in range(nx):
                for iz in range(nz):
                    x = mn[0] + (ix + 0.5) * w / nx
                    z = mn[2] + (iz + 0.5) * L / nz
                    _wb(m, bone, (x - 1.5, mx[1], z - 1.5), (x + 1.5, mx[1] + 1, z + 1.5), "armor", tag="armor")
    if "side_spikes" in feats:
        for bone, mn, mx in spine:
            if not bone.startswith(("Chest", "Hips", "Tail1")):
                continue
            L = mx[2] - mn[2]
            n = max(1, int(L // 5))
            y = mn[1] + (mx[1] - mn[1]) * 0.55
            for k in range(n):
                z = mn[2] + (k + 0.5) * L / n
                for s in (-1, 1):
                    x0 = mx[0] if s > 0 else mn[0]
                    _wb(m, bone, (min(x0, x0 + s * 3), y - 1, z - 1), (max(x0, x0 + s * 3), y + 1, z + 1), "horn", tag="horn")
    if "mane" in feats:
        for i, (mn, mx) in enumerate(m.meta["neck"]):
            _wb(m, "Neck%d" % (i + 1), (mn[0] - 1, mx[1] - 1, mn[2]), (mx[0] + 1, mx[1] + 2, mx[2]), "feather", tag="feather")
        _wb(m, "Head", (smn[0] + 1, top, smx[2] - 3), (smx[0] - 1, top + 2, smx[2] + 1), "feather", tag="feather")
    if "feathers" in feats:
        _wb(m, "Head", (-1, top, smx[2] - 4), (1, top + 2, smx[2]), "feather", tag="feather")
        _wb(m, "Head", (-0.5, top + 2, smx[2] - 2), (0.5, top + 3, smx[2]), "feather", tag="feather")
        if m.meta["tail"]:
            mn, mx = m.meta["tail"][-1]
            last = "Tail%d" % len(m.meta["tail"])
            _wb(m, last, (mn[0] - 1, mn[1] - 0.5, mx[2] - 3), (mx[0] + 1, mx[1] + 0.5, mx[2] + 3), "feather", tag="feather")
    if "thagomizer" in feats and m.meta["tail"]:
        last = "Tail%d" % len(m.meta["tail"])
        mn, mx = m.meta["tail"][-1]
        B = m.bones[last]
        for k, zf in enumerate((0.35, 0.8)):
            z = mn[2] + (mx[2] - mn[2]) * zf
            for s in (-1, 1):
                c = np.array([s * 2.5, mx[1] + 1.5, z])
                R = rz(math.radians(-s * 50)) @ rx(math.radians(-25))
                m.box_local(last, B["R"].T @ (c - B["pos"]), (1, 7, 1), "horn", R=B["R"].T @ R, tag="horn")
    if "club" in feats and m.meta["tail"]:
        last = "Tail%d" % len(m.meta["tail"])
        mn, mx = (np.array(v) for v in m.meta["tail"][-1])
        w, h = (mx[0] - mn[0]) * 2.6, (mx[1] - mn[1]) * 2.0
        cy = (mn[1] + mx[1]) / 2
        _wb(m, last, (-w / 2, cy - h / 2, mx[2] - 2), (w / 2, cy + h / 2, mx[2] + 5), "club", tag="club")
