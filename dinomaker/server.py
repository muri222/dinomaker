"""Painel DinoMaker: servidor local (só stdlib) + interface web em dinomaker/ui.

  python -m dinomaker painel        -> abre http://localhost:8765
"""
import base64
import io
import json
import os
import shutil
import tempfile
import threading
import time
import traceback
import uuid
import webbrowser
import zipfile
from concurrent.futures import ThreadPoolExecutor
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, unquote

import numpy as np

from .anims import bake
from .batch import run_batch, THEMES, ARCH
from .genome import (load_history, save_history, resolve, genome_to_spec, most_similar, check_unique,
                     signature, similarity, slug)
from .model import build_model
from .pipeline import generate, pack_kits, ROOT
from .species import (ARCHETYPES, SPECIES, PALETTES, PATTERNS, EYE_STYLES, SIZE_CLASSES, ALL_FEATURES,
                      CLAW_COLORS, PARAM_SPEC, INT_PARAMS, FEATURE_GROUPS)
from .texture import paint_faces, build_atlas, FACES, Painter
from .vfx import THEMES as VFX_THEMES, VFX_DEFAULTS, effective_vfx

UI = os.path.join(os.path.dirname(__file__), "ui")
OUT = os.path.join(ROOT, "output")
LIBDIR = os.path.join(ROOT, "library")
EXPORTS = os.path.join(ROOT, "exportados")
LOCK = threading.Lock()
JOBS = {}
POOL = ThreadPoolExecutor(2)


class Ctx:
    history = os.path.join(ROOT, "history", "history.json")
    threshold = 0.82


# ---------------------------------------------------------------- helpers
def hist_without(exclude):
    h = load_history(Ctx.history)
    if exclude:
        h = dict(h, dinos=[d for d in h["dinos"] if d["id"] != exclude])
    return h


def originality(g, exclude=None):
    h = hist_without(exclude)
    s, d = most_similar(g, h)
    name_taken = any(x["id"] == g["id"] for x in h["dinos"])
    return {"score": round(s, 3), "nearest": d["name"] if d else None, "nearest_id": d["id"] if d else None,
            "threshold": Ctx.threshold, "ok": (s < Ctx.threshold) and not name_taken, "name_taken": name_taken}


def preview(spec, exclude=None):
    t0 = time.time()
    g = resolve(spec, hist_without(exclude))
    m = build_model(g)
    faces = paint_faces(m, g)
    imgs, (W, H, k) = build_atlas(faces, g, max_px=512)
    buf = io.BytesIO()
    imgs["albedo"].save(buf, "PNG")
    clips, rig, meta = bake(m, g)
    # geometria por osso, em coordenadas locais do osso (px)
    bones = []
    index = {}
    for n, b in m.bones.items():
        index[n] = len(bones)
        bones.append({"name": n, "parent": b["parent"], "pos": [], "uv": []})
    for f in faces:
        box = m.boxes[f["box"]]
        bn = bones[index[box["bone"]]]
        o, u, v, w, h = f["o"], f["u"], f["v"], f["w"], f["h"]
        cs = [o, o + u * w, o + u * w + v * h, o + v * h]
        x0, y0 = f["rect"]
        uvs = [(x0, y0), (x0 + w, y0), (x0 + w, y0 + h), (x0, y0 + h)]
        P = [box["c"] + box["R"] @ p for p in cs]
        for i in (0, 1, 2, 0, 2, 3):
            bn["pos"].extend(round(float(c), 3) for c in P[i])
            bn["uv"].extend((round(uvs[i][0] / W, 5), round(uvs[i][1] / H, 5)))
    anims = {}
    for cname, clip in clips.items():
        frames = list(range(0, clip["frames"], 2))
        anims[cname] = {"loop": clip["loop"], "duration": clip["duration"], "fps": 15,
                        "frames": [[[round(float(x), 4) for x in clip["world"][b["name"]][fi].T.flatten()] for b in bones]
                                   for fi in frames]}
    mn, mx = m.bbox()
    s = g["px_size"]
    # VFX para o preview (unidades em px do modelo)
    theme, T, opt = effective_vfx(g)
    kk = max(0.6, (mx[1] - mn[1]) * s / 6.0) / s
    cmn, cmx = (np.array(v) for v in m.meta["chest"])
    hmn, hmx = (np.array(v) for v in m.meta["hips"])
    body = (cmn + hmx) / 2
    smn = np.array(m.meta["snout"][0]) if m.meta["snout"][0][2] < m.meta["skull"][0][2] else np.array(m.meta["skull"][0])
    mouth = np.array([0.0, smn[1], smn[2] - 0.5])

    def anchor(bone, pw):
        B = m.bones[bone]
        return {"bone": index[bone], "local": [round(float(x), 3) for x in B["R"].T @ (pw - B["pos"])]}
    vfx = {"theme": theme, "opt": opt, "scale": kk, "glow": T.get("glow"),
           "aura": T.get("aura"), "breath": T.get("breath"),
           "anchors": {"body": anchor("Chest", body), "mouth": anchor("Head", mouth)}}
    if m.meta["tail"]:
        tmn, tmx = (np.array(v) for v in m.meta["tail"][-1])
        vfx["anchors"]["tail"] = anchor("Tail%d" % len(m.meta["tail"]), (tmn + tmx) / 2)
    return {
        "colors": Painter(m, g).effective_colors(), "vfx": vfx,
        "genome": g, "spec": genome_to_spec(g), "bones": bones, "anims": anims,
        "atlas": "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode(),
        "px_size": s, "originality": originality(g, exclude),
        "stats": {"altura": round((mx[1] - mn[1]) * s, 1), "comprimento": round((mx[2] - mn[2]) * s, 1),
                  "walk": round(meta["walk_speed"] * s, 1), "run": round(meta["run_speed"] * s, 1),
                  "pecas": len(m.boxes), "ossos": len(m.bones), "ms": int((time.time() - t0) * 1000)},
    }


