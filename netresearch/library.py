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
Stable rule choice (rule pickm): as pick, but the choice waits for a clear lead: after >= Y_PICK updates it
keeps the candidate whose SLOW running accuracy (EMA rate PICK_A) leads by more than PICK_M, at the latest
after PICK_H updates. On the copy tasks dfa learns slower at first and often overtakes delta_head only after
60 updates (seeds 5 / 6, both candidates trained 140 updates: dfa is better at the end in 11 of 12 copy runs,
the fixed decision at 60 picks it in 8). Until then the slot predicts with the currently better candidate.
Fast re-recognition (flag f, modes k3cf / k6cf): the vote is already right on the first batch of a returning
task, but the context EMA needs 2 batches to cross 0.5. If the active hypothesis FAILS clearly (base: loss
above the surprise threshold; a mature set: exact match below RHO x its level) and the vote is another stored
hypothesis (base or a mature set, consistent by the test above), the context switches at once. NEW (a new
allocation) still needs the EMA, so a single false alarm cannot allocate.
Noise-aware consistency (flag n, modes k3cfn / k6cfn): a set counts as inconsistent only if its exact match is
below RHO x its level by more than Z_CONS binomial sd, sqrt(p (1 - p) / m) with m examples scored in the
batch. Without it a weakly learned copy set (level ~0.15, 1 of 16 right = 0.06 < 0.08) failed on single
noisy batches although it lowered the loss 6-8 fold; two such batches in a row allocated a new set and threw
the progress away (0.8 restarts per copy task, mostly hier_s; diagnosed with NETRESEARCH_LIB_DIAG=1 on seeds
5 / 6). plus1 on minus1 (level ~0.6, threshold 0.18, accuracy ~0) is still rejected.
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
import os
import re
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
         "minus1": lambda w: (w[:, 3] - 1) % 256, "prev": lambda w: w[:, 2], "prev2": lambda w: w[:, 1],
         # suite "twelve" adds (appended: the data seeds of the first six stay unchanged)
         "xm33": lambda w: w[:, 3] ^ 0x33, "xmFF": lambda w: w[:, 3] ^ 0xFF, "plus2": lambda w: (w[:, 3] + 2) % 256,
         "minus2": lambda w: (w[:, 3] - 2) % 256, "prev3": lambda w: w[:, 0],
         "diff": lambda w: (w[:, 2] - w[:, 1]) % 256}           # step of the sequence (an inner computation)
ORDERS = [["xm0F", "prev", "plus1", "xmA5", "prev2", "minus1"], ["prev", "plus1", "xm0F", "minus1", "xmA5", "prev2"]]
ORDERS12 = [["xm0F", "prev", "plus1", "xm33", "prev2", "minus2", "xmA5", "diff", "plus2", "xmFF", "prev3", "minus1"],
            ["prev", "plus2", "xm33", "minus1", "prev3", "xmA5", "plus1", "diff", "xmFF", "prev2", "minus2", "xm0F"]]
DRIFT, N_DRIFT, N_AFTER = "plus1>plus2", 100, 50
FIRST, SECOND, N_BASE = 100, 40, 30
Y_PICK = 2 * Y
PICK_A, PICK_M, PICK_H = 0.05, 0.15, 4 * Y                 # pickm: slow accuracy EMA, lead margin, horizon
A, H, PROBE_STEPS = 32, 0.2, 3
RHO = 0.5
Z_CONS = 1.0                                               # flag n: consistency slack in binomial sd
DRIFT_FRAC, DRIFT_FRAC_STRICT, DRIFT_Z = 0.25, 0.4, 3.0                            # flag d: fork if the level falls this far below its peak
# (the larger of DRIFT_FRAC x peak and DRIFT_Z sd of the level EMA; that sd is 0.23 x the batch sd: EMA rate 0.1)
DIAG = bool(os.environ.get("NETRESEARCH_LIB_DIAG"))         # log the explain criteria of the active set
RULES = ["delta_head", "dfa", "pick", "pickm"]
MODES = ["k2", "k3", "k6", "oracle", "k3c", "k6c", "k3cf", "k6cf", "k3cfn", "k6cfn"]   # + k3p / k6p (probe), any kN...


def phases(order):
    return [("base", N_BASE)] + [(t, FIRST) for t in order] + [("base", N_BASE)] + \
        [(t, SECOND) for t in reversed(order)]


def drift_plan(order):
    """order ends with plus1; plus1 turns into plus2 gradually (share of plus2 examples 0 -> 1 over N_DRIFT
    batches), plus2 stays N_AFTER batches; after the base break plus2, the others and finally plus1 return."""
    return ([("base", N_BASE)] + [(t, FIRST) for t in order] + [(DRIFT, N_DRIFT), ("plus2", N_AFTER),
            ("base", N_BASE), ("plus2", SECOND)] + [(t, SECOND) for t in order[:-1][::-1]] + [("plus1", SECOND)])


