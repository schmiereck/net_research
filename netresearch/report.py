"""Aggregate results/runs.jsonl into results/report.md (+ heatmap PNG).

    python -m netresearch.report [--runs results/runs.jsonl]
"""
import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
GROUP_ORDER = ["patterns", "memory", "image", "text", "game"]
# sequential single-hue ramp (light -> dark blue)
RAMP = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]


def load(path):
    rows = [json.loads(l) for l in Path(path).read_text().splitlines() if l.strip()]
    errors = [r for r in rows if "error" in r]
    df = pd.DataFrame([r for r in rows if "error" not in r])
    return df, errors


def heatmap(piv, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.colors import LinearSegmentedColormap

    cmap = LinearSegmentedColormap.from_list("seq", RAMP)
    vals = piv.values.astype(float)
    fig, ax = plt.subplots(figsize=(1.0 + 0.62 * vals.shape[1], 0.8 + 0.36 * vals.shape[0]))
    ax.imshow(np.clip(vals, 0, 1), cmap=cmap, vmin=0, vmax=1, aspect="auto")
    ax.set_xticks(range(vals.shape[1]), piv.columns, rotation=40, ha="right", fontsize=9, color="#333")
    ax.set_yticks(range(vals.shape[0]), piv.index, fontsize=9, color="#333")
    for i in range(vals.shape[0]):
        for j in range(vals.shape[1]):
            v = vals[i, j]
            if np.isnan(v):
                continue
            ax.text(j, i, f"{v:.2f}", ha="center", va="center", fontsize=7.5,
                    color="white" if np.clip(v, 0, 1) > 0.55 else "#222")
    ax.set_xticks(np.arange(-.5, vals.shape[1]), minor=True)
    ax.set_yticks(np.arange(-.5, vals.shape[0]), minor=True)
    ax.grid(which="minor", color="white", linewidth=2)
    ax.tick_params(which="both", length=0)
    for s in ax.spines.values():
        s.set_visible(False)
    ax.set_title("Score (0 = Zufall, 1 = perfekt / Experte)", fontsize=10, loc="left", color="#222")
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)


def md_table(df, fmt="{:.2f}"):
    cols = list(df.columns)
    out = ["| " + " | ".join([df.index.name or ""] + [str(c) for c in cols]) + " |",
           "|" + "---|" * (len(cols) + 1)]
    for idx, row in df.iterrows():
        cells = [fmt.format(v) if isinstance(v, (float, np.floating)) and not np.isnan(v) else
                 ("–" if isinstance(v, float) else str(v)) for v in row]
        out.append("| " + " | ".join([str(idx)] + cells) + " |")
    return "\n".join(out)


def main():
    from .models import MODEL_ORDER
    from .tasks import TASKS, make_task

    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", default=str(ROOT / "results" / "runs.jsonl"))
    ap.add_argument("--out", default=str(ROOT / "results" / "report.md"))
    a = ap.parse_args()
    df, errors = load(a.runs)
    out_dir = Path(a.out).parent

    tasks = [t for t in TASKS if t in set(df.task)]
    models = [m for m in MODEL_ORDER if m in set(df.model)]
    agg = df.groupby(["model", "task"]).agg(score=("score", "mean"), sd=("score", "std"), n=("seed", "count"))
    piv = agg["score"].unstack("task").reindex(index=models, columns=tasks)
    piv.index.name = "Modell"
    groups = {t: make_task(t).spec.group for t in tasks}

    summary = pd.DataFrame(index=piv.index)
    for g in GROUP_ORDER:
        cols = [t for t in tasks if groups[t] == g]
        if cols:
            summary[g] = piv[cols].mean(axis=1)
    summary["gesamt"] = piv.mean(axis=1)
    summary["Ø Rang"] = piv.rank(axis=0, ascending=False).mean(axis=1)
    meta = df.groupby("model").agg(params=("params", "first"), width=("width", "first"),
                                   time=("train_time", "sum"))
    summary["Parameter"] = meta["params"].reindex(summary.index).map(lambda v: f"{v / 1000:.0f}k")
    summary["Trainzeit [min]"] = (meta["time"].reindex(summary.index) / 60).map(lambda v: f"{v:.1f}")
    summary = summary.sort_values("gesamt", ascending=False)

    heatmap(piv, out_dir / "heatmap.png")

    # raw metrics per task
    raw = []
    for t in tasks:
        sub = df[df.task == t].groupby("model").mean(numeric_only=True).reindex(models)
        if make_task(t).spec.kind == "control":
            cols = ["return", "ep_len", "score"]
        elif "bpc" in sub:
            cols = ["acc", "bpc", "score"] if t == "charnext" else ["acc", "score"]
        else:
            cols = ["acc", "score"] + (["bit_acc"] if t == "count" else [])
        tab = sub[[c for c in cols if c in sub]].dropna(how="all")
        tab.index.name = "Modell"
        extra = ""
        if make_task(t).spec.kind == "control":
            r0 = df[df.task == t].iloc[0]
            extra = f" (Random: {r0['random']:.2f}, Experte: {r0['expert']:.2f})"
        raw.append(f"### {t}{extra}\n\n{make_task(t).spec.description}\n\n{md_table(tab)}\n")

    seeds = sorted(int(s) for s in df.seed.unique())
    lines = [
        "# NetResearch – Benchmark-Report", "",
        f"Läufe: {len(df)} (Seeds {seeds}), Updates je Lauf: {sorted(int(u) for u in df.updates.unique())}, "
        f"~100k Parameter je Modell. Fehlgeschlagene Läufe: {len(errors)}.", "",
        "Score: Klassifikation `(acc-chance)/(1-chance)`, Bits: Exact-Match, Spiele "
        "`(Return-Random)/(Experte-Random)`. Werte < 0 = schlechter als Zufall.", "",
        "## Zusammenfassung (Mittel je Task-Gruppe)", "", md_table(summary), "",
        "## Score je Task", "", "![heatmap](heatmap.png)", "", md_table(piv), "",
        "## Rohmetriken je Task", "", *raw,
    ]
    if errors:
        lines += ["## Fehler", ""] + [f"* {e['model']} / {e['task']}: `{e['error'].splitlines()[-1]}`"
                                      for e in errors]
    Path(a.out).write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {a.out}")


if __name__ == "__main__":
    main()
