"""A transferable label map without the affine assumption (PLAN_TRAINER Phase F): learned over MANY tasks.

    python -m netresearch.label_map train [--steps 4000] [--threads 4]     # -> checkpoint + report

The dream labels of latent_sleep.py need a map "place of the red cube -> command" that carries over to places the
robot has not met the task in. So far it was an affine least-squares fit (fails where a calibration saturates).
Here the map is a TABLE COMPLETION learned over many synthetic calibrations: the input is the 16 x 16 table of the
fovea's cells with the commands known from the day's memories filled in (and a mask), the output a command for
every cell. Trained on random calibrations of a broad family (per axis an integer-ish linear map of (dx, dy) with
offset, rounding mode and clipping, steps wrapped as in the step code), with the memories drawn ONLY from the right
half (dx >= 0) and the loss on ALL cells, so the learner has to extrapolate into the left half. The six test
devices of the robot cases (flipx, swap, rot90, strong, weak, offx) are excluded from training as tables: a sampled
calibration that equals one of them on the whole field is drawn again (the family stays: near relatives remain).
"""
import argparse
import json
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn

ROOT = Path(__file__).resolve().parents[1]
CKPT = ROOT / "results" / "checkpoints" / "label_map.pt"
OUT = ROOT / "results" / "label_map.jsonl"
TEST_DEVICES = ["flipx", "swap", "rot90", "strong", "weak", "offx"]
GRID = np.stack(np.meshgrid(np.arange(-8, 8), np.arange(-8, 8), indexing="xy"), -1).reshape(-1, 2)   # [256, (dx, dy)]
COEF = np.array([-2, -1.5, -1, -0.5, 0, 0.5, 1, 1.5, 2])


def wrap(v):
    return (np.asarray(v, np.int64) + 8) % 16 - 8


def device_table(name):
    from .tasks.servo import DEVICES
    dx, dy = DEVICES[name](GRID[:, 0], GRID[:, 1])
    return np.stack([wrap(dx), wrap(dy)], -1)


def random_table(rng):
    """A random calibration of the family -> commands [256, 2] for every cell."""
    out = []
    for _ in range(2):
        a = rng.choice(COEF, 2) * (rng.random(2) < [0.8, 0.4])     # mostly one input, sometimes both
        if not a.any():
            a[rng.integers(2)] = rng.choice([-1, 1])
        v = GRID @ a + rng.integers(-3, 4)
        v = {0: np.fix, 1: np.round, 2: np.floor}[int(rng.integers(3))](v)
        lo, hi = (-8, 7) if rng.random() < 0.6 else (int(rng.integers(-8, -2)), int(rng.integers(3, 8)))
        out.append(wrap(np.clip(v, lo, hi)))
    return np.stack(out, -1)


class Completer(nn.Module):
    """Table completion with weights shared over the cells: a set encoder turns the known cells (place, command)
    into a task code (mean over the memories), a decoder answers (place, task code) -> command (16 classes per
    axis) for every cell."""

    def __init__(self, hid=256, code=128):
        super().__init__()                                  # (one-hot places and commands learned slower: LOGBUCH)
        self.enc = nn.Sequential(nn.Linear(4, hid), nn.GELU(), nn.Linear(hid, hid), nn.GELU(), nn.Linear(hid, code))
        self.post = nn.Sequential(nn.Linear(code, code), nn.GELU())
        self.dec = nn.Sequential(nn.Linear(2 + code, hid), nn.GELU(), nn.Linear(hid, hid), nn.GELU(),
                                 nn.Linear(hid, 32))
        self.register_buffer("grid", torch.from_numpy(GRID.astype(np.float32)) / 8.0)

    def forward(self, known, mask):
        """known [B, 256, 2] (commands / 8 where known, else 0), mask [B, 256] -> logits [B, 256, 2, 16]."""
        B = known.shape[0]
        g = self.grid.expand(B, 256, 2)
        e = self.enc(torch.cat([g, known], -1)) * mask[..., None]
        code = self.post(e.sum(1) / mask.sum(1, keepdim=True).clamp(min=1))
        return self.dec(torch.cat([g, code[:, None].expand(B, 256, code.shape[-1])], -1)).view(B, 256, 2, 16)


