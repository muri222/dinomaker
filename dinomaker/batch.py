"""Gerador em lote: escolhe conceitos únicos (checa histórico) e gera em paralelo."""
import json
import os
import random
from concurrent.futures import ProcessPoolExecutor

from .genome import load_history, save_history, add_to_history, random_name, slug
from .pipeline import unique_genome, generate, ROOT
from .species import ARCHETYPES, SPECIES

REAL = [
    ("Rex Tempestade", "tyrannosaurus", "midnight", "zigzag", ["glow_eyes"], {}),
    ("Rex Bombom", "tyrannosaurus", "candy", "spots", [], {"chibi": True}),
    ("Giga Sombra", "giganotosaurus", "shadow", "dorsal", ["glow_eyes"], {}),
    ("Alo Ferrugem", "allosaurus", "rust", "stripes", [], {}),
    ("Carno Chifrudo", "carnotaurus", "sunset", "tiger", [], {}),
    ("Cerato Pirata", "ceratosaurus", "royal", "bands", [], {}),
    ("Velo Relâmpago", "velociraptor", "gold", "zigzag", [], {}),
    ("Deino Ninja", "deinonychus", "shadow", "stripes", ["glow_eyes"], {}),
    ("Utah Turbo", "utahraptor", "volcano", "dorsal", [], {}),
    ("Dilo Leque", "dilophosaurus", "toxic", "spots", [], {}),
    ("Compy Pipoca", "compsognathus", "gold", "spots", [], {"chibi": True}),
    ("Galimimo Veloz", "gallimimus", "desert", "stripes", [], {}),
    ("Ovi Arco-Íris", "oviraptor", {"primary": "#ff5fa2", "belly": "#fff0f6", "accent": "#5fd0ff", "pattern": "#ffd23a"}, "spots", [], {}),
    ("Teri Garras", "therizinosaurus", "forest", "mottled", [], {}),
    ("Barion Pescador", "baryonyx", "lagoon", "spots", [], {}),
    ("Conca Corcunda", "concavenator", "jungle", "tiger", [], {}),
    ("Diplo Gigante", "diplodocus", "slate", "bands", [], {}),
    ("Amarga Espinhos", "amargasaurus", "sunset", "dorsal", [], {}),
    ("Estira Coroa", "styracosaurus", "gold", "rosettes", [], {}),
    ("Proto Bebê", "protoceratops", "bubblegum", "spots", [], {"chibi": True}),
    ("Sino Rei", "sinoceratops", "royal", "bands", [], {}),
    ("Kentro Espeto", "kentrosaurus", "toxic", "stripes", [], {}),
    ("Coritos Trompete", "corythosaurus", "grape", "spots", [], {}),
    ("Edmonto Pato", "edmontosaurus", "lime", "mottled", [], {}),
    ("Iguano Polegar", "iguanodon", "forest", "stripes", [], {}),
    ("Quetzal Céu", "quetzalcoatlus", "sunset", "zigzag", [], {}),
    ("Dimorfo Bicudo", "dimorphodon", "candy", "spots", [], {}),
    ("Anquilo Martelo", "ankylosaurus", "volcano", "bands", [], {}),
    ("Trici Trovão", "triceratops", "midnight", "zigzag", ["glow_eyes"], {}),
    ("Estego Neve", "stegosaurus", "snow", "spots", [], {}),
    ("Braqui Floresta", "brachiosaurus", "forest", "tiger", [], {}),
    ("Espino Coral", "spinosaurus", "lagoon", "bands", [], {}),
    ("Paqui Bate-Bate", "pachycephalosaurus", "volcano", "stripes", [], {}),
    ("Ptero Algodão", "pteranodon", "candy", "spots", [], {"chibi": True}),
    ("Velo Sereno", "velociraptor", "frost", "spots", [], {}),
    ("Rex Dourado", "tyrannosaurus", "gold", "rosettes", [], {}),
    ("Diplo Bolinha", "diplodocus", "bubblegum", "spots", [], {"chibi": True}),
    ("Galimimo Pôr-do-Sol", "gallimimus", "sunset", "bands", [], {}),
    ("Estira Tóxico", "styracosaurus", "toxic", "mottled", [], {}),
    ("Quetzal Real", "quetzalcoatlus", "royal", "dorsal", [], {}),
]

ARCH = {"theropod": "Rex", "raptor": "Raptor", "spinosaur": "Espino", "sauropod": "Pescoçudo",
        "ceratopsian": "Trici", "stegosaur": "Estego", "ankylosaur": "Anquilo", "hadrosaur": "Hadro",
        "pachycephalosaur": "Cabeçudo", "pterosaur": "Ptero"}

