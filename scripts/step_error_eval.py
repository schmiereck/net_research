"""How far off are the wrong gaze / reach steps? (Review 2026-11-13, point 3.4: the step (dx, dy) is coded as two
4-bit two's complement numbers and scored by exact match of all 8 bits.)

    python scripts/step_error_eval.py [--tasks robot_findc robot_reach ...] [--n 3000]

For every checkpoint in results/checkpoints/<task>/ (mean over the seeds of a model), on test examples:
    exact    share with both numbers right (the usual score, chance 0)
    near     share at most ONE cell off in each axis (includes exact)
    err      mean Euclidean error in cells
    wrong<=1 share of the WRONG answers that are at most one cell off in each axis
    ax(-1,0) accuracy of one axis when its true value is -1 or 0 (there all four bits flip between neighbours)
    ax(else) accuracy of one axis for the other true values
-> results/step_error.jsonl
"""
import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from netresearch.tasks import make_task  # noqa: E402
from netresearch.train import load_checkpoint, run_sequence  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def steps(bits):
    """[n, 8] bits (two nibbles, MSB first, two's complement) -> [n, 2] signed steps."""
    v = (bits.reshape(len(bits), 2, 4).astype(np.int64) * np.array([8, 4, 2, 1])).sum(-1)
    return np.where(v > 7, v - 16, v)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tasks", nargs="+", default=["robot_gaze", "robot_find", "robot_findc", "robot_finds",
                                                   "robot_reach"])
    ap.add_argument("--n", type=int, default=3000)
    a = ap.parse_args()
    out = open(ROOT / "results" / "step_error.jsonl", "a")
    keys = ("exact", "near", "err", "wrong_le1", "ax_cliff", "ax_else")
    for tname in a.tasks:
        task = make_task(tname)
        b = task.sample(a.n, np.random.default_rng(0), "test")
        true = steps(b["target"][0])
        extra = {k: torch.tensor(b[k]) for k in ("cmd", "ref") if k in b}
        per = defaultdict(list)
        for p in sorted((ROOT / "results" / "checkpoints" / tname).glob("*.pt")):
            name, seed = re.fullmatch(r"(.+)_s(\d+)", p.stem).groups()
            try:
                model = load_checkpoint(name, tname, int(seed))
                with torch.no_grad():
                    lg, _ = run_sequence(model, torch.tensor(b["obs"]), **extra)
            except Exception as e:                                   # a checkpoint of an older model layout
                print(f"  skipped {p.name}: {type(e).__name__}")
                continue
            pred = steps((lg[0][:, task.spec.out_slice] > 0).numpy())
            d = np.abs(pred - true)
            ok, near = d.max(1) == 0, d.max(1) <= 1
            cliff = (true == -1) | (true == 0)
            row = [ok.mean(), near.mean(), np.sqrt((d ** 2).sum(1)).mean(),
                   near[~ok].mean() if (~ok).any() else float("nan"),
                   (d == 0)[cliff].mean(), (d == 0)[~cliff].mean()]
            per[name].append(row)
            out.write(json.dumps({"task": tname, "model": name, "seed": int(seed),
                                  **{k: round(float(v), 4) for k, v in zip(keys, row)}}) + "\n")
        print(f"\n{tname}  (share of axis values that are -1 or 0: {((true == -1) | (true == 0)).mean():.2f})")
        print(f"{'model':<24} exact  near   err  wrong<=1  ax(-1,0)  ax(else)  seeds")
        for name, rows in per.items():
            m = np.nanmean(rows, 0)
            print(f"{name:<24} {m[0]:.2f}  {m[1]:.2f}  {m[2]:5.2f}    {m[3]:.2f}      {m[4]:.2f}      {m[5]:.2f}     {len(rows)}")
    out.close()


if __name__ == "__main__":
    sys.exit(main())
