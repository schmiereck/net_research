"""Run the benchmark matrix (models x tasks x seeds) in parallel; results are appended to a JSONL file.

    python -m netresearch.bench --models all --tasks all --seeds 0 1 --updates 1500 --workers 10
Already finished (model, task, seed, updates) combinations in the output file are skipped (resumable).
"""
import argparse
import json
import multiprocessing as mp
import os
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _init_worker():
    import torch
    torch.set_num_threads(1)


def _job(args):
    model, task, seed, updates = args
    from .train import run
    try:
        return run(model, task, seed=seed, updates=updates)
    except Exception:  # noqa: BLE001 - keep the matrix running, record the failure
        return {"model": model, "task": task, "seed": seed, "updates": updates, "error": traceback.format_exc()}


def main():
    from .models import MODEL_ORDER
    from .tasks import TASKS

    ap = argparse.ArgumentParser()
    ap.add_argument("--models", nargs="+", default=["all"])
    ap.add_argument("--tasks", nargs="+", default=["all"])
    ap.add_argument("--seeds", nargs="+", type=int, default=[0])
    ap.add_argument("--updates", type=int, default=1500)
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 2))
    ap.add_argument("--out", default=str(ROOT / "results" / "runs.jsonl"))
    a = ap.parse_args()

    models = MODEL_ORDER if a.models == ["all"] else a.models
    tasks = list(TASKS) if a.tasks == ["all"] else a.tasks
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    done = set()
    if out.exists():
        for line in out.read_text().splitlines():
            r = json.loads(line)
            if "error" not in r:
                done.add((r["model"], r["task"], r["seed"], r["updates"]))

    # task-level preparation in the main process (data caches, game baselines)
    from .train import game_baselines
    from .tasks import make_task
    for t in tasks:
        task = make_task(t)
        if task.spec.kind == "control":
            print(f"baseline {t}: {game_baselines(task)}", flush=True)

    # slow (stateful + long sequences, games) jobs first for better load balancing
    def cost(j):
        m, t, _, _ = j
        return (t in ("cycle_mem", "crossing", "maze", "racer", "bricks", "paddle")) * 2 + \
            (m in ("hier_s", "hier_i", "layer_s", "layer_i", "attnmem", "vit"))
    jobs = sorted([(m, t, s, a.updates) for s in a.seeds for t in tasks for m in models
                   if (m, t, s, a.updates) not in done], key=cost, reverse=True)
    print(f"{len(jobs)} jobs ({len(done)} already done), {a.workers} workers", flush=True)
    t0 = time.time()
    with mp.get_context("spawn").Pool(a.workers, initializer=_init_worker) as pool, out.open("a") as f:
        for k, r in enumerate(pool.imap_unordered(_job, jobs), 1):
            f.write(json.dumps(r) + "\n")
            f.flush()
            el = time.time() - t0
            msg = f"ERROR {r['error'].splitlines()[-1]}" if "error" in r else \
                f"score={r['score']:.3f} t={r['train_time']}s"
            print(f"[{k}/{len(jobs)} {el / 60:5.1f}min] {r['model']:11s} {r['task']:10s} s{r['seed']} {msg}",
                  flush=True)


if __name__ == "__main__":
    main()
