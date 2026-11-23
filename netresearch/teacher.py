"""Phase D (PLAN_TRAINER.md): a learned local rule for the fast weights inside a frozen net, found by ES.

    python -m netresearch.teacher check                                   # theta = 0 reproduces dfa@task exactly
    python -m netresearch.teacher run --name d3 [--mode full|eta] [--cases lib_prev2 ...] [--seeds 0 1 2]
                                      [--gens 300] [--pop 48] [--episodes 8] [--workers 14] [--out ...]
    python -m netresearch.teacher eval --name d3 --cases lib_prev --seeds 5 6 [--ks 64] [--out ...]

The net (layer_s@25k, numseq start nets in data/base_nets) stays frozen. Fast weights F on fc1, fc2 and the
head as in fastweights.py (W_eff = W + F), oracle gate "@task" (the WHEN is given, only the HOW is learned).
The output error e = sigmoid(logits) - target reaches the inner maps through the fixed random feedback matrices
B of dfa; no gradient in the inner loop.

The teacher is one small MLP, the same for every output unit j of every map (fc1, fc2, head) and every cell.
Its input (telemetry) per unit: the fed-back error d_j (normalised by its rms over the map), tanh of the unit's
output, gelu'(pre-activation) for fc1 (else 1), the episode loss S, the change of S since the last update, the
update number t / T, and the map (one-hot). Its two outputs a_j, h_j give the update
    dF = -eta_map * x^T (base_j (1 + a_j) d_j + h_j tanh(y_j) rms(d)) / mean |x|^2
with base_j = gelu'(z_j) for fc1, 1 otherwise (dfa's own factor). The last layer starts at zero and the
eta_map = eta_dfa exp(p_map) at p = 0, so theta = 0 is exactly dfa@task (checked by "check").
Mode "eta" (stage D.2, control): ES tunes only the three p_map; the MLP stays zero. It separates "a learned
rule" from "a better step size".

ES (outer loop): antithetic pairs, centred ranks, Adam on the mean. Fitness of a candidate: mean over the
generation's episodes (case x start net x draw of the k examples; both halves of a pair see the same ones) of
the test score on unseen sequences after 1, 5, 10 and 20 updates.
-> results/teacher.jsonl (one row per generation: fitness of the mean on fixed validation episodes every
   VAL_EVERY generations), results/teacher/<name>.pt (theta of the mean, the best validated theta).
"""
import argparse
import json
import math
import multiprocessing as mp
import time
from pathlib import Path

import numpy as np
import torch

from .adapt import CASES, score_on, spec_of, start_net
from .fastweights import Fast, default_eta

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results" / "teacher.jsonl"
TDIR = ROOT / "results" / "teacher"
MODEL = "layer_s@25k"
MAPS = ["fc1", "fc2", "head"]
N_IN, HID = 9, 16
SHAPES = [("W1", (N_IN, HID)), ("b1", (HID,)), ("W2", (HID, HID)), ("b2", (HID,)), ("W3", (HID, 2)), ("b3", (2,)),
          ("p", (3,))]
SIZES = [int(np.prod(s)) for _, s in SHAPES]
N_THETA = sum(SIZES)
T_FIT, T_POINTS = 20, (1, 5, 10, 20)
K = 64
VAL_EVERY = 10
TRAIN_CASES = ["lib_prev2", "lib_prev3", "lib_xm0F", "lib_xmA5"]        # placeholder until D.0 decides


def unpack(theta):
    out, i = {}, 0
    for (n, s), k in zip(SHAPES, SIZES):
        out[n] = theta[i:i + k].view(s)
        i += k
    return out


def init_theta(seed):
    """Random first layers (small), zero output layer and p: theta is dfa@task exactly."""
    g = torch.Generator().manual_seed(seed)
    th = torch.zeros(N_THETA)
    P = unpack(th)
    P["W1"].copy_(torch.randn(N_IN, HID, generator=g) / math.sqrt(N_IN))
    P["W2"].copy_(torch.randn(HID, HID, generator=g) / math.sqrt(HID))
    return th


