"""Curriculum runs: one net learns a list of phases one after the other; a phase is one task or several at once.

    python -m netresearch.curriculum run --plans "same_shift:12000" "read_shift:2000 same_shift:10000" \
        "read_shift+same_shift:12000" --models layer_s gru --seeds 5 6 --watch same_shift [--workers 4]

A plan is a list of phases "task[+task...]:updates". Several tasks in a phase are trained round-robin (updates
= gradient steps of the phase in total). Every phase has its own optimizer and learning-rate schedule (warm-up,
cosine), as a single run has. The word "freeze" between phases (PLAN_TRAINER Phase C, models/route.py) freezes
the net trained so far and adds a new module of the same kind that reads the frozen net's top representation
through its command port; only the new module, that read-out and an output gate learn from then on. "freeze" as
the first word freezes the untrained net (control: same structure, no skill in the frozen part); "freeze:<opt>"
runs one of the probes in models/route.py; "freeze:sel" (also "freeze:pcell+sel") adds the selection by task: the
statistic of the phase just learned is taken at the freeze, and the row gets "selected" (share of scored steps
per watched task handed to the frozen net alone). --watch: tasks whose test score is recorded every 250 updates over the whole
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
    return [("freeze", p.partition(":")[2]) if p.split(":")[0] == "freeze"
            else (p.split(":")[0].split("+"), int(p.split(":")[1])) for p in plan.split()]


def job(args):
    plan, model_name, seed, watch, name = args
    import numpy as np
    import torch
    torch.set_num_threads(1)
    from .models import build_model
    from .tasks import make_task
    from .train import final_metrics, make_learner, quick_score, save_checkpoint, train_loop
    try:
        torch.manual_seed(seed)
        phases = parse(plan)
        for names, _ in phases:
            for t in ([] if names == "freeze" else names):
                make_task(t)                   # fail early on a missing task or data set
        model = build_model(model_name, 100_000, seed=seed)
        params = model_name.partition("@")[2]
        params = int(float(params.rstrip("k")) * 1000) if params else 100_000
        rng = torch.get_rng_state()
        for names, opt in phases:                        # fail early on a probe this net does not have (e.g.
            if names == "freeze":                        # 'pcell' for a non-grid), not after the first stage
                from .models.route import freeze_and_route
                freeze_and_route(build_model(model_name, 100_000, seed=seed), model_name, params, seed, opt=opt)
        torch.set_rng_state(rng)                         # the check leaves the run as it was
        watch = watch or phases[-1][0]
        wt = {t: make_task(t) for t in watch}
        curve, ref_curve, done, t0 = [], [], 0, time.time()
        ref_pics = None
        if hasattr(model, "ref_enc"):                    # pictures of the wanted object to watch the encoder with
            b = next(iter(wt.values())).sample(256, np.random.default_rng(4242), split="test")
            if "ref" in b:
                r = torch.tensor(b["ref"].reshape(-1, *b["ref"].shape[-3:]))
                ref_pics = r[r.flatten(1).amax(1) > 0][:512].float()         # without the blank ones

        def watch_ref(u):
            if ref_pics is not None:
                enc = getattr(model, "new", model).ref_enc   # after "freeze": the new module's encoder
                with torch.no_grad():
                    pre = enc.net[:-1](ref_pics)
                out = enc.net[-1](pre)             # tanh ("+ref") or nothing ("+refl")
                ref_curve.append([u, round(out.std(0).mean().item(), 4),
                                  round((out.abs() > 0.95).float().mean().item(), 4),
                                  round(pre.abs().mean().item(), 3), round(pre.std(0).mean().item(), 3)])
        for k, (names, updates) in enumerate(phases):
            if names == "freeze":
                from .models.route import freeze_and_route
                model = freeze_and_route(model, model_name, params, seed, opt=updates)
                if model.wants_select:                   # "sel": the statistic of the task(s) just learned
                    from .models.route import fit_familiar
                    old = [p for p, _ in phases[:k] if p != "freeze"]
                    assert old, "freeze:sel needs a learned phase before it"
                    fit_familiar(model, [make_task(t) for t in old[-1]])
                continue
            specs = [make_task(t).spec for t in names]
            # tasks of one phase that share the symbol area must use the same code there: several step tasks in
            # the population code are fine (the area means the same, one step), one next to another code is not
            sym = [s for s in specs if s.role == "symbol"]
            if any(s.pop for s in sym) and not all(s.pop for s in sym):
                raise ValueError(f"{'+'.join(names)}: a step task in the population code shares the symbol area "
                                 f"with another task; use its '<name>_bits' form in this phase")
            learners = [make_learner(model, make_task(t), updates, 64, seed + 100 * k + j)
                        for j, t in enumerate(names)]

            def on_eval(i, done=done):
                watch_ref(done + i)
                if i > 0:
                    curve.append([done + i, {t: round(quick_score(model, task), 4) for t, task in wt.items()}])
            train_loop(model, learners, updates, 2e-3, 10 ** 9, on_eval, 250)
            done += updates
        fm = {t: final_metrics(model, task) for t, task in wt.items()}
        final = {t: round(m["score"], 4) for t, m in fm.items()}
        parts = {t: m["parts"] for t, m in fm.items() if "parts" in m}
        near = {t: [round(m["near"], 4), round(m["step_err"], 4)] for t, m in fm.items() if "near" in m}
        curve.append([done, final])
        frozen_final = None
        if hasattr(model, "frozen"):                     # Freeze & Route: the frozen net alone on the watched tasks
            frozen_final = {t: round(final_metrics(model.frozen, task)["score"], 4) for t, task in wt.items()}
        selected = None
        if getattr(model, "select", False):              # "sel": share of scored steps handed to the frozen net
            from .models.route import selection_share
            selected = {t: round(selection_share(model, task), 4) for t, task in wt.items()}
        watch_ref(done)
        if name:
            save_checkpoint(model, model_name, name, seed, list(final.values())[-1])
        return {"plan": plan, "task": plan, "model": model_name, "seed": seed, "updates": done, "final": final, "parts": parts,
                "near": near,          # step tasks: [share at most one cell off, mean error in cells]
                "time": round(time.time() - t0, 1), "curve": curve,
                **({"frozen_final": frozen_final} if frozen_final else {}),
                **({"selected": selected} if selected else {}),
                # picture encoder ("+ref") at every evaluation: [update, spread of the output over pictures,
                # share of output values beyond +-0.95, mean |value before the tanh|, its spread over pictures]
                **({"ref_curve": ref_curve} if ref_curve else {})}
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
