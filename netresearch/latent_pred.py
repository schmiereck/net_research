"""A latent predictor for dreams (PLAN_TRAINER Phase F): next latent state from the current one and a gaze step.

    python -m netresearch.latent_pred train [--model layer_s] [--seed 5] [--parts 4]   # -> checkpoint + report

The net never predicts images. The frozen encoder of a robot_gaze net (data/base_nets/robot_gaze) turns a fovea
view into its latent state h (the head input); the predictor P learns h_{t+1} = h_t + P(h_t, step) from the
robot's own eye movements, with no task and no labels:
    data   the scenes of the robot_gaze nets (three cubes, gazemulti) with their camera image
           (data/robot/gazemulti_{train,test}_img.npz: rdf_thalamus_sml export_netresearch.py --tasks gazemulti
           --n-train 4000 --n-test 1000 --images; the same scenes as the first 4000 / 1000 of gazemulti_*.npz).
           Along every scene a run of T random gaze steps (|dx|, |dy| <= MAX_STEP, the gaze kept inside the image)
           is re-sampled with the robot's fovea (tasks/fovea.py, bit-identical to the exported views) and encoded.
           (--data shape: the shape search scenes of data/robot/loopimg; the robot_gaze encoder does not see
           their bodies, so they are no use here.)
    P      MLP [h, dx / 8, dy / 8] -> 256 -> 256 -> delta h (residual), Adam on the one-step squared error
           (--loss one), or on the error of its own rollout over all T steps (--loss roll: the predictor is fed its
           own predictions, as in a dream, and the gradient runs through the whole run).
    conseq  (command) the CONSEQUENCE model: where the red cube will be after a gaze step, learned from what the
           base head reads before and after the robot's own eye movements (no labels, no geometry).
    --tag  name of the variant (checkpoint <model>_s<seed><tag>.pt; "" = the first predictor).
Report on held-out scenes: one-step and T-step rollout error relative to the variance of h, against "nothing
moves" (h_{t+k} = h_t); and whether the predicted latent keeps its MEANING: a linear probe trained on true latents
reads the step to each of the scene's three cubes (exact cell), and the base net's own head reads the step to the
red cube (its task); both measured on true, predicted and unmoved latents.
"""
import argparse
import copy
import glob
import json
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn

from .adapt import start_net
from .fastweights import Fast, default_eta
from .tasks import fovea as fv

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "robot"
CKPT = ROOT / "results" / "checkpoints" / "latent_pred"
OUT = ROOT / "results" / "latent_pred.jsonl"
T, MAX_STEP, RUNS, HID = 4, 5, 4, 256


class Predictor(nn.Module):
    def __init__(self, d, hid=HID):
        super().__init__()
        self.net = nn.Sequential(nn.Linear(d + 2, hid), nn.GELU(), nn.Linear(hid, hid), nn.GELU(), nn.Linear(hid, d))

    def forward(self, h, step):
        return h + self.net(torch.cat([h, step / 8.0], -1))


def encoder(model_name, seed):
    m = start_net(model_name, "robot_gaze", seed)
    return Fast(m, "rls_rf@task", default_eta("rls_rf@task"), 0, None)   # only for head_inputs (frozen latents)


