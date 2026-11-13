"""Reading the shape at a named place of the search scene (robot_shape_at, robot_shape_at_f32): where does it fail?

    python scripts/shape_at_eval.py [--models cnn+cmd ... cnn+cmd+rez3 ...] [--seeds 0 1 2]

Reads the checkpoints of the bench runs and all 3 x 3000 (scene, body) pairs of data/robot/gazeshape_test.npz.
Per net (mean over seeds):
    all      accuracy (chance 0.2)
    in/out   accuracy for bodies up to ring 5 (full resolution) and beyond (ring = max(|dx|, |dy|) in cells)
    near/far accuracy when the nearest other body is closer than / at least NEAR cells away
    other    share of the errors that name the shape of one of the two OTHER bodies of the scene (two of the
             four wrong classes are in the scene, so blind guessing gives 0.5)
-> results/shape_at.jsonl
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np
import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from netresearch.tasks import make_task  # noqa: E402
from netresearch.train import load_checkpoint, run_sequence  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
NEAR = 4


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", nargs="+", default=["cnn+cmd", "vit+cmd", "layer_s+cell", "hier_s+cell",
                                                    "cnn+cmd+rez3", "vit+cmd+rez3", "layer_s+cell+rez3",
                                                    "hier_s+cell+rez3"])
    ap.add_argument("--seeds", nargs="+", type=int, default=[0, 1, 2])
    ap.add_argument("--suffix", default="", help='"_in" / "_in12": scenes with all bodies up to ring 5')
    a = ap.parse_args()
    out = open(ROOT / "results" / "shape_at.jsonl", "a")
    print(f"{'model':<20}  all    in   out  near   far  other     (near: next body < {NEAR} cells)")
    for name in a.models:
        tname = "robot_shape_at" + a.suffix + ("_f32" if "+rez" in name or "+ret" in name else "")
        task = make_task(tname)
        d = task._load(task.files[0] + "_test")
        n = len(d["obs"])
        c = d["cells"].astype(np.int64)
        pos, shp = c[:, :6].reshape(n, 3, 2), c[:, 9:12]
        rows = []
        for s in a.seeds:
            model = load_checkpoint(name, tname, s)
            if model is None:
                continue
            ok, oth, ring, gap = [], [], [], []
            for k in range(3):
                b = task.make(d, np.arange(n), np.full(n, k))
                with torch.no_grad():
                    lg, _ = run_sequence(model, torch.tensor(b["obs"]), cmd=torch.tensor(b["cmd"]))
                pred = lg[0][:, task.spec.out_slice].argmax(-1).numpy()
                others = np.delete(shp, k, axis=1)
                ok.append(pred == shp[:, k])
                oth.append((pred[:, None] == others).any(1))
                ring.append(np.abs(pos[:, k]).max(1))
                gap.append(np.abs(np.delete(pos, k, axis=1) - pos[:, k:k + 1]).max(2).min(1))
            ok, oth, ring, gap = (np.concatenate(v) for v in (ok, oth, ring, gap))
            row = [ok.mean(), ok[ring <= 5].mean(), ok[ring > 5].mean() if (ring > 5).any() else float("nan"), ok[gap < NEAR].mean(),
                   ok[gap >= NEAR].mean(), oth[~ok].mean()]
            rows.append(row)
            out.write(json.dumps({"model": name, "task": tname, "seed": s, **{
                k: round(float(v), 4) for k, v in zip(("all", "in", "out", "near", "far", "other"), row)},
                "n_near": int((gap < NEAR).sum()), "n_in": int((ring <= 5).sum()), "n": int(len(ok))}) + "\n")
        if rows:
            print(f"{name:<20}" + "".join(f" {v:.2f} " for v in np.mean(rows, 0)) + f"   ({len(rows)} seeds)")
    out.close()


if __name__ == "__main__":
    sys.exit(main())
