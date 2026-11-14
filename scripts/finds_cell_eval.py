"""Shape search on the inner scenes: why is the gaze step so often ONE cell off?

    python scripts/finds_cell_eval.py [--task robot_finds_in_f32] [--seeds 0 1 2]

Needs data/robot/<scenes>_test_pos.npz (made in the robot project from the same scenes; <scenes> = gazeshapein or
gazeshapec): for every body the
distance in pixels from its projected origin to the nearest sampling point of the fovea (d1) and to the second
nearest (d2). margin = d2 - d1: near 0 the body lies on the border between two cells, and the "right" cell is
decided by a fraction of a pixel (one cell = 4 px, one pixel of the 32 x 32 view = 2 px).
Per net (mean over seeds), over the answers that found the right body (exact or one cell off):
    exact share by margin band, by shape of the wanted body, and which axis is off (dx / dy / both).
-> results/finds_cell.jsonl
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
from netresearch.tasks.robot import data_path  # noqa: E402
from netresearch.train import load_checkpoint, run_sequence  # noqa: E402
from finds_error_eval import decode  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
BANDS = (0.0, 0.25, 0.5, 1.0, 2.0, 99.0)                             # margin in pixels
SHAPES = ("cube", "L", "U", "T", "cross")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", default="robot_finds_in_f32")
    ap.add_argument("--seeds", nargs="+", type=int, default=[0, 1, 2])
    a = ap.parse_args()
    task = make_task(a.task)
    d = task._load(f"{task.files[0]}_test")
    g = np.load(data_path(f"{task.files[0]}_test_pos.npz"))
    assert (g["cells"] == d["cells"]).all(), "position file belongs to other scenes"
    n = len(d["obs"])
    i, k = np.tile(np.arange(n), 3), np.repeat(np.arange(3), n)
    b = task.make(d, i, k, view=0)
    c = d["cells"][i].astype(np.int64)
    r = np.arange(len(i))
    true = c[:, :6].reshape(-1, 3, 2)[r, k]
    margin = (g["d2"] - g["d1"])[i, k]
    shape = c[r, 9 + k]
    band = np.digitize(margin, BANDS[1:-1])
    print(f"{a.task}: {len(i)} pairs; share per margin band "
          + " ".join(f"{(band == j).mean():.2f}" for j in range(len(BANDS) - 1)))
    per = defaultdict(list)
    out = open(ROOT / "results" / "finds_cell.jsonl", "a")
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
        dd = np.abs(decode(torch.cat(lg)[:, task.spec.out_slice].numpy(), task.spec) - true)
        found, exact = dd.max(1) <= 1, dd.max(1) == 0
        off = found & ~exact
        row = {"by_margin": [float(exact[found & (band == j)].mean()) for j in range(len(BANDS) - 1)],
               "by_shape": [float(exact[found & (shape == j)].mean()) for j in range(len(SHAPES))],
               "axis": [float(((dd[:, 0] == 1) & (dd[:, 1] == 0))[off].mean()),
                        float(((dd[:, 0] == 0) & (dd[:, 1] == 1))[off].mean()),
                        float(((dd[:, 0] == 1) & (dd[:, 1] == 1))[off].mean())]}
        per[name].append(row)
        out.write(json.dumps({"task": a.task, "model": name, "seed": int(seed),
                              **{q: [round(x, 4) for x in v] for q, v in row.items()}}) + "\n")
    out.close()
    f = lambda v: " ".join(f"{x:.2f}" for x in v)                    # noqa: E731
    print("exact among found, by margin (px) " + " | ".join(f"{BANDS[j]}-{BANDS[j + 1]}" for j in range(len(BANDS) - 1)))
    print(f"{'model':<26} by margin                 by shape ({' '.join(SHAPES)})   off in dx / dy / both")
    for name, rows in per.items():
        m = {q: np.mean([x[q] for x in rows], 0) for q in rows[0]}
        print(f"{name:<26} {f(m['by_margin'])}  {f(m['by_shape'])}  {f(m['axis'])}")


if __name__ == "__main__":
    sys.exit(main())
