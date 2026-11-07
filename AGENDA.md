# Forschungsagenda

Hauptziel: **Architekturen mit Gedächtnis entwickeln**. Zwei gleichwertige Blickwinkel:
* **Spezialisten:** ein Netz pro Aufgabe. Welche Architektur kann was, wie schnell und wie robust?
* **Generalisten:** ein Netz für alle Aufgaben (Multi-Task). Was bleibt erhalten, was stört sich?

Priorität: **P1** = als Nächstes, **P2** = danach, **P3** = später / Forschungsrichtung.
Status: offen · läuft · erledigt.

## Gedächtnis

| Prio | Thema | Status | Notiz |
|---|---|---|---|
| P1 | **Scratchpad**: jedes Modul hat n Werte, liest sie als Input und schreibt sie mit `m ← mult·m + add` | erster Test erledigt | Trägt deutlich: mlp_sp64 auf cycle_mem 0.00 → 0.41, bus_add_s_sp64 0.00 → 0.99, Spiele +0.2–0.35. Ergebnisse: results/scratchpad.jsonl. Nur 1 Seed |
| P1 | Scratchpad-Größe: wie viele Werte pro Modul und global sind nötig? | teilweise | Spiele: 4 Werte reichen. cycle_mem (bis 64 Bit): Gesamtkapazität zählt; global teilen hilft stark (bus_s 16 lokal 0.47 → mit 4 global 0.90) |
| P1 | Scratchpad: geteilt vs. individuell (bus_add_i_sp16 0.96 vs. bus_add_s_sp16 0.47 auf cycle_mem) | offen | Gegenteil des Gitter-Befunds; mit Seeds prüfen |
| P1 | Scratchpad auf allen 15 Aufgaben und im Multi-Task-Lauf | offen | Schadet der Speicher bei Aufgaben ohne Gedächtnisbedarf? |
| P1 | Scratchpad für Layer- und Hierarchie-Gitter | erster Test erledigt | Globaler Teil = gemeinsamer Speicher, Schreibvorschläge gemittelt. cycle_mem: hier_s 0.78 → 0.99, hier_i 0.07 → 0.95, layer_i 0.89 → 0.99, lernt viel schneller. Spiele: kaum Änderung (Decke). 1 Seed |
| P2 | Rekurrenter Bus (Zustand von Takt zu Takt) | offen | Zusatz-Modell; die Modelle ohne Gedächtnis bleiben im Feld |
| P2 | Hierarchie-Gitter mit mehreren Ticks pro Frame | offen | Zusatz-Modell |
| P2 | Warum vergisst hier_s im Multi-Task-Lauf sein Gedächtnis (cycle_mem 0.78 → 0.01)? | offen | |
| P3 | Mehrstufiges Gedächtnis (schnell/langsam, Kurz-/Langzeit) | offen | Noch keine konkrete Idee; Bezug zu W_fast/W_slow in PLAN_TRAINER.md |

## Multi-Task

| Prio | Thema | Status | Notiz |
|---|---|---|---|
| P1 | **Aufgaben-Kennung als eigener Eingang** (nicht im Bild) | offen | Prüft, ob der Verlust bei cycle/count/numseq an der Mehrdeutigkeit liegt |
| P2 | Gradienten-Konflikt zwischen Aufgaben mit größeren Batches messen | offen | Bisher cos ≈ 0, aber verrauscht |
| P3 | Transfer: hilft eine gelernte Aufgabe beim Lernen einer neuen? | offen | Überschneidung mit dem Anpassungs-Benchmark |

## Spezialisten und Benchmark

| Prio | Thema | Status | Notiz |
|---|---|---|---|
| P1 | Mehrere Seeds (mindestens 3) für die Haupttabelle | offen | Auf dem zweiten PC über Nacht |
| P2 | crossing lernt nur cnn (0.77) | offen | Aufgabe oder Experte prüfen |
| P2 | Maze-Experte ist schwach | offen | |
| P2 | Geteilte Gewichte: warum hilft das Teilen im Gitter, obwohl die Gradienten der Positionen orthogonal sind? | offen | Daten in grad_summary.csv |
| P3 | Größere Szenarien (32x32), Pinball | offen | |
| P3 | Andere Lernverfahren: RL (PPO), ES | offen | ES auch für den Trainer |

## Trainer und Weltmodell (PLAN_TRAINER.md)

| Prio | Thema | Status | Notiz |
|---|---|---|---|
| P2 | Erster Test der Wiedererkennungs-Signale R: sagen sie vorher, was schnell lernbar ist? | offen | Mit vorhandenen Checkpoints, Abschnitt 4b |
| P2 | Anpassungs-Benchmark (Phase A) | offen | |
| P3 | Trainer-Netz per ES, schnelle/langsame Gewichte (Phasen B–F) | offen | |
| P3 | Weight-Editing durch ein LLM | offen | |

## Offene Grundsatzfragen

* Welches Basisnetz für den Trainer? Hängt von den Gedächtnis-Ergebnissen ab.
* Weltmodell: latente Vorhersage oder eigener Ausgabebereich für den nächsten Frame?
* Erster Anpassungsfall: „einen neuen Zyklus merken“?
* Wie viel Gedächtnis (Werte pro Modul, global) ist bei 100k Parametern und CPU-Budget sinnvoll?

## Infrastruktur

| Prio | Thema | Status | Notiz |
|---|---|---|---|
| P1 | Zweiter PC (16 Kerne, 32 GB) als Rechenknecht | offen | Kein Zugang von hier (Ping und alle Ports zu). Idee: Worker auf dem zweiten PC holt Aufträge per git pull und pusht die Ergebnisse |
| P2 | GPU-Test (stundenweise gemietet) für die rechenintensiven Modelle | offen | Messung (scripts/profile_run.py): Gitter (_s, _iw) und ViT sind rechengebunden und brauchen ~60 % der Benchmark-Zeit |
| P3 | Viele Netze gleichzeitig auf der GPU (vmap), für ES-Populationen | offen | |
