"""What do the nets keep of the cue? Linear probes on the state along the sequences of the memory gaze loop.

    python scripts/loop_state_probe.py [--tasks robot_loop_cue_f32 robot_loop_blind_f32]
                                       [--models layer_s+cell+ref+rez3 hier_s+cell+ref+rez3] [--n 4500]

Nothing is trained but the probes. The stored nets (results/checkpoints/<task>) run over the test sequences of
the task (teacher run, so every net sees the same images): cue step, then 4 steps without the picture. After
every step the state is taken and a linear read-out (ridge regression on one half of the sequences, measured on
the other half) is asked for
    shape   which of the 5 shapes is wanted (chance 0.2; 0.33 for someone who sees the three bodies of the scene)
    step    the gaze step (dx, dy) that is right at the FIRST step of the run (R^2, mean of both axes)
"ref" is the same read-out on the output of the picture encoder at the cue step (16 values), "all" on the whole
state, "L0".. on one layer of the grid alone.
-> results/loop_state_probe.json (one row per task, net and seed)
"""
import argparse
import json
import re
import sys
from pathlib import Path

import numpy as np
import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from netresearch.tasks import make_task  # noqa: E402
from netresearch.train import load_checkpoint, run_sequence  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def ridge(xa, ya, xb, lam=1.0):
    """Ridge regression with intercept, fitted on (xa, ya), predictions for xb. Features are standardised."""
    mu, sd = xa.mean(0), xa.std(0) + 1e-6
    xa, xb = (xa - mu) / sd, (xb - mu) / sd
    ym = ya.mean(0)
    if xa.shape[1] > xa.shape[0]:                                      # dual form
        k = xa @ xa.T
        w = xa.T @ np.linalg.solve(k + lam * len(xa) * np.eye(len(xa)), ya - ym)
    else:
        w = np.linalg.solve(xa.T @ xa + lam * len(xa) * np.eye(xa.shape[1]), xa.T @ (ya - ym))
    return xb @ w + ym


def probes(x, shape, step, half):
    """x [N, F] -> accuracy of the shape read-out, R^2 of the step read-out (on the second half)."""
    x = x.astype(np.float64)
    p = ridge(x[:half], np.eye(5)[shape[:half]], x[half:], lam=0.01)
    acc = float((p.argmax(1) == shape[half:]).mean())
    q = ridge(x[:half], step[:half].astype(np.float64), x[half:], lam=0.01)
    r2 = 1.0 - ((q - step[half:]) ** 2).sum(0) / ((step[half:] - step[half:].mean(0)) ** 2).sum(0)
    return round(acc, 4), round(float(r2.mean()), 4)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tasks", nargs="+", default=["robot_loop_cue_f32", "robot_loop_blind_f32"])
    ap.add_argument("--models", nargs="+", default=["layer_s+cell+ref+rez3", "hier_s+cell+ref+rez3"])
    ap.add_argument("--n", type=int, default=4500)
    a = ap.parse_args()
    rows = []
    for tname in a.tasks:
        task = make_task(tname)
        d = task._load("test")
        n = min(a.n, len(d["steps"]))
        idx, half = np.arange(n), n // 2
        b = task.make(d, idx, view=0)
        obs, ref = torch.tensor(b["obs"]), torch.tensor(b["ref"])
        shape, step = d["shape"][:n].astype(np.int64), d["steps"][:n, 0].astype(np.float64)
        for p in sorted((ROOT / "results" / "checkpoints" / tname).glob("*.pt")):
            name, seed = re.fullmatch(r"(.+)_s(\d+)", p.stem).groups()
            if name not in a.models:
                continue
            model = load_checkpoint(name, tname, int(seed))
            row = {"task": tname, "model": name, "seed": int(seed), "n": n}
            with torch.no_grad():
                row["ref"] = probes(model.ref_enc(ref[0].float()).numpy(), shape, step, half)
                state, per = None, []
                for t in range(obs.shape[0]):
                    states = []
                    for lo in range(0, n, 500):                        # the batch in chunks, state per chunk
                        st = None if state is None else [s[lo:lo + 500] for s in state]
                        _, st = run_sequence(model, obs[t:t + 1, lo:lo + 500], state=st, ref=ref[t:t + 1, lo:lo + 500])
                        states.append(st)
                    state = [torch.cat([s[k] for s in states]) for k in range(len(states[0]))]
                    s = state[0].numpy()                               # [N, layers, cells, features]
                    r = {"all": probes(s.reshape(n, -1), shape, step, half)}
                    for layer in range(s.shape[1]):
                        r[f"L{layer}"] = probes(s[:, layer].reshape(n, -1), shape, step, half)
                    per.append(r)
            row["steps"] = per
            rows.append(row)
            print(f"{tname[11:-4]:<6}{name.split('+')[0]:<9}s{seed}  ref {row['ref'][0]:.2f}  shape after cue/1/2/3/4: "
                  + " ".join(f"{r['all'][0]:.2f}" for r in per) + "   step after cue/1: "
                  + " ".join(f"{r['all'][1]:.2f}" for r in per[:2]), flush=True)
    json.dump(rows, open(ROOT / "results" / "loop_state_probe.json", "w"), indent=1)


if __name__ == "__main__":
    sys.exit(main())
