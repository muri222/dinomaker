"""Teste de estresse: dinos com TUDO aleatório (dentro dos limites do painel) precisam
montar, animar, não ter z-fighting e manter os pés no chão.
  python -m unittest tests.test_fuzz            (60 casos)
  FUZZ_N=500 python -m unittest tests.test_fuzz (mais casos)
"""
import os
import random
import unittest

import numpy as np

from dinomaker.anims import bake
from dinomaker.genome import resolve, GROUPS
from dinomaker.model import build_model, coplanar_conflicts
from dinomaker.species import (ARCHETYPES, PARAM_SPEC, INT_PARAMS, ALL_FEATURES, PATTERNS, EYE_STYLES, PALETTES)
from dinomaker.texture import paint_faces


def random_spec(rng):
    arch = rng.choice(list(ARCHETYPES))
    params = {}
    for k, (_, _, lo, hi, _) in PARAM_SPEC.items():
        if rng.random() < 0.35:
            v = rng.uniform(lo, hi)
            params[k] = int(round(v)) if k in INT_PARAMS else round(v, 2)
    col = lambda: "#%06x" % rng.randrange(0, 0xFFFFFF)  # noqa: E731
    return {
        "exact": True, "archetype": arch, "fantasy": True, "seed": rng.randrange(1, 10 ** 6),
        "name": "Fuzz %d" % rng.randrange(10 ** 9), "px_size": rng.uniform(0.06, 0.35),
        "variation": {g: rng.uniform(0.5, 1.8) for g in GROUPS},
        "features_exact": rng.sample(ALL_FEATURES, rng.randint(0, 10)),
        "params": params,
        "palette": dict(PALETTES[rng.choice(list(PALETTES))], primary=col(), pattern2=col(), pupil=col()),
        "pattern": {"type": rng.choice(PATTERNS), "scale": rng.randint(3, 10), "density": rng.uniform(0.1, 1)},
        "eyes": {"style": rng.choice(EYE_STYLES), "size": rng.randint(1, 5)},
        "color_adjust": {"hue": rng.uniform(-180, 180), "sat": rng.uniform(0, 2), "val": rng.uniform(0.3, 1.6)},
        "texture": {"grain": rng.uniform(0, 3), "belly": rng.uniform(0, 0.5), "pattern_legs": rng.random() < 0.5},
        "vfx": {"theme": rng.choice(["", "fire", "ice", "magic", "none"]), "intensity": rng.uniform(0, 3),
                "size": rng.uniform(0.3, 3), "aura": rng.random() < 0.7},
        "anim": {"energy": rng.uniform(0.4, 1.8)},
        "attack": rng.choice(["bite", "claw", "headbutt", "tailswipe", "stomp", "peck"]),
    }


class TestFuzz(unittest.TestCase):
    def test_random_dinos(self):
        n = int(os.environ.get("FUZZ_N", 60))
        rng = random.Random(1234)
        for i in range(n):
            spec = random_spec(rng)
            with self.subTest(i=i, arch=spec["archetype"]):
                g = resolve(spec)
                m = build_model(g)
                self.assertEqual(coplanar_conflicts(m), [])
                for b in m.boxes:
                    self.assertTrue(np.all(b["size"] > 0.2))
                for lg in m.legs:
                    self.assertAlmostEqual(lg["ankle"][1], g["params"]["foot_h"], delta=1e-6)
                clips, rig, meta = bake(m, g)
                self.assertIn("Idle", clips)
                for name, clip in clips.items():
                    for J in clip["world"]["Hips"]:
                        self.assertTrue(np.all(np.isfinite(J)), name)
                if i % 10 == 0:
                    faces = paint_faces(m, g)
                    self.assertTrue(all(np.all(np.isfinite(f["clean"])) for f in faces))


if __name__ == "__main__":
    unittest.main()
