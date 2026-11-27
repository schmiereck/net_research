"""Phase F, first test (PLAN_TRAINER.md, Phase F): learning while awake, consolidation in a sleep phase on dreams.

    python -m netresearch.sleep check                                   # base net as predictor, dream quality
    python -m netresearch.sleep run [--cases lib_prev lib_xmFF] [--seeds 5 6] [--draws 3] [--workers 4]

Two modules of the same shape on the frozen start net (W stays fixed):
    wake   fast weights F (fc1, fc2, head), learned from the k = 64 examples by a rule found in phase D
           (default `pos_map`, 20 updates, oracle gate "task" as in phase D).
    sleep  a second set S of the same shape, trained only from dreams: inputs the sleeping net makes up
           itself, labelled by the waking net (W + F). After sleep F is gone; only W + S is scored on unseen
           test sequences. Sleep learns with the gradient for now (Adam on S through the frozen net, as
           grad@task): an upper bound for a local sleep rule to be found later.
The dream is not scored against the world: its targets come from the waking net (distillation). What a dream
source decides is WHICH inputs the skill is carried over on. Sources (POOL inputs each, 3 visible numbers):
    replay      the k training inputs themselves (needs the stored episode)
    dream_mem   the base net (W, F off; it predicts the 4th number of a sequence) rolls out ROLL steps from
                the k training inputs as start values: window (a, b, c) -> d -> (b, c, d) -> ...
    dream_rand  the same rollouts from random start values
    noise       random triples, no rollout (control: inputs without any world model)
    real        fresh base sequences from the task generator (the ideal dream; needs the world itself)
Dream quality: the share of dream windows that are base sequences (arithmetic with step 1..63, or
fibonacci-like), which the base task generator can produce.
"""
import argparse
import json
import multiprocessing as mp
from pathlib import Path

import numpy as np
import torch

from .adapt import CASES, _numseq_words, score_on, spec_of
from .fastweights import Fast, default_eta
from .tasks.patterns import WORD, draw_rows
from .teacher import MODEL, Teach, _init_worker, _net, load_rule

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results" / "sleep.jsonl"
SOURCES = ["replay", "dream_mem", "dream_rand", "noise", "real"]
POOL, ROLL, T_WAKE, T_SLEEP, BATCH = 1024, 16, 20, 200, 64
SLEEP_POINTS = (0, 20, 50, 100, 200)
POW = 1 << np.arange(WORD - 1, -1, -1)


def windows_of(b):
    """The 3 visible numbers of every example of a batch -> [n, 3] ints."""
    bits = b["obs"][0][:, 0, :3, 16 - WORD:].numpy()
    return (bits > 0.5).astype(np.int64) @ POW


def obs_of(w3):
    w = np.concatenate([w3, np.zeros((len(w3), 1), np.int64)], 1)
    return torch.from_numpy(draw_rows(w, np.full(len(w), 3))[None])


@torch.no_grad()
def predict_bits(model, w3, spec):
    from .train import run_sequence
    model.eval()
    logits, _ = run_sequence(model, obs_of(w3))
    model.train()
    return (logits[0][:, spec.out_slice] > 0).float()


def rollout(model0, start, steps, spec):
    """Dream: the base net (F off) predicts the next number and the window slides on; -> all new windows."""
    w, out = start.copy(), []
    for _ in range(steps):
        d = predict_bits(model0, w, spec).long().numpy() @ POW
        w = np.stack([w[:, 1], w[:, 2], d], 1)
        out.append(w)
    return np.concatenate(out)


def valid(w3):
    """Share of windows that are base sequences (arithmetic with step 1..63, or fibonacci-like)."""
    s1, s2 = (w3[:, 1] - w3[:, 0]) % 256, (w3[:, 2] - w3[:, 1]) % 256
    ari = (s1 == s2) & (s1 >= 1) & (s1 <= 63)
    fib = w3[:, 2] == (w3[:, 0] + w3[:, 1]) % 256
    return float((ari | fib).mean())


