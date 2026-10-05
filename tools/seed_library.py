"""Adiciona N dinos únicos (sorteados pelo gerador de lote) à biblioteca, só com miniatura.
FBX/kit são gerados depois, sob demanda, na hora de exportar.

  python tools/seed_library.py --count 1000
"""
import argparse
import os
import shutil
import sys
import tempfile
from concurrent.futures import ProcessPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dinomaker.batch import candidates  # noqa: E402
from dinomaker.genome import load_history, save_history, add_to_history  # noqa: E402
from dinomaker.pipeline import generate, save_thumb, unique_genome, ROOT  # noqa: E402

HIST = os.path.join(ROOT, "history", "history.json")


def thumb_one(g):
    tmp = tempfile.mkdtemp(prefix="dinothumb_")
    try:
        _, out_dir = generate({}, tmp, HIST, genome=g, formats=(), previews=True,
                              update_history=False, log=lambda *a: None)
        return g["id"], save_thumb(out_dir, g["id"]) is not None
    except Exception as e:  # noqa: BLE001
        return g["id"], str(e)[-300:]
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--count", type=int, default=1000)
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2)))
    ap.add_argument("--max-tries", type=int, default=60000)
    a = ap.parse_args()
    hist = load_history(HIST)
    chosen, tried = [], 0
    for spec in candidates("mix", seed=len(hist["dinos"])):
        if len(chosen) >= a.count or tried >= a.max_tries:
            break
        tried += 1
        try:
            g, _ = unique_genome(spec, hist, 0.82, max_tries=2)
        except (RuntimeError, ValueError):
            continue
        add_to_history(hist, g, "output/" + g["id"])
        chosen.append(g)
        if len(chosen) % 100 == 0:
            print("conceitos %d (testados %d)" % (len(chosen), tried), flush=True)
    save_history(HIST, hist)
    print("salvos no histórico: %d (testados %d)" % (len(chosen), tried), flush=True)
    bad = []
    with ProcessPoolExecutor(a.workers) as ex:
        for i, (gid, ok) in enumerate(ex.map(thumb_one, chosen, chunksize=4)):
            if ok is not True:
                bad.append((gid, ok))
            if (i + 1) % 50 == 0:
                print("miniaturas %d/%d" % (i + 1, len(chosen)), flush=True)
    print("FIM ok=%d falhas=%d" % (len(chosen) - len(bad), len(bad)), bad[:5])


if __name__ == "__main__":
    main()
