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


LEARNERS = ["grad", "rls_rf", "rule"]


def learner(kind, model, seed, spec, rule="pos_map"):
    """The sleep module S on `model` (gate "task", on): grad = Adam on fc1 / fc2 / head through the frozen net
    (grad@task); rls_rf = recursive least squares on the head with fixed random features (no backprop; the best
    head rule of phase B / D); rule = the phase D rule itself, run on the dreams (no backprop)."""
    if kind == "rule":
        theta, pos, horizon = load_rule(rule)
        s = Teach(model, theta, seed, spec, T=horizon, pos=pos)
    else:
        r = f"{kind}@task"
        s = Fast(model, r, default_eta(r), seed, spec)
    s.task_on = 1.0
    return s


def dream_batch(w3, y, rng):
    i = rng.integers(0, len(w3), BATCH)
    return {"obs": obs_of(w3[i]), "target": y[i][None], "mask": torch.ones(1, BATCH)}


def episode(case, seed, draw, rule="pos_map", model_name=MODEL, sources=SOURCES, learners=("grad",)):
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
    if tuple(learners) != ("grad",):
        row["learners"] = list(learners)
    for src in sources:
        w3 = pool_of(src, model0, train_w, rng, spec)
        y = predict_bits(wake, w3, spec)                       # labels from the waking net (F on)
        for kind in learners:
            slow = _net(seed, model_name)
            fs = learner(kind, slow, seed * 100 + draw, spec, rule)
            cur = []
            for t in range(T_SLEEP + 1):
                if t in SLEEP_POINTS:
                    cur.append([t, score_on(slow, tb, spec)])
                if t < T_SLEEP:
                    fs.step(dream_batch(w3, y, rng))
            key = "sources" if kind == "grad" else f"sources_{kind}"
            row.setdefault(key, {})[src] = {"valid": round(valid(w3), 4), "n": int(len(w3)), "curve": cur}
    return row


# ------------------------------------------------------------------------------------------------ the loop
CYCLES, T_LOOP_SLEEP = 4, 100


def reset(fw):
    """A fresh wake phase: the fast weights F back to zero (the rule's fixed random feedback stays)."""
    for n in fw.F:
        fw.F[n].zero_()
    fw.t, fw.S_prev = 0, None


GATES = ["none", "surprise", "surprise_ex"]
SURPRISE_MIN = 0.1        # gate "surprise": learn only while at least this share of the day's examples is wrong


def wrong_of(model, b, spec):
    """Per example True if the net gets the whole answer wrong."""
    from .adapt import exact
    from .train import run_sequence
    with torch.no_grad():
        model.eval()
        logits, _ = run_sequence(model, b["obs"])
        model.train()
        ok = exact(spec, logits[0][:, spec.out_slice], b["target"][0]) > 0.5
    return (~ok) & (b["mask"][0] > 0)


def wake_step(fw, model, b, spec, gate):
    """One wake update under a surprise gate; -> number of examples learned on.
    surprise     per update: the rule runs on the whole batch, but only while >= SURPRISE_MIN of it is wrong
                 (the rule was formed on whole batches, so its working range is kept)
    surprise_ex  per example: the rule runs only on the examples that are wrong (a sub-batch)"""
    if gate != "none":
        wrong = wrong_of(model, b, spec)
        if gate == "surprise" and float(wrong.float().mean()) < SURPRISE_MIN:
            return 0
        if gate == "surprise_ex":
            if not wrong.any():
                return 0
            b = {"obs": b["obs"][:, wrong], "target": b["target"][:, wrong], "mask": b["mask"][:, wrong]}
    fw.step(b)
    return int(b["mask"].sum())


