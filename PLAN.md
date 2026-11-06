# NetResearch – Umsetzungsplan

Ziel: Eine reproduzierbare Benchmark-Plattform, auf der unterschiedliche Netzarchitekturen
(klassisch, CNN, komplexwertig, Attention, modulare Bus-/Layer-/Hierarchie-Netze) **unter
gleichen Bedingungen** (gleiches I/O, gleiches Parameter-Budget, gleiches Trainingsbudget)
auf vielen Szenarien trainiert und verglichen werden.

Hardware-Annahme: CPU-only (12 Threads), daher kleine Netze (~100k Parameter) und kleine
Szenarien (16x16 Raster). Alles in Python 3.12 + PyTorch (CPU).

---

## 1. Einheitliche Schnittstelle („größter gemeinsamer Nenner“)

### Input
* Ein Frame pro Zeitschritt: Tensor `[3, 16, 16]`, binäres RGB (0/1).
* Alle Szenarien sind **sequenziell** (Episoden aus Zeitschritten). Bildklassifikation ist
  einfach eine Episode der Länge 1. Damit können Netze mit Gedächtnis überall eingesetzt werden.

### Output
* Ein Vektor mit **64 Logits** für jedes Netz und jedes Szenario.
* Jedes Szenario deklariert, wie es die Slots nutzt:
  * `class`: Softmax über die ersten `n` Slots (Aktionen, Klassen, Zeichen).
  * `bits`: Sigmoid über die ersten `n` Slots (Bitmuster, z.B. nächste Zahl als 8 Bit).
* Aktions-Slots für Spiele (fest): `0 noop, 1 left, 2 right, 3 up, 4 down, 5 fire, 6 jump, 7 reserve`.

### Netz-API
```
model.init_state(batch) -> state           # Tupel von Tensoren (Batch zuerst) oder ()
model(obs[B,3,16,16], state) -> logits[B,64], state
```
Zustandslose Netze geben `()` zurück; rekurrente Netze tragen ihren Zustand selbst.
Episodengrenzen werden vom Framework durch Maskieren des Zustands behandelt.

---

## 2. Szenarien (Phase 1)

| Klasse   | Task          | Beschreibung | Braucht Gedächtnis |
|----------|---------------|--------------|--------------------|
| Patterns | `cycle`       | Zufälliger Bit-Zyklus (Länge 2–12), letzte 16 Bits sichtbar → nächstes Bit | nein |
| Patterns | `cycle_mem`   | Wie `cycle`, aber nur das aktuelle Bit sichtbar | **ja** |
| Patterns | `count`       | Letzte 4 Zahlen (8 Bit) sichtbar, Schrittweite 1–7 → nächste Zahl (bits) | nein |
| Image    | `shapes`      | 6 geometrische Figuren, zufällig Größe/Position/Farbe + Rauschen | nein |
| Image    | `digits`      | Ziffern-OCR, gerendert aus System-Fonts; **Test-Fonts ≠ Train-Fonts** | nein |
| Text     | `charnext`    | Nächstes Zeichen (42er Alphabet), letzte 16 Zeichen als One-Hot-Zeilen | teilweise |
| Game     | `paddle`      | Ball-und-Schläger-Duell gegen CPU-Gegner | nein* |
| Game     | `bricks`      | Mauer mit Ball und Schläger abräumen | nein* |
| Game     | `crossing`    | Spielfigur über Fahrspuren mit Verkehr bringen | teilweise |
| Game     | `racer`       | Scrollende Straße, Hindernissen ausweichen | nein |
| Game     | `maze`        | Labyrinth, Punkte sammeln, zwei Verfolger meiden | teilweise |

\* Der Ball hinterlässt eine „Spur“ (vorherige Position in anderer Farbe), damit die Richtung
aus einem einzelnen Frame ablesbar ist. Gedächtnis wird gezielt über `cycle_mem` getestet.

Die Spiele sind eigene Minimal-Umsetzungen der jeweiligen Spielmechanik in 16x16 Pixeln
(generische Namen, abstrakte Grafik).

**Training der Spiele:** Jedes Spiel hat eine geskriptete Experten-Policy (Vorausberechnung /
Suche). Trainiert wird per **Imitation Learning mit DAgger** (Experte labelt auch die Zustände,
die das Netz selbst besucht). Das ist auf CPU um Größenordnungen günstiger als RL und
vergleicht die Architekturen fair. RL (z.B. PPO) ist für Phase 3 vorgesehen.

**Metriken / Normierung (0 = Zufall/Chance, 1 = perfekt bzw. Experte):**
* Klassifikation: `(acc - chance) / (1 - chance)`
* Bits: Exact-Match-Genauigkeit
* Spiele: `(Return - Random) / (Experte - Random)`

---

## 3. Architekturen (Phase 1)

