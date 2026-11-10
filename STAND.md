# Stand der Forschung

Kurzfassung, Stand 2026-11-10. Details: [`AGENDA.md`](AGENDA.md) (alle Themen mit Status),
[`PLAN_TRAINER.md`](PLAN_TRAINER.md) (Trainer-Netz, Messungen je Phase), [`results/report.md`](results/report.md)
(Benchmark-Tabellen).

## Ziel

Architekturen mit Gedächtnis, und ein Teacher-Netz, das einem trainierten Netz schnell Neues beibringt, ohne
Backprop und ohne das Alte zu vergessen. Alle Aufgaben laufen über dieselbe Schnittstelle (Bild 16×16×3 rein,
64 Ausgaben raus), alle Netze haben etwa 100k Parameter.

## Was wir wissen

**1. Architekturen (Benchmark, 3 Seeds)**
- Das Gitter mit geteilten Modulen (`layer_s`) ist insgesamt das beste Netz, vor `hier_s`, `layer_i` und `cnn`.
- Geteilte Gewichte gewinnen gegen individuelle vor allem durch die größere Modulbreite bei gleicher
  Parameterzahl.
- Grid-Welten scheitern am Bezugsrahmen, nicht an der Größe: Ist das Bild auf den Spieler zentriert, erreichen
  die Netze das Ziel (8×8: 98 %); bewegt sich der Spieler in einem festen Bild, fast nie.

**2. Gedächtnis**
- Ein Notizblock je Modul (`_sp4`: 4 Werte, geschrieben mit `m ← mult·m + add`) löst lange Verzögerungen
  (`delay` 1.00; ohne Notizblock 0.00) und kostet auf Aufgaben ohne Gedächtnisbedarf fast nichts.
- Ein Notizblock mit Inhaltsadressierung und 4 Köpfen (`layer_s_am4`) löst die ganze Gedächtnis-Batterie
  (recall, delay, crossmem, cycle_mem je 1.00, 1 Seed).

**3. Schnelles Nachlernen (Phasen A und B des Trainer-Plans)**
- Normales Nachtrainieren (Adam) vergisst die alte Aufgabe zu 50–99 %.
- Schnelle Gewichte auf dem eingefrorenen Netz, die nur im passenden Kontext wirken, vergessen nichts.
- Der Kontext lässt sich aus dem Fehlervergleich bestimmen (mit und ohne schnelle Gewichte), ohne Orakel.
- **Bibliothek:** mehrere Sätze schneller Gewichte, Auswahl per Fehlervergleich, Verdrängung des am längsten
  unbenutzten Satzes, Schutz gegen schädliches Teilen, Abspalten bei schleichender Veränderung.
  - 6 Aufgaben: 0.77 gegen Orakel 0.80. 12 Aufgaben: 0.68 gegen 0.72. Drift: 0.72 gegen 0.73.
  - Servo-Aufgabe (6 Geräte-Kalibrierungen): 0.63 gegen 0.65, ohne jede Anpassung der Bibliothek.
- **Lernregel zweiter Ordnung am Kopf** (rekursive kleinste Quadrate, ohne Backprop): hebt die Bibliothek auf
  servo von 0.63 auf 0.86, mit nichtlinearer Erweiterung auf 0.91; die sechs Zahlenfolgen-Aufgaben von 0.77
  auf 0.89, zwölf Aufgaben von 0.68 auf 0.85, Drift von 0.72 auf 0.86.
- **Offene Grenze:** Das *Verwalten* der Fähigkeiten ist fast gelöst, das *Lernen* nur am Kopf.
  - Die lokale Regel am Ausgabe-Kopf lernt nur, was linear aus dem Kopf-Eingang ablesbar ist (Umordnungen
    0.9; Vorzeichen, Versatz, Verstärkung 0.5; lineare Obergrenze 0.74, mit nichtlinearer Erweiterung 0.93).
  - Neue Rechenregeln lernt bisher keine Methode in 200 Updates, auch Adam nicht.
  - Die Regel für innere Schichten (DFA) hilft bei Kopier-Aufgaben, versagt aber auf der Servo-Aufgabe ganz.

**4. Netzgröße und Modulzahl (Nacht 2026-11-10, `scripts/size_summary.py`)**
- 25k → 100k Parameter bringt fast überall viel. 100k → 400k bringt noch etwas bei `count` und `push_easy`,
  nichts bei `grid_follow`, und kostet die dreifache Rechenzeit.
- Individuelle Module (`layer_i`) holen erst mit 400k auf.
- `vit` löst die Servo-Aufgabe schon mit 25k, scheitert aber in jeder Größe an Zahlenfolgen und Gedächtnis:
  eine Frage der Architektur, nicht der Größe.
- Die Spaltenzahl des Gitters wirkt stärker als die Größe: 16 statt 8 Spalten hebt `count` von 0.63 auf 0.84
  und `push_easy` von 0.56 auf 0.82, senkt aber `servo` von 0.99 auf 0.41. Die Zeilenzahl ist fast egal.

**5. Brücke zum Roboter-Projekt (rdf_thalamus_sml)**
- Fovea-Bilder des MuJoCo-Arms sind als Aufgaben eingehängt. „Wo ist der rote Würfel“ (`robot_gaze`) lösen die
  Netze (0.93–1.00), „Schritt von der Hand zum Würfel“ (`robot_reach`) noch nicht (um 0.10).
- `robot_reach` scheitert am Verrechnen: Hand (0.90) und Würfel (0.70) werden einzeln gelesen.
- Die Bibliothek lernt auf Roboter-Bildern Kalibrierungen des Blicks (0.91, Orakel 0.96), aber kein anderes
  Ziel (grün statt rot: 0.01). Das geht mit Schreiben nur am Kopf prinzipiell nicht.
- Mit einem **Ziel-Eingang** (Kommando = Farbe des gesuchten Würfels als Vektor) finden die Netze den
  kommandierten Würfel (cnn 0.72, Gitter-Netze ~0.5, ohne Eingang 0.04) und folgen dem Kommando. Mit
  gewürfelten Farben im Training verallgemeinert das Kommando auf einen nie gesehenen Farbton (cnn 0.31
  gegen 0.42 bei trainierten Farbtönen); die Gitter-Netze sind dabei noch schwach (0.14–0.18).
- Plan: Stufe b MuJoCo-Regelkreis mit Teacher als Experten, Stufe c Lieferquote als End-Benchmark; dazu die
  Servo-Stufe in Gelenkwinkeln (Fernziel physischer Arm, Abgleich über die Kamera).

## Wo wir stehen

- Erledigt: Benchmark-Plattform, Gedächtnis-Varianten, Phase A, Phase B bis zur Bibliothek mit Servo-Stufe 1.
- Als Nächstes: `robot_reach` verstehen, die Bibliothek auf den Roboter-Aufgaben, die Regel zweiter Ordnung
  für innere Schichten.
- Danach: Servo mit Verzögerung und Regelkreis, Wahrnehmung als eigene Stufe, Lehrplan ohne Freeze,
  einheitliches Port-Interface, dann der gelernte Teacher (Phasen D–F).
- Noch nicht begonnen: gelernter Teacher, Weltmodell, Reinforcement Learning.