def loop_episode(case, seed, draw, kind, rule="pos_map", model_name=MODEL, cycles=CYCLES, source="dream_mem",
                 gate="none", controls=False):
    """Wake and sleep in turn. Every cycle brings k = 64 new training examples of the same task (daily life).
    Wake: F starts at zero and learns on W + S with the found rule (T_WAKE updates). Sleep: S goes on learning
    (it is not reset) from dreams started at the day's examples, labelled by W + S + F; then F is cleared.
    So what was learned in sleep flows back into the next day: the wake rule starts from W + S.
    Controls with the same real data: `wake_only` (no sleep, F keeps learning over all days) and `grad`
    (Adam on the fast weights, T_WAKE updates a day: plain training of a net).
    gate "surprise": the wake rule (in the loop and in `wake_only`) learns only on the examples the net still
    gets wrong; an update with none of them is skipped (PLAN_TRAINER section 4, building block 5).
    controls: two more, on their own nets and random streams (the loop itself is unchanged):
    `rls_direct` rls_rf on the head trained directly on the real examples of every day (T_WAKE updates a day;
                 plain training with the best head rule), and
    `sleep_only` the loop with a wake phase on day 1 only; on the later days the net just sleeps on dreams from
                 the day's examples, labelled by W + S (separates what waking adds from repeated sleep)."""
    base, maker = CASES[case][0], CASES[case][1]
    spec = spec_of(base)
    tb = maker(draw + 10 * seed, 64)[1]                        # fixed unseen test set
    days = [maker(draw + 10 * seed + 1000 * c, 64)[0] for c in range(cycles)]
    theta, pos, horizon = load_rule(rule)
    rng = np.random.default_rng(1000 * seed + draw)
    m = _net(seed, model_name)
    S = learner(kind, m, seed * 100 + draw + 50, spec, rule)   # hooked first: the slow module
    F = Teach(m, theta, seed * 100 + draw, spec, T=horizon, pos=pos)
    model0 = _net(seed, model_name)
    ctl_w = _net(seed, model_name)
    W = Teach(ctl_w, theta, seed * 100 + draw, spec, T=horizon, pos=pos)
    W.task_on = 1.0
    ctl_g = _net(seed, model_name)
    G = Fast(ctl_g, "grad@task", default_eta("grad@task"), seed * 100 + draw, spec)
    G.task_on = 1.0
    row = {"case": case, "seed": seed, "draw": draw, "model": model_name, "rule": rule, "learner": kind,
           "source": source, "cycles": cycles, "t_wake": T_WAKE, "t_sleep": T_LOOP_SLEEP,
           "s_before": score_on(m, tb, spec), "wake": [], "sleep": [], "wake_only": [], "grad": []}
    if gate != "none":
        row.update({"gate": gate, "n_wake": [], "n_wake_only": []})
    if controls:
        rng2 = np.random.default_rng(1000 * seed + draw)
        m2 = _net(seed, model_name)
        S2 = learner(kind, m2, seed * 100 + draw + 50, spec, rule)
        F2 = Teach(m2, theta, seed * 100 + draw, spec, T=horizon, pos=pos)
        ctl_r = _net(seed, model_name)
        Rd = Fast(ctl_r, "rls_rf@task", default_eta("rls_rf@task"), seed * 100 + draw, spec)
        Rd.task_on = 1.0
        row.update({"rls_direct": [], "sleep_only": []})
    for c, b in enumerate(days):
        reset(F)
        F.task_on = 1.0
        nf = nw = 0
        for _ in range(T_WAKE):
            nf += wake_step(F, m, b, spec, gate)
            nw += wake_step(W, ctl_w, b, spec, gate)
            G.step(b)
        if gate != "none":                                     # examples learned on (of T_WAKE * 64)
            row["n_wake"].append(nf)
            row["n_wake_only"].append(nw)
        row["wake"].append(score_on(m, tb, spec))              # W + S + F
        row["wake_only"].append(score_on(ctl_w, tb, spec))
        row["grad"].append(score_on(ctl_g, tb, spec))
        w3 = pool_of(source, model0, windows_of(b), rng, spec)
        y = predict_bits(m, w3, spec)                          # labels from W + S + F
        F.task_on = 0.0                                        # asleep: F off, only S learns
        for _ in range(T_LOOP_SLEEP):
            S.step(dream_batch(w3, y, rng))
        row["sleep"].append(score_on(m, tb, spec))             # W + S
        if controls:
            for _ in range(T_WAKE):
                Rd.step(b)
            row["rls_direct"].append(score_on(ctl_r, tb, spec))
            F2.task_on = 1.0
            if c == 0:                                         # sleep_only: awake on day 1 only
                for _ in range(T_WAKE):
                    wake_step(F2, m2, b, spec, gate)
            w3 = pool_of(source, model0, windows_of(b), rng2, spec)
            y = predict_bits(m2, w3, spec)
            F2.task_on = 0.0
            for _ in range(T_LOOP_SLEEP):
                S2.step(dream_batch(w3, y, rng2))
            reset(F2)
            row["sleep_only"].append(score_on(m2, tb, spec))
    return row


