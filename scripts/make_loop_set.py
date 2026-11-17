"""Gaze sequences for the shape search: what the eye sees along a run of several gaze steps.

    python scripts/make_loop_set.py --train data/robot/loopimg --test gazeshapec_test_img [--steps 4]

From search scenes with their camera image (robot project: export_netresearch.py --tasks gazeshapec --images) a
sequence of `steps` views is made for every scene and every wanted body: the first view is the scene as exported,
each further one is the view after a gaze step (netresearch/tasks/fovea.py). The steps come from a NOISY TEACHER,
not from a net, so the set does not depend on any trained model:
    0.70  the true step to the wanted body
    0.20  the true step, one cell off in a random direction
    0.10  the true step to one of the other two bodies (the gaze lands on the wrong body)
A step that would lose the wanted body from the field of view or leave the camera image is replaced by the true
step. The label of every view is the true step from THAT gaze to the wanted body ((0, 0) once the eye is on it).
-> data/robot/gazeloop_train.npz / gazeloop_test.npz: f32 uint8 [N, steps, 3, 32, 32], steps int8 [N, steps, 2],
   refs uint8 [N, 2, 3, 16, 16] (the two pictures of the wanted body), body int8 [N] (which of the three),
   shape int8 [N] (its shape index).

With --two: TWO wanted bodies one after the other (for the task robot_loop_two_f32). `steps` views with the first
body A as the goal, then `steps` views with the second body B as the goal, in one run of the eye; the teacher is
the same, and it keeps B in view while it goes for A (a pair where the true step to A loses B is left out).
Training: 2 ordered pairs (A, B) per scene, test: all 6.
-> data/robot/gazeloop2_train.npz / gazeloop2_test.npz: f32 [N, 2 * steps, 3, 32, 32], steps [N, 2 * steps, 2]
   (to A in the first half, to B in the second), refs [N, 2, 2, 3, 16, 16] (A and B, two pictures each),
   body int8 [N, 2], shape int8 [N, 2], scene int32 [N].

With --goals 3: three goals one after the other (robot_loop_three_f32), any sequence of the three bodies without
the same body twice in a row: A, B, C or A, B, A (12 per scene); the teacher keeps every body still to come in
view. Training: 2 of the 12 sequences per scene, test: all 12.
-> data/robot/gazeloop3_*.npz, shapes as above with 3 in place of 2.
"""
import itertools
import argparse
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from netresearch.tasks import fovea as fv  # noqa: E402
from netresearch.tasks.robot import data_path  # noqa: E402

ROOT = Path(__file__).resolve().parents[1] / "data" / "robot"
P_NEAR, P_OTHER = 0.20, 0.10
DIRS = [(dx, dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1) if (dx, dy) != (0, 0)]


def in_view(gaze, px):
    dx, dy, dist = fv.nearest_cell(gaze, px)
    return dist <= 2 * fv.K, (dx, dy)


def sequences(d, steps, rng):
    n = len(d["obs"])
    views = np.zeros((n * 3, steps, 3, 32, 32), np.uint8)
    lab = np.zeros((n * 3, steps, 2), np.int8)
    for i in range(n):
        sat = fv.integral(d["big"][i])
        pos = d["pos"][i]
        for k in range(3):
            gaze, q = d["gaze"][i].astype(float), 3 * i + k
            for t in range(steps):
                ok, true = in_view(gaze, pos[k])
                assert ok, (i, k, t)
                views[q, t], lab[q, t] = fv.sample_fine(sat, gaze), true
                u, step = rng.random(), true
                if u < P_OTHER:
                    o = (k + 1 + int(rng.integers(0, 2))) % 3
                    ok, s = in_view(gaze, pos[o])
                    step = s if ok else true
                elif u < P_OTHER + P_NEAR:
                    e = DIRS[int(rng.integers(0, len(DIRS)))]
                    step = (int(np.clip(true[0] + e[0], -8, 7)), int(np.clip(true[1] + e[1], -8, 7)))
                g = fv.shift(gaze, *step)
                if not (0 <= g[0] < fv.RES and 0 <= g[1] < fv.RES and in_view(g, pos[k])[0]):
                    g = fv.shift(gaze, *true)
                gaze = g
    body = np.tile(np.arange(3, dtype=np.int8), n)
    idx = np.repeat(np.arange(n), 3)
    return {"f32": views, "steps": lab, "refs": d["refs"][idx, body], "body": body,
            "shape": d["cells"][idx, 9 + body].astype(np.int8)}