def inputs(cells, cmds):
    """Memories (cells [n, 2], commands [n, 2], ints) -> known [256, 2], mask [256] (last memory of a cell wins)."""
    known, mask = np.zeros((256, 2), np.float32), np.zeros(256, np.float32)
    idx = (cells[:, 1] + 8) * 16 + (cells[:, 0] + 8)
    known[idx] = cmds / 8.0
    mask[idx] = 1.0
    return known, mask


def sample_memories(rng, n=64, right=True):
    cells = rng.integers(-8, 8, (n, 2))
    if right:
        cells[:, 0] = rng.integers(0, 8, n)
    return cells


def make_batch(rng, B, exclude):
    K, M, Y = [], [], []
    for _ in range(B):
        while True:
            t = random_table(rng)
            if not any((t == e).all() for e in exclude):
                break
        cells = sample_memories(rng, int(rng.integers(16, 97)))
        idx = (cells[:, 1] + 8) * 16 + (cells[:, 0] + 8)
        k, m = inputs(cells, t[idx])
        K.append(k)
        M.append(m)
        Y.append(t + 8)
    return torch.from_numpy(np.stack(K)), torch.from_numpy(np.stack(M)), torch.from_numpy(np.stack(Y))


_FAMILY = None


def family():
    """All calibrations of the family per axis: (a1, a2, b, rounding, lo, hi) -> table [n_hyp, 256] and a
    simplicity cost (offset, clipping and a second input cost; full range and one input are simplest)."""
    global _FAMILY
    if _FAMILY is None:
        rows, cost = [], []
        clips = [(-8, 7)] + [(lo, hi) for lo in range(-8, -2) for hi in range(3, 8) if (lo, hi) != (-8, 7)]
        for a1 in COEF:
            for a2 in COEF:
                if a1 == 0 and a2 == 0:
                    continue
                for b in range(-3, 4):
                    v = GRID @ np.array([a1, a2]) + b
                    for r, fn in enumerate((np.trunc, np.round, np.floor)):
                        w = fn(v)
                        for lo, hi in clips:
                            rows.append(wrap(np.clip(w, lo, hi)))
                            cost.append(abs(b) + (a1 != 0) + (a2 != 0) + ((lo, hi) != (-8, 7)) * 2 + 0.1 * r)
        T = np.stack(rows)
        T, keep = np.unique(T, axis=0, return_index=True)   # identical tables: keep the cheapest description
        c = np.array(cost)
        best = {}
        for i, row in enumerate(rows):
            k = row.tobytes()
            best[k] = min(best.get(k, 1e9), c[i])
        _FAMILY = (T, np.array([best[t.tobytes()] for t in T]))
    return _FAMILY


def family_map(cells, cmds):
    """Hypothesis search: per axis the calibration of the family that fits the memories best (fewest misses,
    then the simplest); -> g(cells) -> commands."""
    T, cost = family()
    cells, cmds = np.asarray(cells), np.asarray(cmds)
    idx = (np.clip(cells[:, 1], -8, 7) + 8) * 16 + (np.clip(cells[:, 0], -8, 7) + 8)
    table = np.zeros((256, 2), np.int64)
    for ax in range(2):
        miss = (T[:, idx] != cmds[None, :, ax]).sum(1)
        table[:, ax] = T[np.lexsort((cost, miss))[0]]

    def g(q):
        q = np.clip(np.asarray(q), -8, 7)
        return table[(q[:, 1] + 8) * 16 + (q[:, 0] + 8)]
    return g


def affine_fit(cells, cmds):
    from .latent_sleep import cell_label_map
    return cell_label_map(cells, cmds, "lin")