class Teach(Fast):
    """dfa@task with the update of every unit modulated by the teacher MLP (theta)."""

    def __init__(self, model, theta, seed, spec, T=T_FIT):
        super().__init__(model, "dfa@task", default_eta("dfa@task"), seed, spec)
        self.P, self.T, self.t, self.S_prev = unpack(theta), T, 0, None

    def mlp(self, f):
        P = self.P
        h = torch.tanh(f @ P["W1"] + P["b1"])
        h = torch.tanh(h @ P["W2"] + P["b2"])
        return h @ P["W3"] + P["b3"]

    @torch.no_grad()
    def step(self, b):
        from .train import supervised_loss
        self.rec = []
        logits, e = self._err(b)
        rec, self.rec = self.rec, None
        S = float(supervised_loss(self.spec, logits, b["target"], b["mask"]))
        dS = 0.0 if self.S_prev is None else S - self.S_prev
        self.S_prev = S
        glob = torch.tensor([S, 10 * dS, self.t / self.T])
        self.t += 1
        for n, x, out in rec:
            if n == "head":
                d, base = e, None
            else:
                key = (n, x.shape[1], out.shape[-1])
                if key not in self.B:                       # fixed random feedback, as dfa (same order, same gen)
                    self.B[key] = torch.randn(e.shape[-1], x.shape[1] * out.shape[-1], generator=self.gen) \
                        / math.sqrt(e.shape[-1])
                d = (e @ self.B[key]).view(x.shape[0], x.shape[1], -1)
                base = None
                if n == "fc1":                              # gelu'(z), z = pre-activation (dfa's own factor)
                    s = torch.sigmoid(1.702 * out)
                    base = s * (1 + 1.702 * out * (1 - s))
            rms = d.pow(2).mean().sqrt() + 1e-8
            onehot = torch.zeros(3)
            onehot[MAPS.index(n)] = 1.0
            ty = torch.tanh(out)
            f = torch.stack([d / rms, ty, base if base is not None else torch.ones_like(d)], -1)
            f = torch.cat([f, torch.cat([glob, onehot]).expand(*d.shape, 6)], -1)
            o = self.mlp(f)
            dd = d * (1 + o[..., 0])
            if base is not None:
                dd = base * d * (1 + o[..., 0])             # = dfa's d * gelu' at o = 0 (same product order)
            dd = dd + o[..., 1] * ty * rms
            eta_n = self.eta * math.exp(float(self.P["p"][MAPS.index(n)]))
            if n == "head":
                self._apply_eta(n, x, dd, eta_n, 1)
            else:
                self._apply_eta(n, x, dd, eta_n, sum(r[0] == n for r in rec))

    def _apply_eta(self, n, x, d, eta, n_calls):
        x2, d2 = x.reshape(-1, x.shape[-1]), d.reshape(-1, d.shape[-1])
        self.F[n] -= eta * (x2.T @ (d2 / n_calls)) / x2.pow(2).sum(1).mean() / max(1.0, x.shape[0] / 6)


# ------------------------------------------------------------------------------------------------ episodes
_nets = {}


def _net(seed):
    """A fresh copy of the frozen start net (loaded once per process)."""
    import copy
    if seed not in _nets:
        _nets[seed] = start_net(MODEL, "numseq", seed)
    return copy.deepcopy(_nets[seed])


def episode(theta, case, seed, draw, k=K, T=T_FIT, points=T_POINTS):
    """-> curve [[s, test score]] of the teacher rule on one episode (draw: which k examples)."""
    base, maker = CASES[case][0], CASES[case][1]
    spec = spec_of(base)
    b, tb = maker(draw + 10 * seed, k)
    model = _net(seed)
    fw = Teach(model, theta, seed * 100 + draw, spec, T=max(T, T_FIT))
    fw.task_on = 1.0
    cur = []
    for s in range(max(points) + 1):
        if s in points:
            cur.append([s, score_on(model, tb, spec)])
        if s < max(points):
            fw.step(b)
            if not all(torch.isfinite(f).all() for n, f in fw.F.items() if not n.startswith("_")):
                cur += [[p, 0.0] for p in points if p > s]
                break
    return cur


def _fit_job(a):
    theta, case, seed, draw = a
    c = episode(theta, case, seed, draw)
    return float(np.mean([v for _, v in c]))


def _init_worker():
    torch.set_num_threads(1)


def ranks(f):
    r = np.empty(len(f))
    r[np.argsort(f)] = np.arange(len(f))
    return r / (len(f) - 1) - 0.5