Alle Modelle werden automatisch auf **~100k Parameter** skaliert (Breite per Suche angepasst).

| Name | Beschreibung | Gedächtnis |
|------|--------------|-----------|
| `mlp` | Klassisches NN, 2 Hidden-Layer | – |
| `cnn` | ConvNet, 2 Conv-Layer + FC | – |
| `cvnn` | Komplexwertiges MLP (komplexe Gewichte, modReLU) | – |
| `vit` | Attention über 4x4-Patches (Mini-Transformer) | – |
| `gru` | MLP-Encoder + GRU | ja |
| `attnmem` | Attention über die letzten 16 Frame-Embeddings | ja |
| `bus_{add,mul,gate,film}_{s,i}` | Bus-Netz, 4 Einspeise-Varianten, `s`=ein geteiltes Modul an jeder Stelle, `i`=individuelle Module | – |
| `subbus_i` | Bus, dessen Module intern wieder Sub-Busse sind | – |
| `layer_{s,i}` | Layer-Gitter: Eingänge LP/P/RP von oben, L/R lateral (vorheriger Takt) | ja (lateral) |
| `hier_{s,i}` | Hierarchisches Gitter nach Konzept (siehe unten) | ja (Rückkanäle) |

**Bus-Einspeisung** (Punkt A):
1. add: `B + f(B)`
2. mul: `B ⊙ f(B)` mit `f = 2·sigmoid(·)` (Filter um 1 initialisiert, sonst stirbt das Signal)
3. gate: `(1-G)⊙B + G⊙f(B)`
4. film: `γ(B)⊙B + β(B)`

**Hierarchie-Gitter** (Konzept aus NetResearch.md): Module auf einem Schachbrett-Gitter
(`(Zeile+Spalte)` gerade). Nachbarn von X an (r,c): P=(r-2,c), LP/RP=(r-1,c∓1),
LS/RS=(r+1,c∓1), S=(r+2,c).
* Eingänge: `IP ← P.OS`, `ILP ← LP.ORS`, `IRP ← RP.OLS` (abwärts, im selben Takt),
  `ILS ← LS.ORP` (aufwärts, aus dem vorherigen Takt → Rekurrenz/Gedächtnis).
* Ausgänge: `OLS, OS, ORS, ORP`.
* Zeilen werden von oben nach unten berechnet. Oberhalb des Gitters liegen zwei „virtuelle
  Zeilen“, die aus dem Input kommen (je Spalte ein Bildstreifen-Encoder). Unten werden die
  `OS`-Ausgänge der letzten beiden Zeilen (eine pro Spalte) zum Output zusammengefasst.
  Am Rand fehlende Ein-/Ausgänge bleiben ungenutzt (Null).

---

## 4. Training & Benchmark

* Optimierer Adam, Cosine-LR, Gradient-Clipping; gleiches Budget an Updates für alle Modelle.
* Supervised: Sequenzen der Länge T (Truncated BPTT); zustandslose Modelle werden effizient
  über `T×B` gebatcht.
* Spiele: DAgger (β von 1 → 0), Replay-Puffer von Trajektorien-Stücken, Evaluation über 32 Episoden.
* Runner: Matrix `Modelle × Tasks × Seeds`, parallel über Prozesse, Ergebnisse als JSONL.
* Report: `results/report.md` mit Tabellen (normierter Score, Rang, Parameter, Zeit) und
  Heatmap-Grafik.

---

## 5. Projektstruktur

```
netresearch/
  spec.py            # Konstanten, TaskSpec
  tasks/             # patterns.py, images.py, text.py, games/*.py, registry
  models/            # basic.py, bus.py, grid.py, registry (inkl. Parameter-Matching)
  train.py           # Trainings-/Eval-Schleifen (supervised + DAgger)
  bench.py           # CLI: Matrix ausführen
  report.py          # Auswertung + Grafiken
tests/               # Smoke-Tests: jedes Modell × jeder Task, Experten-Qualität
results/             # Ergebnisse
```

---

## 6. Phasen

* **Phase 1 (jetzt):** Plattform, 11 Tasks, 22 Modelle, Baseline-Lauf, Report.
* **Phase 2:** Mehr Szenarien (Pinball, Gedächtnis-Spiele ohne Spur, größere Raster 32x32),
  Ablationen (Tiefe, Anzahl Ticks im Hierarchie-Gitter, shared vs. individuell bei gleichem
  Compute statt gleichen Parametern), Multi-Task-Training (ein Netz für alle Tasks).
* **Phase 3:** Alternative Trainingsverfahren: RL (PPO), Evolutionäre Strategien,
  „Weight-Editing“ durch LLM (LLM liest/ändert Gewichte bzw. Modul-Code anhand von
  Fehleranalysen), Transfer zwischen Tasks.
