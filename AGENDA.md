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
| P1 | **Bezugsrahmen-Test** (2026-11-08): dieselben 8x8-Welten allozentrisch (grid_small, Welt fest im Bild) vs. egozentrisch (grid_small_ego, Bild auf den Spieler zentriert) | erledigt, Hypothese bestätigt | results/frame.jsonl, 13 Modelle x 3 Seeds. allo → ego: mlp 0.22→0.80, bus_add_s 0.21→0.85, gru 0.46→0.98, attnmem 0.49→0.96, hier_s 0.50→0.97, layer_i 0.51→0.99, cnn 0.72→0.98, layer_s 0.80→0.99, layer_s_sp4 0.87→0.99. CoordConv hilft nicht (cnn_coord 0.76 vs 0.72; grid_easy 0.47 vs 0.49). Also nicht das Finden der Position, sondern Beziehungen relativ zum Spieler (Nachbarfelder, Zielrichtung) sind der Engpass; ego macht die Politik translationsinvariant. Erklärt grid_easy und grid_scroll_easy (Spieler wandert im Bild). Zweite Meinung (agy): Deutung plausibel, eher 'relativer Rahmen' als nur 'Nachbar-Lookup'. Ideen: Zentrier-Modul (soft-argmax der Spielerposition + differenzierbares Verschieben = gelerntes Ego-Bild, als Vorstufe für jede Architektur), Probing (Nachbarinhalt/Zielrichtung allo vs ego), zufällige Weltverschiebung. |
| P2 | **RecencyMemory `_ar`** (2026-11-08): Codex-Review fand in AllocMemory Sättigung der Belegung (nach 16 Schreibvorgängen immer Zeile 0) und doppeltes beta; `_ar` schreibt in die am längsten unbeschriebene Zeile | getestet, kein Vorteil | Seed 0: recall/delay/cycle_mem wie `_am` (ar4 recall 0.79–0.93 etwas schlechter), crossmem 0.05 (layer_s_am4 dagegen 1.00 in allen 3 Seeds), grid_follow_easy 0.80–0.92 (am 0.75–0.86), grid_scroll_easy ≤ 0.08 bei beiden. Sieb A1: layer_s_ar besteht, layer_s_ar4/hier_s_ar/hier_s_ar4 scheitern an bricks. Offen: warum gerade das 'fehlerhafte' layer_s_am4 crossmem löst (Festhalten von Zeile 0 als stabiler Speicher?). |
| P2 | crossing lernt nur cnn (0.77) | offen | Aufgabe oder Experte prüfen |
| P2 | Maze-Experte ist schwach | offen | |
| P2 | Geteilte Gewichte: warum hilft das Teilen im Gitter, obwohl die Gradienten der Positionen orthogonal sind? | offen | Daten in grad_summary.csv |
| P3 | Größere Szenarien (32x32), Pinball | offen | |
| P3 | Andere Lernverfahren: RL (PPO), ES | offen | ES auch für den Trainer |

## Trainer und Weltmodell (PLAN_TRAINER.md)

| Prio | Thema | Status | Notiz |
|---|---|---|---|
| P2 | Erster Test der Wiedererkennungs-Signale R: sagen sie vorher, was schnell lernbar ist? | offen | Mit vorhandenen Checkpoints, Abschnitt 4b |
| P1 | Anpassungs-Benchmark (Phase A) | erledigt 2026-11-09 | fixcycle: von null an schneller als vortrainiert; Adam vergisst 0.5–0.9, Replay 0.1. Neue Rechenregeln lernt keine Methode (Leiter-Ende). Details PLAN_TRAINER Phase A |
| P2 | Feste Regeln T1, T2 auf schnellen Gewichten (Phase B, erster Teil) | erledigt 2026-11-09 | kein k-shot (≤ 0.13 nach 5 Updates); Delta-Regel am Kopf schneller als Adam; Vergessen hängt am Wirkungsbereich: mit Ähnlichkeits-Gate 0.00 (PLAN_TRAINER Phase B) |
| P2 | Gelerntes Kontext-Gate für schnelle Gewichte (novel / lda) | erledigt 2026-11-09 | Vergessen überall nahe 0, Gates generalisieren auf neue Test-Eingaben (kNN nicht); die Rechenregeln lernt der Kopf allein nicht (PLAN_TRAINER Phase B) |
| P2 | Gegatete schnelle Gewichte im Inneren (fc1 / fc2) + Adaptionsfall mittlerer Schwierigkeit | erledigt 2026-11-09 | Mittlere Fälle xormask / prev / plus1 / cycle2. Eingabe-Gates versagen bei gleichen Eingaben, mit Orakel-Kontext Vergessen 0. Regel hängt am Wirkungsort: Delta am Kopf für Ausgangs-Änderungen, DFA im Inneren lernt prev ohne Backprop (PLAN_TRAINER Phase B) |
| P2 | Kontext aus Fehlervergleich statt Orakel (erste Telemetrie) | erledigt 2026-11-09 | fast Orakel-Niveau, 2–3 Fehl-Batches je Wechsel; Lernen nur bei eingeschaltetem Kontext (err_c) nötig; ohne Gate zerstören DFA / grad die Basis (PLAN_TRAINER Phase B) |
| P2 | Mehrere Sätze schneller Gewichte, Auswahl per Fehlervergleich | erledigt 2026-11-09 | fast Orakel-Niveau beim zweiten Besuch, Auswahl 90–95 % richtig; ein Satz allein verliert frühere Aufgaben; Kompetenz-Kriterium braucht absolute Untergrenze (PLAN_TRAINER Phase B) |
| P2 | Bibliothek unter Druck: mehr Aufgaben als Plätze, Regel je Satz | als Nächstes | Verdrängung, geteilte Sätze für verwandte Aufgaben; delta_head / DFA je Satz per Modulation |
| P2 | Port-Interface (Telemetrie / Modulation / Freeze) | offen | Telemetrie L0 / L1 / Überraschung steht; Modulation wählt Wirkungsort und Regel |
| P2 | Gemischte Regel: delta_head + dfa gemeinsam, gewichtet | offen | DFA-Schrittweite für plus1 abstimmen (bricht bei η = 3 ein) |
| P3 | Zyklus-Trennung kanonisch (minimale Periode) | offen, bekannt | (0,2) und (0,2,0,2) liegen getrennt; selten, betrifft auch die Basisaufgabe cycle; Änderung bricht Vergleichbarkeit |
| P2 | T3 Freeze & Route als Lehrplan-Test über die Sieb-Stufen (Phase C) | offen | braucht individuelle Module oder Fähigkeiten-Bibliothek |
| P3 | Gelernter Teacher per ES (Phasen D–F) | offen | |
| P3 | T4 State-Critic: Langeweile, Lernfortschritt, Gefahr, Muster (Phase G) | offen | setzt RL-Schleife voraus |
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
