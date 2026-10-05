"""Genoma: resolve um spec (parcial) em parâmetros concretos, mede similaridade
e mantém o histórico para não repetir dinossauros."""
import colorsys
import copy
import datetime
import json
import math
import os
import random
import re

from .species import (ARCHETYPES, SPECIES, PALETTES, PATTERNS, EYE_STYLES, SIZE_CLASSES,
                      FANTASY_FEATURES, CLAW_COLORS, MOUTH_COLOR, TOOTH_COLOR, SYLLABLES_A, SYLLABLES_B)

GROUPS = {
    "head": ["skull_len", "skull_h", "skull_w", "snout_len", "snout_h", "snout_w", "jaw_h"],
    "neck": ["neck_len", "neck_w", "neck_h", "neck_rise"],
    "tail": ["tail_len", "tail_w", "tail_h"],
    "legs": ["thigh", "shin", "foot_len"],
    "body": ["hips_len", "chest_len", "body_h", "chest_h"],
    "bulk": ["body_w", "chest_w", "thigh_w", "thigh_d", "shin_w", "foot_w", "neck_w", "tail_w", "front_w", "arm_w"],
    "arms": ["arm", "fore", "hand"],
}


# ---------------------------------------------------------------- cores
def hex2rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def rgb2hex(c):
    return "#%02x%02x%02x" % tuple(max(0, min(255, int(round(v)))) for v in c)


def hsv_shift(hexc, dh=0.0, ds=0.0, dv=0.0):
    r, g, b = (v / 255 for v in hex2rgb(hexc))
    h, s, v = colorsys.rgb_to_hsv(r, g, b)
    h = (h + dh) % 1.0
    s = min(max(s + ds, 0), 1)
    v = min(max(v + dv, 0), 1)
    return rgb2hex([c * 255 for c in colorsys.hsv_to_rgb(h, s, v)])


def hue(hexc):
    r, g, b = (v / 255 for v in hex2rgb(hexc))
    h, s, v = colorsys.rgb_to_hsv(r, g, b)
    return h, s, v


# ---------------------------------------------------------------- resolve
def slug(s):
    s = s.lower()
    for a, b in (("áàâã", "a"), ("éê", "e"), ("í", "i"), ("óôõ", "o"), ("ú", "u"), ("ç", "c")):
        for ch in a:
            s = s.replace(ch, b)
    return re.sub(r"[^a-z0-9]+", "_", s).strip("_")


def random_name(rng, taken):
    for _ in range(200):
        n = rng.choice(SYLLABLES_A) + rng.choice(SYLLABLES_A).lower() + rng.choice(SYLLABLES_B)
        if slug(n) not in taken:
            return n
    return "Dino%d" % rng.randint(1000, 9999)