def new_job(kind, fn, *args):
    jid = uuid.uuid4().hex[:10]
    job = {"id": jid, "kind": kind, "status": "rodando", "log": [], "progress": None, "result": None, "error": None,
           "started": time.time()}
    JOBS[jid] = job

    def run():
        try:
            job["result"] = fn(job, *args)
            job["status"] = "ok"
        except Exception as e:  # noqa: BLE001
            job["status"] = "erro"
            job["error"] = str(e)
            job["log"].append(traceback.format_exc()[-1500:])
    POOL.submit(run)
    return job


def _rm_thumb(did):
    try:
        os.remove(os.path.join(LIBDIR, "thumbs", did + ".jpg"))
    except OSError:
        pass


def job_save(job, spec, mode, replace_id):
    with LOCK:
        h = load_history(Ctx.history)
        g = resolve(spec, hist_without(replace_id))
        if mode == "replace" and replace_id and replace_id != g["id"]:
            h["dinos"] = [d for d in h["dinos"] if d["id"] != replace_id]
            shutil.rmtree(os.path.join(OUT, replace_id), ignore_errors=True)
            _rm_thumb(replace_id)
            save_history(Ctx.history, h)
    job["log"].append("gerando %s (Blender)..." % g["name"])
    generate({}, OUT, Ctx.history, genome=g, log=job["log"].append)
    return {"id": g["id"], "name": g["name"]}


def job_batch(job, opts):
    def prog(p):
        job["progress"] = p
        if p.get("stage") == "gerando":
            job["log"].append("[%d/%d] %s %s" % (p["done"], p["total"], p["id"], "ERRO" if p.get("error") else "ok"))
        else:
            job["log"].append("conceitos escolhidos: %d (testados %d)" % (p["chosen"], p["tried"]))
    with LOCK:
        ids = run_batch(int(opts.get("count", 10)), Ctx.history, OUT, kinds=opts.get("kinds", "mix"),
                        archetypes=opts.get("archetypes") or None, themes=opts.get("themes") or None,
                        workers=int(opts.get("workers", 4)), name=opts.get("name") or "Lote", progress=prog)
    return {"ids": ids}


LEIA = """{name} - dinomaker (versao B, mesh com textura pixel art)

UMA VEZ SO: Studio > Plugins > Pasta de plugins > copie DinoMaker_Plugin.rbxm. Reabra o Studio.
1. Importar 3D > selecione TODOS os .fbx da pasta FBX (textura ja vem dentro).
2. Arraste {kits} para o Studio.
3. Barra DinoMaker > "Instalar kits" (ou so de Play). "Passear" liga o passeio.
Lista dos dinos: lista_dinos.csv | fotos: previews/
"""