def teacher_step(gaze, pos, k, keep, rng):
    """One step of the noisy teacher towards body k; the bodies in `keep` must stay in view. Returns the new
    gaze, or None if even the true step loses one of them."""
    ok, true = in_view(gaze, pos[k])
    u, step = rng.random(), true
    if u < P_OTHER:
        o = (k + 1 + int(rng.integers(0, 2))) % 3
        ok, s = in_view(gaze, pos[o])
        step = s if ok else true
    elif u < P_OTHER + P_NEAR:
        e = DIRS[int(rng.integers(0, len(DIRS)))]
        step = (int(np.clip(true[0] + e[0], -8, 7)), int(np.clip(true[1] + e[1], -8, 7)))
    for s in (step, true):
        g = fv.shift(gaze, *s)
        if 0 <= g[0] < fv.RES and 0 <= g[1] < fv.RES and all(in_view(g, pos[j])[0] for j in keep):
            return g
    return None


def orders(goals):
    """All goal sequences over the three bodies without the same body twice in a row: 6 for two goals, 12 for
    three (the 6 orders of all three bodies and the 6 of the kind A, B, A). With returns the last goal cannot be
    found by elimination ("the body I have not been to"); it needs the last picture."""
    return [o for o in itertools.product(range(3), repeat=goals) if all(x != y for x, y in zip(o, o[1:]))]


def sequences_two(d, steps, rng, per_scene, goals=2):
    """Runs with several goals: `steps` views towards A, then `steps` views towards B (then C)."""
    pairs = orders(goals)
    views, lab, meta, dropped = [], [], [], 0
    for i in range(len(d["obs"])):
        sat, pos = fv.integral(d["big"][i]), d["pos"][i]
        chosen = pairs if per_scene >= len(pairs) else [pairs[j] for j in rng.permutation(len(pairs))[:per_scene]]
        for order in chosen:
            gaze, v, s = d["gaze"][i].astype(float), [], []
            for t in range(goals * steps):
                k = order[t // steps]
                ok, true = in_view(gaze, pos[k])
                assert ok, (i, order, t)
                v.append(fv.sample_fine(sat, gaze))
                s.append(true)
                gaze = teacher_step(gaze, pos, k, order[t // steps:], rng)
                if gaze is None:
                    break
            if gaze is None:
                dropped += 1
                continue
            views.append(np.stack(v))
            lab.append(np.array(s, np.int8))
            meta.append((i, *order))
    m = np.array(meta)
    return {"f32": np.stack(views), "steps": np.stack(lab), "refs": d["refs"][m[:, 0][:, None], m[:, 1:]],
            "body": m[:, 1:].astype(np.int8), "shape": d["cells"][m[:, 0][:, None], 9 + m[:, 1:]].astype(np.int8),
            "scene": m[:, 0].astype(np.int32)}, dropped


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--train", help="folder with gazeshapec_train*_img.npz parts")
    ap.add_argument("--test", help="name of a test set with camera images, e.g. gazeshapec_test_img")
    ap.add_argument("--steps", type=int, default=4)
    ap.add_argument("--two", action="store_true", help="two wanted bodies one after the other (gazeloop2_*)")
    ap.add_argument("--goals", type=int, default=1, help="wanted bodies one after the other (2: as --two, 3)")
    a = ap.parse_args()
    a.goals = 2 if a.two else a.goals
    a.two = a.goals > 1
    jobs = []
    if a.train:
        jobs.append(("train", sorted(Path(a.train).glob("*_train*_img.npz")), 1))
    if a.test:
        jobs.append(("test", [data_path(a.test + ".npz")], 2))
    for split, files, seed in jobs:
        rng, parts, sizes = np.random.default_rng(seed), [], []
        for f in files:
            d = np.load(f)
            d = {q: d[q] for q in ("obs", "gaze", "pos", "cells", "refs", "big")}
            if a.two:
                p, dropped = sequences_two(d, a.steps, rng, 2 if split == "train" else 12, a.goals)
                p["scene"] += sum(n for n, _ in sizes)
                sizes.append((len(d["obs"]), dropped))
                parts.append(p)
            else:
                parts.append(sequences(d, a.steps, rng))
            print(f"  {Path(f).name}: {len(d['obs'])} scenes", flush=True)
        out = {q: np.concatenate([p[q] for p in parts]) for q in parts[0]}
        if a.two:
            np.savez_compressed(ROOT / f"gazeloop{a.goals}_{split}.npz", **out)
            m = np.abs(out["steps"]).max(-1)
            print(f"gazeloop{a.goals}_{split}: {len(m)} sequences ({sum(x for _, x in sizes)} orders left out); share of "
                  f"views with the goal in the centre cell, per step:", np.round((m == 0).mean(0), 2),
                  "at most one cell off:", np.round((m <= 1).mean(0), 2), flush=True)
            continue
        np.savez_compressed(ROOT / f"gazeloop_{split}.npz", **out)
        m = np.abs(out["steps"]).max(-1)
        print(f"gazeloop_{split}: {len(m)} sequences; share of views with the body in the centre cell, per step:",
              np.round((m == 0).mean(0), 2), "at most one cell off:", np.round((m <= 1).mean(0), 2), flush=True)


if __name__ == "__main__":
    sys.exit(main())