def resolve(spec, history=None, seed=None):
    """spec (dict parcial) -> genoma completo."""
    spec = copy.deepcopy(spec or {})
    seed = spec.get("seed", seed if seed is not None else random.randrange(1, 2 ** 31))
    rng = random.Random(seed)
    taken = {slug(d["name"]) for d in (history or {}).get("dinos", [])}

    fantasy = bool(spec.get("fantasy", False))
    species = spec.get("species")
    if species and species not in SPECIES:
        raise ValueError("espécie desconhecida: %s (veja `dinomaker species`)" % species)
    if not species and not spec.get("archetype"):
        if fantasy:
            spec["archetype"] = rng.choice(list(ARCHETYPES))
        else:
            species = rng.choice(list(SPECIES))
    if species:
        arch, display, sfeats, sover = SPECIES[species]
    else:
        arch, display, sfeats, sover = spec["archetype"], None, [], {}
    if arch not in ARCHETYPES:
        raise ValueError("arquétipo desconhecido: %s" % arch)

    P = copy.deepcopy(ARCHETYPES[arch])
    base_feats = P.pop("features")
    P.update({k: v for k, v in sover.items()})

    # variação proporcional por grupo
    lo, hi = (0.78, 1.32) if fantasy else (0.86, 1.18)
    var = {g: round(rng.uniform(lo, hi), 3) for g in GROUPS}
    var.update(spec.get("variation", {}))
    chibi = spec.get("chibi", rng.random() < (0.35 if fantasy else 0.15))
    exact = bool(spec.get("exact"))  # vindo do editor: variação/features já são finais
    if chibi and not exact:
        var["head"] = round(var["head"] * 1.25, 3)
        var["legs"] = round(var["legs"] * 0.85, 3)
    for g, keys in GROUPS.items():
        for k in keys:
            if k in P:
                P[k] = round(P[k] * var[g], 2)

    # features
    feats = list(dict.fromkeys(base_feats + [f for f in sfeats if not f.startswith("-")]))
    for f in sfeats:
        if f.startswith("-") and f[1:] in feats:
            feats.remove(f[1:])
    if fantasy and "features" not in spec:
        extra = rng.sample(FANTASY_FEATURES, rng.randint(1, 3))
        feats += [f for f in extra if f not in feats]
    for f in spec.get("features", []):
        if f.startswith("-"):
            if f[1:] in feats:
                feats.remove(f[1:])
        elif f not in feats:
            feats.append(f)
    if exact and "features_exact" in spec:
        feats = list(dict.fromkeys(spec["features_exact"]))
    elif "beak" in feats and "teeth" in feats and "teeth" not in spec.get("features", []):
        feats.remove("teeth")
    if not exact and P["diet"] == "carnivore" and "beak" not in feats and "teeth" not in feats:
        feats.append("teeth")

    P.update(spec.get("params", {}))
    size = spec.get("size", P.pop("size", "medium"))
    P.pop("size", None)
    P["seed"] = seed

    # paleta
    pal = spec.get("palette")
    if isinstance(pal, str):
        palette = dict(PALETTES[pal])
        pal_name = pal
    elif isinstance(pal, dict):
        pal_name = "custom"
        palette = dict(PALETTES[rng.choice(list(PALETTES))])
        palette.update(pal)
    else:
        pal_name = rng.choice(list(PALETTES))
        palette = dict(PALETTES[pal_name])
        dh = rng.uniform(-0.04, 0.04)
        palette = {k: hsv_shift(v, dh=dh) for k, v in palette.items()}
    palette.setdefault("claw", rng.choice(CLAW_COLORS))
    palette.setdefault("mouth", MOUTH_COLOR)
    palette.setdefault("tooth", TOOTH_COLOR)
    palette.setdefault("eye", "#ffd23a" if P["diet"] == "carnivore" else "#ffffff")

    pattern = {"type": rng.choice([p for p in PATTERNS if p not in ("lava", "galaxy")] if not fantasy else PATTERNS),
               "scale": rng.choice([4, 5, 6, 7, 8]), "density": round(rng.uniform(0.4, 0.9), 2)}
    pattern.update(spec.get("pattern", {}))

    eyes = {"style": "fierce" if P["diet"] == "carnivore" and not chibi else "cute",
            "size": int(P.get("eye", 3)) + (1 if chibi else 0)}
    if "glow_eyes" in feats:
        eyes["style"] = "glow"
    eyes.update(spec.get("eyes", {}))
    P["eye"] = eyes["size"]

    name = spec.get("name") or (display if (display and slug(display) not in taken) else random_name(rng, taken))

    return {
        "version": 1,
        "name": name,
        "id": slug(name),
        "species": species or "custom",
        "archetype": arch,
        "fantasy": fantasy,
        "chibi": bool(chibi),
        "seed": seed,
        "size": size,
        "px_size": float(spec["px_size"]) if spec.get("px_size") else SIZE_CLASSES.get(size, size if isinstance(size, (int, float)) else 0.14),
        "palette_name": pal_name,
        "palette": palette,
        "pattern": pattern,
        "eyes": eyes,
        "features": feats,
        "attack": spec.get("attack", P["attack"]),
        "studs": bool(spec.get("studs", False)),
        "variation": var,
        "param_overrides": dict(spec.get("params", {})),
        "params": P,
        "description": spec.get("description", ""),
        "vfx": spec.get("vfx", {}),
    }


# ---------------------------------------------------------------- similaridade
def signature(g):
    P = g["params"]
    body = P["hips_len"] + P["chest_len"]
    return {
        "archetype": g["archetype"],
        "species": g["species"],
        "ratios": [
            P["neck_len"] * P["neck_segs"] / body,
            P["tail_len"] * P["tail_segs"] / body,
            (P["thigh"] + P["shin"]) / P["body_h"],
            (P["skull_len"] + P["snout_len"]) / body,
            P["body_w"] / body,
        ],
        "features": sorted(g["features"]),
        "hues": [hue(g["palette"]["primary"]), hue(g["palette"]["accent"]), hue(g["palette"]["belly"])],
        "pattern": g["pattern"]["type"],
        "eyes": g["eyes"]["style"],
        "size": g["size"],
        "chibi": g.get("chibi", False),
    }


