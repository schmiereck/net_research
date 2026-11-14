"""Shape search (robot_finds*): where do the wrong gaze steps land?

    python scripts/finds_error_eval.py [--task robot_finds_in_f32] [--seeds 0 1 2]

For every checkpoint in results/checkpoints/<task>/ (mean over the seeds of a model), on all 3 x n (scene, wanted
body) pairs of the test file. Every answer falls into exactly one class (checked in this order):
    exact   the step to the wanted body (the usual score)
    close   at most one cell off in each axis from the wanted body: right body, step not exact
    other   at most one cell off from one of the two OTHER bodies of the scene: wrong body chosen
    lost    anywhere else
    right   exact + close: the wanted body was found
"+ref" nets get the picture of the wanted body, "+cmd" / "+cell" nets its shape as a one-hot command (name given
from outside), so the difference between the two is the cost of reading and comparing the picture.
-> results/finds_error.jsonl
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


def decode(x, spec):
    """Logits or targets of a step task -> [n, 2] signed steps (8 bits, or for *_pop / *_hot the strongest of 16
    units per axis)."""
    if spec.pop:
        return x.reshape(len(x), 2, 16).argmax(-1).astype(np.int64) - 8
    return steps(x > 0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", default="robot_finds_in_f32")
    ap.add_argument("--seeds", nargs="+", type=int, default=[0, 1, 2])
    a = ap.parse_args()
    task = make_task(a.task)
    d = task._load(f"{task.files[0]}_test")
    n = len(d["obs"])
    i = np.tile(np.arange(n), 3)
    k = np.repeat(np.arange(3), n)
    b = task.make(d, i, k, view=0)
    c = d["cells"][i].astype(np.int64)
    pos = c[:, :6].reshape(-1, 3, 2)                                 # steps to the three bodies
    r = np.arange(len(i))
    assert (steps(b["target"][0]) == pos[r, k]).all()                # make() gives the 8 bits for *_pop too
    keys = ("exact", "close", "other", "lost", "right")
    per = defaultdict(list)
    out = open(ROOT / "results" / "finds_error.jsonl", "a")
    for p in sorted((ROOT / "results" / "checkpoints" / a.task).glob("*.pt")):
        name, seed = re.fullmatch(r"(.+)_s(\d+)", p.stem).groups()
        if int(seed) not in a.seeds:
            continue
        model = load_checkpoint(name, a.task, int(seed))
        extra = {"ref": torch.tensor(b["ref"])} if "+ref" in name else {"cmd": torch.tensor(b["cmd"])}
        lg = []
        with torch.no_grad():
            for s in range(0, len(i), 1000):
                e = {q: v[:, s:s + 1000] for q, v in extra.items()}
                lg.append(run_sequence(model, torch.tensor(b["obs"][:, s:s + 1000]), **e)[0][0])
        pred = decode(torch.cat(lg)[:, task.spec.out_slice].numpy(), task.spec)
        dist = np.abs(pred[:, None] - pos).max(-1)                   # [N, 3] distance to each body (cells)
        own = dist[r, k]
        oth = np.where(np.arange(3)[None] == k[:, None], 99, dist).min(1)
        exact = own == 0
        close = ~exact & (own <= 1)
        other = ~exact & ~close & (oth <= 1)
        lost = ~exact & ~close & ~other
        row = [exact.mean(), close.mean(), other.mean(), lost.mean(), (exact | close).mean()]
        per[name].append(row)
        out.write(json.dumps({"task": a.task, "model": name, "seed": int(seed),
                              **{q: round(float(v), 4) for q, v in zip(keys, row)}}) + "\n")
    out.close()
    print(f"{a.task}: {len(i)} pairs")
    print(f"{'model':<26} exact  close  other  lost   right  seeds")
    for name, rows in per.items():
        m = np.mean(rows, 0)
        print(f"{name:<26} {m[0]:.2f}   {m[1]:.2f}   {m[2]:.2f}   {m[3]:.2f}   {m[4]:.2f}   {len(rows)}")


if __name__ == "__main__":
    sys.exit(main())
