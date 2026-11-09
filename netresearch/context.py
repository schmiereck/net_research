"""Phase B, context from error comparison (PLAN_TRAINER.md): when should the fast weights act, if the new task
has the SAME inputs as the base task (xormask, prev, plus1)? No oracle: the context comes from the errors.

    python -m netresearch.context run --models layer_s hier_s layer_s_sp4 [--seeds 0 1 2] [--workers 6]
    python -m netresearch.context summary [--file results/context.jsonl]

Stream: batches of B examples, one task per phase: base (50 batches), new (200), base (50), new (50). The net
first PREDICTS a batch with the current context c (fast weights scaled by c), is scored on it (online
accuracy, the stream metric), then sees the answers:
    L0 = loss of the frozen net (fast weights off), L1 = loss with fast weights fully on.
    r  = sigmoid((log(L0 / L1) - M) / TAU)    fast weights explain the batch clearly better than the base net
                                              (margin M: with F = 0, L0 = L1 gives r = 0.12, not a coin flip)
    s  = sigmoid((L0 - thr) / sd)             surprise: the base net is worse than on its own task
                                              (thr = mean + 3 sd of the base batch loss, calibrated once)
    w  = max(r, s)                            responsibility of the fast weights for this batch
    c <- (1 - ALPHA) c + ALPHA w              context for the NEXT batch
    Decisions are hard: the fast weights act fully if c > 0.5 (else not at all), and they learn (gate 1, step
    size eta) only from batches with w > 0.5. A soft gate was tried first (seed 5): a residual c of 0.03-0.17
    after the return to the base task still broke the base predictions with DFA fast weights (accuracy 0.6),
    and the small updates on base batches eroded the new skill.
Modes:
    err     the rule above.
    err_c   as err, but the fast weights learn only if the integrated context is on too (c > 0.5 before the
            batch, w > 0.5): a single surprising base batch (heavy-tailed base loss, about 2 per 50 batches
            above mean + 3 sd) then no longer trains them on base data.
    oracle  c = 1 / w = 1 on new-task batches, 0 / 0 on base batches (perfect context, upper bound).
    always  c = 1, w = 1 everywhere (no gate: the fast weights learn every batch, as plain fine-tuning).
Measured per phase: online accuracy (first 10 batches / last 10), context c, switch delay (batches until c
crosses 0.5 after a task change).
"""
import argparse
import json
import math
import multiprocessing as mp
import time
import traceback
from pathlib import Path

import numpy as np
import torch

from .adapt import CASES, SPEC, start_net
from .fastweights import Fast, default_eta

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results" / "context.jsonl"
PHASES = [("base", 50), ("new", 200), ("base", 50), ("new", 50)]
B = 16
TAU, ALPHA, M = 0.2, 0.3, 0.4
COMBOS = [("xormask", "delta_head"), ("xormask", "grad"), ("prev", "dfa"), ("prev", "grad"),
          ("plus1", "delta_head"), ("plus1", "grad")]
MODES = ["err", "err_c", "oracle", "always"]


def _loss_acc(model, b, spec):
    from .train import run_sequence, supervised_loss
    logits, _ = run_sequence(model, b["obs"])
    loss = float(supervised_loss(spec, logits, b["target"], b["mask"]))
    pred = (logits[..., spec.out_slice] > 0).float()
    ok = (pred == b["target"]).float().min(-1).values * b["mask"]
    return loss, float(ok.sum() / b["mask"].sum())


def stream(model_name, seed, variant, case, rule, mode):
    from .tasks import make_task
    from .train import to_t
    base_name = CASES[case][0]
    model = start_net(model_name, base_name, seed)
    torch.manual_seed(seed + variant)
    task = make_task(base_name)
    n_new = sum(n for p, n in PHASES if p == "new") * B
    new_b, _ = CASES[case][1](variant + 10 * seed, n_new)          # fresh training-split examples, in order
    rng = np.random.default_rng(seed * 100 + variant + 7)
    eta = default_eta(rule + "@task")                              # tuned for the task-gated rule
    fw = Fast(model, rule + "@task", eta, seed * 100 + variant)

    def base_batch():
        return to_t(task.sample(B, rng))
    with torch.no_grad():                                            # calibration of the surprise threshold
        fw.task_on = 0.0
        cal = [_loss_acc(model, base_batch(), task.spec)[0] for _ in range(32)]
    mu, sd = float(np.mean(cal)), float(np.std(cal)) + 1e-6
    thr = mu + 3 * sd

    c, i_new, log = 0.0, 0, []
    for phase, n in PHASES:
        for _ in range(n):
            if phase == "new":
                b = {k: v[:, i_new * B:(i_new + 1) * B] for k, v in new_b.items()}
                i_new += 1
                spec = SPEC
            else:
                b, spec = base_batch(), task.spec
            if mode == "oracle":
                c = 1.0 if phase == "new" else 0.0
            elif mode == "always":
                c = 1.0
            gate = float(c > 0.5) if mode.startswith("err") else c
            with torch.no_grad():
                fw.task_on = gate
                _, acc = _loss_acc(model, b, spec)                    # predict first
                fw.task_on = 0.0
                l0, _ = _loss_acc(model, b, spec)
                fw.task_on = 1.0
                l1, _ = _loss_acc(model, b, spec)
            r = 1 / (1 + math.exp(-(math.log(max(l0, 1e-6) / max(l1, 1e-6)) - M) / TAU))
            s = 1 / (1 + math.exp(-max(min((l0 - thr) / sd, 50), -50)))
            w = {"err": max(r, s), "err_c": max(r, s), "oracle": c, "always": 1.0}[mode]
            log.append([phase, round(acc, 4), round(c, 3), round(w, 3), round(l0, 4), round(l1, 4), gate])
            learn = w > 0.5 and (mode != "err_c" or gate > 0.5)
            if mode.startswith("err"):
                c = (1 - ALPHA) * c + ALPHA * w
            if learn:
                fw.task_on = 1.0
                fw.step(b)
    return log, {"thr": round(thr, 4), "base_loss": round(mu, 4)}