def runs(files, rng, runs_per_scene=RUNS, with_view=False, n_scenes=None):
    """-> views uint8 [N, T + 1, 3, 16, 16], steps [N, T, 2], body steps [N, T + 1, 3, 2] (true step to each body
    from that gaze)."""
    V, S, Bd, IV = [], [], [], []
    for f in files:
        with np.load(f) as z:                               # read every array once (an npz decompresses on access)
            imgs, gazes, poss = z["img"][:n_scenes], z["gaze"][:n_scenes], z["pos"][:n_scenes]
        for i in range(len(imgs)):
            sat = fv.integral(imgs[i])
            for _ in range(runs_per_scene):
                g = np.asarray(gazes[i], float)
                views, steps, bodies = [fv.sample(sat, g)], [], [[fv.nearest_cell(g, p)[:2] for p in poss[i]]]
                inview = [fv.nearest_cell(g, poss[i][0])[2] <= 2 * fv.K]
                for _ in range(T):
                    while True:
                        s = rng.integers(-MAX_STEP, MAX_STEP + 1, 2)
                        g2 = fv.shift(g, s[0], s[1])
                        if 20 <= g2[0] <= 220 and 20 <= g2[1] <= 220:
                            break
                    g = g2
                    steps.append(s)
                    views.append(fv.sample(sat, g))
                    bodies.append([fv.nearest_cell(g, p)[:2] for p in poss[i]])
                    inview.append(fv.nearest_cell(g, poss[i][0])[2] <= 2 * fv.K)
                V.append(views)
                S.append(steps)
                Bd.append(bodies)
                IV.append(inview)
    if with_view:                                           # also: is the red cube in the field of view
        return np.array(V), np.array(S, np.float32), np.array(Bd, np.int64), np.array(IV)
    return np.array(V), np.array(S, np.float32), np.array(Bd, np.int64)


@torch.no_grad()
def encode(enc, views):
    n, t = views.shape[:2]
    x = torch.from_numpy(views.reshape(n * t, *views.shape[2:]).astype(np.float32) / 255.0)[None]
    return enc.head_inputs(x).view(n, t, -1)


def head_acc(enc, h, bodies):
    """The base net's own head (robot_gaze: step to the red cube) on latents h: share with the exact true step."""
    from .adapt import spec_of
    from .tasks.servo import decode_step
    spec = spec_of("robot_gaze")
    with torch.no_grad():
        st = decode_step(enc.model.head(h)[:, spec.out_slice].numpy(), spec)
    return float((st == bodies[:, 0]).all(-1).mean())


def probe_fit(h, bodies, lam=1.0):
    """Ridge probe h -> (dx, dy) of each of the 3 bodies (6 outputs)."""
    X = torch.cat([h, torch.ones(len(h), 1)], 1)
    Y = torch.from_numpy(bodies.reshape(len(h), 6).astype(np.float32))
    return torch.linalg.solve(X.T @ X + lam * torch.eye(X.shape[1]), X.T @ Y)


def probe_acc(W, h, bodies):
    X = torch.cat([h, torch.ones(len(h), 1)], 1)
    pred = torch.round(X @ W).numpy().reshape(len(h), 3, 2)
    return float((pred == bodies).all(-1).mean())