SUITES = {"six": {"tasks": list(ORDERS[0]), "orders": ORDERS, "plan": phases},
          "twelve": {"tasks": list(ORDERS12[0]), "orders": ORDERS12, "plan": phases},
          "drift": {"tasks": ["xm0F", "prev", "plus1", "plus2"],
                    "orders": [["xm0F", "prev", "plus1"], ["prev", "xm0F", "plus1"]], "plan": drift_plan}}


def drift_data(a, b, seed, variant, n_batches):
    """Batches whose examples follow task b with probability (i + 0.5) / n_batches in batch i, else task a."""
    rng = np.random.default_rng(31337 + 101 * seed + variant)
    n = n_batches * B
    w = _numseq_words(n, rng, "train")
    da, db = _batch(w, np.full(n, 3), TASKS[a](w)), _batch(w, np.full(n, 3), TASKS[b](w))
    use_b = torch.from_numpy(rng.random(n) < (np.arange(n) // B + 0.5) / n_batches)
    da["target"] = torch.where(use_b[None, :, None], db["target"], da["target"])
    return da


def task_data(name, seed, variant, n):
    rng = np.random.default_rng(7919 * (list(TASKS).index(name) + 1) + 101 * seed + variant)
    w = _numseq_words(n, rng, "train")
    return _batch(w, np.full(n, 3), TASKS[name](w))


class Slot:
    """One library entry: one set of fast weights, or for rule 'pick' two candidates (delta_head, dfa)."""

    def __init__(self, model, rule, seed):
        names = ["delta_head", "dfa"] if rule.startswith("pick") else [rule]
        self.margin = rule == "pickm"
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
        self.slow = [None] * len(self.members)                   # pickm: slow running accuracy per candidate
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
                list(self.ema), list(self.slow))

    def restore(self, snap):
        Fs, self.choice, self.ema, self.slow = snap
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
            s = self.slow[i]
            self.slow[i] = ai if s is None else (1 - PICK_A) * s + PICK_A * ai
            fw.step(b)
        n = n_upd + 1
        if self.margin:                                          # sequential: decide on a clear lead only
            lead = self.slow[1] - self.slow[0]
            if n >= Y_PICK and (abs(lead) > PICK_M or n >= PICK_H):
                self.choice = int(lead > 0)
        elif n >= Y_PICK:                                        # decide: keep the better rule
            self.choice = self.cur()
        if self.choice is not None:
            with torch.no_grad():
                for i, fw in enumerate(self.members):
                    if i != self.choice:
                        for f in fw.F.values():
                            f.zero_()


def stream(model_name, seed, variant, rule, mode, suite="six"):
    from .tasks import make_task
    from .train import to_t
    S = SUITES[suite]
    order = S["orders"][variant % 2]
    plan = S["plan"](order)
    model = start_net(model_name, "numseq", seed)
    torch.manual_seed(seed + variant)
    task = make_task("numseq")
    if suite == "six":                                          # as before (same data streams)
        data = {t: task_data(t, seed, variant, (FIRST + SECOND) * B) for t in order}
    else:
        need = {}
        for p, n in plan:
            if p != "base":
                need[p] = need.get(p, 0) + n
        data = {t: drift_data("plus1", "plus2", seed, variant, n) if t == DRIFT else task_data(t, seed, variant, n * B)
                for t, n in need.items()}
    used = {t: 0 for t in data}
    rng = np.random.default_rng(seed * 100 + variant + 7)
    arng = np.random.default_rng(seed * 100 + variant + 99)       # anchors: own stream, base batches unchanged
    mk = re.fullmatch(r"k(\d+)([a-z]*)", mode)
    flags = mk.group(2) if mk else ""
    probe, consist, fast, noisy = "p" in flags, "c" in flags, "f" in flags, "n" in flags
    fork = "d" in flags or "e" in flags
    drift_frac = DRIFT_FRAC_STRICT if "e" in flags else DRIFT_FRAC          # e: stricter fork threshold
    cap = int(mk.group(1)) if mk else len(S["tasks"])          # library capacity (mature sets); oracle: a slot per task
    K = cap + (mode != "oracle")                                # + 1 working buffer
    slots = [Slot(model, rule, seed * 100 + variant + 1000 * i) for i in range(K)]

    def set_active(a):
        for i, sl in enumerate(slots, 1):
            sl.on(float(i == a))

    def base_batch():
        return to_t(task.sample(B, rng))
    def inconsistent(i, acc_i, m):
        """Exact match clearly below RHO x the set's own level (flag n: by more than one binomial sd)."""
        if n_upd[i] < Y or aval[i] is None or aval[i] < 0.1:
            return False
        slack = Z_CONS * math.sqrt(aval[i] * (1 - aval[i]) / m) if noisy else 0.0
        return acc_i < RHO * aval[i] - slack

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
    peak = [None] * (K + 1)                                     # flag d: best level (and lvl, snapshot then)
    gen = [0] * (K + 1)                                         # allocation counter per slot (identity)
    active, n_upd, in_use, last_use, n_alloc, n_fast = 0, [0] * (K + 1), [False] * (K + 1), [0] * (K + 1), 0, 0
    forks = []
    log, choices, alive, t, diag = [], [], [], 0, []
    for phase, n in plan:
        alive.append([j * 1000 + gen[j] for j in range(1, K + 1) if in_use[j]])   # slot identities at phase start
        for k_ph in range(n):
            t += 1
            if phase == "base":
                b, spec = base_batch(), task.spec
            else:
                i = used[phase]
                b, spec = {k: v[:, i * B:(i + 1) * B] for k, v in data[phase].items()}, SPEC
                used[phase] += 1
            if mode == "oracle":
                cur = phase if phase != DRIFT else ("plus1" if (k_ph + 0.5) / n < 0.5 else "plus2")
                active = 0 if phase == "base" else S["tasks"].index(cur) + 1
                if active and not in_use[active]:
                    in_use[active], gen[active] = True, 1
            with torch.no_grad():
                set_active(active)
                _, acc = _loss_acc(model, b, spec)                  # predict first
                m_b = float(b["mask"].sum())                       # examples scored in this batch
                set_active(0)
                l0, _ = _loss_acc(model, b, spec)
                ls, accs = {}, {}
                for i in range(1, K + 1):
                    if in_use[i]:
                        set_active(i)
                        ls[i], accs[i] = _loss_acc(model, b, spec)
            expl = {i: li for i, li in ls.items() if math.log(max(l0, 1e-6) / max(li, 1e-6)) > M
                    and (lvl[i] is None or li < LVL * lvl[i] + thr)
                    and not (consist and inconsistent(i, accs[i], m_b))}
            if DIAG and active and active in ls:   # why (not) explained: [t, phase, n, log L0/L, L / level bound,
                #   acc - RHO x level (without slack), acc, surprise, inconsistent (the test as applied)]
                la = ls[active]
                diag.append([t, phase, n_upd[active], round(math.log(max(l0, 1e-6) / max(la, 1e-6)), 3),
                             None if lvl[active] is None else round(la / (LVL * lvl[active] + thr), 3),
                             None if aval[active] is None else round(accs[active] - RHO * aval[active], 3),
                             round(accs[active], 3), int(l0 > thr),
                             int(consist and inconsistent(active, accs[active], m_b))])   # the actual test
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
                if fork and n_upd[active] >= Y and aval[active] is not None:
                    pk = peak[active]
                    if pk is None or aval[active] > pk[0]:          # new best level: keep a snapshot of it
                        peak[active] = (aval[active], lvl[active], slots[active - 1].snapshot())
                    elif pk[0] >= 0.1 and aval[active] < pk[0] - max(drift_frac * pk[0],
                                                                     DRIFT_Z * 0.23 * math.sqrt(pk[0] * (1 - pk[0]) / m_b)):
                        # drift: the set still explains and learns, but its level has fallen well below its best.
                        # The drifting state moves on in another place; the old set goes back to its best state.
                        free = [i for i in range(1, K + 1) if not in_use[i]]
                        young = [i for i in range(1, K + 1) if in_use[i] and n_upd[i] < Y]
                        k = free[0] if free else young[0]           # K = cap + 1: a non-mature place exists
                        j = active
                        slots[k - 1].restore(slots[j - 1].snapshot())
                        in_use[k], gen[k], last_use[k] = True, gen[k] + 1, t
                        n_upd[k], lvl[k], aval[k], peak[k] = n_upd[j], lvl[j], aval[j], None
                        slots[j - 1].restore(pk[2])
                        aval[j], lvl[j] = pk[0], pk[1]
                        c[k], c[j] = c[j], 0.0
                        forks.append([t, phase, j, k, round(pk[0], 3), round(aval[k], 3)])
                        active = k
                        mature = [i for i in range(1, K + 1) if in_use[i] and n_upd[i] >= Y]
                        if len(mature) > cap:                       # consolidate: evict the LRU mature set
                            e = min((i for i in mature if i not in (j, k)), key=lambda i: last_use[i])
                            slots[e - 1].reset()
                            in_use[e], n_upd[e], lvl[e], aval[e], peak[e] = False, 0, None, None, None
                            c[0] += c[e]
                            c[e] = 0.0
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
                    in_use[j], n_upd[j], lvl[j], aval[j], peak[j] = False, 0, None, None, None
                    c[0] += c[j]
                    c[j] = 0.0
            if mode == "oracle":
                continue
            if fast and vote != active and vote != NEW and (vote == 0 or n_upd[vote] >= Y):
                if active == 0:                                     # does the current hypothesis fail clearly?
                    fails = l0 > thr
                else:
                    fails = active in accs and inconsistent(active, accs[active], m_b)   # (not measured: just forked)
                if fails:                                           # ... and a stored one explains: switch now
                    c[:] = 0.0
                    c[vote] = 1.0
                    n_fast += 1
                    active = vote
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
                    n_upd[j], lvl[j], aval[j], peak[j] = 0, None, None, None
                    in_use[j], last_use[j] = True, t
                    gen[j] += 1
                    c[j], c[NEW] = c[j] + c[NEW], 0.0
                    n_alloc += 1
                    active = j
                else:
                    active = top
    return log, {"thr": round(thr, 4), "n_alloc": n_alloc, "n_fast": n_fast, "n_fork": len(forks), "forks": forks,
                 "order": order, "plan": plan,
                 "choices": choices,
                 "alive": alive, **({"diag": diag} if DIAG else {})}


def phase_stats(log, plan, alive):
    mapping, i = {}, 0
    for p, n in plan:                                  # slot identity at the end of the first visit
        if p != "base" and p not in mapping:
            tail = [x[2] for x in log[i + n - 20:i + n]]
            mapping[p] = max(set(tail), key=tail.count)
        i += n
    out, i, seen = [], 0, set()
    for k, (p, n) in enumerate(plan):
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
    model_name, seed, rule, mode, variants, suite = a
    key = {"model": model_name, "seed": seed, "rule": rule, "mode": mode, "suite": suite}
    try:
        t0 = time.time()
        runs = []
        for v in variants:
            log, info = stream(model_name, seed, v, rule, mode, suite)
            runs.append({"variant": v, "phases": phase_stats(log, info["plan"], info["alive"]), "log": log, **info})
        return {**key, "runs": runs, "time": round(time.time() - t0, 1)}
    except Exception:  # noqa: BLE001
        return {**key, "error": traceback.format_exc()}


def _init_worker():
    torch.set_num_threads(1)


def execute(jobs, workers, out):
    out = Path(out)
    done = set()
    if out.exists():
        for ln in out.read_text().splitlines():
            r = json.loads(ln)
            if "error" not in r:
                done.add((r["model"], r["seed"], r["rule"], r["mode"], r.get("suite", "six")))
    jobs = [j for j in jobs if (*j[:4], j[5]) not in done]
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
                  f"{r['rule']:10s} {r['mode']:6s} {r['suite']:6s} {msg}", flush=True)


