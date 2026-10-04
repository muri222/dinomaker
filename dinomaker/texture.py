"""Textura pixel art procedural.

Cada face de cada caixa recebe uma grade de pixels (1 px = 1 unidade do modelo).
- Versão B (mesh): grades empacotadas num atlas + mapas PBR (SurfaceAppearance).
- Versão A (Parts): a grade "limpa" (sem ruído) vira placas finas de cor.
"""
import math
import numpy as np

from .mathx import hash01, vnoise
from .genome import hex2rgb

# n, v (u = v x n)
FACES = {
    "+X": ((1, 0, 0), (0, 1, 0)),
    "-X": ((-1, 0, 0), (0, 1, 0)),
    "+Z": ((0, 0, 1), (0, 1, 0)),
    "-Z": ((0, 0, -1), (0, 1, 0)),
    "+Y": ((0, 1, 0), (0, 0, -1)),
    "-Y": ((0, -1, 0), (0, 0, 1)),
}

ROUGH = {"skin": 0.78, "mouth": 0.55, "tooth": 0.4, "claw": 0.45, "horn": 0.5, "eye": 0.12,
         "crystal": 0.15, "glow": 0.3, "frill": 0.7, "sail": 0.7, "plate": 0.65, "crest": 0.65, "feather": 0.85,
         "dome": 0.55, "club": 0.6, "armor": 0.6, "beak": 0.45, "wing": 0.8, "nostril": 0.8}


def face_frame(box, fname):
    n, v = (np.array(a, float) for a in FACES[fname])
    u = np.cross(v, n)
    s = box["size"]
    w = int(round(abs(s @ u)))
    h = int(round(abs(s @ v)))
    o = n * abs(s @ n) / 2 - u * w / 2 - v * h / 2
    return n, u, v, w, h, o


def _mix(a, b, t):
    return tuple(a[i] + (b[i] - a[i]) * t for i in range(3))


def _mul(a, f):
    return tuple(min(255.0, a[i] * f) for i in range(3))


