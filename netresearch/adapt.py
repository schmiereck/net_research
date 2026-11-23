"""Adaptation benchmark (PLAN_TRAINER.md, phase A): how fast does a TRAINED net learn a new variant of a
task family, and how much of the old task does it lose on the way?

    python -m netresearch.adapt run --models layer_s hier_s ... [--cases all] [--seeds 0 1 2] [--workers 6]
    python -m netresearch.adapt summary [--file results/adapt.jsonl]

Start nets are the benchmark checkpoints (results/checkpoints/<base task>/<model>_s<seed>.pt); a missing one is
trained first with the normal benchmark run (and saved), so the benchmark also runs on a fresh worker.

Cases (each: base task the start net knows -> new variant):
    fixcycle   base cycle.  One fixed, unseen cycle of 6 words; only the CURRENT row is visible, so the
               cycle cannot be read from the image and has to be stored in the weights (k = the 6 transitions).
               Pure memorisation, "einen neuen Zyklus merken".
    double     base numseq. New rule v[n+1] = 2 v[n] + c (mod 256), 3 rows visible -> next. k training
               sequences; scored on unseen sequences of the same rule (has the RULE been learned?).
    trib       base numseq. New rule v[n+1] = v[n] + v[n-1] + v[n-2] (mod 256); as above.
    countbig   base count.  Steps 16..31 (training had 1..15); as above.
Middle cases (candidates for "learnable in 200 updates, but needs generalisation"); the inputs are the
base task's own sequences, only the asked output changes; scored on unseen sequences:
    xormask    base numseq. Output = next number XOR a fixed mask (variant 0: 0x0F, 1: 0xA5).
    prev       base numseq. Output = the last visible number (copy instead of predict).
    plus1      base numseq. Output = next number + 1 (mod 256, carries).
    cycle2     base cycle.  Output = the word after the next one (2P..15 rows visible).

Step cases (servo_<device>, robot_green / robot_blue): the step in the population code like their base tasks
servo / robot_gaze (32 outputs in the symbol area, SPEC_POP); "<case>_bits" is the same case in the old 8-bit
code on the base "<base>_bits" (results before 2026-11-23). Pinned base nets: data/base_nets/<base task>.

Methods (all Adam, full batch on the k examples):
    adam      fine-tuning of the start net, lr 1e-3
    adam_lo   the same with lr 1e-4 (less forgetting, slower)
    replay    lr 1e-3, every update also trains on a fresh batch of the base task (standard remedy against
              forgetting; needs the old data, which a fast learner should not)
    scratch   lr 1e-3 from a freshly initialised net (how much does the pretraining help?)
Recorded per run: score on the new variant after s = 0, 1, 2, 5, 10, 20, 50, 100, 200 updates (curve), and the
score on the base task at the same points (retention).
"""
import argparse
import json
import multiprocessing as mp
import os
import time
import traceback
import zlib
from pathlib import Path

import numpy as np
import torch

from .spec import TaskSpec
from .tasks.patterns import WORD, _split_of, draw_rows, gen_row_cycle, sample_row_cycles, to_bits

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results" / "adapt.jsonl"
STEPS = [0, 1, 2, 5, 10, 20, 50, 100, 200]
if os.environ.get("NETRESEARCH_ADAPT_LONG"):       # long horizon (robot cases: is an inner change learnable at all?)
    STEPS += [500, 1000, 2000]
KS = [8, 64, 512]                 # number of training examples for the rule cases
N_TEST = 512
METHODS = {"adam": (1e-3, False), "adam_lo": (1e-4, False), "replay": (1e-3, True), "scratch": (1e-3, False)}
SPEC = TaskSpec("adapt", "patterns", "supervised", "bits", WORD, seq_len=1, chance=0.0)
# step cases on a base task in the population code (servo, robot_gaze; their old 8-bit form is "<name>_bits"):
# the step as 32 outputs in the symbol area, scored by the strongest unit per axis (tasks/servo.py)
SPEC_POP = TaskSpec("adapt_pop", "patterns", "supervised", "bits", 32, seq_len=1, chance=0.0, role="symbol", pop=True)


