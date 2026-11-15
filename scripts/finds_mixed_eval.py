"""Single step on the mixed search scenes (robot_finds_m_f32), split by kind of scene.

    python scripts/finds_mixed_eval.py [--seeds 0 1 2]

The mixed test set holds first the centroid scenes (gazeshapec, gaze between the three bodies), then the scenes
in which the gaze hangs on one body (gazeshapeu: body 0 lies 0..5 cells from the centre, the other two anywhere
in the field of view). Per net: exact / near on the old scenes, on body 0 of the new scenes (also by its distance
from the centre) and on the two other bodies of the new scenes. -> results/finds_mixed.jsonl
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
from netresearch.tasks.servo import decode_step  # noqa: E402
from netresearch.train import load_checkpoint, run_sequence  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
TASK = "robot_finds_m_f32"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", nargs="+", type=int, default=[0, 1, 2])
    a = ap.parse_args()
    task = make_task(TASK)
    d = task._load(f"{task.files[0]}_test")
    n = len(d["obs"])
    i, k = np.tile(np.arange(n), 3), np.repeat(np.arange(3), n)
    b = task.make(d, i, k, view=0)
    true = d["cells"][i].astype(np.int64)[:, :6].reshape(-1, 3, 2)[np.arange(len(i)), k]
    ring = np.abs(true).max(1)
    old, own, rim = i < n // 2, (i >= n // 2) & (k == 0), (i >= n // 2) & (k > 0)
    per = defaultdict(list)
    with open(ROOT / "results" / "finds_mixed.jsonl", "a") as out:
        for p in sorted((ROOT / "results" / "checkpoints" / TASK).glob("*.pt")):
            name, seed = re.fullmatch(r"(.+)_s(\d+)", p.stem).groups()
            if int(seed) not in a.seeds:
                continue
            model = load_checkpoint(name, TASK, int(seed))
            lg = []
            with torch.no_grad():
                for s in range(0, len(i), 1000):
                    lg.append(run_sequence(model, torch.tensor(b["obs"][:, s:s + 1000]),
                                           ref=torch.tensor(b["ref"][:, s:s + 1000]))[0][0])
            e = np.abs(decode_step(torch.cat(lg)[:, task.spec.out_slice].numpy(), task.spec) - true).max(1)
            row = {"old": [(e[old] == 0).mean(), (e[old] <= 1).mean()], "own": [(e[own] == 0).mean(), (e[own] <= 1).mean()],
                   "rim": [(e[rim] == 0).mean(), (e[rim] <= 1).mean()],
                   "own_exact_by_ring": [(e[own & (ring == r)] == 0).mean() for r in range(6)],
                   "rim_exact_by_ring": [(e[rim & (ring == r)] == 0).mean() if (rim & (ring == r)).sum() > 30 else float("nan")
                                         for r in range(9)]}
            row = {q: [round(float(x), 4) for x in v] for q, v in row.items()}
            per[name].append(row)
            out.write(json.dumps({"task": TASK, "model": name, "seed": int(seed), **row}) + "\n")
    f = lambda v: " ".join(f"{x:.2f}" for x in v)                       # noqa: E731
    print(f"{'model':<24} old exact near | body at the gaze exact near | rim bodies exact near | "
          "body at the gaze, exact by ring 0..5 | rim bodies, exact by ring 0..8")
    for name, rows in per.items():
        m = {q: np.mean([x[q] for x in rows], 0) for q in rows[0]}
        print(f"{name:<24} {f(m['old'])} | {f(m['own'])} | {f(m['rim'])} | {f(m['own_exact_by_ring'])} | {f(m['rim_exact_by_ring'])}")


if __name__ == "__main__":
    sys.exit(main())
