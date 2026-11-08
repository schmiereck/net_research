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
| P1 | Scratchpad: geteilt vs. individuell (bus) | geklärt (3 Seeds) | cycle_mem: bus_add_i_sp16 0.96 vs. bus_add_s_sp16 0.50; bei 64 Werten holt das geteilte auf (0.99). Individuelle Positionen nutzen ihren Speicher getrennt besser |
| P1 | Scratchpad auf allen 15 Aufgaben (3 Seeds, Rechen-PC) | erledigt | Gedächtnis-Aufgaben (cycle_mem, paddle_mem, bricks_mem): mlp 0.41 → 0.63–0.77, bus_add_s 0.44 → 0.67–0.95, bus_add_i 0.48 → 0.93, hier_s 0.87 → 0.93–0.96, hier_i 0.63 → 0.87. Aufgaben ohne Gedächtnisbedarf: kaum Kosten (−0.00 bis −0.04). layer_s hat schon eigenes Gedächtnis: kein Gewinn (0.80 → 0.79–0.80). **Ausnahme layer_i_sp4: instabil in Spielen** (bricks 0.86/0.28/0.17 je Seed, Gesamt 0.71 → 0.64) |
| P1 | Scratchpad für Layer- und Hierarchie-Gitter | erster Test erledigt | Globaler Teil = gemeinsamer Speicher, Schreibvorschläge gemittelt. cycle_mem: hier_s 0.78 → 0.99, hier_i 0.07 → 0.95, layer_i 0.89 → 0.99, lernt viel schneller. Spiele: kaum Änderung (Decke). 1 Seed |
| P1 | Fremde Scratchpads lesen statt gemittelt global schreiben: 8 Nachbarn (`_sp4n`) oder per gelernter Adresse, 4 Abfragen (`_sp4a`) | erster Test: unentschieden | Die drei Gedächtnis-Aufgaben unterscheiden die Varianten nicht (cycle_mem schon mit eigenem Speicher ~0.99). Adresse kostet +40–70 % Zeit. Braucht schwerere Gedächtnis-Aufgaben |
| P1 | Schwerere Gedächtnis-Aufgaben: assoziativer Abruf (Schlüssel→Wert), lange Verzögerung, Information wechselt die Bildregion | erledigt | `recall`, `delay`, `crossmem` (tasks/memory.py). Erster Lauf (18 Modelle, 1 Seed): delay lösen nur Gitter mit Scratchpad (1.00); recall nur attnmem (1.00); crossmem niemand (attnmem 0.37). Alle anderen speichern eine Überlagerung (Bit-Genauigkeit 0.69 = Mehrheit der Wörter) |
| P1 | Scratchpad mit Inhaltsadressierung (Schlüssel/Wert) | **gelöst (1 Seed)**: `layer_s_am4` (4 Köpfe) löst die ganze Batterie: recall, delay, crossmem, cycle_mem je 1.00. `layer_s_am`/`hier_s_am`: recall+delay 1.00, crossmem 0.05 (1 Kopf: 4 gleichzeitige Wörter passen nicht in eine Zeile). hier_s_am4 crossmem nur 0.14. layer_i_am recall 0.06 (schmal, Breite 14). Kosten: ~3× Trainingszeit von layer_s auf den Gedächtnis-Aufgaben. Nächster Schritt: alle Aufgaben, 3 Seeds | `_kv`: ein globales Schlüsselnetz wählt per Softmax die Zeile (16 × 4 Werte pro Modul). **Kollabiert**: alle 16 Schlüssel landen auf derselben Zeile, recall 0.05 (kv4: 2 Zeilen, 0.23). `_am` (zweiter Entwurf): Schreiben in die am wenigsten belegte Zeile (gelernte Schreibstärke), dort wird auch ein Schlüsselvektor abgelegt; Lesen per Skalarprodukt Abfrage·Schlüssel über die belegten Zeilen; Werte weiter verteilt über die Module (mult/add). Erstes Modell im Feld, das recall UND delay löst (attnmem: recall 1.00, delay 0.34; Gitter-Scratchpad: delay 1.00, recall 0.05). Schwäche beider: Schlüssel nur aus dem aktuellen Bild |
| P2 | crossmem: ohne Verzögerung lösbar? (Auswahl per Zeiger vs. Gedächtnis trennen) | offen | |
| P2 | layer_i_sp4 instabil in Spielen: warum? (schmale individuelle Module + Speicher + DAgger) | offen | |
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
| P1 | Mehrere Seeds (mindestens 3) für die Haupttabelle | erledigt | Rangfolge stabil, Streuung des Gesamtwerts ±0.01–0.02 |
| P1 | **Grid-World** (Idee 2026-11-07, Variante A) | erster Lauf (14 Modelle, 3 Seeds): zu schwer | `grid` (16×16 voll sichtbar, Start/Ziel/Wände/Gruben), `grid_follow` (32×32, Sicht auf den Spieler zentriert), `grid_scroll` (Kamera mit Totzone), `push` (Kiste aufs Ziel schieben, exakter Experte per Rückwärtssuche). Erkundender Experte kennt nur, was er gesehen hat. Trainingsabschnitte 32 statt 16 Schritte. Offen: push mit 2 Kisten, push in der Scroll-Welt. **Ergebnis**: alle Modelle 0.12–0.30 auf grid, 0.43–0.69 auf grid_follow (vor allem: nicht in Gruben fallen), 0.20–0.40 auf grid_scroll, push 0.00. Trainingsfehler klein (0.3–0.4), aber die Episoden laufen in die Zeitgrenze: die Netze lernen etwa die lokale Gier-Regel (Schritt Richtung Ziel) und bleiben in Sackgassen hängen; die Gier-Regel selbst erreicht das Ziel nur in 16 % (stimmt aber in 79 % der Schritte mit dem Experten überein). grid misst damit globale Wegplanung, nicht Gedächtnis -> Kandidat für den Test mehrerer Ticks pro Frame. Vorschlag: Gedächtnis-Varianten mit weniger Wänden, push vereinfachen |
| P1 | **Sieb** (Idee 2026-11-08): Stufen, durch die eine Architektur muss, um zu den schweren Tests zu kommen. Pfad A ohne Gedächtnis A1→A2→A3, Pfad M Gedächtnis A1→M1→M2→M3 | gebaut, erster Lauf fertig (12 Modelle, Seed 0) | netresearch/sieve.py (`status`, `next`, `run`); bestanden = jede Aufgabe ≥ 0.75. A1 Grundlagen (shapes, digits, paddle, bricks), A2 Steuern (+grid_easy, push_easy), A3 Planen (grid, push), M1 Halten (cycle_mem, paddle_mem, bricks_mem, delay), M2 Binden/Erkunden (recall, crossmem, grid_*_easy), M3 Erkunden schwer (grid_follow, grid_scroll). Grid-World jetzt in leicht (5 % Wände) und schwer; push bleibt das schwere Ziel, push_easy als Vorstufe. Offen: Schwelle 0.75 prüfen, Seeds | Ergebnis 1. Lauf: A1 11/12 (attnmem bricks 0.71); A2 0/11, beste cnn 0.66 (grid_easy 0.44, push_easy 0.71), layer_s 0.58 (crossing 0.43, grid_easy 0.17); M1 2/11 (nur layer_s_sp4, hier_s_sp4; alle anderen scheitern an delay); M2 0/2: grid_follow_easy gelingt (hier_s_sp4 0.95, layer_s_sp4 0.80), aber grid_scroll_easy 0.03/0.05 und recall/crossmem 0.05. Befund: grid_easy (voll sichtbar, Spieler wandert im Bild) ist schwerer als grid_follow_easy (Spieler fest in der Mitte) → Engpass ist das Lokalisieren der eigenen Position im Bild, nicht das Gedächtnis; dasselbe erklärt grid_scroll_easy. Nächste Schritte: _am-Modelle durchs Sieb (M2 recall/crossmem), Positionslesen (Koordinatenkanäle/CoordConv?) als Architektur-Idee. Abbildung: python -m netresearch.sieve_plot → results/sieve.png/.svg.
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
| P1 | Zweiter PC (16 Kerne, 32 GB) als Rechenknecht | erledigt | netresearch.worker + netresearch.jobs, Austausch über OneDrive (WORKER.md) |
| P2 | GPU-Test (stundenweise gemietet) für die rechenintensiven Modelle | offen | Messung (scripts/profile_run.py): Gitter (_s, _iw) und ViT sind rechengebunden und brauchen ~60 % der Benchmark-Zeit |
| P3 | Viele Netze gleichzeitig auf der GPU (vmap), für ES-Populationen | offen | |