def spec_of(base):
    """Output code of the cases on `base`: SPEC_POP if the base task gives its step in the population code."""
    from .tasks import make_task
    return SPEC_POP if make_task(base).spec.pop else SPEC


def exact(spec, lg, target):
    """Per example 1.0 if the whole answer is right (lg: logits of the task's slice)."""
    if spec.pop:
        return (lg.reshape(*lg.shape[:-1], 2, 16).argmax(-1)
                == target.reshape(*lg.shape[:-1], 2, 16).argmax(-1)).all(-1).float()
    return ((lg > 0).float() == target).float().min(-1).values


def step_target(dx, dy, pop):
    """Signed steps -> targets [n, 8] (bits) or [n, 32] (population code, width STEP_SIGMA). Steps outside -8..7
    wrap around in both codes (the bits keep 4 per axis; e.g. flipx of -8 gives +8 -> -8, as in the base tasks)."""
    from .tasks.servo import STEP_SIGMA, command_bits, pop_code
    if not pop:
        return command_bits(dx, dy)
    st = (np.stack([dx, dy], 1).astype(np.int64) + 8) % 16 - 8
    return pop_code(st, STEP_SIGMA)


def _batch(words, n_visible, target):
    """-> supervised batch dict (T = 1) like the pattern tasks."""
    B = len(words)
    return {"obs": torch.from_numpy(draw_rows(words, n_visible)[None]),
            "target": torch.from_numpy(to_bits(target)[None]), "mask": torch.ones(1, B)}


# --------------------------------------------------------------------------------------------- cases
def case_fixcycle(variant, k):
    rng = np.random.default_rng(1000 + variant)
    while True:                                   # unseen cycle (test split), 6 distinct words
        w, key = gen_row_cycle(rng, 6, 6)
        if _split_of(("rows",) + key) == "test" and len(set(w.tolist())) == 6:
            break
    b = _batch(w[:, None], np.ones(6, np.int64), np.roll(w, -1))
    return b, b                                   # train = test: all 6 transitions


def _rule_seqs(rule, n, rng, split):
    out = []
    while len(out) < n:
        a, b, c = (int(x) for x in rng.integers(0, 256, size=3))
        if rule == "double":
            s = [a]
            for _ in range(3):
                s.append((2 * s[-1] + c) % 256)
            key = (rule, a, c)
        elif rule == "trib":
            s = [a, b, c]
            s.append((a + b + c) % 256)
            key = (rule, a, b, c)
        else:                                     # countbig: start a, step 16..31, 2..16 rows visible
            step = 16 + int(rng.integers(16))
            s = [(a + step * j) % 256 for j in range(17)]
            key = (rule, a, step)
        if _split_of(key) == split:
            out.append(s)
    return out


def case_rule(rule, variant, k):
    rng = np.random.default_rng(zlib.crc32(rule.encode()) + 7919 * variant)

    def make(n, split):
        seqs = _rule_seqs(rule, n, rng, split)
        if rule == "countbig":
            words = np.array(seqs)
            nv = rng.integers(2, 17, size=n)
            return _batch(words, nv, words[np.arange(n), nv])
        words = np.array(seqs)
        return _batch(words, np.full(n, 3), words[:, 3])
    return make(k, "train"), make(N_TEST, "test")


def _numseq_words(n, rng, split):
    """Base numseq sequences (arithmetic step 1..63 or fibonacci-like), split by the visible prefix (first 3 numbers),
    so identical inputs never fall on both sides. (A prefix that is both arithmetic and fibonacci-like, a = k,
    keeps two different 4th values; about 1/256 of the arithmetic sequences.)"""
    out = []
    while len(out) < n:
        a, b, k = (int(x) for x in rng.integers(0, 256, size=3))
        k = 1 + k % 63
        if rng.random() < 0.5:
            seq = [a, b]
            while len(seq) < 4:
                seq.append((seq[-1] + seq[-2]) % 256)
        else:
            seq = [(a + k * j) % 256 for j in range(4)]
        if _split_of(("mid", *seq[:3])) == split:
            out.append(seq)
    return np.array(out)


MASKS = [0x0F, 0xA5]


