"""Testa o DinoRig.lua (kit da versão B) com um mock do Roblox: o "importador"
gira, escala, desloca o modelo e orienta cada osso aleatoriamente; o kit precisa
encaixar sozinho e levar os ossos à pose certa."""
import os
import unittest

import numpy as np

try:
    from lupa import LuaRuntime
except ImportError:  # pragma: no cover
    LuaRuntime = None

from dinomaker.anims import bake
from dinomaker.export_kit import rig_data_lua
from dinomaker.genome import resolve
from dinomaker.model import build_model

HERE = os.path.dirname(os.path.abspath(__file__))
LUA = os.path.join(os.path.dirname(HERE), "dinomaker", "lua")


def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def comps(M):
    return [float(M[0, 3]), float(M[1, 3]), float(M[2, 3])] + [float(M[i, j]) for i in range(3) for j in range(3)]


def rand_rot(rng):
    q, r = np.linalg.qr(rng.normal(size=(3, 3)))
    q = q @ np.diag(np.sign(np.diag(r)))
    if np.linalg.det(q) < 0:
        q[:, 0] *= -1
    return q


@unittest.skipIf(LuaRuntime is None, "lupa não instalado")
class TestKitLua(unittest.TestCase):
    def run_case(self, species, clip, frame, loose=False):
        g = resolve({"species": species, "seed": 4})
        m = build_model(g)
        clips, rig, meta = bake(m, g)
        s = g["px_size"]
        L = LuaRuntime(unpack_returned_tuples=True)
        L.execute(read(os.path.join(HERE, "roblox_mock.lua")))
        data = L.execute(rig_data_lua(m, g, meta))
        G = L.globals()
        kit = G.Instance.new("Folder")
        kit.Name = "DinoKit"
        dm = G.Instance.new("ModuleScript")
        dm.Name = "DinoRigData"
        dm._module = data
        dm.Parent = kit
        G.script = L.table(Parent=kit)
        G.require = L.eval("function(inst) return inst._module end")
        Rig = L.execute(read(os.path.join(LUA, "DinoRig.lua")))

        # "importação": similaridade S + orientação aleatória por osso
        rng = np.random.default_rng(1)
        Rs = np.array([[0, 0, 1], [0, 1, 0], [-1, 0, 0]], float)  # 90° em Y
        k, t = 2.5, np.array([10.0, 3.0, -7.0])

        def S_point(p):
            return t + k * Rs @ p

        model = G.Instance.new("Model")
        part = G.Instance.new("MeshPart")
        P = np.eye(4)
        P[:3, :3] = rand_rot(rng)
        P[:3, 3] = [4, 1, 2]
        part.CFrame = G.CFrame.new(*comps(P))
        part.Parent = model
        ws = G.Instance.new("Workspace")
        G.workspace = ws
        base = G.Instance.new("Part")
        base.Name = "Baseplate"
        base.Anchored = True
        base.CFrame = G.CFrame.new(0, -1, 0)
        base.Parent = ws
        model.Parent = ws
        kit.Parent = ws if loose else model
        if loose:  # outro dino (espécie diferente) com ossos de mesmo nome
            g2 = resolve({"species": "brachiosaurus", "seed": 9})
            m2 = build_model(g2)
            other = G.Instance.new("Model")
            p2 = G.Instance.new("MeshPart")
            p2.CFrame = G.CFrame.new(50, 0, 0)
            p2.Parent = other
            made = {}
            for n, b in m2.bones.items():
                Wb = np.eye(4)
                Wb[:3, 3] = b["pos"] * g2["px_size"] + np.array([50, 0, 0])
                pw = np.eye(4)
                if b["parent"]:
                    pw[:3, 3] = m2.bones[b["parent"]]["pos"] * g2["px_size"] + np.array([50, 0, 0])
                else:
                    pw[:3, 3] = [50, 0, 0]
                bone = G.Instance.new("Bone")
                bone.Name = n
                bone.CFrame = G.CFrame.new(*comps(np.linalg.inv(pw) @ Wb))
                bone.Parent = made[b["parent"]] if b["parent"] else p2
                made[n] = bone
            other.Parent = ws
        W, O, inst = {}, {}, {}
        for n, b in m.bones.items():
            O[n] = rand_rot(rng)
            Wb = np.eye(4)
            Wb[:3, :3] = O[n]
            Wb[:3, 3] = S_point(b["pos"] * s)
            W[n] = Wb
            parent_w = W[b["parent"]] if b["parent"] else P
            bone = G.Instance.new("Bone")
            bone.Name = n
            bone.CFrame = G.CFrame.new(*comps(np.linalg.inv(parent_w) @ Wb))
            bone.Parent = inst[b["parent"]] if b["parent"] else part
            inst[n] = bone

        self.assertFalse(Rig.setup(ws, kit))  # nunca trata o Workspace como dino
        same = L.eval("function(a, b) return rawequal(a, b) end")
        self.assertTrue(same(Rig.findTarget(kit), model))
        self.assertTrue(same(kit.Parent, model))
        self.assertTrue(Rig.setup(model, kit))
        self.assertTrue(base.Anchored)
        self.assertIsNone(ws.FindFirstChildOfClass(ws, "Humanoid"))
        hrp = model.HumanoidRootPart
        drv = Rig.newDriver(model, hrp, kit)
        loc = clips[clip]["local"][frame]
        pose = L.table()
        for n, (R, tl) in loc.items():
            M = np.eye(4)
            M[:3, :3] = R
            M[:3, 3] = tl * s
            pose[n] = G.CFrame.new(*comps(M))
        drv.apply(pose)

        worst = 0.0
        for n, b in m.bones.items():
            got = inst[n].TransformedWorldCFrame
            c = list(got.components(got))
            gp = np.array(c[:3])
            Jw = clips[clip]["world"][n][frame]
            want_p = S_point(Jw[:3, 3] * s)
            worst = max(worst, np.linalg.norm(gp - want_p))
            gr = np.array(c[3:]).reshape(3, 3)
            want_r = Rs @ Jw[:3, :3] @ b["R"].T @ Rs.T @ O[n]
            self.assertLess(np.abs(gr - want_r).max(), 1e-4, n)
        self.assertLess(worst, 1e-3)
        self.assertAlmostEqual(model.GetAttribute(model, "DinoMapK"), k, places=4)

    def test_theropod_attack(self):
        self.run_case("tyrannosaurus", "Attack", 15)

    def test_quadruped_walk(self):
        self.run_case("triceratops", "Walk", 7)

    def test_kit_loose_in_workspace(self):
        self.run_case("stegosaurus", "Idle", 10, loose=True)

    def test_pterosaur_fly(self):
        self.run_case("pteranodon", "Fly", 5)


if __name__ == "__main__":
    unittest.main()
