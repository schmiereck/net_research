# Labor-Logbuch

Chronologisches Protokoll der Forschung in NetResearch: was gefragt wurde, was gemacht wurde, was herauskam und
was wir daraus geschlossen haben. Auch Irrwege und verworfene Hypothesen stehen hier, damit der Weg zu den
Ergebnissen nachvollziehbar bleibt (Ziel: Grundlage für eine spätere Veröffentlichung).

Abgrenzung zu den anderen Dokumenten:

| Dokument | Inhalt |
|---|---|
| `LOGBUCH.md` (dieses) | der Weg: Einträge in zeitlicher Reihenfolge, nachträglich nicht umgeschrieben |
| [`STAND.md`](STAND.md) | der aktuelle Wissensstand, kurz |
| [`AGENDA.md`](AGENDA.md) | alle Themen mit Status und Priorität, Kandidaten-Liste |
| [`PLAN_TRAINER.md`](PLAN_TRAINER.md) | Plan zum Trainer-Netz und die ausführlichen Messtabellen je Phase |
| [`results/report.md`](results/report.md) | Benchmark-Tabellen |

**Regeln für Einträge**

- Ein Eintrag je Untersuchung: Frage, Vorgehen, Ergebnis, Schluss, Belege (Ergebnis-Datei, Commit).
- Alte Einträge werden nicht geändert. Stellt sich etwas später als falsch heraus, bekommt der alte Eintrag
  einen Verweis „→ korrigiert in …“, und die Korrektur steht im neuen Eintrag.
- Zahlen nennen immer Seeds und Updates. Abstimm-Seeds sind 5 und 6, Test-Seeds 0–2. Ergebnisse nur auf den
  Abstimm-Seeds gelten als vorläufig.
- Prognosen werden VOR dem Lauf eingetragen und danach geprüft.

**Feste Versuchsbedingungen** (soweit nicht anders vermerkt)

- Einheitliche Schnittstelle: Bild 16×16×3 rein, 64 Ausgaben in festen Bereichen (Motor, Klasse, Bits, Symbol).
- Alle Netze etwa 100k Parameter; Größen-Varianten tragen den Zusatz `@25k` / `@400k`.
- Score: 0 = Zufall, 1 = gelöst.
- Rechner: ein lokaler PC und ein Rechen-PC („Worker“), der Aufträge per Commit aus dem Repository holt.
- Die Aufgaben bilden eine Leiter von leicht bis unlösbar; es gibt keine aufgabenspezifischen Reparaturen.

**Namen der wichtigsten Netze**

| Name | Netz |
|---|---|
| `mlp`, `cnn`, `vit`, `gru`, `lstm` | Standard-Netze als Bezug |
| `attnmem` | Attention-Speicher über frühere Bilder |
| `vitmem` | vit je Bild, dann Aufmerksamkeit über die letzten 16 Bilder |
| `esn` | Reservoir: festes Zufallsnetz, nur die Auslese lernt |
| `layer_s` / `layer_i` | Gitter aus Modulen in Schichten, geteilte / individuelle Gewichte |
| `hier_s` | Hierarchie-Gitter |
| `_sp4`, `_am4`, `_ar4` | Gitter mit Notizblock je Modul / mit Inhaltsadressierung / mit Überschreiben nach Alter |
| `_c16`, `_r8` … | Gitter mit anderer Spalten- / Zeilenzahl |
| `+cmd`, `+cell`, `+ref`, `+retN` | Kommando-Eingang / je Zelle / Adresse aus einem Bild / Vorschalt-Stufe für 32×32 |

---

## 2026-11-06 — Benchmark-Plattform

- **Frage:** Wie vergleicht man sehr verschiedene Architekturen fair?
- **Gemacht:** Plattform mit einheitlicher Schnittstelle, 15 Aufgaben (Muster, Zählen, Zahlenfolgen,
  Gedächtnis-Spiele), Standard-Netze und modulare Netze (Bus, Schicht-Gitter, Hierarchie), GUI.
- **Belege:** f60104f, 46d462e.

## 2026-11-07 — Architektur-Vergleich, Gewichte teilen, Multi-Task

- **Frage:** Welche Architektur ist bei 100k Parametern insgesamt am besten? Hilft es, Gewichte zwischen
  Modulen zu teilen?
- **Ergebnis (3 Seeds):** Das Gitter mit geteilten Modulen (`layer_s`) liegt insgesamt vorn, vor `hier_s`,
  `layer_i` und `cnn`. Geteilte Gewichte gewinnen vor allem, weil die Module bei gleicher Parameterzahl
  breiter sind.
- **Multi-Task** (ein Netz, alle 15 Aufgaben): gerechnet für 11 Netze; `hier_s` verliert dabei sein Gedächtnis
  (`cycle_mem` 0.78 → 0.01), Ursache offen.
- **Belege:** 8aa392f, d096cb3, 46a2676; `results/report.md`.

## 2026-11-07 / 08 — Gedächtnis-Varianten

