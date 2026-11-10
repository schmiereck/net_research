"""robot_findc: does the colour address generalise to a hue never seen in training?

    python scripts/robot_findc_eval.py [--models cnn+cmd layer_s+cmd ...] [--seeds 0 1 2]

    test     test scenes with trained hues, a random cube commanded
    held     scenes with one cube in the held-out hue band (green, 0.25-0.40), that cube commanded
    control  the same scenes, a cube with a trained hue commanded (is it the scenes or the address?)
    wrong    test scenes, the command of ANOTHER cube of the scene: share of answers that still hit the asked
             cube (near 0 = the net follows the command)
Exact match, within +-1 cell and mean absolute error in cells.
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np
import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from netresearch.tasks import make_task  # noqa: E402
from netresearch.train import load_checkpoint, run_sequence, to_t  # noqa: E402

W = np.array([8, 4, 2, 1])


def decode(bits):
    v = (bits.reshape(-1, 2, 4) * W).sum(-1)
    return np.where(v > 7, v - 16, v)


def score(model, b, target=None):
    with torch.no_grad():
        lg, _ = run_sequence(model, b["obs"], cmd=b["cmd"], ref=b.get("ref"))
    p = decode((lg[0, :, 18:26] > 0).numpy().astype(np.int64))
    t = decode((b["target"] if target is None else target)[0].numpy().astype(np.int64))
    e = np.abs(p - t)
    return {"exact": round(float((e.sum(1) == 0).mean()), 4), "within1": round(float((e.max(1) <= 1).mean()), 4),
            "mae": round(float(e.mean()), 3), "n": len(t)}


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--models", nargs="+", default=["cnn+cmd", "layer_s+cmd", "layer_s_sp4+cmd", "vit+cmd"])
    ap.add_argument("--seeds", nargs="+", type=int, default=[0, 1, 2])
    ap.add_argument("--out", default="results/robot_findc_eval.jsonl")
    ap.add_argument("--task", default="robot_findc", choices=["robot_findc", "robot_findi"])
    a = ap.parse_args()
    task = make_task(a.task)
    d = task._load(f"{task.files[0]}_test")
    n = len(d["obs"])
    k = np.random.default_rng(0).integers(0, 3, size=n)
    sets = {"test": to_t(task.make(d, np.arange(n), k)), "held": to_t(task.held_out()),
            "control": to_t(task.held_out(other=True))}
    wrong = to_t(task.make(d, np.arange(n), (k + 1) % 3))              # another cube's command / picture ...
    rows = []
    for m in a.models:
        for s in a.seeds:
            model = load_checkpoint(m, a.task, s)
            if model is None:
                continue
            if hasattr(model, "ref_enc"):                    # what does the net's own address carry?
                with torch.no_grad():
                    z = model.ref_enc(sets["test"]["ref"])[0].numpy()
                col = sets["test"]["cmd"][0, :, :3].numpy()
                h = len(z) // 2                               # colour from the address: linear fit on one half,
                A = np.c_[z[:h], np.ones(h)]                  # R^2 on the other
                w = np.linalg.lstsq(A, col[:h], rcond=None)[0]
                res = col[h:] - np.c_[z[h:], np.ones(len(z) - h)] @ w
                r2 = 1 - (res ** 2).sum() / ((col[h:] - col[h:].mean(0)) ** 2).sum()
                rows.append({"model": m, "seed": s, "set": "addr_r2", "exact": round(float(r2), 4),
                             "within1": round(float(r2), 4), "mae": float("nan"), "n": len(z) - h})
            for name, b in sets.items():
                rows.append({"model": m, "seed": s, "set": name, **score(model, b)})
            rows.append({"model": m, "seed": s, "set": "wrong", **score(model, wrong, sets["test"]["target"])})
    with open(a.out, "w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    import pandas as pd
    df = pd.DataFrame(rows)
    with pd.option_context("display.width", 200):
        for v in ("exact", "within1", "mae"):
            print(v)
            t = df.pivot_table(index="model", columns="set", values=v)
            print(t[[c for c in ("test", "held", "control", "wrong", "addr_r2") if c in t]].round(2).to_string())


if __name__ == "__main__":
    main()
