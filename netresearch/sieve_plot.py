"""Figure of the benchmark sieve: how far and how well each architecture gets along both paths.

    python -m netresearch.sieve_plot [--models ...] [--out results/sieve]      # writes .png and .svg

Top: the stage tree (A1 -> A2 -> A3 without memory, A1 -> M1 -> M2 -> M3 memory) with how many architectures
reached / passed each stage. Below, one ranked bar chart per path. Progress = number of stages passed + mean
score of the first stage not passed (so 2.6 = two stages passed, 0.6 on the third). The solid part of a bar
is the passed stages, the light part the partial score of the stage where the architecture stopped.
"""
import argparse

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyBboxPatch  # noqa: E402

from .sieve import PASS, ROOT, STAGES, evaluate, load_results  # noqa: E402

PATHS = {"A": ["A1", "A2", "A3"], "M": ["A1", "M1", "M2", "M3"]}
TITLE = {"A": "Pfad A: ohne Gedächtnis", "M": "Pfad M: Gedächtnis"}
COL = {"A": "#2a78d6", "M": "#eb6834"}                  # categorical slots 1, 2 (reference palette)
LIGHT = {"A": "#b4cff0", "M": "#f6c4ae"}
SURFACE, INK, INK2, MUTED, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#8a8984", "#e4e3df"


def progress(ev, path):
    """-> (progress value, passed stages, stopping stage, its mean, worst task, state of the stopping stage)."""
    passed = 0
    for s in PATHS[path]:
        state, mu, worst, ws, _ = ev[s]
        if state == "pass":
            passed += 1
            continue
        if state == "fail":
            return passed + mu, passed, s, mu, (worst, ws), "fail"
        return passed, passed, s, None, None, state           # missing results
    return passed, passed, None, None, None, "done"


def wrap(words, width=38):
    lines, cur = [], ""
    for w in words:
        if cur and len(cur) + len(w) + 2 > width:
            lines.append(cur + ",")
            cur = w
        else:
            cur = f"{cur}, {w}" if cur else w
    return "\n".join(lines + [cur])


def draw_tree(ax, evs):
    ax.set_xlim(0, 4)
    ax.set_ylim(0, 2)
    ax.axis("off")
    pos = {"A1": (0.5, 1.0), "A2": (1.5, 1.55), "A3": (2.5, 1.55), "M1": (1.5, 0.45), "M2": (2.5, 0.45),
           "M3": (3.5, 0.45)}
    w, h = 0.84, 0.8
    for s, (x, y) in pos.items():
        admitted = sum(ev[s][0] != "locked" for ev in evs.values())
        ok = sum(ev[s][0] == "pass" for ev in evs.values())
        open_ = sum(ev[s][0] == "missing" for ev in evs.values())
        path = "M" if s.startswith("M") else "A"
        hard = s in ("A3", "M3")
        ax.add_patch(FancyBboxPatch((x - w / 2, y - h / 2), w, h, boxstyle="round,pad=0,rounding_size=0.06",
                                    fc=SURFACE, ec=COL[path] if s != "A1" else INK2, lw=2.2 if hard else 1.2))
        desc = STAGES[s][0].split(": ")[1]
        ax.text(x, y + 0.23, f"{s}  {desc}", ha="center", va="center", fontsize=8.5, color=INK, weight="bold")
        ax.text(x, y + 0.03, wrap(STAGES[s][2]), ha="center", va="center", fontsize=6.3, color=INK2,
                linespacing=1.3)
        ax.text(x, y - 0.19, f"{admitted} zugelassen → {ok} bestanden", ha="center", va="center", fontsize=7.5,
                color=INK)
        if open_:
            ax.text(x, y - 0.3, f"{open_} noch ohne Ergebnis", ha="center", va="center", fontsize=6.5, color=MUTED)
    for a, b in (("A1", "A2"), ("A2", "A3"), ("A1", "M1"), ("M1", "M2"), ("M2", "M3")):
        (x0, y0), (x1, y1) = pos[a], pos[b]
        ax.annotate("", xy=(x1 - w / 2, y1), xytext=(x0 + w / 2, y0),
                    arrowprops=dict(arrowstyle="-|>", color=MUTED, lw=1.2, shrinkA=2, shrinkB=2))
    ax.text(3.5, 1.55, f"bestanden: jede Aufgabe\nder Stufe ≥ {PASS}\n(Mittel über die Seeds)", ha="center",
            va="center", fontsize=7.5, color=INK2)


def draw_path(ax, evs, path):
    stages = PATHS[path]
    rows = sorted(((m, *progress(ev, path)) for m, ev in evs.items()), key=lambda r: (r[1], r[0]))
    for i, (m, val, passed, stop, mu, worst, state) in enumerate(rows):
        if passed:
            ax.barh(i, passed, height=0.62, color=COL[path], edgecolor=SURFACE, linewidth=1.5)
        if mu is not None:
            ax.barh(i, mu, left=passed, height=0.62, color=LIGHT[path], edgecolor=SURFACE, linewidth=1.5)
        end = passed + (mu or 0)
        if state == "fail":
            note = f"{stop} {mu:.2f} · {worst[0]} {worst[1]:.2f}"
        elif state == "done":
            note = "alle Stufen bestanden"
        else:
            note = f"{stop}: Ergebnisse fehlen"
        ax.text(end + 0.04, i, note, va="center", fontsize=7, color=INK2 if state != "missing" else MUTED)
    ax.set_yticks(range(len(rows)), [r[0] for r in rows], fontsize=7.5, color=INK)
    ax.set_xlim(0, len(stages) + 0.9)
    ax.set_ylim(-0.6, len(rows) - 0.4)
    ax.set_xticks([k + 0.5 for k in range(len(stages))], stages, fontsize=8, color=INK2)
    for k in range(1, len(stages) + 1):
        ax.axvline(k, color=GRID, lw=1, zorder=0)
    ax.tick_params(length=0)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(GRID)
    ax.set_title(TITLE[path], loc="left", fontsize=10, color=INK, weight="bold")
    ax.set_xlabel("Fortschritt = bestandene Stufen + Mittel der Stufe, an der die Architektur hängen bleibt",
                  fontsize=7, color=INK2)


def plot(models, out):
    res = load_results()
    models = models or sorted(res.model.unique())
    evs = evaluate(models, res)
    evs = {m: ev for m, ev in evs.items() if ev["A1"][0] != "missing"}
    n = len(evs)
    fig = plt.figure(figsize=(11, 3.2 + 0.2 * n), facecolor=SURFACE)
    gs = fig.add_gridspec(2, 2, height_ratios=[2.6, 0.2 * n + 0.6], hspace=0.25, wspace=0.55)
    draw_tree(fig.add_subplot(gs[0, :]), evs)
    for j, path in enumerate("AM"):
        ax = fig.add_subplot(gs[1, j])
        ax.set_facecolor(SURFACE)
        draw_path(ax, evs, path)
    fig.suptitle(f"Benchmark-Sieb: {n} Architekturen", x=0.06, ha="left", fontsize=12, color=INK, weight="bold")
    for ext in ("png", "svg"):
        fig.savefig(f"{out}.{ext}", dpi=160, bbox_inches="tight", facecolor=SURFACE)
    print(f"written {out}.png / .svg")


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--models", nargs="+", default=None)
    ap.add_argument("--out", default=str(ROOT / "results" / "sieve"))
    a = ap.parse_args()
    plot(a.models, a.out)


if __name__ == "__main__":
    main()