- **Frage:** Welcher Speicher im Modul löst welche Gedächtnis-Aufgabe?
- **Gemacht:** Notizblock je Modul (`_sp`, Schreiben mit `m ← mult·m + add`), Lesen von Nachbarn oder per
  gelernter Adresse, Schlüssel-Wert-Speicher (`_kv`), zuweisender Speicher (`_am`), Überschreiben nach Alter
  (`_ar`); Gedächtnis-Batterie (recall, delay, crossmem, cycle_mem).
- **Ergebnis:** Der Notizblock löst lange Verzögerungen (`delay` 1.00 gegen 0.00) und kostet sonst fast
  nichts. `_kv` bricht zusammen. `layer_s_am4` löst die ganze Batterie (1 Seed). `_ar` bringt keinen Vorteil
  gegenüber `_am`.
- **Review:** Codex fand in `_am` eine Sättigung der Belegung und ein doppelt angewandtes beta; daraus entstand
  `_ar`.
- **Belege:** ac39286 … 798d712, 2a7ad7b, 75d85ef.

## 2026-11-08 — Grid-Welten, Sieb, Bezugsrahmen

- **Frage:** Können die Netze in kleinen Welten zu einem Ziel laufen?
- **Ergebnis 1:** Erster Lauf (14 Netze, 3 Seeds): zu schwer; die Aufgaben prüfen Planen, nicht Gedächtnis.
- **Gemacht:** „Sieb“ aus gestuften Aufgaben (Pfad A ohne, Pfad M mit Gedächtnis), bestanden ab 0.75;
  später auf 50 Architekturen erweitert.
- **Bezugsrahmen-Test:** dieselben 8×8-Welten mit festem Bild und mit auf den Spieler zentriertem Bild.
- **Ergebnis 2:** Die Welten scheitern am Bezugsrahmen, nicht an der Größe. Zentriert erreichen alle Netze
  0.80–0.99 (z. B. mlp 0.22 → 0.80, gru 0.46 → 0.98); CoordConv hilft nicht.
- **Belege:** 0475534, b86c362, 5fd85f1, 90b45fe, f52da2c; `results/frame.jsonl`.

## 2026-11-09 — Schnelles Nachlernen (Phasen A und B des Trainer-Plans)

- **Frage:** Wie lernt ein trainiertes Netz schnell Neues, ohne Backprop und ohne Altes zu vergessen?
- **Phase A:** Nachtrainieren mit Adam vergisst die alte Aufgabe zu 50–99 %; neue Rechenregeln lernt keine
  Methode in 200 Updates.
- **Phase B:** Schnelle Gewichte auf dem eingefrorenen Netz, die nur im passenden Kontext wirken, vergessen
  nichts. Der Kontext lässt sich aus dem Fehlervergleich (mit / ohne schnelle Gewichte) bestimmen, ohne Orakel.
- **Bibliothek:** mehrere Sätze schneller Gewichte, Auswahl per Fehlervergleich, Verdrängung, Schutz gegen
  schädliches Teilen, Abspalten bei Drift. 6 Aufgaben 0.77 (Orakel 0.80), 12 Aufgaben 0.68 (0.72), Drift 0.72
  (0.73).
- **Irrwege:** Eingabe-Gates versagen bei gleichen Eingaben; ein Probe-Update trennt verwandte Aufgaben nicht;
  der erste Konsistenztest verwarf schwache Sätze auf verrauschten Batches (behoben mit einer Rauschgrenze).
- **Belege:** 76a534b … ecf0e0b; `results/library.jsonl`; PLAN_TRAINER Phasen A und B.

## 2026-11-10 — Servo, Lernregel zweiter Ordnung, Größe und Modulzahl

- **Servo-Aufgabe** (6 Geräte-Kalibrierungen): Bibliothek 0.63 gegen Orakel 0.65.
- **Lernregel zweiter Ordnung am Kopf** (rekursive kleinste Quadrate): servo 0.63 → 0.86, mit nichtlinearer
  Erweiterung 0.91; sechs Aufgaben 0.77 → 0.89, zwölf 0.68 → 0.85, Drift 0.72 → 0.86 (Test-Seeds).
- **Grenze:** Das Verwalten der Fähigkeiten ist fast gelöst, das Lernen nur am Kopf. Die Regel für innere
  Schichten (DFA) versagt auf servo.
- **Größe:** 25k → 100k bringt fast überall viel, 100k → 400k wenig. `vit` scheitert in jeder Größe an
  Zahlenfolgen und Gedächtnis. Die Spaltenzahl des Gitters wirkt stärker als die Größe (16 Spalten: `count`
  0.63 → 0.84, `servo` 0.99 → 0.41).
- **Nachmessung mit vierfacher Trainingszeit:** Die Spaltenzahl ändert vor allem das Lerntempo, je Aufgabe
  verschieden; kein allgemeines Wahrnehmungs-Defizit der Gitter.
- **Belege:** 3cb8799, c2c5fd0, 182f4b1, f5ce85c, d294278; `results/grid_slow.jsonl`.

## 2026-11-10 — Brücke zum Roboter-Projekt (Stufe a)

- **Gemacht:** Fovea-Bilder des MuJoCo-Arms aus `rdf_thalamus_sml` als Aufgaben: `robot_gaze` (Blick auf den
  roten Würfel), `robot_reach` (Schritt von der Hand zum Würfel).