def loop_fitness(theta, pos, horizon, case, seed, draw, model_name=MODEL, days=4, gate="surprise", kind="rls_rf",
                 source="dream_mem"):
    """ES fitness of a wake rule theta inside the loop (teacher.py run --fitness loop): the loop of loop_episode
    without its controls; -> mean test score of W + S after each of the `days` nights (rewards early and lasting
    gains alike)."""
    base, maker = CASES[case][0], CASES[case][1]
    spec = spec_of(base)
    tb = maker(draw + 10 * seed, 64)[1]
    rng = np.random.default_rng(1000 * seed + draw)
    m = _net(seed, model_name)
    S = learner(kind, m, seed * 100 + draw + 50, spec)
    F = Teach(m, theta, seed * 100 + draw, spec, T=horizon, pos=pos)
    model0 = _net(seed, model_name)
    scores = []
    for c in range(days):
        b = maker(draw + 10 * seed + 1000 * c, 64)[0]
        reset(F)
        F.task_on = 1.0
        for _ in range(T_WAKE):
            wake_step(F, m, b, spec, gate)
        w3 = pool_of(source, model0, windows_of(b), rng, spec)
        y = predict_bits(m, w3, spec)
        F.task_on = 0.0
        for _ in range(T_LOOP_SLEEP):
            S.step(dream_batch(w3, y, rng))
        scores.append(score_on(m, tb, spec))
    return float(np.mean(scores))


def _job(a):
    return episode(*a)


def _loop_job(a):
    return loop_episode(*a)


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
    ap.add_argument("cmd", choices=["check", "run", "loop"])
    ap.add_argument("--cases", nargs="+", default=["lib_prev", "lib_xmFF"])
    ap.add_argument("--seeds", nargs="+", type=int, default=[5, 6])
    ap.add_argument("--draws", type=int, default=3)
    ap.add_argument("--rule", default="pos_map")
    ap.add_argument("--model", default=MODEL)
    ap.add_argument("--sources", nargs="+", default=SOURCES)
    ap.add_argument("--learners", nargs="+", default=["grad"], choices=LEARNERS)
    ap.add_argument("--cycles", type=int, default=CYCLES)
    ap.add_argument("--gates", nargs="+", default=["none"], choices=GATES)
    ap.add_argument("--controls", action="store_true", help="loop: also rls_direct and sleep_only")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--out", default=str(OUT))
    a = ap.parse_args()
    if a.cmd == "check":
        check(a.model)
        return
    if a.cmd == "loop":
        jobs = [(c, s, d, k, a.rule, a.model, a.cycles, "dream_mem", g, a.controls) for g in a.gates for c in a.cases
                for k in a.learners for s in a.seeds for d in range(a.draws)]
        fn = _loop_job
    else:
        jobs = [(c, s, d, a.rule, a.model, a.sources, a.learners) for c in a.cases for s in a.seeds
                for d in range(a.draws)]
        fn = _job
    with mp.get_context("spawn").Pool(a.workers, initializer=_init_worker) as pool, open(a.out, "a") as f:
        for row in pool.imap(fn, jobs):
            f.write(json.dumps(row) + "\n")
            f.flush()
            if a.cmd == "loop":
                print(row["case"], row["learner"], row["seed"], row["draw"], "wake", row["wake"], "sleep",
                      row["sleep"], "wake_only", row["wake_only"], "grad", row["grad"], flush=True)
            else:
                print(row["case"], row["seed"], row["draw"], "wake", row["s_wake"],
                      {k: {s: v["curve"][-1][1] for s, v in d.items()} for k, d in row.items()
                       if k.startswith("sources")}, flush=True)


if __name__ == "__main__":
    main()