def case_mid(name, variant, k):
    rng = np.random.default_rng(zlib.crc32(name.encode()) + 7919 * variant)

    def make(n, split):
        if name == "cycle2":
            words, P = sample_row_cycles(n, 17, rng, split)
            nv = np.array([rng.integers(min(2 * p, 15), 16) for p in P])
            return _batch(words, nv, words[np.arange(n), nv + 1])
        w = _numseq_words(n, rng, split)
        tgt = {"xormask": w[:, 3] ^ MASKS[variant % 2], "prev": w[:, 2], "plus1": (w[:, 3] + 1) % 256}[name]
        return _batch(w, np.full(n, 3), tgt)
    return make(k, "train"), make(N_TEST, "test")


# new outputs on the numseq inputs (library.py suites six / twelve / drift; cases lib_<name>)
NUMSEQ_TASKS = {"xm0F": lambda w: w[:, 3] ^ 0x0F, "xmA5": lambda w: w[:, 3] ^ 0xA5, "plus1": lambda w: (w[:, 3] + 1) % 256,
                "minus1": lambda w: (w[:, 3] - 1) % 256, "prev": lambda w: w[:, 2], "prev2": lambda w: w[:, 1],
                # suite "twelve" adds (appended: the data seeds of the first six stay unchanged)
                "xm33": lambda w: w[:, 3] ^ 0x33, "xmFF": lambda w: w[:, 3] ^ 0xFF, "plus2": lambda w: (w[:, 3] + 2) % 256,
                "minus2": lambda w: (w[:, 3] - 2) % 256, "prev3": lambda w: w[:, 0],
                "diff": lambda w: (w[:, 2] - w[:, 1]) % 256}           # step of the sequence (an inner computation)


def case_lib(name, variant, k):
    """Another output on the base numseq inputs (NUMSEQ_TASKS); k training sequences, scored on unseen ones."""
    rng = np.random.default_rng(zlib.crc32(("lib_" + name).encode()) + 7919 * variant)

    def make(n, split):
        w = _numseq_words(n, rng, split)
        return _batch(w, np.full(n, 3), NUMSEQ_TASKS[name](w))
    return make(k, "train"), make(N_TEST, "test")


CASES = {
    "fixcycle": ("cycle", lambda v, k: case_fixcycle(v, k), [6], 4),       # base, maker, ks, n variants
    "double": ("numseq", lambda v, k: case_rule("double", v, k), KS, 2),
    "trib": ("numseq", lambda v, k: case_rule("trib", v, k), KS, 2),
    "countbig": ("count", lambda v, k: case_rule("countbig", v, k), KS, 2),
    "xormask": ("numseq", lambda v, k: case_mid("xormask", v, k), KS, 2),
    "prev": ("numseq", lambda v, k: case_mid("prev", v, k), KS, 2),
    "plus1": ("numseq", lambda v, k: case_mid("plus1", v, k), KS, 2),
    "cycle2": ("cycle", lambda v, k: case_mid("cycle2", v, k), KS, 2),
}
def case_servo(device, variant, k, pop=True):
    """Servo calibration (tasks/servo.py): base inputs, the command of another device; unseen test situations.
    pop: the command in the population code (base servo), else in 8 bits (base servo_bits); same data."""
    from .tasks.servo import bits_steps, servo_batch
    from .train import to_t
    rng = np.random.default_rng(zlib.crc32(device.encode()) + 7919 * variant)
    out = []
    for n, split in ((k, "train"), (N_TEST, "test")):
        b = servo_batch(device, n, rng, split)
        if pop:
            st = bits_steps(b["target"][0])
            b["target"] = step_target(st[:, 0], st[:, 1], True)[None]
        out.append(to_t(b))
    return tuple(out)


SERVO_CASES = ["flipx", "swap", "rot90", "strong", "weak", "offx"]
for _n in NUMSEQ_TASKS:                                       # phase D family (PLAN_TRAINER)
    CASES["lib_" + _n] = ("numseq", lambda v, k, _n=_n: case_lib(_n, v, k), KS, 2)
