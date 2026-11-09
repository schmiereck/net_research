"""Phase B, several sets of fast weights chosen by error comparison (PLAN_TRAINER.md): a first skill library.

    python -m netresearch.slots run --models layer_s hier_s layer_s_sp4 [--seeds 0 1 2] [--workers 6]
    python -m netresearch.slots summary [--file results/slots.jsonl]

Stream (batches of B = 16, same inputs for all tasks: numseq sequences): base 30, then three new tasks
xormask / prev / plus1 with 150 batches each, base 30, and a second visit of every new task (40 each).
Variant 0 visits them in the order xormask, prev, plus1, variant 1 in the order plus1, xormask, prev.
As in context.py the net first predicts a batch with the active hypothesis, then sees the answers.

Hypotheses: base (all fast weights off), slot 1..K (one set of fast weights on), NEW. Per batch:
    L0 = loss of the frozen net, L_i = loss with slot i alone.
    slot i explains the batch if log(L0 / L_i) > M (clearly better than the base net) AND L_i < LVL x its own
    level (EMA of its loss on the batches it learned from) + thr (floor: near zero loss a relative test alone
    fires on normal outliers; without it delta_head allocated 6.4 slots for 3 tasks, results/slots_nofloor.jsonl). The second condition is needed: on a DIFFERENT
    new task the base net is confidently wrong, and a slot with less confident outputs already has a much
    lower BCE loss without knowing the task (first smoke test: no new slot was allocated). s = surprise of the
    base net (L0 > mean + 3 sd of its own batch loss, calibrated once).
    vote = the explaining slot with the lowest loss; else, if surprised: the active slot while it is young
           (fewer than Y updates, still learning its task), otherwise NEW; else base.
    c = EMA of the one-hot votes (ALPHA). The active hypothesis changes when another one has c > 0.5.
    NEW becoming active allocates a slot (first unused one, else the least recently used one, reset).
    Only the active slot learns, and only from batches that vote for it (err_c of context.py).
Modes:
    multi   K = 4 slots (enough for the three tasks).
    single  K = 1: every new task resets and relearns the one slot (no library, but the base is protected).
    shared  K = 1 without reset: one set of fast weights learns all new tasks in turn (interference).
    oracle  slot = task, base = off, perfect context (upper bound).
Measured per phase: online accuracy, and "sel" = fraction of batches predicted with the right hypothesis
(base for base, for a new task the slot it used at the end of its first visit).
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
from .context import ALPHA, B, M, _loss_acc
from .fastweights import Fast, default_eta

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results" / "slots.jsonl"
ORDERS = [["xormask", "prev", "plus1"], ["plus1", "xormask", "prev"]]
FIRST, SECOND, N_BASE = 150, 40, 30
Y = 30
LVL = 2.0
RULES = ["grad", "delta_head", "dfa"]
MODES = ["multi", "single", "shared", "oracle"]


def phases(order):
    return [("base", N_BASE)] + [(t, FIRST) for t in order] + [("base", N_BASE)] + [(t, SECOND) for t in order]


def _new_slot(model, rule, eta, seed):
    fw = Fast(model, rule + "@task", eta, seed)
    fw.task_on = 0.0
    return fw


def _reset(fw):
    with torch.no_grad():
        for f in fw.F.values():
            f.zero_()
    if fw.opt is not None:
        fw.opt = torch.optim.Adam(list(fw.F.values()), lr=fw.eta)


def stream(model_name, seed, variant, rule, mode):
    from .tasks import make_task
    from .train import to_t
    order = ORDERS[variant % 2]
    model = start_net(model_name, "numseq", seed)
    torch.manual_seed(seed + variant)
    task = make_task("numseq")
    data = {t: CASES[t][1](variant + 10 * seed, (FIRST + SECOND) * B)[0] for t in order}
    used = {t: 0 for t in order}
    rng = np.random.default_rng(seed * 100 + variant + 7)
    eta = default_eta(rule + "@task")
    K = {"multi": 4, "oracle": 3}.get(mode, 1)
    slots = [_new_slot(model, rule, eta, seed * 100 + variant + 1000 * i) for i in range(K)]

    def set_active(a):                                     # a = 0 base, i >= 1 slot i
        for i, fw in enumerate(slots, 1):
            fw.task_on = float(i == a)

    def base_batch():
        return to_t(task.sample(B, rng))
    with torch.no_grad():
        set_active(0)
        cal = [_loss_acc(model, base_batch(), task.spec)[0] for _ in range(32)]
    mu, sd = float(np.mean(cal)), float(np.std(cal)) + 1e-6
    thr = mu + 3 * sd

    NEW = K + 1
    c = np.zeros(K + 2)
    c[0] = 1.0
    lvl = [None] * (K + 1)
    active, n_upd, in_use, last_use, n_alloc, log = 0, [0] * (K + 1), [False] * (K + 1), [0] * (K + 1), 0, []
    t = 0
    for phase, n in phases(order):
        for _ in range(n):
            t += 1
            if phase == "base":
                b, spec = base_batch(), task.spec
            else:
                i = used[phase]
                b, spec = {k: v[:, i * B:(i + 1) * B] for k, v in data[phase].items()}, SPEC
                used[phase] += 1
            if mode == "oracle":
                active = 0 if phase == "base" else order.index(phase) + 1
            with torch.no_grad():
                set_active(active)
                _, acc = _loss_acc(model, b, spec)                  # predict first
                set_active(0)
                l0, _ = _loss_acc(model, b, spec)
                ls = {}
                for i in range(1, K + 1):
                    if in_use[i]:
                        set_active(i)
                        ls[i] = _loss_acc(model, b, spec)[0]
            s = l0 > thr
            expl = {i: li for i, li in ls.items() if math.log(max(l0, 1e-6) / max(li, 1e-6)) > M
                    and (lvl[i] is None or li < LVL * lvl[i] + thr)}
            if expl:
                vote = min(expl, key=expl.get)
            elif s:
                vote = active if (active and n_upd[active] < Y) else NEW
            else:
                vote = 0
            if mode == "oracle":
                vote = active
            log.append([phase, round(acc, 4), active, vote, round(l0, 4)])
            last_use[active] = t                                    # LRU: last use, not last update
            if active and vote == active:                           # learn: context and batch agree
                la = ls.get(active)
                if la is not None:
                    lvl[active] = la if lvl[active] is None else 0.9 * lvl[active] + 0.1 * la
                set_active(active)
                slots[active - 1].step(b)
                n_upd[active] += 1
            if mode == "oracle":
                in_use[active] = True
                continue
            c = (1 - ALPHA) * c
            c[vote] += ALPHA
            top = int(np.argmax(c))
            if c[top] > 0.5 and top != active:
                if top == NEW:
                    free = [i for i in range(1, K + 1) if not in_use[i]]
                    j = free[0] if free else min(range(1, K + 1), key=lambda i: last_use[i])
                    if in_use[j] and mode != "shared":
                        _reset(slots[j - 1])
                        n_upd[j], lvl[j] = 0, None
                    if mode == "shared" and in_use[j]:
                        n_upd[j], lvl[j] = 0, None                               # young again: may learn the new task
                    in_use[j], last_use[j] = True, t
                    c[j], c[NEW] = c[j] + c[NEW], 0.0                # keep the EMA normalised
                    n_alloc += 1
                    active = j
                else:
                    active = top
    return log, {"thr": round(thr, 4), "n_alloc": n_alloc, "order": order}


def phase_stats(log, order):
    mapping = {}
    i = 0
    for p, n in phases(order):                                 # slot used at the end of the first visit
        if p != "base" and p not in mapping:
            tail = [x[2] for x in log[i + n - 20:i + n]]
            mapping[p] = max(set(tail), key=tail.count)
        i += n
    out, i, seen = [], 0, set()
    for p, n in phases(order):
        seg = log[i:i + n]
        want = 0 if p == "base" else mapping[p]            # a new task mapped to base was never learned:
        if p != "base" and want == 0:                       # its selection counts as failed
            want = -1
        visit = 2 if (p in seen and p != "base") else 1
        seen.add(p)
        out.append({"phase": p, "visit": visit if p != "base" else (1 if i == 0 else 2),
                    "acc": round(float(np.mean([x[1] for x in seg])), 4),
                    "acc_first10": round(float(np.mean([x[1] for x in seg[:10]])), 4),
                    "acc_last10": round(float(np.mean([x[1] for x in seg[-10:]])), 4),
                    "sel": round(float(np.mean([x[2] == want for x in seg])), 4),
                    "slot": want})
        i += n
    return out


def _job(a):
    model_name, seed, rule, mode, variants = a
    try:
        t0 = time.time()
        runs = []
        for v in variants:
            log, info = stream(model_name, seed, v, rule, mode)
            runs.append({"variant": v, "phases": phase_stats(log, info["order"]), "log": log, **info})
        return {"model": model_name, "seed": seed, "rule": rule, "mode": mode, "runs": runs,
                "time": round(time.time() - t0, 1)}
    except Exception:  # noqa: BLE001
        return {"model": model_name, "seed": seed, "rule": rule, "mode": mode, "error": traceback.format_exc()}


def _init_worker():
    torch.set_num_threads(1)


def execute(jobs, workers, out):
    out = Path(out)
    done = set()
    if out.exists():
        for ln in out.read_text().splitlines():
            r = json.loads(ln)
            if "error" not in r:
                done.add((r["model"], r["seed"], r["rule"], r["mode"]))
    jobs = [j for j in jobs if tuple(j[:4]) not in done]
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
                second = [p for q in ph for p in q if p["visit"] == 2 and p["phase"] != "base"]
                msg = (f"2nd visit acc {np.mean([p['acc'] for p in second]):.2f} sel "
                       f"{np.mean([p['sel'] for p in second]):.2f} alloc "
                       f"{np.mean([x['n_alloc'] for x in r['runs']]):.1f} t={r['time']}s")
            print(f"[{i}/{len(jobs)} {(time.time() - t0) / 60:5.1f}min] {r['model']:11s} s{r['seed']} "
                  f"{r['rule']:10s} {r['mode']:6s} {msg}", flush=True)


def summary(path):
    import pandas as pd
    rows = []
    for ln in Path(path).read_text().splitlines():
        r = json.loads(ln)
        if "error" in r:
            continue
        for x in r["runs"]:
            for p in x["phases"]:
                rows.append({"rule": r["rule"], "mode": r["mode"], "model": r["model"], "task": p["phase"],
                             "visit": p["visit"], "acc": p["acc"], "first10": p["acc_first10"],
                             "end": p["acc_last10"], "sel": p["sel"], "alloc": x["n_alloc"]})
    d = pd.DataFrame(rows)
    g = d.groupby(["rule", "mode", "task", "visit"]).mean(numeric_only=True).round(2).unstack("visit")
    with pd.option_context("display.max_rows", 500, "display.width", 250, "display.max_columns", 50):
        print(g.to_string())


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("cmd", choices=["run", "summary"])
    ap.add_argument("--models", nargs="+", default=["layer_s"])
    ap.add_argument("--seeds", nargs="+", type=int, default=[0, 1, 2])
    ap.add_argument("--rules", nargs="+", default=RULES)
    ap.add_argument("--modes", nargs="+", default=MODES)
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--file", default=str(OUT))
    a = ap.parse_args()
    if a.cmd == "summary":
        summary(a.file)
    else:
        execute([(m, s, r, mo, [0, 1]) for s in a.seeds for r in a.rules for m in a.models for mo in a.modes],
                a.workers, a.out)


if __name__ == "__main__":
    main()
