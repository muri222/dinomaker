"""Monta um lote grande: escolhe conceitos únicos (checa histórico), grava os specs e
gera os dinos em paralelo. Uso:
  python tools/make_batch.py --total 100 --name Lote2 [--workers 4]
"""
import argparse
import json
import os
import sys
from concurrent.futures import ProcessPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dinomaker.genome import load_history, save_history, add_to_history  # noqa: E402
from dinomaker.pipeline import unique_genome, generate, ROOT  # noqa: E402
from dinomaker.cli import DEFAULT_HISTORY, DEFAULT_OUT  # noqa: E402

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
    "Sombrio": dict(palette="shadow", pattern={"type": "dorsal"}, features=["glow_eyes", "back_spikes"], vfx={"theme": "magic"}),
    "Arco-Íris": dict(palette={"primary": "#7a5cff", "belly": "#fff4d6", "accent": "#ff5fa2", "pattern": "#3fe0a0"}, pattern={"type": "stripes"}, chibi=True, vfx={"theme": "magic"}),
    "Zumbi": dict(palette={"primary": "#7a9a6a", "belly": "#b8c8a0", "accent": "#5aff5a", "pattern": "#4a5a40"}, pattern={"type": "mottled"}, features=["glow_eyes"], vfx={"theme": "toxic"}),
}


def candidates():
    out = []
    for i, (name, sp, pal, pat, feats, extra) in enumerate(REAL):
        s = dict(name=name, species=sp, palette=pal, pattern={"type": pat}, features=feats, seed=5000 + i)
        s.update(extra)
        out.append(s)
    # fantasia: percorre temas x arquétipos intercalando para variar
    archs = list(ARCH)
    themes = list(THEMES)
    k = 0
    for r in range(len(themes)):
        for j, a in enumerate(archs):
            t = themes[(j + r) % len(themes)]
            s = dict(name="%s %s" % (ARCH[a], t), archetype=a, fantasy=True, seed=7000 + k)
            s.update(json.loads(json.dumps(THEMES[t])))
            out.append(s)
            k += 1
    return out


def build_one(args):
    g, out_root = args
    try:
        generate({}, out_root, DEFAULT_HISTORY, genome=g, update_history=False, log=lambda *a: None)
        return g["id"], None
    except Exception as e:  # noqa: BLE001
        return g["id"], str(e)[-500:]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--total", type=int, default=100)
    ap.add_argument("--name", default="Lote2")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--threshold", type=float, default=0.82)
    a = ap.parse_args()

    hist = load_history(DEFAULT_HISTORY)
    have = [d for d in hist["dinos"] if not d.get("legacy")]
    need = a.total - len(have)
    spec_dir = os.path.join(ROOT, "specs", a.name.lower())
    os.makedirs(spec_dir, exist_ok=True)
    chosen, skipped = [], []
    for spec in candidates():
        if len(chosen) >= need:
            break
        try:
            g, why = unique_genome(spec, hist, a.threshold, max_tries=6)
        except RuntimeError as e:
            skipped.append((spec["name"], str(e).splitlines()[-1].strip()))
            continue
        add_to_history(hist, g, os.path.join("output", g["id"]))
        chosen.append(g)
        with open(os.path.join(spec_dir, g["id"] + ".json"), "w", encoding="utf-8") as f:
            json.dump(spec, f, ensure_ascii=False, indent=1)
    print("escolhidos:", len(chosen), "| pulados:", len(skipped))
    for n, why in skipped:
        print("  pulado:", n, "->", why)

    out_root = os.path.join(ROOT, "output")
    errors = []
    with ProcessPoolExecutor(a.workers) as ex:
        for i, (gid, err) in enumerate(ex.map(build_one, [(g, out_root) for g in chosen])):
            print("[%d/%d] %s %s" % (i + 1, len(chosen), gid, "OK" if not err else "ERRO " + err), flush=True)
            if err:
                errors.append(gid)
    if errors:
        hist["dinos"] = [d for d in hist["dinos"] if d["id"] not in errors]
    save_history(DEFAULT_HISTORY, hist)
    print("total no histórico (sem legados):", len([d for d in hist["dinos"] if not d.get("legacy")]))


if __name__ == "__main__":
    main()