def open_folder(path):
    import subprocess
    import sys
    if sys.platform.startswith("win"):
        os.startfile(path)  # noqa: S606
    elif sys.platform == "darwin":
        subprocess.Popen(["open", path])
    else:
        subprocess.Popen(["xdg-open", path])


def job_export(job, ids, name):
    """Monta exportados/<nome>/ (pronto para o Studio) + exportados/<nome>.zip."""
    h = load_history(Ctx.history)
    by = {d["id"]: d for d in h["dinos"] if d.get("genome")}
    gens = [by[i]["genome"] for i in ids if i in by]
    if not gens:
        raise RuntimeError("nenhum dino válido selecionado")
    base = slug(name or "Pacote") or "pacote"
    name, k = base, 2
    while os.path.exists(os.path.join(EXPORTS, name)) or os.path.exists(os.path.join(EXPORTS, name + ".zip")):
        name, k = "%s_%d" % (base, k), k + 1
    for i, g in enumerate(gens):
        fbx = os.path.join(OUT, g["id"], "B_mesh", g["id"] + ".fbx")
        if not os.path.exists(fbx):
            job["log"].append("[%d/%d] gerando %s no Blender..." % (i + 1, len(gens), g["name"]))
            generate({}, OUT, Ctx.history, genome=g, update_history=False, log=lambda *a: None)
        job["progress"] = {"done": i + 1, "total": len(gens)}
    job["log"].append("empacotando %d kits..." % len(gens))
    final = os.path.join(EXPORTS, name)
    os.makedirs(os.path.join(final, "FBX"))
    with tempfile.TemporaryDirectory() as tmp:
        kits, plug = pack_kits(gens, tmp, name, log=lambda *a: None)
        kb = kits[:-1]  # .rbxm (binário) quando o Node/rbx-dom está instalado; senão o .rbxmx serve igual
        shutil.copy(kb if os.path.exists(kb) else kits, final)
        pre = os.path.join(ROOT, "tools", "DinoMaker_Plugin.rbxm")
        shutil.copy(pre if os.path.exists(pre) else plug, final)
    for g in gens:
        shutil.copy(os.path.join(OUT, g["id"], "B_mesh", g["id"] + ".fbx"), os.path.join(final, "FBX", g["id"] + ".fbx"))
        pv = os.path.join(OUT, g["id"], "preview", "idle_front34.png")
        if os.path.exists(pv):
            os.makedirs(os.path.join(final, "previews"), exist_ok=True)
            shutil.copy(pv, os.path.join(final, "previews", g["id"] + ".png"))
    rows = ["nome;id;especie;arquetipo;fantasia;paleta;padrao;features"]
    for g in gens:
        rows.append(";".join([g["name"], g["id"], g["species"], g["archetype"], "sim" if g["fantasy"] else "nao",
                              g["palette_name"], g["pattern"]["type"], ",".join(g["features"])]))
    with open(os.path.join(final, "lista_dinos.csv"), "w", encoding="utf-8-sig") as f:
        f.write("\n".join(rows))
    kits_fn = next(f for f in os.listdir(final) if "_DinoKits." in f)
    with open(os.path.join(final, "LEIA-ME.txt"), "w", encoding="utf-8") as f:
        f.write(LEIA.format(name=name, kits=kits_fn))
    zpath = os.path.join(EXPORTS, name + ".zip")
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        for dp, _, fns in os.walk(final):
            for fn in fns:
                full = os.path.join(dp, fn)
                z.write(full, os.path.relpath(full, final))
    job["log"].append("pronto: %s" % final)
    return {"zip": "/files/exportados/%s.zip" % name, "count": len(gens), "folder": final, "name": name}