for _d in SERVO_CASES:
    CASES["servo_" + _d] = ("servo", lambda v, k, _d=_d: case_servo(_d, v, k), KS, 2)
    CASES["servo_" + _d + "_bits"] = ("servo_bits", lambda v, k, _d=_d: case_servo(_d, v, k, False), KS, 2)


def case_robot(target, variant, k, pop=True):
    """Another target on the same robot images (base robot_gaze = step to the red cube): the step to the green /
    blue cube (images with all three cubes, data/robot/gazemulti_*; library.py suite robot). The base net's head
    input carries the red cube's place, not the others' (head rules 0.01 there, LOGBUCH / PLAN_TRAINER Phase B):
    the case for "the head is not enough". Train: k images of the training file, test: N_TEST unseen images."""
    from .tasks.robot import DATA
    from .train import to_t
    col = {"green": 2, "blue": 4}[target]
    rng = np.random.default_rng(zlib.crc32(target.encode()) + 7919 * variant)

    def make(n, split):
        d = np.load(DATA / f"gazemulti_{split}.npz")
        i = rng.permutation(len(d["obs"]))[:n]
        c = d["cells"][i].astype(np.int64)
        return to_t({"obs": (d["obs"][i].astype(np.float32) / 255.0)[None],
                     "target": step_target(c[:, col], c[:, col + 1], pop)[None], "mask": np.ones((1, n), np.float32)})
    return make(k, "train"), make(N_TEST, "test")


for _t in ("green", "blue"):
    CASES["robot_" + _t] = ("robot_gaze", lambda v, k, _t=_t: case_robot(_t, v, k), KS, 2)
    CASES["robot_" + _t + "_bits"] = ("robot_gaze_bits", lambda v, k, _t=_t: case_robot(_t, v, k, False), KS, 2)
BASE_UPDATES = {"servo": 6000, "servo_bits": 6000, "robot_gaze": 6000, "robot_gaze_bits": 6000}                    # the grid nets need 4x the benchmark budget for servo
PHASE_A = ["fixcycle", "double", "trib", "countbig"]          # "--cases all" of the phase A run


# ------------------------------------------------------------------------------------------ measuring
@torch.no_grad()
def score_on(model, b, spec=SPEC):
    from .train import run_sequence
    model.eval()
    logits, _ = run_sequence(model, b["obs"])
    acc = (exact(spec, logits[..., spec.out_slice], b["target"]) * b["mask"]).sum() / b["mask"].sum()
    model.train()
    return round(float(acc), 4)


def base_score(model, task):
    from .train import evaluate_supervised
    return round(evaluate_supervised(model, task, n_batches=2)["score"], 4)


BASE_NETS = Path(__file__).resolve().parents[1] / "data" / "base_nets"   # pinned in git: same on every PC


def start_net(model_name, base, seed):
    from .train import load_checkpoint, run
    pinned = BASE_NETS / base / f"{model_name}_s{seed}.pt"    # step tasks: <name> population code, <name>_bits 8 bits
    if pinned.exists():                           # base nets trained on the main PC (workers train slightly
        return load_checkpoint(model_name, base, seed, pinned)   # different weights: CPU rounding)
    m = load_checkpoint(model_name, base, seed)
    if m is None:                                 # not trained yet here (e.g. fresh worker): train and save
        run(model_name, base, seed=seed, updates=BASE_UPDATES.get(base, 1500))
        m = load_checkpoint(model_name, base, seed)
    return m


def adapt_curve(model, train_b, test_b, base_task, lr, replay, seed, spec=SPEC):
    from .train import supervised_loss, run_sequence, to_t
    opt = torch.optim.Adam(model.parameters(), lr=lr)
    rng = np.random.default_rng(seed)
    model.train()
    curve, ret = [], []
    for s in range(STEPS[-1] + 1):
        if s in STEPS:
            curve.append([s, score_on(model, test_b, spec)])
            ret.append([s, base_score(model, base_task)])
        if s == STEPS[-1]:
            break
        logits, _ = run_sequence(model, train_b["obs"])
        loss = supervised_loss(spec, logits, train_b["target"], train_b["mask"])
        if replay:
            rb = to_t(base_task.sample(64, rng))
            lg, _ = run_sequence(model, rb["obs"])
            loss = loss + supervised_loss(base_task.spec, lg, rb["target"], rb["mask"])
        opt.zero_grad()
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        opt.step()
    return curve, ret


