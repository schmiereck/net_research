"""Benchmark sieve: stages of increasing difficulty that an architecture has to pass to reach the hard tests.

Two paths, because memory is a separate ability:
    A  without memory: perception, steering, planning           A1 -> A2 -> A3
    M  memory (needs A1: an architecture must first see and act)       A1 -> M1 -> M2 -> M3
A stage is passed when every task of the stage reaches PASS (mean over the seeds that exist). The last stage of
each path holds the hard goal tasks (A3: path planning, push; M3: exploring in large worlds).

    python -m netresearch.sieve status [--models ...]      # table: per model and stage pass / fail / missing
    python -m netresearch.sieve next   [--models ...]      # bench commands for the stages that are due
    python -m netresearch.sieve run --models ... [--seeds 0] [--workers 6]   # run stage by stage locally

Results are read from all results/*.jsonl files (runs with 1500 updates; a later file wins for the same run).
"""
import argparse
import subprocess
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results" / "sieve.jsonl"
PASS = 0.75

# name -> (description, prerequisite stage, tasks)
STAGES = {
    "A1": ("ohne Gedächtnis: Grundlagen", None, ["shapes", "digits", "paddle", "bricks"]),
    "A2": ("ohne Gedächtnis: Steuern", "A1", ["cycle", "numseq", "racer", "maze", "crossing", "grid_easy", "push_easy"]),
    "A3": ("ohne Gedächtnis: Planen (schwer)", "A2", ["grid", "push"]),
    "M1": ("Gedächtnis: Halten", "A1", ["cycle_mem", "paddle_mem", "bricks_mem", "delay"]),
    "M2": ("Gedächtnis: Binden, Erkunden", "M1", ["recall", "crossmem", "grid_follow_easy", "grid_scroll_easy"]),
    "M3": ("Gedächtnis: Erkunden (schwer)", "M2", ["grid_follow", "grid_scroll"]),
}


def load_results():
    frames = []
    for p in sorted((ROOT / "results").glob("*.jsonl")):
        try:
            d = pd.read_json(p, lines=True)
        except ValueError:
            continue
        if {"model", "task", "seed", "score"} <= set(d.columns):
            d = d[d.get("updates", 1500) == 1500] if "updates" in d.columns else d
            frames.append(d[["model", "task", "seed", "score"]])
    if not frames:
        return pd.DataFrame(columns=["model", "task", "seed", "score"])
    d = pd.concat(frames).dropna(subset=["score"])
    return d.drop_duplicates(["model", "task", "seed"], keep="last")


def evaluate(models, res=None):
    """-> {model: {stage: (state, mean, worst task, worst score, n seeds)}}, state = pass / fail / missing / locked."""
    res = load_results() if res is None else res
    mean = res.groupby(["model", "task"]).score.mean()
    seeds = res.groupby(["model", "task"]).seed.nunique()
    out = {}
    for m in models:
        st = {}
        for name, (_, pre, tasks) in STAGES.items():
            if pre and st[pre][0] != "pass":
                st[name] = ("locked", None, None, None, 0)
                continue
            have = [t for t in tasks if (m, t) in mean.index]
            if len(have) < len(tasks):
                st[name] = ("missing", None, None, None, 0)
                continue
            sc = {t: float(mean[(m, t)]) for t in tasks}
            worst = min(sc, key=sc.get)
            n = int(min(seeds[(m, t)] for t in tasks))
            st[name] = ("pass" if sc[worst] >= PASS else "fail", sum(sc.values()) / len(sc), worst, sc[worst], n)
        out[m] = st
    return out


def missing_tasks(model, stage, res):
    have = set(res[res.model == model].task)
    return [t for t in STAGES[stage][2] if t not in have]


def status(models):
    res = load_results()
    models = models or sorted(res.model.unique())
    ev = evaluate(models, res)
    print(f"Sieb (bestanden: jede Aufgabe der Stufe >= {PASS}; Wert = Mittel der Stufe, dahinter schwächste Aufgabe)")
    for name, (desc, pre, tasks) in STAGES.items():
        print(f"  {name} {desc:34s} <- {pre or '-':3s} {', '.join(tasks)}")
    w = max(len(m) for m in models)
    print("\n" + " " * w + "".join(f"  {s:>24s}" for s in STAGES))
    for m in models:
        cells = []
        for s in STAGES:
            state, mu, worst, ws, n = ev[m][s]
            if state in ("pass", "fail"):
                mark = "OK " if state == "pass" else "-- "
                cells.append(f"{mark}{mu:.2f} ({worst} {ws:.2f})"[:24])
            else:
                cells.append(state)
        print(f"{m:{w}s}" + "".join(f"  {c:>24s}" for c in cells))


def due(models, res):
    """Stages whose prerequisite is passed but that still lack results -> {stage: {model: [tasks]}}."""
    ev = evaluate(models, res)
    plan = {}
    for m in models:
        for s in STAGES:
            if ev[m][s][0] == "missing":
                plan.setdefault(s, {})[m] = missing_tasks(m, s, res)
    return plan


def bench_args(models_tasks, seeds):
    tasks = sorted({t for ts in models_tasks.values() for t in ts})
    return ["--models", *models_tasks, "--tasks", *tasks, "--seeds", *map(str, seeds)]


def next_cmd(models, seeds):
    res = load_results()
    plan = due(models or sorted(res.model.unique()), res)
    if not plan:
        print("nichts fällig: alle Modelle haben für jede offene Stufe Ergebnisse oder sind ausgesiebt")
    for s, mt in plan.items():
        print(f"{s}: python -m netresearch.bench {' '.join(bench_args(mt, seeds))} --out {OUT.relative_to(ROOT)}")


def run(models, seeds, workers):
    """Run the due stages locally until nothing is due any more (stage by stage, the sieve decides who goes on)."""
    while True:
        plan = due(models, load_results())
        if not plan:
            break
        s = next(iter(plan))
        args = bench_args(plan[s], seeds)
        print(f"== Stufe {s}: {' '.join(args)}", flush=True)
        rc = subprocess.call([sys.executable, "-m", "netresearch.bench", *args, "--workers", str(workers),
                              "--out", str(OUT)], cwd=ROOT)
        if rc:
            raise SystemExit(rc)
    status(models)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("cmd", choices=["status", "next", "run"])
    ap.add_argument("--models", nargs="+", default=None)
    ap.add_argument("--seeds", nargs="+", type=int, default=[0])
    ap.add_argument("--workers", type=int, default=6)
    a = ap.parse_args()
    if a.cmd == "status":
        status(a.models)
    elif a.cmd == "next":
        next_cmd(a.models, a.seeds)
    else:
        if not a.models:
            raise SystemExit("run needs --models")
        run(a.models, a.seeds, a.workers)


if __name__ == "__main__":
    main()