- **Ergebnis:** `robot_gaze` 0.93–1.00; `robot_reach` um 0.10.
- **Erste Diagnose:** `robot_reach` scheitert am Verrechnen, Hand und Würfel werden einzeln gelesen.
  → präzisiert am 2026-11-12 (mit Hilfsaufgabe begrenzt das Lesen des Würfels).
- **Kommando-Eingang** (`+cmd`, `robot_findc`): Mit der Farbe des gesuchten Würfels als Vektor finden die
  Netze ihn (ohne Eingang 0.04); verallgemeinert auf einen nie gesehenen Farbton. Mit vierfacher Trainingszeit
  vit 0.64, cnn 0.62, `layer_s` 0.56. Kommando je Zelle (`+cell`) bringt nichts.
- **Adresse aus einem Bild** (`+ref`): so gut wie die vorgegebene Farbe, verallgemeinert besser.
- **Negativ:** Suche nach Form in einem einzigen Blick (`robot_finds`) scheitert (0.05–0.09), obwohl die
  Adresse die Form trägt.
- **Belege:** 5ea8274, aeeae44, a36bb6a, d6a50f8, eb37ce8, 030b512.

## 2026-11-10 / 11 — Anschauen und Vergleichen

- **Idee:** Statt in einem Blick zu suchen, erst den gesuchten Körper zeigen, dann nacheinander die drei
  Kandidaten anschauen (`robot_lookmem`).
- **Ergebnis:** `attnmem` wählt in 82 % den richtigen Körper (nie gesehenes Y: 56 %), `gru` 68 %; Gitter und
  `vit` 0.00. Der Vergleich über die Adresse in einem Blick (`robot_look`) gelingt niemandem (0.50).
- **Synthetische Gegenstücke:** `match` (Muster am festen Ort) lösen alle Gitter mit 1.00; `match_shift`
  (wanderndes Muster) 0.00; `gru` / `attnmem` 0.42–0.44.
- **Fehler unterwegs:** Ein verschobenes Wort ohne Markierung war mehrdeutig; behoben mit einer Linie unter
  jedem Wort. Die Zahlen blieben gleich.
- **Belege:** 5fabb19, 6636d20, 3f6b443; `results/match.jsonl`.

## 2026-11-11 — Zerlegung und eine verworfene Hypothese

- **Hypothese:** Den Gittern fehlt eine ortsunabhängige Beschreibung; ein Lesekopf über die Spalten könnte
  helfen.
- **Einwand des Nutzers:** keine Lösung um das Unvermögen eines Netzes herum bauen.
- **Gemacht:** `match_shift` zerlegt in Lesen (`read_shift`), Merken (`keep_shift`) und Vergleichen in einem
  Bild (`same_fixed`, `same_shift`).
- **Ergebnis:** Die Hypothese ist widerlegt: Gitter lesen und merken ein wanderndes Wort mit 1.00. Gebrochen
  ist `same_shift`, und zwar bei allen Architekturen. Mit 24000 Updates lösen es die Gitter am besten
  (`hier_s` 0.96, `layer_s` 0.89, `gru` 0.71, `vit` / `attnmem` höchstens 0.13).
- **Schluss:** Die Teilleistungen sind da, das Zusammensetzen wird nur sehr spät gefunden. Lesekopf verworfen.
- **Belege:** 80eef23, 1febd88; `results/match_parts.jsonl`.

## 2026-11-11 / 12 — Lehrplan

- **Frage:** Öffnet eine Vorstufe mit den Teilaufgaben die zusammengesetzte Aufgabe?
- **Ergebnis (Seeds 0–2, 8 Netze, gleiche Gesamtzahl Updates):** `match_shift` allein 0.00 (Gitter) bzw.
  0.43–0.57 (`attnmem`, `gru`); mit Vorstufe `keep_shift+same_shift` 0.97–1.00. Für `match_shift` reichen 3000
  Updates nur Merken. Lesen als Nebenaufgabe hebt `cnn` auf `same_shift` von 0.00 auf 1.00.
- **Übertrag auf den Roboter:** Mit derselben synthetischen Vorstufe wählt `hier_s` auf `robot_lookmem` in
  86 % den richtigen Körper (Y 60 %) und liegt vor `attnmem` (81 % / 51 % mit derselben Vorstufe).
- **Inhalt der Vorstufe (Seeds 5 / 6):** nur Merken 0.00, nur Vergleichen höchstens 0.32, beides zusammen
  0.56–0.85; 6000 Updates reichen.
- **Schluss:** Lange Plateaus sind fehlende Zwischenziele. Das ist die Rolle, die ein Teacher übernehmen soll.
- **Belege:** 7a7597a, 8601cce, 4faedc8, f65c260; `results/curriculum.jsonl`.

## 2026-11-12 — Zwischenziele auf den Roboter-Aufgaben

- **Gemacht:** Hilfsaufgaben, die die Zwischengrößen als Ausgabe verlangen (`robot_reach_parts`: Zelle der
  Hand und des Würfels; `robot_finds_parts`), Auswertung je Teil.
