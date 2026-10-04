"""Orquestra: spec -> genoma único -> modelo -> textura -> animações -> exports A e B."""
import glob
import json
import os
import shutil
import subprocess
import sys

import numpy as np

from .anims import bake
from .export_rbx import export_rbxmx
from .genome import resolve, check_unique, load_history, save_history, add_to_history, signature, most_similar
from .model import build_model
from .texture import paint_faces, build_atlas

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)


def find_blender():
    env = os.environ.get("DINOMAKER_BLENDER")
    if env:
        return [env] if not env.endswith(("python", "python3", "python.exe")) else [env, "BPY"]
    exe = shutil.which("blender")
    if exe:
        return [exe]
    cands = sorted(glob.glob(r"C:\Program Files\Blender Foundation\Blender*\blender.exe"), reverse=True)
    cands += sorted(glob.glob("/Applications/Blender.app/Contents/MacOS/Blender"))
    if cands:
        return [cands[0]]
    try:
        import bpy  # noqa: F401
        return [sys.executable, "BPY"]
    except Exception:
        return None


def run_blender(build_json):
    cmd = find_blender()
    if not cmd:
        raise RuntimeError("Blender não encontrado. Instale o Blender (4.2+) ou defina DINOMAKER_BLENDER com o caminho do executável.")
    script = os.path.join(HERE, "blender_build.py")
    if len(cmd) == 2 and cmd[1] == "BPY":
        full = [cmd[0], script, build_json]
    else:
        full = [cmd[0], "-b", "--factory-startup", "-P", script, "--", build_json]
    p = subprocess.run(full, capture_output=True, text=True)
    if "DINOMAKER_BLENDER_OK" not in p.stdout:
        raise RuntimeError("Blender falhou:\n" + p.stdout[-3000:] + "\n" + p.stderr[-3000:])


def validate_rbxmx(path):
    """Valida com rbx-dom (Node) e grava também o .rbxm binário, se disponível."""
    node = shutil.which("node")
    if not node:
        return "validação pulada (Node.js não encontrado)"
    env = dict(os.environ)
    extra = [os.path.join(ROOT, "tools", "node_modules")]
    if env.get("NODE_PATH"):
        extra.append(env["NODE_PATH"])
    env["NODE_PATH"] = os.pathsep.join(extra)
    p = subprocess.run([node, os.path.join(ROOT, "tools", "validate_rbx.js"), path, "--binary"],
                       capture_output=True, text=True, env=env)
    if p.returncode != 0:
        if "Cannot find module 'rbx-dom'" in p.stderr:
            return "validação pulada (rode `npm install` em tools/)"
        raise RuntimeError("rbxmx inválido:\n" + p.stderr[-2000:])
    return "validado com rbx-dom + .rbxm gerado"


def unique_genome(spec, hist, threshold, max_tries=40):
    reasons = []
    seed = spec.get("seed")
    for k in range(max_tries):
        sp = dict(spec)
        if seed is not None:
            sp["seed"] = seed + k
        g = resolve(sp, hist, seed=None if seed is None else seed + k)
        ok, why = check_unique(g, hist, threshold)
        if ok:
            return g, why
        reasons.append(why)
        if "nome" in why and spec.get("name"):
            break
    raise RuntimeError("Não consegui um dino único com esse spec:\n  - " + "\n  - ".join(dict.fromkeys(reasons)))


def _bone_len(model, name):
    b = model.bones[name]
    best = 2.0
    for box in model.boxes:
        if box["bone"] != name:
            continue
        d = b["dir"]
        ext = abs(box["c"] @ d) + abs(box["size"] @ np.abs(box["R"] @ d)) / 2
        best = max(best, ext)
    return best


def build_json(model, g, faces, atlas_dims, clips, tex_paths, out):
    W, H, _k = atlas_dims
    bones = []
    for n, b in model.bones.items():
        J = np.eye(4)
        J[:3, :3] = b["R"]
        J[:3, 3] = b["pos"]
        bones.append(dict(name=n, parent=b["parent"], pos=b["pos"].tolist(), R=b["R"].tolist(),
                          dir=b["dir"].tolist(), len=_bone_len(model, n), Jrest=J.flatten().tolist()))
    fl = []
    for f in faces:
        box = model.boxes[f["box"]]
        B = model.bones[box["bone"]]
        o, u, v, w, h = f["o"], f["u"], f["v"], f["w"], f["h"]
        corners = [o, o + u * w, o + u * w + v * h, o + v * h]
        x0, y0 = f["rect"]
        uvs = [(x0, y0), (x0 + w, y0), (x0 + w, y0 + h), (x0, y0 + h)]
        verts = [(B["pos"] + B["R"] @ (box["c"] + box["R"] @ p)).tolist() for p in corners]
        fl.append(dict(bone=box["bone"], verts=verts, uv=[(a / W, b / H) for a, b in uvs]))
    anims = {}
    for cname, clip in clips.items():
        anims[cname] = dict(frames=clip["frames"], loop=clip["loop"],
                            world={bn: [np.round(J, 5).flatten().tolist() for J in Js] for bn, Js in clip["world"].items()})
    return dict(name=g["id"], px_size=g["px_size"], bones=bones, faces=fl, textures=tex_paths, anims=anims, export=out)


