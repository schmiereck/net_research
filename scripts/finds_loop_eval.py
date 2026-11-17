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
robot_loop_three_f32: the same with three cue steps and three goals (3 steps each), all 12 sequences without the
same body twice in a row (A, B, C and A, B, A). For any number of goals: near_goal / exact_goal / other_goal per goal at the end of its steps, near_upto
(this goal and all before it near), near_all, split = where the run stands at the end of each goal's steps (near
it / an earlier goal / a later goal / the body that is no goal / none / out), split_prev_ok the same for the runs
with all earlier goals near.
-> results/finds_loop.jsonl (one row per net and seed, lists over the steps 0..steps)
"""
import argparse
import itertools
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


def loop(d, lo, hi, fine, steps, policy, goals=1):
    """Runs for the scenes lo..hi-1 and all three bodies. policy(views [P, 3, s, s] uint8, scene index [P],
    body [P]) -> steps [P, 2], or None for the oracle. Returns per run and step: truth [P, steps + 1, 4]
    (dx, dy, px, other), answers [P, steps, 2], out [P, steps + 1].
    goals > 1: runs with several goals one after the other, every sequence of the three bodies without the same
    body twice in a row (6 for two goals, 12 for three: A, B, C and A, B, A); each goal
    gets steps // goals steps (truth is measured against the goal of the coming step, after the last step against
    the last goal); the policy gets body = (A, B[, C]). Two more results at the end of each goal's share of steps:
    the state against that goal [P, goals, 4] and where the run stands [P, goals]: 0 near that goal, 1 near an
    earlier goal, 2 near a later goal, 3 near the body that is no goal, 4 near none ("near" = at most one cell)."""
    sat = [fv.integral((d["big"] if fine else d["img"])[i]) for i in range(lo, hi)]
    view = (lambda i, g: fv.sample_fine(sat[i - lo], g)) if fine else (lambda i, g: fv.sample(sat[i - lo], g))
    idx, body = np.repeat(np.arange(lo, hi), 3), np.tile(np.arange(3), hi - lo)
    goal = lambda p, t: body[p]                                        # noqa: E731
    seg = steps // goals
    if goals > 1:
        orders = np.array([o for o in itertools.product(range(3), repeat=goals) if all(x != y for x, y in zip(o, o[1:]))])
        idx = np.repeat(np.arange(lo, hi), len(orders))
        body = tuple(np.tile(orders[:, j], hi - lo) for j in range(goals))
        goal = lambda p, t: body[min(t // seg, goals - 1)][p]           # noqa: E731
    P = len(idx)
    seg_end, cls = np.zeros((P, goals, 4)), np.zeros((P, goals), np.int64)
    gaze = d["gaze"][idx].astype(float)
    truth, ans, out = np.zeros((P, steps + 1, 4)), np.zeros((P, steps, 2), np.int64), np.zeros((P, steps + 1), bool)
    for t in range(steps + 1):
        for p in range(P):
            truth[p, t] = measure(gaze[p], d["pos"][idx[p]], goal(p, t))
            if goals > 1 and t > 0 and t % seg == 0:
                j = t // seg - 1
                seg_end[p, j] = measure(gaze[p], d["pos"][idx[p]], body[j][p])
                near = [max(abs(x) for x in measure(gaze[p], d["pos"][idx[p]], k)[:2]) <= 1 for k in range(3)]
                order = [body[i][p] for i in range(goals)]
                c = 4
                for code, ks in ((0, [order[j]]), (1, order[:j]), (2, order[j + 1:]),
                                 (3, [k for k in range(3) if k not in order])):
                    if any(near[k] for k in ks):
                        c = code
                        break
                cls[p, j] = c
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
    ret = np.array(body[-1] == body[0]) if goals > 2 else np.zeros(P, bool)   # sequences like A, B, A
    return (truth, ans, out, seg_end, cls, ret) if goals > 1 else (truth, ans, out)


def shares(c, ok):
    """Shares of all runs [6]: near the goal / an earlier goal / a later goal / the body that is no goal / none /
    out of the image."""
    return [round(float(x.mean()), 4) if len(c) else float("nan")
            for x in [(c == k) & ok for k in range(5)] + [~ok]]


def summary(truth, ans, out, seg_end=None, cls=None, ret=None):
    ok = ~out
    r = np.abs(truth[:, :, :2]).max(-1)
    px = np.where(ok, truth[:, :, 2], np.nan)
    flip = np.zeros(ans.shape[:2], bool)
    flip[:, 1:] = (ans[:, 1:] == -ans[:, :-1]).all(-1) & (ans[:, 1:] != 0).any(-1)
    f = lambda x: [round(float(v), 4) for v in x]                      # noqa: E731
    extra = {}
    if seg_end is not None:                                            # several goals: each at the end of its steps
        G, seg = seg_end.shape[1], (truth.shape[1] - 1) // seg_end.shape[1]
        g = lambda x: round(float(x.mean()), 4)                        # noqa: E731
        okj = [ok[:, (j + 1) * seg] for j in range(G)]
        rj = [np.abs(seg_end[:, j, :2]).max(-1) for j in range(G)]
        nearj = [(rj[j] <= 1) & okj[j] for j in range(G)]
        prev = [np.all(nearj[:j], 0) if j else np.ones(len(r), bool) for j in range(G)]
        extra = {"near_goal": [g(x) for x in nearj], "exact_goal": [g((rj[j] == 0) & okj[j]) for j in range(G)],
                 "other_goal": [g(seg_end[:, j, 3].astype(bool) & okj[j]) for j in range(G)],
                 "near_upto": [g(prev[j] & nearj[j]) for j in range(G)], "near_all": g(np.all(nearj, 0)),
                 "split": [shares(cls[:, j], okj[j]) for j in range(G)],
                 "split_prev_ok": [shares(cls[prev[j], j], okj[j][prev[j]]) for j in range(G)]}
        if G > 2:                         # the last goal, for sequences A, B, C ("new") and A, B, A ("ret") apart
            for key, m in (("new", ~ret), ("ret", ret)):
                extra.update({f"near_goal_{key}": [g(x[m]) for x in nearj], f"near_all_{key}": g(np.all(nearj, 0)[m]),
                              f"split_last_{key}": shares(cls[m & prev[-1], -1], okj[-1][m & prev[-1]])})
        if G == 2:                                                     # the names of the first two-goal rows
            s0, s1, s1a = extra["split"][0], extra["split"][1], extra["split_prev_ok"][1]
            pick = lambda s, o: [s[0], s[o], s[3], s[4], s[5]]          # noqa: E731
            extra.update({"near_a": extra["near_goal"][0], "exact_a": extra["exact_goal"][0],
                          "other_a": extra["other_goal"][0], "near_both": extra["near_all"],
                          "split_half": pick(s0, 2), "split_end": pick(s1, 1), "split_end_a_ok": pick(s1a, 1),
                          "share_a_ok": extra["near_goal"][0]})
    return {**extra, "exact": f(((r == 0) & ok).mean(0)), "near": f(((r <= 1) & ok).mean(0)),
            "px_median": f(np.nanmedian(px, 0)), "px_mean": f(np.nanmean(px, 0)),
            "other": f((truth[:, :, 3].astype(bool) & ok).mean(0)), "out": f(out.mean(0)),
            "rest": f((ans == 0).all(-1).mean(0)), "flip": f(flip.mean(0))}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", default="robot_finds_c_f32")
    ap.add_argument("--seeds", nargs="+", type=int, default=[0, 1, 2])
    ap.add_argument("--steps", type=int, default=None, help="default 4; 3 per goal for a task with several goals")
    ap.add_argument("--scenes", type=int, default=1500)
    ap.add_argument("--models", nargs="*", help="only these nets (default: every stored net of the task)")
    ap.add_argument("--images", default="gazeshapec", help="scene set with camera images (<name>_test_img.npz)")
    ap.add_argument("--amnesia", action="store_true", help="wipe the net's memory before every step (control)")
    a = ap.parse_args()
    task = make_task(a.task)
    amnesia = a.amnesia or task.spec.seq_len == 1                       # single-step nets never carried a state
    cue = getattr(task, "cue", None)                         # robot_loop_cue_f32 / _blind_f32 / _two_f32
    goals = getattr(task, "G", 1)
    a.steps = a.steps or (3 * goals if goals > 1 else 4)
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
    print(f"{a.task}: {n} scenes x {3 * 2 ** (goals - 1)} runs, {a.steps} steps, {len(nets)} nets", flush=True)

    def policy(model):
        state = [None]                                                  # memory of the net along the run

        primed = [False]

        def f(views, idx, body):
            pic = lambda k: torch.tensor(d["refs"][idx, k, 0].astype(np.float32) / 255.0)[None]   # noqa: E731
            ref = pic(body[0] if goals > 1 else body)
            x = torch.tensor(views.astype(np.float32) / 255.0)[None]
            with torch.no_grad():
                if cue and not primed[0]:                               # cue step: the picture, eye does not move
                    primed[0] = True
                    _, st = run_sequence(model, x if cue == "view" else torch.zeros_like(x), ref=ref)
                    for k in range(1, goals):                           # further cue steps: B (and C)
                        _, st = run_sequence(model, torch.zeros_like(x), state=st if model.stateful else None,
                                             ref=pic(body[k]))
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
        parts["oracle", -1].append(loop(d, lo, hi, fine, a.steps, None, goals))
        for name, seed, model in nets:
            parts[name, seed].append(loop(d, lo, hi, fine, a.steps, policy(model), goals))
        print(f"  scenes {hi}/{n}", flush=True)
    per = defaultdict(list)
    with open(ROOT / "results" / "finds_loop.jsonl", "a") as out:
        for (name, seed), ps in parts.items():
            s = summary(*(np.concatenate(x) for x in zip(*ps)))
            per[name].append(s)
            out.write(json.dumps({"task": a.task + ("/amnesia" if a.amnesia else ""), "model": name, "seed": seed, "scenes": n, "steps": a.steps, **s}) + "\n")
    f = lambda v: " ".join(f"{x:.2f}" for x in v)                       # noqa: E731
    print(f"\nmean over seeds; columns = before step 1, after step 1 .. {a.steps}")
    if goals > 1:
        for q, head in (("near_goal", "near each goal at the end of its steps"),
                        ("near_upto", "near this goal and all before it"), ("near_all", "all goals near")):
            print(f"\n{head}")
            for name, rows in per.items():
                print(f"  {name:<26} {f(np.atleast_1d(np.mean([x[q] for x in rows], 0)))}")
        if goals > 2:
            for key, head in (("new", "A, B, C"), ("ret", "A, B, A")):
                print(f"\nsequences {head}: near each goal; all near")
                for name, rows in per.items():
                    print(f"  {name:<26} {f(np.mean([x['near_goal_' + key] for x in rows], 0))}  "
                          f"{np.mean([x['near_all_' + key] for x in rows]):.2f}")
                print(f"sequences {head}, last goal, runs with A and B near: near it / an earlier goal / a later goal"
                      " / no goal / none / out")
                for name, rows in per.items():
                    print(f"  {name:<26} {f(np.nanmean([x['split_last_' + key] for x in rows], 0))}")
        for q, head in (("split", "all runs"), ("split_prev_ok", "runs with all earlier goals near")):
            for j in range(goals):
                print(f"\ngoal {'ABC'[j]}, {head}: near it / an earlier goal / a later goal / no goal / none / out")
                for name, rows in per.items():
                    print(f"  {name:<26} {f(np.nanmean([x[q][j] for x in rows], 0))}")
    for q in ("exact", "near", "px_median", "other", "out", "rest", "flip"):
        print(f"\n{q}")
        for name, rows in per.items():
            print(f"  {name:<26} {f(np.mean([x[q] for x in rows], 0))}")


if __name__ == "__main__":
    sys.exit(main())