def job_fill(job):
    """Gera (Blender) os dinos do histórico que ainda não têm arquivos (FBX, kit, previews)."""
    h = load_history(Ctx.history)
    todo = [d["genome"] for d in h["dinos"] if d.get("genome") and not
            os.path.exists(os.path.join(OUT, d["id"], "B_mesh", d["id"] + ".fbx"))]
    if not todo:
        job["log"].append("nada faltando")
        return {"count": 0}
    from concurrent.futures import ProcessPoolExecutor
    from .batch import _build_one
    with ProcessPoolExecutor(max(1, min(4, (os.cpu_count() or 2) - 1))) as ex:
        for i, (gid, err) in enumerate(ex.map(_build_one, [(g, OUT, Ctx.history) for g in todo])):
            job["progress"] = {"done": i + 1, "total": len(todo)}
            job["log"].append("[%d/%d] %s %s" % (i + 1, len(todo), gid, "ERRO" if err else "ok"))
    return {"count": len(todo)}


def meta():
    arch_species = {}
    for k, (a, disp, _, _) in SPECIES.items():
        arch_species.setdefault(a, []).append({"key": k, "name": disp})
    return {
        "archetypes": [{"key": a, "name": ARCH.get(a, a), "stance": ARCHETYPES[a]["stance"]} for a in ARCHETYPES],
        "species": arch_species, "palettes": PALETTES, "patterns": PATTERNS, "eye_styles": EYE_STYLES,
        "sizes": SIZE_CLASSES, "features": ALL_FEATURES, "themes": list(THEMES), "vfx": list(VFX_THEMES),
        "attacks": ["bite", "claw", "headbutt", "tailswipe", "stomp", "peck"], "claws": CLAW_COLORS,
        "groups": ["head", "neck", "tail", "legs", "arms", "body", "bulk"], "threshold": Ctx.threshold,
        "params": [{"key": k, "label": v[0], "group": v[1], "min": v[2], "max": v[3], "step": v[4], "int": k in INT_PARAMS}
                   for k, v in PARAM_SPEC.items()],
        "feature_groups": FEATURE_GROUPS, "vfx_defaults": VFX_DEFAULTS,
    }


def library():
    h = load_history(Ctx.history)
    out = []
    for d in h["dinos"]:
        thumb = os.path.join(OUT, d["id"], "preview", "idle_front34.png")
        small = os.path.join(LIBDIR, "thumbs", d["id"] + ".jpg")
        url = ("/files/library/thumbs/%s.jpg" % d["id"] if os.path.exists(small) else
               "/files/output/%s/preview/idle_front34.png" % d["id"] if os.path.exists(thumb) else None)
        out.append({"id": d["id"], "name": d["name"], "species": d["species"], "archetype": d["archetype"],
                    "fantasy": d.get("fantasy"), "palette": d.get("palette"), "pattern": d.get("pattern"),
                    "legacy": bool(d.get("legacy")), "editable": bool(d.get("genome")),
                    "thumb": url,
                    "built": os.path.exists(os.path.join(OUT, d["id"], "B_mesh", d["id"] + ".fbx")),
                    "created": d.get("created")})
    novos = sorted([d for d in out if not d["legacy"]], key=lambda d: d.get("created") or "", reverse=True)
    return novos + [d for d in out if d["legacy"]]