- **Ergebnis `robot_reach` (Seeds 5 / 6):** vit 0.12 → 0.40, `layer_s` 0.11 → 0.19.
- **Ergebnis `robot_finds`:** negativ. Die gezeigte Form wird gelesen (0.96), die Suchszene nicht (Positionen
  0.10–0.21, Formen 0.22–0.32 bei Zufall 0.2).
- **Schluss:** Bei der Form-Suche ist die Wahrnehmung in einem Blick der Engpass; das stützt „nacheinander
  anschauen“.
- **Belege:** dee5236, 7c309bc, 2a2d656; `results/curriculum_parts.jsonl`.

## 2026-11-12 — Projektziel: Pipeline mit Prognose

- **Ziel (Nutzer):** Viele Architekturen auf kleinen Aufgaben vergleichen, nur die interessanten auf die
  Roboter-Aufgaben schicken; herausfinden, welche kleine Aufgabe welche Roboter-Aufgabe vorhersagt.
- **Gemacht:** `scripts/forecast.py` (Rangübereinstimmung rho über die Architekturen, die beides gerechnet
  haben).
- **Erste Tabelle:** `match_shift` → `robot_lookmem` +0.88 (n = 7, nachträglich gebaut); `push_easy` →
  `robot_findc` +0.85 (n = 9); `servo` → `robot_gaze` nur als Sieb; die alte Gedächtnis-Batterie sagt
  `robot_lookmem` nicht vorher.
- **Belege:** 4ccc39b; STAND.md Abschnitt „Prognose“.

## 2026-11-12 — `robot_reach`: Daten, Größe, Lesen

- **Frage:** Was begrenzt „Hand zum Würfel“, wenn die Hilfsaufgabe das Verrechnen öffnet?
- **Ergebnis (Seeds 5 / 6, 24000 Updates je Aufgabe):** 48000 statt 12000 Bilder heben jedes Netz (vit mit
  Hilfsaufgabe 0.42 → 0.59, cnn 0.14 → 0.42, `layer_s` 0.20 → 0.45). 400k statt 100k Parameter bringen nur
  +0.03 bis +0.08 (vit@400k 0.64). Beim vit liegt die Hauptaufgabe fast auf der Lesequote (0.59 / 0.61). Die
  Hand wird zu 0.78–0.92 gelesen, der Würfel zu 0.54–0.72.
- **Schluss:** Engpass sind Datenmenge und das Lesen des Würfels, nicht die Netzgröße. Vorläufig; Bestätigung
  auf Seeds 0–2 läuft.
- **Belege:** ecb2920; `results/reach_read.jsonl`.

## 2026-11-12 — Auflösung der Fovea

- **Anlass (Nutzer):** Im Fovea-Bild wirkt die Auflösung zu gering, um einen Körper an der Form zu erkennen;
  Vorschlag: doppelte Auflösung mit ein bis drei Schichten davor.
- **Gemacht:** `robot_shape` (Blick auf einem von drei gleichfarbigen Körpern, 5 Formen) in vier Abtastungen:
  Standard, Zoom 2×, Zoom 4×, 32×32 über dasselbe Blickfeld mit Vorschalt-Stufe `+ret0..3`.
- **Ergebnis (Seeds 0–2, 6000 Updates):** Standard 0.93–0.99; Zoom 2× +0.00 bis +0.03; Zoom 4× eher
  schlechter; 32×32 mit 2–3 Schichten 0.98–1.00; mit einer Schicht schlechter als bloßes Mitteln.
- **Schluss:** Liegt der Blick auf dem Körper, begrenzt die Auflösung das Erkennen nicht. Die Vorschalt-Stufe
  funktioniert, der Gewinn ist klein. Offen: Körper am Rand des Blickfelds; Fläche statt Umriss.
- **Belege:** 81c70e0, ecb2920; `results/resolution.jsonl`.

## 2026-11-12 — Prognose-Lücken und eine gescheiterte blinde Prognose

- **Prognose vorab:** Wenn `push_easy` `robot_findc` vorhersagt, muss vit auf `push_easy` gut sein.
- **Ergebnis:** vit `push_easy` 0.11 bei `robot_findc` 0.65: Prognose gescheitert. rho fällt auf +0.70
  (n = 14). `attnmem` löst `servo` (1.00), aber nicht `robot_gaze` (0.51): Das Sieb gilt nur in einer Richtung.
- **Belege:** ecb2920; `results/gap.jsonl`.

## 2026-11-12 — Vergleicher-Zelle (negativ)

- **Hypothese:** Dem Gitter fehlt zum Vergleichen eine multiplikative Verknüpfung von Eingabe und Gehaltenem.
- **Gemacht:** Zelle mit Produkten (`layer_s_x`, `_sp4x`, `_am4x`), gleiche Parameterzahl.
- **Ergebnis (Seeds 5 / 6, 12000 Updates):** `match_shift` 0.00 mit und ohne; `same_shift` nicht besser (ohne
  Speicher 0.10 / 0.03 gegen 0.83 / 0.00).
- **Schluss:** Das Plateau liegt nicht an fehlender Multiplikation. Nicht auf die Test-Seeds genommen.
- **Belege:** f643156, 9f3ea79; `results/comparator.jsonl`.

## 2026-11-12 — Drei neue Netze mit blinder Prognose