def run(name, mode, cases, seeds, gens, pop, n_ep, sigma, lr, workers, out, seed=0):
    TDIR.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(seed)
    theta = init_theta(seed)
    mask = torch.zeros(N_THETA)
    if mode == "eta":
        mask[-3:] = 1.0                                     # only p (log step size per map)
    else:
        mask[:] = 1.0
    m, v = torch.zeros(N_THETA), torch.zeros(N_THETA)
    val = [(c, s, 10_000 + i) for c in cases for s in seeds for i in range(2)]   # fixed validation episodes
    best = (-1.0, theta.clone())
    t0 = time.time()
    with mp.get_context("spawn").Pool(workers, initializer=_init_worker) as pool, open(out, "a") as f:
        for g in range(gens + 1):
            row = {"name": name, "mode": mode, "gen": g}
            if g % VAL_EVERY == 0 or g == gens:
                vf = pool.map(_fit_job, [(theta, c, s, d) for c, s, d in val])
                row["val"] = round(float(np.mean(vf)), 4)
                row["val_cases"] = {c: round(float(np.mean([x for (cc, _, _), x in zip(val, vf) if cc == c])), 4)
                                    for c in cases}
                if row["val"] > best[0]:
                    best = (row["val"], theta.clone())
                torch.save({"theta": theta, "best": best[1], "best_val": best[0], "mode": mode, "gen": g,
                            "cases": cases, "seeds": seeds}, TDIR / f"{name}.pt")
            if g == gens:
                f.write(json.dumps(row) + "\n")
                break
            eps = [(cases[rng.integers(len(cases))], seeds[rng.integers(len(seeds))], int(rng.integers(10_000)))
                   for _ in range(n_ep)]
            noise = torch.randn(pop // 2, N_THETA, generator=torch.Generator().manual_seed(seed * 100_000 + g)) * mask
            cands = [theta + sigma * z for z in noise] + [theta - sigma * z for z in noise]
            fit = pool.map(_fit_job, [(c, *e) for c in cands for e in eps])
            fit = np.array(fit).reshape(len(cands), n_ep).mean(1)
            r = ranks(fit)
            h = pop // 2
            grad = ((torch.tensor(r[:h] - r[h:], dtype=torch.float32)[:, None] * noise).sum(0)) / (pop * sigma)
            m = 0.9 * m + 0.1 * grad                        # Adam ascent on the mean
            v = 0.999 * v + 0.001 * grad ** 2
            theta = theta + lr * (m / (1 - 0.9 ** (g + 1))) / ((v / (1 - 0.999 ** (g + 1))).sqrt() + 1e-8) * mask
            row.update({"fit_mean": round(float(fit.mean()), 4), "fit_max": round(float(fit.max()), 4),
                        "p": [round(float(x), 3) for x in theta[-3:]], "norm": round(float(theta.norm()), 3),
                        "time": round(time.time() - t0, 1)})
            f.write(json.dumps(row) + "\n")
            f.flush()
            print(f"gen {g:4d} fit {row['fit_mean']:.3f} (max {row['fit_max']:.3f})"
                  + (f" val {row['val']:.3f}" if "val" in row else "") + f" p {row['p']} t={row['time']:.0f}s",
                  flush=True)


def evaluate(name, cases, seeds, ks, draws, steps, out, workers, which="best"):
    """Curves of a found rule (rows like fastweights inner, rule 'teach:<name>'), up to max(steps) updates."""
    ck = torch.load(TDIR / f"{name}.pt", weights_only=False)
    theta = ck[which]
    jobs = [(theta, c, s, d, k, steps) for c in cases for s in seeds for k in ks for d in range(draws)]
    with mp.get_context("spawn").Pool(workers, initializer=_init_worker) as pool, open(out, "a") as f:
        for (th, c, s, d, k, st), cur in zip(jobs, pool.map(_eval_job, jobs)):
            f.write(json.dumps({"model": MODEL, "case": c, "k": k, "seed": s, "rule": f"teach:{name}:{which}",
                                "eta": 0, "steps": list(st), "runs": [{"variant": d, "curve": cur}]}) + "\n")


def _eval_job(a):
    theta, c, s, d, k, st = a
    return episode(theta, c, s, d, k=k, T=T_FIT, points=tuple(st))


def check():
    """theta = 0 (and init_theta) must reproduce dfa@task of fastweights exactly."""
    from .fastweights import curve
    th = init_theta(0)
    for case in ["lib_prev", "lib_xm0F"]:
        model = start_net(MODEL, "numseq", 0)
        ref, _, _ = curve(MODEL, 0, 1, "dfa@task", default_eta("dfa@task"), case, K)
        refd = dict(ref)
        pts = tuple(s for s in refd if s <= 20)
        cur = episode(th, case, 0, 1 - 10 * 0, points=pts)  # draw so that maker(draw + 10 seed) = maker(1)
        ok = all(refd[s] == v for s, v in cur)
        print(case, "teacher(theta=0)", cur, "dfa@task", [[s, refd[s]] for s in pts], "IDENTICAL" if ok else "DIFF")
        del model


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("cmd", choices=["check", "run", "eval"])
    ap.add_argument("--name", default="d3")
    ap.add_argument("--mode", choices=["full", "eta"], default="full")
    ap.add_argument("--cases", nargs="+", default=TRAIN_CASES)
    ap.add_argument("--seeds", nargs="+", type=int, default=[0, 1, 2])
    ap.add_argument("--gens", type=int, default=300)
    ap.add_argument("--pop", type=int, default=48)
    ap.add_argument("--episodes", type=int, default=8)
    ap.add_argument("--sigma", type=float, default=0.05)
    ap.add_argument("--lr", type=float, default=0.02)
    ap.add_argument("--ks", nargs="+", type=int, default=[K])
    ap.add_argument("--draws", type=int, default=2)
    ap.add_argument("--steps", nargs="+", type=int, default=[0, 1, 2, 5, 10, 20, 50, 100, 200])
    ap.add_argument("--which", choices=["best", "theta"], default="best")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    if a.cmd == "check":
        check()
    elif a.cmd == "run":
        run(a.name, a.mode, a.cases, a.seeds, a.gens, a.pop, a.episodes, a.sigma, a.lr, a.workers,
            a.out or str(OUT))
    else:
        evaluate(a.name, a.cases, a.seeds, a.ks, a.draws, a.steps, a.out or str(ROOT / "results" / "teacher_eval.jsonl"),
                 a.workers, a.which)


if __name__ == "__main__":
    main()