# ---------------------------------------------------------------- HTTP
class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _json(self, obj, code=200):
        data = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _file(self, path):
        if not os.path.isfile(path):
            return self._json({"erro": "não encontrado"}, 404)
        ext = os.path.splitext(path)[1].lower()
        ctype = {".html": "text/html; charset=utf-8", ".js": "application/javascript", ".css": "text/css",
                 ".png": "image/png", ".zip": "application/zip", ".json": "application/json"}.get(ext, "application/octet-stream")
        with open(path, "rb") as f:
            data = f.read()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        if ext == ".zip":
            self.send_header("Content-Disposition", 'attachment; filename="%s"' % os.path.basename(path))
        self.end_headers()
        self.wfile.write(data)

    def _body(self):
        n = int(self.headers.get("Content-Length") or 0)
        return json.loads(self.rfile.read(n) or b"{}")

    def do_GET(self):
        p = unquote(urlparse(self.path).path)
        try:
            if p in ("/", "/index.html"):
                return self._file(os.path.join(UI, "index.html"))
            if p.startswith("/ui/"):
                return self._file(os.path.normpath(os.path.join(UI, p[4:])) if ".." not in p else "")
            if p.startswith(("/files/output/", "/files/library/", "/files/exportados/")):
                full = os.path.normpath(os.path.join(ROOT, p[len("/files/"):]))
                if not any(full.startswith(d + os.sep) for d in (OUT, LIBDIR, EXPORTS)) or ".." in p:
                    return self._json({"erro": "proibido"}, 403)
                return self._file(full)
            if p == "/api/meta":
                return self._json(meta())
            if p == "/api/library":
                return self._json(library())
            if p.startswith("/api/dino/"):
                did = p.split("/")[-1]
                d = next((x for x in load_history(Ctx.history)["dinos"] if x["id"] == did), None)
                if not d or not d.get("genome"):
                    return self._json({"erro": "dino sem genoma (legado)"}, 404)
                return self._json({"spec": genome_to_spec(d["genome"]), "genome": d["genome"]})
            if p.startswith("/api/job/"):
                j = JOBS.get(p.split("/")[-1])
                return self._json(j or {"erro": "job não existe"}, 200 if j else 404)
            if p == "/api/jobs":
                return self._json(sorted(JOBS.values(), key=lambda j: -j["started"])[:20])
            return self._json({"erro": "rota"}, 404)
        except Exception as e:  # noqa: BLE001
            return self._json({"erro": str(e)}, 500)

    def do_POST(self):
        p = urlparse(self.path).path
        try:
            b = self._body()
            if p == "/api/preview":
                return self._json(preview(b["spec"], b.get("exclude")))
            if p == "/api/new":
                spec = {k: v for k, v in b.items() if v not in (None, "", [])}
                h = load_history(Ctx.history)
                from .pipeline import unique_genome
                tries = [spec] if spec.get("species") or spec.get("archetype") else [spec, dict(spec, fantasy=True)]
                g = why = None
                for sp in tries:
                    try:
                        g, why = unique_genome(sp, h, Ctx.threshold, max_tries=60)
                        break
                    except RuntimeError as e:
                        why = str(e)
                if g is None:  # espaço lotado para esse corpo: entrega mesmo assim, o medidor mostra
                    g = resolve(spec, h)
                return self._json({"spec": genome_to_spec(g), "why": why})
            if p == "/api/save":
                spec, mode, rid = b["spec"], b.get("mode", "new"), b.get("replace_id")
                g = resolve(spec, hist_without(rid if mode == "replace" else None))
                if mode == "new" and not b.get("force"):
                    ok, why = check_unique(g, load_history(Ctx.history), Ctx.threshold)
                    if not ok:
                        return self._json({"erro": why}, 409)
                return self._json(new_job("salvar", job_save, spec, mode, rid))
            if p == "/api/batch":
                return self._json(new_job("lote", job_batch, b))
            if p == "/api/export":
                return self._json(new_job("exportar", job_export, b.get("ids", []), b.get("name")))
            if p == "/api/fill":
                return self._json(new_job("miniaturas", job_fill))
            if p == "/api/open":  # abre a pasta exportada no Explorer/Finder
                full = os.path.normpath(os.path.join(EXPORTS, os.path.basename(b.get("name", ""))))
                if not full.startswith(EXPORTS + os.sep) or not os.path.isdir(full):
                    return self._json({"erro": "pasta não encontrada"}, 404)
                open_folder(full)
                return self._json({"ok": True})
            if p == "/api/forget":
                with LOCK:
                    h = load_history(Ctx.history)
                    h["dinos"] = [d for d in h["dinos"] if d["id"] != b["id"] or d.get("legacy")]
                    save_history(Ctx.history, h)
                if b.get("delete_files"):
                    shutil.rmtree(os.path.join(OUT, b["id"]), ignore_errors=True)
                    _rm_thumb(b["id"])
                return self._json({"ok": True})
            return self._json({"erro": "rota"}, 404)
        except Exception as e:  # noqa: BLE001
            traceback.print_exc()
            return self._json({"erro": str(e)}, 500)


def serve(port=8765, open_browser=True, history=None):
    if history:
        Ctx.history = history
    srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    url = "http://localhost:%d" % port
    print("[dinomaker] painel em %s  (Ctrl+C para sair)" % url)
    if open_browser:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