def train(model_name="layer_s", seed=5, parts=4, epochs=40, out=OUT, data="multi", loss_kind="one", tag="",
          runs_per_scene=RUNS, hid=HID, head_w=0.0, n_scenes=None):
    torch.manual_seed(seed)
    rng = np.random.default_rng(seed)
    if data == "multi":
        files, test = [DATA / "gazemulti_train_img.npz"], DATA / "gazemulti_test_img.npz"
    else:
        files = sorted(glob.glob(str(DATA / "loopimg" / "gazeshapec_train_p*_img.npz")),
                       key=lambda f: int(f.split("_p")[1].split("_")[0]))[:parts]
        test = DATA / "gazeshapec_test_img.npz"
    enc = encoder(model_name, seed)
    Vtr, Str, Btr = runs(files, rng, runs_per_scene, n_scenes=n_scenes or 4000)
    Vte, Ste, Bte = runs([test], np.random.default_rng(1000 + seed), 1)
    Htr, Hte = encode(enc, Vtr), encode(enc, Vte)
    d = Htr.shape[-1]
    var = float(Htr.reshape(-1, d).var(0).sum())
    P = Predictor(d, hid)
    from .adapt import spec_of
    sl = spec_of("robot_gaze").out_slice
    head = enc.model.head                                   # frozen base head: what it reads must survive the step
    with torch.no_grad():
        Ltr = head(Htr.reshape(-1, d))[:, sl].view(Htr.shape[0], Htr.shape[1], -1)
    opt = torch.optim.Adam(P.parameters(), lr=1e-3)
    h0, h1 = Htr[:, :-1].reshape(-1, d), Htr[:, 1:].reshape(-1, d)
    st = torch.from_numpy(Str.reshape(-1, 2))
    S_all = torch.from_numpy(Str)
    for ep in range(epochs):
        if loss_kind == "roll":                             # whole runs: rollout from the first latent
            perm = torch.randperm(len(Htr))
            for i in range(0, len(Htr), 64):
                j = perm[i:i + 64]
                h, loss = Htr[j, 0], 0.0
                for t in range(T):
                    h = P(h, S_all[j, t])
                    loss = loss + (h - Htr[j, t + 1]).pow(2).sum(-1).mean()
                    if head_w:                                      # head consistency: same reading as the true latent
                        loss = loss + head_w * (head(h)[:, sl] - Ltr[j, t + 1]).pow(2).sum(-1).mean()
                opt.zero_grad()
                (loss / T).backward()
                opt.step()
            continue
        perm = torch.randperm(len(h0))
        for i in range(0, len(h0), 256):
            j = perm[i:i + 256]
            loss = (P(h0[j], st[j]) - h1[j]).pow(2).sum(-1).mean()
            opt.zero_grad()
            loss.backward()
            opt.step()
    W = probe_fit(Htr.reshape(-1, d), Btr.reshape(-1, 3, 2))
    rep = {"model": model_name, "seed": seed, "data": data, "parts": parts if data != "multi" else None, "n_train_runs": len(Vtr), "n_test_runs": len(Vte),
           "T": T, "max_step": MAX_STEP, "epochs": epochs, "d": d}
    if loss_kind != "one" or tag or runs_per_scene != RUNS:
        rep.update({"loss": loss_kind, "tag": tag, "runs_per_scene": runs_per_scene})
    if hid != HID or head_w or (n_scenes or 4000) != 4000:
        rep.update({"hid": hid, "head_w": head_w, "n_scenes": n_scenes or 4000})
    with torch.no_grad():
        ste = torch.from_numpy(Ste)
        h = Hte[:, 0]
        err_p, err_0, acc_p, acc_0, acc_t, hd_p, hd_0, hd_t = [], [], [], [], [], [], [], []
        for k in range(1, T + 1):
            h = P(h, ste[:, k - 1])
            true = Hte[:, k]
            err_p.append(round(float((h - true).pow(2).sum(-1).mean()) / var, 4))
            err_0.append(round(float((Hte[:, 0] - true).pow(2).sum(-1).mean()) / var, 4))
            acc_p.append(round(probe_acc(W, h, Bte[:, k]), 4))
            acc_0.append(round(probe_acc(W, Hte[:, 0], Bte[:, k]), 4))
            acc_t.append(round(probe_acc(W, true, Bte[:, k]), 4))
            hd_t.append(round(head_acc(enc, true, Bte[:, k]), 4))
            hd_p.append(round(head_acc(enc, h, Bte[:, k]), 4))
            hd_0.append(round(head_acc(enc, Hte[:, 0], Bte[:, k]), 4))
    rep.update({"err_pred": err_p, "err_still": err_0, "probe_true": acc_t, "probe_pred": acc_p,
                "probe_still": acc_0, "head_true": hd_t, "head_pred": hd_p, "head_still": hd_0})
    CKPT.mkdir(parents=True, exist_ok=True)
    torch.save({"state": P.state_dict(), "d": d, "hid": hid, "report": rep}, CKPT / f"{model_name}_s{seed}{tag}.pt")
    with open(out, "a") as f:
        f.write(json.dumps(rep) + "\n")
    print(json.dumps(rep))
    return P