def phase_stats(log):
    out, i = [], 0
    for p, n in PHASES:
        seg = log[i:i + n]
        acc, cs, gs = [x[1] for x in seg], [x[2] for x in seg], [x[6] for x in seg]
        want = p == "new"
        delay = next((j for j, gg in enumerate(gs) if (gg > 0.5) == want), n)   # batches with the wrong gate
        out.append({"phase": p, "acc_first10": round(float(np.mean(acc[:10])), 4),
                    "acc_last10": round(float(np.mean(acc[-10:])), 4), "acc": round(float(np.mean(acc)), 4),
                    "c_mean": round(float(np.mean(cs)), 3), "delay": delay})
        i += n
    return out


def _job(a):
    model_name, seed, case, rule, mode, variants = a
    try:
        t0 = time.time()
        runs = []
        for v in variants:
            log, info = stream(model_name, seed, v, case, rule, mode)
            runs.append({"variant": v, "phases": phase_stats(log), "log": log, **info})
        return {"model": model_name, "seed": seed, "case": case, "rule": rule, "mode": mode,
                "runs": runs, "time": round(time.time() - t0, 1)}
    except Exception:  # noqa: BLE001
        return {"model": model_name, "seed": seed, "case": case, "rule": rule, "mode": mode,
                "error": traceback.format_exc()}


def _init_worker():
    torch.set_num_threads(1)


def execute(jobs, workers, out):
    out = Path(out)
    done = set()
    if out.exists():
        for ln in out.read_text().splitlines():
            r = json.loads(ln)
            if "error" not in r:
                done.add((r["model"], r["seed"], r["case"], r["rule"], r["mode"]))
    jobs = [j for j in jobs if tuple(j[:5]) not in done]
    print(f"{len(jobs)} jobs, {workers} workers", flush=True)
    t0 = time.time()
    with mp.get_context("spawn").Pool(workers, initializer=_init_worker) as pool, out.open("a") as f:
        for i, r in enumerate(pool.imap_unordered(_job, jobs), 1):
            f.write(json.dumps(r) + "\n")
            f.flush()
            if "error" in r:
                msg = "ERROR " + r["error"].strip().splitlines()[-1]
            else:
                ph = [x["phases"] for x in r["runs"]]
                msg = " | ".join(f"{p['phase']} {np.mean([q[j]['acc'] for q in ph]):.2f}"
                                 f" c{np.mean([q[j]['c_mean'] for q in ph]):.2f}"
                                 f" d{np.mean([q[j]['delay'] for q in ph]):.0f}"
                                 for j, p in enumerate(ph[0])) + f" t={r['time']}s"
            print(f"[{i}/{len(jobs)} {(time.time() - t0) / 60:5.1f}min] {r['model']:11s} s{r['seed']} "
                  f"{r['case']:8s} {r['rule']:10s} {r['mode']:6s} {msg}", flush=True)


def summary(path):
    import pandas as pd
    rows = []
    for ln in Path(path).read_text().splitlines():
        r = json.loads(ln)
        if "error" in r:
            continue
        for x in r["runs"]:
            row = {"case": r["case"], "rule": r["rule"], "mode": r["mode"], "model": r["model"]}
            for j, p in enumerate(x["phases"]):
                tag = f"{p['phase'][0]}{j + 1}"
                row[f"{tag}_acc"] = p["acc"]
                row[f"{tag}_end"] = p["acc_last10"]
                row[f"{tag}_c"] = p["c_mean"]
                if j:
                    row[f"{tag}_d"] = p["delay"]
            rows.append(row)
    d = pd.DataFrame(rows)
    g = d.groupby(["case", "rule", "mode"]).mean(numeric_only=True).round(2)
    with pd.option_context("display.max_rows", 500, "display.width", 250, "display.max_columns", 50):
        print(g.to_string())


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("cmd", choices=["run", "summary"])
    ap.add_argument("--models", nargs="+", default=["layer_s"])
    ap.add_argument("--seeds", nargs="+", type=int, default=[0, 1, 2])
    ap.add_argument("--modes", nargs="+", default=MODES)
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--file", default=str(OUT))
    a = ap.parse_args()
    if a.cmd == "summary":
        summary(a.file)
    else:
        execute([(m, s, c, r, mo, [0, 1]) for s in a.seeds for c, r in COMBOS for m in a.models
                 for mo in a.modes], a.workers, a.out)


if __name__ == "__main__":
    main()
