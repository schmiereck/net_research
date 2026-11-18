"""Form or place? What the nets of a run with several goals keep of each goal once the scene is in view, and where.

    python scripts/loop_where_probe.py --task robot_loop_three_f32 --ckpt robot_loop_three_f32_24k \
        --models layer_s+cell+refl+rez3 layer_s_sp4+cell+refl+rez3 --seeds 0 1 2 3 4 7

Follow-up to scripts/loop_goals_probe.py. The nets run over ORACLE runs (every net sees the same views): from the
start gaze of a scene the eye takes the true step to the goal of the moment (3 steps per goal); before that the G
cue steps with the goal pictures (view 0), blank image. After every step a linear ridge read-out (as in
loop_state_probe.py, fitted on half of the scenes, measured on the other half) is asked for
    shape   the shape of goal k (accuracy; goal k only in runs where it is a body not named before)
    place   where goal k lies, as pixel offset from the gaze centre (R^2, mean of both axes); same runs
    nogoal  the place of the body that is NO goal (runs A, B, A only): a body in view that the net need not keep;
            the control for "place" (what the view alone gives)
from the whole state ("all") and from every part of the state alone ("p0", "p1", ...; for layer_s_sp4 p0 = the
grid, p1 = the scratchpad, 4 values per cell), and from 128 random values of p0 ("p0r128", the size of the
scratchpad: is the scratchpad special or just 128 values?). Floor "view": the same read-outs from the state the net reaches from a fresh memory after only
the current view, with a blank picture (what the view alone tells, e.g. through how the bodies of a scene lie).
-> results/loop_where_probe.jsonl, one row per net and seed: read[src][q][t][k].
"""
import argparse
import itertools
import json
import sys
from pathlib import Path

import numpy as np
import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from netresearch.tasks import fovea as fv  # noqa: E402
from netresearch.tasks.registry import TASKS  # noqa: E402
from netresearch.tasks.robot import data_path  # noqa: E402
from netresearch.train import load_checkpoint, run_sequence  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from finds_loop_eval import inside, measure  # noqa: E402
from loop_state_probe import ridge  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def acc(x, y, tr, te):
    p = ridge(x[tr], np.eye(5)[y[tr]], x[te], lam=0.01)
    return round(float((p.argmax(1) == y[te]).mean()), 3)


def r2(x, y, tr, te):
    q = ridge(x[tr], y[tr], x[te], lam=0.01)
    yt = y[te]
    return round(float((1.0 - ((q - yt) ** 2).sum(0) / ((yt - yt.mean(0)) ** 2).sum(0)).mean()), 3)


