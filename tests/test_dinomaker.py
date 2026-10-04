"""Testes rápidos (sem Blender): python -m unittest discover tests"""
import os
import tempfile
import unittest
import xml.etree.ElementTree as ET

from dinomaker.anims import bake, Rig
from dinomaker.export_rbx import export_rbxmx
from dinomaker.genome import resolve, signature, similarity, check_unique, add_to_history
from dinomaker.model import build_model, coplanar_conflicts
from dinomaker.species import SPECIES, ARCHETYPES
from dinomaker.texture import paint_faces, build_atlas


class TestGenome(unittest.TestCase):
    def test_deterministic(self):
        a = resolve({"species": "triceratops", "seed": 42})
        b = resolve({"species": "triceratops", "seed": 42})
        self.assertEqual(a, b)

    def test_similarity(self):
        a = resolve({"species": "triceratops", "seed": 1})
        self.assertEqual(similarity(signature(a), signature(a)), 1.0)
        b = resolve({"species": "pteranodon", "seed": 2, "palette": "candy"})
        self.assertLess(similarity(signature(a), signature(b)), 0.6)

    def test_history_blocks_copy(self):
        hist = {"dinos": []}
        a = resolve({"species": "stegosaurus", "seed": 3, "palette": "jungle"})
        add_to_history(hist, a, "x")
        b = resolve({"species": "stegosaurus", "seed": 3, "palette": "jungle", "name": "Outro"})
        ok, why = check_unique(b, hist, 0.82)
        self.assertFalse(ok, why)


class TestBuild(unittest.TestCase):
    def test_all_species_build_and_animate(self):
        for sp in SPECIES:
            g = resolve({"species": sp, "seed": 7})
            m = build_model(g)
            self.assertGreater(len(m.boxes), 10, sp)
            for b in m.boxes:
                self.assertTrue(all(s >= 0.5 for s in b["size"]), sp)
            self.assertEqual(coplanar_conflicts(m), [], sp)  # sem z-fighting
            for lg in m.legs:
                self.assertAlmostEqual(lg["ankle"][1], g["params"]["foot_h"], delta=1e-6, msg=sp)
            clips, rig, meta = bake(m, g)
            for name in ("Idle", "Walk", "Run", "Attack", "Roar", "Hit", "Eat", "Death"):
                self.assertIn(name, clips, sp)
            if "wings" in g["features"]:
                self.assertIn("Fly", clips)

    def test_feet_planted_in_idle(self):
        g = resolve({"species": "tyrannosaurus", "seed": 3})
        m = build_model(g)
        clips, rig, meta = bake(m, g)
        for fi in range(0, clips["Idle"]["frames"], 10):
            for lg in m.legs:
                foot = lg["bones"][2]
                J = clips["Idle"]["world"][foot][fi]
                self.assertLess(abs(J[1, 3] - lg["ankle"][1]), 0.05)

    def test_fantasy_archetypes(self):
        for arch in ARCHETYPES:
            g = resolve({"archetype": arch, "fantasy": True, "seed": 11})
            build_model(g)


class TestExport(unittest.TestCase):
    def test_rbxmx_and_atlas(self):
        g = resolve({"species": "velociraptor", "seed": 5})
        m = build_model(g)
        faces = paint_faces(m, g, crisp=True)
        clips, rig, meta = bake(m, g)
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "x.rbxmx")
            info = export_rbxmx(p, m, g, faces, clips, meta, detail="low")
            root = ET.parse(p).getroot()
            classes = [it.get("class") for it in root.iter("Item")]
            self.assertEqual(classes.count("Motor6D"), len(m.bones))
            self.assertEqual(classes.count("KeyframeSequence"), len(clips))
            self.assertIn("Humanoid", classes)
            self.assertLess(info["parts"], 200)
        imgs, (W, H, k) = build_atlas(paint_faces(m, g), g)
        self.assertLessEqual(max(W, H) * k, 1024)
        self.assertEqual(imgs["albedo"].size, (W * k, H * k))


if __name__ == "__main__":
    unittest.main()
