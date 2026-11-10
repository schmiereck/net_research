"""Why is robot_reach hard? Same images, three asked outputs, two training-set sizes.

    python scripts/robot_reach_probe.py --data <dir with reach_train.npz / reach_test.npz incl. cells>
        [--models cnn layer_s] [--targets hand cube diff] [--sizes 12000 48000] [--updates 6000]

    hand   cell (column, row) of the grasp point          (can the net read the hand from the arm's shape?)
    cube   cell (column, row) of the red cube             (as robot_gaze, but with the arm near the cube)
    diff   cube - hand, the robot_reach label             (both readings and the subtraction)
Scored on the test scenes: exact, within +-1 cell, mean absolute error in cells.
"""
import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from netresearch.models import build_model  # noqa: E402
from netresearch.tasks.servo import command_bits  # noqa: E402
from netresearch.train import make_opt, run_sequence  # noqa: E402

W = np.array([8, 4, 2, 1])


def labels(d, target):
    c = d["cells"].astype(np.int64)
    return {"hand": c[:, 0:2], "cube": c[:, 2:4], "diff": d["target"].astype(np.int64)}[target]


def decode(bits, signed):
    v = (bits.reshape(-1, 2, 4) * W).sum(-1)
    return np.where(v > 7, v - 16, v) if signed else v


def run(model_name, target, n, updates, tr, te, seed=0):
    torch.manual_seed(seed)
    rng = np.random.default_rng(seed)
    model = build_model(model_name, seed=seed)
    x = torch.from_numpy(tr["obs"][:n].astype(np.float32) / 255)
    y = torch.from_numpy(command_bits(*labels(tr, target)[:n].T))
    opt, sched = make_opt(model, updates, 2e-3)
    t0, loss_sum = time.time(), 0.0
    for i in range(updates):
        idx = torch.from_numpy(rng.integers(0, n, size=64))
        lg, _ = run_sequence(model, x[idx][None])
        loss = torch.nn.functional.binary_cross_entropy_with_logits(lg[0, :, 18:26], y[idx])
        opt.zero_grad()
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        opt.step()
        sched.step()
        loss_sum += loss.item() if i >= updates - 200 else 0.0
    model.eval()
    with torch.no_grad():
        lg, _ = run_sequence(model, torch.from_numpy(te["obs"].astype(np.float32) / 255)[None])
    signed = target == "diff"
    p = decode((lg[0, :, 18:26] > 0).numpy().astype(np.int64), signed)
    e = np.abs(p - labels(te, target))
    return {"model": model_name, "target": target, "n": n, "updates": updates,
            "exact": round(float((e.sum(1) == 0).mean()), 4), "within1": round(float((e.max(1) <= 1).mean()), 4),
            "mae": round(float(e.mean()), 3), "train_loss": round(loss_sum / 200, 4), "time": round(time.time() - t0)}


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--data", required=True)
    ap.add_argument("--models", nargs="+", default=["cnn", "layer_s"])
    ap.add_argument("--targets", nargs="+", default=["hand", "cube", "diff"])
    ap.add_argument("--sizes", nargs="+", type=int, default=[12000, 48000])
    ap.add_argument("--updates", type=int, default=6000)
    ap.add_argument("--out", default="results/robot_reach_probe.jsonl")
    a = ap.parse_args()
    torch.set_num_threads(1)
    tr, te = (dict(np.load(Path(a.data) / f"reach_{s}.npz")) for s in ("train", "test"))
    for m in a.models:
        for t in a.targets:
            for n in a.sizes:
                r = run(m, t, n, a.updates, tr, te)
                print(r, flush=True)
                with open(a.out, "a") as f:
                    f.write(json.dumps(r) + "\n")


if __name__ == "__main__":
    main()