def _hdist(a, b):
    """Distância de cor 0..1 (matiz circular ponderada pela saturação + valor)."""
    dh = abs(a[0] - b[0])
    dh = min(dh, 1 - dh) * 2
    sat = min(a[1], b[1])
    return min(1.0, dh * sat + abs(a[1] - b[1]) * 0.5 + abs(a[2] - b[2]) * 0.5)


def similarity(sa, sb):
    """1.0 = idêntico, 0.0 = nada a ver."""
    d = 0.0
    d += 0.30 * (0.0 if sa["archetype"] == sb["archetype"] else 1.0)
    d += 0.05 * (0.0 if sa["species"] == sb["species"] else 1.0)
    rd = math.sqrt(sum(((x - y) / max(abs(x), abs(y), 0.1)) ** 2 for x, y in zip(sa["ratios"], sb["ratios"])) / len(sa["ratios"]))
    d += 0.15 * min(1.0, rd * 2.5)
    fa, fb = set(sa["features"]), set(sb["features"])
    jac = 1 - (len(fa & fb) / len(fa | fb) if (fa | fb) else 1.0)
    d += 0.20 * jac
    hd = (_hdist(sa["hues"][0], sb["hues"][0]) * 0.6 + _hdist(sa["hues"][1], sb["hues"][1]) * 0.25 +
          _hdist(sa["hues"][2], sb["hues"][2]) * 0.15)
    d += 0.20 * hd
    d += 0.07 * (0.0 if sa["pattern"] == sb["pattern"] else 1.0)
    d += 0.03 * (0.0 if sa["eyes"] == sb["eyes"] else 1.0)
    sim = 1.0 - min(d, 1.0)
    # mesmo corpo + mesma cor principal já parece repetido aos olhos: pesa mais
    if sa["archetype"] == sb["archetype"] and _hdist(sa["hues"][0], sb["hues"][0]) < 0.12:
        sim = min(1.0, sim + 0.08)
    return round(sim, 4)


# ---------------------------------------------------------------- histórico
def load_history(path):
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return {"version": 1, "dinos": []}


def save_history(path, hist):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(hist, f, ensure_ascii=False, indent=1)


def most_similar(g, hist):
    sig = signature(g)
    best = (0.0, None)
    for d in hist.get("dinos", []):
        s = similarity(sig, d["signature"])
        if s > best[0]:
            best = (s, d)
    return best


def check_unique(g, hist, threshold):
    """Retorna (ok, motivo)."""
    if any(d["id"] == g["id"] for d in hist.get("dinos", [])):
        return False, "nome '%s' já existe no histórico" % g["name"]
    s, d = most_similar(g, hist)
    if d is not None and s >= threshold:
        return False, "parecido demais com '%s' (similaridade %.2f >= %.2f)" % (d["name"], s, threshold)
    return True, "ok (mais próximo: %s %.2f)" % (d["name"] if d else "-", s)


def add_to_history(hist, g, out_dir):
    hist.setdefault("dinos", []).append({
        "id": g["id"], "name": g["name"], "species": g["species"], "archetype": g["archetype"],
        "fantasy": g["fantasy"], "palette": g["palette_name"], "pattern": g["pattern"]["type"],
        "features": g["features"], "created": datetime.datetime.now().isoformat(timespec="seconds"),
        "output": out_dir, "signature": signature(g), "genome": g,
    })


def genome_to_spec(g):
    """Genoma -> spec editável (o editor muda campos e chama resolve de novo)."""
    sp = {
        "exact": True, "name": g["name"], "seed": g["seed"], "fantasy": g["fantasy"], "chibi": g.get("chibi", False),
        "size": g["size"], "px_size": g["px_size"], "palette": dict(g["palette"]), "pattern": dict(g["pattern"]),
        "eyes": dict(g["eyes"]), "features_exact": list(g["features"]), "variation": dict(g["variation"]),
        "attack": g["attack"], "vfx": dict(g.get("vfx") or {}), "params": dict(g.get("param_overrides") or {}),
        "description": g.get("description", ""),
    }
    if g["species"] != "custom":
        sp["species"] = g["species"]
    else:
        sp["archetype"] = g["archetype"]
    return sp