def load(model_name, seed, tag=""):
    ck = torch.load(CKPT / f"{model_name}_s{seed}{tag}.pt", weights_only=False)
    P = Predictor(ck["d"], ck.get("hid", HID))
    P.load_state_dict(ck["state"])
    return P.eval()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["train", "conseq"])
    ap.add_argument("--model", default="layer_s")
    ap.add_argument("--seeds", nargs="+", type=int, default=[5])
    ap.add_argument("--parts", type=int, default=4, help="--data shape: how many image parts")
    ap.add_argument("--data", choices=["multi", "shape"], default="multi")
    ap.add_argument("--loss", choices=["one", "roll"], default="one")
    ap.add_argument("--tag", default="")
    ap.add_argument("--central", type=int, default=CENTRAL, help="conseq: learn from read cells within +-central")
    ap.add_argument("--hid", type=int, default=HID)
    ap.add_argument("--scenes", type=int, default=4000, help="train: first n scenes of gazemulti_train_img")
    ap.add_argument("--head-w", type=float, default=0.0, help="weight of the head-consistency loss (roll)")
    ap.add_argument("--runs", type=int, default=RUNS, help="runs of T steps per scene")
    ap.add_argument("--epochs", type=int, default=40)
    ap.add_argument("--out", default=str(OUT))
    a = ap.parse_args()
    for s in a.seeds:
        if a.cmd == "conseq":
            train_conseq(a.model, s, a.epochs, a.out, a.runs, a.central, a.tag)
        else:
            train(a.model, s, a.parts, a.epochs, a.out, a.data, a.loss, a.tag, a.runs, a.hid, a.head_w, a.scenes)



# ------------------------------------------------------------------- consequence of a gaze step (learned)
class Consequence(nn.Module):
    """Where the red cube will be after a gaze step: (cell before, step) -> cell after (16 classes per axis).
    Learned from the robot's own eye movements; inputs and targets are what the base net's head READS before and
    after the step (no labels, no geometry)."""

    def __init__(self):
        super().__init__()                                  # inputs one-hot: cell and step per axis (the hex rows
        self.net = nn.Sequential(nn.Linear(64, 128), nn.GELU(), nn.Linear(128, 128), nn.GELU(), nn.Linear(128, 32))

    def forward(self, c, step):                             # shift every second row: parity matters, not size)
        oh = lambda v: nn.functional.one_hot((v.long() + 8).clamp(0, 15), 16).float().flatten(1)
        return self.net(torch.cat([oh(c), oh(step)], -1)).view(-1, 2, 16)

    def cell(self, c, step):
        """-> predicted cells [n, 2] (ints -8..7) for numpy cells and steps."""
        with torch.no_grad():
            lg = self(torch.from_numpy(np.asarray(c, np.float32)), torch.from_numpy(np.asarray(step, np.float32)))
        return lg.argmax(-1).numpy().astype(np.int64) - 8


def read_cells(enc, h):
    """The base head's reading of the red cube's cell from latents h -> [n, 2]."""
    from .adapt import spec_of
    from .tasks.servo import decode_step
    spec = spec_of("robot_gaze")
    with torch.no_grad():
        return decode_step(enc.model.head(h)[:, spec.out_slice].numpy(), spec)


CENTRAL = 5     # the consequence model learns from steps whose READ cells lie within +-CENTRAL (the head reads there
#                 at 0.98, in the periphery at 0.74); dreams keep the cube there too


