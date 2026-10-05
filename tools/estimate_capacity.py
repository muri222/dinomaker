"""Estima quantos dinos ÚNICOS o gerador consegue criar (com o mesmo bloqueio de
originalidade do painel, limiar 0.82). Sorteia muitos genomas e aceita só os que não
parecem nenhum já aceito (empacotamento guloso). Similaridade vetorizada com numpy.

  python tools/estimate_capacity.py --mode lote  --samples 60000
  python tools/estimate_capacity.py --mode painel --samples 60000
"""
import argparse
import math
import os
import random
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dinomaker.genome import resolve, signature  # noqa: E402
from dinomaker.species import ARCHETYPES, SPECIES, PATTERNS, ALL_FEATURES, EYE_STYLES  # noqa: E402

A_IDX = {a: i for i, a in enumerate(ARCHETYPES)}
S_IDX = {s: i for i, s in enumerate(list(SPECIES) + ["custom"])}
P_IDX = {p: i for i, p in enumerate(PATTERNS)}
F_IDX = {f: i for i, f in enumerate(ALL_FEATURES)}
E_IDX = {e: i for i, e in enumerate(EYE_STYLES)}


def vec(sig):
    f = np.zeros(len(ALL_FEATURES), bool)
    for x in sig["features"]:
        if x in F_IDX:
            f[F_IDX[x]] = True
    return (A_IDX[sig["archetype"]], S_IDX.get(sig["species"], 0), np.array(sig["ratios"]), f,
            np.array(sig["hues"]), P_IDX.get(sig["pattern"], 0), E_IDX.get(sig["eyes"], 0))


class Store:
    def __init__(self, cap=400000):
        nf = len(ALL_FEATURES)
        self.n = 0
        self.a = np.zeros(cap, int); self.s = np.zeros(cap, int); self.r = np.zeros((cap, 5))
        self.f = np.zeros((cap, nf), bool); self.h = np.zeros((cap, 3, 3)); self.p = np.zeros(cap, int); self.e = np.zeros(cap, int)

    def max_sim(self, v):
        if self.n == 0:
            return 0.0
        n = self.n
        a, s, r, f, h, p, e = v
        d = 0.30 * (self.a[:n] != a) + 0.05 * (self.s[:n] != s)
        den = np.maximum(np.maximum(np.abs(self.r[:n]), np.abs(r)), 0.1)
        rd = np.sqrt((((self.r[:n] - r) / den) ** 2).mean(1))
        d += 0.15 * np.minimum(1.0, rd * 2.5)
        inter = (self.f[:n] & f).sum(1)
        uni = (self.f[:n] | f).sum(1)
        jac = np.where(uni > 0, 1 - inter / np.maximum(uni, 1), 0.0)
        d += 0.20 * jac

        def hd(H, hh):
            dh = np.abs(H[:, 0] - hh[0])
            dh = np.minimum(dh, 1 - dh) * 2
            sat = np.minimum(H[:, 1], hh[1])
            return np.minimum(1.0, dh * sat + np.abs(H[:, 1] - hh[1]) * 0.5 + np.abs(H[:, 2] - hh[2]) * 0.5)
        H = self.h[:n]
        d += 0.20 * (hd(H[:, 0], h[0]) * 0.6 + hd(H[:, 1], h[1]) * 0.25 + hd(H[:, 2], h[2]) * 0.15)
        d += 0.07 * (self.p[:n] != p) + 0.03 * (self.e[:n] != e)
        sim = 1 - np.minimum(d, 1)
        sim = np.where((self.a[:n] == a) & (hd(H[:, 0], h[0]) < 0.12), np.minimum(1, sim + 0.08), sim)
        return float(sim.max())

    def add(self, v):
        i = self.n
        self.a[i], self.s[i], self.r[i], self.f[i], self.h[i], self.p[i], self.e[i] = v
        self.n += 1


def sample_lote(rng):
    if rng.random() < 0.4:
        return resolve({"species": rng.choice(list(SPECIES)), "seed": rng.randrange(10 ** 9)})
    return resolve({"archetype": rng.choice(list(ARCHETYPES)), "fantasy": True, "seed": rng.randrange(10 ** 9)})


def sample_painel(rng):
    from tests.test_fuzz import random_spec
    return resolve(random_spec(rng))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["lote", "painel"], default="lote")
    ap.add_argument("--samples", type=int, default=60000)
    ap.add_argument("--threshold", type=float, default=0.82)
    a = ap.parse_args()
    rng = random.Random(7)
    st = Store()
    window, acc_w = 2000, 0
    sampler = sample_lote if a.mode == "lote" else sample_painel
    for i in range(1, a.samples + 1):
        v = vec(signature(sampler(rng)))
        if st.max_sim(v) < a.threshold:
            st.add(v)
            acc_w += 1
        if i % window == 0:
            print("amostras %6d | únicos %6d | aceitação na janela %.1f%%" % (i, st.n, 100 * acc_w / window), flush=True)
            acc_w = 0
    print("RESULTADO", a.mode, st.n)


if __name__ == "__main__":
    main()
