"""Versão B: kit (.rbxmx) para arrastar para dentro do modelo importado pelo Import 3D.

Pasta "DinoKit" com: DinoRigData (posições de descanso do gerador), DinoRig (encaixe
automático + driver de Bones), Animations (KeyframeSequences), VFX, DinoAnimator,
DinoBrain e DinoAPI. Mesma API e atributos da versão A.
"""
import os

import numpy as np

from .export_rbx import Ref, Node, animations_folder, script_node, attrs_xml, LUA_DIR
from .vfx import add_vfx


def _cf_list(M):
    R, t = M[:3, :3], M[:3, 3]
    vals = list(t) + [R[i, j] for i in range(3) for j in range(3)]
    return "{%s}" % ", ".join("%.5f" % (0.0 if abs(v) < 1e-9 else v) for v in vals)


def rig_data_lua(model, genome, meta):
    s = genome["px_size"]
    lines = ["-- gerado pelo dinomaker: posições de descanso do rig (studs, espaço do gerador)", "return {", "\tbones = {"]
    for n, b in model.bones.items():
        M = np.eye(4)
        M[:3, :3] = b["R"]
        M[:3, 3] = b["pos"] * s
        par = '"%s"' % b["parent"] if b["parent"] else "nil"
        lines.append('\t\t{ name = "%s", parent = %s, rest = %s },' % (n, par, _cf_list(M)))
    lines.append("\t},")
    hmn, hmx = (np.array(v) for v in model.meta["hips"])
    cmn, cmx = (np.array(v) for v in model.meta["chest"])
    size = np.array([max(hmx[0] - hmn[0], cmx[0] - cmn[0]), hmx[1] - hmn[1], hmx[2] - cmn[2]])
    c = np.array([0, hmn[1] + size[1] / 2, (hmx[2] + cmn[2]) / 2])
    H = np.eye(4)
    H[:3, 3] = c * s
    lines.append("\thrp = { cf = %s, size = {%.4f, %.4f, %.4f} }," % ((_cf_list(H),) + tuple(size * s)))
    lines.append("\thipHeight = %.4f," % (hmn[1] * s))
    lines.append("\twalkSpeed = %.4f," % (meta["walk_speed"] * s))
    lines.append("\trunSpeed = %.4f," % (meta["run_speed"] * s))
    lines.append("}")
    return "\n".join(lines) + "\n"


def export_kit(path, model, genome, clips, meta):
    Ref.n = 0
    s = genome["px_size"]
    kit = Node("Folder", "DinoKit")
    vfx = Node("Folder", "VFX")
    theme = add_vfx(Node, model, genome, None, s, kit_folder=vfx)
    kit.add(vfx)
    kit.add(animations_folder(model, clips, s))

    def src(name):
        with open(os.path.join(LUA_DIR, name + ".lua"), encoding="utf-8") as fh:
            return fh.read()

    kit.add(script_node("ModuleScript", "DinoRigData", rig_data_lua(model, genome, meta)))
    kit.add(script_node("ModuleScript", "DinoRig", src("DinoRig")))
    kit.add(script_node("ModuleScript", "DinoAPI", src("DinoAPI")))
    kit.add(script_node("Script", "DinoAnimator", src("DinoAnimator"), run_context=2))
    kit.add(script_node("Script", "DinoBrain", src("DinoBrain"), run_context=1))
    kit.props.append(attrs_xml({
        "DinoName": genome["name"], "Species": genome["species"], "Archetype": genome["archetype"],
        "Wander": False, "WanderRadius": 40.0, "Action": "", "ActionNonce": 0.0,
        "AttackStyle": genome["attack"], "Flying": False, "VFX": True, "VFXTheme": theme,
    }))
    out = ['<roblox xmlns:xmime="http://www.w3.org/2005/05/xmlmime" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
           'xsi:noNamespaceSchemaLocation="http://www.roblox.com/roblox.xsd" version="4">',
           "<External>null</External><External>nil</External>"]
    kit.xml(out)
    out.append("</roblox>")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(out))
    return theme