def pool_of(src, model0, train_w, rng, spec):
    if src == "replay":
        return train_w
    if src == "dream_mem":
        return rollout(model0, train_w, ROLL, spec)[:POOL]
    if src == "dream_rand":
        return rollout(model0, rng.integers(0, 256, (POOL // ROLL, 3)), ROLL, spec)[:POOL]
    if src == "noise":
        return rng.integers(0, 256, (POOL, 3))
    return _numseq_words(POOL, rng, "train")[:, :3]          # real


def episode(case, seed, draw, rule="pos_map", model_name=MODEL, sources=SOURCES):
    base, maker = CASES[case][0], CASES[case][1]
    spec = spec_of(base)
    b, tb = maker(draw + 10 * seed, 64)
    theta, pos, horizon = load_rule(rule)
    wake = _net(seed, model_name)                              # wake: W + F, F by the found rule
    fw = Teach(wake, theta, seed * 100 + draw, spec, T=horizon, pos=pos)
    fw.task_on = 1.0
    row = {"case": case, "seed": seed, "draw": draw, "model": model_name, "rule": rule,
           "s_before": score_on(wake, tb, spec)}
    for _ in range(T_WAKE):
        fw.step(b)
    row["s_wake"] = score_on(wake, tb, spec)
    model0 = _net(seed, model_name)                            # the sleeping world model: W only
    train_w = windows_of(b)
    rng = np.random.default_rng(1000 * seed + draw)
    row["sources"] = {}
    for src in sources:
        w3 = pool_of(src, model0, train_w, rng, spec)
        y = predict_bits(wake, w3, spec)                       # labels from the waking net (F on)
        slow = _net(seed, model_name)
        fs = Fast(slow, "grad@task", default_eta("grad@task"), seed * 100 + draw, spec)
        fs.task_on = 1.0
        cur = []
        for t in range(T_SLEEP + 1):
            if t in SLEEP_POINTS:
                cur.append([t, score_on(slow, tb, spec)])
            if t < T_SLEEP:
                i = rng.integers(0, len(w3), BATCH)
                fs.step({"obs": obs_of(w3[i]), "target": y[i][None], "mask": torch.ones(1, BATCH)})
        row["sources"][src] = {"valid": round(valid(w3), 4), "n": int(len(w3)), "curve": cur}
    return row


def _job(a):
    return episode(*a)


def check(model_name=MODEL, seed=5):
    """The base net as predictor of the next number, and the quality of its dreams."""
    from .adapt import SPEC
    rng = np.random.default_rng(0)
    m = _net(seed, model_name)
    w = _numseq_words(512, rng, "test")
    d = predict_bits(m, w[:, :3], SPEC).long().numpy() @ POW
    print(f"{model_name} s{seed}: next number right on unseen base sequences {float((d == w[:, 3]).mean()):.3f}")
    for name, start in [("dream_mem", w[:64, :3]), ("dream_rand", rng.integers(0, 256, (64, 3)))]:
        r = rollout(m, start, ROLL, SPEC)
        per = [valid(r[64 * i:64 * (i + 1)]) for i in range(ROLL)]
        print(name, "valid per rollout step", [round(x, 2) for x in per], "all", round(valid(r), 3))
    print("noise valid", round(valid(rng.integers(0, 256, (POOL, 3))), 3))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["check", "run"])
    ap.add_argument("--cases", nargs="+", default=["lib_prev", "lib_xmFF"])
    ap.add_argument("--seeds", nargs="+", type=int, default=[5, 6])
    ap.add_argument("--draws", type=int, default=3)
    ap.add_argument("--rule", default="pos_map")
    ap.add_argument("--model", default=MODEL)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--out", default=str(OUT))
    a = ap.parse_args()
    if a.cmd == "check":
        check(a.model)
        return
    jobs = [(c, s, d, a.rule, a.model) for c in a.cases for s in a.seeds for d in range(a.draws)]
    with mp.get_context("spawn").Pool(a.workers, initializer=_init_worker) as pool, open(a.out, "a") as f:
        for row in pool.imap(_job, jobs):
            f.write(json.dumps(row) + "\n")
            f.flush()
            print(row["case"], row["seed"], row["draw"], "wake", row["s_wake"],
                  {k: v["curve"][-1][1] for k, v in row["sources"].items()}, flush=True)


if __name__ == "__main__":
    main()