- **Anlass (Nutzer):** Architektur heißt sowohl das Innere eines Moduls als auch die Verschaltung der Module;
  die Kandidaten-Liste war zu sehr auf Bilderkennung ausgerichtet (Tabelle der Ebenen in AGENDA.md).
- **Gemacht:** `lstm`, `vitmem`, `esn` durch die kleine Batterie (Seeds 0–2), Prognose notiert (ebeba6e), dann
  die Roboter-Aufgaben.
- **Ergebnis:**

  | Netz | `match_shift` / `push_easy` / `servo` | `robot_lookmem` | `robot_findc` | `robot_gaze` | `robot_reach` |
  |---|---|---|---|---|---|
  | vitmem | 0.50 / 0.61 / 1.00 | 0.87 (Prognose 0.4–0.5) | 0.61 (0.5–0.6) | 0.97 (> 0.9) | 0.10 |
  | lstm | 0.60 / 0.09 / 0.61 | 0.21 (um 0.5) | 0.09 (um 0.1) | 0.40 (0.4–0.5) | 0.04 |
  | esn | 0.00 / −0.03 / 0.01 | 0.00 (0.00) | 0.03 (um 0.1) | 0.09 (< 0.4) | 0.02 |

- **Schluss:** Die Reihenfolge der drei Netze stimmte auf allen drei Roboter-Aufgaben, die Höhe nicht immer
  (`vitmem` unterschätzt, `lstm` überschätzt). rho jetzt: `match_shift` → `robot_lookmem` +0.86 (n = 10),
  `push_easy` → `robot_findc` +0.76 (n = 17). `vitmem` ist ohne Vorstufe das beste Netz auf `robot_lookmem`.
- **Belege:** 1d22f39, ebeba6e, 9eeaca8; `results/new3.jsonl`, `results/new3_lookmem.jsonl`.

## 2026-11-12 — `vitmem` auf `robot_lookmem`: braucht keine Vorstufe

- **Frage:** Wie gut wählt `vitmem` den richtigen Körper, auch beim nie gesehenen Y, und hilft ihm die Vorstufe?
- **Ergebnis (Seeds 0–2; Anteil der Szenen mit richtig gewähltem Körper):**

  | Training | trainierte Formen | Szenen mit Y, Y gesucht | Szenen mit Y, anderer gesucht |
  |---|---|---|---|
  | allein, 6000 Updates | 0.89 | 0.59 | 0.76 |
  | allein, 12000 Updates | 0.93 | 0.64 | 0.80 |
  | Vorstufe `keep_shift+same_shift:12000`, dann 12000 | 0.90 | 0.60 | 0.78 |

  Zum Vergleich: `hier_s` mit Vorstufe 0.86 / Y 0.60, `attnmem` allein (24000 Updates) 0.82 / Y 0.56.
- **Schluss:** `vitmem` ist das beste Netz auf dieser Aufgabe und braucht keine Vorstufe; sie schadet eher
  (0.90 gegen 0.93). Das Y bleibt bei allen Netzen bei etwa 0.6: Die Verallgemeinerung auf eine neue Form ist
  die gemeinsame Grenze, nicht das Vergleichen.
- **Belege:** `results/curriculum.jsonl`, `results/robot_lookmem_eval.jsonl`,
  `results/robot_lookmem_curV_eval.jsonl`, `results/robot_lookmem_aloneV_eval.jsonl`.

## 2026-11-12 — `robot_reach` auf den Test-Seeds bestätigt

- **Gemacht:** dieselben vier Pläne wie am Vormittag, Seeds 0–2, dazu `vitmem` (Rechen-PC, `reach_confirm`).
- **Ergebnis (Score auf `robot_reach`; in Klammern die Lesequote der Hilfsaufgabe):**

  | Netz | 12000 Bilder allein | 12000 mit Hilfsaufgabe | 48000 allein | 48000 mit Hilfsaufgabe |
  |---|---|---|---|---|
  | vit | 0.15 | 0.47 (0.50) | 0.33 | 0.62 (0.63) |
  | vitmem | 0.13 | 0.40 (0.42) | 0.31 | 0.59 (0.61) |
  | layer_s | 0.12 | 0.20 (0.33) | 0.25 | 0.44 (0.55) |
  | cnn | 0.09 | 0.14 (0.29) | 0.21 | 0.40 (0.59) |
  | hier_s | 0.08 | 0.12 (0.17) | 0.18 | 0.24 (0.41) |

  Lesen bei 48000 Bildern: Hand 0.79–0.89, Würfel 0.53–0.71.
- **Schluss:** Das Bild von den Abstimm-Seeds hält. Mehr Daten und die Hilfsaufgabe wirken zusammen (vit 0.15 →
  0.62). Die beiden vit-Netze setzen das Gelesene fast verlustfrei um, cnn und Gitter verlieren beim
  Verrechnen 0.11–0.19. `vitmem` liegt knapp unter dem vit.
- **Belege:** `results/reach_read.jsonl`.

## 2026-11-12 — Form am Rand des Blickfelds: erster Versuch fehlerhaft