def evaluate(model, seeds=range(20)):
    """Per test device: share of held-out (dx < 0) and seen (dx >= 0) cells right, for the completer and the affine
    map, from 64 memories in the right half (mean over `seeds` memory draws)."""
    res = {}
    for name in TEST_DEVICES:
        t = device_table(name)
        acc = {"meta_held": [], "meta_seen": [], "lin_held": [], "lin_seen": [], "fam_held": [], "fam_seen": []}
        for s in seeds:
            rng = np.random.default_rng(10_000 + s)
            cells = sample_memories(rng)
            idx = (cells[:, 1] + 8) * 16 + (cells[:, 0] + 8)
            k, m = inputs(cells, t[idx])
            with torch.no_grad():
                pred = model(torch.from_numpy(k)[None], torch.from_numpy(m)[None])[0].argmax(-1).numpy() - 8
            lin = affine_fit(cells, t[idx])(GRID)
            fam = family_map(cells, t[idx])(GRID)
            held, seen = GRID[:, 0] < 0, GRID[:, 0] >= 0
            for nm, p in (("meta", pred), ("lin", lin), ("fam", fam)):
                ok = (p == t).all(-1)
                acc[nm + "_held"].append(ok[held].mean())
                acc[nm + "_seen"].append(ok[seen].mean())
        res[name] = {k: round(float(np.mean(v)), 4) for k, v in acc.items()}
    return res


def train(steps=4000, batch=256, seed=0, out=OUT, threads=4):
    """Every step a fresh batch of random calibrations (no task is seen twice)."""
    import time
    torch.set_num_threads(threads)
    torch.manual_seed(seed)
    rng = np.random.default_rng(seed)
    exclude = [device_table(n) for n in TEST_DEVICES]
    model = Completer()
    opt = torch.optim.Adam(model.parameters(), lr=1e-3)
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, steps)
    t0 = time.time()
    for st in range(steps):
        K, M, Y = make_batch(rng, batch, exclude)
        loss = nn.functional.cross_entropy(model(K, M).reshape(-1, 16), Y.reshape(-1))
        opt.zero_grad()
        loss.backward()
        opt.step()
        sched.step()
        if st % 250 == 0:
            print(f"step {st} loss {loss.item():.3f} t={time.time() - t0:.0f}s", flush=True)
    model.eval()
    Kv, Mv, Yv = make_batch(np.random.default_rng(seed + 1), 2000, exclude)
    with torch.no_grad():
        ok = (model(Kv, Mv).argmax(-1) == Yv).all(-1).float()
    held = torch.from_numpy(GRID[:, 0] < 0)
    rep = {"what": "label_map", "steps": steps, "batch": batch, "seed": seed,
           "val_family_held": round(float(ok[:, held].mean()), 4), "val_family_seen": round(float(ok[:, ~held].mean()), 4),
           "devices": evaluate(model)}
    CKPT.parent.mkdir(parents=True, exist_ok=True)
    torch.save({"state": model.state_dict(), "report": rep}, CKPT)
    with open(out, "a") as f:
        f.write(json.dumps(rep) + "\n")
    print(json.dumps(rep))
    return model


def load():
    m = Completer()
    m.load_state_dict(torch.load(CKPT, weights_only=False)["state"])
    return m.eval()


def completer_map(model, cells, cmds):
    """The label map of latent_sleep.py from the day's memories, with the learned completer."""
    k, m = inputs(np.asarray(cells), np.asarray(cmds))
    with torch.no_grad():
        table = model(torch.from_numpy(k)[None], torch.from_numpy(m)[None])[0].argmax(-1).numpy() - 8

    def g(q):
        q = np.clip(np.asarray(q), -8, 7)
        return table[(q[:, 1] + 8) * 16 + (q[:, 0] + 8)]
    return g


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["train"])
    ap.add_argument("--steps", type=int, default=4000)
    ap.add_argument("--threads", type=int, default=4)
    ap.add_argument("--out", default=str(OUT))
    a = ap.parse_args()
    train(a.steps, out=a.out, threads=a.threads)


if __name__ == "__main__":
    main()
