"""Where does the frozen net keep the word of frame 0 during match_shift? Ridge probe (train 3000 / test 1000 seqs)
on: top (head input), cells (state[0], all rows), last row, memory (M, G). Bit accuracy of the stored word, t=1..3."""
import sys, numpy as np, torch
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[2]))
from netresearch.models import build_model
from netresearch.models.route import _Tap
from netresearch.tasks import make_task
torch.set_num_threads(4)
D = sys.argv[1]
task = make_task("match_shift")
b = task.sample(4000, np.random.default_rng(7), split="test")
obs = torch.tensor(b["obs"])
o0 = b["obs"][0]
bits = np.zeros((4000, 8), np.float32)
for i in range(4000):
    line = (o0[i, 2] > 0.5) & (o0[i, 0] < 0.5); line[0, 0] = False       # blue only: the line under the word
    rr, cc = np.nonzero(line); r, c = rr.min() - 1, cc.min()
    bits[i] = o0[i, 0, r, c:c + 8]
print("bits mean", bits.mean().round(3), "per bit", bits.mean(0).round(2))
def probe(X, y, lam=1.0):
    X = (X - X[:3000].mean(0)) / (X[:3000].std(0) + 1e-6)
    X = np.concatenate([X, np.ones((len(X), 1))], 1)
    A = X[:3000]; W = np.linalg.solve(A.T @ A + lam * np.eye(A.shape[1]), A.T @ (y[:3000] * 2 - 1))
    return ((X[3000:] @ W > 0) == (y[3000:] > 0.5)).mean()
for seed in map(int, sys.argv[2:]):
    net = build_model("layer_s", 100_000, seed=seed); net.load_state_dict(torch.load(f"{D}/s{seed}.pt")); net.eval()
    tap = _Tap(net.head)
    st = net.init_state(4000); res = []
    with torch.no_grad():
        for t in range(4):
            _, st = net(obs[t], st)
            if t == 0: continue
            f = {"top": tap.value.numpy(), "cells": st[0].flatten(1).numpy(), "last": st[0][:, -1].flatten(1).numpy()}
            res.append({k: round(probe(v, bits), 3) for k, v in f.items()})
    print(seed, "dims", {k: v.shape[1] for k, v in f.items()}, flush=True)
    for t, r in enumerate(res, 1): print("   t", t, r, flush=True)
