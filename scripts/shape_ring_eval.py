"""Shape recognition by distance of the body from the centre of the fovea (robot_shape_edge, robot_shape_edge_f32).

    python scripts/shape_ring_eval.py [--models cnn vit ... cnn+ret3 ...] [--seeds 0 1 2]

Reads the checkpoints of the bench runs and the test set data/robot/shapeedge_test.npz; ring = cells[:, 1] =
max(|column|, |row|) of the body relative to the centre, in cells. Up to ring 5 the cells have full resolution,
beyond they get coarser. Prints accuracy per ring (mean over seeds); chance is 0.2.
-> results/shape_ring.jsonl
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", nargs="+", default=["cnn", "vit", "layer_s", "hier_s",
                                                    "cnn+ret0", "vit+ret0", "layer_s+ret0", "hier_s+ret0",
                                                    "cnn+ret3", "vit+ret3", "layer_s+ret3", "hier_s+ret3"])
    ap.add_argument("--seeds", nargs="+", type=int, default=[0, 1, 2])
    ap.add_argument("--suffix", default="", help='"_big" for the nets trained on 48000 images')
    a = ap.parse_args()
    d = np.load(ROOT / "data" / "robot" / "shapeedge_test.npz")
    tgt, ring = d["cells"][:, 0].astype(np.int64), d["cells"][:, 1]
    rings = sorted(set(ring.tolist()))
    print(f"{'model':<14}" + "".join(f"  r{r}" + " " * 2 for r in rings) + "   all      n per ring: "
          + " ".join(str(int((ring == r).sum())) for r in rings))
    out = open(ROOT / "results" / "shape_ring.jsonl", "a")
    for name in a.models:
        fine = "+ret" in name or "+rez" in name
        task = ("robot_shape_edge_f32" if fine else "robot_shape_edge") + a.suffix
        spec, key = make_task(task).spec, "f32" if fine else "obs"
        obs = torch.tensor(d[key].astype(np.float32) / 255.0)[None]
        acc = []
        for s in a.seeds:
            model = load_checkpoint(name, task, s)
            if model is None:
                continue
            with torch.no_grad():
                lg, _ = run_sequence(model, obs)
            ok = (lg[0][:, spec.out_slice].argmax(-1).numpy() == tgt)
            row = [float(ok[ring == r].mean()) for r in rings] + [float(ok.mean())]
            acc.append(row)
            out.write(json.dumps({"model": name, "task": task, "seed": s, "rings": rings,
                                  "acc": [round(v, 4) for v in row[:-1]], "all": round(row[-1], 4)}) + "\n")
        if acc:
            m = np.mean(acc, 0)
            print(f"{name:<14}" + "".join(f" {v:.2f} " for v in m[:-1]) + f"  {m[-1]:.2f}   ({len(acc)} seeds)")
    out.close()


if __name__ == "__main__":
    sys.exit(main())
