"""What a net with memory keeps of the goal pictures along a run with several goals (robot_loop_*_f32).

    python scripts/loop_goals_probe.py --task robot_loop_three_f32 --ckpt robot_loop_three_f32_24k \
        --models layer_s+cell+refl+rez3 layer_s_sp4+cell+refl+rez3 --seeds 0 1 2 3 4 7

The stored nets run teacher-forced over test sequences (`gazeloop{G}_test`, picture view 0): G cue steps with the
pictures of the goals, then the views of the noisy-teacher run. After every step the memory state is read out, and
a linear read-out (the ridge regression of scripts/loop_state_probe.py, fitted on half of the scenes, measured on
the other half) tries to tell the SHAPE of each goal (5 shapes, chance about 0.2) from it. That separates three ways to lose a goal:
    not written     the shape of goal k cannot be read even right after its cue step
    overwritten     it can be read after its cue step, but no longer later
    not used        it can still be read when the net goes for it, but the net goes elsewhere
Also measured: how far apart the address encoder puts the goal pictures (spread of its output over the pictures,
and how well a probe reads the shape from it), so that a dead input (as with the tanh, 2026-11-16) is seen.
-> results/loop_goals_probe.jsonl, one row per net and seed: probe[t][k] = test accuracy for the shape of goal k
   from the state after step t (t = 0 .. T-1; steps 0 .. G-1 are the cue steps).
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np
import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from netresearch.tasks.registry import TASKS  # noqa: E402
from netresearch.train import load_checkpoint, run_sequence  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from loop_state_probe import ridge  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def flat(state):
    parts = state if isinstance(state, (tuple, list)) else [state]
    return torch.cat([p.reshape(p.shape[0], -1).float() for p in parts if p.numel()], 1)


def probe(x, y, train, test):
    """Shape read-out (ridge on one-hot targets, as in loop_state_probe.py): test accuracy."""
    x = np.asarray(x, np.float64)
    p = ridge(x[train], np.eye(5)[y[train]], x[test], lam=0.01)
    return float((p.argmax(1) == y[test]).mean())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", default="robot_loop_three_f32")
    ap.add_argument("--ckpt", default=None)
    ap.add_argument("--models", nargs="+", required=True)
    ap.add_argument("--seeds", nargs="+", type=int, default=[0, 1, 2])
    ap.add_argument("--n", type=int, default=3000, help="test sequences used")
    a = ap.parse_args()
    task = TASKS[a.task]()
    d = task._load("test")
    rng = np.random.default_rng(0)
    idx = np.sort(rng.choice(len(d["scene"]), size=min(a.n, len(d["scene"])), replace=False))
    scenes = d["scene"][idx]
    us = np.unique(scenes)
    train = np.isin(scenes, rng.permutation(us)[: len(us) // 2])
    test = ~train
    shape = d["shape"][idx].astype(np.int64)                           # [n, G]
    body = d["body"][idx]
    # goal k is read only in sequences where it is a body not named before (for A, B, C: all; for the third goal
    # of A, B, A it would be the shape of A again)
    new = [np.ones(len(idx), bool)] + [~(body[:, :k] == body[:, k:k + 1]).any(1) for k in range(1, task.G)]
    # what the earlier shapes alone tell about goal k (the shapes of a scene are not independent)
    base = [round(probe(np.eye(5)[shape[:, :k]].reshape(len(idx), -1) if k else np.zeros((len(idx), 1)),
                        shape[:, k], train & new[k], test & new[k]), 3) for k in range(task.G)]
    print(f"read-out of each goal's shape from the earlier shapes alone (floor): {base}", flush=True)
    b = task.make(d, idx, view=0)
    obs, ref = torch.tensor(b["obs"]), torch.tensor(b["ref"])
    G, T = task.G, task.T
    with open(ROOT / "results" / "loop_goals_probe.jsonl", "a") as out:
        for name in a.models:
            for seed in a.seeds:
                model = load_checkpoint(name, a.ckpt or a.task, seed)
                if model is None:
                    print(f"  {name} s{seed}: no checkpoint", flush=True)
                    continue
                model.eval()
                states, st = [], None
                with torch.no_grad():
                    enc = model.ref_enc(ref[:G].reshape(-1, *ref.shape[2:]).float()).reshape(G, len(idx), -1)
                    for t in range(T):
                        _, st = run_sequence(model, obs[t:t + 1], state=st, ref=ref[t:t + 1])
                        states.append(flat(st).numpy())
                acc = [[round(probe(states[t], shape[:, k], train & new[k], test & new[k]), 3) for k in range(G)]
                       for t in range(T)]
                e = enc.numpy()
                spread = [round(float(e[k].std(0).mean()), 4) for k in range(G)]
                enc_acc = [round(probe(e[k], shape[:, k], train & new[k], test & new[k]), 3) for k in range(G)]
                row = {"task": a.task, "ckpt": a.ckpt or a.task, "model": name, "seed": seed, "n": len(idx),
                       "state_dim": int(states[0].shape[1]), "floor": base, "probe": acc, "enc_spread": spread, "enc_probe": enc_acc}
                out.write(json.dumps(row) + "\n")
                out.flush()
                print(f"{name} s{seed}: dim {row['state_dim']}, encoder spread {spread} probe {enc_acc}", flush=True)
                for t in range(T):
                    print(f"    after step {t:2d}{' (cue)' if t < G else '      '}: " +
                          " ".join(f"{'ABC'[k]} {acc[t][k]:.2f}" for k in range(G)), flush=True)


if __name__ == "__main__":
    sys.exit(main())