def summary(path, suite="six"):
    import pandas as pd
    rows, ch = [], []
    for ln in Path(path).read_text().splitlines():
        r = json.loads(ln)
        if "error" in r or r.get("suite", "six") != suite:
            continue
        for x in r["runs"]:
            for p in x["phases"]:
                rows.append({"rule": r["rule"], "mode": r["mode"], "task": p["phase"], "visit": p["visit"],
                             "acc": p["acc"], "first10": p["acc_first10"], "end": p["acc_last10"],
                             "sel": p["sel"], "hit": p["hit"], "alloc": x["n_alloc"],
                             "fast": x.get("n_fast", 0)})
            for ph, cc in x.get("choices", []):
                ch.append({"rule": r["rule"], "mode": r["mode"], "task": ph, "dfa": float(cc == "dfa")})
    d = pd.DataFrame(rows)
    with pd.option_context("display.max_rows", 500, "display.width", 250, "display.max_columns", 50):
        print(d.groupby(["rule", "mode", "visit"]).mean(numeric_only=True).round(2).to_string())
        print()
        print(d[d.visit == 2].pivot_table(index=["rule", "mode"], columns="task", values="acc").round(2).to_string())
        if ch:
            print("\npick: share of slots that chose dfa, by the task they were allocated for")
            print(pd.DataFrame(ch).pivot_table(index=["rule", "mode"], columns="task", values="dfa").round(2).to_string())


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
    ap.add_argument("--suites", nargs="+", default=["six"], choices=list(SUITES))
    a = ap.parse_args()
    if a.cmd == "summary":
        for su in a.suites:
            print(f"== suite {su}")
            summary(a.file, su)
    else:
        execute([(m, s, r, mo, [0, 1], su) for su in a.suites for s in a.seeds for r in a.rules for m in a.models
                 for mo in a.modes], a.workers, a.out)


if __name__ == "__main__":
    main()
