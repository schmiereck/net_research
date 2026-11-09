"""Phase B (PLAN_TRAINER.md): fast weights on a frozen trained net, updated by FIXED rules (no learned teacher).

    python -m netresearch.fastweights sweep  [--models layer_s] [--seed 0]        # step sizes per rule
    python -m netresearch.fastweights run    --models layer_s hier_s ... [--seeds 0 1 2] [--workers 5]
    python -m netresearch.fastweights summary [--file results/fastweights.jsonl]

Question: does a fast weight layer alone give k-shot learning without forgetting? The slow weights W (the
benchmark checkpoint) stay frozen; every linear map of the shared module (fc1, fc2) and the output head get
W_eff = W + F, and only F changes. Measured on the adaptation case fixcycle (adapt.py) like phase A: score on
the new cycle and retention of the base task after s = 0..200 updates, F active the whole time.

Rules (the update signal each one needs is what a teacher would have to provide later):
    lora        T2 with the gradient: F = u v^T (rank 4) per map, u, v trained by Adam (lr 1e-2).
                Upper bound for "low rank alone": is restricting the change enough against forgetting?
    delta_head  T1, local: only the head, delta rule dF = -eta x^T e / |x|^2, e = sigmoid(logits) - target.
                Is the trained representation already good enough that a new readout suffices?
    dfa         T1, local with a broadcast error: head as delta_head; fc1 / fc2 of every cell get
                dF = -eta x^T delta / |x|^2 with delta = e B_m (fixed random feedback matrix per map and
                cell, direct feedback alignment; times gelu' for fc1). No backprop through the net.
    np3         T1 with a SCALAR third factor (the plan's 3-factor rule): noise xi on the outputs of
                head and fc2, per example m = -(L_noisy - L_clean) / sigma^2, eligibility E = x^T xi,
                dF = eta m E / |x|^2. Only a reward-like number per example reaches the weights.
    delta_gated control: delta_head, but the fast change only acts on inputs similar to the trained ones,
                out += g(x) x F with g(x) = max_i exp(-BETA (1 - cos(x, k_i))), k_i = head inputs of the
                training examples (an episodic key store). Tests whether forgetting comes from WHERE the
                change acts (it acts on every input) rather than from how it is learned: the "when" a teacher
                (or a context gate) would have to supply.
    adam        reference: full Adam fine-tuning lr 1e-3 (= phase A "adam", run again with the same seeds)
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
import torch.nn as nn
import torch.nn.functional as F

from .adapt import SPEC, STEPS, base_score, case_fixcycle, score_on, start_net

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results" / "fastweights.jsonl"
SWEEP = {"lora": [1e-3, 1e-2, 3e-2, 1e-1], "delta_head": [0.1, 0.3, 1.0, 3.0], "dfa": [0.03, 0.1, 0.3, 1.0],
         "np3": [0.1, 0.3, 1.0, 3.0], "delta_gated": [1.0, 3.0], "adam": [1e-3]}
DEFAULT = {"lora": 3e-2, "delta_head": 3.0, "dfa": 1.0, "np3": 0.1, "delta_gated": 3.0, "adam": 1e-3}
RANK, SIGMA, BETA = 4, 0.1, 50.0


class Fast:
    """Fast weights attached by forward hooks to the head (nn.Linear) and the shared fc1 / fc2 (CellLinear)."""

    def __init__(self, model, rule, eta, seed):
        from .models.grid import CellLinear
        self.model, self.rule, self.eta = model, rule, eta
        for p in model.parameters():
            p.requires_grad_(False)
        self.mods = {"head": model.head}
        if rule not in ("delta_head", "delta_gated"):
            for n in ("fc1", "fc2"):
                m = getattr(model, n, None)
                if isinstance(m, CellLinear) and m.shared:
                    self.mods[n] = m
        g = torch.Generator().manual_seed(seed)
        self.F, self.uv, self.B = {}, {}, {}
        for n, m in self.mods.items():
            n_in, n_out = (m.in_features, m.out_features) if isinstance(m, nn.Linear) else m.w.shape
            if rule == "lora":
                u = (torch.randn(n_in, RANK, generator=g) / math.sqrt(n_in)).requires_grad_()
                self.uv[n] = (u, torch.zeros(RANK, n_out, requires_grad=True))
            else:
                self.F[n] = torch.zeros(n_in, n_out)
            m.register_forward_hook(self._hook(n))
        self.opt = torch.optim.Adam([p for uv in self.uv.values() for p in uv], lr=eta) if rule == "lora" else None
        self.gen = g
        self.gate = []
        self.rec, self.noise, self.keys = None, None, None

    def _hook(self, n):
        def hook(mod, inp, out):
            x = inp[0]
            if self.rule == "lora":
                u, v = self.uv[n]
                out = out + (x @ u) @ v
            elif self.rule == "delta_gated":
                xn = F.normalize(x, dim=-1)
                if self.keys is None:                       # first call = the training batch
                    self.keys = xn.detach().clone()
                g = torch.exp(-BETA * (1 - xn @ self.keys.T)).max(-1).values
                self.gate.append(float(g.mean()))
                out = out + g[:, None] * (x @ self.F[n])
            else:
                out = out + x @ self.F[n]
            if self.noise is not None and n in ("head", "fc2"):
                xi = torch.randn(out.shape, generator=self.gen) * SIGMA
                self.noise.append((n, x, xi))
                out = out + xi
            if self.rec is not None:
                self.rec.append((n, x, out))
            return out
        return hook

    # ------------------------------------------------------------------------------------------- update
    def _err(self, b):
        from .train import run_sequence
        logits, _ = run_sequence(self.model, b["obs"])
        lg = logits[0][:, SPEC.out_slice]
        e = torch.zeros_like(logits[0])
        e[:, SPEC.out_slice] = (torch.sigmoid(lg) - b["target"][0]) * b["mask"][0][:, None]
        return logits, e

    def _apply(self, n, x, d):
        """dF = -eta * sum over examples / cells of x^T d / mean |x|^2 (NLMS: eta = 1 moves an example's own
        output by about its error)."""
        x2, d2 = x.reshape(-1, x.shape[-1]), d.reshape(-1, d.shape[-1])
        self.F[n] -= self.eta * (x2.T @ d2) / x2.pow(2).sum(1).mean()

    def step(self, b):
        if self.rule == "lora":
            from .train import run_sequence, supervised_loss
            logits, _ = run_sequence(self.model, b["obs"])
            loss = supervised_loss(SPEC, logits, b["target"], b["mask"])
            self.opt.zero_grad()
            loss.backward()
            self.opt.step()
            return
        with torch.no_grad():
            if self.rule == "np3":
                self._np3(b)
                return
            self.rec = []
            _, e = self._err(b)
            rec, self.rec = self.rec, None
            for n, x, out in rec:
                if n == "head":
                    self._apply(n, x, e)
                    continue
                key = (n, x.shape[1], out.shape[-1])
                if key not in self.B:                       # fixed random feedback, one per cell
                    self.B[key] = torch.randn(e.shape[-1], x.shape[1] * out.shape[-1], generator=self.gen) \
                        / math.sqrt(e.shape[-1])
                d = (e @ self.B[key]).view(x.shape[0], x.shape[1], -1)
                if n == "fc1":                              # gelu'(z), z = pre-activation
                    s = torch.sigmoid(1.702 * out)
                    d = d * s * (1 + 1.702 * out * (1 - s))
                self._apply(n, x, d / sum(r[0] == n for r in rec))   # average over the rows calling it

    def _np3(self, b):
        from .train import run_sequence
        tgt, mask = b["target"][0], b["mask"][0]

        def per_example_loss():
            lg = run_sequence(self.model, b["obs"])[0][0][:, SPEC.out_slice]
            return F.binary_cross_entropy_with_logits(lg, tgt, reduction="none").mean(-1) * mask
        clean = per_example_loss()
        self.noise = []
        noisy = per_example_loss()
        rec, self.noise = self.noise, None
        m = -(noisy - clean) / SIGMA ** 2                   # scalar third factor per example
        for n, x, xi in rec:
            mb = m.view(-1, *([1] * (xi.dim() - 1)))
            self._apply(n, x, -mb * xi / max(1, sum(r[0] == n for r in rec)))


def curve(model_name, seed, variant, rule, eta):
    model = start_net(model_name, "cycle", seed)
    torch.manual_seed(seed + variant)
    from .tasks import make_task
    task = make_task("cycle")
    b, _ = case_fixcycle(variant + 10 * seed, 6)
    if rule == "adam":
        from .adapt import adapt_curve
        return adapt_curve(model, b, b, task, eta, False, seed + variant)
    fw = Fast(model, rule, eta, seed * 100 + variant)
    cur, ret = [], []
    for s in range(STEPS[-1] + 1):
        if s in STEPS:
            cur.append([s, score_on(model, b)])
            ret.append([s, base_score(model, task)])
        if s < STEPS[-1]:
            fw.step(b)
    return cur, ret


def _job(a):
    model_name, seed, rule, eta, variants = a
    try:
        t0 = time.time()
        runs = []
        for v in variants:
            c, r = curve(model_name, seed, v, rule, eta)
            runs.append({"variant": v, "curve": c, "retention": r})
        return {"model": model_name, "case": "fixcycle", "seed": seed, "rule": rule, "eta": eta, "steps": STEPS,
                "runs": runs, "time": round(time.time() - t0, 1)}
    except Exception:  # noqa: BLE001
        return {"model": model_name, "seed": seed, "rule": rule, "eta": eta, "error": traceback.format_exc()}


def _init_worker():
    torch.set_num_threads(1)


def execute(jobs, workers, out):
    out = Path(out)
    done = set()
    if out.exists():
        for ln in out.read_text().splitlines():
            r = json.loads(ln)
            if "error" not in r:
                done.add((r["model"], r["seed"], r["rule"], r["eta"], len(r["runs"])))
    jobs = [j for j in jobs if (j[0], j[1], j[2], j[3], len(j[4])) not in done]
    print(f"{len(jobs)} jobs, {workers} workers", flush=True)
    t0 = time.time()
    with mp.get_context("spawn").Pool(workers, initializer=_init_worker) as pool, out.open("a") as f:
        for i, r in enumerate(pool.imap_unordered(_job, jobs), 1):
            f.write(json.dumps(r) + "\n")
            f.flush()
            if "error" in r:
                msg = "ERROR " + r["error"].strip().splitlines()[-1]
            else:
                c = np.mean([dict(x["curve"])[5] for x in r["runs"]])
                e = np.mean([x["curve"][-1][1] for x in r["runs"]])
                d = np.mean([x["retention"][0][1] - x["retention"][-1][1] for x in r["runs"]])
                msg = f"s5 {c:.2f} end {e:.2f} forget {d:.2f} t={r['time']}s"
            print(f"[{i}/{len(jobs)} {(time.time() - t0) / 60:5.1f}min] {r['model']:11s} s{r['seed']} "
                  f"{r['rule']:10s} eta={r['eta']:<6g} {msg}", flush=True)


def summary(path):
    import pandas as pd
    rows = []
    for ln in Path(path).read_text().splitlines():
        r = json.loads(ln)
        if "error" in r:
            continue
        for x in r["runs"]:
            c, ret = dict(x["curve"]), dict(x["retention"])
            rows.append({"model": r["model"], "rule": r["rule"], "eta": r["eta"], "n_var": len(r["runs"]),
                         "seed": r["seed"], "s1": c[1], "s5": c[5], "s20": c[20], "s200": c[200],
                         "forget5": ret[0] - ret[5], "forget20": ret[0] - ret[20], "forget200": ret[0] - ret[200]})
    d = pd.DataFrame(rows)
    g = d.groupby(["model", "rule", "eta"]).agg(
        n=("seed", "size"), **{k: (k, "mean") for k in ["s1", "s5", "s20", "s200", "forget5", "forget20",
                                                         "forget200"]}).round(2)
    with pd.option_context("display.max_rows", 500, "display.width", 200):
        print(g.to_string())


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("cmd", choices=["sweep", "run", "summary"])
    ap.add_argument("--models", nargs="+", default=["layer_s"])
    ap.add_argument("--rules", nargs="+", default=list(DEFAULT))
    ap.add_argument("--seeds", nargs="+", type=int, default=[0, 1, 2])
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--workers", type=int, default=5)
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--file", default=str(OUT))
    a = ap.parse_args()
    if a.cmd == "summary":
        summary(a.file)
    elif a.cmd == "sweep":
        execute([(m, a.seed, r, eta, [0, 1]) for m in a.models for r in a.rules for eta in SWEEP[r]],
                a.workers, a.out)
    else:
        execute([(m, s, r, DEFAULT[r], [0, 1, 2, 3]) for s in a.seeds for m in a.models for r in a.rules],
                a.workers, a.out)


if __name__ == "__main__":
    main()
