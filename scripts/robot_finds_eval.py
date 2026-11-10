"""robot_finds: does the address a net forms from a picture carry the SHAPE of the object?

    python scripts/robot_finds_eval.py [--models vit+ref cnn+ref ...] [--seeds 0 1 2]

Search task (exact match / within +-1 cell on test scenes):
    test     trained shapes, the wanted object shown in view 0
    view1    the same, shown in the other view (another scene and rotation): should be the same
    held     scenes with the Y (never trained), the Y shown
    control  the same scenes, a trained shape shown
    wrong    test scenes, the picture of ANOTHER object of the scene; share of answers that still hit the asked
             object (near 0 = the net follows the picture)
Address itself (only "+ref" nets), per scene with its three objects:
    same     is the address of view 0 of an object nearest to the address of ITS view 1 among the three
             view-1 addresses of the scene? (chance 1/3; 1 = two pictures of one object give the same address)
    same_y   the same for the scenes with the Y, counted for the Y only
    shape    shape read from the address by a linear classifier (fit on half of the test scenes, scored on the
             other half; 5 trained shapes, chance 0.2)
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
    return {"exact": round(float((e.sum(1) == 0).mean()), 4), "within1": round(float((e.max(1) <= 1).mean()), 4)}


def addresses(model, d):
    """-> z [N, 3 objects, 2 views, N_CMD]."""
    with torch.no_grad():
        return model.ref_enc(torch.from_numpy(d["refs"].astype(np.float32) / 255.0)).numpy()


def same_object(z, only=None):
    """Share of (scene, object) whose view-0 address is nearest to its own view-1 address."""
    dist = ((z[:, :, None, 0] - z[:, None, :, 1]) ** 2).sum(-1)            # N, object (view 0), object (view 1)
    hit = dist.argmin(-1) == np.arange(3)
    if only is not None:
        return float(hit[np.arange(len(z)), only].mean())
    return float(hit.mean())


def shape_readout(z, shapes):
    x, y = z[:, :, 0].reshape(-1, z.shape[-1]), shapes.reshape(-1)
    h = len(x) // 2
    A = np.c_[x, np.ones(len(x))]
    w = np.linalg.lstsq(A[:h], np.eye(6)[y[:h]], rcond=None)[0]
    return float(((A[h:] @ w).argmax(1) == y[h:]).mean())


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--models", nargs="+", default=["vit+ref", "cnn+ref", "layer_s_sp4+cell+ref", "vit+cmd", "cnn+cmd"])
    ap.add_argument("--seeds", nargs="+", type=int, default=[0, 1, 2])
    ap.add_argument("--out", default="results/robot_finds_eval.jsonl")
    a = ap.parse_args()
    task = make_task("robot_finds")
    d, dh = task._load("gazeshape_test"), task._load("gazeshapeheld_test")
    n = len(d["obs"])
    idx, k = np.arange(n), np.random.default_rng(0).integers(0, 3, size=n)
    sets = {"test": to_t(task.make(d, idx, k, 0)), "view1": to_t(task.make(d, idx, k, 1)),
            "held": to_t(task.held_out()), "control": to_t(task.held_out(other=True))}
    wrong = to_t(task.make(d, idx, (k + 1) % 3, 0))
    rows = []
    for m in a.models:
        for s in a.seeds:
            model = load_checkpoint(m, "robot_finds", s)
            if model is None:
                continue
            r = {"model": m, "seed": s}
            for name, b in sets.items():
                sc = score(model, b)
                r[name], r[name + "_w1"] = sc["exact"], sc["within1"]
            r["wrong"] = score(model, wrong, sets["test"]["target"])["exact"]
            if hasattr(model, "ref_enc"):
                z = addresses(model, d)
                r["same"] = round(same_object(z), 4)
                r["same_y"] = round(same_object(addresses(model, dh), dh["cells"][:, 12].astype(np.int64)), 4)
                r["shape"] = round(shape_readout(z, d["cells"][:, 9:12].astype(np.int64)), 4)
            rows.append(r)
    with open(a.out, "w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    import pandas as pd
    with pd.option_context("display.width", 220):
        print(pd.DataFrame(rows).groupby("model").mean(numeric_only=True).drop(columns="seed").round(2).to_string())


if __name__ == "__main__":
    main()
