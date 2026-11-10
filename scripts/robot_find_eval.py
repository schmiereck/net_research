"""robot_find per commanded object: the three cubes (trained) and the L and the U (colours never commanded).

    python scripts/robot_find_eval.py [--models layer_s+cmd cnn+cmd ...] [--seeds 0 1 2]

For every object: exact match and within +-1 cell on the test scenes in which that object is in view. For the
L and the U the label is the body origin, which need not lie on the material (U), so "within 1" and the mean
error are the fairer measures there. Control "wrong": the command of another cube (red asked, green
commanded): how often is the answer still the red cube's cell? (near 0 = the net follows the command).
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

NAMES = ["red", "green", "blue", "L", "U"]
W = np.array([8, 4, 2, 1])


def decode(bits):
    v = (bits.reshape(-1, 2, 4) * W).sum(-1)
    return np.where(v > 7, v - 16, v)


def predict(model, b):
    with torch.no_grad():
        lg, _ = run_sequence(model, b["obs"], cmd=b.get("cmd"))
    return decode((lg[0, :, 18:26] > 0).numpy().astype(np.int64))


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--models", nargs="+", default=["layer_s+cmd", "layer_s_sp4+cmd", "hier_s+cmd", "cnn+cmd",
                                                    "vit+cmd", "layer_s", "cnn"])
    ap.add_argument("--seeds", nargs="+", type=int, default=[0, 1, 2])
    ap.add_argument("--out", default="results/robot_find_eval.jsonl")
    a = ap.parse_args()
    task = make_task("robot_find")
    rows = []
    for m in a.models:
        for s in a.seeds:
            model = load_checkpoint(m, "robot_find", s)
            if model is None:
                continue
            for k, name in enumerate(NAMES):
                b = to_t(task.held_out(k))
                t = decode(b["target"][0].numpy().astype(np.int64))
                e = np.abs(predict(model, b) - t)
                rows.append({"model": m, "seed": s, "object": name, "n": len(t),
                             "exact": round(float((e.sum(1) == 0).mean()), 4),
                             "within1": round(float((e.max(1) <= 1).mean()), 4), "mae": round(float(e.mean()), 3)})
            b = to_t(task.held_out(0))                       # red asked ...
            t = decode(b["target"][0].numpy().astype(np.int64))
            b["cmd"] = to_t(task.held_out(1))["cmd"][:, :1].expand(-1, len(t), -1).clone()   # ... green commanded
            e = np.abs(predict(model, b) - t)
            rows.append({"model": m, "seed": s, "object": "wrong", "n": len(t),
                         "exact": round(float((e.sum(1) == 0).mean()), 4),
                         "within1": round(float((e.max(1) <= 1).mean()), 4), "mae": round(float(e.mean()), 3)})
    with open(a.out, "w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    import pandas as pd
    d = pd.DataFrame(rows)
    with pd.option_context("display.width", 200):
        for v in ("exact", "within1", "mae"):
            print(v)
            print(d.pivot_table(index="model", columns="object", values=v)[NAMES + ["wrong"]].round(2).to_string())


if __name__ == "__main__":
    main()
