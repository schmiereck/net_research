"""Where does the time of a training run go? Times data generation, forward, backward and optimizer step
per update, and checks how the time per update scales with batch size and thread count (a hint whether
larger hardware / a GPU would help: if 8x batch costs ~1x time, the run is overhead-bound).

usage: python scripts/profile_run.py [--updates 60]
"""
import argparse
import time

import torch

from netresearch.models import build_model
from netresearch.tasks import make_task
from netresearch.train import make_learner, make_opt

CASES = [("mlp", "cycle"), ("cnn", "digits"), ("gru", "cycle_mem"), ("layer_s", "cycle_mem"),
         ("hier_s", "cycle"), ("bus_add_s_sp16", "cycle_mem"), ("cnn", "bricks"), ("layer_s", "bricks_mem")]


def profile(model_name, task_name, updates, batch, threads):
    torch.set_num_threads(threads)
    task = make_task(task_name)
    model = build_model(model_name)
    learner = make_learner(model, task, 1500, batch, 0)
    opt, _ = make_opt(model, 1500, 2e-3)
    t = dict(data=0.0, fwd=0.0, bwd=0.0, opt=0.0)
    for i in range(updates + 5):
        a = time.perf_counter()
        b = learner.next_batch(model)
        c = time.perf_counter()
        loss = learner.loss_on(model, b)
        d = time.perf_counter()
        opt.zero_grad()
        loss.backward()
        e = time.perf_counter()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        opt.step()
        f = time.perf_counter()
        if i >= 5:                                  # skip warm-up
            for k, v in zip(t, (c - a, d - c, e - d, f - e)):
                t[k] += v
    return {k: 1000 * v / updates for k, v in t.items()}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--updates", type=int, default=60)
    a = ap.parse_args()
    print(f"{'model':16s}{'task':12s}{'setting':14s}{'ms/upd':>8s}{'data':>7s}{'fwd':>7s}{'bwd':>7s}{'opt':>7s}")
    for m, tk in CASES:
        for batch, threads in ((64, 1), (512, 1), (64, 4)):
            r = profile(m, tk, a.updates, batch, threads)
            tot = sum(r.values())
            print(f"{m:16s}{tk:12s}{f'b{batch} t{threads}':14s}{tot:8.1f}" +
                  "".join(f"{100 * v / tot:6.0f}%" for v in r.values()), flush=True)


if __name__ == "__main__":
    main()
