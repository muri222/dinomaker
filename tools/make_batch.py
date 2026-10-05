"""Lote grande pela linha de comando: python tools/make_batch.py --count 50 --name Lote3"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dinomaker.batch import run_batch  # noqa: E402
from dinomaker.cli import DEFAULT_HISTORY  # noqa: E402

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--count", type=int, default=10, help="quantos dinos NOVOS")
    ap.add_argument("--name", default="Lote")
    ap.add_argument("--kinds", choices=["mix", "real", "fantasy"], default="mix")
    ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args()
    ids = run_batch(a.count, DEFAULT_HISTORY, kinds=a.kinds, workers=a.workers, name=a.name, progress=print)
    print("gerados:", len(ids))
