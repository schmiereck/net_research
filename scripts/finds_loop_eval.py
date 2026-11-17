"""Shape search in a LOOP: the net's gaze step is carried out, the next image comes from the new gaze.

    python scripts/finds_loop_eval.py [--task robot_finds_c_f32] [--seeds 0 1 2] [--steps 4] [--scenes 1500]
                                      [--images gazeshapec]

The nets are the stored single-step nets (results/checkpoints/<task>); nothing is trained here. Needs
data/robot/<scenes>_test_img.npz (robot project: export_netresearch.py --tasks gazeshapec --n-train 0 --images):
the test scenes with the whole camera image, so the fovea can be sampled anew at any gaze (netresearch/tasks/
fovea.py, checked here bit for bit against the exported views).
One run = one scene and one wanted body (3 per scene), the picture of the wanted body stays the same. Before
every step and after the last one the true state is measured (nets with memory keep it along the run; --amnesia
wipes it before every step):
    exact   the body lies in the centre cell (right answer now: step (0, 0))
    near    at most one cell beside it
    px      distance in camera pixels from the body to the point the centre cell looks at (one cell = 4 px)
    other   another body of the scene is nearer to that point than the wanted one and the wanted one is more than
            8 px away: the gaze sits on the wrong body
    out     the gaze has left the camera image (the run stops there, counts as a miss)
and of the net's answers: rest = it answers (0, 0); flip = its step is the exact reverse of its previous one.
"oracle" takes the true step every time: what the geometry allows (cells are coarse from 5 cells outward, so
one true step does not always land in the centre cell).
Tasks with a cue step (robot_loop_cue_f32, robot_loop_blind_f32): the net gets the picture of the wanted body once
before the run (with the first view or with a blank view) and a blank picture at every step of the run.
robot_loop_two_f32: two cue steps (picture of A, then of B, view blank), then 3 steps that should go for A and 3
for B, all 6 ordered pairs of a scene; the lists then hold the state against the goal of the coming step (A up to
index 2, B from index 3), near_a / exact_a / other_a the state against A at half time, near_both = A near at half
time and B near at the end.
-> results/finds_loop.jsonl (one row per net and seed, lists over the steps 0..steps)
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
from netresearch.tasks import fovea as fv  # noqa: E402
from netresearch.tasks import make_task  # noqa: E402
from netresearch.tasks.robot import data_path  # noqa: E402
from netresearch.tasks.servo import decode_step  # noqa: E402
from netresearch.train import load_checkpoint, run_sequence  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
CHUNK = 50                                                            # scenes whose camera images are held at once


def measure(gaze, pos, k):
    """True state of one run: step to the body (dx, dy), pixel distance to the centre point, wrong body?"""
    c = fv.centre_px(gaze)
    dist = np.linalg.norm(pos - c, axis=-1)
    dx, dy, _ = fv.nearest_cell(gaze, pos[k])
    return dx, dy, float(dist[k]), bool(dist.argmin() != k and dist[k] > 8.0)


def inside(g):
    return 0 <= g[0] < fv.RES and 0 <= g[1] < fv.RES


def loop(d, lo, hi, fine, steps, policy, two=False):
    """Runs for the scenes lo..hi-1 and all three bodies. policy(views [P, 3, s, s] uint8, scene index [P],
    body [P]) -> steps [P, 2], or None for the oracle. Returns per run and step: truth [P, steps + 1, 4]
    (dx, dy, px, other), answers [P, steps, 2], out [P, steps + 1].
    two: runs with two goals, all 6 ordered pairs (A, B) of a scene; the first half of the steps goes for A, the
    second for B (truth is measured against the goal of the coming step, after the last step against B); the
    policy gets body = (A, B). A fourth result: the state against A at the end of the first half [P, 4]."""
    sat = [fv.integral((d["big"] if fine else d["img"])[i]) for i in range(lo, hi)]
    view = (lambda i, g: fv.sample_fine(sat[i - lo], g)) if fine else (lambda i, g: fv.sample(sat[i - lo], g))
    idx, body = np.repeat(np.arange(lo, hi), 3), np.tile(np.arange(3), hi - lo)
    goal = lambda p, t: body[p]                                        # noqa: E731
    if two:
        ab = np.array([(x, y) for x in range(3) for y in range(3) if x != y])
        idx, body = np.repeat(np.arange(lo, hi), 6), (np.tile(ab[:, 0], hi - lo), np.tile(ab[:, 1], hi - lo))
        goal = lambda p, t: body[0][p] if t < steps // 2 else body[1][p]   # noqa: E731
    P = len(idx)
    end_a = np.zeros((P, 4))
    gaze = d["gaze"][idx].astype(float)
    truth, ans, out = np.zeros((P, steps + 1, 4)), np.zeros((P, steps, 2), np.int64), np.zeros((P, steps + 1), bool)
    for t in range(steps + 1):
        for p in range(P):
            truth[p, t] = measure(gaze[p], d["pos"][idx[p]], goal(p, t))
            if two and t == steps // 2:
                end_a[p] = measure(gaze[p], d["pos"][idx[p]], body[0][p])
        if t == steps:
            break
        if policy is None:
            a = truth[:, t, :2].astype(np.int64)
        else:
            a = policy(np.stack([view(idx[p], gaze[p]) for p in range(P)]), idx, body)
        ans[:, t] = a
        for p in range(P):
            if out[p, t]:
                continue
            g = fv.shift(gaze[p], a[p, 0], a[p, 1])
            if inside(g):
                gaze[p] = g
            else:
                out[p, t + 1:] = True
    return (truth, ans, out, end_a) if two else (truth, ans, out)


def summary(truth, ans, out, end_a=None):
    ok = ~out
    r = np.abs(truth[:, :, :2]).max(-1)
    px = np.where(ok, truth[:, :, 2], np.nan)
    flip = np.zeros(ans.shape[:2], bool)
    flip[:, 1:] = (ans[:, 1:] == -ans[:, :-1]).all(-1) & (ans[:, 1:] != 0).any(-1)
    f = lambda x: [round(float(v), 4) for v in x]                      # noqa: E731
    extra = {}
    if end_a is not None:                                              # two goals: A at half time, B at the end
        h = truth.shape[1] // 2
        ra, oka = np.abs(end_a[:, :2]).max(-1), ok[:, h]
        g = lambda x: round(float(x.mean()), 4)                        # noqa: E731
        extra = {"near_a": g((ra <= 1) & oka), "exact_a": g((ra == 0) & oka),
                 "other_a": g(end_a[:, 3].astype(bool) & oka),
                 "near_both": g((ra <= 1) & oka & (r[:, -1] <= 1) & ok[:, -1])}
    return {**extra, "exact": f(((r == 0) & ok).mean(0)), "near": f(((r <= 1) & ok).mean(0)),
            "px_median": f(np.nanmedian(px, 0)), "px_mean": f(np.nanmean(px, 0)),
            "other": f((truth[:, :, 3].astype(bool) & ok).mean(0)), "out": f(out.mean(0)),
            "rest": f((ans == 0).all(-1).mean(0)), "flip": f(flip.mean(0))}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", default="robot_finds_c_f32")
    ap.add_argument("--seeds", nargs="+", type=int, default=[0, 1, 2])
    ap.add_argument("--steps", type=int, default=None, help="default 4; 6 for a task with two goals")
    ap.add_argument("--scenes", type=int, default=1500)
    ap.add_argument("--models", nargs="*", help="only these nets (default: every stored net of the task)")
    ap.add_argument("--images", default="gazeshapec", help="scene set with camera images (<name>_test_img.npz)")
    ap.add_argument("--amnesia", action="store_true", help="wipe the net's memory before every step (control)")
    a = ap.parse_args()
    task = make_task(a.task)
    amnesia = a.amnesia or task.spec.seq_len == 1                       # single-step nets never carried a state
    cue = getattr(task, "cue", None)                         # robot_loop_cue_f32 / _blind_f32 / _two_f32
    two = cue == "two"
    a.steps = a.steps or (6 if two else 4)
    fine = a.task.endswith("_f32")
    d = np.load(data_path(f"{a.images}_test_img.npz"))
    n = min(a.scenes, len(d["obs"]))
    d = {q: d[q][:n] for q in ("obs", "f32", "gaze", "pos", "cells", "refs", "img", "big")}
    for i in range(0, n, max(1, n // 20)):                             # the copy of the sampler is exact
        assert (fv.sample(fv.integral(d["img"][i]), d["gaze"][i]) == d["obs"][i]).all(), i
        assert (fv.sample_fine(fv.integral(d["big"][i]), d["gaze"][i]) == d["f32"][i]).all(), i
    nets = []
    for p in sorted((ROOT / "results" / "checkpoints" / a.task).glob("*.pt")):
        name, seed = re.fullmatch(r"(.+)_s(\d+)", p.stem).groups()
        if int(seed) in a.seeds and (not a.models or name in a.models):
            nets.append((name, int(seed), load_checkpoint(name, a.task, int(seed))))
    print(f"{a.task}: {n} scenes x {6 if two else 3} runs, {a.steps} steps, {len(nets)} nets", flush=True)

    def policy(model):
        state = [None]                                                  # memory of the net along the run

        primed = [False]

        def f(views, idx, body):
            pic = lambda k: torch.tensor(d["refs"][idx, k, 0].astype(np.float32) / 255.0)[None]   # noqa: E731
            ref = pic(body[0] if two else body)
            x = torch.tensor(views.astype(np.float32) / 255.0)[None]
            with torch.no_grad():
                if cue and not primed[0]:                               # cue step: the picture, eye does not move
                    primed[0] = True
                    _, st = run_sequence(model, x if cue == "view" else torch.zeros_like(x), ref=ref)
                    if two:                                             # second cue step: the picture of B
                        _, st = run_sequence(model, torch.zeros_like(x), state=st if model.stateful else None,
                                             ref=pic(body[1]))
                    state[0] = st if model.stateful else None
                if cue:
                    ref = torch.zeros_like(ref)                         # during the run the picture is blank
                lg, st = run_sequence(model, x, state=None if amnesia else state[0], ref=ref)
            state[0] = st if model.stateful else None
            return decode_step(lg[0][:, task.spec.out_slice].numpy(), task.spec)
        return f

    parts = defaultdict(list)
    for lo in range(0, n, CHUNK):
        hi = min(n, lo + CHUNK)
        parts["oracle", -1].append(loop(d, lo, hi, fine, a.steps, None, two))
        for name, seed, model in nets:
            parts[name, seed].append(loop(d, lo, hi, fine, a.steps, policy(model), two))
        print(f"  scenes {hi}/{n}", flush=True)
    per = defaultdict(list)
    with open(ROOT / "results" / "finds_loop.jsonl", "a") as out:
        for (name, seed), ps in parts.items():
            s = summary(*(np.concatenate(x) for x in zip(*ps)))
            per[name].append(s)
            out.write(json.dumps({"task": a.task + ("/amnesia" if a.amnesia else ""), "model": name, "seed": seed, "scenes": n, "steps": a.steps, **s}) + "\n")
    f = lambda v: " ".join(f"{x:.2f}" for x in v)                       # noqa: E731
    print(f"\nmean over seeds; columns = before step 1, after step 1 .. {a.steps}")
    if two:
        print("\nA at half time: near / exact / wrong body;  A and B both near")
        for name, rows in per.items():
            print(f"  {name:<26} " + " ".join(f"{np.mean([x[q] for x in rows]):.2f}"
                                             for q in ("near_a", "exact_a", "other_a", "near_both")))
    for q in ("exact", "near", "px_median", "other", "out", "rest", "flip"):
        print(f"\n{q}")
        for name, rows in per.items():
            print(f"  {name:<26} {f(np.mean([x[q] for x in rows], 0))}")


if __name__ == "__main__":
    sys.exit(main())
