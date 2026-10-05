"""Painel DinoMaker: servidor local (só stdlib) + interface web em dinomaker/ui.

  python -m dinomaker painel        -> abre http://localhost:8765
"""
import base64
import io
import json
import os
import shutil
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
                      CLAW_COLORS)
from .texture import paint_faces, build_atlas, FACES
from .vfx import THEMES as VFX_THEMES

UI = os.path.join(os.path.dirname(__file__), "ui")
OUT = os.path.join(ROOT, "output")
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
    return {
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


def job_save(job, spec, mode, replace_id):
    with LOCK:
        h = load_history(Ctx.history)
        g = resolve(spec, hist_without(replace_id))
        if mode == "replace" and replace_id and replace_id != g["id"]:
            h["dinos"] = [d for d in h["dinos"] if d["id"] != replace_id]
            shutil.rmtree(os.path.join(OUT, replace_id), ignore_errors=True)
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
2. Arraste {name}_DinoKits.rbxm para o Studio.
3. Barra DinoMaker > "Instalar kits" (ou so de Play). "Passear" liga o passeio.
Lista dos dinos: lista_dinos.csv | fotos: previews/
"""


def job_export(job, ids, name):
    h = load_history(Ctx.history)
    by = {d["id"]: d for d in h["dinos"] if d.get("genome")}
    gens = [by[i]["genome"] for i in ids if i in by]
    if not gens:
        raise RuntimeError("nenhum dino válido selecionado")
    name = slug(name or "Pacote") or "pacote"
    for i, g in enumerate(gens):
        fbx = os.path.join(OUT, g["id"], "B_mesh", g["id"] + ".fbx")
        if not os.path.exists(fbx):
            job["log"].append("gerando %s que faltava..." % g["id"])
            generate({}, OUT, Ctx.history, genome=g, update_history=False, log=lambda *a: None)
        job["progress"] = {"done": i + 1, "total": len(gens)}
    exp = os.path.join(OUT, "exports", name)
    shutil.rmtree(exp, ignore_errors=True)
    os.makedirs(exp)
    job["log"].append("empacotando %d kits..." % len(gens))
    pack_kits(gens, exp, name, log=job["log"].append)
    zpath = os.path.join(OUT, "exports", name + ".zip")
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        for g in gens:
            z.write(os.path.join(OUT, g["id"], "B_mesh", g["id"] + ".fbx"), "FBX/%s.fbx" % g["id"])
            pv = os.path.join(OUT, g["id"], "preview", "idle_front34.png")
            if os.path.exists(pv):
                z.write(pv, "previews/%s.png" % g["id"])
        for fn in (name + "_DinoKits.rbxm", "DinoMaker_Plugin.rbxm"):
            z.write(os.path.join(exp, fn), fn)
        rows = ["nome;id;especie;arquetipo;fantasia;paleta;padrao;features"]
        for g in gens:
            rows.append(";".join([g["name"], g["id"], g["species"], g["archetype"], "sim" if g["fantasy"] else "nao",
                                  g["palette_name"], g["pattern"]["type"], ",".join(g["features"])]))
        z.writestr("lista_dinos.csv", "﻿" + "\n".join(rows))
        z.writestr("LEIA-ME.txt", LEIA.format(name=name))
    return {"zip": "/files/output/exports/%s.zip" % name, "count": len(gens)}


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
    }


def library():
    h = load_history(Ctx.history)
    out = []
    for d in h["dinos"]:
        thumb = os.path.join(OUT, d["id"], "preview", "idle_front34.png")
        out.append({"id": d["id"], "name": d["name"], "species": d["species"], "archetype": d["archetype"],
                    "fantasy": d.get("fantasy"), "palette": d.get("palette"), "pattern": d.get("pattern"),
                    "legacy": bool(d.get("legacy")), "editable": bool(d.get("genome")),
                    "thumb": "/files/output/%s/preview/idle_front34.png" % d["id"] if os.path.exists(thumb) else None,
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
            if p.startswith("/files/output/"):
                full = os.path.normpath(os.path.join(ROOT, p[len("/files/"):]))
                if not full.startswith(OUT) or ".." in p:
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
                g, why = unique_genome(spec, h, Ctx.threshold, max_tries=10)
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
            if p == "/api/forget":
                with LOCK:
                    h = load_history(Ctx.history)
                    h["dinos"] = [d for d in h["dinos"] if d["id"] != b["id"] or d.get("legacy")]
                    save_history(Ctx.history, h)
                if b.get("delete_files"):
                    shutil.rmtree(os.path.join(OUT, b["id"]), ignore_errors=True)
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