DINO_README = """# {name}

- Espécie base: {species} ({archetype}){fantasy}
- Tamanho: {size} ({height:.1f} studs de altura, {length:.1f} de comprimento)
- Features: {features}
- Paleta: {palette} | Padrão: {pattern} | Olhos: {eyes}
- Animações: {clips}
- WalkSpeed {ws:.1f} / RunSpeed {rs:.1f} studs/s (batem com a passada)

## A) Roblox Parts — pronto para usar (`A_roblox_parts/{id}.rbxmx`)
Studio > Model > (botão direito no Workspace) **Insert from File...** e escolha o `.rbxmx`
(ou arraste o arquivo para a janela do Studio). Já vem com Humanoid, rig Motor6D,
animações embutidas e scripts. Para testar: marque o atributo `Wander` do Model e dê Play.

## B) Mesh + textura PBR (`B_mesh/`)
1. Studio > Avatar/Model > **Import 3D** > `{id}.fbx` (Rig: General, File Dimensions: Studs).
2. No MeshPart importado, adicione **SurfaceAppearance** com `textures/{id}_albedo.png` (ColorMap),
   `_normal.png` (NormalMap), `_roughness.png` (RoughnessMap), `_metalness.png` (MetalnessMap).
3. Animações: Animation Editor > ... > **Import > From FBX Animation** com cada arquivo de `anims/`.
   Depois publique (Publish to Roblox) para obter os AnimationIds.
`{id}.blend` e `{id}.glb` servem para editar/visualizar.
"""


def generate(spec, out_root, history_path, threshold=0.82, formats=("A", "B"), previews=True, detail="medium", dry_run=False, log=print, genome=None):
    """genome != None: rebuild de um dino existente (sem checar unicidade, atualiza o histórico)."""
    hist = load_history(history_path)
    if genome is None:
        g, why = unique_genome(spec, hist, threshold)
    else:
        g, why = genome, "rebuild"
        g.setdefault("vfx", {})
        if "vfx" in spec:
            g["vfx"] = spec["vfx"]
        hist["dinos"] = [d for d in hist["dinos"] if d["id"] != g["id"]]
    log("[dinomaker] %s (%s) — %s" % (g["name"], g["species"], why))
    if dry_run:
        return g, None

    model = build_model(g)
    faces = paint_faces(model, g)
    clips, rig, meta = bake(model, g)
    out_dir = os.path.join(out_root, g["id"])
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "genome.json"), "w", encoding="utf-8") as f:
        json.dump(g, f, ensure_ascii=False, indent=1)

    mn, mx = model.bbox()
    s = g["px_size"]
    info = {}
    if "A" in formats:
        a_dir = os.path.join(out_dir, "A_roblox_parts")
        os.makedirs(a_dir, exist_ok=True)
        faces_a = paint_faces(model, g, crisp=True)
        info["A"] = export_rbxmx(os.path.join(a_dir, g["id"] + ".rbxmx"), model, g, faces_a, clips, meta, detail=detail)
        log("[dinomaker] A: %d parts, %d ossos" % (info["A"]["parts"], info["A"]["bones"]))
        log("[dinomaker] A: " + validate_rbxmx(os.path.join(a_dir, g["id"] + ".rbxmx")))

    b_dir = os.path.join(out_dir, "B_mesh")
    tex_dir = os.path.join(b_dir, "textures")
    os.makedirs(tex_dir, exist_ok=True)
    imgs, dims = build_atlas(faces, g, studs=g.get("studs", False))
    tex_paths = {}
    for k, im in imgs.items():
        p = os.path.abspath(os.path.join(tex_dir, "%s_%s.png" % (g["id"], k)))
        im.save(p)
        tex_paths[k] = p
    out = dict(blend=os.path.abspath(os.path.join(b_dir, g["id"] + ".blend")))
    if "B" in formats:
        out.update(fbx=os.path.abspath(os.path.join(b_dir, g["id"] + ".fbx")),
                   fbx_anims=os.path.abspath(os.path.join(b_dir, "anims")),
                   glb=os.path.abspath(os.path.join(b_dir, g["id"] + ".glb")))
    if previews:
        poses = [["Idle", 1], ["Walk", max(1, clips["Walk"]["frames"] // 4)], ["Attack", 15], ["Roar", 25]]
        if "Fly" in clips:
            poses.append(["Fly", 5])
        out["previews"] = dict(dir=os.path.abspath(os.path.join(out_dir, "preview")), res=512, poses=poses,
                               views={"front34": (0.9, -1.1, 0.5)}, side_idle=True)
    data = build_json(model, g, faces, dims, clips, tex_paths, out)
    bj = os.path.join(out_dir, "build.json")
    with open(bj, "w") as f:
        json.dump(data, f)
    if "B" in formats or previews:
        run_blender(bj)
    os.remove(bj)

    with open(os.path.join(out_dir, "README.md"), "w", encoding="utf-8") as f:
        f.write(DINO_README.format(
            name=g["name"], id=g["id"], species=g["species"], archetype=g["archetype"],
            fantasy=" — fantasia" if g["fantasy"] else "", size=g["size"],
            height=(mx[1] - mn[1]) * s, length=(mx[2] - mn[2]) * s, features=", ".join(g["features"]) or "-",
            palette=g["palette_name"], pattern=g["pattern"]["type"], eyes=g["eyes"]["style"],
            clips=", ".join(clips), ws=meta["walk_speed"] * s, rs=meta["run_speed"] * s))

    add_to_history(hist, g, os.path.relpath(out_dir, ROOT) if out_dir.startswith(ROOT) else out_dir)
    save_history(history_path, hist)
    log("[dinomaker] pronto: %s" % out_dir)
    return g, out_dir
