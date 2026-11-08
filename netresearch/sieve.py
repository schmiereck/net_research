"""Benchmark sieve: stages of increasing difficulty that an architecture has to pass to reach the hard tests.

Two paths, because memory is a separate ability:
    A  without memory: perception, steering, planning           A1 -> A2 -> A3 -> A4
    M  memory (needs A1: an architecture must first see and act)       A1 -> M1 -> M2 -> M3 -> M4
A stage is passed when every task of the stage reaches PASS (mean over the seeds that exist). The last stage of
each path holds the hard goal tasks (A4: path planning, push; M4: exploring in large worlds).

    python -m netresearch.sieve status [--models ...]      # table: per model and stage pass / fail / missing
    python -m netresearch.sieve next   [--models ...]      # bench commands for the stages that are due
    python -m netresearch.sieve run --models ... [--seeds 0] [--workers 6] [--out results/sieve.jsonl]
                                                           # run stage by stage until nothing is due
On the worker PC: python -m netresearch.jobs submit --sieve <name> -- --models ... --seeds 0 1 2
(the worker runs "sieve run" there; all results committed in results/ count, so only missing runs are made).
A new architecture needs nothing else: it starts at A1 and only gets the stages it unlocks.

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
    "A2": ("ohne Gedächtnis: Steuern", "A1", ["cycle", "numseq", "grid_small_ego"]),
    "A3": ("ohne Gedächtnis: Ausweichen, Planen", "A2", ["maze", "push_easy", "racer", "crossing", "grid_small"]),
    "A4": ("ohne Gedächtnis: Planen (schwer)", "A3", ["grid_easy", "grid", "push"]),
    "M1": ("Gedächtnis: Halten", "A1", ["cycle_mem", "paddle_mem", "bricks_mem", "delay"]),
    "M2": ("Gedächtnis: Binden", "M1", ["recall", "grid_follow_easy"]),
    "M3": ("Gedächtnis: Verknüpfen", "M2", ["crossmem", "grid_scroll_easy"]),
    "M4": ("Gedächtnis: Erkunden (schwer)", "M3", ["grid_follow", "grid_scroll"]),
}


def load_results(extra=()):
    """All runs in results/*.jsonl (+ extra files, e.g. a worker's own output), later files win."""
    frames = []
    files = sorted((ROOT / "results").glob("*.jsonl"))
    files += [Path(e) for e in extra if Path(e).exists() and Path(e).resolve() not in {f.resolve() for f in files}]
    for p in files:
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


def evaluate(models, res=None, seeds=None):
    """-> {model: {stage: (state, mean, worst task, worst score, n seeds)}}, state = pass / fail / missing / locked.
    seeds: a stage counts as complete only when every task has all these seeds (default: at least one seed)."""
    res = load_results() if res is None else res
    mean = res.groupby(["model", "task"]).score.mean()
    have = set(zip(res.model, res.task, res.seed))
    nseeds = res.groupby(["model", "task"]).seed.nunique()
    out = {}
    for m in models:
        st = {}
        for name, (_, pre, tasks) in STAGES.items():
            if pre and st[pre][0] != "pass":
                st[name] = ("locked", None, None, None, 0)
                continue
            if missing_tasks(m, name, res, seeds, have):
                st[name] = ("missing", None, None, None, 0)
                continue
            sc = {t: float(mean[(m, t)]) for t in tasks}
            worst = min(sc, key=sc.get)
            n = int(min(nseeds[(m, t)] for t in tasks))
            st[name] = ("pass" if sc[worst] >= PASS else "fail", sum(sc.values()) / len(sc), worst, sc[worst], n)
        out[m] = st
    return out


def missing_tasks(model, stage, res, seeds=None, have=None):
    """-> {task: [missing seeds]} (seeds=None: a task is missing only if it has no seed at all)."""
    have = set(zip(res.model, res.task, res.seed)) if have is None else have
    seen = {t for (m, t, _) in have if m == model}
    miss = {}
    for t in STAGES[stage][2]:
        if seeds is None:
            if t not in seen:
                miss[t] = [0]
        else:
            ms = [sd for sd in seeds if (model, t, sd) not in have]
            if ms:
                miss[t] = ms
    return miss


def status(models, extra=()):
    res = load_results(extra)
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


def due(models, res, seeds):
    """Runs that are due: the first incomplete stage (in STAGES order) whose prerequisite is passed.
    -> (stage, [bench argument lists]) or (None, []). Models with the same missing tasks and seeds share one
    bench call, so nothing that exists already is run again."""
    ev = evaluate(models, res, seeds)
    have = set(zip(res.model, res.task, res.seed))
    for s in STAGES:
        groups = {}
        for m in models:
            if ev[m][s][0] != "missing":
                continue
            miss = missing_tasks(m, s, res, seeds, have)
            by_seeds = {}
            for t, ms in miss.items():
                by_seeds.setdefault(tuple(ms), []).append(t)
            for ms, ts in by_seeds.items():
                groups.setdefault((tuple(sorted(ts)), ms), []).append(m)
        if groups:
            return s, [["--models", *ms, "--tasks", *ts, "--seeds", *map(str, sd)]
                       for (ts, sd), ms in groups.items()]
    return None, []


def next_cmd(models, seeds):
    res = load_results()
    models = models or sorted(res.model.unique())
    s, calls = due(models, res, seeds)
    if not calls:
        print("nichts fällig: alle Modelle haben für jede offene Stufe Ergebnisse oder sind ausgesiebt")
    for args in calls:
        print(f"{s}: python -m netresearch.bench {' '.join(args)} --out {OUT.relative_to(ROOT)}")
    if calls:
        print("(danach können weitere Stufen fällig werden; 'run' macht das automatisch)")


def run(models, seeds, workers, out=OUT):
    """Run the due runs stage by stage until nothing is due any more (the sieve decides who goes on)."""
    tried = set()
    while True:
        s, calls = due(models, load_results([out]), seeds)
        if not calls:
            break
        key = (s, tuple(map(tuple, calls)))
        if key in tried:                                # bench ran but the results are still missing
            raise SystemExit(f"stage {s}: runs failed, see the log")
        tried.add(key)
        for args in calls:
            print(f"== Stufe {s}: {' '.join(args)}", flush=True)
            rc = subprocess.call([sys.executable, "-m", "netresearch.bench", *args, "--workers", str(workers),
                                  "--out", str(out)], cwd=ROOT)
            if rc:
                raise SystemExit(rc)
    status(models, [out])


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("cmd", choices=["status", "next", "run"])
    ap.add_argument("--models", nargs="+", default=None)
    ap.add_argument("--seeds", nargs="+", type=int, default=[0])
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--out", default=str(OUT))
    a = ap.parse_args()
    if a.cmd == "status":
        status(a.models)
    elif a.cmd == "next":
        next_cmd(a.models, a.seeds)
    else:
        if not a.models:
            raise SystemExit("run needs --models")
        run(a.models, a.seeds, a.workers, Path(a.out))


if __name__ == "__main__":
    main()
