"""Registra no histórico os dinos feitos à mão antes do gerador (dino_envio_1.blend),
para o gerador evitar criar algo parecido com eles. Rode uma vez:
  python tools/seed_legacy.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dinomaker.genome import resolve, load_history, save_history, add_to_history  # noqa: E402
from dinomaker.cli import DEFAULT_HISTORY  # noqa: E402

LEGACY = [
    dict(name="T-Rex Verde (legado)", species="tyrannosaurus", palette=dict(primary="#3f8f2c", belly="#c9c46a", accent="#e0c27a", pattern="#2c6a1f"), pattern={"type": "mottled"}),
    dict(name="Indominus (legado)", archetype="theropod", features=["back_spikes", "horns_brow"], palette=dict(primary="#cfc9bd", belly="#efe9dc", accent="#5a5a5a", pattern="#8f8a80"), pattern={"type": "stripes"}),
    dict(name="Dino Azul de Chifres (legado)", archetype="theropod", features=["horns_brow", "back_spikes"], palette=dict(primary="#4a7fc0", belly="#9cc0e6", accent="#d9c24a", pattern="#2f5f9a"), pattern={"type": "mottled"}),
    dict(name="Dino Laranja (legado)", archetype="theropod", palette=dict(primary="#d08a2e", belly="#f0c890", accent="#7a4a1e", pattern="#a5601f"), pattern={"type": "mottled"}),
    dict(name="Dino Rosa (legado)", archetype="ceratopsian", features=["-frill", "-horns_long"], palette=dict(primary="#e98bc1", belly="#ffe0f0", accent="#f2e04a", pattern="#f2e04a"), pattern={"type": "spots"}),
    dict(name="Raptor Laranja de Crista (legado)", archetype="raptor", features=["crest_fan"], palette=dict(primary="#c0581f", belly="#e8a060", accent="#e8c040", pattern="#8a3a14"), pattern={"type": "none"}),
    dict(name="Dino Turquesa (legado)", archetype="spinosaur", features=["-sail"], palette=dict(primary="#2fb0c8", belly="#7fd8e8", accent="#1d6f80", pattern="#1d7f94"), pattern={"type": "stripes"}),
    dict(name="Anquilo Verde de Clava (legado)", archetype="ankylosaur", palette=dict(primary="#4f8f2a", belly="#9cc04a", accent="#e08a2a", pattern="#2f6a1a"), pattern={"type": "mottled"}),
]


def main():
    hist = load_history(DEFAULT_HISTORY)
    have = {d["id"] for d in hist["dinos"]}
    n = 0
    for i, spec in enumerate(LEGACY):
        spec = dict(spec, seed=1000 + i, chibi=False)
        g = resolve(spec, hist)
        if g["id"] in have:
            continue
        add_to_history(hist, g, "legado:dino_envio_1.blend")
        hist["dinos"][-1]["legacy"] = True
        n += 1
    save_history(DEFAULT_HISTORY, hist)
    print("legados adicionados:", n)


if __name__ == "__main__":
    main()
