"""Does a small benchmark forecast a robot benchmark? Rank agreement over the architectures that ran both.

    python scripts/forecast.py

For each pair (small task, robot task): the architectures with results on both (plain 100k nets, mean over
seeds, at the given number of updates), Spearman's rho of the two score columns, and the scores themselves.
With few architectures rho is a description, not a proof; the pairs are listed in PAIRS and should grow with
every architecture that is run on both sides. Reads all results/*.jsonl with plain single-task runs.
"""
import glob
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SKIP = ("library", "eval", "curriculum", "probe", "breakdown", "multitask")
# (small task, updates or None = most, robot task, updates)
PAIRS = [("servo", 6000, "robot_gaze", 6000),
         ("servo", 6000, "robot_reach", 6000),
         ("servo", 6000, "robot_findc", 24000),
         ("count", None, "robot_findc", 24000),
         ("push_easy", None, "robot_findc", 24000),
         ("match_shift", 12000, "robot_lookmem", 6000),
         ("same_shift", 24000, "robot_lookmem", 6000),
         ("keep_shift", None, "robot_lookmem", 6000),
         ("cycle_mem", None, "robot_lookmem", 6000),
         ("recall", None, "robot_lookmem", 6000)]


def load():
    rows = []
    for f in glob.glob(str(ROOT / "results" / "*.jsonl")):
        if any(x in Path(f).name for x in SKIP):
            continue
        for ln in open(f):
            try:
                r = json.loads(ln)
            except ValueError:
                continue
            if "score" in r and "model" in r and isinstance(r.get("task"), str):
                m = r["model"].replace("+cmd", "")                     # the command port is part of the task
                if "@" not in m and "+" not in m:
                    rows.append((m, r["task"], r.get("updates"), r["score"]))
    return pd.DataFrame(rows, columns=["model", "task", "updates", "score"])


def main():
    df = load()

    def col(task, upd):
        d = df[df.task == task]
        return d[d.updates == (upd or d.updates.max())].groupby("model").score.mean()

    for a, ua, b, ub in PAIRS:
        x, y = col(a, ua), col(b, ub)
        m = sorted(set(x.index) & set(y.index), key=lambda k: -y[k])
        rho = x[m].rank().corr(y[m].rank()) if len(m) > 2 and x[m].nunique() > 1 and y[m].nunique() > 1 \
            else float("nan")
        print(f"{a:<12} -> {b:<14} n={len(m):<2} rho={rho:+.2f}   "
              + "  ".join(f"{k} {x[k]:.2f}/{y[k]:.2f}" for k in m))


if __name__ == "__main__":
    sys.exit(main())
