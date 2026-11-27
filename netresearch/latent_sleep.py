"""Phase F, stage 1 on the robot images: wake / sleep with dreams in the LATENT space (PLAN_TRAINER Phase F).

    python -m netresearch.latent_sleep run [--cases robot_eye_flipx ...] [--model layer_s] [--seeds 5 6] [--draws 2]

The net never predicts or dreams images. Everything after the frozen encoder happens on the head input h (the
latent state the head reads), and both modules sit at the head:
    wake   fast weights F at the head, rls_rf on the day's k = 64 labelled images (one update; under the surprise
           switch: only while >= 10 % of the day's examples are wrong). F is cleared every night.
    sleep  a second module S at the head (rls_rf, its own random features), trained ONLY on dream latents,
           labelled by the waking head (W + S + F on the latent; the label is the decoded step, re-coded as a
           target like a real one). No image is seen in sleep. S is kept from night to night.
Dream latents (DREAM_N per night):
    replay   the latents of the day's 64 labelled images
    noise    variations of them: h + EPS * sd * N(0, 1) (sd per unit over the day's latents)
    mix      recombinations: l h_i + (1 - l) h_j of two of the day's latents, l ~ U(0, 1)
    unlab    latents of DREAM_N unlabelled images the robot saw that day (other images of the training file)
    gauss    samples of a Gaussian fitted once to the latents of the base images (a generative model of the
             latent space, stored with the net)
    pred_near / pred_far  dreams of the latent predictor (latent_pred.py; learned from the robot's own eye
             movements, no labels): from one of the day's latents, 1 random gaze step with |dx|, |dy| <= 2
             (near), or 2 steps with |dx|, |dy| <= 5 (far); the dream is the predicted latent after the steps
Controls: `unlab_true` (sleep on the unlabelled latents with their TRUE labels: what the dream labels cost) and
`rls_direct` (rls_rf at the head trained directly on every day's labelled images, kept over the days).
"""
import argparse
import copy
import json
import multiprocessing as mp
from pathlib import Path

import numpy as np
import torch

from .adapt import CASES, exact, score_on, spec_of, start_net, step_target
from .fastweights import RLS_LAMBDA, RLS_M, Fast, default_eta
from .tasks.servo import decode_step

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results" / "latent_sleep.jsonl"
SOURCES = ["replay", "noise", "mix", "unlab", "gauss", "unlab_true"]
PRED = {"pred_near": (1, 2), "pred_far": (2, 5)}             # dream source -> (gaze steps, largest |dx|, |dy|)
DAYS, K, DREAM_N, BATCH, EPS, SURPRISE_MIN = 4, 64, 1024, 64, 0.5, 0.1
_nets = {}


def net(model, base, seed):
    if (model, base, seed) not in _nets:
        _nets[model, base, seed] = start_net(model, base, seed)
    return copy.deepcopy(_nets[model, base, seed])


def rls(module, model, z, target, spec):
    """One rls_rf step of `module` at the head, on latents z (instead of images); targets as in a real batch."""
    module.rec = []
    logits = model.head(z)                                  # the hooks add the fast parts (S, F) of the head
    (_, x, _), module.rec = module.rec[-1], None
    p = module.phi(x)
    r = torch.zeros_like(logits)
    r[:, spec.out_slice] = RLS_M * (2 * target - 1) - logits[:, spec.out_slice]
    Q = module.F["_Q"]
    Pp = p / module.eta + p @ Q
    K_ = torch.linalg.solve(torch.eye(len(p)) + Pp @ p.T, Pp).T
    module.F["head"] += K_ @ r
    Q -= K_ @ Pp
    if RLS_LAMBDA < 1:
        Q.add_(torch.eye(len(Q)) / module.eta).div_(RLS_LAMBDA).sub_(torch.eye(len(Q)) / module.eta)


@torch.no_grad()
def labels(model, z, spec):
    """The waking head's answer on latents z, re-coded as a target (decoded step -> step code)."""
    lg = model.head(z)[:, spec.out_slice].numpy()
    st = decode_step(lg, spec)
    return torch.from_numpy(step_target(st[:, 0], st[:, 1], spec.pop))


def unlabelled(seed, draw, day, n):
    """n images of the training file the robot saw on that day, without labels."""
    from .tasks.robot import DATA
    d = np.load(DATA / "gazemulti_train.npz")
    rng = np.random.default_rng(777 + 1000 * seed + 100 * draw + day)
    i = rng.permutation(len(d["obs"]))[:n]
    return torch.from_numpy(d["obs"][i].astype(np.float32) / 255.0)[None], d["cells"][i].astype(np.int64)


def dreams(src, h_day, rng, gauss, pred=None):
    if src in PRED:
        n_steps, big = PRED[src]
        i = torch.from_numpy(rng.integers(0, len(h_day), DREAM_N))
        z = h_day[i]
        with torch.no_grad():
            for _ in range(n_steps):
                z = pred(z, torch.from_numpy(rng.integers(-big, big + 1, (DREAM_N, 2)).astype(np.float32)))
        return z
    if src == "replay":
        return h_day
    if src == "noise":
        sd = h_day.std(0, keepdim=True)
        i = torch.from_numpy(rng.integers(0, len(h_day), DREAM_N))
        return h_day[i] + EPS * sd * torch.from_numpy(rng.standard_normal((DREAM_N, h_day.shape[1])).astype(np.float32))
    if src == "mix":
        i, j = (torch.from_numpy(rng.integers(0, len(h_day), DREAM_N)) for _ in range(2))
        lam = torch.from_numpy(rng.random((DREAM_N, 1)).astype(np.float32))
        return lam * h_day[i] + (1 - lam) * h_day[j]
    mean, L = gauss
    return mean + torch.from_numpy(rng.standard_normal((DREAM_N, len(mean))).astype(np.float32)) @ L.T


