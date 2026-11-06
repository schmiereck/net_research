# NetResearch

Benchmark-Plattform zum Vergleich von Netzarchitekturen auf einheitlichem I/O
(Input: 3×16×16 binäres RGB pro Zeitschritt, Output: 64 Logits). Konzept: `NetResearch.md`,
Plan: `PLAN.md`.

## Setup
```
python -m venv .venv
.venv\Scripts\python -m pip install torch --index-url https://download.pytorch.org/whl/cpu
.venv\Scripts\python -m pip install numpy matplotlib pillow pandas pytest
```

## Benutzung
```
# Tests
.venv\Scripts\python -m pytest -q tests

# Benchmark (resumable, Ergebnisse in results/runs.jsonl)
.venv\Scripts\python -m netresearch.bench --models all --tasks all --seeds 0 --updates 1500 --workers 10
.venv\Scripts\python -m netresearch.bench --models gru hier_i --tasks cycle_mem --seeds 0 1 2

# Report -> results/report.md + results/heatmap.png
.venv\Scripts\python -m netresearch.report

# GUI: trainierte Modelle live nebeneinander beobachten (braucht results/checkpoints aus einem Bench-Lauf)
.venv\Scripts\python -m netresearch.gui
```

## Erweitern
* **Neues Modell:** Klasse mit `init_state(B)` und `forward(x, state) -> (logits[B,64], state)`
  (siehe `netresearch/models/basic.py`), dann in `MODELS`/`MODEL_ORDER` in
  `netresearch/models/__init__.py` eintragen (Konstruktor mit `width`-Argument → automatisches
  Parameter-Matching).
* **Neuer Task:** `SupervisedTask.sample()` bzw. `Game` mit `reset/step/render/expert`
  implementieren und in `netresearch/tasks/registry.py` registrieren.

## Daten
* `data/alice.txt` – „Alice's Adventures in Wonderland“, Project Gutenberg (gemeinfrei).
* `data/digits.npz` – wird beim ersten Start aus den Windows-System-Fonts erzeugt
  (Test-Fonts: Georgia, Trebuchet, Constantia, Segoe Print).
