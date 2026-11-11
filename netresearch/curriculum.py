"""Curriculum runs: one net learns a list of phases one after the other; a phase is one task or several at once.

    python -m netresearch.curriculum run --plans "same_shift:12000" "read_shift:2000 same_shift:10000" \
        "read_shift+same_shift:12000" --models layer_s gru --seeds 5 6 --watch same_shift [--workers 4]

A plan is a list of phases "task[+task...]:updates". Several tasks in a phase are trained round-robin (updates
= gradient steps of the phase in total). Every phase has its own optimizer and learning-rate schedule (warm-up,
cosine), as a single run has. --watch: tasks whose test score is recorded every 250 updates over the whole
plan (default: the tasks of the last phase).
-> results/curriculum.jsonl: plan (also as "task"), model, seed, final scores, curve [[update, {task: score}],
...]. Runs already in the output file are skipped.
"""
import argparse
import json
import multiprocessing as mp
import sys
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def parse(plan):
    return [(p.split(":")[0].split("+"), int(p.split(":")[1])) for p in plan.split()]


def job(args):
    plan, model_name, seed, watch, name = args
    import torch
    torch.set_num_threads(1)
    from .models import build_model
    from .tasks import make_task
    from .train import final_metrics, make_learner, quick_score, save_checkpoint, train_loop
    try:
        torch.manual_seed(seed)
        phases = parse(plan)
        model = build_model(model_name, 100_000, seed=seed)
        watch = watch or phases[-1][0]
        wt = {t: make_task(t) for t in watch}
        curve, done, t0 = [], 0, time.time()
        for k, (names, updates) in enumerate(phases):
            learners = [make_learner(model, make_task(t), updates, 64, seed + 100 * k + j)
                        for j, t in enumerate(names)]

            def on_eval(i, done=done):
                if i > 0:
                    curve.append([done + i, {t: round(quick_score(model, task), 4) for t, task in wt.items()}])
            train_loop(model, learners, updates, 2e-3, 10 ** 9, on_eval, 250)
            done += updates
        final = {t: round(final_metrics(model, task)["score"], 4) for t, task in wt.items()}
        curve.append([done, final])
        if name:
            save_checkpoint(model, model_name, name, seed, list(final.values())[-1])
        return {"plan": plan, "task": plan, "model": model_name, "seed": seed, "updates": done, "final": final,
                "time": round(time.time() - t0, 1), "curve": curve}
    except Exception:  # noqa: BLE001
        return {"plan": plan, "model": model_name, "seed": seed, "error": traceback.format_exc()}


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("cmd", choices=["run"])
    ap.add_argument("--plans", nargs="+", required=True)
    ap.add_argument("--models", nargs="+", required=True)
    ap.add_argument("--seeds", nargs="+", type=int, default=[5, 6])
    ap.add_argument("--watch", nargs="+", default=None)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--save-as", default=None, help="checkpoint name (in place of a task name)")
    ap.add_argument("--out", default=str(ROOT / "results" / "curriculum.jsonl"))
    a = ap.parse_args()
    done = set()
    if Path(a.out).exists():
        for ln in Path(a.out).read_text().splitlines():
            r = json.loads(ln)
            if "error" not in r:
                done.add((r["plan"], r["model"], r["seed"]))
    jobs = [(p, m, s, a.watch, a.save_as) for p in a.plans for m in a.models for s in a.seeds
            if (p, m, s) not in done]
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    with mp.Pool(a.workers) as pool:
        for n, r in enumerate(pool.imap_unordered(job, jobs), 1):
            with open(a.out, "a") as f:
                f.write(json.dumps(r) + "\n")
            print(f"[{n}/{len(jobs)}] {r['model']:<12} s{r['seed']} {r['plan']:<50} "
                  f"{r.get('final', r.get('error', '')[-200:])}", flush=True)


if __name__ == "__main__":
    main()
