"""Phase B, the fast-weight library under pressure (PLAN_TRAINER.md): more tasks than slots, and a rule per slot.

    python -m netresearch.library run --models layer_s hier_s layer_s_sp4 [--seeds 0 1 2] [--workers 6]
    python -m netresearch.library summary [--file results/library.jsonl]

Six new tasks with the SAME inputs (numseq sequences, training split), only the asked output differs:
    xm0F / xmA5   next number XOR 0x0F / 0xA5        (output-level changes)
    plus1 / minus1 next number +1 / -1 (mod 256)
    prev / prev2  the last / second-to-last visible number (copy: an inner change)
Stream (batches of B = 16): base 30, every task once (100 batches each), base 30, every task again (40 each)
in REVERSED order. With K slots and least-recently-used eviction the last K tasks of the first round are
still stored when they come back; the others were evicted and must be relearned. (In the same order LRU
would evict every task just before it returns.)
Selection and learning as slots.py (error comparison with competence level + floor, young-slot rule, learning
only when context and batch agree). Allocation with a WORKING BUFFER: there are K + 1 sets of fast weights,
at most K of them mature (>= Y updates, the library). NEW starts a young set in a free place or replaces a
young one (an abandoned start); only when a young set matures and the library is full is the least recently
used mature set evicted. Without the buffer (first smoke test) a short false alarm inside a weakly learned
task (minus1, accuracy 0.6) allocated a new set and thereby evicted a finished skill.
"Recently used" counts only CONFIRMED use (the active set and the batch's vote agree). Counting every use
let a related set that was briefly mis-selected (plus1 during minus1) displace an unrelated one (xmA5).
Rules per slot:
    delta_head, dfa   fixed as in slots.py.
    pick        a young slot trains BOTH a delta_head and a dfa set of fast weights (each on its own, gate 1);
                it predicts with the better one (running exact-match accuracy, then loss), and after Y updates
                it keeps that one and drops the other (decided after Y_PICK updates). (By loss alone delta_head wins too early: it lowers
                the BCE faster while dfa ends up more accurate on prev / prev2.) A first "rule choice by telemetry": output-level vs inner change.
Share only without harm (modes k3p / k6p): every set keeps a small anchor memory (reservoir of A examples
from the batches it learned from). Before a MATURE set is credited with a batch (its vote), a probe update on
that batch is applied (PROBE_STEPS steps) and undone again; if it lowers the exact-match accuracy on the
set's own anchors by more than H, the batch is not this set's task after all (the anchor loss ratio is logged
too): it votes for the active young set (if any) or NEW, so a
related but different task gets its own set instead of overwriting (plus1 / minus1 in the first run).
    Measured on seeds 5 / 6 (not in the run), this does NOT separate: with PROBE_STEPS = 3 the anchor loss
    ratio and the exact-match drop of a weakly learned set are as large for its OWN task (prev, plus1 with
    delta_head: drop median 0.03-0.06, p90 0.16) as for the related foreign one (minus1 on the plus1 set:
    median 0.00, p90 0.12). The noise of the learning rule hides the conflict.
Consistent sharing (modes k3c / k6c): a mature set explains a batch only if its exact-match accuracy on the
batch is at least RHO x its accuracy level (EMA on the batches it learned from; checked only if that level is
>= 0.1). Exact match is sharp where the BCE loss is not: the plus1 set predicts +1 and is almost never exactly
right on minus1, although most of the 8 output bits agree. No example memory needed.
The probe restores F, the rule choice and its running scores; it is meant for the local rules of this module
(delta_head, dfa, pick), whose updates have no optimizer state (grad / lora would keep Adam moments).
Modes: K = 2, 3, 6 library places (+ 1 buffer); oracle (6 slots, slot = task, perfect context).
Measured on the second visit: accuracy, first 10 batches, hit = the task's slot from the first round was still
alive (not evicted) when it came back, sel = fraction of batches predicted with that slot.
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

from .adapt import SPEC, _batch, _numseq_words, start_net
from .context import ALPHA, B, M, _loss_acc
from .fastweights import Fast, default_eta
from .slots import LVL, Y

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results" / "library.jsonl"
TASKS = {"xm0F": lambda w: w[:, 3] ^ 0x0F, "xmA5": lambda w: w[:, 3] ^ 0xA5, "plus1": lambda w: (w[:, 3] + 1) % 256,
         "minus1": lambda w: (w[:, 3] - 1) % 256, "prev": lambda w: w[:, 2], "prev2": lambda w: w[:, 1]}
ORDERS = [["xm0F", "prev", "plus1", "xmA5", "prev2", "minus1"], ["prev", "plus1", "xm0F", "minus1", "xmA5", "prev2"]]
FIRST, SECOND, N_BASE = 100, 40, 30
Y_PICK = 2 * Y
A, H, PROBE_STEPS = 32, 0.2, 3
RHO = 0.5
RULES = ["delta_head", "dfa", "pick"]
MODES = ["k2", "k3", "k6", "oracle", "k3c", "k6c"]   # + k3p / k6p (probe)


def phases(order):
    return [("base", N_BASE)] + [(t, FIRST) for t in order] + [("base", N_BASE)] + \
        [(t, SECOND) for t in reversed(order)]


def task_data(name, seed, variant, n):
    rng = np.random.default_rng(7919 * (list(TASKS).index(name) + 1) + 101 * seed + variant)
    w = _numseq_words(n, rng, "train")
    return _batch(w, np.full(n, 3), TASKS[name](w))


class Slot:
    """One library entry: one set of fast weights, or for rule 'pick' two candidates (delta_head, dfa)."""

    def __init__(self, model, rule, seed):
        names = ["delta_head", "dfa"] if rule == "pick" else [rule]
        self.members = []
        for i, r in enumerate(names):
            fw = Fast(model, r + "@task", default_eta(r + "@task"), seed + 17 * i)
            fw.task_on = 0.0
            self.members.append(fw)
        self.reset()

    def reset(self):
        with torch.no_grad():
            for fw in self.members:
                for f in fw.F.values():
                    f.zero_()
                if fw.opt is not None:
                    fw.opt = torch.optim.Adam(list(fw.F.values()), lr=fw.eta)
        self.choice = None if len(self.members) > 1 else 0
        self.ema = [None] * len(self.members)                    # running (accuracy, -loss) per candidate
        self.anchors, self.n_seen = [], 0

    def add_anchors(self, b, rng):
        """Reservoir of A examples (obs, target, mask) of the batches this set learned from."""
        for i in range(b["obs"].shape[1]):
            ex = tuple(b[k][:, i:i + 1] for k in ("obs", "target", "mask"))
            self.n_seen += 1
            if len(self.anchors) < A:
                self.anchors.append(ex)
            else:
                j = int(rng.integers(self.n_seen))
                if j < A:
                    self.anchors[j] = ex

    def anchor_batch(self):
        return {k: torch.cat([a[i] for a in self.anchors], dim=1) for i, k in enumerate(("obs", "target", "mask"))}

    def snapshot(self):
        return ([{n: f.clone() for n, f in fw.F.items()} for fw in self.members], self.choice,
                list(self.ema))

    def restore(self, snap):
        Fs, self.choice, self.ema = snap
        with torch.no_grad():
            for fw, F0 in zip(self.members, Fs):
                for n, f in fw.F.items():
                    f.copy_(F0[n])

    def cur(self):
        if self.choice is not None:
            return self.choice
        if any(x is None for x in self.ema):
            return 0
        return max(range(len(self.ema)), key=lambda i: self.ema[i])

    def on(self, x):
        k = self.cur()
        for i, fw in enumerate(self.members):
            fw.task_on = x if i == k else 0.0

    def step(self, b, spec, n_upd):
        if self.choice is not None:
            self.on(1.0)
            self.members[self.choice].step(b)
            return
        for i, fw in enumerate(self.members):                    # young 'pick' slot: train both candidates
            for j, g in enumerate(self.members):
                g.task_on = float(i == j)
            with torch.no_grad():
                li, ai = _loss_acc(fw.model, b, spec)
            e = self.ema[i]
            self.ema[i] = (ai, -li) if e is None else (0.8 * e[0] + 0.2 * ai, 0.8 * e[1] - 0.2 * li)
            fw.step(b)
        if n_upd + 1 >= Y_PICK:                                  # decide: keep the better rule
            self.choice = self.cur()
            with torch.no_grad():
                for i, fw in enumerate(self.members):
                    if i != self.choice:
                        for f in fw.F.values():
                            f.zero_()


def stream(model_name, seed, variant, rule, mode):
    from .tasks import make_task
    from .train import to_t
    order = ORDERS[variant % 2]
    model = start_net(model_name, "numseq", seed)
    torch.manual_seed(seed + variant)
    task = make_task("numseq")
    data = {t: task_data(t, seed, variant, (FIRST + SECOND) * B) for t in order}
    used = {t: 0 for t in order}
    rng = np.random.default_rng(seed * 100 + variant + 7)
    arng = np.random.default_rng(seed * 100 + variant + 99)       # anchors: own stream, base batches unchanged
    probe, consist = mode.endswith("p"), mode.endswith("c")
    cap = {"k2": 2, "k3": 3, "k3p": 3, "k3c": 3}.get(mode, 6)                     # library capacity (mature sets)
    K = cap + (mode != "oracle")                                # + 1 working buffer
    slots = [Slot(model, rule, seed * 100 + variant + 1000 * i) for i in range(K)]

    def set_active(a):
        for i, sl in enumerate(slots, 1):
            sl.on(float(i == a))

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
    aval = [None] * (K + 1)                                     # accuracy level per set
    gen = [0] * (K + 1)                                         # allocation counter per slot (identity)
    active, n_upd, in_use, last_use, n_alloc = 0, [0] * (K + 1), [False] * (K + 1), [0] * (K + 1), 0
    log, choices, alive, t = [], [], [], 0
    for phase, n in phases(order):
        alive.append([j * 1000 + gen[j] for j in range(1, K + 1) if in_use[j]])   # slot identities at phase start
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
                if active and not in_use[active]:
                    in_use[active], gen[active] = True, 1
            with torch.no_grad():
                set_active(active)
                _, acc = _loss_acc(model, b, spec)                  # predict first
                set_active(0)
                l0, _ = _loss_acc(model, b, spec)
                ls, accs = {}, {}
                for i in range(1, K + 1):
                    if in_use[i]:
                        set_active(i)
                        ls[i], accs[i] = _loss_acc(model, b, spec)
            expl = {i: li for i, li in ls.items() if math.log(max(l0, 1e-6) / max(li, 1e-6)) > M
                    and (lvl[i] is None or li < LVL * lvl[i] + thr)
                    and not (consist and n_upd[i] >= Y and aval[i] is not None and aval[i] >= 0.1
                             and accs[i] < RHO * aval[i])}
            if mode == "oracle":
                vote = active
            elif expl:
                vote = min(expl, key=expl.get)
            elif l0 > thr:
                vote = active if (active and n_upd[active] < Y) else NEW
            else:
                vote = 0
            ratio = None
            if probe and 1 <= vote <= K and n_upd[vote] >= Y and len(slots[vote - 1].anchors) >= A // 2:                               # probe: would learning this batch hurt?
                sl = slots[vote - 1]
                ab = sl.anchor_batch()
                set_active(vote)
                with torch.no_grad():
                    before, acc_b = _loss_acc(model, ab, SPEC)
                snap = sl.snapshot()
                set_active(0)
                for _ in range(PROBE_STEPS):                        # same procedure as real learning; an
                    sl.step(b, spec, 0 if sl.choice is None else Y_PICK)   # undecided pick trains both

                set_active(vote)
                with torch.no_grad():
                    after, acc_a = _loss_acc(model, ab, SPEC)
                sl.restore(snap)
                ratio = (round(after / max(before, 1e-6), 3), round(acc_b - acc_a, 4))
                if ratio[1] > H:
                    vote = active if (active and n_upd[active] < Y) else NEW
            log.append([phase, round(acc, 4), active * 1000 + gen[active] if active else 0, vote,
                        ratio])
            if vote == active:
                last_use[active] = t                                # LRU: confirmed use only
            if active and vote == active:
                la = ls.get(active)
                if la is not None:
                    lvl[active] = la if lvl[active] is None else 0.9 * lvl[active] + 0.1 * la
                    aa = accs[active]
                    aval[active] = aa if aval[active] is None else 0.9 * aval[active] + 0.1 * aa
                set_active(0)
                sl = slots[active - 1]
                undecided = sl.choice is None
                sl.step(b, spec, n_upd[active])
                if probe:
                    sl.add_anchors(b, arng)
                if undecided and sl.choice is not None:
                    choices.append([phase, ["delta_head", "dfa"][sl.choice]])
                n_upd[active] += 1
                mature = [j for j in range(1, K + 1) if in_use[j] and n_upd[j] >= Y]
                if mode != "oracle" and n_upd[active] == Y and len(mature) > cap:     # consolidate: evict LRU
                    j = min((j for j in mature if j != active), key=lambda i: last_use[i])
                    slots[j - 1].reset()
                    in_use[j], n_upd[j], lvl[j], aval[j] = False, 0, None, None
                    c[0] += c[j]
                    c[j] = 0.0
            if mode == "oracle":
                continue
            c = (1 - ALPHA) * c
            c[vote] += ALPHA
            top = int(np.argmax(c))
            if c[top] > 0.5 and top != active:
                if top == NEW:
                    free = [i for i in range(1, K + 1) if not in_use[i]]
                    young = [i for i in range(1, K + 1) if in_use[i] and n_upd[i] < Y and i != active]
                    j = free[0] if free else (young[0] if young else min(range(1, K + 1), key=lambda i: last_use[i]))
                    if in_use[j]:
                        slots[j - 1].reset()
                    n_upd[j], lvl[j], aval[j] = 0, None, None
                    in_use[j], last_use[j] = True, t
                    gen[j] += 1
                    c[j], c[NEW] = c[j] + c[NEW], 0.0
                    n_alloc += 1
                    active = j
                else:
                    active = top
    return log, {"thr": round(thr, 4), "n_alloc": n_alloc, "order": order, "choices": choices, "alive": alive}


def phase_stats(log, order, alive):
    mapping, i = {}, 0
    for p, n in phases(order):                                  # slot identity at the end of the first visit
        if p != "base" and p not in mapping:
            tail = [x[2] for x in log[i + n - 20:i + n]]
            mapping[p] = max(set(tail), key=tail.count)
        i += n
    out, i, seen = [], 0, set()
    for k, (p, n) in enumerate(phases(order)):
        seg = log[i:i + n]
        second = p in seen and p != "base"
        seen.add(p)
        if p != "base":
            want = mapping[p] if mapping[p] else -1             # mapped to base = never learned
            hit = (want in alive[k]) if second else True        # not evicted before the second visit
            out.append({"phase": p, "visit": 2 if second else 1,
                        "acc": round(float(np.mean([x[1] for x in seg])), 4),
                        "acc_first10": round(float(np.mean([x[1] for x in seg[:10]])), 4),
                        "acc_last10": round(float(np.mean([x[1] for x in seg[-10:]])), 4),
                        "sel": round(float(np.mean([x[2] == want for x in seg])), 4), "hit": float(hit)})
        i += n
    return out


def _job(a):
    model_name, seed, rule, mode, variants = a
    try:
        t0 = time.time()
        runs = []
        for v in variants:
            log, info = stream(model_name, seed, v, rule, mode)
            runs.append({"variant": v, "phases": phase_stats(log, info["order"], info["alive"]), "log": log, **info})
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
                sec = [p for x in r["runs"] for p in x["phases"] if p["visit"] == 2]
                msg = (f"2nd acc {np.mean([p['acc'] for p in sec]):.2f} hit {np.mean([p['hit'] for p in sec]):.2f}"
                       f" alloc {np.mean([x['n_alloc'] for x in r['runs']]):.1f} t={r['time']}s")
            print(f"[{i}/{len(jobs)} {(time.time() - t0) / 60:5.1f}min] {r['model']:11s} s{r['seed']} "
                  f"{r['rule']:10s} {r['mode']:6s} {msg}", flush=True)


def summary(path):
    import pandas as pd
    rows, ch = [], []
    for ln in Path(path).read_text().splitlines():
        r = json.loads(ln)
        if "error" in r:
            continue
        for x in r["runs"]:
            for p in x["phases"]:
                rows.append({"rule": r["rule"], "mode": r["mode"], "task": p["phase"], "visit": p["visit"],
                             "acc": p["acc"], "first10": p["acc_first10"], "end": p["acc_last10"],
                             "sel": p["sel"], "hit": p["hit"], "alloc": x["n_alloc"]})
            for ph, cc in x.get("choices", []):
                ch.append({"mode": r["mode"], "task": ph, "dfa": float(cc == "dfa")})
    d = pd.DataFrame(rows)
    with pd.option_context("display.max_rows", 500, "display.width", 250, "display.max_columns", 50):
        print(d.groupby(["rule", "mode", "visit"]).mean(numeric_only=True).round(2).to_string())
        print()
        print(d[d.visit == 2].pivot_table(index=["rule", "mode"], columns="task", values="acc").round(2).to_string())
        if ch:
            print("\npick: share of slots that chose dfa, by the task they were allocated for")
            print(pd.DataFrame(ch).pivot_table(index="mode", columns="task", values="dfa").round(2).to_string())


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