def _job(args):
    model_name, case, seed = args
    from .models import build_model, count_params
    from .tasks import make_task
    base, maker, ks, n_var = CASES[case]
    try:
        torch.manual_seed(seed)
        task = make_task(base)
        start = start_net(model_name, base, seed)
        rows = []
        t0 = time.time()
        for v in range(n_var):
            for k in ks:
                train_b, test_b = maker(v + 10 * seed, k)
                for method, (lr, replay) in METHODS.items():
                    if method == "scratch":
                        m = build_model(model_name, seed=seed + 100)
                    else:
                        m = start_net(model_name, base, seed)          # fresh copy of the start net
                    curve, ret = adapt_curve(m, train_b, test_b, task, lr, replay, seed + v, spec_of(base))
                    rows.append({"variant": v, "k": k, "method": method, "curve": curve, "retention": ret})
        return {"model": model_name, "case": case, "base": base, "seed": seed, "params": count_params(start),
                "start_base_score": base_score(start, task), "steps": STEPS, "runs": rows,
                "time": round(time.time() - t0, 1)}
    except Exception:  # noqa: BLE001
        return {"model": model_name, "case": case, "seed": seed, "error": traceback.format_exc()}


def _init_worker():
    torch.set_num_threads(1)


def run(models, cases, seeds, workers, out):
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    done = set()
    if out.exists():
        for ln in out.read_text().splitlines():
            r = json.loads(ln)
            if "error" not in r:
                done.add((r["model"], r["case"], r["seed"]))
    jobs = [(m, c, s) for s in seeds for c in cases for m in models if (m, c, s) not in done]
    print(f"{len(jobs)} jobs ({len(done)} already done), {workers} workers", flush=True)
    t0 = time.time()
    with mp.get_context("spawn").Pool(workers, initializer=_init_worker) as pool, out.open("a") as f:
        for i, r in enumerate(pool.imap_unordered(_job, jobs), 1):
            f.write(json.dumps(r) + "\n")
            f.flush()
            if "error" in r:
                msg = "ERROR " + r["error"].strip().splitlines()[-1]
            else:
                ad = [x["curve"][-1][1] for x in r["runs"] if x["method"] == "adam"]
                msg = f"adam end {np.mean(ad):.2f} t={r['time']}s"
            print(f"[{i}/{len(jobs)} {(time.time() - t0) / 60:5.1f}min] {r['model']:11s} {r['case']:9s} "
                  f"s{r['seed']} {msg}", flush=True)


# -------------------------------------------------------------------------------------------- summary
def summary(path):
    rows = []
    for ln in Path(path).read_text().splitlines():
        r = json.loads(ln)
        if "error" in r:
            continue
        for x in r["runs"]:
            c, ret = dict(x["curve"]), dict(x["retention"])
            rows.append({"model": r["model"], "case": r["case"], "k": x["k"], "method": x["method"],
                         "s0": c[0], "s5": c[5], "s20": c[20], "s200": c[200],
                         "auc": float(np.mean(list(c.values()))),
                         "ret_drop": ret[0] - ret[200], "ret_drop20": ret[0] - ret[20]})
    import pandas as pd
    d = pd.DataFrame(rows)
    g = d.groupby(["case", "k", "model", "method"])[["s0", "s5", "s20", "s200", "auc", "ret_drop20",
                                                      "ret_drop"]].mean().round(2)
    with pd.option_context("display.max_rows", 500, "display.width", 200):
        print(g.unstack("method").to_string())


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("cmd", choices=["run", "summary"])
    ap.add_argument("--models", nargs="+", default=["layer_s", "hier_s"])
    ap.add_argument("--cases", nargs="+", default=["all"])
    ap.add_argument("--seeds", nargs="+", type=int, default=[0])
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 2))
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--file", default=str(OUT))
    a = ap.parse_args()
    if a.cmd == "summary":
        summary(a.file)
    else:
        run(a.models, PHASE_A if a.cases == ["all"] else a.cases, a.seeds, a.workers, a.out)


if __name__ == "__main__":
    main()
