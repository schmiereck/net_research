"""Phase B (PLAN_TRAINER.md): fast weights on a frozen trained net, updated by FIXED rules (no learned teacher).

    python -m netresearch.fastweights sweep  [--models layer_s] [--seed 0]        # step sizes per rule
    python -m netresearch.fastweights run    --models layer_s hier_s ... [--seeds 0 1 2] [--workers 5]
    python -m netresearch.fastweights gates  --models layer_s hier_s [--cases all] [--seeds 0 1 2]   # context gates
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
                column, the same for every row of the shared module; direct feedback alignment; times
                gelu' for fc1). No backprop through the net.
    np3         T1 with a SCALAR third factor (the plan's 3-factor rule): noise xi on the outputs of
                head and fc2, per example m = -(L_noisy - L_clean) / sigma^2, eligibility E = x^T xi,
                dF = eta m E / |x|^2. Only a reward-like number per example reaches the weights.
                L is the mean over the 8 output bits, so at equal eta the expected head update is 8x
                smaller than delta_head's (Codex review); the sweep's eta = 3 is about delta eta = 0.4.
    delta_gated control: delta_head, but the fast change only acts on inputs similar to the trained ones,
                out += g(x) x F with g(x) = max_i exp(-BETA (1 - cos(x, k_i))), k_i = head inputs of the
                training examples (an episodic key store). Tests whether forgetting comes from WHERE the
                change acts (it acts on every input) rather than from how it is learned: the "when" a teacher
                (or a context gate) would have to supply.
    Learned context gates (same delta rule on the head, out += g(x) x F; none stores single examples, the
    base task is seen only through summary statistics fitted once, as if stored with the trained net):
    delta_novel g = how far x lies outside the base distribution: Mahalanobis distance to the base head
                inputs (mean, covariance), g = sigmoid((d - d99) / (0.05 d99)), d99 = 99th percentile on base.
    delta_lda   g = linear discriminant between the base statistics and the k new training inputs
                (shared base covariance), g = 0.02 at the base mean, 0.98 at the mean of the new inputs.
    The rule cases (adapt.py: double, trib, countbig) score on UNSEEN test sequences, so a gate must
    generalise. double / trib have the same input form as their base numseq (only the rule is new), so an
    input gate can hardly separate them; countbig has larger steps than count.
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

from .adapt import CASES, SPEC, STEPS, base_score, score_on, start_net

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results" / "fastweights.jsonl"
SWEEP = {"lora": [1e-3, 1e-2, 3e-2, 1e-1], "delta_head": [0.1, 0.3, 1.0, 3.0], "dfa": [0.03, 0.1, 0.3, 1.0],
         "np3": [0.1, 0.3, 1.0, 3.0], "delta_gated": [1.0, 3.0], "adam": [1e-3]}
DEFAULT = {"lora": 3e-2, "delta_head": 3.0, "dfa": 1.0, "np3": 0.1, "delta_gated": 3.0, "delta_novel": 3.0,
           "delta_lda": 3.0, "adam": 1e-3}
RANK, SIGMA, BETA = 4, 0.1, 50.0
REF_B = 6                     # eta refers to a batch of 6 examples (fixcycle); bigger batches are averaged
GATED = ("delta_gated", "delta_novel", "delta_lda")
GATE_RULES = ["adam", "delta_head", *GATED]
GATE_KS = [8, 64, 512]


class Fast:
    """Fast weights attached by forward hooks to the head (nn.Linear) and the shared fc1 / fc2 (CellLinear)."""

    def __init__(self, model, rule, eta, seed):
        from .models.grid import CellLinear
        self.model, self.rule, self.eta = model, rule, eta
        for p in model.parameters():
            p.requires_grad_(False)
        self.mods = {"head": model.head}
        if rule not in ("delta_head", *GATED):
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
        self.rec, self.noise, self.keys, self.cap = None, None, None, None

    def _hook(self, n):
        def hook(mod, inp, out):
            x = inp[0]
            if self.rule == "lora":
                u, v = self.uv[n]
                out = out + (x @ u) @ v
            elif self.rule in GATED:
                if self.cap is not None:
                    self.cap.append(x.detach())
                if self.keys is not None:                   # gate fitted (fit_gate)
                    out = out + self.g(x)[:, None] * (x @ self.F[n])
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

    # --------------------------------------------------------------------------------------------- gates
    @torch.no_grad()
    def head_inputs(self, obs):
        from .train import run_sequence
        self.cap = []
        for i in range(0, obs.shape[1], 512):
            run_sequence(self.model, obs[:, i:i + 512])
        x, self.cap = torch.cat(self.cap), None
        return x

    @torch.no_grad()
    def fit_gate(self, train_b, base_task, seed, n=2048):
        """Gate statistics: base head inputs (n fresh base examples, summary only) and the k training inputs."""
        from .train import to_t
        base = self.head_inputs(to_t(base_task.sample(n, np.random.default_rng(seed)))["obs"])
        new = self.head_inputs(train_b["obs"])
        self.keys = F.normalize(new, dim=-1)
        mu0 = base.mean(0)
        c = torch.cov(base.T)
        c += (0.1 * c.diagonal().mean()) * torch.eye(c.shape[0])        # shrinkage
        self.P, self.mu0 = torch.linalg.inv(c), mu0
        if self.rule == "delta_novel":
            self.d99 = torch.quantile(self._maha(base), 0.99)
        elif self.rule == "delta_lda":
            self.w = self.P @ (new.mean(0) - mu0)
            s0, s1 = float((base @ self.w).mean()), float((new @ self.w).mean())
            self.c, self.tau = (s0 + s1) / 2, max(abs(s1 - s0) / 8, 1e-6) * (1 if s1 >= s0 else -1)
        return base

    def _maha(self, x):
        d = x - self.mu0
        return ((d @ self.P) * d).sum(-1).sqrt()

    def g(self, x):
        if self.rule == "delta_gated":
            return torch.exp(-BETA * (1 - F.normalize(x, dim=-1) @ self.keys.T)).max(-1).values
        if self.rule == "delta_novel":
            return torch.sigmoid((self._maha(x) - self.d99) / (0.05 * self.d99))
        return torch.sigmoid((x @ self.w - self.c) / self.tau)

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
        self.F[n] -= self.eta * (x2.T @ d2) / x2.pow(2).sum(1).mean() / max(1.0, x.shape[0] / REF_B)

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


def curve(model_name, seed, variant, rule, eta, case="fixcycle", k=6):
    """-> (curve, retention, gate info). The rule cases use the variant numbering of adapt.py."""
    base_name, maker = CASES[case][0], CASES[case][1]
    model = start_net(model_name, base_name, seed)
    torch.manual_seed(seed + variant)
    from .tasks import make_task
    task = make_task(base_name)
    b, tb = maker(variant + 10 * seed, k)
    if rule == "adam":
        from .adapt import adapt_curve
        return (*adapt_curve(model, b, tb, task, eta, False, seed + variant), None)
    fw = Fast(model, rule, eta, seed * 100 + variant)
    info = None
    if rule in GATED:
        base = fw.fit_gate(b, task, seed * 100 + variant + 1)
        with torch.no_grad():
            info = {"gate_base": round(float(fw.g(base).mean()), 4),
                    "gate_train": round(float(fw.g(fw.head_inputs(b["obs"])).mean()), 4),
                    "gate_test": round(float(fw.g(fw.head_inputs(tb["obs"])).mean()), 4)}
    cur, ret = [], []
    for s in range(STEPS[-1] + 1):
        if s in STEPS:
            cur.append([s, score_on(model, tb)])
            ret.append([s, base_score(model, task)])
        if s < STEPS[-1]:
            fw.step(b)
    return cur, ret, info


def _job(a):
    model_name, seed, rule, eta, variants = a[:5]
    case, k = a[5:] if len(a) > 5 else ("fixcycle", 6)
    try:
        t0 = time.time()
        runs = []
        for v in variants:
            c, r, info = curve(model_name, seed, v, rule, eta, case, k)
            runs.append({"variant": v, "curve": c, "retention": r, **({"gate": info} if info else {})})
        return {"model": model_name, "case": case, "k": k, "seed": seed, "rule": rule, "eta": eta,
                "steps": STEPS, "runs": runs, "time": round(time.time() - t0, 1)}
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
                done.add((r["model"], r["seed"], r["rule"], r["eta"], len(r["runs"]), r.get("case", "fixcycle"),
                          r.get("k", 6)))
    jobs = [j for j in jobs if (*j[:4], len(j[4]), *(j[5:] or ("fixcycle", 6))) not in done]
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
                  f"{r.get('case', ''):8s} k={r.get('k', '')!s:4s} "
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
            gt = x.get("gate", {})
            rows.append({"case": r.get("case", "fixcycle"), "k": r.get("k", 6),
                         "g_base": gt.get("gate_base"), "g_test": gt.get("gate_test"),
                         "model": r["model"], "rule": r["rule"], "eta": r["eta"], "n_var": len(r["runs"]),
                         "seed": r["seed"], "s1": c[1], "s5": c[5], "s20": c[20], "s200": c[200],
                         "forget5": ret[0] - ret[5], "forget20": ret[0] - ret[20], "forget200": ret[0] - ret[200]})
    d = pd.DataFrame(rows)
    g = d.groupby(["case", "k", "model", "rule", "eta"]).agg(
        n=("seed", "size"), **{k: (k, "mean") for k in ["s1", "s5", "s20", "s200", "forget20", "forget200",
                                                         "g_base", "g_test"]}).round(2)
    with pd.option_context("display.max_rows", 500, "display.width", 200):
        print(g.to_string())


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("cmd", choices=["sweep", "run", "gates", "summary"])
    ap.add_argument("--cases", nargs="+", default=["all"])
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
    elif a.cmd == "gates":
        cases = list(CASES) if a.cases == ["all"] else a.cases
        rules = GATE_RULES if a.rules == list(DEFAULT) else a.rules
        jobs = []
        for c in cases:
            ks, n_var = ([6], 4) if c == "fixcycle" else (GATE_KS, 2)
            jobs += [(m, s, r, DEFAULT[r], list(range(n_var)), c, k)
                     for s in a.seeds for m in a.models for r in rules for k in ks]
        execute(jobs, a.workers, a.out if a.out != str(OUT) else str(ROOT / "results" / "fastgate.jsonl"))
    else:
        execute([(m, s, r, DEFAULT[r], [0, 1, 2, 3]) for s in a.seeds for m in a.models for r in a.rules],
                a.workers, a.out)


if __name__ == "__main__":
    main()
