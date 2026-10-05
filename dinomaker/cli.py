"""CLI: python -m dinomaker <comando>"""
import argparse
import json
import os
import sys

from .genome import load_history, save_history, resolve, most_similar
from .species import SPECIES, ARCHETYPES, PALETTES, PATTERNS, ALL_FEATURES, SIZE_CLASSES
from .pipeline import generate, ROOT

DEFAULT_HISTORY = os.path.join(ROOT, "history", "history.json")
DEFAULT_OUT = os.path.join(ROOT, "output")


def main(argv=None):
    ap = argparse.ArgumentParser(prog="dinomaker", description="Gerador de dinossauros estilo Roblox")
    ap.add_argument("--history", default=DEFAULT_HISTORY)
    sub = ap.add_subparsers(dest="cmd", required=True)

    n = sub.add_parser("new", help="gera dino(s) novo(s)")
    n.add_argument("--spec", help="arquivo JSON com o spec (parcial)")
    n.add_argument("--species", choices=sorted(SPECIES))
    n.add_argument("--archetype", choices=sorted(ARCHETYPES))
    n.add_argument("--fantasy", action="store_true")
    n.add_argument("--chibi", action="store_true", help="cabeça/olhos maiores (fofo)")
    n.add_argument("--name")
    n.add_argument("--palette", choices=sorted(PALETTES))
    n.add_argument("--pattern", choices=PATTERNS)
    n.add_argument("--size", choices=sorted(SIZE_CLASSES))
    n.add_argument("--features", help="lista separada por vírgula (use -feature para remover)")
    n.add_argument("--studs", action="store_true", help="superfície com studs estilo LEGO")
    n.add_argument("--seed", type=int)
    n.add_argument("--count", type=int, default=1)
    n.add_argument("--formats", default="A,B")
    n.add_argument("--detail", choices=["high", "medium", "low", "none"], default="medium", help="placas pixel art na versão A")
    n.add_argument("--no-preview", action="store_true")
    n.add_argument("--threshold", type=float, default=0.82, help="similaridade máxima aceita (0-1)")
    n.add_argument("--out", default=DEFAULT_OUT)
    n.add_argument("--dry-run", action="store_true", help="só resolve o genoma e checa unicidade")

    sub.add_parser("list", help="lista o histórico")
    sub.add_parser("species", help="lista espécies, arquétipos, paletas, padrões e features")
    c = sub.add_parser("check", help="checa um spec contra o histórico sem gerar")
    c.add_argument("spec")
    rb = sub.add_parser("rebuild", help="regera dino(s) existentes com a versão atual do gerador")
    rb.add_argument("ids", nargs="*", help="ids (vazio = todos os não-legados)")
    rb.add_argument("--vfx", help="força um tema de VFX: fire, ice, electric, magic, toxic, nature, none")
    rb.add_argument("--formats", default="A,B")
    rb.add_argument("--detail", choices=["high", "medium", "low", "none"], default="medium")
    rb.add_argument("--no-preview", action="store_true")
    rb.add_argument("--out", default=DEFAULT_OUT)
    pk = sub.add_parser("pack", help="junta os DinoKits de vários dinos num arquivo só + gera o plugin do Studio")
    pk.add_argument("ids", nargs="*", help="ids (vazio = todos os não-legados)")
    pk.add_argument("--name", default="Lote")
    pk.add_argument("--out", default=DEFAULT_OUT)
    pn = sub.add_parser("painel", help="abre o painel de criação/edição no navegador")
    pn.add_argument("--port", type=int, default=8765)
    pn.add_argument("--no-browser", action="store_true")
    r = sub.add_parser("forget", help="remove um dino do histórico")
    r.add_argument("id")

    a = ap.parse_args(argv)

    if a.cmd == "species":
        print("Espécies:", ", ".join(sorted(SPECIES)))
        print("Arquétipos:", ", ".join(sorted(ARCHETYPES)))
        print("Paletas:", ", ".join(sorted(PALETTES)))
        print("Padrões:", ", ".join(PATTERNS))
        print("Features:", ", ".join(ALL_FEATURES))
        print("Tamanhos:", ", ".join("%s=%.2f" % kv for kv in SIZE_CLASSES.items()))
        return 0

    if a.cmd == "list":
        h = load_history(a.history)
        for d in h["dinos"]:
            print("%-28s %-18s %-16s %-9s %-9s %s" % (d["id"], d["species"], d["archetype"], d["palette"], d["pattern"], ",".join(d["features"])))
        print("total:", len(h["dinos"]))
        return 0

    if a.cmd == "rebuild":
        h = load_history(a.history)
        todo = [d for d in h["dinos"] if not d.get("legacy") and (not a.ids or d["id"] in a.ids)]
        for d in todo:
            g = d.get("genome")
            gp = os.path.join(a.out, d["id"], "genome.json")
            if g is None and os.path.exists(gp):
                with open(gp, encoding="utf-8") as f:
                    g = json.load(f)
            if g is None:
                print("sem genoma salvo para", d["id"])
                continue
            spec = {"vfx": {"theme": a.vfx}} if a.vfx else {}
            generate(spec, a.out, a.history, formats=tuple(x.strip().upper() for x in a.formats.split(",")),
                     previews=not a.no_preview, detail=a.detail, genome=g)
        return 0

    if a.cmd == "pack":
        from .pipeline import pack_kits
        h = load_history(a.history)
        todo = [d for d in h["dinos"] if not d.get("legacy") and d.get("genome") and (not a.ids or d["id"] in a.ids)]
        pack_kits([d["genome"] for d in todo], a.out, a.name)
        return 0

    if a.cmd == "painel":
        from .server import serve
        serve(a.port, open_browser=not a.no_browser, history=a.history)
        return 0

    if a.cmd == "forget":
        h = load_history(a.history)
        before = len(h["dinos"])
        h["dinos"] = [d for d in h["dinos"] if d["id"] != a.id]
        save_history(a.history, h)
        print("removidos:", before - len(h["dinos"]))
        return 0

    if a.cmd == "check":
        with open(a.spec, encoding="utf-8") as f:
            spec = json.load(f)
        h = load_history(a.history)
        g = resolve(spec, h)
        s, d = most_similar(g, h)
        print("%s -> mais parecido: %s (%.2f)" % (g["name"], d["name"] if d else "-", s))
        return 0

    spec = {}
    if a.spec:
        with open(a.spec, encoding="utf-8") as f:
            spec = json.load(f)
    for k in ("species", "archetype", "name", "palette", "size", "seed"):
        v = getattr(a, k)
        if v is not None:
            spec[k] = v
    if a.fantasy:
        spec["fantasy"] = True
    if a.chibi:
        spec["chibi"] = True
    if a.studs:
        spec["studs"] = True
    if a.pattern:
        spec.setdefault("pattern", {})["type"] = a.pattern
    if a.features:
        spec["features"] = [f.strip() for f in a.features.split(",") if f.strip()]
    formats = tuple(x.strip().upper() for x in a.formats.split(","))
    for i in range(a.count):
        sp = dict(spec)
        if a.count > 1 and "name" in sp:
            sp["name"] = "%s %d" % (sp["name"], i + 1)
        if a.count > 1 and "seed" in sp:
            sp["seed"] = sp["seed"] + i * 1000
        generate(sp, a.out, a.history, threshold=a.threshold, formats=formats,
                 previews=not a.no_preview, detail=a.detail, dry_run=a.dry_run)
    return 0


if __name__ == "__main__":
    sys.exit(main())