def train_conseq(model_name="layer_s", seed=5, epochs=30, out=OUT, runs_per_scene=RUNS, central=CENTRAL, tag=""):
    torch.manual_seed(seed)
    enc = encoder(model_name, seed)
    Vtr, Str, Btr = runs([DATA / "gazemulti_train_img.npz"], np.random.default_rng(seed), runs_per_scene, n_scenes=4000)
    Vte, Ste, Bte, IVte = runs([DATA / "gazemulti_test_img.npz"], np.random.default_rng(1000 + seed), 1, True)
    Htr, Hte = encode(enc, Vtr), encode(enc, Vte)
    n, t1, d = Htr.shape
    ctr = read_cells(enc, Htr.reshape(-1, d)).reshape(n, t1, 2)
    a0, a1 = ctr[:, :-1].reshape(-1, 2), ctr[:, 1:].reshape(-1, 2)
    keep = (np.abs(a0).max(-1) <= central) & (np.abs(a1).max(-1) <= central)   # chosen by what the robot reads
    c0 = torch.from_numpy(a0[keep].astype(np.float32))
    c1 = torch.from_numpy(a1[keep] + 8)
    st = torch.from_numpy(Str.reshape(-1, 2)[keep])
    C = Consequence()
    opt = torch.optim.Adam(C.parameters(), lr=1e-3)
    for ep in range(epochs):
        perm = torch.randperm(len(c0))
        for i in range(0, len(c0), 256):
            j = perm[i:i + 256]
            loss = nn.functional.cross_entropy(C(c0[j], st[j]).reshape(-1, 16), c1[j].reshape(-1))
            opt.zero_grad()
            loss.backward()
            opt.step()
    from .latent_sleep import carried
    te_true0, te_true1 = Bte[:, :-1, 0].reshape(-1, 2), Bte[:, 1:, 0].reshape(-1, 2)
    ste = Ste.reshape(-1, 2)
    m, t1e, _ = Hte.shape
    cte = read_cells(enc, Hte.reshape(-1, d)).reshape(m, t1e, 2)
    geo, _ = carried(te_true0, ste[:, None])
    ok = (IVte[:, :-1] & IVte[:, 1:]).reshape(-1)           # judged where the cube is in view before and after
    cen = ok & (np.abs(te_true0).max(-1) <= CENTRAL) & (np.abs(te_true1).max(-1) <= CENTRAL)
    rep = {"what": "consequence", "model": model_name, "seed": seed, "epochs": epochs, "runs_per_scene": runs_per_scene,
           "central": CENTRAL, "train_central": central, "tag": tag, "share_central": round(float(cen.mean()), 4),
           "central_learned_from_true_cell": round(float((C.cell(te_true0, ste) == te_true1).all(-1)[cen].mean()), 4),
           "central_geometry_from_true_cell": round(float((geo == te_true1).all(-1)[cen].mean()), 4),
           "central_c_minus_step": round(float(((te_true0 - ste) == te_true1).all(-1)[cen].mean()), 4),
           "n_train_steps": int(len(c0)),
           "read_acc": round(float((cte == Bte[:, :, 0]).all(-1).mean()), 4),
           "learned_from_true_cell": round(float((C.cell(te_true0, ste) == te_true1).all(-1)[ok].mean()), 4),
           "learned_from_read_cell": round(float((C.cell(cte[:, :-1].reshape(-1, 2), ste) == te_true1).all(-1)[ok].mean()), 4),
           "geometry_from_true_cell": round(float((geo == te_true1).all(-1)[ok].mean()), 4),
           "geometry_from_read_cell": round(float((carried(cte[:, :-1].reshape(-1, 2), ste[:, None])[0]
                                                   == te_true1).all(-1)[ok].mean()), 4),
           "share_in_view": round(float(ok.mean()), 4)}
    CKPT.mkdir(parents=True, exist_ok=True)
    torch.save({"state": C.state_dict(), "report": rep}, CKPT / f"{model_name}_s{seed}_conseq{tag}.pt")
    with open(out, "a") as f:
        f.write(json.dumps(rep) + "\n")
    print(json.dumps(rep))
    return C


def load_conseq(model_name, seed, tag=""):
    C = Consequence()
    C.load_state_dict(torch.load(CKPT / f"{model_name}_s{seed}_conseq{tag}.pt", weights_only=False)["state"])
    return C.eval()


if __name__ == "__main__":
    main()