def episode(case, seed, draw, model_name="layer_s", days=DAYS, gate="surprise", sources=None):
    sources = sources or SOURCES + ["rls_direct"]
    base, maker = CASES[case][0], CASES[case][1]
    spec = spec_of(base)
    device = case.split("robot_eye_")[-1]
    tb = maker(draw + 10 * seed, K)[1]
    day_b = [maker(draw + 10 * seed + 1000 * c, K)[0] for c in range(days)]
    probe = Fast(net(model_name, base, seed), "rls_rf@task", default_eta("rls_rf@task"), 0, spec)
    hb = probe.head_inputs(unlabelled(seed, draw, 99, 2048)[0])             # base latents -> fitted Gaussian
    mean = hb.mean(0)
    cov = torch.cov(hb.T) + 1e-4 * torch.eye(hb.shape[1])
    gauss = (mean, torch.linalg.cholesky(cov))
    row = {"case": case, "seed": seed, "draw": draw, "model": model_name, "days": days, "gate": gate,
           "dream_n": DREAM_N, "eps": EPS}
    eta = default_eta("rls_rf@task")
    pred = None
    if any(s in PRED for s in sources):
        from .latent_pred import load
        pred = load(model_name, seed)
    for src in sources:
        m = net(model_name, base, seed)
        S = Fast(m, "rls_rf@task", eta, seed * 100 + draw + 50, spec)        # hooked first: the slow module
        F = Fast(m, "rls_rf@task", eta, seed * 100 + draw, spec)
        S.task_on, F.task_on = 1.0, 0.0
        rng = np.random.default_rng(1000 * seed + draw)
        cur = {"wake": [], "sleep": [], "n_wake": []}
        for c, b in enumerate(day_b):
            if src == "rls_direct":                                          # plain training, kept over days
                S._rls(b)
                cur["sleep"].append(score_on(m, tb, spec))
                continue
            F.F["head"].zero_()
            F.F["_Q"].zero_()
            F.task_on = 1.0
            with torch.no_grad():
                from .train import run_sequence
                m.eval()
                lg, _ = run_sequence(m, b["obs"])
                m.train()
                wrong = 1 - exact(spec, lg[0][:, spec.out_slice], b["target"][0]).mean().item()
            woke = gate != "surprise" or wrong >= SURPRISE_MIN
            if woke:
                F._rls(b)
            cur["n_wake"].append(int(woke))
            cur["wake"].append(score_on(m, tb, spec))                        # W + S + F
            h_day = probe.head_inputs(b["obs"])
            if src in ("unlab", "unlab_true"):
                obs_u, cells = unlabelled(seed, draw, c, DREAM_N)
                z = probe.head_inputs(obs_u)
            else:
                z = dreams(src, h_day, rng, gauss, pred)
            with torch.no_grad():
                if src == "unlab_true":
                    from .tasks.servo import DEVICES
                    dx, dy = DEVICES[device](cells[:, 0], cells[:, 1])
                    y = torch.from_numpy(step_target(dx, dy, spec.pop))
                else:
                    y = labels(m, z, spec)                                   # labelled by W + S + F
                F.task_on = 0.0                                              # asleep: F off, S learns
                for i in range(0, len(z), BATCH):
                    rls(S, m, z[i:i + BATCH], y[i:i + BATCH], spec)
            cur["sleep"].append(score_on(m, tb, spec))                       # W + S
        row[src] = cur
    return row


def _job(a):
    torch.set_num_threads(1)
    return episode(*a)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["run"])
    ap.add_argument("--cases", nargs="+", default=[f"robot_eye_{d}" for d in
                                                   ["flipx", "swap", "rot90", "strong", "weak", "offx"]])
    ap.add_argument("--model", default="layer_s")
    ap.add_argument("--seeds", nargs="+", type=int, default=[5, 6])
    ap.add_argument("--draws", type=int, default=2)
    ap.add_argument("--days", type=int, default=DAYS)
    ap.add_argument("--gate", default="surprise", choices=["none", "surprise"])
    ap.add_argument("--sources", nargs="+", default=None, help="default: all but the predictor sources")
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--out", default=str(OUT))
    a = ap.parse_args()
    jobs = [(c, s, d, a.model, a.days, a.gate, a.sources) for c in a.cases for s in a.seeds for d in range(a.draws)]
    with mp.get_context("spawn").Pool(a.workers) as pool, open(a.out, "a") as f:
        for row in pool.imap(_job, jobs):
            f.write(json.dumps(row) + "\n")
            f.flush()
            print(row["case"], row["seed"], row["draw"],
                  {s: row[s]["sleep"] for s in row if isinstance(row[s], dict)}, flush=True)


if __name__ == "__main__":
    main()