def runs(d, G, n, rng):
    """Oracle runs: scene index, goal order, views [T, n, 3, 32, 32] uint8, place of every body [T, n, 3, 2]."""
    orders = [o for o in itertools.product(range(3), repeat=G) if all(x != y for x, y in zip(o, o[1:]))]
    pairs = [(i, o) for i in range(len(d["pos"])) for o in range(len(orders))]
    pick = sorted(rng.choice(len(pairs), size=n, replace=False))
    T, steps = G + 3 * G, 3 * G
    views = np.zeros((T, n, 3, 32, 32), np.uint8)
    place = np.zeros((T, n, 3, 2), np.float32)
    scene, order = np.zeros(n, np.int64), np.zeros((n, G), np.int64)
    sat_cache = {}
    for r, p in enumerate(pick):
        i, o = pairs[p]
        scene[r], order[r] = i, orders[o]
        if i not in sat_cache:
            sat_cache = {i: fv.integral(d["big"][i])}
        gaze, pos = d["gaze"][i].astype(float), d["pos"][i]
        for s in range(steps):
            t = G + s
            views[t, r] = fv.sample_fine(sat_cache[i], gaze)
            place[t, r] = pos - fv.centre_px(gaze)
            dx, dy = measure(gaze, pos, order[r, s // 3])[:2]
            g = fv.shift(gaze, dx, dy)
            gaze = g if inside(g) else gaze
        place[:G, r] = place[G, r]                                     # not in view yet; unused
    return scene, order, views, place


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", default="robot_loop_three_f32")
    ap.add_argument("--ckpt", default=None)
    ap.add_argument("--models", nargs="+", required=True)
    ap.add_argument("--seeds", nargs="+", type=int, default=[0, 1, 2])
    ap.add_argument("--n", type=int, default=3000, help="oracle runs")
    ap.add_argument("--images", default="gazeshapec")
    a = ap.parse_args()
    task = TASKS[a.task]()
    G, T = task.G, task.T
    d = np.load(data_path(f"{a.images}_test_img.npz"))
    d = {q: d[q] for q in ("gaze", "pos", "cells", "refs", "big")}
    rng = np.random.default_rng(0)
    scene, order, views, place = runs(d, G, a.n, rng)
    us = np.unique(scene)
    tr = np.isin(scene, rng.permutation(us)[: len(us) // 2])
    te = ~tr
    shape = d["cells"][scene[:, None], 9 + order].astype(np.int64)                         # [n, G]
    new = [np.ones(a.n, bool)] + [~(order[:, :k] == order[:, k:k + 1]).any(1) for k in range(1, G)]
    ret = order[:, -1] == order[:, 0]
    nogoal = np.array([[k for k in range(3) if k not in o][0] if r else 0 for o, r in zip(order, ret)])
    ref = np.zeros((T, a.n, 3, 16, 16), np.float32)
    for k in range(G):
        ref[k] = d["refs"][scene, order[:, k], 0].astype(np.float32) / 255.0
    obs, ref = torch.tensor(views.astype(np.float32) / 255.0), torch.tensor(ref)
    print(f"{a.n} oracle runs, {len(us)} scenes; A, B, A runs: {int(ret.sum())}", flush=True)
    with open(ROOT / "results" / "loop_where_probe.jsonl", "a") as out:
        for name in a.models:
            for seed in a.seeds:
                model = load_checkpoint(name, a.ckpt or a.task, seed)
                if model is None:
                    print(f"  {name} s{seed}: no checkpoint", flush=True)
                    continue
                model.eval()
                parts, view, st = [], [], None
                flat = lambda s: [p.reshape(a.n, -1).double().numpy()                       # noqa: E731
                                  for p in (s if isinstance(s, (tuple, list)) else [s]) if p.numel()]
                with torch.no_grad():
                    for t in range(T):
                        _, st = run_sequence(model, obs[t:t + 1], state=st, ref=ref[t:t + 1])
                        parts.append(flat(st))
                        _, s0 = run_sequence(model, obs[t:t + 1], state=None, ref=torch.zeros_like(ref[t:t + 1]))
                        view.append(np.concatenate(flat(s0), 1))
                P = len(parts[0])
                cols = np.random.default_rng(1).choice(parts[0][0].shape[1], size=128, replace=False)
                src = {"all": lambda t: np.concatenate(parts[t], 1), "view": lambda t: view[t]}
                if P > 1:
                    for j in range(P):
                        src[f"p{j}"] = (lambda j: lambda t: parts[t][j])(j)
                    src["p0r128"] = lambda t: parts[t][0][:, cols]
                read = {}
                for s, get in src.items():
                    read[s] = {"shape": [], "place": [], "nogoal": []}
                    for t in range(T):
                        x = get(t)
                        read[s]["shape"].append([acc(x, shape[:, k], tr & new[k], te & new[k]) for k in range(G)])
                        if t < G:
                            read[s]["place"].append([None] * G)
                            read[s]["nogoal"].append(None)
                            continue
                        read[s]["place"].append([r2(x, place[t, np.arange(a.n), order[:, k]], tr & new[k], te & new[k])
                                                 for k in range(G)])
                        read[s]["nogoal"].append(r2(x, place[t, np.arange(a.n), nogoal], tr & ret, te & ret))
                row = {"task": a.task, "ckpt": a.ckpt or a.task, "model": name, "seed": seed, "n": a.n,
                       "parts": [int(p.shape[1]) for p in parts[0]], "read": read}
                out.write(json.dumps(row) + "\n")
                out.flush()
                print(f"{name} s{seed}: parts {row['parts']}", flush=True)
                for s in read:
                    print(f"  [{s}] step: shape A B C | place A B C | no-goal place", flush=True)
                    for t in range(T):
                        sh = " ".join(f"{v:.2f}" for v in read[s]["shape"][t])
                        pl = " ".join("  -  " if v is None else f"{v:5.2f}" for v in read[s]["place"][t])
                        ng = read[s]["nogoal"][t]
                        print(f"    {t:2d}: {sh} | {pl} | {'  -' if ng is None else f'{ng:5.2f}'}", flush=True)


if __name__ == "__main__":
    sys.exit(main())