- **Gemacht:** `robot_shape_edge`: der Körper liegt bis 7 Zellen neben der Mitte.
- **Fehler:** Die anderen beiden gleichfarbigen Körper lagen oft mit im Blickfeld, ohne dass die Aufgabe sagt,
  welcher gemeint ist. Die Zahlen (0.28–0.57 über alle Ringe) messen deshalb nicht die Auflösung am Rand.
- **Behoben:** Der Export verwirft jetzt Szenen mit einem zweiten Körper im Blickfeld; Lauf wiederholt.
- **Belege:** `results/edge_ambiguous/` (der fehlerhafte Lauf, nur zur Nachvollziehbarkeit).

## 2026-11-13 — Form am Rand des Blickfelds (zweiter Lauf)

- **Frage:** Reicht die Auflösung auch, wenn der Körper nicht in der Mitte des Blickfelds liegt?
- **Gemacht:** `robot_shape_edge`: ein einzelner Körper bis 7 Zellen neben der Mitte (bis 5 Zellen volle
  Auflösung, außen gröber); Standard-Fovea, 32×32 gemittelt (`+ret0`) und 32×32 mit drei gelernten Schichten
  (`+ret3`). Seeds 0–2, 6000 Updates, 12000 Bilder. Auswertung je Ring (`scripts/shape_ring_eval.py`).
- **Ergebnis** (Trefferquote, Zufall 0.2; bei `+ret3` nur die Läufe, die gelernt haben):

  | Netz | Ringe 1–3 | Ringe 4–5 | Ring 6 | Ring 7 | gesamt |
  |---|---|---|---|---|---|
  | cnn | 0.72 | 0.69 | 0.52 | 0.43 | 0.58 |
  | cnn+ret3 (1 von 3 Seeds) | 0.88 | 0.82 | 0.66 | 0.54 | 0.72 |
  | layer_s | 0.76 | 0.71 | 0.55 | 0.47 | 0.62 |
  | layer_s+ret3 (2 von 3) | 0.89 | 0.86 | 0.72 | 0.61 | 0.77 |
  | hier_s | 0.66 | 0.67 | 0.53 | 0.45 | 0.58 |
  | hier_s+ret3 (3 von 3) | 0.88 | 0.85 | 0.71 | 0.61 | 0.76 |
  | vit | 0.64 | 0.60 | 0.53 | 0.43 | 0.55 |
  | vit+ret3 (2 von 3) | 0.74 | 0.70 | 0.61 | 0.54 | 0.65 |

  `+ret0` liegt überall auf der Höhe der Standard-Fovea (0.54–0.59 gesamt).
- **Beobachtungen:**
  1. Abseits der Mitte fällt die Erkennung schon bei voller Auflösung von 0.93–0.99 auf 0.60–0.76 und in den
     groben Ringen weiter auf 0.43–0.55.
  2. Die doppelte Auflösung mit gelernter Vorstufe bringt hier 0.10–0.18, in allen Ringen.
  3. Vier der zwölf `+ret3`-Läufe lernen gar nicht (Verlust bleibt beim Zufallswert): Die Vorstufe ist im
     Training instabil.
  4. Die Netze lernen die 12000 Trainingsbilder auswendig (cnn: Verlust im Training 0.06, im Test etwa 2).
     Ein Teil der Lücke zur Mitte ist also Datenmangel, nicht Auflösung.
- **Schluss:** Die Vermutung des Nutzers trifft abseits der Mitte zu, auf dem angeblickten Körper nicht. Ob
  die Lücke an der Auflösung oder an der Datenmenge liegt, ist noch nicht getrennt.
- **Belege:** `results/resolution.jsonl`, `results/shape_ring.jsonl`; Roboter-Projekt f866d7a.

## 2026-11-13 — Vorschalt-Stufe stabilisiert (`+rezN`)

- **Problem:** Vier von zwölf `+ret3`-Läufen lernten nichts (Ausgabe über eine Sigmoid-Funktion, Start beliebig).
- **Gemacht:** `+rezN`: Ausgabe = 2×2-Mittel + gelernte Korrektur, deren letzte Schicht bei null startet. Das
  Training beginnt also genau als `+ret0`.
- **Ergebnis** (`robot_shape_edge_f32`, 12000 Bilder, Seeds 0–2, 6000 Updates; Trefferquote):

  | Netz | Ringe 1–5 | Ring 6 | Ring 7 | gesamt | Standard-Fovea gesamt |
  |---|---|---|---|---|---|
  | layer_s+rez3 | 0.92–0.96 | 0.80 | 0.68 | 0.84 | 0.62 |
  | hier_s+rez3 | 0.89–0.96 | 0.76 | 0.63 | 0.80 | 0.58 |
  | cnn+rez3 | 0.82–0.88 | 0.66 | 0.59 | 0.73 | 0.58 |
  | vit+rez3 | 0.60–0.67 | 0.54 | 0.47 | 0.58 | 0.55 |

  Alle zwölf Läufe lernen. Streuung je Seed: cnn 0.67–0.81, vit 0.43–0.70, Gitter 0.77–0.85.
- **Schluss:** Mit stabiler Vorstufe ist der Gewinn der doppelten Auflösung größer als im ersten Durchgang:
  +0.22 bei beiden Gittern, +0.15 beim cnn, beim vit kaum. In den Ringen mit voller Auflösung erreichen die
  Gitter über 0.9. Das vit profitiert nicht und streut stark.