class Painter:
    def __init__(self, model, genome, crisp=False):
        self.crisp = crisp
        self.m = model
        self.g = genome
        pal = genome["palette"]
        self.C = {k: tuple(float(x) for x in hex2rgb(v)) for k, v in pal.items()}
        self.pat = genome["pattern"]
        self.seed = int(genome["seed"]) % 100000
        self.eyes = genome["eyes"]
        self.light_accent = _mix(self.C["accent"], (255, 255, 255), 0.35)
        self.dark_accent = _mul(self.C["accent"], 0.7)
        self.horn = _mix(self.C["claw"], (255, 255, 255), 0.15)
        # cor de "brilho" (lava, cristais): a mais viva entre acento/padrão/barriga
        import colorsys
        def vivid(c):
            h, s_, v = colorsys.rgb_to_hsv(*(x / 255.0 for x in c))
            return s_ * v + v * 0.3
        self.glow = max((self.C["accent"], self.C["pattern"], self.C["belly"]), key=vivid)

    # -------------------------------------------------------- padrão no mundo
    def pattern_hit(self, p, up):
        t = self.pat["type"]
        sc = float(self.pat.get("scale", 6))
        den = float(self.pat.get("density", 0.6))
        x, y, z = p
        s = self.seed
        if t == "none":
            return None
        if t in ("spots", "rosettes"):
            cx, cy, cz = math.floor(x / sc), math.floor(y / sc), math.floor(z / sc)
            for ix in (cx - 1, cx, cx + 1):
                for iy in (cy - 1, cy, cy + 1):
                    for iz in (cz - 1, cz, cz + 1):
                        if hash01(s, ix, iy, iz, 7) > den:
                            continue
                        px = (ix + 0.2 + 0.6 * hash01(s, ix, iy, iz, 1)) * sc
                        py = (iy + 0.2 + 0.6 * hash01(s, ix, iy, iz, 2)) * sc
                        pz = (iz + 0.2 + 0.6 * hash01(s, ix, iy, iz, 3)) * sc
                        r = sc * (0.22 + 0.2 * hash01(s, ix, iy, iz, 4))
                        d = max(abs(x - px), abs(y - py), abs(z - pz))
                        if t == "spots" and d < r:
                            return "pattern"
                        if t == "rosettes" and r * 0.45 < d < r + 0.5:
                            return "pattern"
            return None
        if t == "stripes":
            if not up:
                return None
            w = sc * 0.45 * den + 0.5
            zz = z + 2.0 * (vnoise(x, y, 0, 6, s) - 0.5) * 3
            return "pattern" if (zz % sc) < w else None
        if t == "tiger":
            if not up:
                return None
            zz = z + (vnoise(x, y * 0.5, z, 5, s) - 0.5) * 6
            w = (sc * 0.4) * (0.4 + 0.6 * min(1, max(0, (y % 40) / 40)))
            return "pattern" if (zz % (sc * 1.2)) < max(1.0, w * den * 1.5) else None
        if t == "dorsal":
            return "pattern" if (abs(x) < sc * 0.35 and up) else None
        if t == "bands":
            return "pattern" if (z % (sc * 1.5)) < sc * 0.5 * den + 0.5 else None
        if t == "mottled":
            return "pattern" if vnoise(x, y, z, sc * 0.8, s) > 1 - den * 0.55 else None
        if t == "lava":
            n = vnoise(x, y, z, sc * 1.2, s)
            return "glow" if abs(n - 0.5) < 0.035 + 0.04 * den else None
        if t == "zigzag":
            tri = abs(((z / sc) % 2) - 1) * sc * 0.8
            return "pattern" if abs((y % 30) - (12 + tri)) < 1.0 + den else None
        if t == "galaxy":
            if hash01(s, int(x * 2), int(y * 2), int(z * 2), 9) > 0.985:
                return "star"
            return "pattern" if vnoise(x, y, z, sc, s) > 0.62 else None
        return None

    # -------------------------------------------------------- cor de um pixel
    def pixel(self, box, fname, q, pw, boxinfo, ij, wh):
        """q: posição no local do osso; pw: posição no mundo (descanso).
        Retorna (cor_limpa, fator_ruido, papel)."""
        role = box["role"]
        for z in box["zones"]:
            if "faces" in z and fname not in z["faces"]:
                continue
            ok = True
            for ax, k in (("x", 0), ("y", 1), ("z", 2)):
                if ax in z and not (z[ax][0] <= q[k] <= z[ax][1]):
                    ok = False
            if ok:
                role = z["role"]
                break
        if fname in box["face_roles"]:
            role = box["face_roles"][fname]

        for d in box["decals"]:
            if fname not in d["faces"]:
                continue
            dp = np.array(d["pos"])
            hs = d["size"] / 2.0
            if d["kind"] == "eye":
                dy, dz = q[1] - dp[1], q[2] - dp[2]
                if abs(dy) < hs and abs(dz) < hs:
                    return self.eye_px(dy, dz, hs), 1.0, "eye"
                if self.eyes["style"] == "fierce" and abs(dz) < hs + 1 and hs <= dy < hs + 1:
                    return _mul(self.C["primary"], 0.55), 1.0, "skin"
            elif d["kind"] == "nostril":
                if abs(q[0] - dp[0]) < 0.5 and abs(q[2] - dp[2]) < 0.5:
                    return _mul(self.C["primary"], 0.35), 1.0, "nostril"

        C = self.C
        if role == "skin":
            col = C["primary"]
            ymin, ymax = boxinfo
            tag = box["tag"]
            belly = False
            if tag in ("body", "neck", "tail", "head"):
                rel = (pw[1] - ymin) / max(ymax - ymin, 1)
                thr = 0.3 if self.crisp else 0.3 + (hash01(self.seed, int(pw[0]), int(pw[2]), 3) - 0.5) * 0.12
                if fname == "-Y" or (fname not in ("+Y",) and rel < thr):
                    belly = True
            if belly:
                col = C["belly"]
            else:
                hit = self.pattern_hit(pw, fname != "-Y")
                if hit == "pattern":
                    col = C["pattern"]
                elif hit == "glow":
                    return self.glow, 1.0, "glow"
                elif hit == "star":
                    col = (255.0, 255.0, 240.0)
            if tag == "foot" and fname == "-Y":
                col = _mul(col, 0.8)
            return col, None, "skin"
        if role == "mouth":
            return C["mouth"], None, "mouth"
        if role == "tooth":
            return C["tooth"], None, "tooth"
        if role in ("claw",):
            return C["claw"], None, "claw"
        if role == "horn":
            ymin, ymax = boxinfo
            rel = (pw[1] - ymin) / max(ymax - ymin, 1)
            return (_mul(self.horn, 0.85) if rel < 0.3 else self.horn), None, "horn"
        if role == "beak":
            return _mix(_mix(C["claw"], (70.0, 60.0, 55.0), 0.45), C["primary"], 0.2), None, "beak"
        if role in ("frill", "crest", "sail", "plate", "feather", "wing"):
            i, j = ij
            w, h = wh
            edge = min(i, j, w - 1 - i, h - 1 - j)
            if role == "frill":
                if edge == 0:
                    return self.dark_accent, None, role
                if self.pattern_hit(pw * 1.3 + 50, True) == "pattern" or (i + j) % 7 == 0 and edge == 2:
                    return C["pattern"] if self.pat["type"] != "none" else self.light_accent, None, role
                return C["accent"], None, role
            if role in ("sail", "plate"):
                ymin, ymax = boxinfo
                rel = (pw[1] - ymin) / max(ymax - ymin, 1)
                if role == "sail" and int(pw[2]) % 6 in (0, 1) and rel > 0.15:
                    return self.dark_accent, None, role
                if rel > 0.75:
                    return self.light_accent, None, role
                if rel < 0.2:
                    return _mix(C["accent"], C["primary"], 0.5), None, role
                return C["accent"], None, role
            if role == "wing":
                rel = j / max(h - 1, 1)
                if (i % 5) == 0:
                    return _mul(C["primary"], 0.8), None, role
                return (_mix(C["accent"], C["belly"], 0.3) if rel < 0.5 else C["accent"]), None, role
            if role == "feather":
                return (self.light_accent if (i + 2 * j) % 5 == 0 else C["accent"]), None, role
            return (self.light_accent if edge == 0 else C["accent"]), None, role
        if role == "crystal":
            i, j = ij
            return (_mix(self.glow, (255, 255, 255), 0.6) if (i + j) % 4 == 0 else self.glow), 1.0, "crystal"
        if role == "dome":
            ymin, ymax = boxinfo
            rel = (pw[1] - ymin) / max(ymax - ymin, 1)
            base = _mix(C["primary"], C["belly"], 0.35)
            if rel > 0.6:
                return _mix(base, (255.0, 255.0, 255.0), 0.25), None, "dome"
            return base, None, "dome"
        if role == "club":
            return (_mul(C["pattern"], 0.9) if (int(pw[0] / 2) + int(pw[2] / 2)) % 2 else C["pattern"]), None, "club"
        if role == "armor":
            return C["pattern"], None, "armor"
        return C["primary"], None, "skin"

    def eye_px(self, dy, dz, hs):
        st = self.eyes["style"]
        C = self.C
        n = int(round(hs * 2))
        # índices inteiros dentro do olho: a = coluna (frente->trás), b = linha (cima->baixo)
        a = int(math.floor(dz + hs))
        b = int(math.floor(hs - dy))
        if st == "glow":
            return (255.0, 255.0, 255.0) if (a == n // 2 and b == n // 2) else C["eye"]
        if st == "fierce":
            if a == n // 2 or (n % 2 == 0 and a == n // 2 - 1 and n > 3):
                return (20.0, 16.0, 16.0)
            return C["eye"]
        # cute: preto com brilho branco no canto superior frontal
        if b == 0 and a == 0:
            return (255.0, 255.0, 255.0)
        if n >= 4 and ((b == 1 and a == 0) or (b == 0 and a == 1)):
            return (255.0, 255.0, 255.0)
        return (24.0, 20.0, 28.0)


# ================================================================ rasterização
def paint_faces(model, genome, crisp=False):
    """Para cada caixa e face: grade limpa (h,w,3), fator de ruído e papéis.
    crisp=True: sem pontilhado na barriga (menos placas na versão A)."""
    pt = Painter(model, genome, crisp)
    out = []
    s = pt.seed
    for bi, box in enumerate(model.boxes):
        B = model.bones[box["bone"]]
        c_w, R_w = model.box_world_frame(box)
        half = box["size"] / 2
        ys = [(c_w + R_w @ (half * np.array([sx, sy, sz])))[1] for sx in (-1, 1) for sy in (-1, 1) for sz in (-1, 1)]
        info = (min(ys), max(ys))
        for fname in FACES:
            n, u, v, w, h, o = face_frame(box, fname)
            if w <= 0 or h <= 0:
                continue
            clean = np.zeros((h, w, 3), np.float32)
            noise = np.ones((h, w), np.float32)
            roles = np.empty((h, w), object)
            for j in range(h):
                for i in range(w):
                    p = o + u * (i + 0.5) + v * (j + 0.5)
                    q = box["c"] + box["R"] @ p
                    pw = B["pos"] + B["R"] @ q
                    col, nz, role = pt.pixel(box, fname, q, pw, info, (i, j), (w, h))
                    clean[j, i] = col
                    roles[j, i] = role
                    if nz is None:
                        f = 1.0 + (vnoise(pw[0], pw[1], pw[2], 2.5, s) - 0.5) * 0.16
                        f *= 0.95 + 0.1 * hash01(s, int(math.floor(pw[0] * 2)), int(math.floor(pw[1] * 2)), int(math.floor(pw[2] * 2)))
                        noise[j, i] = f
            out.append(dict(box=bi, face=fname, w=w, h=h, n=n, u=u, v=v, o=o, clean=clean, noise=noise, roles=roles))
    return out


# ================================================================ atlas (B)
def pack(faces, pad=1):
    order = sorted(range(len(faces)), key=lambda k: (-faces[k]["h"], -faces[k]["w"]))
    area = sum((f["w"] + 2 * pad) * (f["h"] + 2 * pad) for f in faces)
    W = 32
    while W * W < area * 1.25:
        W *= 2
    while True:
        x = y = rowh = 0
        ok = True
        for k in order:
            f = faces[k]
            fw, fh = f["w"] + 2 * pad, f["h"] + 2 * pad
            if fw > W:
                ok = False
                break
            if x + fw > W:
                x, y, rowh = 0, y + rowh, 0
            f["rect"] = (x + pad, y + pad)
            x += fw
            rowh = max(rowh, fh)
        Hh = y + rowh
        if ok and Hh <= W:
            H = 32
            while H < Hh:
                H *= 2
            return W, H
        W *= 2


def build_atlas(faces, genome, max_px=1024, studs=False):
    from PIL import Image

    W, H = pack(faces)
    k = max(1, min(16, max_px // max(W, H)))
    alb = np.zeros((H, W, 3), np.float32)
    rough = np.zeros((H, W), np.float32)
    filled = np.zeros((H, W), bool)
    for f in faces:
        x0, y0 = f["rect"]
        col = f["clean"] * f["noise"][..., None]
        r = np.vectorize(lambda rr: ROUGH.get(rr, 0.7))(f["roles"]).astype(np.float32)
        # coordenadas com origem embaixo-esquerda -> linhas da imagem invertidas no fim
        alb[y0:y0 + f["h"], x0:x0 + f["w"]] = col
        rough[y0:y0 + f["h"], x0:x0 + f["w"]] = r
        filled[y0:y0 + f["h"], x0:x0 + f["w"]] = True
        # padding: replica bordas
        for dst, src in ((y0 - 1, y0), (y0 + f["h"], y0 + f["h"] - 1)):
            if 0 <= dst < H:
                alb[dst, x0:x0 + f["w"]] = alb[src, x0:x0 + f["w"]]
                rough[dst, x0:x0 + f["w"]] = rough[src, x0:x0 + f["w"]]
        for dst, src in ((x0 - 1, x0), (x0 + f["w"], x0 + f["w"] - 1)):
            if 0 <= dst < W:
                alb[max(y0 - 1, 0):y0 + f["h"] + 1, dst] = alb[max(y0 - 1, 0):y0 + f["h"] + 1, src]
                rough[max(y0 - 1, 0):y0 + f["h"] + 1, dst] = rough[max(y0 - 1, 0):y0 + f["h"] + 1, src]

    # upscale nearest (mantém o pixel nítido mesmo com filtro bilinear do Roblox)
    A = np.repeat(np.repeat(alb, k, 0), k, 1)
    Rg = np.repeat(np.repeat(rough, k, 0), k, 1)

    # normal map: bisel nas bordas de cada face (+ studs opcionais)
    N = np.zeros((H * k, W * k, 3), np.float32)
    N[..., 2] = 1.0
    bev = max(1, k // 3)
    for f in faces:
        x0, y0 = f["rect"]
        X0, Y0, FW, FH = x0 * k, y0 * k, f["w"] * k, f["h"] * k
        yy, xx = np.mgrid[0:FH, 0:FW]
        nx = np.where(xx < bev, -0.55, np.where(xx >= FW - bev, 0.55, 0.0))
        ny = np.where(yy < bev, -0.55, np.where(yy >= FH - bev, 0.55, 0.0))
        if studs:
            cs = 4 * k
            cx = (xx % cs) - cs / 2 + 0.5
            cy = (yy % cs) - cs / 2 + 0.5
            rr = np.sqrt(cx ** 2 + cy ** 2)
            R0 = cs * 0.32
            ring = (rr < R0) & (rr > R0 - max(1, k * 0.4))
            nx = np.where(ring & (nx == 0), cx / np.maximum(rr, 1e-3) * 0.5, nx)
            ny = np.where(ring & (ny == 0), cy / np.maximum(rr, 1e-3) * 0.5, ny)
        N[Y0:Y0 + FH, X0:X0 + FW, 0] = nx
        N[Y0:Y0 + FH, X0:X0 + FW, 1] = ny
    N /= np.linalg.norm(N, axis=2, keepdims=True)
    Nimg = ((N * 0.5 + 0.5) * 255).astype(np.uint8)

    def save(arr):
        return Image.fromarray(np.flipud(arr))

    imgs = {
        "albedo": save(np.clip(A, 0, 255).astype(np.uint8)),
        "normal": save(Nimg),
        "roughness": save((np.clip(Rg, 0, 1) * 255).astype(np.uint8)),
        "metalness": save(np.zeros((H * k, W * k), np.uint8)),
    }
    return imgs, (W, H, k)


# ================================================================ placas (A)
def face_plates(face, min_area=1):
    """Retângulos de cor (fora a cor dominante) a partir da grade limpa."""
    g = np.round(face["clean"]).astype(np.int32)
    h, w = g.shape[:2]
    keys = g[..., 0] * 65536 + g[..., 1] * 256 + g[..., 2]
    vals, counts = np.unique(keys, return_counts=True)
    base = int(vals[np.argmax(counts)])
    used = keys == base
    rects = []
    for j in range(h):
        i = 0
        while i < w:
            if used[j, i]:
                i += 1
                continue
            kk = keys[j, i]
            i1 = i
            while i1 + 1 < w and not used[j, i1 + 1] and keys[j, i1 + 1] == kk:
                i1 += 1
            j1 = j
            while j1 + 1 < h and all((not used[j1 + 1, t]) and keys[j1 + 1, t] == kk for t in range(i, i1 + 1)):
                j1 += 1
            used[j:j1 + 1, i:i1 + 1] = True
            if (i1 - i + 1) * (j1 - j + 1) >= min_area:
                rects.append((i, j, i1 - i + 1, j1 - j + 1, int(kk), face["roles"][j, i]))
            i = i1 + 1
    return base, int(counts.max()), rects


def key2rgb(k):
    return ((k >> 16) & 255, (k >> 8) & 255, k & 255)