THEMES = {
    "Magma": dict(palette="volcano", pattern={"type": "lava"}, features=["crystals"], eyes={"style": "glow"}, vfx={"theme": "fire"}),
    "Glacial": dict(palette="frost", pattern={"type": "spots"}, features=["crystals"], vfx={"theme": "ice"}),
    "Elétrico": dict(palette={"primary": "#ffd23a", "belly": "#fff6c0", "accent": "#2b2b2b", "pattern": "#2b2b2b"}, pattern={"type": "zigzag"}, features=["glow_eyes"], vfx={"theme": "electric"}),
    "Cósmico": dict(palette="grape", pattern={"type": "galaxy"}, features=["gem", "glow_eyes"], vfx={"theme": "magic"}),
    "Tóxico": dict(palette="toxic", pattern={"type": "mottled"}, features=["back_spikes"], vfx={"theme": "toxic"}),
    "Musgo": dict(palette="forest", pattern={"type": "mottled"}, features=["antlers", "mane"], vfx={"theme": "nature"}),
    "Abissal": dict(palette={"primary": "#13406e", "belly": "#5fd0f0", "accent": "#3effd8", "pattern": "#0a2647"}, pattern={"type": "bands"}, features=["tusks", "glow_eyes"], vfx={"theme": "water"}),
    "Doce": dict(palette="candy", pattern={"type": "spots"}, chibi=True, vfx={"theme": "magic"}),
    "Dourado": dict(palette="gold", pattern={"type": "rosettes"}, features=["gem"], vfx={"theme": "magic"}),
    "Sombrio": dict(palette={"primary": "#3a2a55", "belly": "#8a6ab0", "accent": "#ff3355", "pattern": "#c9a8ff"}, pattern={"type": "dorsal"}, features=["glow_eyes", "back_spikes"], vfx={"theme": "magic"}),
    "Arco-Íris": dict(palette={"primary": "#7a5cff", "belly": "#fff4d6", "accent": "#ff5fa2", "pattern": "#3fe0a0"}, pattern={"type": "stripes"}, chibi=True, vfx={"theme": "magic"}),
    "Zumbi": dict(palette={"primary": "#7a9a6a", "belly": "#b8c8a0", "accent": "#5aff5a", "pattern": "#4a5a40"}, pattern={"type": "mottled"}, features=["glow_eyes"], vfx={"theme": "toxic"}),
}




def candidates(kinds="mix", archetypes=None, themes=None, seed=0):
    """Gera specs candidatos (curados primeiro, depois aleatórios infinitos)."""
    rng = random.Random(seed)
    archs = [a for a in ARCH if not archetypes or a in archetypes]
    ths = [t for t in THEMES if not themes or t in themes]
    if kinds in ("real", "mix"):
        for i, (name, sp, pal, pat, feats, extra) in enumerate(REAL):
            if SPECIES[sp][0] not in archs:
                continue
            s = dict(name=name, species=sp, palette=pal, pattern={"type": pat}, features=feats, seed=5000 + i)
            s.update(extra)
            yield s
    if kinds in ("fantasy", "mix") and ths:
        k = 0
        for r in range(len(ths)):
            for j, a in enumerate(archs):
                t = ths[(j + r) % len(ths)]
                s = dict(name="%s %s" % (ARCH[a], t), archetype=a, fantasy=True, seed=7000 + k)
                s.update(json.loads(json.dumps(THEMES[t])))
                k += 1
                yield s
    # aleatórios (sem fim)
    n = 0
    while True:
        n += 1
        if kinds == "real" or (kinds == "mix" and rng.random() < 0.4):
            pool = [s for s, v in SPECIES.items() if v[0] in archs] or list(SPECIES)
            yield dict(species=rng.choice(pool), seed=20000 + n)
        else:
            a = rng.choice(archs)
            s = dict(archetype=a, fantasy=True, seed=30000 + n)
            if ths and rng.random() < 0.7:
                t = rng.choice(ths)
                s.update(json.loads(json.dumps(THEMES[t])))
            yield s


def _build_one(args):
    g, out_root, hist_path = args
    try:
        generate({}, out_root, hist_path, genome=g, update_history=False, log=lambda *a: None)
        return g["id"], None
    except Exception as e:  # noqa: BLE001
        return g["id"], str(e)[-500:]


def run_batch(count, history_path, out_root=None, kinds="mix", archetypes=None, themes=None,
              threshold=0.82, workers=4, name="Lote", progress=print, max_candidates=3000):
    """Gera `count` dinos NOVOS e únicos. Retorna lista de ids gerados."""
    out_root = out_root or os.path.join(ROOT, "output")
    hist = load_history(history_path)
    spec_dir = os.path.join(ROOT, "specs", slug(name))
    os.makedirs(spec_dir, exist_ok=True)
    chosen, tried = [], 0
    for spec in candidates(kinds, archetypes, themes, seed=len(hist["dinos"])):
        if len(chosen) >= count or tried >= max_candidates:
            break
        tried += 1
        try:
            g, _ = unique_genome(spec, hist, threshold, max_tries=4)
        except (RuntimeError, ValueError):
            continue
        add_to_history(hist, g, os.path.relpath(os.path.join(out_root, g["id"]), ROOT))
        chosen.append(g)
        with open(os.path.join(spec_dir, g["id"] + ".json"), "w", encoding="utf-8") as f:
            json.dump(spec, f, ensure_ascii=False, indent=1)
    progress({"stage": "conceitos", "chosen": len(chosen), "tried": tried})
    errors, done = [], []
    with ProcessPoolExecutor(workers) as ex:
        for i, (gid, err) in enumerate(ex.map(_build_one, [(g, out_root, history_path) for g in chosen])):
            (errors if err else done).append(gid)
            progress({"stage": "gerando", "done": i + 1, "total": len(chosen), "id": gid, "error": err})
    if errors:
        hist["dinos"] = [d for d in hist["dinos"] if d["id"] not in errors]
    save_history(history_path, hist)
    return done