- **Belege:** f6c4d62; `results/resolution.jsonl`, `results/shape_ring.jsonl`.

## 2026-11-13 — Form abseits der Mitte mit 48000 Bildern: Daten gegen Auflösung

**Frage.** Mit 12000 Bildern lernten die Netze die Trainingsbilder auswendig. Liegt der Gewinn der doppelten
Auflösung nur daran, oder bleibt er mit viermal so vielen Bildern?

**Gemacht.** 48000 Trainingsbilder exportiert (`shapeedge48_train`, gleicher Testsatz), cnn, vit, layer_s, hier_s
mit Standard-Fovea (`robot_shape_edge_big`) und mit `+rez3` auf 32×32 (`robot_shape_edge_f32_big`), Seeds 0–2,
6000 Updates. Auswertung nach Ring mit `scripts/shape_ring_eval.py --suffix _big`.

**Ergebnis.** Trefferquote (Zufall 0,2), Mittel über drei Seeds; innen = Ringe 1–5, außen = Ringe 6–7.

| Netz | Standard 12000 | Standard 48000 | `+rez3` 12000 | `+rez3` 48000 | `+rez3` 48000 innen / außen |
|---|---|---|---|---|---|
| cnn | 0,58 | 0,73 | 0,73 | 0,89 | 0,97 / 0,81 |
| vit | 0,55 | 0,58 | 0,58 | 0,78 | 0,88 / 0,70 |
| layer_s | 0,62 | 0,65 | 0,84 | 0,89 | 0,98 / 0,81 |
| hier_s | 0,58 | 0,62 | 0,80 | 0,89 | 0,97 / 0,82 |

Standard 48000 innen / außen: cnn 0,87 / 0,61, vit 0,66 / 0,51, layer_s 0,76 / 0,56, hier_s 0,71 / 0,53.
Der Testverlust liegt mit 48000 Bildern bei 0,27–0,54 (`+rez3`) und 0,64–0,97 (Standard); mit 12000 Bildern
lag er bei 0,66–2,0.

**Schluss.** Beides zählt, aber die Auflösung mehr. Mehr Bilder allein heben die Standard-Fovea nur um 0,03–0,04
(cnn um 0,15); die doppelte Auflösung bringt bei gleicher Bildzahl 0,16–0,27 dazu. Mit beidem zusammen sind
innerhalb von Ring 5 alle Gitter-Netze und cnn bei 0,97–0,98, im vergröberten Rand bei 0,81. Die Standard-Fovea
verliert also schon im voll aufgelösten Teil Forminformation, sobald der Körper nicht in der Mitte liegt.
Einschränkung: Die Standard-Läufe waren nach 6000 Updates noch nicht ausgelernt (Trainingsverlust fiel noch).

**Belege.** `results/resolution.jsonl`, `results/shape_ring.jsonl`.

## 2026-11-13 — Form-Suche (`robot_finds`) mit 32×32 und Vorschalt-Stufe

**Frage.** Scheitert die Form-Suche (0,03–0,10) am Sehen oder am Vergleichen mit dem Zeigebild?

**Vorhersage vor dem Lauf (2026-11-13, Commit 6f4480c).** Die Auflösung ist nicht der Engpass. Standard bleibt
bei 0,03–0,10; 32×32 hebt kein Netz über 0,25, der Gewinn liegt unter 0,10.

**Gemacht.** Suchszenen neu exportiert, zeichengleich zu den alten, dazu die Szene in 32×32 über dasselbe
Blickfeld (Zeigebild bleibt 16×16). Aufgaben `robot_finds_f32`, `robot_finds_parts_f32`. Auf dem Worker, Seeds
0–2: fünf Netze mit Standard-Fovea und dieselben mit `+rez3`, jeweils allein (24000 Updates) und mit
Hilfsaufgabe (48000 Updates).

**Ergebnis.** Wertung der Suche, Mittel über drei Seeds.

| Netz | Standard | Standard + Hilfsaufgabe | 32×32 | 32×32 + Hilfsaufgabe |
|---|---|---|---|---|
| vit+ref | 0,07 | 0,08 | 0,35 (0,25 / 0,33 / 0,46) | 0,24 |
| layer_s_sp4+cell+ref | 0,09 | 0,10 | 0,32 | 0,27 |
| layer_s+cell+ref | 0,09 | 0,12 | 0,30 | 0,27 |
| hier_s+cell+ref | 0,07 | 0,06 | 0,23 | 0,17 |
| cnn+ref | 0,07 | 0,04 | 0,21 | 0,12 |

Teile der Hilfsaufgabe (Mittel über Netze, Standard → 32×32): erster Blickschritt 0,17–0,26 → 0,30–0,45;
Form der Kandidaten 0,20–0,34 → 0,24–0,45; Form im Zeigebild bei beiden 0,93–0,98 (cnn 0,61 → 0,93).

