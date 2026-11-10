"""Summary of the size / module-count study (results/size.jsonl; 100k references from older result files).
    python scripts/size_summary.py"""
import glob, json, sys
from pathlib import Path
import pandas as pd
ROOT = Path(__file__).resolve().parents[1]
TASKS = ["servo", "numseq", "count", "push_easy", "grid_follow", "cycle_mem"]
rows, seen = [], set()
for f in [ROOT / "results" / "size.jsonl"] + sorted(glob.glob(str(ROOT / "results" / "*.jsonl"))):
    for ln in open(f):
        try:
            r = json.loads(ln)
        except ValueError:
            continue
        if "error" in r or r.get("task") not in TASKS or "score" not in r or r.get("seed") not in (0, 1, 2):
            continue
        if r.get("updates") != (6000 if r["task"] == "servo" else 1500):
            continue
        k = (r["model"], r["task"], r["seed"])
        if k in seen:
            continue
        seen.add(k)
        base, _, size = r["model"].partition("@")
        rows.append({"model": base, "size": size or "100k", "task": r["task"], "seed": r["seed"], "score": r["score"],
                     "time": r["train_time"], "params": r["params"]})
d = pd.DataFrame(rows)
B = ["layer_s", "hier_s", "layer_i", "layer_s_sp4", "vit", "cnn", "gru"]
with pd.option_context("display.width", 250, "display.max_rows", 500):
    for what in ("score", "time"):
        print(f"== {what} by size (mean of seeds 0-2)")
        t = d[d.model.isin(B)].pivot_table(index=["model", "size"], columns="task", values=what)[TASKS]
        t = t.reindex([(m, s) for m in B for s in ("25k", "100k", "400k")])
        print(t.round(2 if what == "score" else 0).to_string())
    print("== n runs"); print(d[d.model.isin(B)].pivot_table(index=["model", "size"], columns="task", values="score", aggfunc="count")[TASKS].to_string())
    print("== module count (100k): rows R (base 4), columns C (base 8)")
    S = [f"layer_{s}{x}" for s in "si" for x in ("_r2", "", "_r8", "_c4", "_c16")]
    t = d[d.model.isin(S) & (d["size"] == "100k")].pivot_table(index="model", columns="task", values="score")[TASKS]
    print(t.reindex(S).round(2).to_string())
    print(d[d.model.isin(S) & (d["size"] == "100k")].pivot_table(index="model", columns="task", values="score", aggfunc="count")[TASKS].reindex(S).to_string())