**Schluss.** Die Vorhersage war falsch. Die doppelte Auflösung verdrei- bis verfünffacht die Wertung
(Gewinn 0,14–0,28), drei Netze liegen über 0,25. Die Auflösung ist also ein echter Engpass der Form-Suche,
aber nicht der einzige: Auch mit 32×32 bleibt die Suche bei 0,2–0,35, und die Form der Kandidaten wird nur zu
0,24–0,45 gelesen. Die Hilfsaufgabe schadet mit 32×32 bei jedem Netz (bei gleicher Zahl von Updates je Aufgabe).
Die Streuung über die Seeds ist außer bei vit klein (±0,01–0,02).

**Belege.** `results/finds_res.jsonl` (Worker-Aufträge finds_std2, finds_f32b; Commit d0c5ff0).

## 2026-11-13 — Form an einer genannten Stelle der Suchszene lesen (`robot_shape_at`)

**Frage.** In `robot_finds` wird die Form der Kandidaten nur zu 0,24–0,45 gelesen, ein Körper allein abseits der
Mitte aber zu 0,6–0,9. Liegt das an der Verwechslung mehrerer gleichfarbiger Körper?

**Vorhersage vor dem Lauf (2026-11-13, Commit 4d5e0cb).** Standard 0,40–0,55, 32×32 0,45–0,65. Mindestens 70 %
der Fehler nennen die Form eines der beiden anderen Körper der Szene (Zufall 50 %).

**Gemacht.** Aufgabe `robot_shape_at` / `robot_shape_at_f32`: Suchszene plus Ort eines der drei Körper als
Kommando (Schritt von der Mitte in Zellen, je Achse acht überlappende Werte) -> Form dieses Körpers (5 Klassen).
cnn, vit (`+cmd`), layer_s, hier_s (`+cell`), Standard gegen `+rez3`, Seeds 0–2, 12000 Updates, auf dem Worker.
Auswertung über alle 9000 Paare (Szene, Körper) des Testsatzes: `scripts/shape_at_eval.py`; Gegenprobe mit
vertauschtem Ort: `scripts/shape_at_swap.py`.

**Ergebnis.** Trefferquote (Zufall 0,2), Mittel über drei Seeds. innen = bis Ring 5 (30 % der Körper), außen =
Ring 6–8; „andere“ = Anteil der Fehler, die die Form eines anderen Körpers der Szene nennen. In Klammern zum
Vergleich ein Körper allein (`robot_shape_edge`, 12000 Bilder, innen = Ringe 1–5, außen = Ringe 6–7).

| Netz | gesamt | innen | außen | nächster Körper < 4 Zellen / weiter | andere |
|---|---|---|---|---|---|
| cnn | 0,39 | 0,63 (0,71) | 0,30 (0,47) | 0,32 / 0,40 | 0,50 |
| vit | 0,25 | 0,27 (0,62) | 0,24 (0,48) | 0,24 / 0,25 | 0,51 |
| layer_s | 0,27 | 0,35 (0,74) | 0,24 (0,51) | 0,24 / 0,27 | 0,51 |
| hier_s | 0,29 | 0,39 (0,66) | 0,25 (0,49) | 0,24 / 0,30 | 0,51 |
| cnn `+rez3` | 0,41 | 0,63 (0,85) | 0,32 (0,63) | 0,33 / 0,42 | 0,50 |
| vit `+rez3` | 0,22 | 0,24 (0,65) | 0,22 (0,50) | 0,21 / 0,22 | 0,51 |
| layer_s `+rez3` | 0,34 | 0,44 (0,94) | 0,30 (0,74) | 0,28 / 0,35 | 0,51 |
| hier_s `+rez3` | 0,37 | 0,48 (0,92) | 0,32 (0,70) | 0,29 / 0,38 | 0,49 |

Gegenprobe: Nennt das Kommando den Ort eines anderen Körpers, ändert sich die Antwort in 62–79 % der Fälle und
trifft die Form des ersten Körpers nur noch zu 0,15–0,20. Die Netze benutzen den Ort also. Testverlust
1,48–1,61 (ln 5 = 1,61), Trainingsverlust am Ende um 0,9: Die Netze lernen die 12000 Szenen auswendig.

**Schluss.** Beide Teile der Vorhersage waren falsch. (1) Die Trefferquote liegt mit 0,22–0,41 weit unter der
Erwartung; vit bleibt beim Zufall. (2) Die Fehler sind blind: Sie nennen die anderen Körper der Szene genau so
oft wie beim Raten (0,50). Es ist also keine Verwechslung der Körper; die Netze wissen bei einem Fehler nicht
einmal, welche Formen in der Szene liegen. Zwei Ursachen sind sichtbar: 70 % der Körper liegen außerhalb von
Ring 5, wo fast nichts gelesen wird (0,22–0,32), und auch innen lesen Gitter und vit viel schlechter als bei
einem Körper allein (0,24–0,48 gegen 0,62–0,94); nur cnn hält innen 0,63. Ein naher Nachbar kostet 0,01–0,09.
Nicht getrennt: ob Gitter und vit an drei Körpern im Bild oder an der Ortsangabe über das Kommando scheitern
(sie benutzen es, aber wie gut, ist offen), und wie viel mehr Szenen bringen würden.

**Belege.** `results/shape_at_runs.jsonl`, `results/shape_at.jsonl` (Worker-Aufträge shape_at, shape_at_f32).

## Laufend / offen

- (nichts)
