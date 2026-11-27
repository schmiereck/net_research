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

## 2026-11-13 — Review von agy, Punkt 3.1: Trainingsfenster der Spiele starten bei Zustand null

**Frage.** Google agy fand im Review (REVIEW-2026-11-13.md): `ControlLearner._sample` setzt den Zustand zu Beginn
jedes 16-Schritte-Fensters zurück, die Auswertung läuft dagegen hunderte Schritte ohne Reset. Erklärt das
schwache oder unruhige Gedächtnis-Netze in den Spielen? (Fundstelle von Claude bestätigt; die Wirkung war
Vermutung.)

**Vorhersage vor dem Lauf (2026-11-13, Commit 914a58a).** Auf bricks_mem und paddle_mem ändert sich wenig
(±0,05). Auf crossing, racer und maze gewinnt gru höchstens 0,2 und bleibt unter cnn.

**Gemacht.** Option `NETRESEARCH_BURN` (Standard 0 = wie bisher): Ein Netz mit Zustand läuft erst die letzten
16 Schritte des vorangehenden Fensters ohne Gradient und geht mit diesem Zustand und den echten Resets ins
Trainingsfenster. Vergleich 0 gegen 16, Seeds 0–2, 1500 Updates, lokal.

**Ergebnis.** Wertung, Mittel über drei Seeds (ohne → mit Vorlauf).

| Netz | bricks_mem | paddle_mem | maze | crossing | racer |
|---|---|---|---|---|---|
| gru | 0,87 → 0,87 | 0,99 → 0,98 | 0,46 → 0,43 | 0,00 → 0,04 | 0,21 → 0,23 |
| layer_i_sp4 | 0,85 → 0,91 | 0,91 → 0,98 | 0,42 → 0,45 | – | – |

layer_i_sp4 je Seed: bricks_mem 0,93 / 0,82 / 0,81 → 0,94 / 0,90 / 0,90; paddle_mem 0,98 / 0,87 / 0,86 →
0,99 / 0,97 / 0,98. In allen neun Paaren ist der Lauf mit Vorlauf mindestens so gut.

**Schluss.** Für gru trifft die Vorhersage zu: kein Effekt, der Rückstand auf crossing, racer und maze hat
eine andere Ursache. Für das Gitter mit Notizblock hat agy recht: Der Vorlauf hebt die schwachen Seeds und
halbiert die Streuung (+0,06 und +0,08 auf den Gedächtnis-Spielen). Das erklärt einen Teil der Unruhe von
layer_i_sp4, nicht aber das Niveau auf maze. Die Option bleibt vorerst aus, damit alte Zahlen vergleichbar
bleiben; ob sie Standard wird, ist offen.

**Belege.** `results/burnin_b0.jsonl`, `results/burnin_b16.jsonl`.

## 2026-11-13 — Suchszenen mit allen Körpern im scharfen Bereich (`gazeshapein`)

**Frage.** In den alten Suchszenen liegen 70 % der Körper außerhalb von Ring 5 und werden dort kaum gelesen.
Was bleibt von den beiden Aufgaben (Form an genannter Stelle, Form-Suche) übrig, wenn alle drei Körper
höchstens 5 Zellen neben der Bildmitte liegen? Scheitern die Netze an drei Körpern im Bild oder am Rand?

**Vorhersage vor dem Lauf (2026-11-13).** Form an genannter Stelle: mit 12000 Szenen cnn 0,6–0,7, Gitter
0,35–0,5, vit unter 0,3; mit 48000 Szenen und `+rez3` cnn und Gitter 0,75–0,9, vit unter 0,5. Form-Suche mit
48000 Szenen und `+rez3`: bestes Netz 0,5–0,7, nicht gelöst (unter 0,8).

**Gemacht.** Export im Roboter-Projekt erweitert (`gazeshapein`: Blick auf den Schwerpunkt der drei Körper
± 3 Zellen, Szenen mit einem Körper jenseits von Ring 5 verworfen; 48000 Trainingsszenen). Aufgaben
`robot_shape_at_in*` und `robot_finds_in*` (`_in12` = die ersten 12000 Szenen), jeweils Standard-Fovea und
32×32 mit `+rez3`. Seeds 0–2; Form an genannter Stelle 12000 Updates, Suche 24000 Updates.

**Ergebnis.** Form an genannter Stelle, Trefferquote (Zufall 0,2):

| Netz | alte Szenen, bis Ring 5 | innen 12000 | innen 48000 | innen 12000 `+rez3` | innen 48000 `+rez3` |
|---|---|---|---|---|---|
| cnn | 0,63 | 0,81 | 0,90 | 0,85 | 0,95 |
| layer_s | 0,35 | 0,74 | 0,78 | 0,91 | 0,94 |
| hier_s | 0,39 | 0,71 | 0,76 | 0,84 | 0,88 |
| vit | 0,27 | 0,56 | 0,56 | 0,52 | 0,69 |

Der Anteil der Fehler, die einen anderen Körper der Szene nennen, bleibt überall bei 0,47–0,51 (Raten 0,5).
vit `+rez3` streut stark (48000: 0,62 / 0,66 / 0,80).

Form-Suche, Wertung (exakter Blickschritt, Zufall 0):

| Netz | alte Szenen | alte Szenen `+rez3` | innen 12000 | innen 48000 | innen 12000 `+rez3` | innen 48000 `+rez3` |
|---|---|---|---|---|---|---|
| layer_s+cell+ref | 0,09 | 0,30 | 0,38 | 0,47 | 0,62 | 0,70 |
| cnn+ref | 0,07 | 0,21 | 0,31 | 0,45 | 0,52 | 0,66 |
| vit+ref | 0,07 | 0,35 | 0,25 | 0,30 | 0,54 | 0,65 |
| hier_s+cell+ref | 0,07 | 0,23 | 0,32 | 0,38 | 0,53 | 0,63 |

Die drei Seeds liegen bei der Suche je Netz höchstens 0,04 auseinander.

**Schluss.** Vorhersage für das Lesen verfehlt, in die pessimistische Richtung: Schon mit 12000 Szenen und
Standard-Fovea lesen cnn und Gitter 0,71–0,81, vit 0,56. Mit 48000 Szenen und `+rez3` liegen cnn und layer_s
über dem vorhergesagten Band (0,94–0,95), vit über 0,5 (0,69). Die Vorhersage für die Suche trifft: bestes
Netz 0,70, nicht gelöst. Daraus folgt: (1) Drei Körper im Bild sind nicht das Hindernis. In den alten Szenen
lasen Gitter und vit auch innen schlecht, weil die meisten Trainingsbeispiele im unlesbaren Rand lagen.
(2) Die Suche steigt von 0,07–0,09 auf 0,63–0,70, wenn Rand, Auflösung und Datenmenge stimmen; alle drei
Hebel wirken und addieren sich. (3) Zwischen Lesen (0,88–0,95) und Suchen (0,63–0,70) bleibt eine Lücke von
etwa 0,25. Sie steckt im Vergleich mit dem Zeigebild und im exakten Blickschritt; welcher Teil wie viel
kostet, ist nicht getrennt. (4) Die Rangfolge kippt mit der Auflösung: vit ist bei der Suche mit Standard-
Fovea letzter und mit `+rez3` gleichauf mit cnn, liest aber die Form an genannter Stelle am schlechtesten.
Einschränkung: Die inneren Szenen sind eine leichtere Aufgabe, kein Ersatz für die alten; der Roboter sieht
Körper auch am Rand.

**Belege.** `results/shape_at_runs.jsonl`, `results/shape_at.jsonl`, `results/finds_res.jsonl`
(Worker-Aufträge at_in_f32b, finds_in, finds_in_f32b; Standard-Läufe der Form-Aufgabe lokal).

## 2026-11-13 — Review von agy, Punkt 3.4: Schritt als zwei 4-Bit-Zahlen, Wertung nur bei exaktem Treffer

**Frage.** agy vermutet zwei Schwächen der Schritt-Ausgabe (dx, dy als Zweierkomplement, alle 8 Bits müssen
stimmen): (a) Knapp-daneben zählt wie völlig falsch, die Wertung unterschätzt die Netze; (b) zwischen −1 und
0 kippen alle vier Bits, dort sollten die Netze schlechter sein. Gemessen an vorhandenen Netzen, ohne neues
Training der Blick-Aufgaben. Keine Vorhersage notiert (Messung an fertigen Netzen).

**Gemacht.** `scripts/step_error_eval.py`: für alle gespeicherten Netze einer Aufgabe exakte Treffer, Anteil
höchstens eine Zelle je Achse daneben, mittlerer Abstand in Zellen, Anteil der Fehler mit höchstens einer
Zelle Abstand, Achsen-Trefferquote bei wahrem Wert −1/0 gegen sonst. Für `robot_reach_big` die besten Netze
mit Hilfsaufgabe neu trainiert (48000 Updates), weil ihre Gewichte nicht gespeichert waren.

**Ergebnis.** `robot_reach_big`, Mittel über die Seeds:

| Netz | exakt | höchstens 1 Zelle | mittlerer Fehler (Zellen) | Achse bei −1/0 | Achse sonst |
|---|---|---|---|---|---|
| vit | 0,62 | 0,87 | 0,69 | 0,69 | 0,78 |
| vitmem | 0,60 | 0,86 | 0,75 | 0,69 | 0,76 |
| layer_s | 0,45 | 0,79 | 1,05 | 0,59 | 0,66 |
| cnn | 0,41 | 0,79 | 1,10 | 0,50 | 0,65 |

Bei `robot_find` und `robot_findc` liegt etwa die Hälfte der falschen Antworten eine Zelle daneben, und bei
−1/0 sind die Netze nicht schlechter als sonst. Bei `robot_finds` (alte Szenen) sind die Fehler groß (5–6
Zellen): Dort wird nicht knapp verfehlt, sondern der falsche Körper oder gar keiner gewählt.

**Schluss.** (a) trifft für das Greifen zu: Zwei Drittel der Fehler der besten Netze liegen eine Zelle
daneben; „höchstens eine Zelle“ ergibt 0,79–0,87 statt 0,41–0,62. Die Decke bei 0,62 ist also zum großen
Teil Wertung. Für die Form-Suche auf den alten Szenen gilt das nicht. (b) ist nur beim Greifen zu sehen
(−0,07 bis −0,15) und dort nicht von einer zweiten Ursache getrennt: Bei −1/0 liegen Hand und Würfel fast
übereinander. Bei den Blick-Aufgaben gibt es keinen Nachteil; die Kodierung allein erklärt ihn also nicht.
Die exakte Wertung bleibt die Hauptzahl (alte Ergebnisse bleiben vergleichbar); mittlerer Fehler und
„höchstens eine Zelle“ stehen als Nebenzahlen über das Skript bereit.

**Belege.** `results/step_error.jsonl`, `results/reach_ckpt.jsonl`.

## 2026-11-13 — Review von agy, Punkt 3.5: Null-Start des Restpfads im Hierarchie-Gitter (`hier_sz`)

**Frage.** `hier_s@400k` bricht auf cycle_mem ein (0,01 gegen 0,80 bei 100k). agy schlägt vor, den Restpfad
bei null starten zu lassen (letzte Schicht der Zelle mit Null-Gewichten), wie bei tiefen Restnetzen üblich.

**Vorhersage vor dem Lauf (2026-11-13).** Der Einbruch verschwindet; `hier_sz@400k` erreicht mindestens 0,5.

**Gemacht.** Modell `hier_sz` (HierGrid mit `zero_init=True`). cycle_mem, 1500 Updates, Seeds 0–2: `hier_sz`,
`hier_sz@400k`, zum Vergleich `hier_s@400k` neu.

**Ergebnis.**

| Netz | Wertung (Seeds 0 / 1 / 2) | Mittel |
|---|---|---|
| hier_s (100k, früher) | 0,78 / 0,70 / 0,92 | 0,80 |
| hier_sz (100k) | 0,00 / 0,01 / 0,07 | 0,03 |
| hier_s@400k | 0,02 / 0,00 / 0,01 | 0,01 |
| hier_sz@400k | 0,00 / 0,00 / 0,01 | 0,00 |

Der Trainingsverlust von `hier_sz` bleibt 500 bis 1100 Updates beim Ratewert 0,693 stehen; ein Seed fängt ab
Update 600 an zu lernen (0,41 am Ende), `hier_sz@400k` bis Update 1500 gar nicht.

**Schluss.** Vorhersage klar verfehlt. Der Null-Start behebt den Einbruch nicht und zerstört zusätzlich das
Netz in Standardgröße (0,80 → 0,03). Vermutete Ursache, nicht geprüft: Im Gitter ist die genullte Schicht
der einzige Weg des Signals von Reihe zu Reihe; solange sie null ist, erhalten die Schichten davor keinen
Gradienten, das Lernen startet spät. Der Vorschlag passt zu Restnetzen mit eigenem Durchgangspfad, nicht zu
diesem Gitter. `hier_sz` bleibt als Modell im Code, wird aber nicht weiter verfolgt. Der Einbruch von
`hier_s@400k` bleibt ungeklärt.

**Belege.** `results/hier_sz.jsonl` (Worker-Auftrag hier_sz).

## 2026-11-13 — Vorlauf (Burn-in), Schritt 1: Welche Gitter profitieren?

**Frage.** Der Vorlauf half layer_i_sp4 (+0,06 und +0,08 auf den Gedächtnis-Spielen), gru nicht. Gilt der
Gewinn für alle Gitter, nur für die mit Notizblock, oder nur für dieses eine Netz?

**Vorhersage vor dem Lauf (2026-11-13).** Netze mit Notizblock (layer_s_sp4, layer_s_am4) gewinnen wie
layer_i_sp4 0,03–0,08 auf bricks_mem und paddle_mem; layer_s und hier_s ändern sich um höchstens 0,03.

**Gemacht.** layer_s, hier_s, layer_s_sp4, layer_s_am4 auf bricks_mem, paddle_mem, maze; Vorlauf 0 gegen 16,
Seeds 0–2, 1500 Updates (Worker-Aufträge burn_who_b0, burn_who_b16).

**Ergebnis.** Wertung, Mittel über drei Seeds (ohne → mit Vorlauf).

| Netz | bricks_mem | paddle_mem | maze |
|---|---|---|---|
| layer_s | 0,94 → 0,96 | 0,98 → 0,97 | 0,49 → 0,48 |
| layer_s_sp4 | 0,93 → 0,93 | 0,97 → 0,98 | 0,45 → 0,50 |
| layer_s_am4 | 0,83 → 0,85 | 0,96 → 0,98 | 0,46 → 0,48 |
| hier_s | 0,90 → 0,82 | 0,97 → 0,98 | 0,44 → 0,46 |
| layer_i_sp4 (früher) | 0,85 → 0,91 | 0,91 → 0,98 | 0,42 → 0,45 |

hier_s auf bricks_mem je Seed: 0,92 / 0,88 / 0,90 → 0,87 / 0,70 / 0,88. layer_s_sp4 auf maze: 0,45 / 0,47 /
0,44 → 0,50 / 0,50 / 0,48 (alle drei Seeds besser).

**Schluss.** Vorhersage für die Notizblock-Netze verfehlt: Auf bricks_mem und paddle_mem gewinnen
layer_s_sp4 und layer_s_am4 nur 0,00–0,02, das liegt in der Seed-Streuung. Für layer_s trifft sie zu. hier_s
verliert auf bricks_mem 0,08, getragen von einem Seed; ob das ein Effekt ist, entscheiden drei Seeds nicht.
Der Gewinn von layer_i_sp4 ist also kein Merkmal des Notizblocks, sondern dieses einen Netzes (einzelne
Gewichte je Zelle und Notizblock); die Netze mit geteilten Gewichten waren ohne Vorlauf schon stabil und nahe
an der Decke. Einziger weiterer Hinweis: layer_s_sp4 auf maze +0,04 in allen drei Seeds. Die Rangfolge der
Netze ändert sich auf keinem der drei Spiele so, dass ein Schluss kippt. Der Vorlauf ist damit kein
allgemeiner Fehler der bisherigen Zahlen; die Option bleibt aus.

**Belege.** `results/burnin_b0.jsonl`, `results/burnin_b16.jsonl`.

## 2026-11-13 — Vorlauf (Burn-in), Schritt 2: `push_easy`

**Frage.** Ändert der Vorlauf die Zahlen auf `push_easy`, dem Spiel, das die Roboter-Aufgaben vorhersagen
soll? Davon hängt ab, ob alle Spiele neu gerechnet werden müssen (Schritt 3).

**Vorhersage vor dem Lauf (2026-11-13, Commit d2c537a).** layer_i_sp4 bleibt mit und ohne Vorlauf unter 0,2;
layer_s und layer_s_sp4 ändern sich im Mittel um höchstens 0,1, ihre Reihenfolge gegenüber den anderen
Netzen bleibt.

**Gemacht.** layer_i_sp4, layer_s_sp4, layer_s auf `push_easy`, Vorlauf 0 gegen 16, Seeds 0–2, 1500 Updates
(Worker-Aufträge burn_push_b0, burn_push_b16).

**Ergebnis.** Wertung (Seeds 0 / 1 / 2, Mittel).

| Netz | ohne Vorlauf | mit Vorlauf |
|---|---|---|
| layer_s_sp4 | 0,61 / 0,58 / 0,77 → 0,66 | 0,61 / 0,61 / 0,71 → 0,65 |
| layer_s | 0,68 / 0,52 / 0,68 → 0,62 | 0,58 / 0,61 / 0,61 → 0,60 |
| layer_i_sp4 | −0,03 / 0,00 / 0,03 → 0,00 | 0,00 / 0,06 / −0,03 → 0,01 |

Nebenbefund: layer_s ohne Vorlauf, Seed 0, ergab hier 0,68, im früheren Lauf 0,48. Gleicher Seed heißt auf
`push_easy` also nicht gleiche Zahl (anderer Rechner oder Code-Stand); die Streuung eines Einzellaufs liegt
bei etwa 0,1–0,2.

**Schluss.** Vorhersage trifft in allen Teilen. Der Vorlauf ändert auf `push_easy` nichts: Die Unterschiede
(−0,01 und −0,02) sind viel kleiner als die Streuung, und layer_i_sp4 bleibt bei null. Schritt 3 entfällt;
die bisherigen Spiel-Zahlen und die Prognose-Rangfolgen gelten weiter. Review-Punkt 3.1 ist damit
abgeschlossen: Die Fundstelle stimmt, die Wirkung beschränkt sich auf layer_i_sp4 in den Gedächtnis-Spielen.
Die Option `--burn` bleibt im Code und ist standardmäßig aus.

**Belege.** `results/burnin_b0.jsonl`, `results/burnin_b16.jsonl`.

## 2026-11-14 — Innere Suchszenen: Was fehlt zwischen Lesen und Suchen?

**Frage.** In den inneren Szenen wird die Form an genannter Stelle zu 0,88–0,95 gelesen, die Suche erreicht
aber nur 0,63–0,70. Steckt die Lücke im Vergleich mit dem Zeigebild oder im exakten Blickschritt?

**Vorhersage vor dem Lauf (2026-11-14, Commit 80be21b).** Mit genannter Form liegen cnn und layer_s 0,05–0,15
über den Netzen mit Zeigebild. Von den Fehlern der Netze mit Zeigebild liegt mindestens die Hälfte beim
richtigen Körper eine Zelle daneben, 20–35 % bei einem anderen Körper; „richtiger Körper gefunden“ erreicht
0,82–0,90.

**Gemacht.** `robot_finds_in_f32` (48000 Szenen, `+rez3`, 24000 Updates, Seeds 0–2) mit Zeigebild (`+ref`) und
mit der Form als Kommando (`+cmd` / `+cell`), Gewichte gespeichert. `scripts/finds_error_eval.py` teilt jede
Antwort auf 9000 Testpaaren ein: exakt / richtiger Körper, höchstens eine Zelle je Achse daneben / höchstens
eine Zelle neben einem anderen Körper der Szene / sonstwo.

**Ergebnis.** Anteile, Mittel über drei Seeds.

| Netz | Form | exakt | richtiger Körper, 1 Zelle daneben | anderer Körper | sonstwo | richtiger Körper gesamt |
|---|---|---|---|---|---|---|
| layer_s | gezeigt | 0,69 | 0,21 | 0,02 | 0,08 | 0,90 |
| layer_s | genannt | 0,73 | 0,20 | 0,01 | 0,07 | 0,93 |
| cnn | gezeigt | 0,66 | 0,22 | 0,03 | 0,09 | 0,88 |
| cnn | genannt | 0,66 | 0,23 | 0,01 | 0,09 | 0,90 |
| vit | gezeigt | 0,64 | 0,22 | 0,03 | 0,10 | 0,87 |
| vit | genannt | 0,71 | 0,21 | 0,01 | 0,07 | 0,92 |
| hier_s | gezeigt | 0,62 | 0,25 | 0,03 | 0,10 | 0,87 |
| hier_s | genannt | 0,66 | 0,25 | 0,01 | 0,09 | 0,90 |

Die neu trainierten Netze mit Zeigebild treffen die Wertungen vom Vortag auf 0,00–0,01.

**Schluss.** Die Lücke ist der exakte Blickschritt, nicht der Vergleich. (1) Der Bildvergleich kostet wenig:
genannt gegen gezeigt +0,00 (cnn) bis +0,07 (vit), layer_s +0,03; die Vorhersage (0,05–0,15 für cnn und
layer_s) war zu hoch. (2) Ein falscher Körper wird fast nie gewählt (0,02–0,03 aller Antworten, 6–9 % der
Fehler); vorhergesagt waren 20–35 % der Fehler, verfehlt. (3) Zwei Drittel der Fehler liegen beim richtigen
Körper eine Zelle daneben (getroffen), und der richtige Körper wird in 0,87–0,90 der Fälle gefunden
(getroffen). Das entspricht der Lesequote von 0,88–0,95: Wer die Form liest, findet den Körper auch. Die
Form-Suche ist in den inneren Szenen also bis auf die Schrittgenauigkeit gelöst; die exakte Wertung
unterschätzt sie, wie beim Greifen (Review-Punkt 3.4). Offen: die 0,07–0,10 „sonstwo“ (nicht aufgeteilt in
zwei Zellen daneben gegen ganz verloren) und warum die eine Zelle fehlt (Körpermitte nahe einer Zellgrenze
oder Grenze der Netze).

**Belege.** `results/finds_gap.jsonl`, `results/finds_error.jsonl` (Worker-Auftrag finds_in_gap2).

## 2026-11-14 — Innere Suchszenen: Woher kommt die eine Zelle Fehler beim Blickschritt?

**Frage.** Die Netze finden den richtigen Körper in 0,87–0,93 der Fälle, treffen den Schritt aber in 0,20–0,25
nur auf eine Zelle genau. Liegt das an der Zellgrenze (die „richtige“ Zelle hängt an einem Bruchteil eines
Pixels) oder an den Netzen?

**Vorhersage vor der Messung (2026-11-14, Commit 3a563f1).** Überwiegend die Zellgrenze: bei Rand unter
0,25 px höchstens 0,6 exakt, bei Rand ab 2 px mindestens 0,9. L, U und T höchstens 0,05 schlechter als Würfel
und Kreuz.

**Gemacht.** Export im Roboter-Projekt speichert den Pixelort jedes Körpers (`pos`); Testsatz neu erzeugt, mit
dem alten Bild für Bild gleich, alle gespeicherten Schritte stimmen mit der nächsten Zelle überein. Rand =
Abstand des Körperorts zur zweitnächsten minus zur nächsten Abtastzelle (Zelle 4 px, ein Bildpunkt der
32×32-Ansicht 2 px). `scripts/finds_cell_eval.py` auf den Netzen von `robot_finds_in_f32`, 9000 Testpaare,
Seeds 0–2. Alle Zahlen: Anteil exakter Schritte unter den Antworten beim richtigen Körper.

**Ergebnis.** Der Rand liegt bei 11 % der Körper unter 0,25 px, bei 21 % unter 0,5 px, bei 31 % über 2 px.

| Netz (Form gezeigt) | Rand < 0,25 | 0,25–0,5 | 0,5–1 | 1–2 | ≥ 2 px |
|---|---|---|---|---|---|
| layer_s | 0,53 | 0,61 | 0,69 | 0,81 | 0,91 |
| cnn | 0,51 | 0,60 | 0,69 | 0,79 | 0,86 |
| vit | 0,52 | 0,61 | 0,68 | 0,77 | 0,87 |
| hier_s | 0,50 | 0,59 | 0,63 | 0,74 | 0,85 |

| Netz (Form gezeigt) | Würfel | Kreuz | U | L | T |
|---|---|---|---|---|---|
| layer_s | 0,87 | 0,82 | 0,79 | 0,72 | 0,62 |
| cnn | 0,88 | 0,82 | 0,75 | 0,67 | 0,59 |
| vit | 0,85 | 0,82 | 0,74 | 0,66 | 0,60 |
| hier_s | 0,82 | 0,78 | 0,73 | 0,63 | 0,57 |

Die Netze mit genannter Form liegen überall 0,00–0,06 darüber, mit demselben Muster. Der Fehler liegt etwa
gleich oft in dx (0,42–0,48) und dy (0,38–0,43), in 0,13–0,15 in beiden Achsen.

**Schluss.** Zwei Ursachen, nicht eine. (1) Die Zellgrenze: Direkt an der Grenze ist der Schritt ein Münzwurf
(0,50–0,54), mit wachsendem Rand steigt die Quote stetig; dieser Teil der Vorhersage trifft. Ab 2 px erreichen
aber nur layer_s (0,91) und vit mit genannter Form (0,90) die vorhergesagten 0,9, cnn und hier_s bleiben bei
0,85–0,86. (2) Die Form: T und L sind 0,15–0,29 schlechter als der Würfel; vorhergesagt waren höchstens 0,05,
klar verfehlt. Vermutung, nicht geprüft: Bei den unsymmetrischen Körpern fällt der Bezugspunkt, dessen Zelle
verlangt wird, nicht mit der sichtbaren Mitte zusammen und wandert mit der Drehung. Für die Wertung heißt
das: Bei rund einem Fünftel der Körper (Rand unter 0,5 px, ein Viertel eines Bildpunkts der 32×32-Ansicht)
ist „exakt“ aus dem Bild kaum entscheidbar; die exakte Wertung hat hier eine Decke unter 1. „Höchstens eine
Zelle daneben“ misst, ob der Körper gefunden wurde, und sollte bei Blick- und Greifschritten als zweite Zahl
neben der exakten stehen. Der Formeffekt ist dagegen echte, lernbare Ungenauigkeit der Netze oder eine
Eigenschaft der Zielgröße; das ist offen.

**Belege.** `results/finds_cell.jsonl`; `data/robot/gazeshapein_test_pos.npz` (nicht im Repository).

## 2026-11-14 — Bezugspunkt der Körper; zweite Zahl für Schritt-Aufgaben

**Frage.** (1) Liegt bei L, U und T der Punkt, dessen Zelle der Blickschritt treffen soll, neben der sichtbaren
Mitte? Das war die Vermutung zum Formeffekt im vorigen Eintrag. (2) Auftrag des Nutzers: „höchstens eine Zelle
daneben“ als zweite Zahl in die Wertung.

**Gemacht.** (1) Im Roboter-Modell je Körper den Abstand zwischen Körper-Ursprung (den der Export projiziert)
und Flächenschwerpunkt seiner Quader gemessen (`scripts/robot_body_origin.py`, läuft im Roboter-Projekt);
Maßstab am Tisch 471 px je Meter, eine Zelle = 4 px = 8,5 mm. (2) `TaskSpec.step`: Für Aufgaben mit einem
Schritt als Ziel (servo, robot_gaze, robot_reach*, robot_find, robot_findc, robot_findi, robot_finds*) meldet
die Auswertung zusätzlich `near` (höchstens eine Zelle je Achse daneben, exakte eingeschlossen) und `step_err`
(mittlerer Abstand in Zellen); in Lehrplan-Läufen steht beides im Feld `near`. `score` bleibt die exakte
Wertung.

**Ergebnis.**

| Körper | Ursprung → Flächenschwerpunkt | exakt unter „gefunden“ (layer_s, voriger Eintrag) |
|---|---|---|
| Würfel | 0,0 px | 0,87 |
| Kreuz | 0,0 px | 0,82 |
| U | 1,8 px | 0,79 |
| T | 2,6 px | 0,62 |
| L | 3,5 px | 0,72 |

Die Körper sind 24–60 mm groß, also 3–7 Zellen. Probe der neuen Zahl an gespeicherten Netzen von
`robot_finds_in_f32` (Seed 0): layer_s mit Zeigebild exakt 0,71, `near` 0,91, `step_err` 0,63.

**Schluss.** Die Vermutung stimmt: Bei den drei unsymmetrischen Körpern liegt der verlangte Punkt 1,8–3,5 px
neben dem Schwerpunkt, bis fast eine Zelle, und er dreht sich mit dem Körper. Würfel und Kreuz haben den
Ursprung in der Mitte, und genau sie werden am genauesten getroffen. Die Reihenfolge innerhalb von U, T, L
folgt dem Abstand nicht streng (T schlechter als L); der Abstand ist also nicht die einzige Größe. Der
Formeffekt ist damit überwiegend eine Eigenschaft der Zielgröße: Der Ursprung ist ein willkürlicher Punkt des
Modells, aus dem Bild nur über Form und Drehung zu erschließen. Ob der Blick besser auf den Schwerpunkt zielen
sollte, ist eine Entscheidung über die Aufgabe und hier nicht getroffen; die Daten sind unverändert.
Einschränkung: Der Flächenschwerpunkt zählt überlappende Quader doppelt, die Abstände sind Näherungen.

**Belege.** `scripts/robot_body_origin.py` (Ausgabe oben), `netresearch/spec.py`, `netresearch/train.py`.

## 2026-11-14 — Schritt als Populations-Code statt 8 Bits

**Frage.** Idee von agy (IDEAS-agy-2026-11-14.md), Auftrag des Nutzers: Lernt ein Netz den Blick- oder
Greifschritt schneller oder genauer, wenn er nicht als zwei 4-Bit-Zahlen, sondern je Achse über 16 Ausgänge
(einer je Wert −8..7) ausgegeben wird?

**Gemacht.** `TaskSpec.pop`, `pop_variant` (`netresearch/tasks/servo.py`): Ziel je Achse entweder eine Glocke
um den wahren Wert (`_pop`, Breite eine Zelle) oder ein einzelner Ausgang (`_hot`); gelesen wird der stärkste
Ausgang je Achse; Wertung = beide Achsen richtig. Gleiche Bilder, gleiche Schritte, gleicher Verlust (BCE).
servo 1500 Updates; robot_findc und robot_finds_in_f32 24000 Updates; Seeds 0–2.
Vorhersage vor dem Lauf (wörtlich aus „Laufend / offen“):

> - Schritt als Populations-Code statt 8 Bits (Idee agy, IDEAS-agy-2026-11-14.md; Auftrag Nutzer 2026-11-14):
> je Achse 16 Ausgänge für −8..7 im Symbol-Bereich, Ziel = Glocke um den wahren Wert (`_pop`, Breite eine
> Zelle) oder ein einzelner Ausgang (`_hot`, ohne Nachbarschaft), gelesen wird der stärkste Ausgang je Achse.
> Gleiche Bilder, gleiche Schritte, gleicher Verlust (BCE). Aufgaben: servo, robot_findc, robot_finds_in_f32,
> jeweils Bits / `_pop` / `_hot`, Seeds 0–2.
> **Vorhersage vor dem Lauf (2026-11-14):** (1) servo: kein großer Tempogewinn; `_pop` braucht bis Wertung 0,5
> mindestens halb so viele Updates wie Bits (kein Faktor 2, schon gar nicht 50), Endwert nach 1500 Updates
> innerhalb ±0,1. (2) robot_finds_in_f32: exakt innerhalb ±0,03 der Bits (0,63–0,70), weil Zellgrenze und
> Bezugspunkt die Decke setzen; `near` +0,00 bis +0,03, mittlerer Fehler mindestens 10 % kleiner. (3)
> robot_findc: `_pop` innerhalb ±0,05 der Bits. (4) `_hot` ist auf den Roboter-Aufgaben nicht besser als
> `_pop` und im Mittel mindestens 0,03 schlechter.

**Ergebnis.** servo, exakt nach 1500 Updates (in Klammern: Updates bis Wertung 0,5, aus der Kurve in
250er-Schritten):

| Netz | Bits | `_pop` | `_hot` |
|---|---|---|---|
| vit | 0,84 (1000) | 1,00 (750) | 0,97 (1000) |
| layer_s | 0,22 (nie) | 0,98 (750) | 0,67 (1250) |
| hier_s | 0,23 (nie) | 0,99 (750) | 0,91 (1000) |
| mlp | 0,03 (nie) | 0,96 (750) | 0,21 (nie) |
| cnn | 0,22 (nie) | 0,22 ± 0,18 (nie) | 0,01 (nie) |

robot_findc (Farbe genannt), exakt / `near` / `step_err`:

| Netz | Bits | `_pop` | `_hot` |
|---|---|---|---|
| cnn+cmd | 0,63 / 0,83 / 1,09 | 0,68 / 0,94 / 0,69 | 0,75 / 0,91 / 0,83 |
| vit+cmd | 0,64 / 0,82 / 1,17 | 0,63 / 0,92 / 0,82 | 0,74 / 0,90 / 0,85 |
| layer_s+cell | 0,45 / 0,72 / 1,87 | 0,59 / 0,91 / 0,99 | 0,64 / 0,85 / 1,45 |
| hier_s+cell | 0,26 / 0,62 / 2,46 | 0,42 / 0,82 / 1,78 | 0,46 / 0,72 / 2,60 |

robot_finds_in_f32 (Form gezeigt, `+ref+rez3`), exakt / richtiger Körper (exakt oder eine Zelle daneben) /
verloren (`scripts/finds_error_eval.py`). Für Bits über alle vier Netze: richtiger Körper 0,87–0,90, verloren
0,07–0,10 (Eintrag „Was fehlt zwischen Lesen und Suchen?“).

| Netz | Bits exakt | `_pop` | `_hot` |
|---|---|---|---|
| cnn | 0,66 | 0,73 / 0,97 / 0,01 | 0,79 / 0,95 / 0,02 |
| layer_s+cell | 0,70 | 0,70 / 0,97 / 0,01 | 0,77 / 0,96 / 0,02 |
| hier_s+cell | 0,63 | 0,63 / 0,96 / 0,02 | 0,71 / 0,94 / 0,03 |
| vit | 0,65 | 0,61 / 0,94 / 0,02 | 0,72 / 0,93 / 0,03 |

`step_err`: `_pop` 0,49–0,81, `_hot` 0,45–0,73; für Bits liegt nur layer_s Seed 0 vor (0,63; layer_s mit
`_pop` 0,49, mit `_hot` 0,45 im Mittel über drei Seeds). Exakt unter „gefunden“ mit `_hot`
(`scripts/finds_cell_eval.py`): Abstand zur Zellgrenze < 0,25 px 0,54–0,56, ≥ 2 px 0,90–0,95; Würfel
0,84–0,89, T 0,63–0,74. Der falsche Körper wird weiter in 0,02–0,04 gewählt.

**Vergleich mit der Vorhersage.** (1) servo: klar verfehlt. Vier von fünf Netzen erreichen mit `_pop` 0,96–1,00,
mit Bits 0,03–0,84. (2) robot_finds_in_f32: `_pop` exakt −0,04 bis +0,07 gegenüber Bits (für zwei von vier
Netzen innerhalb ±0,03), aber der richtige Körper wird um 0,05–0,09 öfter gefunden statt höchstens 0,03:
verfehlt. (3) robot_findc: verfehlt für die Gitter (+0,14 / +0,16), getroffen für cnn und vit. (4) Verfehlt:
`_hot` ist exakt auf beiden Roboter-Aufgaben 0,04–0,11 besser als `_pop`; nur bei `near` und `step_err` auf
robot_findc liegt `_pop` vorn.

**Schluss.** Die Bit-Kodierung des Schritts war selbst ein Hindernis, größer als gedacht. Drei Befunde: (a)
Auf servo ist der Unterschied eine Frage von Lernen oder Nicht-Lernen in 1500 Updates. (b) Der Anteil
„verloren“ der Suche (0,07–0,10) war fast ganz ein Effekt der Bits (ein falsches hohes Bit wirft den Schritt
weit weg); mit je einem Ausgang je Wert bleiben 0,01–0,03. (c) Zellgrenze und Formeffekt bleiben bestehen;
sie sind Eigenschaften der Zielgröße, nicht der Kodierung. `_hot` ist exakt besser, `_pop` lernt auf servo
schneller und liegt näher; vermutlich drückt die breite Glocke (Nachbar 0,61 gegen 1,0) die exakte Wertung,
geprüft ist das nicht (eine schmalere Glocke wäre die Probe). Das cnn auf servo hat von keiner Kodierung
etwas; ungeklärt. Ob die Schritt-Aufgaben der Leiter auf die neue Kodierung umgestellt werden, ist eine
Entscheidung über die Aufgaben (alle bisherigen Zahlen wären nicht mehr vergleichbar) und hier nicht
getroffen; die alten Aufgaben sind unverändert.

**Belege.** `results/pop_servo.jsonl`, `results/pop_findc.jsonl`, `results/finds_pop.jsonl`,
`results/finds_error.jsonl`, `results/finds_cell.jsonl`; Worker-Jobs `pop_servo`, `pop_findc`, `pop_finds`,
`hot_finds` (Commit 08efb9d).

## 2026-11-14 — Innere Suchszenen mit dem Flächenschwerpunkt als Ort (`gazeshapec`)

**Frage.** Auftrag des Nutzers: Blickziel auf den Flächenschwerpunkt statt auf den Körper-Ursprung, als neue
Variante der inneren Szenen. Verschwindet damit der Formeffekt beim Blickschritt? (Hinweis des Nutzers: Hier
geht es um das Erkennen; fürs Greifen werden später andere Punkte der Form wichtig, etwa gut greifbare Zinken.)

**Gemacht.** Export `gazeshapec` im Roboter-Projekt (Commit 3650f5d): wie `gazeshapein`, aber alle Orte
(Schritte, Blick, Ausschnitte, Zeigebilder) am Flächenschwerpunkt der Vereinigung der Quader; 48000
Trainings- und 3000 Testszenen, neu gewürfelt (also andere Szenen als `gazeshapein`). Aufgabe
`robot_finds_c_f32`, 24000 Updates, vier Netze mit Zeigebild (`+ref+rez3`), Seeds 0–2, Bit-Kodierung wie
bisher. Vorhersage vor dem Lauf (wörtlich aus „Laufend / offen“):

> - Innere Suchszenen mit dem Flächenschwerpunkt als Ort jedes Körpers (`gazeshapec`, 48000 Szenen neu
> exportiert; `robot_finds_c_f32`, Netze wie bei `robot_finds_in_f32`, Seeds 0–2). Genauer gemessen (Vereinigung
> der Quader, ohne Doppelzählung) liegt der Ursprung bei L / U / T 3,3 / 2,2 / 1,6 px neben dem Schwerpunkt.
> **Vorhersage vor dem Lauf (2026-11-14):** Der Formeffekt schrumpft, verschwindet aber nicht: exakt unter
> „gefunden“ liegen L, U, T höchstens 0,10 unter dem Würfel (bisher bis 0,29). Die exakte Wertung von layer_s
> mit Zeigebild steigt von 0,70 auf 0,74–0,80; `near` bleibt bei 0,88–0,93. An der Zellgrenze bleibt es beim
> Münzwurf.

**Ergebnis.** Exakt / richtiger Körper / verloren (`scripts/finds_error_eval.py`), in Klammern der alte Ort:

| Netz | exakt | richtiger Körper | verloren |
|---|---|---|---|
| layer_s+cell | 0,74 (0,70) | 0,90 | 0,07 |
| cnn | 0,71 (0,66) | 0,89 | 0,08 |
| vit | 0,69 (0,65) | 0,87 | 0,08 |
| hier_s+cell | 0,68 (0,63) | 0,88 | 0,09 |

`near` aus dem Lauf 0,88–0,90, `step_err` 0,69–0,90. Exakt unter „gefunden“ nach Form
(`scripts/finds_cell_eval.py`), Spanne über die vier Netze, in Klammern der alte Ort (Eintrag „Woher kommt
die eine Zelle Fehler“):

| Würfel | Kreuz | T | L | U |
|---|---|---|---|---|
| 0,84–0,89 (0,82–0,88) | 0,83–0,87 (0,78–0,82) | 0,76–0,81 (0,57–0,62) | 0,71–0,76 (0,63–0,72) | 0,71–0,76 (0,73–0,79) |

Nach Abstand zur Zellgrenze: < 0,25 px 0,52–0,54, ≥ 2 px 0,92–0,95 (alt 0,85–0,91).

**Vergleich mit der Vorhersage.** Exakt layer_s 0,73 (Lauf) / 0,74 (Auswertung): unterer Rand der Spanne
0,74–0,80, knapp. `near` 0,88–0,90: getroffen. Münzwurf an der Grenze: getroffen. Formeffekt „höchstens 0,10
unter dem Würfel“: verfehlt; T liegt 0,07–0,12 darunter, L 0,11–0,18, U 0,12–0,16.

**Schluss.** Der Schwerpunkt als Ziel hilft allen vier Netzen um 0,04–0,05 exakt, und der Formeffekt
schrumpft von bis zu 0,29 auf bis zu 0,18. Er verschwindet nicht. Das Bild je Form ist uneinheitlich: T
gewinnt am meisten (+0,19), obwohl sein Ursprung am wenigsten neben dem Schwerpunkt lag; L gewinnt wenig, U
gar nicht. Der Abstand Ursprung → Schwerpunkt erklärt den Formeffekt also nur zum Teil; bei L und U ist auch
der Schwerpunkt ein Punkt, der aus dem Bild schwer genau zu lesen ist (er liegt neben oder außerhalb des
Materials). Geprüft ist diese Deutung nicht. Einschränkung: Die Szenen sind neu gewürfelt, der Vergleich
alt / neu ist nicht szenengleich. Zusammen mit dem Eintrag zum Populations-Code: Kodierung (+0,07–0,13 mit
`_hot`) und Bezugspunkt (+0,04–0,05) sind zwei getrennte Anteile; ob sie sich addieren, ist nicht gemessen
(`robot_finds_c_f32_hot` gibt es, ist aber nicht gelaufen).

**Belege.** `results/finds_c.jsonl`, `results/finds_error.jsonl`, `results/finds_cell.jsonl`; Worker-Job
`finds_c` (Commit 08efb9d); `data/robot/gazeshapec_*.npz` (nicht im Repo).

## 2026-11-14 — Schwerpunkt und ein Ausgang je Wert zusammen (`robot_finds_c_f32_hot`)

**Frage.** Addieren sich die Gewinne aus der Kodierung (+0,07–0,13) und aus dem Bezugspunkt (+0,04–0,05)?

**Gemacht.** `robot_finds_c_f32_hot`, 24000 Updates, vier Netze mit Zeigebild, Seeds 0–2. Vorhersage vor dem
Lauf (wörtlich aus „Laufend / offen“):

> - Schwerpunkt-Szenen mit einem Ausgang je Wert (`robot_finds_c_f32_hot`, Netze und Seeds wie oben): Addieren
> sich Kodierung (+0,07–0,13) und Bezugspunkt (+0,04–0,05)?
> **Vorhersage vor dem Lauf (2026-11-14):** Ungefähr additiv: exakt 0,75–0,84 über die vier Netze, layer_s
> 0,80–0,84; richtiger Körper 0,93–0,97; verloren höchstens 0,03. L und U bleiben mindestens 0,08 unter dem
> Würfel, an der Zellgrenze (< 0,25 px) bleibt es bei 0,50–0,60.

**Ergebnis.** Exakt in den vier Kombinationen (`scripts/finds_error_eval.py`):

| Netz | Ursprung, Bits | Ursprung, `_hot` | Schwerpunkt, Bits | Schwerpunkt, `_hot` | richtiger Körper | verloren |
|---|---|---|---|---|---|---|
| layer_s+cell | 0,70 | 0,77 | 0,74 | 0,81 | 0,96 | 0,02 |
| cnn | 0,66 | 0,79 | 0,71 | 0,80 | 0,94 | 0,02 |
| vit | 0,65 | 0,72 | 0,69 | 0,78 | 0,94 | 0,02 |
| hier_s+cell | 0,63 | 0,71 | 0,68 | 0,76 | 0,93 | 0,03 |

Exakt unter „gefunden“ (`scripts/finds_cell_eval.py`): Würfel 0,86–0,90, Kreuz 0,86–0,89, T 0,81–0,84,
L 0,77–0,81, U 0,76–0,81; Abstand zur Zellgrenze < 0,25 px 0,54–0,57, ≥ 2 px 0,96–0,98. Der falsche Körper
wird in 0,02–0,04 gewählt.

**Vergleich mit der Vorhersage.** Alle Punkte getroffen: exakt 0,76–0,81 (Spanne 0,75–0,84), layer_s 0,81,
richtiger Körper 0,93–0,96, verloren 0,02–0,03, L und U 0,08–0,11 unter dem Würfel, Zellgrenze 0,54–0,57.

**Schluss.** Die beiden Anteile addieren sich ungefähr (cnn etwas weniger). Die Formsuche auf den inneren
Szenen liegt damit bei 0,76–0,81 exakt statt 0,63–0,70. Was übrig bleibt, ist benannt: die Zellgrenze (weit
weg von ihr trifft das Netz in 0,96–0,98 die richtige Zelle), ein Rest Formeffekt bei L und U und 0,02–0,04
falscher Körper.

**Belege.** `results/finds_c.jsonl`, `results/finds_error.jsonl`, `results/finds_cell.jsonl`; Worker-Job
`finds_c_hot` (Commit a322c18).

## 2026-11-14 — Schritt-Aufgaben auf den Populations-Code umgestellt; Wahl der Glockenbreite

**Frage.** Auftrag des Nutzers: Schritt-Aufgaben auf die neue Kodierung umstellen. Welche der drei Varianten
(Glocke Breite 1, Glocke Breite 0,5, ein Ausgang je Wert)?

**Gemacht.** Auswahl auf den Abstimm-Seeds 5 und 6. Regel und Vorhersage vor dem Lauf (wörtlich aus „Laufend
/ offen“):

> - Auftrag des Nutzers (2026-11-14): Schritt-Aufgaben auf die neue Kodierung umstellen. Vorher Wahl der
> Kodierung auf den Abstimm-Seeds 5 und 6: `_pop` (Glocke, Breite 1 Zelle), `_p05` (Breite 0,5: Nachbar 0,14
> statt 0,61) und `_hot` auf servo (5 Netze, 1500 Updates), robot_findc (4 Netze) und robot_finds_in_f32
> (4 Netze, je 24000 Updates). **Regel, vorab festgelegt:** Es gewinnt die Kodierung mit der höchsten exakten
> Wertung, gemittelt erst über die Netze je Aufgabe, dann über die drei Aufgaben. Liegen zwei innerhalb 0,02,
> entscheidet `near` im selben Mittel.
> **Vorhersage vor dem Lauf (2026-11-14):** `_p05` gewinnt: auf den Roboter-Aufgaben exakt innerhalb ±0,03
> von `_hot`, auf servo wie `_pop` (layer_s, hier_s, mlp mindestens 0,85; `_hot` dort im Mittel mindestens
> 0,15 darunter).

**Ergebnis.** Exakt / `near`, Mittel über die Netze je Aufgabe:

| Aufgabe | `_pop` (Breite 1) | `_p05` (Breite 0,5) | `_hot` |
|---|---|---|---|
| servo (5 Netze, 1500 Updates) | 0,83 / 0,91 | 0,63 / 0,80 | 0,49 / 0,70 |
| robot_findc (4 Netze) | 0,57 / 0,90 | 0,65 / 0,88 | 0,64 / 0,84 |
| robot_finds_in_f32 (4 Netze) | 0,67 / 0,96 | 0,74 / 0,96 | 0,75 / 0,95 |
| Mittel der drei Aufgaben | 0,691 / 0,922 | 0,673 / 0,877 | 0,627 / 0,831 |

servo je Netz (exakt): mlp 0,93 / 0,35 / 0,17; layer_s 0,96 / 0,86 / 0,78; vit 1,00 / 0,96 / 0,54; hier_s
0,99 / 0,98 / 0,94; cnn 0,28 / 0,00 / 0,00.

**Vergleich mit der Vorhersage.** Verfehlt: Es gewinnt `_pop`, nicht `_p05`. Richtig war, dass `_p05` auf den
Roboter-Aufgaben exakt wie `_hot` liegt (±0,01); falsch, dass es auf servo wie `_pop` lernt (mlp 0,35, cnn
0,00).

**Schluss.** Nach der Regel: `_pop` und `_p05` liegen exakt innerhalb 0,02, `near` entscheidet für `_pop`.
`STEP_SIGMA = 1.0`. Das ist ein Tausch, kein klarer Sieg: Die breite Glocke lernt servo in 1500 Updates
deutlich besser und landet öfter in der Nachbarzelle statt weit weg, kostet aber auf den beiden
Roboter-Aufgaben 0,07–0,08 exakt gegenüber `_p05` / `_hot`. Die Entscheidung hängt an der servo-Messung nach
nur 1500 Updates (Lerntempo); bei längeren Läufen kann das Bild anders sein. Die Breite ist eine Konstante
(`netresearch/tasks/servo.py`), `*_p05` und `*_hot` bleiben als Varianten für vier Aufgaben.

Umgestellt (Register `netresearch/tasks/registry.py`, `STEP_TASKS`): servo, robot_gaze, robot_reach,
robot_reach_big, robot_find, robot_findc, robot_findi, robot_finds, robot_finds_f32, robot_finds_in*,
robot_finds_c*. 32 Ausgänge im Symbol-Bereich (26–58), gelesen wird der stärkste Ausgang je Achse, Wertung
= beide Achsen richtig; `near` und `step_err` wie bisher. Die alte Form heißt `<name>_bits` (Bezug für alle
Zahlen vor diesem Eintrag; gespeicherte Netze lokal nach `results/checkpoints/<name>_bits` verschoben, sie
liefern dort die alten Zahlen). Nicht umgestellt: die Hilfsaufgaben `*_parts` (liegen im selben Bereich, drei
Schritte passen nicht hinein; gemeinsame Lehrpläne nur mit `<name>_bits`, sonst bricht der Lehrplan mit
Hinweis ab) und die Anpassungs-Studien (`adapt`, `fastweights`, `library`, `context`: eigene Bit-Ausgabe der
Servo-Geräte). Auswerteskripte und GUI lesen beide Kodierungen über `decode_step`.

**Belege.** `results/step_code_tune.jsonl`, `results/step_code_tune_finds.jsonl`; Worker-Jobs `tune_servo`,
`tune_findc`, `tune_finds` (Commit 1316b69).

## 2026-11-14 — Neuberechnung der Schritt-Aufgaben im Populations-Code

**Frage.** Wie sehen die Schritt-Aufgaben der Leiter nach der Umstellung aus, Netz für Netz gegen die
Bit-Werte?

**Gemacht.** 13 Worker-Jobs (Commit dd11d68), Seeds 0–2, gleiche Netze und Update-Zahlen wie die Bezugsläufe.
Vorhersage vor dem Lauf (wörtlich aus „Laufend / offen“):

> - Neuberechnung der Schritt-Aufgaben im Populations-Code, Seeds 0–2, gleiche Netze und Update-Zahlen wie die
> Bezugsläufe in Bits: servo, robot_gaze, robot_reach (je 6000), robot_find (6000), robot_findc, robot_findi
> (24000); als Lehrplan mit gespeicherten Netzen robot_reach, robot_reach_big, robot_finds, robot_finds_f32,
> robot_finds_in, robot_finds_in_f32, robot_finds_c_f32 (je 24000). Nicht neu gerechnet: Größen-Studie,
> langsame Gitter, `in12`, Lehrpläne mit `*_parts`.
> **Vorhersage vor dem Lauf (2026-11-14):** (1) Kein Netz fällt auf einer Aufgabe exakt um mehr als 0,03
> unter seinen Bit-Wert. (2) servo nach 6000 Updates: alle Netze außer cnn mindestens 0,95; cnn unter 0,6.
> (3) Roboter-Aufgaben: `near` steigt bei jedem Netz, das in Bits exakt über 0,2 lag, um mindestens 0,05;
> exakt steigt im Mittel über die Netze um 0,03–0,12. (4) Gitter-Netze (layer_s, hier_s) gewinnen exakt mehr
> als cnn und vit. (5) robot_reach_big bleibt exakt unter 0,75 (die Greif-Decke war großteils Zellgrenze,
> nicht Kodierung).

**Ergebnis.** Exakt neu (in Klammern Bits), dann `near` neu. Vollständige Tabelle mit allen Netzen:
`results/step_pop_compare.json`.

| Aufgabe (Updates) | cnn | vit | layer_s | hier_s | `near` neu |
|---|---|---|---|---|---|
| servo (6000) | 1,00 (0,99) | 1,00 (1,00) | 1,00 (0,99) | 1,00 (0,92) | 1,00 |
| robot_gaze (6000) | 0,99 (0,98) | 0,96 (0,97) | 0,97 (0,98) | 0,94 (0,93) | 0,99–1,00 |
| robot_reach (24000) | 0,29 (0,09) | 0,29 (0,15) | 0,31 (0,12) | 0,25 (0,08) | 0,80–0,87 |
| robot_reach_big (24000) | 0,52 (0,21) | 0,51 (0,33) | 0,49 (0,25) | 0,41 (0,18) | 0,94–0,97 |
| robot_find (6000; +cmd / +cell) | 0,74 (0,72) | 0,58 (0,54) | 0,66 (0,53) | 0,52 (0,34) | 0,91–0,99 |
| robot_findc (24000; +cmd / +cell) | 0,68 (0,63) | 0,63 (0,65) | 0,59 (0,45) | 0,42 (0,26) | 0,82–0,94 |
| robot_findi (24000; +ref) | 0,67 (0,52) | 0,56 (0,58) | – | – | 0,88–0,93 |
| robot_finds (24000; +ref) | 0,17 (0,07) | 0,16 (0,06) | 0,26 (0,09) | 0,19 (0,07) | 0,46–0,59 |
| robot_finds_f32 (+ref+rez3) | 0,37 (0,20) | 0,36 (0,35) | 0,43 (0,30) | 0,33 (0,23) | 0,67–0,75 |
| robot_finds_in (+ref) | 0,57 (0,45) | 0,43 (0,30) | 0,54 (0,47) | 0,47 (0,38) | 0,80–0,91 |
| robot_finds_in_f32 (+ref+rez3) | 0,72 (0,66) | 0,61 (0,65) | 0,70 (0,70) | 0,62 (0,63) | 0,94–0,97 |
| robot_finds_c_f32 (+ref+rez3) | 0,76 (0,72) | 0,64 (0,69) | 0,74 (0,73) | 0,68 (0,69) | 0,94–0,97 |

Weitere Netze: servo mlp 1,00 (0,25), lstm 1,00 (0,61), layer_i 1,00 (0,75), gru 1,00 (0,87), esn 0,01
(0,01). robot_gaze mlp 0,57 (0,36), esn 0,40 (0,09), vitmem 0,93 (0,97). robot_findc mlp+cmd 0,21 (0,09),
vitmem+cmd 0,56 (0,61). Einige Bit-Bezugswerte bei 6000 Updates haben nur einen Seed (cnn, vit auf servo
und robot_gaze; fast alle auf robot_reach). `near` in Bits liegt nur für wenige alte Läufe vor (robot_findc
hier_s 0,62 → 0,82; robot_finds_c_f32 0,88–0,90 → 0,94–0,97; robot_reach_big aus `results/step_error.jsonl`
0,79–0,87 → 0,94–0,97).

**Vergleich mit der Vorhersage.** (1) Verfehlt: vier Fälle fallen um 0,04–0,05 (vitmem+cmd auf robot_findc,
vit auf robot_finds_c_f32 und robot_finds_in_f32, vitmem auf robot_gaze). (2) Verfehlt: Auf servo erreichen
alle Netze 1,00, auch cnn; nur esn bleibt bei 0,01. (3) Exakt im Mittel je Aufgabe: +0,05 bis +0,14 auf den
meisten, +0,22 auf robot_reach_big, ±0,00 auf robot_finds_in_f32 und robot_finds_c_f32; die Spanne 0,03–0,12
trifft also nur teilweise. `near` war mangels alter Werte nur in drei Fällen prüfbar, dort +0,06 bis +0,20.
(4) Teilweise: Gitter gewinnen auf robot_find und robot_findc mehr als cnn und vit, auf robot_reach und
robot_findi gewinnt cnn am meisten. (5) Getroffen: robot_reach_big exakt 0,41–0,52.

**Schluss.** (a) Die Umstellung hebt fast überall die exakte Wertung, am stärksten dort, wo Netze in Bits
schwach waren (Greifen, alte Suchszenen, mlp / lstm / gru). (b) vit und vitmem sind die Ausnahme: Sie kamen
mit den Bits gut zurecht und verlieren mit der breiten Glocke bis 0,05; die Reihenfolge der Netze verschiebt
sich damit zugunsten von cnn und den Gittern. Ein Teil der früheren „vit vorn“-Befunde auf Schritt-Aufgaben
war also ein Vorteil beim Bit-Kodieren, nicht beim Sehen. (c) servo trennt bei 6000 Updates nicht mehr: alle
lernenden Netze stehen auf 1,00. Als Stufe der Leiter taugt servo nur noch mit weniger Updates (bei 1500
trennt es: cnn 0,22, mlp 0,96) oder als Tempo-Maß. (d) Greifen: `near` 0,94–0,97 bei exakt 0,41–0,52 auf
robot_reach_big; der richtige Bereich wird fast immer getroffen, es fehlt die eine Zelle (Zellgrenze, zwei
Körper im Spiel). (e) Auf den inneren Szenen mit feinem Bild ändert die breite Glocke exakt nichts (dort
hatte `_hot` +0,07–0,13 gebracht); das ist der Preis der Wahl von Breite 1.

**Belege.** `results/step_pop.jsonl`, `results/step_pop_cur.jsonl`, `results/step_pop_compare.json`;
Bezugsläufe in `results/servo_arch.jsonl`, `gap.jsonl`, `new3.jsonl`, `robot.jsonl`, `reach_read.jsonl`,
`finds_res.jsonl`, `finds_c.jsonl`, `grid_slow.jsonl`, `pop_findc.jsonl`.

## 2026-11-15 — Schritt-Aufgaben mit Glockenbreite 0,5; servo als Stufe mit 1500 Updates

**Frage.** Was ändert die schmalere Glocke (0,5 statt 1 Zelle) Netz für Netz, und trennt servo mit 1500
Updates wieder?

**Gemacht.** 14 Worker-Jobs (Commit eff150a), Seeds 0–2, gleiche Netze und Update-Zahlen wie die
Neuberechnung mit Breite 1; servo mit 1500 und mit 6000 Updates (13 Netze). Vorhersage vor dem Lauf
(wörtlich aus „Laufend / offen“):

> - Entscheidung des Nutzers (2026-11-14): Glockenbreite 0,5 statt 1 (`STEP_SIGMA = 0.5`), und servo als Stufe
>   mit 1500 statt 6000 Updates (bei 6000 trennt es nicht mehr). Neuberechnung wie im vorigen Eintrag, Seeds
>   0–2; servo zusätzlich mit 1500 Updates. Netze mit Breite 1 lokal in `results/checkpoints/<name>_pop1`.
>   **Vorhersage vor dem Lauf (2026-11-14):** (1) Gegenüber Breite 1 exakt +0,05 bis +0,10 im Mittel der Netze
>   auf robot_find, robot_findc, robot_findi und allen robot_finds*; `near` dort −0,00 bis −0,04. (2) vit und
>   vitmem liegen auf keiner Aufgabe mehr als 0,03 unter ihrem Bit-Wert. (3) robot_reach_big exakt 0,50–0,62.
>   (4) servo bei 1500 Updates trennt: vit, hier_s, layer_s mindestens 0,85; mlp 0,2–0,5; cnn unter 0,1; bei
>   6000 Updates alle außer esn mindestens 0,98. (5) robot_gaze: kein Netz ändert sich um mehr als 0,03
>   gegenüber Breite 1, außer mlp / esn / gru / lstm (die fallen um bis zu 0,15).

**Ergebnis.** Exakt, Mittel über 3 Seeds; Änderung gegenüber Breite 1, Bit-Werte in Klammern.

| Aufgabe | exakt mit Breite 0,5 | exakt gegen Breite 1 | `near` gegen Breite 1 |
|---|---|---|---|
| servo, 1500 Updates | vit, vitmem, attnmem 1,00; layer_i 0,97; hier_s 0,96; layer_s_sp4 0,93; layer_s 0,92; layer_s_am4 0,90; gru 0,55; mlp 0,40; lstm 0,37; cnn 0,01; esn 0,00 | – | – |
| servo, 6000 Updates | alle 1,00 außer esn 0,01 | ±0,00 | ±0,00 |
| robot_gaze | cnn 0,99; vit 0,98; layer_s 0,98; vitmem 0,97; hier_s 0,96; layer_i 0,91; attnmem 0,64; mlp 0,55; gru 0,51; lstm 0,49; esn 0,37 | +0,00 bis +0,04, attnmem +0,06; mlp −0,01, esn −0,03 | −0,00 bis −0,06 |
| robot_reach (6000 / 24000) | 0,21–0,29 (Bits 0,08–0,15) | **−0,01 bis −0,05**, nur vitmem bei 24000 +0,02 | −0,01 bis −0,08 |
| robot_reach_big | cnn 0,52; vit 0,50; vitmem 0,50; layer_s 0,48; hier_s 0,41 (Bits 0,18–0,33) | −0,02 bis +0,01, vitmem +0,04 | −0,00 bis −0,02 |
| robot_find | cnn+cmd 0,78; layer_s_sp4+cell 0,72; layer_s+cell 0,71; vit+cmd 0,67; hier_s+cmd 0,61 (Bits 0,34–0,72) | +0,04 bis +0,09 | −0,00 bis −0,02 |
| robot_findc | cnn+cmd 0,77; vit+cmd 0,72; layer_s_sp4+cmd 0,69; vitmem+cmd 0,67; layer_s+cell 0,66; hier_s+cell 0,49 | +0,07 bis +0,11; mlp / gru / lstm +0,03 | −0,01 bis −0,04; mlp / gru / lstm −0,05 bis −0,07 |
| robot_findi | cnn+ref 0,71; cnn+cmd 0,67; vit+ref 0,65; vit+cmd 0,65; layer_s_sp4+cell+ref 0,62 | +0,04 bis +0,09 | −0,01 bis −0,02 |
| robot_finds | layer_s_sp4 0,29; layer_s 0,28; vit 0,20; cnn 0,19; hier_s 0,19 (Bits 0,06–0,09) | +0,01 bis +0,04 | −0,02 bis −0,06 |
| robot_finds_f32 | layer_s 0,47; vit 0,46; cnn 0,43; hier_s 0,37 | +0,04 bis +0,10 | −0,04 bis +0,03 |
| robot_finds_in | cnn 0,61; layer_s 0,61; layer_s_sp4 0,61; hier_s 0,54; vit 0,48 | +0,04 bis +0,07 | −0,03 bis +0,00 |
| robot_finds_in_f32 | cnn 0,78; layer_s 0,77; hier_s 0,70; vit 0,70 (Bits 0,63–0,70) | +0,07 bis +0,09 | −0,01 bis +0,00 |
| robot_finds_c_f32 | layer_s 0,80; cnn 0,79; vit 0,77; hier_s 0,76 (Bits 0,69–0,73) | +0,04 bis +0,13 | −0,01 bis +0,02 |

vit und vitmem liegen jetzt auf jeder Aufgabe auf oder über ihrem Bit-Wert (+0,00 bis +0,15); gegenüber
Breite 1 gewinnen sie am meisten (robot_findc +0,09 / +0,11, robot_finds_c_f32 +0,13). Rangkorrelation
servo (1500 Updates) gegen robot_gaze über 13 Netze: +0,27; ohne cnn +0,53.

**Vergleich mit der Vorhersage.** (1) Großteils getroffen: Suchaufgaben exakt +0,04 bis +0,11 für die
lernenden Netze, `near` −0,00 bis −0,04. Daneben: robot_finds (alte Szenen, grobes Bild) nur +0,01 bis
+0,04 bei `near` bis −0,06; vit auf robot_finds_c_f32 +0,13; die schwachen Netze auf robot_findc nur +0,03.
(2) Getroffen: vit / vitmem nirgends unter dem Bit-Wert. (3) Verfehlt für zwei von fünf Netzen: layer_s
0,48, hier_s 0,41; die Breite ändert robot_reach_big praktisch nicht. (4) Getroffen: vit 1,00, hier_s 0,96,
layer_s 0,92, mlp 0,40, cnn 0,01; bei 6000 alle außer esn 1,00. (5) Verfehlt: vitmem und layer_i +0,04,
attnmem +0,06; mlp / esn / gru / lstm fallen nicht um bis zu 0,15, sondern ändern sich um −0,03 bis +0,01.
Nicht vorhergesagt: robot_reach wird mit der schmalen Glocke schlechter (exakt −0,01 bis −0,05).

**Schluss.** (a) Breite 0,5 ist auf allen Suchaufgaben die bessere Wahl und hebt den Nachteil von vit /
vitmem gegenüber den Bits auf; die Verschiebung der Rangfolge zugunsten von cnn und den Gittern, die Breite 1
zeigte, war zum Teil eine Folge der breiten Glocke. (b) Der Preis liegt dort, wo die Netze ungenau sind:
auf robot_reach (mittlerer Fehler über eine Zelle) kostet die schmale Glocke exakt bis 0,05 und `near` bis
0,08, auf robot_finds `near` bis 0,06. Die breite Glocke hilft, solange das Netz den Ort nur ungefähr kennt.
(c) servo trennt mit 1500 Updates wieder, misst aber Lerntempo: cnn 0,01 nach 1500 und 1,00 nach 6000
Updates. Als Sieb für robot_gaze taugt es damit nicht (cnn ist dort das beste Netz).
(d) Die besten Werte der Formsuche: innere Szenen 0,78 (cnn), mit Schwerpunkt 0,80 (layer_s); das entspricht
den `_hot`-Werten vom Vortag (0,76–0,81).

**Belege.** `results/step_p05.jsonl`, `results/step_p05_cur.jsonl`, `results/step_p05_compare.json`
(je Netz: Breite 0,5, Breite 1, Bits); Breite 1 in `results/step_pop*.jsonl`. Netze in
`results/checkpoints/<Aufgabe>`, die mit Breite 1 lokal in `<Aufgabe>_pop1`.

## 2026-11-15 — Formsuche in der Schleife: Der Blickschritt wird ausgeführt

**Frage.** Sagen die Einzelschritt-Zahlen der Formsuche vorher, ob der Blick in der Schleife auf dem
gesuchten Körper landet und dort bleibt?

**Gemacht.** Export im Roboter-Projekt um `--images` erweitert: Die Testszenen von `gazeshapec` werden mit dem
ganzen Kamerabild gespeichert (240 × 240 und 480 × 480; die ersten 1500 Szenen, identisch mit dem bisherigen
Testsatz). `netresearch/tasks/fovea.py` tastet daraus die Fovea an jedem Blickpunkt neu ab, eine Kopie der
Geometrie des Roboters, bitgenau gegen die exportierten Bilder geprüft (auch im Test). Ein Schritt (dx, dy)
verschiebt den Blick so, dass der Abtastpunkt der gewählten Zelle auf den der Mittelzelle fällt.
`scripts/finds_loop_eval.py`: gespeicherte Einzelschritt-Netze von `robot_finds_c_f32` (Breite 0,5, Seeds
0–2), nichts trainiert, kein Gedächtnis zwischen den Schritten; 1500 Szenen × 3 Körper, 4 Schritte, das
Zeigebild bleibt gleich. „Orakel“ nimmt jedes Mal den wahren Schritt. Vorhersage vor dem Lauf (wörtlich
aus „Laufend / offen“, Commit 1549e56):

> - Formsuche in der Schleife (Auftrag Nutzer 2026-11-15): Der Blickschritt des Netzes wird ausgeführt, das
>   nächste Bild kommt vom neuen Blickpunkt (`netresearch/tasks/fovea.py` tastet das Kamerabild wie der Roboter
>   ab, bitgenau gegen die exportierten Bilder geprüft; `scripts/finds_loop_eval.py`). Gespeicherte
>   Einzelschritt-Netze von `robot_finds_c_f32` (Breite 0,5, Seeds 0–2), nichts wird trainiert; 1500 Testszenen
>   × 3 Körper, 4 Schritte. Vorab bekannt (40 Szenen, nur Geometrie, kein Netz): Ein wahrer Schritt landet nur
>   in 0,62 der Fälle in der Mittelzelle, weil die Zellen ab 5 Zellen neben der Mitte gröber werden.
>   **Vorhersage vor dem Lauf (2026-11-15):** (1) Nach Schritt 1 exakt (Körper in der Mittelzelle) 0,45–0,60,
>   `near` 0,92–0,97. (2) Nach den Schritten 2–4 exakt 0,60–0,75 und zwischen Schritt 2 und 4 nicht mehr
>   steigend (Änderung unter 0,03); `near` 0,92–0,97; Median-Abstand höchstens 2,5 px. (3) Die Netze pendeln:
>   bei Schritt 3 und 4 ist der Schritt in 0,10–0,25 der Läufe die genaue Umkehr des vorigen. (4) Blick auf dem
>   falschen Körper: 0,02–0,06, über die Schritte gleichbleibend (Änderung unter 0,02); Blick aus dem Bild
>   unter 0,01. (5) Für die Prognose-Kette: `near` des Einzelschritts sagt `near` nach 4 Schritten auf ±0,03
>   vorher, je Netz; die Reihenfolge der vier Netze bleibt die des Einzelschritts, Abstand der Netze nach 4
>   Schritten höchstens 0,05 in exakt. (6) Orakel (wahrer Schritt): nach 2 Schritten exakt mindestens 0,97.

**Ergebnis.** Mittel über 3 Seeds, nach Schritt 1 / 2 / 3 / 4.

| | exakt (Körper in der Mittelzelle) | `near` (höchstens eine Zelle) | Blick auf falschem Körper | Median-Abstand px |
|---|---|---|---|---|
| Orakel | 0,67 / 1,00 / 1,00 / 1,00 | 0,99 / 1,00 / 1,00 / 1,00 | 0 | 1,8 / 1,5 / 1,5 / 1,5 |
| cnn | 0,54 / 0,48 / 0,59 / 0,53 | 0,95 / 0,86 / 0,90 / 0,88 | 0,03 / 0,10 / 0,06 / 0,09 | 2,0 / 2,2 / 1,8 / 2,0 |
| layer_s | 0,54 / 0,32 / 0,44 / 0,36 | 0,96 / 0,68 / 0,78 / 0,67 | 0,03 / 0,25 / 0,11 / 0,22 | 2,0 / 2,9 / 2,3 / 2,8 |
| vit | 0,51 / 0,28 / 0,42 / 0,34 | 0,94 / 0,60 / 0,77 / 0,63 | 0,04 / 0,29 / 0,12 / 0,26 | 2,1 / 3,7 / 2,5 / 3,2 |
| hier_s | 0,50 / 0,22 / 0,34 / 0,28 | 0,94 / 0,57 / 0,68 / 0,57 | 0,04 / 0,33 / 0,17 / 0,30 | 2,1 / 4,3 / 3,0 / 3,9 |

Der Blick verlässt das Kamerabild nie. Das Netz antwortet „bleib“ (0, 0) bei Schritt 2 in 0,14–0,31 der Läufe
(richtig wäre es in etwa 0,55), bei Schritt 4 in 0,27–0,53. Genaue Umkehr des vorigen Schritts: bei Schritt 3
und 4 in 0,09–0,15.
Diagnose (300 Szenen, Seed 0): Liegt der Körper nach Schritt 1 in der Mittelzelle, macht vit in 0,40 der
Läufe einen Schritt von 5 oder mehr Zellen (cnn 0,12); nach solchen großen Schritten liegt der Blick in
0,69–0,79 auf einem anderen Körper. **Im Trainingssatz liegt der gesuchte Körper nie in der Mitte:** Anteil
der Ziele mit größtem Schritt 0 / 1 / 2 / 3 / 4 / 5 Zellen: 0,000 / 0,002 / 0,019 / 0,076 / 0,215 / 0,687
(der Blick liegt beim Export nahe am Schwerpunkt der drei Körper, die mindestens 60 mm auseinanderliegen).

**Vergleich mit der Vorhersage.** (1) Getroffen: nach Schritt 1 exakt 0,50–0,54, `near` 0,94–0,96.
(2) Verfehlt: exakt nach den Schritten 2–4 0,22–0,59 statt 0,60–0,75, und es schwankt mit dem Schritt
(gerade Schritte schlechter); `near` 0,57–0,90; Median-Abstand nur bei cnn und layer_s (ungerade Schritte)
unter 2,5 px. (3) Großteils getroffen: Umkehr 0,09–0,15 (hier_s bei Schritt 4 mit 0,09 knapp darunter).
(4) Verfehlt, und das ist der Hauptbefund: falscher Körper nach Schritt 2 in 0,10–0,33 statt gleichbleibend
0,02–0,06. (5) Verfehlt: `near` des Einzelschritts (0,95–0,97) sagt `near` nach 4 Schritten nicht vorher
(cnn 0,88, die anderen 0,57–0,67); die Reihenfolge ändert sich (Einzelschritt layer_s 0,80, cnn 0,79, vit
0,77, hier_s 0,76; Schleife cnn weit vorn), Abstand 0,25 statt höchstens 0,05. (6) Getroffen: Orakel 1,00
nach 2 Schritten.

**Schluss.** (a) Der erste Schritt hält, was die Einzelschritt-Zahl verspricht. Danach verlassen die Netze
den Körper wieder: Den Zustand „ich sehe ihn schon an“ gibt es im Trainingssatz nicht, also haben sie nie
gelernt zu bleiben. Das ist eine Lücke der Aufgabe, kein Unvermögen der Netze – geprüft ist das aber erst,
wenn Netze mit solchen Szenen trainiert sind. (b) Für die Prognose-Kette: Eine Einzelschritt-Aufgabe sagt
die Schleife nur vorher, wenn ihre Szenen die Zustände enthalten, die die Schleife besucht. Die bisherige
Leiter tat das nicht; die Unterschiede der Netze außerhalb der Trainingsverteilung (cnn robust, vit und
hier_s nicht) waren im Einzelschritt unsichtbar. (c) Die Geometrie selbst erlaubt 1,00 nach zwei Schritten;
ein wahrer Schritt allein trifft die Mittelzelle nur in 0,67, weil die Zellen ab 5 Zellen neben der Mitte
gröber sind – die Schleife ist also nötig, nicht nur Kontrolle. (d) Nächster Schritt: Suchszenen, in denen
der Abstand des gesuchten Körpers zur Mitte gleichmäßig von 0 bis zum Rand reicht (Export-Variante), damit
trainieren, Schleife erneut messen.

**Belege.** `results/finds_loop.jsonl` (je Netz und Seed, Listen über die Schritte);
`scripts/finds_loop_eval.py`, `netresearch/tasks/fovea.py`; Daten `data/robot/gazeshapec_test_img.npz`
(lokal, 124 MB, nicht im Repository).

## 2026-11-15 — Schleife mit Szenen, die das Ziel auch in der Mitte zeigen (`robot_finds_m_f32`)

**Frage.** Bleiben die Netze auf dem gefundenen Körper, wenn das Training den Zustand „ich sehe ihn schon an“
enthält – und sagt der Einzelschritt die Schleife dann vorher?

**Gemacht.** Export-Variante `gazeshapeu` im Roboter-Projekt (Blick hängt an einem Körper, Abstand zur Mitte
gleichmäßig 0–5 Zellen mit Versatz in der Zelle; die zwei anderen irgendwo im Blickfeld). Aufgabe
`robot_finds_m_f32`: 24000 Szenen `gazeshapec` + 24000 `gazeshapeu` (`scripts/merge_robot_sets.py`), Test
1500 + 1500. Vier Netze, 24000 Updates, Seeds 0–2 (Worker, Commit ab03005; der erste Job lief leer durch,
weil die Daten noch nicht synchronisiert waren). Danach `scripts/finds_loop_eval.py --task robot_finds_m_f32`
auf denselben 1500 Startszenen wie im vorigen Eintrag und `scripts/finds_mixed_eval.py` (Einzelschritt je
Szenenart). Vorhersage vor dem Lauf (wörtlich aus „Laufend / offen“):

> - Formsuche in der Schleife mit Szenen, die das Ziel auch in der Mitte zeigen (Auftrag Nutzer 2026-11-15).
>   Neue Export-Variante `gazeshapeu`: Der Blick hängt an einem Körper, dessen Abstand zur Mitte gleichmäßig 0–5
>   Zellen ist (je etwa ein Sechstel, mit Versatz in der Zelle); die anderen zwei liegen irgendwo im Blickfeld
>   (Probe: zu 90 % in den groben Ringen 6–8). Aufgabe `robot_finds_m_f32`: 24000 Szenen `gazeshapec` + 24000
>   `gazeshapeu` (gleiche Gesamtzahl wie bisher), Test 1500 + 1500. Gleiche vier Netze, 24000 Updates, Seeds
>   0–2; danach dieselbe Schleife auf denselben 1500 Startszenen wie im vorigen Eintrag.
>   **Vorhersage vor dem Lauf (2026-11-15):** (1) Schleife, `near` nach 4 Schritten: jedes Netz mindestens
>   0,90, cnn 0,93–0,97; `near` fällt von Schritt 1 zu Schritt 2 um höchstens 0,03. (2) Exakt nach den
>   Schritten 2–4: 0,65–0,85 (Rest ist die Zellgrenze: der Körper liegt irgendwo in der Mittelzelle). (3) Blick
>   auf dem falschen Körper höchstens 0,06 bei jedem Schritt; „bleib“ bei Schritt 4 in mindestens 0,55 der
>   Läufe. (4) Abstand zwischen bestem und schlechtestem Netz in `near` nach 4 Schritten höchstens 0,06.
>   (5) Einzelschritt auf den alten Testszenen (`gazeshapec`): exakt höchstens 0,05 unter den bisherigen
>   0,76–0,80. (6) Einzelschritt auf den neuen Szenen: Körper am Blick (Abstand 0–5) `near` mindestens 0,93;
>   die zwei Körper im groben Rand exakt nur 0,25–0,50.

**Ergebnis.** Schleife, Mittel über 3 Seeds, nach Schritt 1 / 2 / 3 / 4; in Klammern der Wert nach Schritt 4
mit den alten Netzen (`robot_finds_c_f32`).

| | `near` | exakt | falscher Körper | „bleib“ bei Schritt 2 / 3 / 4 |
|---|---|---|---|---|
| cnn | 0,93 / 0,93 / 0,94 / 0,95 (0,88) | 0,50 / 0,65 / 0,68 / 0,69 (0,53) | 0,05 / 0,06 / 0,04 / 0,04 (0,09) | 0,63 / 0,88 / 0,93 |
| layer_s | 0,94 / 0,91 / 0,93 / 0,94 (0,67) | 0,50 / 0,63 / 0,65 / 0,66 (0,36) | 0,04 / 0,07 / 0,05 / 0,05 (0,22) | 0,61 / 0,86 / 0,91 |
| vit | 0,93 / 0,92 / 0,93 / 0,93 (0,63) | 0,49 / 0,63 / 0,65 / 0,66 (0,34) | 0,04 / 0,07 / 0,06 / 0,05 (0,26) | 0,62 / 0,87 / 0,92 |
| hier_s | 0,90 / 0,87 / 0,89 / 0,90 (0,57) | 0,45 / 0,54 / 0,57 / 0,58 (0,28) | 0,07 / 0,11 / 0,09 / 0,09 (0,30) | 0,60 / 0,82 / 0,88 |

Umkehr des vorigen Schritts 0,01 (vorher 0,09–0,15); Median-Abstand nach Schritt 4 1,7–1,9 px (Orakel 1,5).
Einzelschritt (exakt / `near`):

| | alte Szenen (`gazeshapec`, 1500) | Körper am Blick (neu) | davon genau in der Mitte, exakt | zwei Körper im Rand (neu) |
|---|---|---|---|---|
| cnn | 0,75 / 0,94 | 0,63 / 0,90 | 0,90 | 0,50 / 0,73 |
| layer_s | 0,76 / 0,95 | 0,64 / 0,91 | 0,86 | 0,46 / 0,73 |
| vit | 0,75 / 0,94 | 0,61 / 0,89 | 0,90 | 0,50 / 0,77 |
| hier_s | 0,69 / 0,92 | 0,55 / 0,87 | 0,85 | 0,35 / 0,62 |

Liegt der Körper am Blick 1–5 Zellen neben der Mitte, ist der Schritt nur in 0,44–0,71 exakt.

**Vergleich mit der Vorhersage.** (1) Getroffen, knapp: `near` nach 4 Schritten 0,90–0,95 (hier_s genau 0,90),
cnn 0,95; Rückgang von Schritt 1 zu 2 höchstens 0,03. (2) Teilweise: exakt nach den Schritten 2–4 cnn
0,65–0,69, layer_s und vit 0,63–0,66, hier_s 0,54–0,58 (unter der Spanne). (3) Teilweise: falscher Körper bei
cnn höchstens 0,06, bei layer_s und vit 0,07 bei Schritt 2, bei hier_s 0,07–0,11; „bleib“ bei Schritt 4
0,88–0,93 (weit über den vorhergesagten 0,55). (4) Getroffen: Abstand der Netze 0,05. (5) Für drei Netze
getroffen (−0,02 bis −0,04), hier_s verliert 0,07. (6) Verfehlt im ersten Teil: Körper am Blick `near`
0,87–0,91 statt mindestens 0,93; Rand exakt 0,35–0,50 getroffen.

**Schluss.** (a) Die Lücke lag in den Szenen, nicht in den Netzen: Mit dem Ziel auch in der Mitte bleiben alle
vier Netze auf dem Körper; `near` nach vier Schritten steigt von 0,57–0,88 auf 0,90–0,95, das Pendeln
verschwindet. (b) Jetzt sagt der Einzelschritt die Schleife vorher: `near` auf den Startszenen 0,92–0,95,
`near` nach vier Schritten 0,90–0,95, gleiche Reihenfolge, je Netz höchstens 0,02 Unterschied. Bedingung
dafür ist, dass die Einzelschritt-Szenen die Zustände der Schleife enthalten. (c) Die Schleife gewinnt aber
nichts gegenüber dem ersten Schritt: Wer nach Schritt 1 auf dem falschen Körper sitzt (0,04–0,09), bleibt dort,
und exakt bleibt bei 0,58–0,69, obwohl die Geometrie 1,00 erlaubt. Die Netze antworten „bleib“ in 0,9 der
Läufe, auch wenn der Körper eine Zelle daneben liegt: die Zellgrenze entscheidet weiter wie ein Münzwurf.
(d) Preis der Mischung: Auf den alten Szenen exakt −0,02 bis −0,07 bei halb so vielen Szenen dieser Art.
(e) Offen: Der Körper am Blick wird neben der Mitte schlechter getroffen (0,44–0,71 exakt) als auf den
alten Szenen in gleicher Entfernung; nicht untersucht (Kandidaten: zwei Körper im groben Rand, Versatz in
der Zelle).

**Belege.** `results/finds_loop.jsonl` (Zeilen mit `robot_finds_m_f32`), `results/finds_mixed.jsonl`,
`results/finds_loop_train.jsonl`; Netze in `results/checkpoints/robot_finds_m_f32`; Daten
`data/robot/gazeshapem_*.npz`, `gazeshapeu_*.npz` (lokal und in der Freigabe).

## 2026-11-15 — Gedächtnis zwischen den Blickschritten (`robot_loop_f32`)

**Frage.** Korrigiert die Blickschleife, wenn die Netze auf Folgen entlang eines Blicklaufs lernen – und bringt
ein Gedächtnis über die Schritte etwas gegenüber Netzen ohne?

**Gemacht.** Aufgabe `robot_loop_f32` (Folgen von 4 Bildern, Schritte dazwischen von einem verrauschten Lehrer,
`scripts/make_loop_set.py`), 48000 Trainingsfolgen aus 16000 Szenen. Acht Netze, 12000 Updates, Seeds 0–2
(Worker, Commit a681719, 173 Minuten). Danach `scripts/finds_loop_eval.py --task robot_loop_f32` auf denselben
1500 Startszenen wie in den zwei vorigen Einträgen: einmal behalten die Netze ihren Zustand über die Schritte,
einmal wird er vor jedem Schritt gelöscht (`--amnesia`). Vorhersage vor dem Lauf (wörtlich aus „Laufend /
offen“):

> - Gedächtnis zwischen den Blickschritten (Auftrag Nutzer 2026-11-15). Neue Aufgabe `robot_loop_f32`: Folgen
>   von 4 Bildern einer Suchszene entlang eines Blicklaufs (`scripts/make_loop_set.py`: erstes Bild wie
>   `gazeshapec`, danach je ein Schritt eines verrauschten Lehrers – 0,70 wahrer Schritt, 0,20 eine Zelle
>   daneben, 0,10 auf einen der anderen Körper; netz-unabhängig), Ziel an jedem Bild der wahre Schritt vom
>   jetzigen Blick. 16000 Trainingsszenen × 3 Körper = 48000 Folgen (Kamerabilder aus dem Export mit `--images`),
>   Test 4500 Folgen. Netze je `+ref+rez3`: ohne Gedächtnis cnn, vit; mit Gedächtnis layer_s+cell, hier_s+cell,
>   layer_s_sp4+cell, layer_s_am4+cell, vitmem, attnmem. 12000 Updates (Batch 64 Folgen), Seeds 0–2. Gemessen
>   wird die geschlossene Schleife auf den 1500 Startszenen der vorigen Einträge (`finds_loop_eval.py`, Netze
>   behalten ihren Zustand; Gegenprobe `--amnesia`). Hinweis: Wer immer „bleib“ sagt, ist auf den Folgen schon
>   in etwa 0,44 der Bilder exakt; die Folgen-Wertung ist deshalb nicht die Hauptzahl.
>   **Vorhersage vor dem Lauf (2026-11-15):** (1) Die Schleife korrigiert jetzt: bei cnn steigt exakt von
>   Schritt 1 (um 0,50) auf mindestens 0,72 nach Schritt 4, und der Anteil „falscher Körper“ fällt von Schritt 1
>   zu Schritt 4 um mindestens ein Drittel; `near` nach 4 Schritten cnn 0,95–0,98. (2) Gedächtnis bringt in
>   dieser Form nichts Messbares: das beste Netz mit Gedächtnis liegt in `near` nach 4 Schritten innerhalb von
>   ±0,02 um das beste ohne (cnn oder vit), in exakt innerhalb von ±0,03. (3) attnmem liegt in `near` nach 4
>   Schritten mindestens 0,05 unter cnn; vitmem innerhalb von ±0,03 um vit. (4) Gegenprobe: Mit gelöschtem
>   Zustand verlieren die Gitter-Netze (layer_s, hier_s, sp4, am4) in `near` nach 4 Schritten höchstens 0,03 –
>   sie nutzen den Zustand also kaum. (5) layer_s_am4 und layer_s_sp4 sind nicht besser als layer_s (±0,02).

**Ergebnis.** Schleife, Mittel über 3 Seeds. Folgen-Wertung = Anteil exakter Schritte auf den Testfolgen
(„immer bleib“ liegt bei etwa 0,44).

| | Folgen-Wertung | `near` nach Schritt 1 / 2 / 4 | exakt nach Schritt 1 / 2 / 4 | falscher Körper nach Schritt 1 / 4 | gelöschter Zustand: `near` / exakt nach Schritt 4 |
|---|---|---|---|---|---|
| layer_s_sp4 | 0,81 | 0,90 / 0,93 / 0,94 | 0,46 / 0,73 / 0,75 | 0,07 / 0,06 | 0,70 / 0,50 |
| layer_s | 0,81 | 0,90 / 0,93 / 0,93 | 0,46 / 0,72 / 0,74 | 0,07 / 0,07 | 0,70 / 0,50 |
| cnn (ohne Gedächtnis) | 0,79 | 0,87 / 0,91 / 0,93 | 0,45 / 0,72 / 0,75 | 0,09 / 0,07 | 0,93 / 0,75 |
| layer_s_am4 | 0,78 | 0,86 / 0,89 / 0,90 | 0,42 / 0,68 / 0,70 | 0,10 / 0,09 | 0,60 / 0,39 |
| vit (ohne Gedächtnis) | 0,77 | 0,82 / 0,87 / 0,90 | 0,38 / 0,67 / 0,72 | 0,13 / 0,09 | 0,90 / 0,72 |
| hier_s | 0,79 | 0,84 / 0,88 / 0,89 | 0,40 / 0,68 / 0,71 | 0,12 / 0,10 | 0,67 / 0,47 |
| vitmem | 0,75 | 0,73 / 0,80 / 0,82 | 0,31 / 0,61 / 0,65 | 0,20 / 0,17 | 0,72 / 0,51 |
| attnmem | 0,72 | 0,65 / 0,73 / 0,76 | 0,25 / 0,53 / 0,58 | 0,25 / 0,23 | 0,64 / 0,46 |

Spanne über die Seeds in `near` nach Schritt 4 höchstens 0,02 (vit 0,03). Umkehr des vorigen Schritts 0,00–0,01;
kein Lauf verlässt das Bild. „bleib“ bei Schritt 4: 0,93–0,99. Mit gelöschtem Zustand sagen die Netze mit
Gedächtnis bei Schritt 2 nur in 0,25–0,35 „bleib“ (mit Zustand 0,36–0,59), der Anteil „falscher Körper“ steigt
auf 0,22–0,31, Umkehr 0,05–0,09. Zum Vergleich die Einzelschritt-Netze des vorigen Eintrags
(`robot_finds_m_f32`, 24000 Updates, 48000 Szenen): cnn `near` 0,93 / 0,93 / 0,95, exakt 0,50 / 0,65 / 0,69,
falscher Körper 0,05 / 0,04.

**Vergleich mit der Vorhersage.** (1) Teilweise: cnn exakt steigt von 0,45 auf 0,75 (getroffen, Start etwas
unter „um 0,50“); der Anteil „falscher Körper“ fällt bei cnn nur von 0,09 auf 0,07 (ein Viertel, nicht ein
Drittel; bei vit 0,13 auf 0,09, bei den übrigen kaum) – verfehlt; `near` nach 4 Schritten cnn 0,93 statt
0,95–0,98 – verfehlt. (2) Getroffen: bestes Netz mit Gedächtnis (layer_s_sp4) `near` 0,94 gegen cnn 0,93, exakt
0,75 gegen 0,75. (3) attnmem getroffen (0,17 unter cnn); vitmem verfehlt (0,82 gegen vit 0,90, also −0,08).
(4) Klar verfehlt: Mit gelöschtem Zustand verlieren die Gitter-Netze 0,23–0,30 in `near`, nicht höchstens 0,03.
(5) Getroffen: layer_s_sp4 +0,01, layer_s_am4 −0,03 gegenüber layer_s.

**Schluss.** (a) Folgen-Training macht den zweiten Schritt nützlich: exakt steigt von Schritt 1 zu Schritt 2 um
0,26–0,30 bei allen Netzen (vorher 0,09–0,15) und endet bei cnn, layer_s, layer_s_sp4 auf 0,74–0,75 (vorher
höchstens 0,69). Die letzte Zelle wird jetzt öfter nachgeführt; das Orakel liegt aber bei 1,00. (b) Der falsche
Körper wird weiter kaum verlassen (Rückgang höchstens 0,04), obwohl der Lehrer in 0,10 der Schritte genau
dorthin führt und die Folge den Rückweg zeigt. (c) Gedächtnis bringt in dieser Aufgabe keinen Vorteil: Die
besten Netze mit Gedächtnis (layer_s, layer_s_sp4) enden gleich wie cnn; der Vorsprung in `near` nach Schritt 1
(0,90 gegen 0,87) ist ein Einzelschritt-Vorsprung, den es schon ohne Folgen gab. (d) Die Gegenprobe zeigt
trotzdem, dass die Netze den Zustand benutzen – nur nicht als Erinnerung an die Szene: Im Training kommt ein
frischer Zustand nur beim ersten Bild vor, und dort liegt das Ziel nie in der Mitte. Ein frischer Zustand heißt
für sie „erster Schritt, weit springen“; mit gelöschtem Zustand springen sie deshalb vom gefundenen Körper
wieder weg. Der Zustand dient als Schrittzähler, eine Abkürzung aus dem Aufbau des Datensatzes. Die Gegenprobe
misst hier also Abhängigkeit vom Zustand, nicht Nutzen des Gedächtnisses; meine Vorhersage (4) hatte das nicht
bedacht. (e) vitmem und attnmem sind schon im ersten Schritt deutlich schlechter als vit (0,73 und 0,65 gegen
0,82) und holen das nicht auf. (f) Preis des Folgen-Trainings: Der erste Schritt ist schwächer als bei
`robot_finds_m_f32` (cnn `near` 0,87 gegen 0,93, falscher Körper 0,09 gegen 0,05) – ein Drittel der
Startszenen, und nur jedes vierte Bild ist ein Startbild. Deshalb bleibt `near` nach 4 Schritten bei 0,93 statt
0,95. (g) Die Folgen-Wertung ordnet die Netze ähnlich wie die Schleife, überschätzt aber hier_s und trennt
schwächer (0,72–0,81 gegen `near` 0,76–0,94).

**Belege.** `results/finds_loop.jsonl` (Zeilen `robot_loop_f32` und `robot_loop_f32/amnesia`),
`results/finds_loop_train.jsonl`; Netze in `results/checkpoints/robot_loop_f32`; Daten
`data/robot/gazeloop_*.npz` (lokal und in der Freigabe).

## 2026-11-15 — Blickschleife, die ohne Erinnerung nicht lösbar ist (`robot_loop_cue_f32`, `robot_loop_blind_f32`)

**Frage.** Welche Netze behalten über die Blickschritte, welcher Körper gesucht ist, wenn die Vorlage nur einmal
vor dem Lauf gezeigt wird?

**Gemacht.** Zwei Aufgaben auf den Folgen von `robot_loop_f32` (5 Schritte): Vorlage nur an einem
Hinweis-Schritt vor dem Lauf, danach leer. `cue`: Hinweis-Schritt mit erstem Bild; `blind`: Hinweis-Schritt nur
mit Vorlage, Bild leer. Acht Netze, 12000 Updates, Seeds 0–2 (Worker, Commit a48b5a6, zwei Jobs). Danach
`scripts/finds_loop_eval.py` auf den 1500 Startszenen (Hinweis-Schritt, dann 4 Schritte ohne Vorlage), je mit
behaltenem und gelöschtem Zustand. Vorhersage vor dem Lauf (wörtlich aus „Laufend / offen“):

> - Blickschleife, die ohne Erinnerung nicht lösbar ist (Auftrag Nutzer 2026-11-15). Zwei Aufgaben auf den
>   Folgen von `robot_loop_f32` (gleiche Daten, 5 Schritte): Die Vorlage des gesuchten Körpers gibt es nur an einem
>   Hinweis-Schritt vor dem Lauf (Blick bewegt sich dort nicht, Antwort zählt nicht), an den 4 Schritten des Laufs
>   ist die Vorlage leer. `robot_loop_cue_f32`: der Hinweis-Schritt zeigt auch das erste Bild (das Netz kann den
>   Schritt dort ausrechnen und behalten); `robot_loop_blind_f32`: der Hinweis-Schritt zeigt nur die Vorlage, das
>   Bild ist leer (das Netz muss behalten, WAS gesucht ist). Acht Netze wie zuvor, 12000 Updates, Seeds 0–2.
>   Hauptzahl: geschlossene Schleife auf den 1500 Startszenen (`finds_loop_eval.py`, Hinweis-Schritt, dann 4
>   Schritte ohne Vorlage), Gegenprobe `--amnesia`.
>   **Vorhersage vor dem Lauf (2026-11-15):** (1) Ohne Gedächtnis (cnn, vit) liegt `near` nach 4 Schritten in
>   beiden Aufgaben bei 0,28–0,42 (ein Körper von dreien geraten); mit gelöschtem Zustand landen alle Netze in
>   dieser Spanne. (2) `robot_loop_cue_f32`: layer_s und layer_s_sp4 erreichen `near` nach 4 Schritten 0,80–0,92
>   (unter den 0,93–0,94 mit dauernder Vorlage), hier_s 0,70–0,88. (3) `robot_loop_blind_f32` ist schwerer:
>   layer_s und layer_s_sp4 0,65–0,88, je Netz 0,03–0,15 unter der cue-Variante. (4) vitmem `near` 0,50–0,75,
>   attnmem 0,42–0,70 in der cue-Variante; beide unter layer_s. (5) Erstmals trennen sich die Gedächtnis-Varianten
>   kaum: layer_s_sp4 innerhalb ±0,03 um layer_s, layer_s_am4 0,02–0,10 darunter. (6) Der falsche Körper bleibt
>   das Hauptproblem: Anteil nach 4 Schritten bei layer_s in der blind-Variante mindestens 0,10.

**Ergebnis.** `near` nach 4 Schritten je Seed (0 / 1 / 2); „gelöst“ = `near` über 0,6.

| | `cue`: Seeds | gelöst | `blind`: Seeds | gelöst | Zustand gelöscht (Mittel `cue` / `blind`) |
|---|---|---|---|---|---|
| hier_s | 0,87 / 0,86 / 0,88 | 3 | 0,85 / 0,83 / 0,87 | 3 | 0,22 / 0,28 |
| layer_s_sp4 | 0,31 / 0,32 / 0,92 | 1 | 0,84 / 0,91 / 0,92 | 3 | 0,21 / 0,26 |
| layer_s | 0,91 / 0,32 / 0,31 | 1 | 0,93 / 0,91 / 0,31 | 2 | 0,22 / 0,24 |
| layer_s_am4 | 0,84 / 0,31 / 0,50 | 1 | 0,87 / 0,85 / 0,77 | 3 | 0,22 / 0,23 |
| attnmem | 0,69 / 0,31 / 0,31 | 1 | 0,74 / 0,74 / 0,71 | 3 | 0,19 / 0,26 |
| vitmem | 0,72 / 0,31 / 0,31 | 1 | 0,32 / 0,76 / 0,72 | 2 | 0,28 / 0,29 |
| cnn (ohne Gedächtnis) | 0,33 / 0,33 / 0,33 | – | wie `cue` | – | 0,33 |
| vit (ohne Gedächtnis) | 0,32 / 0,32 / 0,32 | – | wie `cue` | – | 0,32 |

Ungelöste Läufe sitzen genau auf dem Boden der Netze ohne Gedächtnis: `near` 0,31–0,33, falscher Körper 0,667
(sie steuern einen Körper an, unabhängig von der Vorlage). Gelöste Läufe von layer_s und layer_s_sp4: `near`
0,91–0,93, exakt 0,72–0,75, falscher Körper 0,07–0,09 – wie mit dauernd sichtbarer Vorlage (0,93–0,94; 0,74–0,75;
0,06–0,07). Folgen-Wertung im Training: ungelöst 0,62–0,66, gelöst 0,70–0,81; die Trainingskurve verlässt die
Stufe 0,64 bei den gelösten Läufen nach 2500–4500 Updates (Gitter-Netze) bzw. 5750–7250 (vitmem, attnmem); zwei
ungelöste Läufe (`cue`: layer_s_sp4 s0, layer_s_am4 s2) beginnen erst nach 10000 Updates zu steigen.

**Vergleich mit der Vorhersage.** (1) Getroffen für cnn und vit (0,32–0,33); mit gelöschtem Zustand liegen die
Netze mit Gedächtnis darunter (0,19–0,29, unter der Spanne): sie sagen seltener „bleib“. (2) Verfehlt im Mittel:
layer_s 0,51 und layer_s_sp4 0,52 in `cue`, weil je zwei von drei Seeds die Lösung nicht finden; die gelösten
Seeds liegen mit 0,91–0,92 am oberen Rand der Spanne. hier_s getroffen (0,87). (3) Verfehlt, Richtung falsch:
`blind` ist nicht schwerer, sondern wird öfter gelöst (16 von 18 Läufen gegen 8 von 18 in `cue`). (4) vitmem
0,45 unter der Spanne, attnmem 0,44 darin; beide knapp unter layer_s – wegen der Seed-Streuung ohne Aussage.
(5) Nicht prüfbar: Die Mittel unterscheiden sich um bis zu 0,18, aber nur, weil unterschiedlich viele Seeds
lösen. (6) Verfehlt im Kern: Bei den gelösten Läufen ist der falsche Körper mit 0,07–0,09 kein größeres Problem
als mit Vorlage; das Mittel 0,27 kommt vom ungelösten Seed.

**Schluss.** (a) Die Aufgabe trennt sauber: ohne Gedächtnis 0,32–0,33, mit gelöschtem Zustand alle am Boden,
mit Gedächtnis bis 0,93. Erstmals in der Blickschleife ist das Gedächtnis nötig und wird nachweislich benutzt.
(b) Wer die Lösung findet, verliert durch das Merken nichts: layer_s und layer_s_sp4 erreichen ohne Vorlage
dieselben Werte wie mit. Das Behalten über vier Schritte ist für diese Netze nicht der Engpass. (c) Der Engpass
ist das Finden der Lösung im Training: Ein Lauf löst die Aufgabe ganz oder gar nicht. Nur hier_s löst alle
sechs Läufe (bei etwas schwächerem Endwert 0,83–0,88); layer_s 3 von 6, layer_s_sp4 und layer_s_am4 4 von 6,
attnmem 4 von 6, vitmem 3 von 6. Bei drei Seeds je Aufgabe sind diese Quoten grob; die Reihenfolge zwischen den
Gitter-Varianten ist damit nicht belegt, der Abstand von hier_s (6 von 6) zu den übrigen (3–4 von 6) ist ein
Hinweis. Das Mittel über Seeds ist hier die falsche Zahl; berichtet werden müssen Lösequote und Wert der
gelösten Läufe. (d) Unerwartet: Der Hinweis-Schritt MIT Bild wird seltener gelöst als der ohne. Nicht
untersucht; Vermutung: Ohne Bild ist die Vorlage das einzige Signal im Zustand, mit Bild konkurriert sie mit
der Szene. (e) vitmem und attnmem lösen später und enden tiefer (0,69–0,76); das passt zu ihrem schwächeren
ersten Schritt aus dem vorigen Eintrag. (f) Für die Vorhersage-Pipeline: Die Folgen-Wertung im Training sagt
je Lauf vorher, ob die Schleife gelöst ist (über 0,67 = gelöst, in allen 36 Läufen außer layer_s_am4 s2 in `cue`
mit 0,67 und `near` 0,50).

**Belege.** `results/finds_loop.jsonl` (Zeilen `robot_loop_cue_f32`, `robot_loop_blind_f32`, je auch
`/amnesia`), `results/finds_loop_train.jsonl` (Kurven); Netze in `results/checkpoints/robot_loop_cue_f32` und
`robot_loop_blind_f32`.

## 2026-11-16 — Lösequoten der Gedächtnis-Schleife mit acht Seeds

**Frage.** Lernt hier_s die Aufgabe mit einmal gezeigter Vorlage wirklich zuverlässiger als die anderen Netze
mit Gedächtnis, und bleibt der Hinweis-Schritt mit Bild der schwerere?

**Gemacht.** `robot_loop_cue_f32` und `robot_loop_blind_f32`, sechs Netze mit Gedächtnis, fünf weitere Seeds
3, 4, 7, 8, 9, 12000 Updates (Worker, Commit 5d37ef0); Schleife auf den 1500 Startszenen wie im vorigen
Eintrag. Zusammen mit den Seeds 0–2 acht Läufe je Netz und Aufgabe. „Gelöst“ = `near` nach 4 Schritten über
0,6. Vorhersage vor dem Lauf (wörtlich aus „Laufend / offen“):

> - Lösequoten mit mehr Seeds (Auftrag Nutzer 2026-11-15): `robot_loop_cue_f32` und `robot_loop_blind_f32`, die
>   sechs Netze mit Gedächtnis, fünf weitere Seeds 3, 4, 7, 8, 9 (5 und 6 bleiben Abstimm-Seeds), 12000 Updates;
>   Schleife wie zuvor, „gelöst“ = `near` nach 4 Schritten über 0,6. Zusammen mit den Seeds 0–2 dann 8 Läufe je
>   Netz und Aufgabe.
>   **Vorhersage vor dem Lauf (2026-11-15), für die 10 neuen Läufe je Netz (beide Aufgaben zusammen):**
>   (1) hier_s löst mindestens 9 von 10. (2) layer_s, layer_s_sp4, layer_s_am4 lösen je 4–8 von 10; vitmem und
>   attnmem je 3–7 von 10. (3) `cue` bleibt seltener gelöst als `blind`: über alle sechs Netze höchstens 18 von
>   30 Läufen in `cue`, mindestens 22 von 30 in `blind`. (4) Gelöste Läufe von layer_s und layer_s_sp4 liegen in
>   `near` bei 0,89–0,94, gelöste von hier_s bei 0,82–0,89. (5) Die Folgen-Wertung im Training (über 0,67 =
>   gelöst) stimmt in mindestens 57 der 60 Läufe mit der Schleife überein.

**Ergebnis.** Gelöste Läufe von 8 (in Klammern: von den 5 neuen) und `near` der gelösten Läufe.

| | `cue` gelöst | `blind` gelöst | zusammen von 16 | `near` gelöst | exakt gelöst | falscher Körper gelöst |
|---|---|---|---|---|---|---|
| hier_s | 8 (5) | 8 (5) | 16 | 0,80–0,88 | 0,63–0,70 | 0,11–0,19 |
| layer_s | 4 (3) | 7 (5) | 11 | 0,89–0,93 | 0,69–0,74 | 0,07–0,11 |
| layer_s_sp4 | 4 (3) | 7 (4) | 11 | 0,75–0,92 | 0,59–0,74 | 0,07–0,24 |
| attnmem | 5 (4) | 6 (3) | 11 | 0,64–0,76 | 0,48–0,59 | 0,22–0,34 |
| layer_s_am4 | 2 (1) | 8 (5) | 10 | 0,77–0,89 | 0,60–0,70 | 0,10–0,22 |
| vitmem | 4 (3) | 3 (1) | 7 | 0,63–0,78 | 0,48–0,60 | 0,21–0,35 |

Ungelöste Läufe der Gitter-Netze liegen bei 0,31–0,32 (Boden), mit einer Ausnahme (layer_s_am4 `cue` s2: 0,50).
Bei vitmem und attnmem gibt es Zwischenstände: sechs Läufe mit `near` 0,38–0,59. Neue Läufe je Aufgabe über
alle Netze: `cue` 19 von 30, `blind` 23 von 30; alle Läufe: `cue` 27 von 48, `blind` 39 von 48.

**Vergleich mit der Vorhersage.** (1) Getroffen: hier_s 10 von 10. (2) Getroffen: layer_s 8, layer_s_sp4 7,
layer_s_am4 6, attnmem 7, vitmem 4 von 10. (3) `blind` getroffen (23), `cue` um einen Lauf verfehlt (19 statt
höchstens 18); die Richtung stimmt. (4) layer_s getroffen (0,89–0,92); layer_s_sp4 hat zwei gelöste Läufe
darunter (0,75 und 0,79), hier_s einen (0,80). (5) Um einen Lauf verfehlt: 56 von 60 stimmen überein; die vier
Abweichungen sind Zwischenstände von attnmem und vitmem (`near` 0,52–0,59 bei Folgen-Wertung 0,67–0,68).

**Schluss.** (a) hier_s lernt die Aufgabe zuverlässig: 16 von 16 Läufen, die übrigen Gitter-Netze 10–11 von 16
(hier_s gegen layer_s: exakter Fisher-Test zweiseitig p = 0,04). Der Unterschied sitzt in `cue`: hier_s 8 von 8,
layer_s und layer_s_sp4 4 von 8, layer_s_am4 2 von 8. (b) Dafür ist der Endwert von hier_s tiefer: `near`
0,80–0,88 gegen 0,89–0,93 bei gelösten Läufen von layer_s, falscher Körper 0,11–0,19 gegen 0,07–0,11. Das ist
der bekannte Einzelschritt-Abstand von hier_s, kein Gedächtnis-Effekt. Zuverlässigkeit des Lernens und Güte des
Ergebnisses sind hier zwei getrennte Eigenschaften der Architektur. (c) Der Hinweis-Schritt mit Bild ist für
die layer_s-Familie klar schwerer zu lernen (10 von 24 gegen 22 von 24), für hier_s, attnmem und vitmem nicht
(17 von 24 gegen 17 von 24). Die Ursache ist nicht untersucht. (d) layer_s_sp4 und layer_s_am4 sind in der
Lösequote nicht besser als layer_s; am4 ist in `cue` eher schlechter (2 gegen 4 von 8, bei dieser Zahl nicht
belegt). (e) vitmem und attnmem lösen weicher (Zwischenstände) und enden tiefer; vitmem ist das schwächste
Netz (7 von 16). (f) Die Folgen-Wertung im Training sagt die Schleife je Lauf weiter gut vorher (bei den
Gitter-Netzen in allen 64 Läufen bis auf einen), an der Grenze 0,67–0,68 nicht.

**Belege.** `results/finds_loop.jsonl` (Zeilen `robot_loop_cue_f32`, `robot_loop_blind_f32`, Seeds 3, 4, 7, 8,
9), `results/finds_loop_train.jsonl`; Netze in `results/checkpoints/robot_loop_cue_f32` und
`robot_loop_blind_f32`.

## 2026-11-16 — Ungelöste Läufe der Gedächtnis-Schleife: Die Vorlage kommt nicht an

**Frage.** Geht die Vorlage in den ungelösten layer_s-Läufen im Zustand verloren, oder kommt sie nie hinein?

**Gemacht.** `scripts/loop_state_probe.py`: layer_s und hier_s, je 8 Seeds, beide Aufgaben, 4500 Testfolgen;
lineare Auslese (Ridge, halb anpassen, halb messen) der gesuchten Form (Zufall 0,2) und des richtigen ersten
Schritts (R²) aus dem Zustand nach jedem Schritt und aus dem Ausgang des Vorlagen-Encoders. Danach für alle 96
Läufe der sechs Netze mit Gedächtnis: Streuung des Encoder-Ausgangs über 1500 Vorlagen und Anteil der
Ausgangswerte mit Betrag über 0,95 (der Encoder endet in einem tanh) → `results/loop_ref_encoder.json`.
Zusätzlich drei frisch angelegte Netze je Bauart. Vorhersage vor dem Lauf (wörtlich aus „Laufend / offen“):

> - Was behalten die ungelösten layer_s-Läufe vom Hinweis? (Auftrag Nutzer 2026-11-16.) `scripts/loop_state_probe.py`:
>   die gespeicherten Netze (layer_s und hier_s, je 8 Seeds, beide Aufgaben) laufen über die 4500 Testfolgen;
>   nach jedem Schritt liest eine lineare Auslese (Ridge, eine Hälfte der Folgen zum Anpassen, die andere zum
>   Messen) aus dem Zustand die gesuchte Form (5 Formen, Zufall 0,2; 0,33 für jemanden, der nur die drei Körper
>   der Szene sieht) und den richtigen ersten Schritt (R²). Dieselbe Auslese auf dem Ausgang des Vorlagen-Encoders.
>   **Vorhersage vor dem Lauf (2026-11-16):** (1) Am Ausgang des Vorlagen-Encoders ist die Form in gelösten Läufen
>   zu mindestens 0,90 lesbar, in ungelösten zu mindestens 0,70 (auch ein kaum trainierter Encoder trennt die
>   Formen). (2) Im Zustand direkt nach dem Hinweis-Schritt: gelöst mindestens 0,90, ungelöst 0,40–0,80 – die
>   Vorlage kommt an. (3) Nach dem ersten Schritt des Laufs: gelöst mindestens 0,85, ungelöst höchstens 0,45 – sie
>   geht beim ersten Bild ohne Vorlage verloren. (4) hier_s: in allen 16 Läufen an allen Schritten mindestens
>   0,85. (5) In gelösten `cue`-Läufen von layer_s ist der erste Schritt nach dem Hinweis-Schritt mit R² von
>   mindestens 0,5 aus dem Zustand lesbar (das Netz rechnet ihn am Hinweis-Schritt aus), in ungelösten höchstens
>   0,2.

**Ergebnis.** Form-Auslese (Anteil richtig), Spanne über die Läufe.

| | Encoder-Ausgang | Zustand nach Hinweis | nach Schritt 1 | nach Schritt 4 | Schritt-R² nach Hinweis |
|---|---|---|---|---|---|
| layer_s `cue`, gelöst (4) | 0,80–0,85 | 0,74–0,81 | 0,73–0,76 | 0,74–0,75 | 0,25–0,35 |
| layer_s `cue`, ungelöst (4) | 0,31–0,34 | 0,23–0,25 | 0,23–0,24 | 0,66–0,69 | 0,05–0,07 |
| layer_s `blind`, gelöst (7) | 0,75–0,84 | 0,91–0,95 | 0,80–0,86 | 0,74–0,79 | – |
| layer_s `blind`, ungelöst (1) | 0,34 | 0,32 | 0,24 | 0,67 | – |
| hier_s `cue` (8, alle gelöst) | 0,73–0,87 | 0,70–0,83 | 0,68–0,79 | 0,72–0,75 | 0,22–0,41 |
| hier_s `blind` (8, alle gelöst) | 0,72–0,85 | 0,92–0,94 | 0,82–0,87 | 0,71–0,78 | – |
| frisch angelegt (6) | 0,30–0,35 | | | | |

Die 0,66–0,69 der ungelösten Läufe nach Schritt 4 sind keine Erinnerung: Der Lehrer hat den Blick dann meist
auf den gesuchten Körper gestellt, die Form steht im Bild. Encoder-Ausgang der Gitter-Netze (64 Läufe):

| | Streuung über Vorlagen | Anteil Werte mit Betrag über 0,95 |
|---|---|---|
| gelöste Läufe (48) | 0,24–0,72 | 0,37–0,69 |
| ungelöste Läufe am Boden (15; dazu ein Zwischenstand) | 0,00–0,17 | 0,69–1,00 (10 davon ab 0,90) |
| frisch angelegt | 0,01 | 0,00 |

In den ungelösten layer_s-Läufen liegt der Wert vor dem tanh im Mittel bei Betrag 3,5–5,4 mit Streuung
0,6–0,95: Der Ausgang ist für jede Vorlage dasselbe Muster aus ±1. Kein Lauf mit zusammengefallenem Encoder
(Streuung unter 0,05; 15 von 96) ist gelöst. Bei vitmem und attnmem gibt es dagegen ungelöste Läufe mit
lebendem Encoder (in `blind` alle: Streuung 0,09–0,25, kein Wert gesättigt).

**Vergleich mit der Vorhersage.** (1) Verfehlt: gelöst 0,73–0,87 statt mindestens 0,90; ungelöst 0,31–0,34
statt mindestens 0,70 – wie ein frisch angelegter Encoder. (2) Verfehlt im Kern: In ungelösten Läufen kommt die
Vorlage nicht im Zustand an (0,23–0,32); gelöst nur in `blind` über 0,90. (3) Ungelöst höchstens 0,45 getroffen,
aber aus anderem Grund (es war nie etwas da); gelöst 0,73–0,86, überwiegend unter 0,85. (4) Verfehlt: hier_s
0,68–0,94, fallend über die Schritte. (5) Gelöst verfehlt (R² 0,25–0,35 statt mindestens 0,5), ungelöst
getroffen. Meine Annahme „die Vorlage kommt an und geht dann verloren“ war falsch.

**Schluss.** (a) Die ungelösten Läufe der Gitter-Netze scheitern am Eingang, nicht am Gedächtnis: Der
Vorlagen-Encoder gibt für jede Vorlage dasselbe gesättigte Muster aus. Im Zustand ist dann nichts zu behalten.
(b) Gemessen ist der Zusammenhang (ungelöst = Encoder gesättigt und ohne Streuung, 15 von 15 am Boden; gelöst
nie), nicht die Reihenfolge. Naheliegend, aber nicht belegt: Der Ausgang läuft früh in die Sättigung des tanh,
dort ist die Steigung um drei Größenordnungen kleiner, und der Encoder lernt die Formen nicht mehr. Dafür
fehlen Zwischenstände aus dem Training. (c) Folge für den vorigen Eintrag: Die Lösequoten der Gitter-Netze
messen, wie oft der gemeinsame Vorlagen-Eingang (`+ref`) hängen bleibt, nicht die Güte des Gedächtnisses. Dass
hier_s nie hängen bleibt und die layer_s-Familie in `cue` oft, ist damit eine Aussage über das Zusammenspiel
von Bauart und Eingang; warum, ist offen. (d) Wer den Eingang lernt, behält genug: Die Form bleibt über vier
Schritte linear lesbar (0,71–0,79), mit Abfall von 0,91–0,95 direkt nach dem Hinweis in `blind`. (e) In `cue`
wird der erste Schritt am Hinweis-Schritt nur teilweise vorausgerechnet (R² 0,22–0,41); die Netze behalten
vor allem, was gesucht ist. (f) vitmem und attnmem scheitern anders: in `blind` mit lebendem Encoder. Dort
liegt der Engpass hinter dem Eingang. (g) Die lineare Auslese unterschätzt: gelöste Läufe handeln besser
(`near` 0,89–0,93), als 0,75–0,85 Form-Auslese am Encoder vermuten lässt.

**Belege.** `results/loop_state_probe.json`, `results/loop_ref_encoder.json`; Skript
`scripts/loop_state_probe.py`.

## 2026-11-16 — Vorlagen-Encoder im Trainingsverlauf: erst die Sättigung, dann das Hängenbleiben

**Frage.** Geht die Sättigung des Vorlagen-Encoders dem Hängenbleiben voraus, oder ist sie eine Folge davon?

**Gemacht.** `netresearch/curriculum.py` schreibt bei `+ref`-Netzen alle 250 Updates den Encoder mit
(`ref_curve`, 512 Vorlagen). `robot_loop_cue_f32`, 12000 Updates: layer_s, layer_s_sp4, layer_s_am4, hier_s auf
den Seeds 5 und 6; layer_s auf den Seeds 0–2 als Wiederholung (Worker, Commit 4f06cfe). Nebenbei: Der Worker
stürzte zwischen den zwei Jobs an einer von OneDrive gesperrten Job-Datei ab; behoben (db27fd4). Vorhersage vor
dem Lauf (wörtlich aus „Laufend / offen“):

> - Reihenfolge belegen: Sättigung des Vorlagen-Encoders im Trainingsverlauf (Auftrag Nutzer 2026-11-16).
>   `netresearch/curriculum.py` schreibt bei `+ref`-Netzen alle 250 Updates mit (`ref_curve`): Streuung des
>   Encoder-Ausgangs über 512 Vorlagen, Anteil der Ausgangswerte mit Betrag über 0,95, mittlerer Betrag und
>   Streuung vor dem tanh. Läufe auf `robot_loop_cue_f32`, 12000 Updates: layer_s, layer_s_sp4, layer_s_am4,
>   hier_s auf den Abstimm-Seeds 5 und 6; dazu layer_s auf den Seeds 0–2 als Wiederholung mit bekanntem Ausgang
>   (0 gelöst, 1 und 2 ungelöst). Vorab gesehen (lokaler Kurztest des Mitschreibens, layer_s Seed 5, 600 Updates):
>   Anteil gesättigt 0,00 / 0,30 / 0,83 bei Update 0 / 250 / 500, Streuung 0,01 / 0,04 / 0,02.
>   **Vorhersage vor dem Lauf (2026-11-16):** (1) Alle Läufe gehen früh in die Sättigung, gelöste wie ungelöste:
>   bei Update 500 Anteil gesättigt mindestens 0,6 und Streuung unter 0,05. Die Sättigung allein entscheidet also
>   nicht. (2) In gelösten Läufen steigt die Streuung über 0,1, bevor oder spätestens im selben Messpunkt, in dem
>   die Folgen-Wertung 0,67 übersteigt: Erst wacht der Encoder auf, dann löst das Netz. (3) In ungelösten Läufen
>   bleibt die Streuung nach Update 1000 unter 0,05, und der mittlere Betrag vor dem tanh endet bei mindestens
>   3,5. (4) Unsicher: Bei Update 1000 liegt der mittlere Betrag vor dem tanh in jedem später gelösten
>   layer_s-Lauf unter dem jedes später ungelösten. (5) Die Wiederholung von layer_s auf den Seeds 0–2 endet wie
>   zuvor (gelöst, ungelöst, ungelöst). (6) Von den sechs Läufen der layer_s-Familie auf den Seeds 5 und 6 lösen
>   2–4, hier_s löst beide.

**Ergebnis.** Je Lauf: Anteil gesättigter Ausgangswerte bei Update 500 / 1000, mittlerer Betrag vor dem tanh bei
Update 1000, erstes Update mit Streuung über 0,1, erstes Update mit Folgen-Wertung über 0,67, Endwert.

| | gesättigt 500 / 1000 | Betrag 1000 | Streuung > 0,1 | Wertung > 0,67 | Ende |
|---|---|---|---|---|---|
| hier_s s5 | 0,00 / 0,00 | 0,4 | 1750 | 3500 | 0,77 |
| hier_s s6 | 0,00 / 0,00 | 0,3 | 2750 | 4500 | 0,75 |
| layer_s s0 | 0,00 / 0,45 | 1,4 | 2000 | 3250 | 0,80 |
| layer_s_sp4 s6 | 0,39 / 0,65 | 2,0 | 1750 | 2750 | 0,81 |
| layer_s s5 | 0,77 / 0,92 | 2,8 | 8000 | 8250 | 0,68 |
| layer_s s1 | 0,79 / 0,96 | 3,0 | nie | nie | 0,65 |
| layer_s s6 | 0,58 / 1,00 | 3,3 | nie | nie | 0,65 |
| layer_s_sp4 s5 | 0,94 / 1,00 | 3,3 | nie | nie | 0,65 |
| layer_s_am4 s6 | 0,90 / 1,00 | 3,3 | nie | nie | 0,64 |
| layer_s_am4 s5 | 0,91 / 1,00 | 4,6 | nie | nie | 0,65 |
| layer_s s2 | 0,97 / 1,00 | 5,4 | nie | nie | 0,66 |

In den sechs ungelösten Läufen bleibt die Streuung nach Update 1000 bei höchstens 0,02, der Betrag vor dem tanh
steigt bis 5,3–8,1 (Update 2750–5250) und endet bei 3,6–5,3. In layer_s s5 sinkt er ab Update 2750 von 6,8 auf 2,9;
bei Update 8000 trennt der Encoder die Formen. Bei Update 0 und 250 ist in allen Läufen nichts gesättigt. Die
Wiederholung von layer_s auf den Seeds 0–2 trifft die früheren Endwerte auf vier Stellen (0,8010 / 0,6487 /
0,6561).

**Vergleich mit der Vorhersage.** (1) Verfehlt: hier_s sättigt bei Update 500 und 1000 gar nicht, layer_s s0
bei 500 auch nicht; nur die später ungelösten Läufe (0,58–0,97) und layer_s s5 liegen über 0,6. Der eine vorab
gesehene Lauf war nicht typisch für die gelösten. (2) Getroffen: In allen fünf gelösten Läufen steigt die
Streuung 250–1750 Updates vor der Folgen-Wertung. (3) Getroffen: Streuung höchstens 0,02, Betrag am Ende
3,6–5,3. (4) Getroffen, knapp: gelöst 1,4 und 2,8, ungelöst 3,0 / 3,3 / 5,4. (5) Getroffen, auf vier Stellen.
(6) Knapp: 2 von 6 der layer_s-Familie (einer davon spät und mit Endwert 0,68), hier_s beide.

**Schluss.** (a) Die Reihenfolge ist belegt: Die Sättigung steht bei Update 500–1000, das Lösen beginnt
frühestens bei 2750. Wer bei Update 1000 zu mindestens 0,96 gesättigt ist, bleibt hängen (6 von 6); wer bei
höchstens 0,65 liegt, löst bis Update 4500 (4 von 4); der Lauf dazwischen (0,92) löst spät. Der Ausgang eines
Laufs steht damit nach einem Zwölftel des Trainings fest. (b) Der Unterschied der Bauarten liegt in den ersten
1000 Updates: Die layer_s-Familie treibt den Encoder-Ausgang für alle Vorlagen gleich auf große Werte, hier_s
lässt ihn klein (Betrag 0,3–0,4), bis er die Formen trennt. Das erklärt, warum hier_s nie hängen bleibt.
(c) Die Sättigung ist kein endgültiger Zustand: Der Betrag sinkt in mehreren Läufen langsam wieder, in einem
reicht das zum späten Lösen. Längeres Training würde die Lösequote vermutlich heben; nicht gemessen. (d) Belegt
ist die zeitliche Reihenfolge, nicht die Ursache. Der Eingriff (Encoder-Ausgang ohne tanh) steht aus.
(e) Vermutung, nicht geprüft: Die layer_s-Netze benutzen den Encoder-Ausgang zuerst als Marke für den
Hinweis-Schritt (Vorlage da gegen leer); dafür genügt ein großer konstanter Wert. Dazu passt, dass `blind`
(dort markiert das leere Bild den Hinweis-Schritt) seltener hängen bleibt. (f) Die Läufe sind auf dem Worker
bitgenau wiederholbar; ein Seed ist also eine feste Eigenschaft des Laufs, kein Rauschen der Maschine.

**Belege.** `results/loop_refcurve.jsonl` (11 Läufe mit `ref_curve`).

## 2026-11-16 — Ursachen-Probe: Ohne tanh am Vorlagen-Encoder lösen alle Läufe

**Frage.** Ist die Sättigung des tanh am Ausgang des Vorlagen-Encoders die Ursache der ungelösten Läufe?

**Gemacht.** Modell-Variante `+refl` (wie `+ref` ohne den tanh; gleiche Startgewichte bei gleichem Seed).
Dieselben elf Läufe wie im vorigen Eintrag auf `robot_loop_cue_f32`, 12000 Updates (Worker, Commit 8990e1b);
danach die geschlossene Schleife auf den 1500 Startszenen. Vorhersage vor dem Lauf (wörtlich aus „Laufend /
offen“):

> - Ursachen-Probe: Vorlagen-Encoder ohne tanh (Auftrag Nutzer 2026-11-16). Neue Modell-Variante `+refl`
>   (wie `+ref`, der tanh am Ausgang des Encoders fehlt; gleiche Startgewichte bei gleichem Seed, geprüft). Dieselben
>   elf Läufe wie im vorigen Eintrag auf `robot_loop_cue_f32`, 12000 Updates: layer_s, layer_s_sp4, layer_s_am4,
>   hier_s auf den Seeds 5 und 6, layer_s auf den Seeds 0–2; je Lauf direkter Vergleich mit dem `+ref`-Lauf
>   gleichen Seeds (dort lösten von den neun Läufen der layer_s-Familie drei, einer davon spät). Danach die
>   geschlossene Schleife. Vorab gesehen (lokaler Kurztest, layer_s Seed 5, 300 Updates): Betrag des Ausgangs
>   0,33 bei Update 250 (mit tanh davor 0,3).
>   **Vorhersage vor dem Lauf (2026-11-16):** (1) Ohne tanh lösen mindestens 7 der 9 Läufe der layer_s-Familie
>   (Folgen-Wertung am Ende über 0,67), darunter mindestens 4 der 6, die mit tanh ungelöst blieben. (2) Die
>   gelösten Läufe überschreiten 0,67 vor Update 5000. (3) Die layer_s-Familie treibt den Ausgang weiter früh auf
>   große gemeinsame Werte: mittlerer Betrag bei Update 1000 mindestens 2 in mindestens 6 der 9 Läufe (der Antrieb
>   bleibt, nur die Sackgasse fehlt). (4) hier_s löst beide Läufe, Endwert innerhalb ±0,03 um den `+ref`-Lauf
>   (0,77 und 0,75). (5) Gelöste layer_s- und layer_s_sp4-Läufe enden bei 0,78–0,82 und in der Schleife bei
>   `near` nach 4 Schritten 0,88–0,93.

**Ergebnis.** Je Lauf mit tanh (`+ref`) und ohne (`+refl`): Folgen-Wertung am Ende, erstes Update über 0,67,
mittlerer Betrag des Encoder-Werts bei Update 1000 (mit tanh: vor dem tanh); Schleife `near` nach 4 Schritten.

| | Ende `+ref` → `+refl` | über 0,67 ab `+ref` → `+refl` | Betrag bei 1000 `+ref` → `+refl` | Schleife `+refl` (`+ref`) |
|---|---|---|---|---|
| layer_s s0 | 0,80 → 0,80 | 3250 → 3500 | 1,4 → 0,5 | 0,90 (0,91) |
| layer_s s1 | 0,65 → 0,80 | nie → 3000 | 3,0 → 0,9 | 0,89 (0,32) |
| layer_s s2 | 0,66 → 0,79 | nie → 3750 | 5,4 → 1,6 | 0,87 (0,31) |
| layer_s s5 | 0,68 → 0,79 | 8250 → 3500 | 2,8 → 0,9 | 0,88 |
| layer_s s6 | 0,65 → 0,80 | nie → 2750 | 3,3 → 0,8 | 0,90 |
| layer_s_sp4 s5 | 0,65 → 0,79 | nie → 3250 | 3,3 → 1,5 | 0,88 |
| layer_s_sp4 s6 | 0,81 → 0,80 | 2750 → 2500 | 2,0 → 0,7 | 0,90 |
| layer_s_am4 s5 | 0,65 → 0,76 | nie → 3750 | 4,6 → 1,0 | 0,84 |
| layer_s_am4 s6 | 0,64 → 0,75 | nie → 4750 | 3,3 → 1,2 | 0,82 |
| hier_s s5 | 0,77 → 0,77 | 3500 → 3750 | 0,4 → 0,4 | 0,85 |
| hier_s s6 | 0,75 → 0,75 | 4500 → 4750 | 0,3 → 0,3 | 0,81 |

Falscher Körper in der Schleife: layer_s und layer_s_sp4 0,10–0,12, layer_s_am4 0,15–0,17, hier_s 0,15–0,18.
Am Ende liegt die Streuung des Ausgangs über die Vorlagen bei 0,6–1,5 (mit tanh in gelösten Läufen 0,3–0,5).

**Vergleich mit der Vorhersage.** (1) Getroffen: 9 von 9, alle 6 zuvor ungelösten. (2) Getroffen:
2500–4750. (3) Verfehlt: Der Betrag bei Update 1000 liegt in allen neun Läufen unter 2 (0,5–1,6); ohne tanh
treibt die layer_s-Familie den Ausgang nicht auf große Werte. (4) Getroffen: 0,77 und 0,75, wie mit tanh.
(5) Folgen-Wertung getroffen (0,79–0,80); Schleife 0,87–0,90, ein Lauf knapp unter der Spanne (0,87).

**Schluss.** (a) Die Ursache ist belegt: Bei gleichen Startgewichten und gleichem Seed lösen ohne tanh alle
sechs Läufe, die mit tanh hängen blieben, und zwar so früh wie die anderen (Update 2750–4750). Das Hängenbleiben
war eine Sackgasse des Encoder-Ausgangs, keine Eigenschaft der Gedächtnis-Bauarten. (b) Die großen Werte vor
dem tanh waren selbst eine Folge des tanh: Ohne ihn bleibt der Betrag bei 0,5–1,6. Meine Vermutung aus dem
vorigen Eintrag („der Antrieb zu großen Werten bleibt“) ist in dieser Form widerlegt; naheliegend ist, dass
die Netze einen Ausgang der Größe 1 brauchen und der tanh dafür immer größere Werte verlangt. Nicht geprüft.
(c) Läufe, die schon mit tanh lösten, ändern sich kaum (Endwert ±0,01, Beginn ±250 Updates; hier_s
unverändert). In der Schleife liegt layer_s s0 bei 0,90 gegen 0,91. (d) Die Lösequoten der zwei Einträge davor
(hier_s 16 von 16, layer_s-Familie 10–11 von 16) beschreiben den `+ref`-Eingang, nicht das Gedächtnis. Für den
Vergleich der Gedächtnis-Bauarten müssen `cue` und `blind` mit `+refl` auf den Auswerte-Seeds neu laufen.
(e) Erster Eindruck auf den Abstimm-Seeds (keine Auswertung): layer_s und layer_s_sp4 0,87–0,90,
layer_s_am4 0,82–0,84, hier_s 0,81–0,85 – die Reihenfolge des Einzelschritts. (f) Offen: ob der tanh auch
in den älteren `+ref`-Aufgaben Läufe gekostet hat (dort ist die Vorlage dauernd sichtbar; ein Lauf ohne
Streuung am Encoder wäre aufgefallen als Wert am Boden) und ob vitmem und attnmem von `+refl` profitieren.

**Belege.** `results/loop_refcurve.jsonl` (22 Läufe, je mit `ref_curve`), `results/finds_loop.jsonl` (Zeilen
`robot_loop_cue_f32` mit `+refl`); Netze in `results/checkpoints/robot_loop_cue_f32`.

## 2026-11-17 — Gedächtnis-Bauarten in der Schleife mit einmal gezeigter Vorlage, ohne die Eingangs-Sackgasse

**Frage.** Wie ordnen sich die Netze mit Gedächtnis, wenn der Vorlagen-Eingang nicht mehr hängen bleibt?

**Gemacht.** `robot_loop_cue_f32` und `robot_loop_blind_f32` mit `+refl` (Encoder ohne tanh), sechs Netze mit
Gedächtnis, Seeds 0–2, 12000 Updates (Worker, Commit a2209fd; layer_s auf `cue` aus dem vorigen Eintrag).
Geschlossene Schleife auf den 1500 Startszenen. Vorhersage vor dem Lauf (wörtlich aus „Laufend / offen“):

> - Vergleich der Gedächtnis-Bauarten ohne die Eingangs-Sackgasse (Auftrag Nutzer 2026-11-16):
>   `robot_loop_cue_f32` und `robot_loop_blind_f32` mit `+refl`, sechs Netze mit Gedächtnis (layer_s, hier_s,
>   layer_s_sp4, layer_s_am4, vitmem, attnmem), Auswerte-Seeds 0–2, 12000 Updates (layer_s auf `cue` liegt aus dem
>   vorigen Eintrag schon vor: `near` 0,90 / 0,89 / 0,87). Danach die geschlossene Schleife auf den 1500
>   Startszenen; „gelöst“ = `near` nach 4 Schritten über 0,6.
>   **Vorhersage vor dem Lauf (2026-11-16):** (1) Alle 24 Läufe der vier Gitter-Netze sind gelöst. (2) `near` nach
>   4 Schritten, Mittel über Seeds, in beiden Aufgaben: layer_s und layer_s_sp4 0,87–0,92, layer_s_am4 0,80–0,87,
>   hier_s 0,80–0,87. (3) layer_s_sp4 liegt innerhalb ±0,02 um layer_s, layer_s_am4 mindestens 0,03 darunter: Die
>   Gedächtnis-Varianten bringen keinen Vorteil. (4) Je Gitter-Netz unterscheiden sich `cue` und `blind` im Mittel
>   um höchstens 0,03. (5) vitmem und attnmem lösen weiter nicht alle Läufe (ihr Scheitern in `blind` lag nicht
>   am Encoder): vitmem höchstens 4 von 6, attnmem mindestens 4 von 6; gelöste Läufe 0,60–0,78.

**Ergebnis.** `near` nach 4 Schritten je Seed (0 / 1 / 2) und Mittel; in Klammern das Mittel mit `+ref` (tanh)
auf denselben Seeds.

| | `cue` | Mittel | `blind` | Mittel | `near` nach Schritt 1 (`cue` / `blind`) |
|---|---|---|---|---|---|
| layer_s | 0,90 / 0,89 / 0,87 | 0,89 (0,51) | 0,90 / 0,92 / 0,89 | 0,91 (0,72) | 0,85 / 0,86 |
| layer_s_sp4 | 0,85 / 0,87 / 0,92 | 0,88 (0,52) | 0,89 / 0,92 / 0,92 | 0,91 (0,89) | 0,84 / 0,87 |
| hier_s | 0,86 / 0,86 / 0,87 | 0,86 (0,87) | 0,85 / 0,85 / 0,87 | 0,86 (0,85) | 0,81 / 0,79 |
| layer_s_am4 | 0,85 / 0,78 / 0,81 | 0,81 (0,55) | 0,84 / 0,87 / 0,84 | 0,85 (0,83) | 0,76 / 0,79 |
| attnmem | 0,69 / 0,67 / 0,67 | 0,68 (0,44) | 0,76 / 0,72 / 0,68 | 0,72 (0,73) | 0,53 / 0,57 |
| vitmem | 0,70 / 0,40 / 0,48 | 0,53 (0,45) | 0,64 / 0,57 / 0,74 | 0,65 (0,60) | 0,37 / 0,49 |
| cnn, vit (ohne Gedächtnis, `+ref`) | | 0,32–0,33 | | 0,32–0,33 | 0,20 |

Exakt nach 4 Schritten: layer_s 0,71 / 0,73, layer_s_sp4 0,70 / 0,72, hier_s 0,67 / 0,67, layer_s_am4 0,63 /
0,65, attnmem 0,51 / 0,55, vitmem 0,40 / 0,50. Falscher Körper (Mittel über Seeds): layer_s und layer_s_sp4 0,09–0,12, hier_s
0,13–0,14, layer_s_am4 0,15–0,18, attnmem 0,26–0,30, vitmem 0,33–0,44. Zum Vergleich die Schleife mit dauernd
sichtbarer Vorlage (`robot_loop_f32`, `+ref`): layer_s 0,93, layer_s_sp4 0,94, layer_s_am4 0,90, hier_s 0,89,
vitmem 0,82, attnmem 0,76.

**Vergleich mit der Vorhersage.** (1) Getroffen: 24 von 24. (2) Getroffen: layer_s 0,89 / 0,91, layer_s_sp4
0,88 / 0,91, layer_s_am4 0,81 / 0,85, hier_s 0,86 / 0,86. (3) Getroffen: layer_s_sp4 −0,01 / 0,00, layer_s_am4
−0,08 / −0,06. (4) Für drei Netze getroffen (0,01–0,03), layer_s_am4 0,04. (5) Getroffen: vitmem 3 von 6,
attnmem 6 von 6, gelöste Läufe 0,64–0,76.

**Schluss.** (a) Reihenfolge der Bauarten in der Aufgabe, die Gedächtnis braucht: layer_s = layer_s_sp4
(0,88–0,91) vor hier_s (0,86) und layer_s_am4 (0,81–0,85), dann attnmem (0,68–0,72), dann vitmem (0,53–0,65);
ohne Gedächtnis 0,32–0,33. (b) Das ist die Reihenfolge des ersten Schritts: Die Abstände stehen schon nach
Schritt 1 fest; über die Schritte 2–4 gewinnen die Gitter-Netze 0,04–0,06, attnmem und vitmem 0,15. Die Aufgabe misst bei den Gitter-Netzen vor allem,
wie gut die Vorlage über EINEN Schritt in die Suche eingeht; das Behalten über vier Schritte trennt sie nicht.
(c) Preis des Merkens gegenüber dauernd sichtbarer Vorlage: Gitter-Netze 0,02–0,09 (layer_s 0,02–0,04,
hier_s 0,03, layer_s_am4 0,05–0,09), attnmem 0,04–0,08, vitmem 0,17–0,29 (Vergleich über verschiedene
Encoder-Varianten, daher grob). vitmem ist das einzige Netz, dem das Merken selbst deutlich schadet; es löst
auch mit `+refl` nur 3 von 6 Läufen. (d) layer_s_sp4 und layer_s_am4 bringen gegenüber layer_s keinen
Vorteil; am4 ist 0,06–0,08 schlechter. Für diese Aufgabe genügt das Gedächtnis von layer_s. (e) `+refl`
schadet nirgends: hier_s und attnmem `blind` bleiben gleich (±0,01), alle anderen gewinnen. attnmem löst in
`cue` jetzt 3 statt 1 von 3 Läufen – auch dort hing der Encoder. (f) Der falsche Körper bleibt die Fehlerart:
im Mittel 0,09–0,12 bei den besten Netzen, und die Schleife verlässt ihn kaum (`near` steigt bei den
Gitter-Netzen von Schritt 1 zu 4 nur um 0,04–0,06). (g) Um Gedächtnis-Bauarten zu trennen, ist die Aufgabe für die Gitter-Netze zu leicht: ein Inhalt,
vier Schritte. Schwerere Stufen wären längere Läufe oder mehr als ein zu behaltender Inhalt.

**Belege.** `results/finds_loop.jsonl` (Zeilen `robot_loop_cue_f32`, `robot_loop_blind_f32` mit `+refl`),
`results/loop_refcurve.jsonl`; Netze in `results/checkpoints/robot_loop_cue_f32` und `robot_loop_blind_f32`.

## 2026-11-17 — Zwei Ziele nacheinander: die Gedächtnis-Bauarten trennen sich

**Frage.** Trennen sich die Gedächtnis-Bauarten, wenn zwei Inhalte (die Formen von A und B) in fester
Reihenfolge behalten werden müssen, B über fünf Schritte?

**Gemacht.** `robot_loop_two_f32` (neu, `scripts/make_loop_set.py --two`), sechs Netze mit Gedächtnis, `+refl+rez3`,
Seeds 0–2, 12000 Updates (Worker, Commit e60843c). Geschlossene Schleife auf den 1500 Startszenen mit allen 6
geordneten Paaren je Szene (`scripts/finds_loop_eval.py --task robot_loop_two_f32`). Vorhersage vor dem Lauf
(wörtlich aus „Laufend / offen“):

> - Schwerere Gedächtnis-Stufe: zwei Ziele nacheinander (Auftrag Nutzer 2026-11-17; ab jetzt `+refl` als
>   Standard für Vorlagen-Aufgaben). Aufgabe `robot_loop_two_f32` (`scripts/make_loop_set.py --two`): zwei
>   Hinweis-Schritte mit den Vorlagen von A und B (Bild leer), dann ein Blicklauf mit 6 Bildern ohne Vorlage; an
>   den ersten 3 ist der Schritt zu A richtig, an den letzten 3 der zu B. Der Lehrer wie zuvor, er hält B im
>   Blickfeld, solange er A ansteuert (Paare, bei denen das nicht geht, fallen weg: 4 %). 30736 Trainingsfolgen
>   (2 geordnete Paare je Szene), Test 8615. Sechs Netze mit Gedächtnis, `+refl+rez3`, Seeds 0–2, 12000 Updates.
>   Schleife auf den 1500 Startszenen, alle 6 geordneten Paare je Szene: A nach 3 Schritten (`near_a`), B nach 6
>   Schritten, beide (`near_both`). Orakel: 1,00 / 1,00 / 1,00. Wer immer „bleib“ sagt, ist auf den Folgen in etwa
>   0,33 der Bilder exakt.
>   **Vorhersage vor dem Lauf (2026-11-17):** (1) Alle 12 Läufe von layer_s, layer_s_sp4, hier_s und layer_s_am4
>   lösen A (`near_a` über 0,6). (2) A nach 3 Schritten liegt je Netz höchstens 0,05 unter dem Wert nach 4 Schritten
>   in `blind` mit `+refl` (layer_s 0,91, layer_s_sp4 0,91, hier_s 0,86, layer_s_am4 0,85). (3) B nach 6 Schritten
>   ist die schwere Hälfte: layer_s 0,60–0,85, im Mittel mindestens 0,05 unter A; `near_both` bei layer_s
>   0,55–0,80. (4) Erstmals trennen sich die Gitter-Varianten: Bei B liegen layer_s_sp4 oder layer_s_am4 mindestens
>   0,05 über oder unter layer_s (Richtung offen). (5) Mindestens ein Lauf der Gitter-Netze landet bei B am
>   Boden (B ungefähr Zufall unter den zwei übrigen Körpern: `near` bei B höchstens 0,5), während A gelöst ist.
>   (6) vitmem und attnmem: `near_both` höchstens 0,45.

**Ergebnis.** A = `near` gegen A nach 3 Schritten (`near_a`), B = `near` gegen B nach 6 Schritten, beide =
`near_both`; je Seed 0 / 1 / 2 und Mittel. Letzte Spalte: `near` nach Schritt 1, in Klammern derselbe Wert in
`blind` mit einem Ziel (`+refl`, Eintrag davor).

| | A | Mittel | B | Mittel | beide | Mittel | Schritt 1 (ein Ziel) |
|---|---|---|---|---|---|---|---|
| layer_s | 0,87 / 0,85 / 0,86 | 0,86 | 0,80 / 0,77 / 0,80 | 0,79 | 0,73 / 0,70 / 0,73 | 0,72 | 0,81 (0,86) |
| layer_s_sp4 | 0,85 / 0,86 / 0,85 | 0,85 | 0,78 / 0,81 / 0,79 | 0,79 | 0,71 / 0,73 / 0,71 | 0,72 | 0,80 (0,87) |
| hier_s | 0,79 / 0,75 / 0,77 | 0,77 | 0,67 / 0,63 / 0,66 | 0,65 | 0,57 / 0,52 / 0,55 | 0,55 | 0,68 (0,79) |
| layer_s_am4 | 0,76 / 0,79 / 0,75 | 0,77 | 0,65 / 0,70 / 0,66 | 0,67 | 0,54 / 0,61 / 0,56 | 0,57 | 0,69 (0,79) |
| attnmem | 0,32 / 0,60 / 0,38 | 0,43 | 0,31 / 0,60 / 0,36 | 0,43 | 0,15 / 0,42 / 0,19 | 0,25 | 0,28 (0,57) |
| vitmem | 0,58 / 0,35 / 0,32 | 0,42 | 0,58 / 0,32 / 0,30 | 0,40 | 0,40 / 0,16 / 0,14 | 0,23 | 0,26 (0,49) |
| Orakel | | 1,00 | | 1,00 | | 1,00 | 0,99 |

Der Wechsel ist der schwächste Schritt: `near` gegen B nach Schritt 4 (dem ersten Schritt zu B) layer_s und
layer_s_sp4 0,52–0,53, layer_s_am4 0,39, hier_s 0,36, attnmem und vitmem 0,20–0,22 (Orakel 0,85: B liegt
nicht immer in Reichweite eines Schritts). Falscher Körper am Ende: layer_s und layer_s_sp4 0,20, hier_s und
layer_s_am4 0,32, attnmem und vitmem 0,55–0,57; bei A (nach 3 Schritten) 0,13–0,14 / 0,22–0,23 / 0,54–0,56.
Zufall unter drei Körpern ist `near` 0,33; vier der sechs Läufe von attnmem und vitmem liegen dort (0,30–0,38).
Streuung des Encoder-Ausgangs über die Vorlagen am Ende: Gitter-Netze 0,6–1,4, attnmem und vitmem 0,07–0,16
(mit einem Ziel 0,16–0,47).

**Vergleich mit der Vorhersage.** (1) Getroffen: 12 von 12 (0,75–0,87). (2) Für layer_s knapp getroffen (−0,05),
sonst verfehlt: layer_s_sp4 −0,06, layer_s_am4 −0,08, hier_s −0,09. Das zweite Ziel kostet schon bei A mehr als
erwartet. (3) Getroffen: B layer_s 0,79, 0,07 unter A; `near_both` 0,72. (4) Getroffen, aber nur durch
layer_s_am4 (−0,12); layer_s_sp4 liegt gleichauf (0,79). (5) Verfehlt: Kein Gitter-Lauf fällt bei B ab, der
schwächste liegt bei 0,63 (hier_s Seed 1). (6) Getroffen: attnmem 0,25, vitmem 0,23.

**Schluss.** (a) Die Stufe trennt die Bauarten deutlich stärker als die mit einem Ziel: `near_both` layer_s =
layer_s_sp4 0,72 > layer_s_am4 0,57 ≈ hier_s 0,55 >> attnmem 0,25 ≈ vitmem 0,23. Mit einem Ziel lagen die vier
Gitter-Netze innerhalb von 0,06. (b) Die Gitter-Netze behalten zwei Formen in Reihenfolge; keiner der 12 Läufe
scheitert an B. Der Abfall verteilt sich: Schon A nach Schritt 1 ist 0,05–0,11 schwächer als mit einem Ziel
(ein zweiter Inhalt stört den ersten), B verliert gegenüber A weitere 0,06–0,12. (c) Die Inhaltsadressierung
(layer_s_am4), gebaut für mehrere gleichzeitige Inhalte, hilft hier nicht; sie liegt 0,15 unter layer_s. Auch
der Notizblock (layer_s_sp4) bringt nichts. Die Rekurrenz von layer_s genügt für zwei Formen. hier_s fällt
gegenüber einem Ziel am stärksten zurück (Abstand zu layer_s 0,05 → 0,17). (d) attnmem und vitmem scheitern in
vier von sechs Läufen ganz (Zufall), die anderen zwei erreichen 0,58–0,60. Ihr Encoder-Ausgang unterscheidet die
Vorlagen kaum (Streuung 0,07–0,16); ob das Ursache oder Folge ist, ist nicht geprüft. (e) Die verbleibende
Fehlerart ist wie bisher der falsche Körper; ob der B-Fehler am Ende „bei A geblieben“ oder „zum dritten
Körper“ ist, unterscheidet die Auswertung noch nicht. (f) Prognose-Bezug: Die Reihenfolge mit einem Ziel (layer_s
≈ sp4 > hier_s ≈ am4 > attnmem > vitmem) sagt die mit zwei Zielen richtig vorher, die Abstände aber nicht.

**Belege.** `results/finds_loop.jsonl` (Zeilen `robot_loop_two_f32`), `results/loop_refcurve.jsonl` (18 Läufe mit
`ref_curve`); Netze in `results/checkpoints/robot_loop_two_f32`.

## 2026-11-17 — Zwei Ziele: Woraus die Fehler bestehen

**Frage.** Wenn ein Netz B verfehlt: Ist es bei A geblieben (der Wechsel misslingt) oder zum dritten Körper C
gegangen (die Form von B ist verwechselt oder vergessen)?

**Gemacht.** Reine Auswertung der 18 Netze aus dem Eintrag davor. `scripts/finds_loop_eval.py` ordnet jeden
Lauf zur Halbzeit (nach 3 Schritten) und am Ende (nach 6) ein: nahe dem Ziel, nahe dem anderen Ziel, nahe C, bei
keinem, aus dem Bild (in dieser Rangfolge; „nahe“ = höchstens eine Zelle). Dazu das Ende nur für Läufe, die A zur
Halbzeit erreicht haben. 1500 Startszenen, alle 6 geordneten Paare (Commit 2f9f203). Vorhersage vor dem Lauf
(wörtlich aus „Laufend / offen“):

> - B-Fehler aufteilen (Auftrag Nutzer 2026-11-17), reine Auswertung der Netze aus dem Eintrag davor:
>   `finds_loop_eval.py` ordnet jeden Lauf zur Halbzeit und am Ende ein: nahe A / nahe B / nahe dem dritten Körper C
>   / bei keinem / aus dem Bild; zusätzlich das Ende nur für Läufe, die A gelöst haben. Vor dem vollen Lauf
>   gesehen: ein Probelauf auf 50 Szenen mit layer_s Seed 0 (Ende: B 0,78, bei A 0,05, C 0,15; zur Halbzeit
>   „schon bei B“ 0,05; bei gelöstem A am Ende C 0,16, bei A 0,00).
>   **Vorhersage vor dem Lauf (2026-11-17, für die übrigen Netze):** (1) Bei allen vier Gitter-Netzen ist C am Ende
>   der größte Fehler-Anteil, „bei A geblieben“ höchstens 0,07. (2) Bei gelöstem A ist „bei A geblieben“ bei allen
>   Gitter-Netzen höchstens 0,02: Der Wechsel selbst gelingt, verwechselt wird die Form. (3) Vertauschte
>   Reihenfolge (zur Halbzeit schon bei B) liegt bei den Gitter-Netzen bei 0,03–0,10. (4) attnmem und vitmem: die
>   Fehler verteilen sich ungefähr gleich auf A und C (je 0,20–0,35), sie unterscheiden die Formen kaum.

**Ergebnis.** Anteile aller Läufe, Mittel über die Seeds 0–2 (die Seeds streuen bei den Gitter-Netzen um
höchstens 0,03).

| | Halbzeit: A / schon B / C / keiner | Ende: B / A / C / keiner | Ende bei gelöstem A: B / A / C / keiner |
|---|---|---|---|
| layer_s | 0,86 / 0,05 / 0,07 / 0,02 | 0,79 / 0,05 / 0,13 / 0,03 | 0,83 / 0,00 / 0,14 / 0,03 |
| layer_s_sp4 | 0,85 / 0,05 / 0,08 / 0,02 | 0,79 / 0,05 / 0,13 / 0,03 | 0,84 / 0,00 / 0,13 / 0,02 |
| hier_s | 0,77 / 0,08 / 0,12 / 0,03 | 0,65 / 0,08 / 0,20 / 0,06 | 0,72 / 0,01 / 0,22 / 0,05 |
| layer_s_am4 | 0,77 / 0,09 / 0,12 / 0,03 | 0,67 / 0,09 / 0,19 / 0,04 | 0,74 / 0,01 / 0,21 / 0,04 |
| attnmem | 0,43 / 0,23 / 0,26 / 0,08 | 0,43 / 0,23 / 0,27 / 0,07 | 0,55 / 0,02 / 0,38 / 0,06 |
| vitmem | 0,42 / 0,26 / 0,27 / 0,05 | 0,40 / 0,25 / 0,28 / 0,07 | 0,53 / 0,01 / 0,39 / 0,07 |

Aus dem Bild läuft kein Netz (höchstens 0,0002). In den Läufen von attnmem und vitmem, die bei Zufall liegen
(attnmem Seeds 0 und 2, vitmem Seeds 1 und 2), teilen sich die Läufe mit gelöstem A am Ende fast genau hälftig
auf B und C (0,45–0,50 / 0,42–0,46); bei A bleiben dort 0,01–0,02.

**Vergleich mit der Vorhersage.** (1) Teilweise getroffen: C ist bei allen vier Gitter-Netzen der größte
Fehler-Anteil (0,13–0,20). „Am Ende bei A“ liegt aber bei hier_s (0,08) und layer_s_am4 (0,09) über 0,07; nur
layer_s und layer_s_sp4 (0,05) halten die Grenze. (2) Getroffen: 0,00–0,01. (3) Getroffen: 0,05–0,09.
(4) Getroffen: A 0,23–0,25, C 0,27–0,28; die Deutung („unterscheiden die Formen kaum“) gilt, aber der A-Anteil
ist kein Hängenbleiben, siehe (b).

**Schluss.** (a) Der Wechsel von A zu B gelingt immer: Wer A erreicht hat, bleibt dort in höchstens 2 % der
Läufe, bei allen sechs Netzen. Zähler und Umschalten sind gelernt; die Fehler liegen bei den Formen.
(b) „Am Ende bei A“ entspricht in jedem Netz fast genau „zur Halbzeit schon bei B“ (0,05 / 0,05 bis 0,25 /
0,26), und bei gelöstem A kommt es nicht vor. Das passt zu vertauschter Reihenfolge: zuerst B, dann A, also beide
Formen behalten, nur die Reihenfolge verwechselt. Je Lauf verknüpft habe ich das nicht. (c) Der Hauptfehler der
Gitter-Netze ist C: zur Halbzeit 0,07–0,12 und am Ende bei gelöstem A 0,13–0,22. Die Form von B wird im Lauf
öfter verwechselt oder vergessen als die von A (C-Anteil am Ende etwa doppelt so hoch). Die Fehler bestehen also
aus Reihenfolge (0,05–0,09) und Form (0,13–0,20 am Ende); hier_s und layer_s_am4 verlieren gegenüber layer_s in
beiden. (d) attnmem und vitmem in den Läufen bei Zufall: Sie verlassen A sicher und wählen dann blind zwischen
B und C. Sie behalten also „wo ich war, gehe ich nicht wieder hin“ und die Zeit des Wechsels, aber keine Form.
Das passt zur kaum streuenden Encoder-Ausgabe (Eintrag davor) und spricht dafür, dass bei ihnen die Vorlage
nicht ins Gedächtnis kommt, nicht dass das Gedächtnis fehlt. Geprüft ist das nicht. (e) Für die nächste Stufe
heißt das: Mehr Formen zum Behalten (drei Ziele) trifft die Schwachstelle direkt; längere Läufe allein prüfen
eher den Zähler, der schon trägt.

**Belege.** `results/finds_loop.jsonl` (Zeilen `robot_loop_two_f32` mit `split_half`, `split_end`,
`split_end_a_ok`; die übrigen Werte dieser Zeilen gleichen den Zeilen des Eintrags davor, die Schleife ist
deterministisch).

## 2026-11-18 — Drei Ziele nacheinander: die Stufe ist zu steil für 12000 Updates

**Frage.** Hält die Reihenfolge der Gedächtnis-Bauarten aus zwei Zielen bei drei Zielen, wenn das letzte Ziel
nicht per Ausschluss zu finden ist (Folgen A, B, A)? Trennt die Form-Erinnerung die Netze noch deutlicher?

**Gemacht.** Aufgabe `robot_loop_three_f32`, sechs Netze `+refl+rez3` (die Gitter-Netze mit `+cell`), Seeds 0–2,
12000 Updates auf dem Worker (Job `20261117-220541-three_r2`, Commit 8a9bb27, gut 8 h). Schleife mit
`scripts/finds_loop_eval.py --task robot_loop_three_f32` auf den 1500 Startszenen, alle 12 Folgen je Szene,
9 Schritte. Vorhersage vor dem Lauf (wörtlich aus „Laufend / offen“):

> - Drei Ziele nacheinander (Auftrag Nutzer 2026-11-17): Aufgabe `robot_loop_three_f32`
>   (`scripts/make_loop_set.py --goals 3`): drei Hinweis-Schritte mit drei Vorlagen (Bild leer), dann 9 Bilder
>   eines Blicklaufs ohne Vorlage, je 3 Schritte zum ersten, zweiten, dritten Ziel. Die Ziele sind jede Folge der
>   drei Körper ohne direkte Wiederholung: A, B, C oder A, B, A (12 je Szene). Die Folgen mit Rückkehr sind nötig,
>   weil sonst das dritte Ziel per Ausschluss („wo ich noch nicht war“) ohne Form zu finden wäre; genau das tun
>   attnmem und vitmem auf zwei Zielen. Der Lehrer hält alle noch kommenden Ziele im Blickfeld (Folgen, bei denen
>   das nicht geht, fallen weg: 11 %). 28750 Trainingsfolgen (2 je Szene), Test 16201. Sechs Netze wie bei zwei
>   Zielen, `+refl+rez3`, Seeds 0–2, 12000 Updates. Schleife auf den 1500 Startszenen, alle 12 Folgen je Szene;
>   gemessen je Ziel am Ende seiner Schritte (`near_goal`), alle drei (`near_all`), getrennt nach A, B, C und
>   A, B, A; Fehler-Aufteilung je Ziel. Orakel 1,00 überall. Zufall ohne jede Form, aber mit Wissen um den
>   Wechsel: A 1/3, B 1/2, drittes Ziel 1/2, alle drei etwa 0,08.
>   **Vorhersage vor dem Lauf (2026-11-17):** (1) layer_s: `near_goal` A 0,78–0,86, B 0,68–0,80, drittes Ziel
>   0,60–0,78; `near_all` 0,40–0,62. (2) Reihenfolge wie bei zwei Zielen: layer_s und layer_s_sp4 innerhalb
>   ±0,03 bei `near_all`, hier_s und layer_s_am4 mindestens 0,08 darunter. (3) attnmem und vitmem: `near_all`
>   höchstens 0,20. (4) Bei den Gitter-Netzen ist das dritte Ziel bei gelöstem A und B in den Folgen A, B, A um
>   mindestens 0,03 leichter als in A, B, C (die Form von A kam zweimal). (5) Kein Gitter-Lauf bricht ein: In
>   allen 12 liegt das dritte Ziel bei `near` mindestens 0,5.

**Ergebnis.** `near_goal` = nahe dem jeweiligen Ziel am Ende seiner 3 Schritte; Mittel über die Seeds 0–2, dazu
`near_all` je Seed. Rechts: das dritte Ziel nur in Läufen mit A und B nahe, getrennt nach Folge (A, B, C: nahe C /
zurück zu einem früheren Ziel; A, B, A: nahe A / zum Körper, der kein Ziel ist).

| | A | B | drittes | `near_all` (Seeds 0 / 1 / 2) | A, B, C: C / früher | A, B, A: A / kein Ziel |
|---|---|---|---|---|---|---|
| layer_s | 0,81 | 0,65 | 0,60 | 0,44 (0,54 / 0,59 / 0,18) | 0,69 / 0,29 | 0,75 / 0,22 |
| layer_s_sp4 | 0,77 | 0,66 | 0,61 | 0,44 (0,52 / 0,61 / 0,19) | 0,71 / 0,27 | 0,79 / 0,19 |
| hier_s | 0,63 | 0,40 | 0,35 | 0,14 (0,14 / 0,13 / 0,15) | 0,38 / 0,58 | 0,57 / 0,38 |
| layer_s_am4 | 0,56 | 0,45 | 0,42 | 0,19 (0,14 / 0,35 / 0,08) | 0,48 / 0,49 | 0,64 / 0,32 |
| attnmem | 0,49 | 0,50 | 0,52 | 0,25 (0,07 / 0,32 / 0,37) | 0,67 / 0,30 | 0,75 / 0,22 |
| vitmem | 0,52 | 0,52 | 0,53 | 0,28 (0,45 / 0,07 / 0,32) | 0,67 / 0,30 | 0,76 / 0,21 |

Orakel 1,00 überall, Zufall bei `near_all` etwa 0,08. Aus dem Bild läuft kein Netz. Bei gelöstem A bleibt am
Ende von B kein Netz bei A (0,00–0,01), und in den Folgen A, B, A bleibt am Ende kein Netz bei B (0,00–0,01):
Das Verlassen des eben erreichten Körpers sitzt überall. Die Trainings-Werte (`final`) folgen der Schleife:
layer_s und sp4 Seeds 0/1 0,69–0,71, Seed 2 0,62; ihre Kurven steigen bei Seeds 0/1 zwischen 6000 und 9000
Updates von etwa 0,60 auf 0,70, Seed 2 bleibt bei 0,62 stehen.

**Vergleich mit der Vorhersage.** (1) Teilweise getroffen: A 0,81, drittes Ziel 0,60 (gerade an der unteren
Grenze), `near_all` 0,44 liegen im Bereich; B 0,65 liegt unter 0,68. Beides zieht Seed 2 herunter (B 0,44,
drittes 0,36; Seeds 0/1: B 0,73–0,77, drittes 0,69–0,75, `near_all` 0,54–0,59). (2) Getroffen: layer_s und sp4
beide 0,44; hier_s 0,14 und am4 0,19 liegen 0,25–0,30 darunter. (3) Nicht getroffen: attnmem 0,25 und vitmem
0,28 liegen über 0,20. Je zwei ihrer drei Seeds lernen die Aufgabe (0,32–0,45), je einer bleibt bei Zufall
(0,07). (4) Getroffen bei allen vier Gitter-Netzen: A, B, A ist um 0,06 (layer_s), 0,08 (sp4), 0,16 (am4) und
0,19 (hier_s) leichter; die Deutung stimmt aber nur zum Teil, siehe (c). (5) Nicht getroffen: Das dritte Ziel
liegt in 7 von 12 Gitter-Läufen unter 0,5 (hier_s alle drei 0,34–0,35, am4 Seeds 0 und 2, layer_s und sp4
Seed 2 0,36–0,37).

**Schluss.** (a) Die Reihenfolge aus zwei Zielen hält im Mittel (layer_s = sp4 > am4 ≈ hier_s), die Abstände
wachsen: hier_s fällt von 0,55 (zwei Ziele) auf 0,14, layer_s von 0,72 auf 0,44. (b) Die Stufe liegt für
12000 Updates an der Lernbarkeits-Kante: Bei zwei Zielen streuten die Gitter-Netze um höchstens 0,03, jetzt
layer_s und sp4 von 0,18 bis 0,61. Seed 2 bricht bei beiden gleich ein, und zwar in einem Muster: A gelingt
(0,71–0,77), B und das dritte Ziel fallen nahe Zufall. Die stehenbleibende Trainingskurve passt zu „den Sprung
noch nicht gemacht“, nicht zu „kann es nicht“; geprüft ist das nicht. (c) hier_s und am4 haben eine Neigung
zurück zum ersten Ziel: In A, B, C gehen sie in 0,49–0,58 der Läufe zu A zurück, liegen beim dritten Ziel also
bei oder unter Zufall (0,38–0,48 gegen 0,5). Ihr Vorteil in A, B, A ist diese Neigung, nicht eine bessere
Form-Erinnerung. Bei layer_s und sp4 ist der Unterschied klein (0,06–0,08); dort trägt die Form. (d) attnmem und
vitmem zeigen ein anderes Bild als die Gitter-Netze: Sie verlieren über die drei Ziele nichts (je Ziel 0,49–0,53),
ihr Problem ist schon das erste Ziel, und je Seed lernen sie die Aufgabe ganz oder gar nicht. In ihren guten
Seeds liegen sie mit 0,32–0,45 über layer_s Seed 2 und über hier_s. Bei gelöstem A und B finden sie das
dritte Ziel so gut wie layer_s (0,67–0,76). Die Bauarten unterscheiden sich also darin, ob sie lernen (Seeds),
nicht darin, was sie behalten, sobald sie gelernt haben. Mit drei Seeds ist das ein Hinweis, kein Befund.
(e) Prognose-Bezug: Zwei Ziele sagen die Reihenfolge bei drei Zielen richtig voraus, die Zuverlässigkeit
je Seed aber nicht. Für eine Prognose an den Roboter ist die Streuung je Seed hier die wichtigere Größe.
(f) Offen und naheliegend: dieselbe Stufe mit 24000 Updates (nur layer_s und sp4, Seeds 0–2), um (b) zu
prüfen; nicht gestartet.

**Belege.** `results/finds_loop.jsonl` (Zeilen `robot_loop_three_f32` mit `near_goal`, `near_all`,
`near_all_new`/`_ret`, `split`, `split_prev_ok`, `split_last_new`/`_ret`), `results/loop_refcurve.jsonl`
(18 Läufe `robot_loop_three_f32:12000` mit Kurven); Netze in `results/checkpoints/robot_loop_three_f32`.

## 2026-11-18 — Drei Ziele mit 24000 Updates: sp4 wird verlässlich, layer_s nicht

**Frage.** Hatte Seed 2 von layer_s und layer_s_sp4 bei drei Zielen mit 12000 Updates den Sprung nur noch nicht
gemacht? Wird die Stufe mit doppelt so vielen Updates verlässlich?

**Gemacht.** Dieselbe Aufgabe `robot_loop_three_f32`, layer_s und layer_s_sp4 (`+cell+refl+rez3`), Seeds 0–2,
24000 Updates (Job `20261118-060635-three24k`, Commit 5ad8ba8). Das ist keine Fortsetzung der 12000er-Läufe:
Warm-up und Kosinus-Abfall der Lernrate richten sich nach der Gesamtzahl der Updates, jeder Seed nimmt also einen
eigenen Weg. Schleife wie zuvor (`finds_loop_eval.py --ckpt robot_loop_three_f32_24k`), 1500 Szenen, 12 Folgen.
Vorhersage vor dem Lauf (wörtlich aus „Laufend / offen“):

> - Drei Ziele mit 24000 Updates (Auftrag Nutzer 2026-11-18): dieselbe Aufgabe `robot_loop_three_f32` wie im
>   Eintrag davor, nur layer_s und layer_s_sp4 (`+cell+refl+rez3`), Seeds 0–2, 24000 statt 12000 Updates,
>   Checkpoints unter `robot_loop_three_f32_24k` (`finds_loop_eval.py --ckpt`). Prüft, ob Seed 2 bei 12000 Updates
>   den Sprung (Trainingswert 0,62 → 0,70) nur noch nicht gemacht hatte. Schleife wie zuvor, 1500 Szenen, 12 Folgen.
>   **Vorhersage vor dem Lauf (2026-11-18):** (1) Seed 2 macht den Sprung bei beiden Netzen: `near_all` ≥ 0,45,
>   Trainingswert `final` ≥ 0,68. (2) Seeds 0 und 1 gewinnen höchstens wenig: `near_all` je Lauf zwischen dem
>   12000er-Wert −0,02 und +0,08. (3) Damit streuen die drei Seeds je Netz um höchstens 0,10 bei `near_all`,
>   Mittel 0,52–0,65. (4) layer_s und sp4 bleiben innerhalb ±0,04 im Mittel. (5) Beim dritten Ziel in A, B, C
>   (bei gelöstem A und B) bleibt „zurück zu einem früheren Ziel“ der Hauptfehler, 0,15–0,28.

**Ergebnis.** `near_goal` je Ziel und `near_all` je Seed, in Klammern der Wert mit 12000 Updates; rechts der
Trainingswert `final`.

| | Seed | A | B | drittes | `near_all` (12000) | `final` (12000) |
|---|---|---|---|---|---|---|
| layer_s | 0 | 0,90 | 0,84 | 0,83 | 0,72 (0,54) | 0,74 (0,69) |
| layer_s | 1 | 0,88 | 0,47 | 0,37 | 0,21 (0,59) | 0,65 (0,71) |
| layer_s | 2 | 0,87 | 0,80 | 0,77 | 0,64 (0,18) | 0,72 (0,62) |
| layer_s_sp4 | 0 | 0,89 | 0,84 | 0,83 | 0,71 (0,52) | 0,74 (0,69) |
| layer_s_sp4 | 1 | 0,91 | 0,86 | 0,86 | 0,75 (0,61) | 0,75 (0,71) |
| layer_s_sp4 | 2 | 0,89 | 0,86 | 0,85 | 0,73 (0,19) | 0,75 (0,62) |

Mittel `near_all`: layer_s 0,52 (12000: 0,44), sp4 0,73 (0,44). Drittes Ziel in A, B, C bei gelöstem A und B:
layer_s 0,73, zurück zu einem früheren Ziel 0,26 (Seed 1 allein 0,56, Seeds 0/2 0,08–0,12); sp4 0,91 / 0,07.
In A, B, A: layer_s 0,78 / 0,20 zum Körper ohne Ziel, sp4 0,93 / 0,06. Der eingebrochene Lauf (layer_s Seed 1)
zeigt dasselbe Muster wie Seed 2 bei 12000: A gelingt (0,88), B und das dritte Ziel nahe Zufall, die
Trainingskurve bleibt ab etwa 11000 Updates bei 0,63–0,65 stehen.

**Vergleich mit der Vorhersage.** (1) Getroffen: Seed 2 macht bei beiden den Sprung (`near_all` 0,64 / 0,73,
`final` 0,72 / 0,75). (2) Nicht getroffen: Die Seeds 0 und 1 gewinnen viel mehr als +0,08 (sp4 +0,14 bis +0,19,
layer_s Seed 0 +0,19), und layer_s Seed 1 fällt um 0,38. (3) Nicht getroffen: sp4 streut nur um 0,04, liegt mit
0,73 aber über 0,52–0,65; layer_s liegt mit 0,52 im Bereich, streut aber um 0,51. (4) Nicht getroffen: sp4 liegt
0,21 über layer_s. (5) Teilweise: Bei layer_s ist „zurück zu einem früheren Ziel“ mit 0,26 der Hauptfehler im
Bereich (getragen von Seed 1), bei sp4 bleibt es der Hauptfehler, liegt mit 0,07 aber unter 0,15.

**Schluss.** (a) Die Deutung aus dem Eintrag davor („Seed 2 hatte den Sprung nur noch nicht gemacht“) war
zu eng. Mit mehr Updates lernen alle Läufe mehr, aber ob ein Lauf den Sprung schafft, ist bei layer_s Glückssache
je Trainingsweg: Seed 1 schaffte ihn mit 12000 und verfehlt ihn mit 24000, Seed 2 umgekehrt. Bei layer_s steht es
mit beiden Längen 2 von 3 Läufen gelöst. (b) layer_s_sp4 schafft ihn mit 24000 Updates in allen drei Läufen, eng
beieinander (0,71–0,75), und behält auch die Form des dritten Ziels (0,91–0,93 bei gelöstem A und B). Zum
ersten Mal hebt der Notizblock (sp4) sich klar von layer_s ab; bei einem und zwei Zielen lagen beide gleichauf.
Mit drei Seeds ist „3 von 3 gegen 2 von 3“ allerdings kein Beleg für eine höhere Lösequote; der Abstand der
gelösten Läufe (sp4 0,71–0,75 gegen layer_s 0,64–0,72) ist der festere Teil. (c) Der eingebrochene Lauf hat
immer dasselbe Muster: A gelingt, B und das dritte Ziel nicht. Gelernt wird also zuerst das erste Ziel, der Sprung
ist das Behalten und Abrufen der weiteren Formen. (d) Prognose-Bezug: Bei 12000 Updates waren layer_s und sp4
gleich, bei 24000 nicht. Wie lange trainiert wird, entscheidet hier über die Rangfolge; Vergleiche auf dieser
Stufe brauchen die längere Trainingszeit. (e) Offen: Lösequote mit mehr Seeds (z. B. 6 je Netz) bei 24000
Updates, um (b) zu prüfen; nicht gestartet.

**Belege.** `results/finds_loop.jsonl` (Zeilen `robot_loop_three_f32` mit `"ckpt": "robot_loop_three_f32_24k"`),
`results/loop_refcurve.jsonl` (6 Läufe `robot_loop_three_f32:24000` mit Kurven); Netze in
`results/checkpoints/robot_loop_three_f32_24k`.

## 2026-11-18 — Drei Ziele, Lösequote mit sechs Seeds: sp4 6 von 6, layer_s 3 von 6

**Frage.** Lernt layer_s_sp4 drei Ziele nacheinander bei 24000 Updates zuverlässiger als layer_s, oder war
„3 von 3 gegen 2 von 3“ im Eintrag davor Zufall?

**Gemacht.** Wie im Eintrag davor, drei weitere Seeds 3, 4, 7 je Netz (Job `20261118-121830-three24k_seeds`,
Commit 552a890), Schleife mit `finds_loop_eval.py --ckpt robot_loop_three_f32_24k --seeds 3 4 7`. Zusammen mit
den Seeds 0–2 sechs Läufe je Netz. Vorhersage vor dem Lauf (wörtlich aus „Laufend / offen“):

> - Lösequote bei drei Zielen mit 24000 Updates (Auftrag Nutzer 2026-11-18): layer_s und layer_s_sp4
>   (`+cell+refl+rez3`), drei weitere Seeds 3, 4, 7 (5 und 6 bleiben für Abstimmung frei, wie bei der Studie mit
>   acht Seeds), sonst wie im Eintrag davor; zusammen mit Seeds 0–2 sechs Läufe je Netz. „Gelöst“ = `near_all` ≥ 0,45
>   (bisher liegen eingebrochene Läufe bei 0,18–0,21, gelöste bei 0,52–0,75).
>   **Vorhersage vor dem Lauf (2026-11-18):** (1) sp4 löst 5 oder 6 von 6, layer_s 3 bis 5 von 6; sp4 löst
>   mindestens einen Lauf mehr als layer_s. (2) Die gelösten Läufe von sp4 liegen im Mittel mindestens 0,03 über
>   denen von layer_s. (3) Jeder eingebrochene Lauf hat das bekannte Muster: A ≥ 0,80, drittes Ziel ≤ 0,45,
>   Trainingswert `final` ≤ 0,66. (4) Alle gelösten Läufe beider Netze: `near_all` 0,60–0,78.

**Ergebnis.** Alle sechs Läufe je Netz; Seeds 3, 4, 7 neu.

| | Seed | A | B | drittes | `near_all` | `final` | drittes in A, B, C bei gelöstem A und B: C / früher |
|---|---|---|---|---|---|---|---|
| layer_s | 0 | 0,90 | 0,84 | 0,83 | 0,72 | 0,740 | 0,90 / 0,08 |
| layer_s | 1 | 0,88 | 0,47 | 0,37 | 0,21 | 0,647 | 0,41 / 0,56 |
| layer_s | 2 | 0,87 | 0,80 | 0,77 | 0,64 | 0,717 | 0,86 / 0,12 |
| layer_s | 3 | 0,86 | 0,52 | 0,38 | 0,23 | 0,646 | 0,42 / 0,56 |
| layer_s | 4 | 0,87 | 0,53 | 0,40 | 0,24 | 0,651 | 0,45 / 0,52 |
| layer_s | 7 | 0,91 | 0,86 | 0,84 | 0,74 | 0,752 | 0,90 / 0,08 |
| layer_s_sp4 | 0 | 0,89 | 0,84 | 0,83 | 0,71 | 0,742 | 0,90 / 0,08 |
| layer_s_sp4 | 1 | 0,91 | 0,86 | 0,86 | 0,75 | 0,747 | 0,92 / 0,06 |
| layer_s_sp4 | 2 | 0,89 | 0,86 | 0,85 | 0,73 | 0,745 | 0,92 / 0,07 |
| layer_s_sp4 | 3 | 0,91 | 0,87 | 0,86 | 0,76 | 0,755 | 0,92 / 0,07 |
| layer_s_sp4 | 4 | 0,90 | 0,86 | 0,85 | 0,75 | 0,750 | 0,92 / 0,07 |
| layer_s_sp4 | 7 | 0,89 | 0,85 | 0,84 | 0,73 | 0,738 | 0,92 / 0,07 |

Gelöst (`near_all` ≥ 0,45): sp4 6 von 6 (0,71–0,76, Mittel 0,74), layer_s 3 von 6 (0,64–0,74, Mittel 0,70).
Die Läufe sind klar zweigeteilt: eingebrochen 0,21–0,24 bei `final` 0,646–0,651, gelöst ab 0,64 bei `final` ab
0,717; dazwischen liegt nichts. Exakter Test nach Fisher (einseitig, 6/6 gegen 3/6): p = 0,09.

**Vergleich mit der Vorhersage.** (1) Getroffen: sp4 6 von 6, layer_s 3 von 6 (untere Grenze), sp4 drei Läufe
mehr. (2) Getroffen: gelöste Läufe sp4 0,74 gegen layer_s 0,70, +0,04. (3) Getroffen: alle drei eingebrochenen
Läufe A 0,86–0,88, drittes Ziel 0,37–0,40, `final` 0,646–0,651. (4) Getroffen: gelöste Läufe 0,64–0,76.

**Schluss.** (a) Mit 24000 Updates lernt layer_s_sp4 die Stufe in 6 von 6 Läufen, layer_s in 3 von 6. Das ist der
erste Unterschied zwischen beiden auf der ganzen Leiter der Blickschleife. Mit p = 0,09 bei sechs Läufen je Netz
ist er ein deutlicher Hinweis, aber kein sicherer Befund. Für die Rangfolge der Gedächtnis-Bauarten heißt das:
Der Notizblock hilft hier beim Lernen, kaum beim Ergebnis (gelöste Läufe +0,04). (b) Ein eingebrochener Lauf ist
ein eigener, stabiler Zustand: A sicher, dann beim dritten Ziel in A, B, C mehr als die Hälfte zurück zu einem
früheren Ziel, also dieselbe Neigung wie hier_s und layer_s_am4 im Eintrag „Drei Ziele nacheinander“. Das Netz
behält die Form von A, aber nicht die von B und C. (c) Der Trainingswert trennt gelöst und eingebrochen sauber
(Lücke 0,651 bis 0,717); er reicht hier als Lösungs-Kennzeichen, ohne die Schleife zu fahren. (d) Prognose-Bezug:
Auf dieser Stufe sagt die Bauart die Zuverlässigkeit vorher, nicht die erreichte Höhe. Für den Roboter wäre
das die Frage, ob ein Netz beim Nachtrainieren verlässlich ankommt. (e) Offen: Warum layer_s in einem Teil der
Läufe nur A behält. Vermutung: Die Formen von B und C müssen durch dasselbe Gitter-Gedächtnis, das schon A hält,
und der Notizblock gibt ihnen einen eigenen Platz; geprüft ist das nicht.

**Belege.** `results/finds_loop.jsonl` (Zeilen `robot_loop_three_f32` mit `"ckpt": "robot_loop_three_f32_24k"`,
Seeds 0–4 und 7), `results/loop_refcurve.jsonl` (12 Läufe `robot_loop_three_f32:24000`); Netze in
`results/checkpoints/robot_loop_three_f32_24k`.

## 2026-11-18 — Drei Ziele: Die eingebrochenen layer_s-Läufe schreiben B und C, verlieren sie aber beim Losgehen

**Frage.** Warum behalten drei von sechs layer_s-Läufen (24000 Updates) nur das erste Ziel? Kommen die Formen von
B und C gar nicht ins Gedächtnis, werden sie später überschrieben, oder sind sie da und werden nicht genutzt?

**Gemacht.** Reine Auswertung der 12 Netze aus dem Eintrag davor, lokal. `scripts/loop_goals_probe.py`
(Commit 0470a13): 3000 Testfolgen, die Netze laufen über die Blicke des Lehrers (alle Netze sehen dieselben
Bilder), nach jedem der 12 Schritte (0–2 Hinweise, 3–5 zu A, 6–8 zu B, 9–11 zum dritten Ziel) liest eine lineare
Ridge-Auslese die Form jedes Ziels aus dem ganzen Zustand; Ziel C nur in Folgen A, B, C. Boden (frühere Formen
allein): A 0,19, B 0,26, C 0,33. Panne beim Anlegen: Ich hatte zuerst das vorhandene `scripts/loop_state_probe.py`
mit dem neuen Skript überschrieben; aus git wiederhergestellt, unverändert, nicht committet.
Nachtrag zu früheren Einträgen dieses Tages (Bedienfehler und verworfene Entwürfe, die dort fehlen): (i) Der erste
Datensatz für drei Ziele enthielt nur Folgen A, B, C; während des Bauens verworfen, weil das dritte Ziel dort per
Ausschluss ohne Form zu finden wäre; ersetzt durch A, B, C und A, B, A. (ii) Der erste Trainingsjob für drei Ziele
(`three_r1`) brach nach einer Minute ab, weil ich ein überzähliges `run` übergab („unrecognized arguments: run“);
neu eingereicht als `three_r2`. (iii) Die Commit-Nachricht zu drei Zielen mit 12000 Updates zählt die Vorhersage
als „3 of 5 hit“; richtig sind 2 getroffen, 1 teilweise, 2 nicht (so steht es auch im Eintrag).
Vorhersage vor dem Lauf (wörtlich aus „Laufend / offen“):

> - Warum layer_s oft nur das erste Ziel behält (Auftrag Nutzer 2026-11-18): reine Auswertung der 12 Netze mit
>   24000 Updates (layer_s und sp4, Seeds 0–4, 7; layer_s 1, 3, 4 eingebrochen). Neues Skript
>   `scripts/loop_goals_probe.py`: die Netze laufen mit Lehrer-Blicken über 3000 Testfolgen (Vorlagen-Ansicht 0); nach
>   jedem der 12 Schritte liest eine lineare Auslese (Ridge wie in `loop_state_probe.py`, auf der Hälfte der Szenen
>   angepasst, auf der anderen gemessen) die Form jedes Ziels aus dem Zustand. Ziel C nur in Folgen A, B, C. Boden =
>   was die früheren Formen allein verraten: A 0,17, B 0,27, C 0,35 (Probe an hier_s 12000, 400 Folgen, nur zum
>   Testen des Skripts). Dazu Streuung und Auslese des Vorlagen-Encoders. Unterscheidet: nicht geschrieben (gleich
>   nach dem eigenen Hinweis-Schritt nicht lesbar), überschrieben (danach nicht mehr), nicht genutzt (lesbar, aber
>   das Netz geht woandershin).
>   **Vorhersage vor dem Lauf (2026-11-18):** (1) Der Encoder ist nicht die Ursache: Streuung und Encoder-Auslese
>   der eingebrochenen layer_s-Läufe liegen innerhalb ±20 % (relativ) der gelösten. (2) Überschrieben, nicht
>   ungeschrieben: In den eingebrochenen Läufen ist B direkt nach seinem Hinweis-Schritt (Schritt 1) lesbar (≥ 0,50),
>   am Ende der A-Strecke (nach Schritt 5) aber höchstens 0,10 über dem Boden. (3) In allen gelösten Läufen (layer_s
>   und sp4) ist B nach Schritt 5 ≥ 0,50 und C nach Schritt 8 ≥ 0,50 lesbar. (4) A ist in allen 12 Läufen nach
>   Schritt 2 (letzter Hinweis) ≥ 0,60 lesbar. (5) sp4 hält B nach Schritt 5 im Mittel mindestens so gut wie die
>   gelösten layer_s-Läufe.

**Ergebnis.** Lesbarkeit der Form (Anteil richtig) nach ausgewählten Schritten, je Gruppe Spanne über die Läufe.

| | A nach 2 | B nach 1 | C nach 2 | B nach 3 | B nach 5 | C nach 5 | C nach 8 | A nach 11 |
|---|---|---|---|---|---|---|---|---|
| layer_s eingebrochen (1, 3, 4) | 0,94 | 0,92–0,94 | 0,86–0,92 | 0,47–0,49 | 0,28–0,38 | 0,28–0,29 | 0,23–0,24 | 0,24–0,26 |
| layer_s gelöst (0, 2, 7) | 0,90–0,96 | 0,91–0,97 | 0,89–0,95 | 0,54–0,64 | 0,50–0,61 | 0,47–0,53 | 0,44–0,51 | 0,27–0,28 |
| sp4 (alle 6) | 0,94–0,96 | 0,94–0,96 | 0,93–0,95 | 0,65–0,73 | 0,55–0,59 | 0,46–0,54 | 0,45–0,51 | 0,40–0,45 |

Vorlagen-Encoder: Streuung 1,06–1,70, Auslese 0,57–0,66, ohne Unterschied zwischen eingebrochen (1,14–1,60) und
gelöst (1,11–1,70). In allen Netzen steigt die Lesbarkeit eines Ziels wieder, sobald der Blick auf ihm liegt
(B nach 7–8, C nach 10–11, auch in den eingebrochenen Läufen bis 0,61 bzw. 0,54): Das ist das Bild, nicht das
Gedächtnis. Sauber trennt nur die Zeit, bevor das Ziel angeblickt wird: B nach 3–5, C nach 5–8.

**Vergleich mit der Vorhersage.** (1) Getroffen: Der Encoder unterscheidet sich nicht. (2) Teilweise: B ist nach
seinem Hinweis-Schritt lesbar (0,92–0,94); nach Schritt 5 liegt B bei zwei Läufen höchstens 0,10 über dem Boden
(0,28, 0,34), bei Seed 4 mit 0,38 aber 0,12 darüber. (3) Nicht getroffen: B nach 5 ist in allen gelösten Läufen
≥ 0,50 (0,50–0,61), C nach 8 aber nur in 2 von 9 (0,44–0,51), obwohl diese Läufe das dritte Ziel in 0,77–0,86 finden.
(4) Getroffen: A nach dem letzten Hinweis 0,90–0,97. (5) Getroffen: sp4 B nach 5 im Mittel 0,58, gelöste
layer_s 0,56.

**Schluss.** (a) Die eingebrochenen Läufe schreiben alle drei Formen ins Gedächtnis (nach dem letzten Hinweis
0,86–0,94 lesbar, wie die gelösten), verlieren B und C aber in den ersten Schritten der Strecke zu A: schon nach
dem ersten Lauf-Schritt fällt B auf 0,47–0,49, nach dem dritten liegen B und C am Boden. Es ist also
„überschrieben“, nicht „nicht geschrieben“ und nicht der Eingang. Die Ursache ist der Übergang von Hinweis zu
Lauf: Mit den ersten echten Bildern verdrängt der Blick die gemerkten Formen. (b) A überlebt in den eingebrochenen
Läufen nur, weil der Blick ohnehin auf A zuläuft; das passt zum Fehlerbild „A sicher, danach zurück“. (c) Die
gelösten layer_s-Läufe halten B und C nach dem ersten Lauf-Schritt etwas besser (0,54–0,64), sp4 am besten
(0,65–0,73). Der Unterschied zwischen gelöst und eingebrochen entsteht also in den ersten Lauf-Schritten; der
Notizblock hilft genau dort, danach liegen sp4 und gelöste layer_s gleichauf. sp4 hält außerdem A bis zum Ende
(0,40–0,45 gegen 0,24–0,28), braucht es aber nicht mehr. (d) Die Auslese unterschätzt, was die gelösten Netze
vom dritten Ziel wissen: Lesbar ist C vor dem Hinblicken nur zu 0,44–0,51, gefunden wird das dritte Ziel zu 0,77–0,86.
Naheliegende Deutung, nicht geprüft: Sobald die Szene sichtbar ist, merken die Netze nicht mehr die Form, sondern
wo der Körper liegt. Das wäre mit einer Auslese der Lage (statt der Form) zu prüfen. (e) Zur Frage „eigener
Platz für B und C“ aus dem Eintrag davor: Die Vermutung trifft den Ort (Verdrängung durch die laufende
Eingabe), aber nicht ganz den Mechanismus: Der Notizblock von sp4 ist klein (4 Werte je Zelle, 128 von 2304),
und ob B und C dort liegen, ist nicht gemessen. Eine Auslese nur aus dem Notizblock würde das klären.

**Belege.** `results/loop_goals_probe.jsonl` (12 Zeilen: `probe[t][k]`, `floor`, `enc_spread`, `enc_probe`),
Skript `scripts/loop_goals_probe.py`.

## 2026-11-18 — Form oder Lage: Die Netze merken die Form, die Lage aller Körper kennen alle; der Notizblock trägt die Formen

**Frage.** Merken sich die gelösten Netze nach dem Losgehen die Lage der kommenden Ziele statt ihrer Form (Vermutung
aus dem Eintrag davor)? Liegen bei sp4 die Formen im Notizblock?

**Gemacht.** Reine Auswertung der 12 Netze mit 24000 Updates, lokal, `scripts/loop_where_probe.py` (Commit
03dddba), 3000 Orakel-Läufe. Vorhersage vor dem Lauf (wörtlich aus „Laufend / offen“):

> - Form oder Lage, und der Notizblock (Auftrag Nutzer 2026-11-18): reine Auswertung derselben 12 Netze (24000
>   Updates). Neues Skript `scripts/loop_where_probe.py`: Orakel-Läufe (der Blick nimmt den wahren Schritt, alle Netze
>   sehen dieselben Bilder), 3000 Läufe über alle 12 Folgen. Lineare Ridge-Auslese nach jedem Schritt: Form jedes
>   Ziels (Anteil richtig) und Lage jedes Ziels als Pixel-Abstand vom Blickpunkt (R², Mittel beider Achsen); Kontrolle:
>   Lage des Körpers, der kein Ziel ist (Folgen A, B, A). Boden „view“: dieselbe Auslese aus dem Zustand nach nur dem
>   aktuellen Bild, frisches Gedächtnis, leere Vorlage. Bei sp4 zusätzlich getrennt aus dem Gitter (2176 Werte), aus
>   dem Notizblock (128 Werte) und aus 128 zufälligen Gitter-Werten. Vor dem Lauf gesehen nur Probeläufe zum Testen
>   des Skripts an hier_s und sp4 mit 12000 Updates (300 Läufe), nicht an den untersuchten Netzen.
>   **Vorhersage vor dem Lauf (2026-11-18):** (1) Lage statt Form: In allen 9 gelösten Läufen ist die Lage von C nach
>   Schritt 8 (Blick auf B) um mindestens 0,15 R² besser lesbar als im Boden „view“. (2) In den 3 eingebrochenen
>   layer_s-Läufen liegt die Lage von C nach Schritt 8 höchstens 0,05 über dem Boden. (3) Der Boden für die Lage
>   eines Ziels liegt nach den Schritten 5 und 8 bei höchstens 0,30 R². (4) Notizblock: Bei sp4 ist die Form von B
>   nach Schritt 5 aus dem Notizblock allein um mindestens 0,10 besser lesbar als aus 128 zufälligen Gitter-Werten,
>   in mindestens 5 der 6 Läufe. (5) Die Form-Auslese auf Orakel-Läufen wiederholt das Bild der Lehrer-Läufe: B nach
>   Schritt 5 in den eingebrochenen Läufen höchstens 0,12 über 0,26, in den gelösten mindestens 0,45.

**Ergebnis.** (i) Lage, ganzer Zustand gegen Boden „view“, R². Nach Schritt 5 liegt der Blick auf A, B und C sind
noch nicht angeblickt; nach Schritt 8 liegt er auf B, A ist besucht, C nicht.

| | Lage B nach 5 (view) | Lage C nach 5 (view) | Lage A nach 8 (view) | Lage C nach 8 (view) | kein Ziel nach 8 |
|---|---|---|---|---|---|
| layer_s eingebrochen (1, 3, 4) | 0,34–0,39 (0,40–0,43) | 0,04–0,14 (0,31–0,36) | 0,85–0,89 (0,37–0,43) | 0,72–0,77 (0,23–0,27) | 0,71–0,78 |
| layer_s gelöst (0, 2, 7) | 0,44–0,49 (0,43–0,48) | 0,23–0,28 (0,33–0,37) | 0,84–0,89 (0,42–0,43) | 0,67–0,75 (0,27–0,33) | 0,70–0,77 |
| sp4 (alle 6) | 0,40–0,44 (0,38–0,44) | 0,22–0,25 (0,28–0,40) | 0,87–0,91 (0,37–0,41) | 0,75–0,78 (0,21–0,28) | 0,74–0,77 |

(ii) Form (Anteil richtig, Boden B 0,26, C 0,33), ganzer Zustand: B nach 5 eingebrochen 0,31–0,39, gelöst
layer_s 0,55–0,64, sp4 0,59–0,64; C nach 8 eingebrochen 0,24–0,27, gelöst 0,46–0,57, sp4 0,51–0,54.

(iii) sp4 nach Teilen des Zustands (Form; Gitter 2176 Werte, Notizblock 128, 128 zufällige Gitter-Werte):

| | Notizblock | Gitter ganz | 128 Gitter-Werte |
|---|---|---|---|
| B nach 3 (erster Lauf-Schritt) | 0,66–0,75 | 0,55–0,59 | 0,42–0,47 |
| B nach 5 | 0,61–0,66 | 0,55–0,59 | 0,52–0,56 |
| C nach 8 | 0,54–0,60 | — | 0,48–0,52 |
| A nach 11 (Ziel erledigt) | 0,57–0,64 | — | 0,33–0,39 |
| Lage C nach 8 (R²) | 0,40–0,54 | — | 0,68–0,72 |

**Vergleich mit der Vorhersage.** (1) In der Zahl getroffen, in der Sache nicht: Die Lage von C nach Schritt 8
liegt in allen gelösten Läufen 0,39–0,54 über dem Boden, aber ebenso in den eingebrochenen und ebenso für den
Körper, der kein Ziel ist; das ist kein Gedächtnis für das Ziel, siehe (a). (2) Nicht getroffen: Die
eingebrochenen Läufe liegen 0,49–0,50 über dem Boden. (3) Nicht getroffen: Der Boden liegt nach Schritt 5 für B
bei 0,38–0,48, für C bei 0,28–0,40; nach Schritt 8 für C bei 0,21–0,33. (4) Nicht getroffen: Der Vorsprung des
Notizblocks vor 128 zufälligen Gitter-Werten beträgt nach Schritt 5 nur in 2 von 6 Läufen mindestens 0,10
(0,07–0,12); nach dem ersten Lauf-Schritt (Schritt 3) ist er aber 0,22–0,29. (5) Teilweise: gelöste 0,55–0,64
(≥ 0,45); eingebrochene 0,31, 0,37, 0,39, also einer 0,01 über der Grenze von 0,38.
Zusammen: 1 getroffen (nur in der Zahl), 1 teilweise, 3 nicht.

**Schluss.** (a) Die Vermutung „Lage statt Form“ ist widerlegt. Bevor B angeblickt wird (nach Schritt 5), weiß
kein Netz, welcher der beiden anderen Körper B ist, mehr als das Bild allein verrät (Lage B gleich dem Boden, Lage
C sogar darunter); die Form von B ist dagegen in den gelösten Netzen lesbar (0,55–0,64). Gemerkt wird also die
Form. (b) Was alle Netze haben, auch die eingebrochenen, ist eine Karte der Szene mit Verlauf: nach Schritt 8 die
Lage des besuchten A (0,84–0,91), des angeblickten B und des übrigen Körpers (0,67–0,78), gleich gut für ein Ziel
C wie für einen Körper ohne Ziel. Der Boden „view“ hat diese Karte nicht; sie entsteht über die Schritte. (c)
Damit wird das Fehlerbild der eingebrochenen Läufe klar: Sie wissen, wo A liegt und welcher Körper noch nicht
besucht ist, kehren in A, B, C aber trotzdem zu 0,52–0,56 zu A zurück. Ohne die Form kann das Netz A, B, C
nicht von A, B, A unterscheiden und rät; die Karte allein reicht nicht, weil im Training auch Rückkehr vorkommt.
Genau dafür wurden die Folgen A, B, A gebaut. (d) Die Lücke aus dem Eintrag davor (C nur zu 0,44–0,51 lesbar,
aber zu 0,77–0,86 gefunden) erklärt sich wahrscheinlich so: Mit der Karte muss das Netz nach Schritt 8 nur noch
zwischen zwei Körpern wählen (zurück zu A oder zum übrigen), nicht zwischen fünf Formen; ungeprüft. (e)
Notizblock: Der Notizblock von sp4 trägt die Formen. Direkt nach dem Losgehen liest man B aus seinen 128 Werten
besser als aus dem ganzen Gitter (0,66–0,75 gegen 0,55–0,59) und weit besser als aus 128 Gitter-Werten
(0,42–0,47); A bleibt dort bis zum Ende. Die Lage dagegen liegt im Gitter (Lage C nach 8: Notizblock 0,40–0,54,
128 Gitter-Werte 0,68–0,72). Die Arbeit teilt sich also: Gitter = Karte der Szene, Notizblock = Auftrag (Formen).
Das passt zum Eintrag davor: Der Notizblock schützt die Formen genau in dem Moment, in dem die ersten Bilder sie
aus dem Gitter verdrängen. (f) Bezug zur Agenda „Spezialisierte Module im Verbund“: Hier hat sich ohne Vorgabe
eine Aufteilung in Karte und Auftrag ergeben; sie spricht für einen eigenen, vor der Wahrnehmung geschützten
Speicher für Aufträge. Geprüft ist das an einer Aufgabe und einer Bauart.

**Belege.** `results/loop_where_probe.jsonl` (12 Zeilen; `read[Quelle][shape|place|nogoal][Schritt][Ziel]`,
Quellen `all`, `view`, bei sp4 `p0` Gitter, `p1` Notizblock, `p0r128`), Skript `scripts/loop_where_probe.py`.

## 2026-11-18 — attnmem und vitmem: ganz oder gar nicht hängt am Vorlagen-Encoder, der zu langsam aus dem Anfang wächst

**Frage.** Warum lernen attnmem und vitmem die Drei-Ziele-Stufe je Seed ganz oder gar nicht, und was
unterscheidet ihre Läufe bei Zufall von den eingebrochenen layer_s-Läufen („nur A“)?

**Gemacht.** Reine Auswertung der 18 Netze mit 12000 Updates (Seeds 0–2), lokal: `loop_goals_probe.py` (3000
Lehrer-Folgen) und `loop_where_probe.py` (3000 Orakel-Läufe), dazu die Encoder-Streuung über das Training aus
`results/loop_refcurve.jsonl` (`ref_curve`, alle 250 Updates aufgezeichnet). Panne: Der lokale Lauf wurde wegen
Speichermangel vom System abgebrochen. Die Form-Auslese ist vollständig (18 Netze), die Lage-Auslese nur für 11
(es fehlen layer_s_am4 Seed 2, layer_s und layer_s_sp4 alle Seeds); nicht neu gestartet. Vorhersage vor dem Lauf
(wörtlich aus „Laufend / offen“):

> - Warum attnmem und vitmem je Seed ganz oder gar nicht lernen (Auftrag Nutzer 2026-11-18): reine Auswertung der
>   18 Netze aus „Drei Ziele nacheinander“ (12000 Updates, Seeds 0–2) mit `scripts/loop_goals_probe.py` (Lehrer-Läufe,
>   Form je Ziel nach jedem Schritt, Encoder) und `scripts/loop_where_probe.py` (Orakel-Läufe, Form und Lage, Boden
>   „view“). Bei Zufall liegen dort drei Läufe in ALLEN Zielen, auch A (0,31–0,36): attnmem Seed 0, vitmem Seed 1,
>   layer_s_am4 Seed 2; das ist ein anderes Fehlerbild als bei layer_s („nur A“).
>   **Vorhersage vor dem Lauf (2026-11-18):** (1) Die drei Läufe bei Zufall schreiben die Form schon nicht: A ist
>   direkt nach seinem Hinweis-Schritt (nach Schritt 0) höchstens 0,35 lesbar. (2) Ursache ist der Eingang: Die
>   Encoder-Streuung dieser Läufe ist höchstens halb so groß wie die der anderen Läufe derselben Bauart. (3) Die
>   gelösten Läufe von attnmem und vitmem (attnmem 1, 2; vitmem 0, 2) halten die Formen über den Lauf: B nach
>   Schritt 5 ≥ 0,45, C nach Schritt 8 ≥ 0,40 (Lehrer-Läufe). (4) hier_s (alle drei Seeds) und layer_s_am4 Seed 0
>   zeigen das Muster der eingebrochenen layer_s-Läufe: A nach Schritt 2 ≥ 0,60, B nach Schritt 5 ≤ 0,38.
>   (5) Die Karte (Lage von A nach Schritt 8, Orakel-Läufe) ist bei attnmem und vitmem um mindestens 0,10 R²
>   schwächer als bei den Gitter-Netzen (Mittel je Bauart).

**Ergebnis.** Form-Auslese (Lehrer-Läufe, Boden A 0,19, B 0,26, C 0,33) und Encoder am Ende des Trainings.

| | Seed | `near_all` | Encoder-Streuung | Encoder-Auslese | A nach 0 | B nach 5 | C nach 8 |
|---|---|---|---|---|---|---|---|
| attnmem | 0 | 0,07 | 0,046 | 0,37–0,40 | 0,42 | 0,39 | 0,37 |
| attnmem | 1 | 0,32 | 0,094 | 0,50–0,54 | 0,71 | 0,66 | 0,62 |
| attnmem | 2 | 0,37 | 0,101 | 0,55–0,57 | 0,80 | 0,74 | 0,67 |
| vitmem | 0 | 0,45 | 0,236 | 0,51–0,55 | 0,89 | 0,86 | 0,82 |
| vitmem | 1 | 0,07 | 0,043 | 0,34–0,37 | 0,39 | 0,38 | 0,34 |
| vitmem | 2 | 0,32 | 0,145 | 0,49–0,56 | 0,79 | 0,74 | 0,71 |
| layer_s_am4 | 0 | 0,14 | 0,51 | 0,53–0,56 | 0,86 | 0,60 | 0,32 |
| layer_s_am4 | 1 | 0,35 | 0,75 | 0,56–0,58 | 0,90 | 0,73 | 0,48 |
| layer_s_am4 | 2 | 0,08 | 0,44 | 0,41–0,42 | 0,51 | 0,35 | 0,35 |
| hier_s | 0–2 | 0,13–0,15 | 0,39–0,41 | 0,51–0,58 | 0,79–0,86 | 0,25–0,28 | 0,22–0,23 |
| layer_s | 0–2 | 0,18–0,59 | 0,82–0,98 | 0,55–0,62 | 0,87–0,93 | 0,30–0,52 | 0,24–0,41 |

Encoder-Streuung über das Training: Alle Netze beginnen bei etwa 0,01. Bei den Gitter-Netzen wächst sie bis
Update 2000 auf 0,02–0,28 (layer_s 0,27–0,28) und bis 4000 auf 0,21–0,80 (außer layer_s_am4 Seed 2). Bei attnmem und vitmem liegt sie bei
Update 2000 noch bei 0,007–0,022 und bei 4000 bei 0,015–0,041; danach wächst sie in den gelösten Läufen auf
0,09–0,24, in den Läufen bei Zufall nur auf 0,043–0,046. Der Trainingswert steigt bis 4000 in allen sechs Läufen
gleich (0,54–0,56) und trennt sich erst danach. layer_s_am4 Seed 2 wächst ebenfalls spät (0,041 bei 4000, 0,44
am Ende). Lage (Orakel-Läufe, R²): A nach Schritt 8 bei attnmem und vitmem 0,95–0,98 (Boden „view“ 0,69–0,71),
bei hier_s und am4 0,91–0,97 (Boden 0,34–0,40).

**Vergleich mit der Vorhersage.** (1) Nicht getroffen: In den drei Läufen bei Zufall ist A nach seinem
Hinweis-Schritt 0,39–0,51 lesbar, nicht höchstens 0,35 (aber weit unter den gelösten Läufen von attnmem und vitmem, 0,71–0,89). (2) Teilweise:
attnmem Seed 0 (0,046 gegen 0,094–0,101) und vitmem Seed 1 (0,043 gegen 0,145–0,236) erfüllen „höchstens halb so
groß“; layer_s_am4 Seed 2 nicht (0,44 gegen 0,51–0,75). (3) Getroffen: B nach 5 0,66–0,86, C nach 8 0,62–0,82.
(4) Teilweise: hier_s getroffen (A nach 2 0,81–0,88, B nach 5 0,25–0,28); layer_s_am4 Seed 0 nicht (B nach 5
0,60; es verliert erst C, nach 8 0,32). (5) Nicht getroffen: Die Karte ist bei attnmem und vitmem nicht schwächer,
sondern stärker (0,95–0,98 gegen 0,91–0,97); gemessen nur gegen hier_s und am4, da die übrigen Zeilen fehlen.
Zusammen: 1 getroffen, 2 teilweise, 2 nicht.

**Schluss.** (a) Die Läufe von attnmem und vitmem bei Zufall scheitern am Eingang: Ihr Vorlagen-Encoder bleibt
fast ohne Streuung (0,043–0,046), die Form kommt kaum ins Gedächtnis (A gleich nach dem Hinweis 0,39–0,42), also
findet das Netz nicht einmal A. Das ist ein anderes Fehlerbild als bei layer_s (dort schreibt der Encoder gut,
die Bilder verdrängen danach B und C). (b) Ursache vermutlich eine Henne-Ei-Falle am Anfang: Alle Encoder
beginnen bei Streuung 0,01. Bei den Gitter-Netzen wächst sie in den ersten 2000 Updates, bei attnmem und vitmem
kaum; erst ab etwa 4000 trennt sie sich, und wer bis 12000 nicht genug Streuung aufgebaut hat, bleibt bei Zufall.
Plausibel: Der Encoder bekommt nur dann Gradient, wenn das Gedächtnis ihn liest, und das Gedächtnis liest ihn
erst, wenn er etwas unterscheidet. Ob die Streuung Ursache oder Folge ist, trennen die Kurven nicht sicher, weil
beide zugleich wachsen; geprüft wäre es mit einem Encoder, der mit größerer Streuung beginnt, oder mit längerem
Training. (c) Gelernt halten attnmem und vitmem die Formen über den ganzen Lauf besser als jedes Gitter-Netz (B nach
5 bis 0,86, C nach 8 bis 0,82, ohne Abfall). Ihr Speicher wird von den Bildern nicht verdrängt. Ihre Schwäche liegt
dann nicht im Behalten, sondern im Nutzen: Je Ziel finden sie es nur zu 0,56–0,70. (d) layer_s_am4 Seed 2 ist ein
dritter Fall: Encoder spät, aber am Ende brauchbar (0,44), A halb lesbar (0,51), trotzdem bei Zufall; die Form wird
nicht genutzt. (e) Die Karte der Szene haben alle Bauarten; bei attnmem und vitmem steckt sie schon im Zustand nach
einem einzigen Bild (Boden 0,69–0,71), bei den Gitter-Netzen entsteht sie über die Schritte. (f) Für die Agenda
„Schnittstelle festlegen“: Neben „kein begrenzender Ausgang am Port“ (tanh-Befund) gehört dazu „genug
Anfangs-Streuung am Port“, sonst hängt das Lernen am Zufall des Trainingswegs.

**Belege.** `results/loop_goals_probe.jsonl` (18 Zeilen `"ckpt": "robot_loop_three_f32"`),
`results/loop_where_probe.jsonl` (11 Zeilen dazu), `results/loop_refcurve.jsonl` (`ref_curve` der Läufe
`robot_loop_three_f32:12000`).

## 2026-11-18 — Falscher Körper: Netze mit Gedächtnis verlassen ihn seltener als Netze ohne (Teil-Messung)

**Frage.** Hält die alte Aussage „der falsche Körper wird kaum verlassen“ auch je Lauf, und ändert ein Gedächtnis
mit gemerkter Vorlage daran etwas?

**Gemacht.** `finds_loop_eval.py` mit der neuen Größe `recover` (Commit 7cd968b). Panne: Der lokale Lauf wurde
wegen Speichermangel vom System abgebrochen; fertig ist nur `robot_loop_f32` (8 Netze, Seeds 0–2, 1500
Startszenen). `robot_loop_cue_f32`, `robot_loop_blind_f32` und drei Ziele fehlen; die Punkte (3) und (4) der
Vorhersage sind daher nicht gemessen und bleiben unter „Laufend / offen“. Vorhersage vor dem Lauf (wörtlich aus
„Laufend / offen“):

> - Wird ein falscher Körper verlassen? (Punkt aus der Agenda, Auftrag Nutzer 2026-11-18): Die alte Aussage „der
>   falsche Körper wird kaum verlassen“ (Eintrag `robot_loop_f32`, 2026-11-15) stützte sich nur auf den Gesamtanteil
>   „falscher Körper“ je Schritt (0,09 → 0,07), nicht auf einzelne Läufe; Wege hinaus und hinein heben sich dort
>   auf. Neu in `finds_loop_eval.py` (`recover`): je Ziel-Strecke die Läufe, die nach dem ersten Schritt der Strecke
>   auf einem falschen Körper stehen (und nicht nahe dem Ziel), und davon der Anteil nahe dem Ziel bzw. noch auf
>   einem falschen Körper am Ende der Strecke; dazu: nahe nach dem ersten Schritt, davon am Ende auf einem falschen
>   Körper. Läufe: `robot_loop_f32` (8 Netze, Seeds 0–2, 4 Schritte), `robot_loop_cue_f32` und
>   `robot_loop_blind_f32` mit `+refl` (Seeds 0–2), `robot_loop_three_f32` mit 24000 Updates (layer_s und sp4, 6
>   Seeds). Vor dem Lauf gesehen nur Probeläufe zum Testen des Codes: cnn Seed 0 auf `robot_loop_f32`, 30 Szenen
>   (falsch nach Schritt 1 0,13, davon am Ende nahe 0,33, noch falsch 0,58), layer_s 24000 Seed 0 auf drei Zielen,
>   5 Szenen.
>   **Vorhersage vor dem Lauf (2026-11-18):** (1) `robot_loop_f32`: Von den Läufen, die nach Schritt 1 auf einem
>   falschen Körper stehen, sind nach Schritt 4 bei allen Netzen höchstens 0,40 nahe dem Ziel und mindestens 0,50
>   noch auf einem falschen Körper. Die alte Aussage hält also auch je Lauf. (2) Abdriften kommt kaum vor: Wer nach
>   dem ersten Schritt nahe ist, steht am Ende in höchstens 0,03 auf einem falschen Körper (alle Aufgaben und Netze).
>   (3) Mit gemerkter Vorlage (`robot_loop_cue_f32`, `robot_loop_blind_f32`) verlassen die Gitter-Netze den falschen
>   Körper nicht öfter: nahe am Ende höchstens 0,10 über cnn auf `robot_loop_f32`. (4) Drei Ziele, sp4: Bei den
>   Strecken zu B und zum dritten Ziel ist von den Läufen auf einem falschen Körper nach dem ersten Schritt am Ende
>   höchstens 0,30 nahe dem Ziel. Grund für (1), (3), (4): Wer auf einem falschen Körper steht, hält ihn für das
>   Ziel; der Fehler liegt in der Erkennung, die bei jedem Schritt gleich ausfällt, nicht in der Schleife.

**Ergebnis.** `robot_loop_f32`, Mittel über die Seeds (Spanne höchstens 0,05).

| | falsch nach Schritt 1 | davon nahe nach 4 | davon noch falsch nach 4 | nahe nach 1 | davon falsch nach 4 |
|---|---|---|---|---|---|
| vit (ohne Gedächtnis) | 0,13 | 0,32 | 0,64 | 0,82 | 0,002 |
| cnn (ohne Gedächtnis) | 0,09 | 0,26 | 0,71 | 0,87 | 0,001 |
| vitmem | 0,20 | 0,16 | 0,82 | 0,73 | 0,001 |
| hier_s | 0,12 | 0,12 | 0,87 | 0,84 | 0,001 |
| layer_s_sp4 | 0,07 | 0,11 | 0,88 | 0,90 | 0,000 |
| attnmem | 0,25 | 0,10 | 0,88 | 0,65 | 0,003 |
| layer_s_am4 | 0,10 | 0,09 | 0,89 | 0,86 | 0,000 |
| layer_s | 0,07 | 0,09 | 0,89 | 0,90 | 0,000 |

**Vergleich mit der Vorhersage.** (1) Getroffen: nahe am Ende 0,09–0,32 (höchstens 0,40), noch falsch 0,64–0,89
(mindestens 0,50). (2) Getroffen für `robot_loop_f32` (0,000–0,003); für die anderen Aufgaben nicht gemessen.
(3) und (4) nicht gemessen.

**Schluss.** (a) Die alte Aussage hält je Lauf: Wer nach dem ersten Schritt auf einem falschen Körper steht, steht
dort nach drei weiteren Schritten in 0,64–0,89 der Fälle noch. Abdriften vom richtigen Körper gibt es praktisch
nicht. (b) Neu: Die Netze ohne Gedächtnis kommen öfter weg (cnn 0,26, vit 0,32) als alle Netze mit Gedächtnis
(0,09–0,16). Das Gedächtnis hält die einmal getroffene Entscheidung fest. Das passt zum Eintrag zu
`robot_loop_f32` (der Zustand dient als Schrittzähler und Zustand „angekommen“). (c) Mit dem Befund zu drei Zielen
zusammen: Die Netze bauen eine Karte mit Verlauf; ein Körper, auf dem der Blick einmal ruht, gilt danach als
„erreicht“. Ob eine gemerkte Vorlage das ändert, sagen erst die fehlenden Läufe.

**Belege.** `results/finds_loop.jsonl` (Zeilen `robot_loop_f32` mit `recover`).

## 2026-11-19 — Erster Live-Test im Roboter-Simulator: Prüfstand sagt die Rangfolge vorher, der Arm im Bild kostet die Gitter-Netze ein Viertel

**Frage.** Sagt der Prüfstand (`robot_loop_three_f32`) vorher, wie die Netze die Blickschleife mit drei Zielen live
im MuJoCo-Simulator des Roboter-Projekts lösen, auch wenn der Arm sich bewegt und ins Bild kommt?

**Gemacht.** `rdf_thalamus_sml/src/pc_cvnn/netresearch_live_loop.py` (Robot-Commit 2c3f7e1) gegen
`scripts/policy_server.py` (Commit 0e93819), 150 Szenen, alle 12 Folgen, 12 Netze, je `static` und `live`.
Laufzeit etwa 75 Minuten lokal. Vorhersage vor dem Lauf (wörtlich aus „Laufend / offen“):

> - Erster Test im Roboter-Projekt: Blickschleife mit drei Zielen live im MuJoCo-Simulator, mit bewegtem Arm
>   (Wunsch Nutzer 2026-11-18). Skript `rdf_thalamus_sml/src/pc_cvnn/netresearch_live_loop.py` (Simulator-Seite)
>   und `scripts/policy_server.py` (Netz-Seite; zwei Prozesse, weil die Umgebungen getrennt sind). 150 frische
>   Szenen (Saat 77000, Aufbau wie `gazeshapec`), alle 12 Folgen, Kamerabild bei jedem Schritt neu gerendert, Fovea
>   mit der NetResearch-Geometrie neu abgetastet. Bedingung `static`: Arm bleibt in der Ruhelage (entspricht dem
>   Prüfstand, aber live). Bedingung `live`: Nach jedem Ziel führt der Arm den Greifpunkt kinematisch 5 cm über den
>   Körper, auf dem der Blick liegt; die Hand ist beim Suchen des nächsten Ziels im Bild (im Prüfstand nie). Netze:
>   layer_s_sp4 und layer_s mit 24000 Updates (Seeds 0–2), vitmem und attnmem mit 12000 (Seeds 0–2). Vor dem Lauf
>   gesehen: Orakel 1,00 in beiden Bedingungen (5 Szenen), hier_s 12000 Seed 0 auf 3 Szenen zum Testen; geprüft,
>   dass im Live-Fall ab dem zweiten Ziel alle Bilder anders sind (Bild des Arms über dem Körper im Notizordner).
>   Kein act23-Lauf, kein Lernzustand berührt.
>   **Vorhersage vor dem Lauf (2026-11-18):** (1) `static` gibt den Prüfstand wieder: `near_all` je Netz innerhalb
>   ±0,06 um den Prüfstandswert (sp4 0,71 / 0,75 / 0,73, layer_s 0,72 / 0,21 / 0,64, vitmem 0,45 / 0,07 / 0,32,
>   attnmem 0,07 / 0,32 / 0,37). (2) `live`: Das erste Ziel bleibt gleich (±0,02), danach fällt es: `near_all` sinkt
>   bei den gelösten Gitter-Läufen um 0,05–0,20. (3) Die Rangfolge der Bauarten (Mittel über die Seeds) bleibt live
>   wie im Prüfstand: sp4 > layer_s > vitmem, attnmem. (4) Über die 12 Netze sagt der Prüfstandswert den Live-Wert
>   vorher: Spearman ρ ≥ 0,8.

**Ergebnis.** Orakel 1,00 in beiden Bedingungen. `near_all` (Prüfstand = `finds_loop_eval`, 1500 Startszenen):

| Netz | Seed | Prüfstand | static | live | Verlust live | Verlust relativ |
|---|---|---|---|---|---|---|
| layer_s_sp4, 24000 | 0 | 0,714 | 0,716 | 0,552 | 0,163 | 23 % |
| | 1 | 0,753 | 0,768 | 0,554 | 0,214 | 28 % |
| | 2 | 0,732 | 0,761 | 0,561 | 0,200 | 26 % |
| layer_s, 24000 | 0 | 0,721 | 0,757 | 0,597 | 0,160 | 21 % |
| | 1 (eingebrochen) | 0,210 | 0,217 | 0,201 | 0,016 | – |
| | 2 | 0,637 | 0,632 | 0,494 | 0,138 | 22 % |
| vitmem, 12000 | 0 | 0,448 | 0,432 | 0,377 | 0,055 | 13 % |
| | 1 (Zufall) | 0,071 | 0,073 | 0,070 | 0,003 | – |
| | 2 | 0,315 | 0,309 | 0,261 | 0,048 | 16 % |
| attnmem, 12000 | 0 (Zufall) | 0,068 | 0,077 | 0,070 | 0,007 | – |
| | 1 | 0,319 | 0,342 | 0,279 | 0,063 | 18 % |
| | 2 | 0,370 | 0,393 | 0,322 | 0,071 | 18 % |

Erstes Ziel in `live` gleich `static` (bis auf die letzte Stelle). Verlust je Ziel bei sp4: zweites Ziel
0,10–0,12, drittes 0,12–0,16. Neue und zurückkehrende Folgen verlieren gleich viel (sp4 live new 0,556–0,563, ret
0,548–0,558). Mittel je Bauart live: sp4 0,556, layer_s 0,431, vitmem 0,236, attnmem 0,224 (`static`: 0,748,
0,535, 0,271, 0,271). Spearman über die 12 Netze: Prüfstand–live 0,97, Prüfstand–`static` 0,99.

**Vergleich mit der Vorhersage.** (1) Getroffen: Abweichung `static` − Prüfstand −0,016 bis +0,036 (Grenze ±0,06).
Die Abweichungen sind meist positiv (9 von 12); ein kleiner Unterschied der Szenen (eigene Saat, eigener
Szenenbau) ist möglich, geprüft wurde er nicht. (2) Teilweise getroffen: Das erste Ziel bleibt gleich, das ist
aber durch den Aufbau festgelegt (der Arm bewegt sich erst nach dem ersten Ziel) und prüft nichts. Verlust der
gelösten Gitter-Läufe: 4 von 5 im Bereich 0,05–0,20 (0,138–0,200), sp4 Seed 1 mit 0,214 darüber. Verfehlt für
diesen Lauf. (3) Getroffen: sp4 > layer_s > vitmem ≈ attnmem, auch live. (4) Getroffen: ρ = 0,97 (mindestens
0,8). Bilanz: 2 getroffen, 1 getroffen ohne Aussagekraft, 1 teilweise verfehlt.

**Schluss.** (a) Die Brücke trägt: Fovea, Szenenbau und Schrittdeutung des Prüfstands stimmen mit dem Simulator
überein (`static` = Prüfstand innerhalb 0,04), und der Prüfstandswert ordnet die Netze auch live richtig (ρ =
0,97). (b) Was der Prüfstand nicht vorhersagt, ist die Größe des Verlusts durch den Arm im Bild. Die
Gitter-Netze verlieren absolut 0,14–0,21 und relativ 21–28 %, vitmem und attnmem nur 13–18 %. sp4 verliert am
meisten: Sein Vorsprung vor layer_s Seed 0 ist live weg (0,552–0,561 gegen 0,597), und die drei sp4-Seeds landen
live fast gleich. Ob der Verlust aus Verdecken kommt (die Hand liegt über einem Körper) oder aus Ablenkung durch
ein unbekanntes Bild, ist nicht gemessen. (c) Für die Pipeline heißt das: Rangfolge ja, Größe nein. Bilder mit Arm
gehören in den Prüfstand, sonst bleibt die Störung unbewertet. Das ist kein Netz-Fix: Der Arm ist im Roboter
immer im Bild. (d) Grenzen: kinematischer Arm ohne Physik (Körper bleiben liegen), feste Schwebehöhe 5 cm,
Stufe b (kein act23-Lauf, kein Lernzustand berührt), nur 150 Szenen (Standardfehler von `near_all` etwa 0,01).

**Belege.** `results/robot_live_loop.jsonl` (26 Zeilen: Orakel und 12 Netze × 2 Bedingungen), Prüfstand in
`results/finds_loop.jsonl`. Robot-Wiki: Nachtrag in `wiki/fragen/netresearch-bruecke.md`.

## 2026-11-19 — Arm im Bild: Ablenkung, nicht Verdecken; die Hand irgendwo im Bild kostet so viel wie über dem Körper

**Frage.** Kommt der Verlust im Live-Test daher, dass die Hand einen Körper verdeckt, oder daher, dass ein nie
gesehenes Bild (Arm und Hand) im Blickfeld liegt?

**Gemacht.** `netresearch_live_loop.py` mit der Bedingung `away` (Robot-Commit 7d8f0ad), fünf gelöste
Gitter-Läufe, dieselben 150 Szenen, Bedingungen `static`, `live`, `away`. Laufzeit etwa 75 Minuten lokal.
Vorhersage vor dem Lauf (wörtlich aus „Laufend / offen“):

> - Arm im Bild: Verdecken oder Ablenkung? (Folgefrage zum Live-Test 2026-11-19, eigene Entscheidung während der
>   Pause des Nutzers.) Neue Bedingung `away` in `netresearch_live_loop.py`: Nach dem ersten Ziel fährt der Arm 5 cm
>   über eine freie Tischstelle derselben Szene und bleibt dort. Gewählt wird sie im Bild: Die Hand liegt im inneren
>   Ring und mindestens 15 px (Median 23 px, eine Zelle = 4 px) von jedem Körper entfernt; in `live` liegt sie über
>   dem angeblickten Körper. Unterschied zu `live`: Dort fährt der Arm nach dem zweiten Ziel noch einmal um, in `away`
>   nicht. Neu je Lauf: `miss_stay_prev`, für verfehlte Strecken zu Ziel 2 und 3 der Anteil, der auf dem Körper endet,
>   auf dem der Blick am Ende der Strecke davor lag (in `live` liegt dort die Hand). Netze: die fünf gelösten
>   Gitter-Läufe (sp4 Seeds 0–2, layer_s Seeds 0 und 2, 24000 Updates), Bedingungen `static`, `live`, `away`, dieselben
>   150 Szenen (geprüft: gleiche Zahl von Versuchen beim Szenenbau, die Wahl der freien Stelle braucht keine
>   Zufallszahlen). Vor dem Lauf gesehen: Orakel 1,00 in allen drei Bedingungen (5 Szenen), Bild der Hand über der
>   freien Stelle (Notizordner).
>   **Vorhersage vor dem Lauf (2026-11-19):** (1) `static` und `live` geben den ersten Lauf exakt wieder (gleiche
>   `near_all` auf vier Stellen). (2) Ablenkung überwiegt: In `away` verliert jedes der fünf Netze mindestens die
>   Hälfte seines `live`-Verlusts gegenüber `static`. Sicherheit gering: Das Bild der Hand ist neu, aber verdeckt
>   keinen Körper. (3) In `live` enden verfehlte Strecken zu Ziel 2 seltener auf dem Körper davor als in `static`
>   (die Hand verdeckt ihn), bei allen fünf Netzen.

**Ergebnis.** `near_all`, Verlust gegenüber `static`, und `miss_stay_prev` für Ziel 2 / Ziel 3:

| Netz | static | live (Verlust) | away (Verlust) | away / live | auf dem Körper davor: static | live | away |
|---|---|---|---|---|---|---|---|
| sp4 Seed 0 | 0,716 | 0,552 (0,163) | 0,543 (0,172) | 1,05 | 0,03 / 0,05 | 0,13 / 0,16 | 0,09 / 0,08 |
| sp4 Seed 1 | 0,768 | 0,554 (0,214) | 0,548 (0,221) | 1,03 | 0,03 / 0,04 | 0,12 / 0,15 | 0,15 / 0,14 |
| sp4 Seed 2 | 0,761 | 0,561 (0,200) | 0,568 (0,193) | 0,96 | 0,04 / 0,06 | 0,16 / 0,16 | 0,11 / 0,14 |
| layer_s Seed 0 | 0,757 | 0,597 (0,160) | 0,570 (0,187) | 1,17 | 0,05 / 0,02 | 0,10 / 0,09 | 0,10 / 0,14 |
| layer_s Seed 2 | 0,632 | 0,494 (0,138) | 0,492 (0,140) | 1,02 | 0,01 / 0,02 | 0,08 / 0,10 | 0,07 / 0,06 |

`static` und `live` sind auf vier Stellen gleich dem ersten Lauf. Verfehlte Strecken zu Ziel 2 verdoppeln sich
etwa (z. B. sp4 Seed 0: 271 → 448 / 477 von 1800); der größte Teil endet weder nahe dem Ziel noch auf dem Körper
davor (84–93 %).

**Vergleich mit der Vorhersage.** (1) Getroffen: exakt gleich. (2) Getroffen: `away` verliert bei allen fünf
Netzen das 0,96- bis 1,17-fache des `live`-Verlusts (vorhergesagt: mindestens die Hälfte); deutlicher als
erwartet, Verdecken trägt nichts Messbares bei. (3) Verfehlt, in die Gegenrichtung: In `live` enden verfehlte
Strecken zu Ziel 2 bei allen fünf Netzen öfter auf dem Körper davor (0,08–0,16) als in `static` (0,01–0,05). Die
Begründung „die Hand verdeckt ihn“ war falsch: In `away` (Hand nicht dort) ist der Anteil ebenso hoch
(0,07–0,15). Bilanz: 2 getroffen, 1 verfehlt.

**Schluss.** (a) Der Verlust durch den Arm ist Ablenkung durch ein unbekanntes Bild im Blickfeld, nicht Verdecken:
Wo die Hand liegt, ist gleich, solange sie im Bild ist. (b) Ein Teil der Ablenkung zeigt sich als Hängenbleiben:
Mit Arm im Bild bleibt der Blick öfter auf dem gerade gefundenen Körper oder kehrt dorthin zurück. Das passt zur
Karte mit Verlauf (Eintrag „Form oder Lage“): Ein geändertes Bild stört offenbar auch die Spur „hier war ich
schon“. Der größere Teil der Fehler landet aber woanders; wohin genau, ist nicht gemessen. (c) Für den Prüfstand
heißt das: Bilder mit Arm im Blickfeld (beliebige Lage) gehören ins Training oder zumindest in die Prüfung. Eine
gezielte Lage über dem Körper ist dafür nicht nötig. Das ist ein Mangel der Trainingsdaten, nicht der
Netze, und kein Fix um ein Unvermögen herum: Im Roboter ist der Arm immer im Bild. (d) Grenzen: nur die fünf
gelösten Gitter-Läufe, kinematischer Arm, eine freie Stelle je Szene.

**Belege.** `results/robot_live_loop_away.jsonl` (18 Zeilen), Vergleich mit `results/robot_live_loop.jsonl`.

## 2026-11-19 — Nachmessung: Auch mit gemerkter Vorlage und bei drei Zielen wird ein falscher Körper kaum verlassen

**Frage.** Rest der Messung „Wird ein falscher Körper verlassen?“ (Eintrag 2026-11-18, Teil-Messung): Gilt das
Ergebnis auch auf `robot_loop_cue_f32`, `robot_loop_blind_f32` und bei drei Zielen? Dazu die 7 Zeilen der
Lage-Auslese (`loop_where_probe.py`, 12000-Netze), die am 2026-11-18 ebenfalls wegen Speichermangel fehlten.

**Gemacht.** Auf Wunsch des Nutzers neu gestartet, lokal und streng nacheinander (jeder Schritt wartet, bis keine
andere Auswertung läuft). `finds_loop_eval.py` mit `recover`: `robot_loop_cue_f32` und `robot_loop_blind_f32` (6
Netze `+refl`, Seeds 0–2, 1500 Startszenen), drei Ziele mit 24000 Updates (layer_s und sp4, 6 Seeds).
`loop_where_probe.py`: layer_s_am4 Seed 2, layer_s und sp4 Seeds 0–2 (12000 Updates). Alle Läufe vollständig.
Offener Punkt (wörtlich aus „Laufend / offen“):

> - Rest der Messung „Wird ein falscher Körper verlassen?“ (abgebrochen 2026-11-18 wegen Speichermangel): die
>   Läufe `robot_loop_cue_f32`, `robot_loop_blind_f32` (6 Netze `+refl`, Seeds 0–2) und drei Ziele (24000
>   Updates) mit `recover`; es gelten die Punkte (3) und (4) der Vorhersage im Eintrag „Falscher Körper“ vom
>   2026-11-18, unverändert.

Die Punkte der Vorhersage vom 2026-11-18: (2) Abdriften kommt kaum vor: Wer nach dem ersten Schritt nahe ist,
steht am Ende in höchstens 0,03 auf einem falschen Körper (alle Aufgaben und Netze). (3) Mit gemerkter Vorlage
verlassen die Gitter-Netze den falschen Körper nicht öfter: nahe am Ende höchstens 0,10 über cnn auf
`robot_loop_f32` (cnn 0,26, Grenze also 0,36). (4) Drei Ziele, sp4: Bei den Strecken zu B und zum dritten Ziel
ist von den Läufen auf einem falschen Körper nach dem ersten Schritt am Ende höchstens 0,30 nahe dem Ziel.

**Ergebnis.** Spannen über die Seeds. „falsch“ = nach dem ersten Schritt der Strecke auf einem falschen Körper,
„davon nahe“ / „davon noch falsch“ = am Ende der Strecke.

| Aufgabe | Netz | falsch | davon nahe | davon noch falsch | Abdriften |
|---|---|---|---|---|---|
| cue | layer_s, sp4, am4, hier_s | 0,08–0,22 | 0,03–0,08 | 0,91–0,96 | ≤ 0,002 |
| cue | attnmem, vitmem | 0,32–0,58 | 0,03–0,12 | 0,86–0,96 | ≤ 0,004 |
| blind | layer_s, sp4, am4, hier_s | 0,08–0,17 | 0,07–0,12 | 0,87–0,93 | ≤ 0,003 |
| blind | attnmem, vitmem | 0,26–0,43 | 0,08–0,13 | 0,84–0,89 | ≤ 0,003 |
| drei Ziele, Strecke B / C | sp4 (6 Seeds) | 0,15–0,19 | 0,13–0,18 | 0,80–0,85 | ≤ 0,003 |
| drei Ziele, Strecke B / C | layer_s gelöst (0, 2, 7) | 0,16–0,25 | 0,10–0,16 | 0,82–0,89 | ≤ 0,004 |
| drei Ziele, Strecke B / C | layer_s eingebrochen (1, 3, 4) | 0,47–0,62 | 0,02–0,03 | 0,96–0,98 | ≤ 0,009 |

Strecke A bei drei Zielen: falsch 0,10–0,14, davon nahe 0,05–0,16. Lage-Auslese, neue Zeilen: Lage A nach
Schritt 8 layer_s 0,90 und sp4 0,92–0,93 (Boden „view“ 0,40–0,47), layer_s_am4 Seed 2 0,95 (0,40).

**Vergleich mit der Vorhersage.** (2) Getroffen, jetzt für alle Aufgaben: höchstens 0,009 (eingebrochene
layer_s-Läufe, dritte Strecke). (3) Getroffen: Gitter-Netze nahe am Ende 0,03–0,12 (Grenze 0,36). Sie kommen sogar
seltener weg als cnn (0,26) und etwa so selten wie auf `robot_loop_f32` (0,09–0,12). (4) Getroffen: sp4
0,13–0,18 (Grenze 0,30). Zusammen mit dem Teil vom 2026-11-18 ((1) getroffen): 4 von 4 getroffen.

**Schluss.** (a) Das Bild ist auf allen Stufen der Schleife dasselbe: Wer nach dem ersten Schritt auf einem
falschen Körper steht, steht dort am Ende in 0,80–0,98 der Fälle noch, und vom richtigen Körper driftet praktisch
niemand weg. Die Schleife korrigiert keine Verwechslung, auch nicht mit gemerkter Vorlage. (b) Eine gemerkte
Vorlage macht das Weglaufen eher seltener (cue: Gitter 0,03–0,08 gegen cnn ohne Gedächtnis 0,26 auf
`robot_loop_f32`). Das stützt die Deutung vom 2026-11-18: Das Gedächtnis hält die einmal getroffene Entscheidung
fest. (c) Die eingebrochenen layer_s-Läufe stehen auf Strecke B und C zu 0,47–0,62 auf einem falschen Körper und
kommen fast nie weg (0,02–0,03). Das passt dazu, dass sie B und C beim Losgehen verlieren (Eintrag „eingebrochene
layer_s-Läufe“). (d) Lage-Auslese: Die neuen Zeilen ändern die Schlüsse des Eintrags „attnmem und vitmem“ nicht.
Auch layer_s und sp4 mit 12000 Updates bauen die Karte erst über die Schritte (0,90–0,93 gegen Boden 0,40–0,47).
(e) Für die Agenda: Ein Netz, das einen Fehlgriff selbst bemerkt und den Körper verlässt, müsste das eigens
lernen. Im Training kommt „auf falschem Körper, geh weg“ nur als einzelner Lehrerschritt vor, nicht als Folge.

**Belege.** `results/finds_loop.jsonl` (Zeilen mit `recover` für `robot_loop_cue_f32`, `robot_loop_blind_f32`,
`robot_loop_three_f32` mit `ckpt` `robot_loop_three_f32_24k`), `results/loop_where_probe.jsonl` (jetzt 18 Zeilen
für `robot_loop_three_f32`).

## 2026-11-19 — Breiter Port-Anfang (`+pw`): kein einziger Lauf löst, die Henne-Ei-Deutung ist in dieser Form nicht bestätigt

**Frage.** Lernen attnmem und vitmem verlässlich, wenn die Adresse mit größerer Anfangs-Streuung startet (Prüfung
der Deutung aus dem Eintrag „attnmem und vitmem: ganz oder gar nicht“)?

**Gemacht.** Worker-Jobs `20261118-231457-pw_attnvit` (12 Läufe `+pw`) und `20261118-231457-base_attnvit` (6
Läufe ohne, Seeds 3, 4, 7), Commit 0428d41, drei Ziele, 12000 Updates. Danach lokal `finds_loop_eval.py` (1500
Startszenen). Die alte automatische Auswertung wurde durch eine gleichwertige mit Wartesperre ersetzt (siehe
Eintrag „Nachmessung“), am Ergebnis ändert das nichts. Vorhersage vor dem Lauf (wörtlich aus „Laufend / offen“):

> - Breiter Port-Anfang für attnmem und vitmem (Prüfung der Henne-Ei-Deutung, 2026-11-18, eigene Entscheidung während
>   der Pause des Nutzers): Bei attnmem und vitmem geht die Adresse durch zwei klein beginnende lineare Abbildungen
>   (Ende des Vorlagen-Encoders, dann `cmd_in` als Muster auf dem Bild); die Gitter-Netze haben `+cell` (eine
>   Abbildung in jede Zelle). Neuer Namens-Zusatz `+pw`: beide Abbildungen starten 4-mal größer (gleiche Parameter;
>   Faktor vorher festgelegt, nicht abgestimmt). Am Anfang: Encoder-Streuung 0,010 → 0,038 (vitmem 0,030), Muster
>   auf dem Bild 0,005 → 0,087. Worker: `attnmem+refl+pw+rez3` und `vitmem+refl+pw+rez3` Seeds 0–4, 7, dazu
>   `attnmem+refl+rez3` und `vitmem+refl+rez3` Seeds 3, 4, 7 (mit den vorhandenen 0–2 sechs je Netz), drei Ziele,
>   12000 Updates. „Gelöst“ = `near_all` ≥ 0,20 (bisher Zufallsläufe 0,07, gelöste 0,32–0,45). Das ist eine Prüfung
>   der Ursache, kein Vorschlag für den Standard; ob `+pw` übernommen wird, entscheidet der Nutzer.
>   **Vorhersage vor dem Lauf (2026-11-18):** (1) Ohne `+pw` lösen attnmem und vitmem je 3 bis 5 von 6. (2) Mit
>   `+pw` lösen sie zusammen mindestens 11 von 12. (3) Mit `+pw` liegt die Encoder-Streuung bei Update 2000 in allen
>   12 Läufen bei mindestens 0,05 (ohne: 0,007–0,022). (4) Die gelösten Läufe mit `+pw` liegen im Mittel innerhalb
>   ±0,08 um die gelösten ohne: Der Anfang entscheidet, ob gelernt wird, kaum wie gut.

**Ergebnis.** `near_all` je Seed (0 / 1 / 2 / 3 / 4 / 7), „gelöst“ = mindestens 0,20:

| Netz | near_all | gelöst |
|---|---|---|
| attnmem | 0,07 / 0,32 / 0,37 / 0,18 / 0,44 / 0,07 | 3 von 6 (Seed 3 knapp darunter) |
| vitmem | 0,45 / 0,07 / 0,32 / 0,20 / 0,07 / 0,07 | 2 von 6 (Seed 3 mit 0,198 knapp darunter) |
| attnmem `+pw` | 0,07 / 0,07 / 0,07 / 0,07 / 0,10 / 0,07 | 0 von 6 |
| vitmem `+pw` | 0,07 / 0,07 / 0,10 / 0,07 / 0,10 / 0,07 | 0 von 6 |

Encoder-Streuung (`loop_refcurve.jsonl`) bei Update 0 / 2000 / 4000 / Ende:
- ohne `+pw`, alle 12 Läufe: 0,006–0,012 / 0,007–0,022 / 0,014–0,052 / 0,043–0,239.
- mit `+pw`: 0,023–0,048 / 0,013–0,082 / 0,012–0,054 / 0,020–0,065.
Die Streuung beginnt also größer, sinkt dann aber in 10 von 12 Läufen bis Update 2000 und wächst danach kaum.
Ohne `+pw` ist sie am Ende in allen Läufen viel größer als am Anfang (mindestens 0,043). Die neuen Basis-Läufe passen nicht ganz zur alten Trennung nach der
End-Streuung: vitmem Seed 4 endet bei 0,094 und liegt trotzdem bei Zufall, attnmem Seed 3 und vitmem Seed 3
liegen mit 0,084 / 0,119 dazwischen (0,18 / 0,20).

**Vergleich mit der Vorhersage.** (1) Teilweise: attnmem 3 von 6 getroffen, vitmem 2 von 6 verfehlt (knapp: Seed
3 0,198). (2) Klar verfehlt: 0 von 12 statt mindestens 11. (3) Verfehlt: Streuung bei Update 2000 nur in 1 von 12
Läufen mindestens 0,05 (vitmem Seed 1, 0,082). (4) Nicht prüfbar, kein Lauf mit `+pw` gelöst. Bilanz: 1 teilweise,
2 verfehlt, 1 nicht prüfbar.

**Schluss.** (a) Der breite Port-Anfang hilft nicht, er schadet: Mit `+pw` kommt kein Lauf über Zufall. Die
Deutung „der Encoder wächst zu langsam aus der kleinen Anfangs-Streuung“ ist in dieser Form nicht bestätigt. Eine
größere Anfangs-Streuung allein bringt die Form nicht ins Gedächtnis; das Training drückt sie zuerst wieder
herunter. (b) Ungeprüfte Vermutung zur Ursache: `+pw` vergrößert zwei Dinge zugleich, das Ende des
Vorlagen-Encoders und `cmd_in`, das Muster auf dem Bild (0,005 → 0,087). Ein so großes, anfangs zufälliges Muster
auf jedem Bild stört die Wahrnehmung. Das Netz lernt vermutlich zuerst, es zu dämpfen, und dämpft dabei den
Weg der Adresse mit. Trennen ließe sich das mit einem Lauf, der nur den Encoder vergrößert. (c) Die alte
Beobachtung bleibt: Gelöste Läufe haben am Ende eine größere Encoder-Streuung. Ob sie Ursache oder Folge des
Lernens ist, ist nach diesem Lauf offener als vorher. Mit sechs Seeds ist sie auch kein sauberer Trenner mehr
(vitmem Seed 4). (d) Lösequote ohne `+pw` mit sechs Seeds: attnmem 3/6, vitmem 2/6; zusammen mit den
Gitter-Netzen (sp4 6/6 bei 24000 Updates) bleibt der Abstand der Bauarten auf dieser Stufe bestehen. (e) `+pw`
wird nicht Standard; der Namens-Zusatz bleibt im Code, damit die Läufe nachvollziehbar sind.

**Belege.** `results/finds_loop.jsonl` (Zeilen `attnmem` / `vitmem` auf `robot_loop_three_f32`),
`results/loop_refcurve.jsonl` (18 neue Zeilen), `results/checkpoints/robot_loop_three_f32/`.

## 2026-11-19 — Korrektur: Die Zustands-Auslese misst bei attnmem und vitmem nur das Eingangs-Archiv

**Frage.** Hinweis aus dem Review von Gemini (REVIEW-2026-11-19.md, Abschnitt 2.2): Ist die Auslese aus dem
Zustand (`loop_goals_probe.py`, `loop_where_probe.py`) bei attnmem und vitmem mit den Gitter-Netzen vergleichbar?

**Gemacht.** Code gelesen (`netresearch/models/basic.py`, `AttnMem.forward`, `ViTMem.forward`), nichts gerechnet.

**Ergebnis.** Der Zustand von attnmem und vitmem ist ein Ringpuffer der letzten 16 Bild-Einbettungen `e_t`, so wie
sie aus dem Bild-Encoder kommen. Die Verarbeitung über die Zeit (Attention des aktuellen Bildes über den Puffer)
rechnet nur die Ausgabe und schreibt nichts zurück. Bei 12 Schritten fällt kein Eintrag heraus; die drei
Hinweis-Bilder liegen bis zum Ende unverändert im Puffer. Bei den Gitter-Netzen ist der Zustand dagegen das
Ergebnis der Rechnung und wird bei jedem Schritt überschrieben.

**Schluss.** Folgende Aussagen sind durch den Bau bedingt und keine Befunde über das Lernen:
- Eintrag „attnmem und vitmem: ganz oder gar nicht“, Schluss (c): „Gelernt halten attnmem und vitmem die Formen
  über den ganzen Lauf besser als jedes Gitter-Netz (nicht verdrängt)“. Gemessen ist nur, wie gut der Bild-Encoder
  die Form in eine Einbettung legt. Dass sie nicht verdrängt wird, folgt aus dem Puffer.
- Derselbe Eintrag, Schluss (e): „Bei attnmem und vitmem steckt die Karte schon im Zustand nach einem einzigen
  Bild“. Der Boden „view“ ist dort die Einbettung eines Bildes; die Karte im ganzen Zustand ist das Archiv aller
  Einbettungen, nicht eine gerechnete Karte.
- Die Folgerung „ihre Schwäche liegt im Nutzen, nicht im Behalten“ bleibt als Vermutung stehen, ist durch diese
  Auslese aber nicht gestützt.

Was gilt weiter: Bei den Läufen bei Zufall ist A schon direkt nach dem Hinweis kaum lesbar (0,39–0,42). Das ist
genau die Einbettung des Hinweis-Bildes, also ein Befund über den Encoder, und stützt die Deutung „Eingang statt
Gedächtnis“. Alle Aussagen über die Gitter-Netze (Verdrängen beim Losgehen, Karte und Notizblock bei sp4) sind
nicht betroffen.

Zusätzlich bestätigt (Review 2.1 und 2.2): Die Ports sind nicht gleich.
- Bei attnmem und vitmem erreicht die Vorlage die Laufschritte nur als ein Eintrag von 48 Werten im Puffer. Das
  aktuelle Bild wird im Bild-Encoder verarbeitet, ohne die gesuchte Form zu kennen.
- In den Laufschritten geht `ref_enc(0)` als konstantes Muster aufs Bild (`attach_cmd`). Bei den Gittern geht es
  als konstanter Vektor in jede Zelle (`+cell`).
- Der Rückstand von attnmem und vitmem auf den Schleifen-Stufen ist deshalb zum Teil eine Frage der Schnittstelle,
  nicht nur der Bauart.

**Belege.** `netresearch/models/basic.py` (AttnMem, ViTMem), `netresearch/train.py` (`run_sequence`: `ref_enc`
wird auch auf das leere Bild angewendet), `netresearch/models/__init__.py` (`attach_cmd`).

## 2026-11-19 — Live-Test mit der Prüfstands-Regel „Bild verlassen“: bitgleich, die Regel erklärt nichts

**Frage.** Ändert die Prüfstands-Regel für Schritte aus dem Bild (Hinweis Review Gemini 2.4) das Live-Ergebnis,
und erklärt sie die leicht höheren `static`-Werte?

**Gemacht.** `netresearch_live_loop.py` mit `out_rule: bench` und einem Bild je Armstellung (Robot-Commit
a892395), dieselben 12 Netze und 150 Szenen, `static` und `live`. Vorhersage vor dem Lauf (wörtlich aus „Laufend /
offen“):

> - Live-Test mit der Prüfstands-Regel für „Bild verlassen“ (2026-11-19, Hinweis Review 2.4): Im Prüfstand
>   (`finds_loop_eval.py`) beendet ein Schritt aus dem Bild den Lauf, alle späteren Ziele zählen als verfehlt. Im
>   Live-Skript blieb der Blick bisher einfach stehen. Jetzt gleich wie im Prüfstand (Feld `out_rule: bench`, dazu
>   `out` = Zahl der Läufe, die das Bild verlassen). Außerdem wird je Schritt nur ein Bild je Armstellung gerendert
>   (Ergebnis unverändert, schneller). Neu gemessen: dieselben 12 Netze, dieselben 150 Szenen, `static` und `live`.
>   Vor dem Lauf gesehen: Orakel 1,00 in allen Bedingungen (5 Szenen).
>   **Vorhersage vor dem Lauf (2026-11-19):** (1) Die Regel ändert fast nichts: `near_all` je Netz und Bedingung
>   höchstens 0,01 unter dem ersten Lauf, weil der Blick in diesen Szenen kaum das Bild verlässt (höchstens 1 % der
>   Läufe). (2) Damit erklärt die Regel die leicht höheren `static`-Werte nicht: Weiterhin liegen mindestens 8 von 12
>   Netzen über dem Prüfstand. (3) Spearman Prüfstand–live bleibt mindestens 0,95. (4) Der Lauf `live` ist mindestens
>   dreimal so schnell wie vorher (vorher 262–356 s je Netz).

**Ergebnis.** Alle 24 Werte `near_all` sind auf vier Stellen gleich dem ersten Lauf. Von 43 200 Läufen
(12 Netze × 2 Bedingungen × 1800) verlässt genau einer das Bild (attnmem Seed 2, `live`), und der war am
betroffenen Ziel ohnehin verfehlt. `static` liegt weiter in 9 von 12 Netzen über dem Prüfstand. Laufzeit je Netz
`live` 47–86 s statt 262–356 s (3,1- bis 7,5-mal schneller), `static` unverändert 34–37 s.

**Vergleich mit der Vorhersage.** (1) Getroffen: Änderung 0,000 (Grenze 0,01), 1 Lauf aus dem Bild. (2) Getroffen:
9 von 12 über dem Prüfstand. (3) Getroffen: Spearman unverändert (die Live-Werte sind bitgleich). (4) Getroffen:
mindestens 3,1-mal schneller. Bilanz: 4 von 4.

**Schluss.** (a) Der Hinweis aus dem Review war ein echter Unterschied im Code, wirkt in diesen Szenen aber nicht:
Der Blick verlässt das Bild praktisch nie. Die Zahlen des ersten Live-Tests bleiben gültig. (b) Die leicht
höheren `static`-Werte (Mittel +0,010) bleiben unerklärt. Übrig sind die eigenen Szenen des Live-Skripts (eigene
Saat, eigener Szenenbau); geprüft ist das nicht. (c) Der schnellere Live-Test macht größere Prüfungen bezahlbar
(12 Netze, beide Bedingungen, etwa 25 statt 75 Minuten).

**Belege.** `results/robot_live_loop_v2.jsonl` (26 Zeilen, Felder `out` und `out_rule`).

## 2026-11-20 — `+rv`, Etappe 1 (drei Ziele): Endstand bei 24000 Updates gleich, bei 12000 eher etwas tiefer

**Frage.** Ändert der neue Standard `+rv` (ein Schritt ohne Vorlage sendet keinen Befehl) die Ergebnisse auf der
Stufe „drei Ziele nacheinander“?

**Gemacht.** Worker-Jobs `20261119-083513-rv_three_grid` (12 Läufe, 346 min mit 6 Prozessen),
`20261119-083513-rv_three_attnvit` (12 Läufe, 167 min) und `20261119-203605-rv_three24k` (12 Läufe, 530 min mit
12 Prozessen; der erste Versuch `154959` scheiterte nach 1 min an einem Fehler beim Einreichen, ohne
`--module curriculum`). Danach lokal `finds_loop_eval.py`, 1500 Startszenen, Vergleich mit denselben Seeds ohne
`+rv`. Die Auswertung von attnmem und vitmem wurde einmal wegen knappen Arbeitsspeichers abgebrochen und
vollständig neu gerechnet. Vorhersage vor dem Lauf (wörtlich aus „Laufend / offen“):

> - Neuer Standard `+rv` für Netze mit Vorlage, Etappe 1: drei Ziele (Nutzer 2026-11-19: „sauber vor Zeit“, Hinweis
>   Review Gemini 2.1). Mit `+rv` sendet ein Schritt ohne Vorlage keinen Befehl: kein Ausgang des
>   Vorlagen-Encoders, kein Muster aufs Bild (auch nicht dessen Bias). Die Schleifen-Aufgaben liefern dafür
>   ausdrücklich `ref_mask`. Ohne `+rv` sieht der Encoder in den Laufschritten das leere Bild, und
>   `ref_enc(0)` geht als konstanter Befehl in den Port. Geprüft (Commit mit dieser Vorhersage):
>   - alte Netze rechnen bitgleich;
>   - `+rv` hat bei gleichem Seed dieselben Anfangsgewichte;
>   - Laufschritte mit `+rv` = Netz ganz ohne Befehl (Unterschied 0);
>   - kein Gradient in den Adress-Weg aus Schritten ohne Vorlage;
>   - Rauchtest 300 Updates für attnmem und sp4.
>   Nebenbefund: Trainierte Netze ohne `+rv` nutzen `ref_enc(0)` stark (Ausgabe ändert sich um bis zu 7,6 bei
>   attnmem, 2,0 bei sp4, 0,7 bei layer_s), offenbar als Zeichen „jetzt Laufphase“. Mit `+rv` müssen sie das aus
>   dem Bild lesen (in den Hinweis-Schritten ist es leer).
>   Worker, 6 Prozesse: (A) layer_s, sp4, am4, hier_s mit `+cell+refl+rv+rez3`, Seeds 0–2, 12000 Updates; (B)
>   attnmem, vitmem mit `+refl+rv+rez3`, Seeds 0–4, 7, 12000 Updates; (C) layer_s, sp4 mit `+rv`, Seeds 0–4, 7, 24000
>   Updates. Vergleich jeweils mit denselben Seeds ohne `+rv`.
>   **Vorhersage vor dem Lauf (2026-11-19):** (1) Gitter-Netze, 12000 Updates: Das Mittel von `near_all` je Bauart
>   liegt innerhalb ±0,08 um den Wert ohne `+rv`. Der konstante Befehl war für sie nur ein Zeichen für die
>   Laufphase, das Bild liefert dasselbe. (2) attnmem und vitmem: Mit `+rv` lösen zusammen 3 bis 7 von 12
>   (`near_all` ≥ 0,20; ohne: 5 von 12). Das Muster `ref_enc(0)` ist am Anfang zu klein, um über Lernen oder
>   Nicht-Lernen zu entscheiden. (3) 24000 Updates: sp4 löst 6 von 6, layer_s 2 bis 4 von 6 (ohne: 6 und 3). (4)
>   Gelöste Läufe liegen je Bauart im Mittel innerhalb ±0,05 um die gelösten ohne `+rv`. Kurz: `+rv` macht die
>   Schnittstelle sauber, ändert die Ergebnisse dieser Stufe aber nicht messbar.

**Ergebnis.** `near_all`, ohne → mit `+rv`. Bei 12000 Updates Seeds 0 / 1 / 2 (attnmem, vitmem: 0 / 1 / 2 / 3 / 4 /
7), „gelöst“ ab 0,20. Bei 24000 Updates Seeds 0 / 1 / 2 / 3 / 4 / 7, „gelöst“ ab 0,45 wie im Eintrag „Lösequote
mit sechs Seeds“.

| Netz | ohne `+rv` | mit `+rv` | Mittel | gelöst |
|---|---|---|---|---|
| layer_s, 12k | 0,54 / 0,59 / 0,18 | 0,21 / 0,52 / 0,18 | 0,435 → 0,303 | 2 → 2 |
| sp4, 12k | 0,52 / 0,61 / 0,19 | 0,27 / 0,65 / 0,25 | 0,443 → 0,388 | 2 → 3 |
| am4, 12k | 0,14 / 0,35 / 0,08 | 0,10 / 0,21 / 0,12 | 0,191 → 0,143 | 1 → 1 |
| hier_s, 12k | 0,14 / 0,13 / 0,15 | 0,15 / 0,15 / 0,13 | 0,142 → 0,141 | 0 → 0 |
| attnmem, 12k | 0,07 / 0,32 / 0,37 / 0,18 / 0,44 / 0,07 | 0,07 / 0,07 / 0,07 / 0,31 / 0,38 / 0,07 | 0,241 → 0,161 | 3 → 2 |
| vitmem, 12k | 0,45 / 0,07 / 0,32 / 0,20 / 0,07 / 0,07 | 0,56 / 0,07 / 0,07 / 0,44 / 0,07 / 0,07 | 0,195 → 0,213 | 2 → 2 |
| layer_s, 24k | 0,72 / 0,21 / 0,64 / 0,23 / 0,25 / 0,74 | 0,71 / 0,21 / 0,19 / 0,21 / 0,60 / 0,72 | 0,463 → 0,440 | 3 → 3 |
| sp4, 24k | 0,71 / 0,75 / 0,73 / 0,76 / 0,75 / 0,73 | 0,64 / 0,78 / 0,73 / 0,75 / 0,73 / 0,69 | 0,739 → 0,719 | 6 → 6 |

- Welche Seeds lösen, wechselt: attnmem verliert Seeds 1 und 2 und gewinnt Seed 3, vitmem verliert Seed 2 und
  gewinnt Seed 3, layer_s 24k verliert Seed 2 und gewinnt Seed 4 (0,60, tiefer als die übrigen gelösten).
- Bei den Gitter-Netzen mit 12000 Updates sinken vor allem die späteren Ziele: `near_goal` für Ziel 2 / 3
  layer_s 0,65 / 0,60 → 0,55 / 0,48, sp4 0,66 / 0,61 → 0,62 / 0,55, am4 0,45 / 0,42 → 0,42 / 0,37. Ziel 1 bleibt
  fast gleich (Abstand höchstens 0,013). hier_s ändert sich nicht.
- Der Trainingswert (`loop_refcurve.jsonl`) unterscheidet sich bei Update 2000 um höchstens 0,02, bei 6000 um
  höchstens 0,04 in beide Richtungen. Bei 12000 liegen layer_s und sp4 Seed 0 mit `+rv` tiefer (0,69 → 0,64). Bei 24000 Updates liegen alle Endwerte innerhalb 0,02,
  außer layer_s Seed 2 (0,72 → 0,63, eingebrochen) und Seed 4 (0,65 → 0,71, gelöst).

**Vergleich mit der Vorhersage.** (1) Teilweise: sp4 −0,06, am4 −0,05, hier_s 0,00 innerhalb ±0,08, layer_s −0,13
verfehlt. (2) Getroffen: 4 von 12 gelöst (Bereich 3–7). (3) Getroffen: sp4 6 von 6, layer_s 3 von 6. Die Schwelle
ist dabei nicht ausdrücklich genannt; gemeint war die des Bezugs „6 und 3“ (0,45). Mit der Schwelle 0,20 käme
layer_s ohne `+rv` auf 6 und mit auf 5 von 6, das liegt außerhalb des Bereichs. (4) Teilweise: bei 24000 Updates
getroffen (layer_s −0,02, sp4 −0,02). Bei 12000 Updates verfehlt bei layer_s (0,56 → 0,37), sp4 (0,57 → 0,39),
am4 (0,35 → 0,21) und vitmem (0,38 → 0,50), getroffen bei attnmem (−0,03). Mit nur 1 bis 3 gelösten Läufen je
Bauart ist dieser Mittelwert allerdings stark vom einzelnen Lauf abhängig. Bilanz: 2 getroffen, 2 teilweise.

**Schluss.** (a) Bei 24000 Updates ändert `+rv` den Endstand nicht: sp4 löst weiter 6 von 6, layer_s 3 von 6, die
gelösten Läufe liegen 0,02 tiefer. Der Unterschied der Bauarten (sp4 verlässlich, layer_s nicht) bleibt. (b) Bei
12000 Updates liegen die Gitter-Netze mit `+rv` eher etwas tiefer, und zwar bei den Zielen 2 und 3. Das passt zu
„lernen etwas langsamer“: Ohne `+rv` hatten sie mit `ref_enc(0)` ein festes Zeichen für die Laufphase, mit `+rv`
müssen sie das selbst aus dem Ablauf lernen. Mit drei Seeds je Bauart und einem einzelnen Lauf (layer_s Seed 0) als
größtem Beitrag ist das ein Hinweis, kein Befund. (c) Bei attnmem und vitmem entscheidet `+rv` nicht über Lernen
oder Nicht-Lernen insgesamt (5 → 4 von 12), es mischt aber neu, welche Seeds lernen. Das Ergebnis auf dieser Stufe
ist bei ihnen also stark vom Zufall des einzelnen Laufs abhängig, und eine Lösequote braucht mehr als sechs Seeds.
(d) Ab jetzt gilt `+rv` für neue Läufe mit Vorlage. Vergleiche nur innerhalb derselben Schnittstelle (mit oder ohne
`+rv`); die alten Zahlen bleiben als Bezug gültig. (e) Zum Worker: 12 Läufe mit 24000 Updates brauchten mit 12
Prozessen 530 min, die beiden 6er-Jobs vorher zusammen 652 min.

**Belege.** `results/finds_loop.jsonl` (36 Zeilen `*+rv*` auf `robot_loop_three_f32`, davon 12 mit `ckpt`
`robot_loop_three_f32_24k`), `results/loop_refcurve.jsonl` (36 neue Zeilen), `results/checkpoints/robot_loop_three_f32/`
und `robot_loop_three_f32_24k/`.

## 2026-11-20 — `+rv`, Etappe 2 (cue, blind, two): mit nur einem Hinweis-Schritt lernen mehr Läufe die Adresse nicht

**Frage.** Ändert `+rv` (ein Schritt ohne Vorlage sendet keinen Befehl) die Ergebnisse auf den Stufen „Hinweis mit
Ansicht“ (cue), „Hinweis allein“ (blind) und „zwei Ziele“ (two)?

**Gemacht.** Worker-Jobs `20261120-060819-rv_cue` (271 min), `20261120-060819-rv_blind` (194 min) und
`20261120-060820-rv_two` (359 min), je 6 Netze × Seeds 0–2, 12000 Updates, 6 Prozesse, Commit dca3bed. Danach
lokal `finds_loop_eval.py`, 1500 Startszenen. Vorhersage vor dem Lauf (wörtlich aus „Laufend / offen“):

> - `+rv`, Etappe 2: dieselben 6 Netze (layer_s, sp4, am4, hier_s mit `+cell+refl+rv+rez3`, attnmem und vitmem
>   mit `+refl+rv+rez3`), Seeds 0–2, 12000 Updates, auf `robot_loop_cue_f32`, `robot_loop_blind_f32` und
>   `robot_loop_two_f32`. Vergleich mit denselben Seeds ohne `+rv`. Maß: `near` nach dem letzten Schritt (cue,
>   blind), `near_both` (two). Mittel ohne `+rv` (Seeds 0–2):
>   - cue: layer_s 0,888, sp4 0,880, am4 0,812, hier_s 0,861, attnmem 0,680, vitmem 0,528;
>   - blind: layer_s 0,906, sp4 0,907, am4 0,849, hier_s 0,855, attnmem 0,719, vitmem 0,649;
>   - two: layer_s 0,718, sp4 0,718, am4 0,570, hier_s 0,551, attnmem 0,251, vitmem 0,234.
>   **Vorhersage vor dem Lauf (2026-11-20):** (1) cue und blind, Gitter-Netze: Mittel je Bauart innerhalb ±0,03 um
>   den Wert ohne `+rv`. Mit nur einem Ziel gibt es nach dem Hinweis nur eine Laufphase; das Zeichen `ref_enc(0)`
>   trägt dort kaum Information. (2) cue und blind, attnmem und vitmem: Mittel je Bauart innerhalb ±0,10 (sie
>   streuen schon ohne `+rv` stark, vitmem cue 0,40–0,70). (3) two, Gitter-Netze: Mittel je Bauart höchstens 0,08
>   unter dem Wert ohne `+rv` und höchstens 0,03 darüber; im Mittel der vier Bauarten tiefer (wie bei drei Zielen,
>   Etappe 1, Schluss b). (4) two, attnmem und vitmem: innerhalb ±0,12. (5) In allen drei Aufgaben liegen die vier
>   Gitter-Netze im Mittel weiter über attnmem und vitmem.

**Ergebnis.** Je Seed 0 / 1 / 2, ohne → mit `+rv` (cue, blind: `near` nach dem letzten Schritt; two: `near_both`):

| Netz | cue | blind | two |
|---|---|---|---|
| layer_s | 0,90 / 0,90 / 0,87 → 0,85 / 0,89 / 0,81 (−0,04) | 0,90 / 0,92 / 0,89 → 0,92 / 0,91 / 0,87 (−0,01) | 0,73 / 0,70 / 0,73 → 0,70 / 0,74 / 0,72 (0,00) |
| sp4 | 0,85 / 0,87 / 0,92 → 0,57 / 0,85 / 0,89 (−0,11) | 0,89 / 0,92 / 0,92 → 0,45 / 0,91 / 0,93 (−0,14) | 0,71 / 0,73 / 0,71 → 0,73 / 0,76 / 0,75 (+0,03) |
| am4 | 0,85 / 0,78 / 0,81 → 0,79 / 0,77 / 0,77 (−0,03) | 0,84 / 0,87 / 0,84 → 0,86 / 0,86 / 0,76 (−0,02) | 0,54 / 0,61 / 0,56 → 0,40 / 0,57 / 0,48 (−0,09) |
| hier_s | 0,86 / 0,86 / 0,87 → 0,71 / 0,85 / 0,86 (−0,05) | 0,85 / 0,85 / 0,87 → 0,85 / 0,86 / 0,88 (+0,01) | 0,58 / 0,53 / 0,55 → 0,62 / 0,56 / 0,63 (+0,05) |
| attnmem | 0,69 / 0,68 / 0,67 → 0,71 / 0,73 / 0,64 (+0,02) | 0,76 / 0,72 / 0,68 → 0,67 / 0,80 / 0,77 (+0,03) | 0,15 / 0,42 / 0,19 → 0,14 / 0,43 / 0,32 (+0,05) |
| vitmem | 0,70 / 0,40 / 0,48 → 0,45 / 0,31 / 0,31 (−0,17) | 0,64 / 0,57 / 0,74 → 0,42 / 0,31 / 0,32 (−0,30) | 0,40 / 0,16 / 0,14 → 0,40 / 0,50 / 0,53 (+0,24) |

Mittel der vier Gitter-Netze ohne → mit: cue 0,861 → 0,801, blind 0,879 → 0,838, two 0,639 → 0,637. attnmem und
vitmem: cue 0,604 → 0,525, blind 0,684 → 0,547, two 0,242 → 0,386.

- Die Einbrüche bei cue und blind sind Läufe, die einen Körper ansteuern, aber nicht sicher den gesuchten
  (`near` + `other` am Ende 0,96–0,99). Bei Zufall unter drei Körpern läge `near` bei etwa 0,31.
  - Auf Zufall: vitmem cue Seeds 1 und 2 (0,308), blind Seeds 1 und 2 (0,309 / 0,321). Ohne `+rv` lag kein
    vitmem-Lauf auf diesen beiden Stufen so tief (niedrigster 0,404).
  - Dazwischen: vitmem Seed 0 (0,45 / 0,42), sp4 Seed 0 (0,57 / 0,45), hier_s Seed 0 auf cue (0,71).
- Der Trainingswert zeigt dasselbe: sp4 Seed 0 endet mit `+rv` bei 0,69 (cue) und 0,67 (blind), die anderen
  sp4-Läufe bei 0,78–0,80. Er trennt sich zwischen Update 4000 und 8000.
- Bei two lösen mit `+rv` alle drei vitmem-Läufe (`near_a` 0,59–0,68), ohne nur Seed 0.
- Encoder-Streuung (`ref_curve`, Streuung der Ausgabe über 256 Vorlagen) bei Update 2000 / 4000: sp4 Seed 0
  startet mit `+rv` spät (cue 0,007 / 0,086, blind 0,010 / 0,103; die übrigen sp4-Läufe 0,02–0,94 / 0,59–1,55).
  Bei vitmem gibt es kein einheitliches Bild: blind mit `+rv` kleiner (0,016–0,026 bei 4000, ohne 0,049–0,090),
  cue Seed 2 mit `+rv` dagegen am größten von allen (1,23) und trotzdem auf Zufall.

**Vergleich mit der Vorhersage.** (1) Verfehlt: 3 von 8 innerhalb ±0,03 (blind layer_s, am4, hier_s); cue alle
vier darunter (−0,03 bis −0,11), blind sp4 −0,14. (2) Teilweise: attnmem getroffen (+0,02 / +0,03), vitmem klar
verfehlt (−0,17 / −0,30). (3) Teilweise: layer_s 0,00 und sp4 +0,030 im Bereich, am4 −0,09 und hier_s +0,05
außerhalb; das Mittel der vier liegt 0,002 tiefer, also praktisch gleich. (4) Teilweise: attnmem +0,05 getroffen,
vitmem +0,24 verfehlt. (5) Getroffen: Die Gitter-Netze liegen in allen drei Aufgaben im Mittel klar über attnmem
und vitmem. Bilanz: 1 getroffen, 3 teilweise, 1 verfehlt.

**Schluss.** (a) `+rv` ist nicht neutral. Mit nur einem Hinweis-Schritt (cue, blind) lernen mehr Läufe die
Adresse nicht: vitmem 4 von 6 auf Zufall (ohne 0 von 6), dazu sp4 Seed 0 auf beiden Stufen halb. Das gleicht dem
Muster der älteren Läufe mit `+ref` (vor `+refl`): Dort lagen auf cue sp4 Seeds 0 und 1 und vitmem Seeds 1 und 2
auf Zufall. (b) Bei zwei Hinweis-Schritten (two) ist es umgekehrt:
vitmem löst 3 von 3 (ohne 1 von 3), die Gitter-Netze bleiben im Mittel gleich. (c) Warum, ist ungeklärt. Was sich
zwischen den Stufen unterscheidet: Zahl der Hinweis-Schritte (1 gegen 2), Länge des Laufs (4 gegen 6) und bei cue
die Ansicht im Hinweis-Schritt. Eine Vermutung, ungeprüft: Ohne `+rv` lieferte `ref_enc(0)` in jedem Laufschritt
ein kleines Signal durch den Vorlagen-Weg, und dieses Signal half, den Weg früh in Gang zu bringen. Mit einem
einzigen Hinweis-Schritt fehlt dann fast jeder Gradient in den Encoder. Für sp4 Seed 0 passt der späte Start der Encoder-Streuung
dazu, für vitmem nicht (cue Seed 2). (d) Mit drei Seeds je Netz sind die
Unterschiede einzelner Bauarten unsicher. Für vitmem auf cue und blind (4 von 6 auf Zufall gegen 0 von 6) ist er
deutlich. (e) Der Beschluss „`+rv` ist Standard“ (Etappe 1, Schluss d) ist damit offen. Sauber ist die
Schnittstelle mit `+rv`; sie macht das Lernen aber auf den Stufen mit einem Hinweis-Schritt unzuverlässiger. Bevor
wir festlegen, sollte geprüft werden, ob das am Fehlen des Gradienten liegt (siehe Vermutung c).

**Belege.** `results/finds_loop.jsonl` (Zeilen `*+rv*` auf `robot_loop_cue_f32`, `robot_loop_blind_f32`,
`robot_loop_two_f32`, je 18), `results/loop_refcurve.jsonl` (54 neue Zeilen), `results/checkpoints/robot_loop_{cue,blind,two}_f32/`.

## 2026-11-21 — `+rv` mit einem Hinweis-Schritt, mehr Seeds: bei vitmem bestätigt (6 von 12 auf Zufall, ohne 0 von 12), bei sp4 nicht

**Frage.** Ist der Befund aus Etappe 2 echt: Lernen mit `+rv` auf cue und blind mehr Läufe die Adresse nicht?

**Gemacht.** Worker-Jobs `20261120-234122-rvseeds_blind` (102 min) und `20261120-234122-rvseeds_cue` (105 min),
je 12 Läufe mit 14 Prozessen, Commit 70b6c29. Danach lokal `finds_loop_eval.py`, 1500 Startszenen. Zusammen mit
Etappe 2 sind es je Netz, Aufgabe und Variante 6 Läufe (Seeds 0–4, 7). Vorhersage vor dem Lauf (wörtlich aus
„Laufend / offen“):

> - `+rv` mit einem Hinweis-Schritt, Nachmessung mit mehr Seeds (Auftrag Nutzer 2026-11-20): Ist der Befund aus
>   Etappe 2 echt (vitmem auf cue und blind mit `+rv` 4 von 6 Läufen auf Zufall, ohne 0 von 6; sp4 Seed 0 halb
>   eingebrochen)? vitmem `+refl+rez3` und `+refl+rv+rez3`, layer_s_sp4 `+cell+refl+rez3` und `+cell+refl+rv+rez3`,
>   auf `robot_loop_cue_f32` und `robot_loop_blind_f32`, Seeds 3, 4, 7, 12000 Updates: 24 Läufe, Worker mit 14
>   Prozessen. Maß wie in Etappe 2: `near` nach dem letzten Schritt. „Auf Zufall“ heißt `near` ≤ 0,35,
>   „eingebrochen“ bei sp4 heißt `near` < 0,75 (gelernte sp4-Läufe bisher 0,85–0,93).
>   **Vorhersage vor dem Lauf (2026-11-20):** (1) vitmem mit `+rv`: mindestens 3 der 6 neuen Läufe auf Zufall; ohne
>   `+rv`: höchstens 1 von 6. (2) Zusammen mit Seeds 0–2 (12 Läufe je Variante) ist der Unterschied bei vitmem im
>   exakten Test nach Fisher (einseitig) p < 0,05. (3) sp4 mit `+rv`: mindestens 1 der 6 neuen Läufe eingebrochen;
>   ohne `+rv`: keiner. (4) sp4-Läufe, die nicht eingebrochen sind, liegen mit und ohne `+rv` im Mittel höchstens
>   0,03 auseinander: `+rv` entscheidet über Lernen oder Nicht-Lernen, nicht über die Güte danach.

**Ergebnis.** `near` nach dem letzten Schritt, Seeds 0 / 1 / 2 / 3 / 4 / 7 (die ersten drei aus Etappe 2):

| Netz | Aufgabe | ohne `+rv` | mit `+rv` |
|---|---|---|---|
| vitmem | cue | 0,70 / 0,40 / 0,48 / 0,62 / 0,70 / 0,74 | 0,45 / 0,31 / 0,31 / 0,52 / 0,47 / 0,58 |
| vitmem | blind | 0,64 / 0,57 / 0,74 / 0,62 / 0,43 / 0,45 | 0,42 / 0,31 / 0,32 / 0,82 / 0,31 / 0,35 |
| sp4 | cue | 0,85 / 0,87 / 0,92 / 0,88 / 0,90 / 0,89 | 0,57 / 0,85 / 0,89 / 0,86 / 0,90 / 0,85 |
| sp4 | blind | 0,89 / 0,92 / 0,92 / 0,90 / 0,91 / 0,91 | 0,45 / 0,91 / 0,93 / 0,91 / 0,86 / 0,82 |

- vitmem auf Zufall (`near` ≤ 0,35): mit `+rv` 6 von 12 (cue 2, blind 4), ohne 0 von 12 (niedrigster 0,40).
  Exakter Test nach Fisher, einseitig: p = 0,007. Mittel aller 12 Läufe ohne → mit: 0,590 → 0,430.
- Die neuen Läufe auf Zufall sind blind Seed 4 (0,307) und Seed 7 (0,348). Bei cue liegen die neuen
  `+rv`-Läufe bei 0,47–0,58, also unter allen neuen Läufen ohne `+rv` (0,62–0,74), aber über Zufall.
- sp4 eingebrochen (`near` < 0,75): mit `+rv` 2 von 12 (beide Seed 0), ohne 0 von 12; p = 0,24. Die 6 neuen
  `+rv`-Läufe liegen alle bei 0,82–0,91.
- sp4, nicht eingebrochene Läufe im Mittel: ohne 0,896 (12 Läufe), mit 0,877 (10 Läufe), Abstand 0,019. Nur die
  neuen Seeds: 0,899 gegen 0,865, Abstand 0,034.

**Vergleich mit der Vorhersage.** (1) Teilweise: mit `+rv` 2 der 6 neuen Läufe auf Zufall (vorhergesagt mindestens
3), ohne 0 von 6 (getroffen). (2) Getroffen: p = 0,007. (3) Verfehlt: kein neuer sp4-Lauf mit `+rv` eingebrochen.
(4) Getroffen mit allen Läufen (0,019); nur mit den neuen Seeds knapp darüber (0,034). Bilanz: 2 getroffen, 1
teilweise, 1 verfehlt.

**Schluss.** (a) Für vitmem ist der Befund bestätigt: Mit einem einzigen Hinweis-Schritt macht `+rv` das Lernen
der Adresse deutlich unzuverlässiger (6 von 12 auf Zufall gegen 0 von 12), am stärksten bei blind, wo der
Hinweis-Schritt nur die Vorlage zeigt. (b) Für sp4 ist er nicht bestätigt. Die beiden Einbrüche kommen beide aus
Seed 0; mit den neuen Seeds sieht man keinen Unterschied der Lösequote. Die gelernten Läufe liegen mit `+rv` eher
etwas tiefer (0,02–0,03). (c) Zusammen mit Etappe 2 (two: vitmem mit `+rv` besser) hängt die Wirkung von `+rv`
also an der Bauart und an der Zahl der Hinweis-Schritte. Ein Standard, der vitmem auf einer Stufe hilft und auf
einer anderen schadet, ist keine reine Frage der Sauberkeit. (d) Die Ursache bleibt offen. Prüfbar ist die
Frage, ob die Netze ohne `+rv` vom festen Befehl `ref_enc(0)` als Zeichen für die Laufphase profitieren. Dafür
käme in Frage: Die Laufschritte senden ein eigenes, gelerntes Zeichen „keine Vorlage“, das nicht durch den
Vorlagen-Encoder geht. Hilft das vitmem so wie ohne `+rv`, liegt es am Zeichen, nicht am Gradienten in den
Encoder.

**Belege.** `results/finds_loop.jsonl` (24 neue Zeilen, Seeds 3, 4, 7 auf `robot_loop_cue_f32` und
`robot_loop_blind_f32`), `results/loop_refcurve.jsonl` (24 neue Zeilen), `results/checkpoints/robot_loop_{cue,blind}_f32/`.

## 2026-11-21 — Korrektur: Die Live-Tests liefen mit falscher Szenenfarbe

**Frage.** Beim Bau der Video-Aufzeichnung für den Live-Test (Auftrag Nutzer 2026-11-21) aufgefallen: Stimmt die
Farbe der Szenen im Live-Skript?

**Gemacht.** Code gelesen (`rdf_thalamus_sml/src/pc_cvnn/netresearch_live_loop.py`, `make_scene`;
`export_netresearch.py`, `_paint`). Danach korrigiert und mit dem neuen Video-Skript an drei Szenen angesehen.

**Ergebnis.** `make_scene` malt die drei Körper einer Szene in einer eigenen Zufallsfarbe. Die Farbe steht in
`geom_rgba` des Modells, nicht im gespeicherten Zustand `qpos`. Das Skript erzeugt zuerst alle 150 Szenen und
rechnet sie danach. Damit lief jede Szene in der Farbe der zuletzt erzeugten. Die Zeigebilder wurden dagegen beim
Erzeugen aufgenommen, also in der eigenen Farbe. In 149 von 150 Szenen hatten Zeigebild und Szene verschiedene
Farben; im Prüfstand (`gazeshapec`) haben sie dieselbe.

**Schluss.** (a) Betroffen sind alle Live-Zahlen: die Einträge „Erster Live-Test im Roboter-Simulator“, „Arm im
Bild: Ablenkung, nicht Verdecken“ und „Live-Test mit der Prüfstands-Regel“. Sie gelten nur unter Vorbehalt, bis
neu gemessen ist. (b) Weil `static` trotzdem nahe am Prüfstand lag (höchstens 0,04 Abstand), suchen die Netze
offenbar vor allem nach der Form, die Farbe des Zeigebilds spielt wenig Rolle. Das ist eine Deutung, keine Messung.
Die unerklärten leicht höheren `static`-Werte (Mittel +0,010) könnten hiermit zusammenhängen. (c) Korrigiert in
Robot-Commit 17c0b19: Die Szene trägt ihre Farbe, vor jeder Szene wird neu gemalt (`show_scene`), neue Zeilen tragen
`scene_colour: own`. Die Szenen selbst sind unverändert (die Farbe verbraucht keine Zufallszahlen). (d) Neu:
`netresearch_live_video.py` zeichnet einzelne Läufe als Video auf (gleiche Szenen und Regeln). Erster Test mit
layer_s_sp4, 24000 Updates, Seed 0, `live`, Szenen 0–2, Folgen A B C und A B A: 5 von 6 Läufen treffen alle drei
Ziele. Das ist ein Blick auf einzelne Läufe, keine Messung.

**Belege.** `rdf_thalamus_sml`, Commit 17c0b19; Wiki `befunde/netresearch-live-blickschleife.md` (Nachtrag
2026-11-21).

## 2026-11-21 — Live-Test mit eigener Szenenfarbe: die Befunde halten, sp4 war durch die falsche Farbe leicht benachteiligt

**Frage.** Ändern sich die Live-Befunde, wenn jede Szene in ihrer eigenen Farbe läuft (Korrektur vom selben Tag)?

**Gemacht.** `rdf_thalamus_sml/src/pc_cvnn/netresearch_live_loop.py` (Robot-Commit 17c0b19) gegen
`scripts/policy_server.py`, dieselben 12 Netze und 150 Szenen, Bedingungen `static`, `live` und `away`, lokal
(etwa 35 min). Orakel 1,00 in allen drei Bedingungen. Vorhersage vor dem Lauf (wörtlich aus „Laufend / offen“):

> - Live-Test neu mit eigener Szenenfarbe (Auftrag Nutzer 2026-11-21, nach der Korrektur vom selben Tag):
>   dieselben 12 Netze (sp4 und layer_s 24000 Updates, vitmem und attnmem 12000, je Seeds 0–2), dieselben 150
>   Szenen (Saat 77000), Bedingungen `static`, `live` und `away` (vorher `away` nur für 5 Netze), Robot-Commit
>   17c0b19 -> `results/robot_live_loop_v3.jsonl`.
>   **Vorhersage vor dem Lauf (2026-11-21):** (1) Die Farbe spielt kaum eine Rolle: `static` je Netz höchstens 0,04
>   vom alten Wert. (2) Abstand `static` zum Prüfstand im Mittel der 12 Netze innerhalb ±0,02 (vorher +0,010).
>   (3) Der Arm kostet weiter: Gitter-Netze mit `static` ≥ 0,5 verlieren mit `live` 15–30 % (vorher 21–28 %).
>   (4) `away` gegen `live` je Netz mit `static` ≥ 0,2 im Verhältnis 0,9–1,2 (Ablenkung, nicht Verdecken, hält).
>   (5) Spearman Prüfstand–`live` mindestens 0,9.

**Ergebnis.** `near_all`, alter Wert (falsche Farbe) → neuer Wert:

| Netz | Seed | Prüfstand | `static` | `live` | Verlust | `away` | `away` / `live` |
|---|---|---|---|---|---|---|---|
| sp4, 24k | 0 | 0,714 | 0,716 → 0,759 | 0,552 → 0,581 | 23 % | 0,573 | 0,99 |
| sp4, 24k | 1 | 0,753 | 0,768 → 0,794 | 0,554 → 0,557 | 30 % | 0,558 | 1,00 |
| sp4, 24k | 2 | 0,732 | 0,761 → 0,780 | 0,561 → 0,586 | 25 % | 0,579 | 0,99 |
| layer_s, 24k | 0 | 0,721 | 0,757 → 0,758 | 0,597 → 0,582 | 23 % | 0,551 | 0,95 |
| layer_s, 24k | 1 | 0,210 | 0,217 → 0,221 | 0,201 → 0,206 | 7 % | 0,189 | 0,92 |
| layer_s, 24k | 2 | 0,637 | 0,632 → 0,637 | 0,494 → 0,493 | 23 % | 0,496 | 1,01 |
| vitmem | 0 | 0,448 | 0,432 → 0,441 | 0,377 → 0,372 | 16 % | 0,368 | 0,99 |
| vitmem | 1 | 0,071 | 0,073 → 0,080 | 0,070 → 0,067 | 17 % | 0,070 | 1,05 |
| vitmem | 2 | 0,315 | 0,309 → 0,321 | 0,261 → 0,267 | 17 % | 0,274 | 1,03 |
| attnmem | 0 | 0,068 | 0,077 → 0,073 | 0,070 → 0,067 | 8 % | 0,064 | 0,96 |
| attnmem | 1 | 0,319 | 0,342 → 0,328 | 0,279 → 0,272 | 17 % | 0,265 | 0,98 |
| attnmem | 2 | 0,370 | 0,393 → 0,396 | 0,322 → 0,318 | 20 % | 0,314 | 0,99 |

- `static` ändert sich bei 9 von 12 Netzen um höchstens 0,014. Die drei sp4-Läufe steigen: +0,019 bis +0,043.
- `static` liegt jetzt bei 11 von 12 Netzen über dem Prüfstand, im Mittel +0,019 (vorher +0,010).
- Spearman Prüfstand–`live` 0,951 (vorher 0,97), Prüfstand–`static` 0,993.

**Vergleich mit der Vorhersage.** (1) Teilweise: 11 von 12 innerhalb 0,04, sp4 Seed 0 mit +0,043 knapp darüber.
(2) Getroffen, knapp: +0,019 (Grenze ±0,02). (3) Getroffen: die fünf Gitter-Läufe mit `static` ≥ 0,5 verlieren
23–30 %. (4) Getroffen: `away` / `live` 0,92–1,05 bei allen 10 Netzen mit `static` ≥ 0,2. (5) Getroffen: 0,951.
Bilanz: 4 getroffen, 1 teilweise.

**Schluss.** (a) Die Befunde vom 19.11. halten: Der Prüfstand sagt die Rangfolge vorher (Spearman 0,95), der Arm
im Bild kostet die Gitter-Netze ein Viertel (23–30 %), und er stört durch Ablenkung, nicht durch Verdecken
(`away` gleich `live`, jetzt für alle 10 Netze über Zufall geprüft). Der Vorbehalt aus der Korrektur ist damit
aufgehoben; die neuen Zahlen ersetzen die alten. (b) Die falsche Farbe hat nur sp4 merklich geschadet (bis 0,04);
die anderen Bauarten suchen offenbar nur nach der Form. Warum gerade sp4 auf die Farbe des Zeigebilds achtet, ist
nicht geprüft. (c) Der leicht höhere Wert `static` gegenüber dem Prüfstand ist nicht die Farbe, er wird mit der
richtigen Farbe sogar größer (+0,019). Übrig bleiben die eigenen Szenen des Live-Skripts (eigene Saat, Schwerpunkt
aus dem Modell, Zeigebilder aus der Simulation). Für die Vorhersage der Rangfolge ist das unerheblich.

**Belege.** `results/robot_live_loop_v3.jsonl` (39 Zeilen, Feld `scene_colour: own`); Wiki
`befunde/netresearch-live-blickschleife.md`.

## 2026-11-21 — `+rvt` (gelerntes Zeichen „keine Vorlage“): bringt vitmem nicht zurück (4 von 12 auf Zufall, ohne `+rv` 0 von 12)

**Frage.** Fehlte vitmem mit `+rv` das feste Zeichen für die Laufphase (dann hilft `+rvt`) oder der Gradient, den
`ref_enc(0)` in jedem Laufschritt in den Vorlagen-Encoder gab (dann hilft `+rvt` nicht)?

**Gemacht.** Worker-Jobs `20261121-084252-rvt_cue` und `20261121-084253-rvt_blind` (je 105 min, 14 Prozesse,
Commit 7bdb562), je vitmem und sp4 × Seeds 0–4, 7, 12000 Updates. Danach lokal `finds_loop_eval.py`, 1500
Startszenen. Vergleich mit denselben Seeds ohne `+rv` und mit `+rv`. Vorhersage vor dem Lauf (wörtlich aus
„Laufend / offen“, Commit 7bdb562):

> - Gelerntes Zeichen „keine Vorlage“ (`+rvt`, Auftrag Nutzer 2026-11-21): Wie `+rv`, aber Laufschritte senden
>   statt nichts ein eigenes, gelerntes Zeichen (16 Werte, `model.no_ref`, Start bei 0), das wie ein gewöhnlicher
>   Befehl in den Port geht, nicht durch den Vorlagen-Encoder. Geprüft (`scripts/check_ref_valid.py`, Teil 6):
>   - gleiche Anfangsgewichte wie `+rv`, dazu das Zeichen bei 0;
>   - Hinweis-Schritte rechnen wie `+rv`, Laufschritte wie ein Befehl gleich dem Zeichen;
>   - kein Gradient in den Vorlagen-Encoder aus Laufschritten, aber in das Zeichen;
>   - Rauchtest 300 Updates (vitmem, sp4), das Zeichen lernt.
>   Frage: Fehlte vitmem mit `+rv` das feste Zeichen für die Laufphase (dann hilft `+rvt`) oder der Gradient, den
>   `ref_enc(0)` in jedem Laufschritt in den Encoder gab (dann hilft `+rvt` nicht)? vitmem und sp4 mit
>   `+refl+rvt+rez3` (sp4 mit `+cell`), `robot_loop_cue_f32` und `robot_loop_blind_f32`, Seeds 0–4, 7, 12000 Updates:
>   24 Läufe, Worker mit 14 Prozessen. Vergleich mit denselben Seeds ohne `+rv` (vitmem 0 von 12 auf Zufall) und mit
>   `+rv` (6 von 12). Maße und Schwellen wie in der Nachmessung (Zufall: `near` ≤ 0,35; sp4 eingebrochen: < 0,75).
>   **Vorhersage vor dem Lauf (2026-11-21):** (1) Das Zeichen hilft nicht: vitmem mit `+rvt` mindestens 4 von 12
>   auf Zufall. Begründung: Auch mit `+rv` ist die Laufphase am Bild erkennbar (im Hinweis-Schritt liegt ein Muster
>   auf dem Bild, in den Laufschritten nicht); was ohne `+rv` zusätzlich da war, ist der Gradient durch den
>   gemeinsamen Encoder-Weg. (2) Damit vitmem `+rvt` gegen ohne `+rv`: Fisher einseitig p < 0,05. (3) sp4 mit `+rvt`:
>   höchstens 2 von 12 eingebrochen. (4) sp4, nicht eingebrochene Läufe: Mittel innerhalb 0,03 um ohne `+rv`
>   (0,896).

**Ergebnis.** `near` nach dem letzten Schritt, Seeds 0 / 1 / 2 / 3 / 4 / 7:

| Netz | Aufgabe | ohne `+rv` | mit `+rv` | mit `+rvt` |
|---|---|---|---|---|
| vitmem | cue | 0,70 / 0,40 / 0,48 / 0,62 / 0,70 / 0,74 | 0,45 / 0,31 / 0,31 / 0,52 / 0,47 / 0,58 | 0,31 / 0,36 / 0,31 / 0,65 / 0,66 / 0,71 |
| vitmem | blind | 0,64 / 0,57 / 0,74 / 0,62 / 0,43 / 0,45 | 0,42 / 0,31 / 0,32 / 0,82 / 0,31 / 0,35 | 0,31 / 0,54 / 0,81 / 0,75 / 0,42 / 0,31 |
| sp4 | cue | 0,85 / 0,87 / 0,92 / 0,88 / 0,90 / 0,89 | 0,57 / 0,85 / 0,89 / 0,85 / 0,90 / 0,85 | 0,77 / 0,81 / 0,90 / 0,87 / 0,91 / 0,85 |
| sp4 | blind | 0,89 / 0,92 / 0,92 / 0,90 / 0,91 / 0,91 | 0,45 / 0,91 / 0,92 / 0,90 / 0,86 / 0,82 | 0,51 / 0,91 / 0,92 / 0,91 / 0,68 / 0,86 |

- vitmem auf Zufall (`near` ≤ 0,35): ohne 0 von 12, mit `+rv` 6 von 12, mit `+rvt` 4 von 12. Mittel aller 12
  Läufe: 0,590 / 0,430 / 0,512. Fisher einseitig `+rvt` gegen ohne: p = 0,047; `+rv` gegen `+rvt`: p = 0,34.
- Mit `+rvt` liegen andere vitmem-Seeds auf Zufall als mit `+rv`: cue 0 und 2, blind 0 und 7 (mit `+rv`: cue 1
  und 2, blind 1, 2, 4, 7). Seed 0 lag ohne `+rv` auf beiden Stufen hoch (0,70 / 0,64).
- Alle Läufe steuern am Ende einen Körper an (`near` + `other` 0,97–1,00); wer auf Zufall liegt, wählt den
  falschen.
- sp4 eingebrochen (`near` < 0,75): ohne 0 von 12, mit `+rv` 2 von 12, mit `+rvt` 2 von 12 (blind Seed 0 mit 0,51,
  blind Seed 4 mit 0,68; cue Seed 0 knapp darüber mit 0,77). Fisher gegen ohne: p = 0,24. Nicht eingebrochene
  Läufe im Mittel: ohne 0,896, mit `+rv` 0,877, mit `+rvt` 0,872.

**Vergleich mit der Vorhersage.** (1) Getroffen, genau an der Grenze: 4 von 12. (2) Getroffen, knapp: p = 0,047.
(3) Getroffen: 2 von 12. (4) Getroffen: 0,872, Abstand 0,024. Bilanz: 4 getroffen.

**Schluss.** (a) Das gelernte Zeichen bringt vitmem nicht auf den Stand ohne `+rv`: 4 von 12 Läufen lernen die
Adresse nicht, ohne `+rv` keiner. Das spricht gegen die Deutung „es fehlte nur ein Zeichen für die Laufphase“ und
passt zur Deutung „es fehlte der Gradient durch den gemeinsamen Encoder-Weg“. (b) Belegt ist diese Deutung damit
nicht. Geprüft ist nur das Gegenteil, und auch das knapp (p = 0,047 bei der vorher gesetzten Grenze). Zwischen
`+rv` und `+rvt` ist kein Unterschied messbar (6 gegen 4 von 12, p = 0,34). Dass das Zeichen ein wenig hilft, ist
also möglich, aber nicht gezeigt. (c) Welche Seeds scheitern, wechselt mit der Variante. Das Scheitern hängt also
am einzelnen Lauf, nicht an einem festen Seed; nur sp4 Seed 0 ist in beiden Varianten schwach. (d) Für sp4 bleibt
das Bild wie bei `+rv`: gelegentliche Einbrüche (2 von 12), sonst etwa 0,02 tiefer als ohne `+rv`. (e) Für die
offene Frage „`+rv` als Standard“ heißt das: Die Netze ohne `+rv` lernen die Adresse auf den Stufen mit einem
Hinweis-Schritt zuverlässiger, und ein Zeichen allein ersetzt das nicht.

**Belege.** `results/finds_loop.jsonl` (24 neue Zeilen `*+rvt*` auf `robot_loop_cue_f32` und
`robot_loop_blind_f32`), `results/loop_refcurve.jsonl` (24 neue Zeilen), `results/checkpoints/robot_loop_{cue,blind}_f32/`.

Nachtrag zum Eintrag „Live-Test mit eigener Szenenfarbe“ (selber Tag): Beim Einfügen hatte das Skript die damals
noch offene `+rvt`-Vorhersage mit in das Zitat jenes Eintrags gezogen. Sie ist dort entfernt und steht hier.

## 2026-11-21 — Phase C, erster Test: Das eingefrorene Können wird genutzt, aber Andocken lernt langsamer als Feintuning, und Mischen schlägt beides

**Frage.** Lernt ein neues Modul `match_shift`, wenn es ein eingefrorenes Netz mit dem Können `keep_shift`
seitlich lesen darf, und wie steht das gegen Feintuning, Mischen und eine Kontrolle ohne Können?

**Gemacht.** Worker-Job `20261121-131839-route_match` (45 Läufe, 14 Prozesse, Commit 85c08b4), layer_s, hier_s,
gru, Seeds 0–2. Vorhersage vor dem Lauf (wörtlich aus „Laufend / offen“):

> - Phase C, erster Test: Einfrieren und Andocken auf der Vergleichs-Leiter (Auftrag Nutzer 2026-11-21: Port ohne
>   `+rv` schließen, mit Phase C beginnen; Anbindung seitlich + Gate, Prüfstand Vergleichs-Leiter).
>   Baustein `netresearch/models/route.py`, Lehrplan-Wort `freeze` in `netresearch/curriculum.py`:
>   - Das bis dahin gelernte Netz wird eingefroren (kein Gradient, Gewichte bleiben gleich).
>   - Ein neues Modul gleicher Bauart (100k, eigener Start) lernt weiter. Es bekommt die oberste Darstellung des
>     eingefrorenen Netzes (Eingang seines Kopfes) über eine gelernte Abbildung auf 16 Werte an seinem
>     Befehls-Port (`+cell` bei Gittern, `+cmd` bei gru).
>   - Ein Gate (ein Wert je Schritt, aus der obersten Darstellung des neuen Moduls, Start 0,5) mischt die
>     Ausgaben beider.
>   - Geprüft in `scripts/check_route.py`: eingefrorener Teil rechnet wie das Netz allein (auch mit Resets),
>     Gewichte bleiben gleich, kein Gradient dorthin, Gradient in neues Modul, Abbildung und Gate, seitliches
>     Signal wirkt.
>   Fünf Pläne, je 12000 Updates insgesamt (bei `freeze` + Kontrolle 9000 nach dem Einfrieren), layer_s, hier_s,
>   gru, Seeds 0–2, `--watch keep_shift match_shift`, Worker mit 14 Prozessen -> `results/route.jsonl`:
>   (P1) `match_shift:12000` von null an; (P2) `keep_shift:3000 match_shift:9000` Feintuning;
>   (P3) `keep_shift:3000 freeze match_shift:9000` Einfrieren und Andocken; (P4) `freeze match_shift:9000`
>   Kontrolle: eingefroren wird ein ungelerntes Netz (gleicher Aufbau, kein Können darin);
>   (P5) `keep_shift+match_shift:12000` beides gemischt.
>   Bekannt (Seeds 5, 6): von null an layer_s und hier_s 0,00, gru 0,43; nach 3000 Updates `keep_shift` lösen alle
>   drei `match_shift` (0,94–1,00). Nie gemessen: wie viel `keep_shift` beim Feintuning verloren geht.
>   Bewertung: `match_shift` gelöst = Wert ≥ 0,8.
>   **Vorhersage vor dem Lauf (2026-11-21):** (1) P1: layer_s und hier_s ≤ 0,1 in 6 von 6, gru 0,3–0,5.
>   (2) P2: `match_shift` gelöst in mindestens 7 von 9; `keep_shift` am Ende < 0,5 in mindestens 6 von 9 (das
>   Feintuning vergisst). (3) P3: `match_shift` gelöst in mindestens 6 von 9, bei den Gittern je Seed mindestens
>   0,5 über P4. (4) P4: layer_s und hier_s ≤ 0,1 in 6 von 6, gru 0,3–0,5. (5) P3 lernt langsamer als P2:
>   nach 3000 Updates der zweiten Stufe (Update 6000) liegt das Mittel von P3 unter dem von P2. (6) Das
>   eingefrorene Netz allein behält `keep_shift` genau (Prüfung, keine Vorhersage); der Verbund aus P3 löst
>   `keep_shift` dagegen nicht (< 0,5 in mindestens 6 von 9), weil das Gate nichts über die Aufgabe weiß.
>   (7) P5: die Gitter lösen `match_shift` in höchstens 3 von 6.

**Ergebnis.** `match_shift` am Ende, Seeds 0 / 1 / 2:

| Netz | P1 von null | P2 Feintuning | P3 Einfrieren + Andocken | P4 Kontrolle | P5 gemischt |
|---|---|---|---|---|---|
| layer_s | 0,00 / 0,00 / 0,00 | 1,00 / 1,00 / 0,99 | 0,52 / 0,74 / 0,32 | 0,00 / 0,00 / 0,00 | 0,81 / 0,96 / 0,73 |
| hier_s | 0,00 / 0,00 / 0,00 | 1,00 / 1,00 / 1,00 | 0,93 / 0,46 / 0,87 | 0,00 / 0,00 / 0,00 | 1,00 / 1,00 / 0,99 |
| gru | 0,44 / 0,43 / 0,42 | 0,99 / 0,99 / 0,99 | 0,97 / 0,97 / 0,97 | 0,00 / 0,00 / 0,00 | 0,95 / 0,97 / 0,92 |

`keep_shift` am Ende:

| Netz | P2 Feintuning | P3 Verbund | P3 eingefrorenes Netz allein | P5 gemischt |
|---|---|---|---|---|
| layer_s | 0,01 / 0,06 / 0,02 | 0,18 / 0,10 / 0,12 | 1,00 / 1,00 / 1,00 | 1,00 / 1,00 / 1,00 |
| hier_s | 0,00 / 0,00 / 0,00 | 0,05 / 0,11 / 0,02 | 1,00 / 1,00 / 1,00 | 1,00 / 1,00 / 1,00 |
| gru | 0,00 / 0,01 / 0,03 | 0,01 / 0,00 / 0,00 | 0,40 / 0,45 / 0,43 | 0,13 / 0,12 / 0,04 |

- Nach Stufe 1 (3000 Updates) können die Gitter `keep_shift` ganz (1,00), gru nur zu 0,37–0,42.
- Feintuning vergisst `keep_shift` sofort: 250 Updates nach dem Wechsel liegt es bei 0,00–0,07.
- `match_shift` nach 3000 Updates der zweiten Stufe (Update 6000), Mittel aller 9 Läufe: P2 0,90, P3 0,48. Bei den
  Gittern P2 0,74–0,95, P3 0,11–0,54; gru in P2 und P3 gleich (0,90–0,94).
- P3 bei layer_s steigt am Ende noch (Seed 0: 0,34 bei Update 9000, 0,52 bei 12000; Seed 1: 0,49 → 0,74), Seed 2
  bleibt bei 0,3. hier_s Seed 1 bleibt bei 0,39–0,46.
- Die Kontrolle P4 liegt in allen 9 Läufen bei 0,00, auch gru (von null an allein 0,43).

**Vergleich mit der Vorhersage.** (1) Getroffen. (2) Getroffen: 9 von 9 gelöst, `keep_shift` in 9 von 9 unter
0,5. (3) Verfehlt: 5 von 9 gelöst (vorhergesagt mindestens 6); bei den Gittern 4 von 6 Seeds mindestens 0,5 über
P4 (verfehlt sind layer_s Seed 2 und hier_s Seed 1). (4) Teilweise: Gitter getroffen, gru verfehlt (0,00 statt
0,3–0,5). (5) Getroffen: 0,48 gegen 0,90. (6) Getroffen: Das eingefrorene Netz allein hält `keep_shift` (Gitter
1,00 wie vor dem Einfrieren; gru 0,40–0,45, im Rahmen der Messstreuung um 0,37–0,42), der Verbund löst es in 9 von 9
nicht. (7) Verfehlt: Die Gitter lösen gemischt 5 von 6 (vorhergesagt höchstens 3). Bilanz: 4 getroffen, 1
teilweise, 2 verfehlt.

**Schluss.** (a) Das eingefrorene Können wird genutzt: Ohne Können (P4) lernt kein Lauf `match_shift`, mit Können
(P3) liegen alle Läufe bei 0,32–0,97. Sogar das gru, das `keep_shift` nur zu 0,4 gelernt hatte, macht
`match_shift` für das neue Modul lernbar (0,97). (b) Für die Gitter ist Andocken aber deutlich schwächer als
Feintuning: 2 von 6 gelöst gegen 6 von 6, und langsamer. Einige Läufe steigen am Ende noch; ob mehr Updates
reichen, ist nicht gemessen. Mögliche Gründe, ungeprüft: Das seitliche Signal ist nur die oberste Darstellung,
durch 16 Werte; ein frisches layer_s ignoriert am Anfang jeden Befehl (zweite Zellschicht startet bei null).
(c) Feintuning vergisst vollständig und sofort. (d) Mischen ist für die Gitter am besten: beide Aufgaben (keep
1,00, match 0,73–1,00) mit einem Netz und ohne Zusatz-Parameter. Wenn die Daten der alten Aufgabe verfügbar
sind, schlägt Mischen also das Einfrieren. Einfrieren lohnt nur, wo sie fehlen. (e) Der Verbund verliert
`keep_shift`: Das Gate sieht nur die Eingabe, nicht die Aufgabe. Das Können bleibt nur im eingefrorenen Eintrag
selbst erhalten. Für eine Bibliothek fehlt also die Auswahl nach Aufgabe. (f) Ungeklärt: Warum die Kontrolle
beim gru 0,00 ergibt, wo das gru allein 0,43 erreicht. Vermutlich stört die zufällige Ausgabe des ungelernten
Netzes, die das Gate am Anfang zur Hälfte beimischt; geprüft ist das nicht. (g) gru lernt `keep_shift` in keinem
Plan über 0,45; für gru ist die Leiter also kein sauberer Test des Erhalts.

**Belege.** `results/route.jsonl` (45 Zeilen, Feld `frozen_final` für das eingefrorene Netz allein, Lernkurven
alle 250 Updates für beide Aufgaben).

## 2026-11-21 — Phase C, Schwäche der Gitter: das seitliche Signal „nur oben“ ist der Engpass, nicht die Breite

**Frage.** Warum lernen die Gitter-Netze beim Einfrieren und Andocken `match_shift` schwächer als beim Feintuning
(erster Test: 2 von 6 gelöst gegen 6 von 6)? Geprüft werden die drei Vermutungen aus dem vorigen Eintrag: das
seitliche Signal geht nur durch 16 Werte (1a), es kommt nur aus der obersten Darstellung (1b), ein frisches
layer_s ignoriert anfangs den Befehl (2).

**Gemacht.** Job `20261121-153910-route_probe` (Commit 60e60cf), 60 Läufe auf dem Worker mit 14 Prozessen. Je eine
Änderung gegenüber `freeze` (`netresearch/models/route.py`, geprüft in `scripts/check_route.py` Teil 6). Stufe 1
ist in allen Varianten gleich: `frozen_final` stimmt je Netz und Seed in allen sechs Varianten überein. Vorhersage
vor dem Lauf (wörtlich aus „Laufend / offen“):

> - Phase C, Ursachen der Schwäche bei den Gittern (Auftrag Nutzer 2026-11-21: „Prüfe die Vermutungen zur Schwäche
>   bei den Gittern“). Plan wie P3 (`keep_shift:3000 freeze… match_shift:9000`), je eine Änderung
>   (`netresearch/models/route.py`, geprüft in `scripts/check_route.py` Teil 6):
>   - `freeze` unverändert (Seeds 0–2 als Wiederholung, Stufe 1 ist bei gleichem Seed bitgleich, geprüft);
>   - Vermutung 1a „durch 16 Werte“: `freeze:p64` (64 Werte), `freeze:pfull` (die ganze oberste Darstellung);
>   - Vermutung 1b „nur oben“: `freeze:pcell` (jede neue Zelle liest die gleiche eingefrorene Zelle, 16 Werte
>     je Zelle; layer_s: Ausgabe der Zelle, hier_s: ORP-Ausgang des Moduls);
>   - Vermutung 2 „frisches layer_s ignoriert den Befehl“: `freeze:fc2` (zweite Zellschicht startet zufällig).
>     hier_s startet sie ohnehin zufällig; dort ist `fc2` nur ein neu gewürfelter Start und zeigt, wie stark
>     der Start allein streut;
>   - zusätzlich: `freeze:nogate` (keine Beimischung der alten Ausgabe).
>   layer_s und hier_s, Seeds 0–4, 60 Läufe, Worker mit 14 Prozessen -> `results/route.jsonl`. Vergleich je Seed
>   gegen `freeze`; Maß: `match_shift` am Ende, Mittel über 10 Läufe (5 Seeds × 2 Netze); gelöst = ≥ 0,8.
>   **Vorhersage vor dem Lauf (2026-11-21):** (0) `freeze` Seeds 0–2 wiederholt die alten Werte auf ±0,01.
>   (1) Breite ist nicht der Engpass: `p64` und `pfull` je im Mittel innerhalb ±0,10 von `freeze`. (2) „Nur
>   oben“ ist der Engpass: `pcell` im Mittel mindestens 0,15 über `freeze` und gelöst in mindestens 7 von 10.
>   (3) Der Null-Start ist es nicht: `fc2` bei layer_s im Mittel innerhalb ±0,10 von `freeze`; bei hier_s (nur
>   neu gewürfelt) ebenso. (4) `nogate` im Mittel innerhalb ±0,10 von `freeze`. (5) Keine Variante erreicht das
>   Tempo des Feintunings: bei Update 6000 liegt jede im Mittel unter 0,80 (Feintuning der Gitter: 0,85).

**Ergebnis.** `match_shift` am Ende, Seeds 0–4:

| Variante | layer_s | Mittel | hier_s | Mittel | alle 10: Mittel | Δ zu `freeze` (je Seed besser / schlechter) | gelöst | Update 6000 |
|---|---|---|---|---|---|---|---|---|
| `freeze` | 0,52 / 0,74 / 0,32 / 0,31 / 0,38 | 0,455 | 0,93 / 0,46 / 0,87 / 0,93 / 0,81 | 0,799 | 0,627 | — | 4/10 | 0,258 |
| `p64` | 0,56 / 0,49 / 0,41 / 0,36 / 0,43 | 0,451 | 0,84 / 0,81 / 0,55 / 0,90 / 0,57 | 0,734 | 0,592 | −0,034 (5 / 5) | 3/10 | 0,266 |
| `pfull` | 0,56 / 0,46 / 0,45 / 0,38 / 0,47 | 0,463 | 0,52 / 0,53 / 0,48 / 0,52 / 0,51 | 0,515 | 0,489 | −0,138 (5 / 5) | 0/10 | 0,220 |
| `pcell` | 0,97 / 0,94 / 0,76 / 0,87 / 0,92 | 0,891 | 0,88 / 0,91 / 0,87 / 0,97 / 0,93 | 0,912 | **0,901** | **+0,274 (8 / 1)** | **9/10** | 0,165 |
| `fc2` | 0,92 / 0,91 / 0,42 / 0,40 / 0,46 | 0,622 | 0,84 / 0,83 / 0,88 / 0,85 / 0,87 | 0,854 | 0,738 | +0,111 (7 / 2) | 7/10 | 0,266 |
| `nogate` | 0,89 / 0,61 / 0,41 / 0,28 / 0,44 | 0,526 | 0,94 / 0,84 / 0,85 / 0,92 / 0,72 | 0,852 | 0,689 | +0,062 (4 / 3) | 5/10 | 0,283 |

(„besser / schlechter“: Unterschied je Seed über 0,02.) Lernkurve, `match_shift` im Mittel über 5 Seeds, bei Update
4500 / 6000 / 7500 / 9000 / 10500 / 12000:

| | layer_s | hier_s |
|---|---|---|
| Feintuning (erster Test, Seeds 0–2) | 0,63 / 0,89 / 0,96 / 0,99 / 1,00 / 1,00 (beide Gitter zusammen) | (links) |
| `freeze` | 0,03 / 0,12 / 0,24 / 0,32 / 0,43 / 0,45 | 0,14 / 0,39 / 0,63 / 0,74 / 0,80 / 0,80 |
| `pcell` | 0,00 / 0,09 / 0,42 / 0,73 / 0,87 / 0,89 | 0,00 / 0,24 / 0,67 / 0,85 / 0,91 / 0,91 |
| `fc2` | 0,04 / 0,18 / 0,41 / 0,53 / 0,60 / 0,62 | 0,14 / 0,35 / 0,64 / 0,78 / 0,85 / 0,85 |

- `freeze` Seeds 0–2 wiederholt die Werte des ersten Tests exakt (alle Stellen gleich, auch `keep_shift` und das
  eingefrorene Netz allein). Die drei Wiederholungen sind deshalb beim Abholen nicht neu angehängt worden.
- `pcell` gegen `freeze`: gelöst 9 von 10 gegen 4 von 10 (Fisher einseitig p = 0,029), je Seed 8 besser, 1
  schlechter (Vorzeichentest einseitig p = 0,020). Einziger ungelöster Lauf: layer_s Seed 2 mit 0,76.
- `pcell` startet langsamer (Update 6000: 0,165 gegen 0,258), steigt dann steiler und liegt ab Update 7500 vorn.
- `fc2` bei layer_s zerfällt in zwei Gruppen: Seeds 0/1 lösen (0,92 / 0,91), Seeds 2–4 liegen wie `freeze` bei
  0,40–0,46. Bei hier_s (nur neu gewürfelt) +0,055.
- `pfull` bei hier_s: alle fünf Läufe enden bei 0,48–0,53, keiner löst.
- `keep_shift` im Verbund bleibt in allen 60 Läufen unter 0,6 (`nogate`: 0,00 in allen 10, `pfull`: 0,13–0,55).

**Vergleich mit der Vorhersage.** (0) Getroffen: Die Wiederholung ist exakt. (1) Teilweise: `p64` −0,034
(getroffen), `pfull` −0,138 (verfehlt, schlechter statt gleich). (2) Getroffen: +0,274 und 9 von 10 gelöst.
(3) Teilweise: bei layer_s +0,167 (verfehlt, der Null-Start erklärt einen Teil), bei hier_s +0,055 (getroffen).
(4) Getroffen: +0,062. (5) Getroffen: Bei Update 6000 liegt jede Variante bei höchstens 0,283. Bilanz: 4
getroffen, 2 teilweise.

**Schluss.** (a) Der Engpass ist, dass das neue Modul nur die oberste Darstellung sieht. Liest jede neue Zelle
ihre eingefrorene Zelle, lösen beide Gitter `match_shift` (9 von 10, Mittel 0,90). Damit liegt das Andocken am
Ende fast beim Feintuning (1,00), aber weiterhin langsamer: Es braucht bis Update 9000–10500, das Feintuning bis
6000. (b) Die Breite des Ports ist es nicht: 64 Werte ändern nichts. Die ganze oberste Darstellung als Befehl
schadet hier_s sogar: alle fünf Läufe enden bei rund 0,5, keiner löst. Der Grund ist nicht geprüft; dass alle
fünf gleich hoch enden, sieht nach einem festen Teilerfolg aus. (c) Der Null-Start der zweiten Zellschicht
erklärt bei layer_s einen Teil: 2 von 5 Seeds lösen mit zufälligem Start, 3 von 5 bleiben bei `freeze`. Neu
gewürfelt streut hier_s um etwa ±0,05, der Effekt bei layer_s ist größer. (d) Das Gate ist zum Lernen nicht
nötig: Ohne Beimischung lernt das neue Modul nicht schlechter (+0,06). Den Erhalt im Verbund leistet es ohnehin
nicht; `keep_shift` geht in allen Varianten verloren, mit `nogate` ganz. Die Auswahl nach Aufgabe fehlt weiter.
(e) Für die Bibliothek heißt das: Ein Eintrag sollte nicht nur seine oberste Darstellung veröffentlichen,
sondern was jede Zelle weitergibt. Das ist bei Gittern natürlich (gleiche Form, Zelle zu Zelle), für Netze anderer
Bauart aber nicht ohne Weiteres übertragbar. (f) Offen: ob `pcell` und ein zufälliger Start von fc2 zusammen
layer_s schneller machen, und ob `pcell` auch auf der Blickschleifen-Leiter trägt.

**Belege.** `results/route.jsonl` (99 Zeilen, davon 54 aus diesem Job; Feld `plan` mit der Variante, z. B.
`keep_shift:3000 freeze:pcell match_shift:9000`). Die Wiederholungen `freeze` Seeds 0–2 stehen nur im
Job-Ergebnis auf dem Share (`results/20261121-153910-route_probe/runs.jsonl`), sie gleichen den vorhandenen
Zeilen exakt.

## 2026-11-21 — Phase C, `pcell` mit zufälligem Start von fc2: layer_s lernt schneller und sicherer, bleibt aber hinter dem Feintuning

**Frage.** Lernt layer_s beim Andocken schneller, wenn jede neue Zelle ihre eingefrorene Zelle liest (`pcell`) UND
die zweite Zellschicht des neuen Moduls zufällig startet (`fc2`)?

**Gemacht.** Jobs `20261121-191851-pcell_fc2` und `20261121-191852-route_seeds59` (Commit 58a0b68), 25 Läufe auf dem
Worker. Damit liegen für layer_s alle vier Varianten (`freeze`, `fc2`, `pcell`, `pcell+fc2`) auf Seeds 0–9 vor.
Stufe 1 ist je Seed in allen vier Varianten gleich (`frozen_final` identisch). Vorhersage vor dem Lauf (wörtlich
aus „Laufend / offen“):

> - Phase C, `pcell` zusammen mit zufälligem Start von fc2 bei layer_s (Auftrag Nutzer 2026-11-21: „prüfe pcell
>   zusammen mit fc2 bei layer_s“). Frage: Lernt layer_s mit `freeze:pcell+fc2` schneller als mit `pcell` allein?
>   Begründung der Erwartung: Bei layer_s startet fc2 bei null, die Zelle reicht anfangs nur den Restpfad durch;
>   der Befehl je Zelle wirkt erst, wenn fc2 gewachsen ist. `pcell+fc2` unterscheidet sich von `pcell` nur in fc2
>   (geprüft in `scripts/check_route.py`), Stufe 1 ist gleich, also Vergleich je Seed.
>   Plan `keep_shift:3000 freeze:pcell+fc2 match_shift:9000`, layer_s, Seeds 0–9. Dazu `freeze`, `freeze:pcell`
>   und `freeze:fc2` für Seeds 5–9 (0–4 liegen vor), also alle vier Varianten auf 10 Seeds; 25 Läufe, Worker mit
>   14 Prozessen -> `results/route.jsonl`. Gelöst = `match_shift` ≥ 0,8.
>   **Vorhersage vor dem Lauf (2026-11-21):** (1) Schneller: bei Update 7500 liegt `pcell+fc2` im Mittel
>   mindestens 0,15 über `pcell` (dort 0,42 auf Seeds 0–4) und je Seed in mindestens 7 von 10 darüber.
>   (2) Am Ende kein Schaden: Mittel innerhalb ±0,05 von `pcell` oder darüber, gelöst in mindestens 8 von 10.
>   (3) Der Befund des vorigen Eintrags wiederholt sich auf Seeds 5–9: `pcell` löst mindestens 4 von 5,
>   `freeze` höchstens 2 von 5. (4) `fc2` allein löst auf Seeds 5–9 1 bis 3 von 5 (wie 2 von 5 auf Seeds 0–4).

**Ergebnis.** layer_s, `match_shift`, Seeds 0–9:

| Variante | am Ende je Seed 0–9 | Mittel | gelöst | Update 7500 (Mittel) | Update 9000 (Mittel) |
|---|---|---|---|---|---|
| `freeze` | 0,52 0,74 0,32 0,31 0,38 0,60 0,31 0,64 0,67 0,40 | 0,490 | 0/10 | 0,25 | 0,36 |
| `fc2` | 0,92 0,91 0,42 0,40 0,46 0,91 0,58 0,70 0,92 0,36 | 0,659 | 4/10 | 0,41 | 0,55 |
| `pcell` | 0,97 0,94 0,76 0,87 0,92 0,84 0,40 0,90 0,98 0,07 | 0,765 | 7/10 | 0,33 | 0,61 |
| `pcell+fc2` | 0,97 0,95 0,91 0,93 0,96 0,86 0,91 0,97 0,99 0,00 | **0,845** | **9/10** | **0,56** | **0,77** |

- `pcell+fc2` gegen `pcell` bei Update 7500, je Seed: −0,01 / +0,02 / +0,17 / +0,43 / +0,36 / +0,57 / +0,27 /
  +0,50 / −0,03 / 0,00; im Mittel +0,23. Darüber in 7 von 10 Seeds, um mehr als 0,02 in 6.
- Erstes Update mit `match_shift` ≥ 0,8: `pcell+fc2` 6750–9500 (Median 8750, Seed 9 nie), `pcell` 6500–10750
  (3 von 10 nie). Feintuning (erster Test, Seeds 0–2): Mittel 0,89 bei Update 6000.
- Am Ende `pcell+fc2` gegen `pcell` im Mittel +0,08; größter Gewinn Seed 6 (0,40 → 0,91), größter Verlust Seed 9
  (0,07 → 0,00). Gelöst 9 gegen 7 von 10 (Fisher einseitig p = 0,29, nicht gesichert).
- Seed 9 scheitert mit beiden `pcell`-Varianten (0,07 und 0,00, die ganze zweite Stufe flach), während `freeze`
  (0,40) und `fc2` (0,36) dort lernen. Das eingefrorene Netz von Seed 9 hat `keep_shift` wie alle mit 1,00 gelernt;
  auffällig ist nur, dass sein eigener `match_shift`-Wert mit −0,14 näher an null liegt als bei den anderen
  Seeds (−0,35 bis −0,75). Beim `pcell`-Lauf von Seed 9 behält der Verbund `keep_shift` 0,60, als ob das Gate auf
  der alten Ausgabe bliebe. Beides ist nicht geprüft.
- Auf den neuen Seeds 5–9 löst `pcell` 3 von 5 (Seeds 0–4: 4 von 5), `freeze` 0 von 5, `fc2` 2 von 5.

**Vergleich mit der Vorhersage.** (1) Getroffen: +0,23 im Mittel bei Update 7500, darüber in 7 von 10 Seeds
(knapp: Seed 1 nur +0,02). (2) Getroffen: Mittel +0,08 über `pcell`, gelöst 9 von 10. (3) Teilweise: `freeze`
0 von 5 getroffen, `pcell` nur 3 von 5 statt mindestens 4. (4) Getroffen: `fc2` 2 von 5. Bilanz: 3 getroffen,
1 teilweise.

**Schluss.** (a) Beide Ursachen wirken bei layer_s zusammen: Mit beiden Änderungen lernt layer_s schneller (bei
Update 7500 im Mittel 0,56 statt 0,33) und löst 9 von 10 Seeds. Ohne Änderung löst es keinen, mit je einer 4
bzw. 7. Ob die Kombination am Ende wirklich mehr Läufe löst als `pcell` allein, ist mit 10 Seeds nicht
gesichert (p = 0,29); der Gewinn im Tempo ist deutlicher. (b) Das Feintuning bleibt schneller: Es erreicht 0,8 im
Mittel vor Update 6000, `pcell+fc2` im Median bei 8750. (c) Auf zehn Seeds ist `pcell` allein bei layer_s
schwächer als es die Seeds 0–4 nahelegten (7 von 10 statt 4 von 5 gelöst; zusammen mit hier_s im vorigen Eintrag
9 von 10). Der Kern des vorigen Befunds hält: `freeze` löst bei layer_s keinen von 10. (d) Ein Seed (9) scheitert
gerade mit dem Signal je Zelle, ohne es nicht. Ein Einzelfall, aber er zeigt, dass `pcell` auch ganz versagen
kann; der Grund ist offen.

**Belege.** `results/route.jsonl` (124 Zeilen; Plan `keep_shift:3000 freeze:pcell+fc2 match_shift:9000` und die
drei anderen Varianten für Seeds 5–9).

## 2026-11-21 — Phase C, gru-Kontrolle: Das Gate verhinderte das Lernen; ohne Gate hilft sogar ein ungelerntes eingefrorenes gru

**Frage.** Warum ergibt die gru-Kontrolle des ersten Tests (ungelerntes Netz eingefroren, dann `match_shift`)
0,00, wo gru allein 0,43 erreicht?

**Gemacht.** Job `20261121-224747-gru_nogate` (Commit 568ed77), 6 Läufe auf dem Worker. Vorhersage vor dem Lauf
(wörtlich aus „Laufend / offen“):

> - Phase C, offener Punkt (f) des ersten Tests: Warum ergibt die gru-Kontrolle (`freeze match_shift:9000`,
>   ungelerntes Netz eingefroren) 0,00, wo gru allein 0,43 erreicht? Vermutung von damals: Die zufällige Ausgabe
>   des ungelernten Netzes stört, weil das Gate sie anfangs zur Hälfte beimischt. Prüfung: dieselbe Kontrolle ohne
>   Gate (`freeze:nogate match_shift:9000`), gru, Seeds 0–2; dazu `freeze:nogate` nach Stufe 1
>   (`keep_shift:3000 freeze:nogate match_shift:9000`), gru, Seeds 0–2. 6 Läufe auf dem Worker ->
>   `results/route.jsonl`. Wiederholt zum Vergleich: nichts (Kontrolle mit Gate liegt vor: 0,00 / 0,00 / 0,00).
>   **Vorhersage vor dem Lauf (2026-11-21):** (1) Kontrolle ohne Gate: gru 0,3–0,5 in 3 von 3 (wie von null an),
>   die Vermutung trifft also zu. (2) Nach Stufe 1 ohne Gate: gru ≥ 0,9 in 3 von 3 (mit Gate 0,97).

**Ergebnis.** gru, `match_shift` am Ende, Seeds 0 / 1 / 2:

| Plan | Ergebnis |
|---|---|
| von null an (`match_shift:12000`, erster Test) | 0,44 / 0,43 / 0,42 |
| Kontrolle mit Gate (`freeze match_shift:9000`, erster Test) | 0,00 / 0,00 / 0,00 |
| **Kontrolle ohne Gate** (`freeze:nogate match_shift:9000`) | **0,00 / 0,90 / 0,85** |
| nach Stufe 1, mit Gate (erster Test) | 0,97 / 0,97 / 0,97 |
| nach Stufe 1, ohne Gate (`keep_shift:3000 freeze:nogate match_shift:9000`) | 0,97 / 0,98 / 0,98 |

- gru von null an steht schon nach 1500 Updates bei 0,36–0,39 und bleibt bei etwa 0,4.
- Die Kontrolle mit Gate bleibt in allen 3 Läufen die ganze Zeit bei 0,00.
- Ohne Gate verlassen Seeds 1 und 2 die Null nach 3000 bzw. 4500 Updates und steigen bis 0,90 / 0,85.
  Seed 0 bleibt bei 0,00.

**Vergleich mit der Vorhersage.** (1) Verfehlt in den Zahlen: Nur 2 von 3 Läufen kommen von der Null weg, und
diese liegen mit 0,85–0,90 weit über 0,3–0,5. Die Richtung trifft: Ohne Gate lernt die Kontrolle in 2 von 3
Läufen, mit Gate in keinem. (2) Getroffen: 0,97–0,98. Bilanz: 1 getroffen, 1 verfehlt.

**Schluss.** (a) Das Gate war bei der gru-Kontrolle das Hindernis. Mit Gate bleibt keiner der drei Läufe über
null, ohne Gate lernen zwei. Wie genau das Gate das neue Modul festhält, ist nicht gemessen. (b) Ein ungelerntes
eingefrorenes gru hilft dem neuen gru sogar: 0,85–0,90 gegen 0,43 von null an, in 9000 statt 12000 Updates. Ein
zufälliges rekurrentes Netz wirkt offenbar als fester Speicher (wie ein Reservoir beim esn), den das neue Modul
lesen kann. Damit ist das ungelernte eingefrorene Netz beim gru keine saubere Kontrolle für „kein Können“; bei
den Gittern war es eine (0,00 in 6 von 6 mit Gate, ohne Gate nicht gemessen). (c) Der Verbund hat doppelt so
viele Parameter wie gru allein, und das neue Modul hat einen Befehls-Port (`gru+cmd`). Welcher der drei Gründe
(Reservoir, mehr Parameter, Port) den Unterschied zu „von null an“ macht, trennt dieser Versuch nicht.
(d) Nach Stufe 1 ändert das Gate beim gru nichts (0,97 mit und ohne).

**Belege.** `results/route.jsonl` (6 neue Zeilen, Pläne mit `freeze:nogate`, Modell gru).

## 2026-11-21 — Phase C, Seed 9 mit `pcell`: kein Versagen, sondern eine sehr lange Anlaufzeit, verursacht vom eingefrorenen Netz

**Frage.** Warum lernt layer_s Seed 9 `match_shift` weder mit `pcell` (0,07) noch mit `pcell+fc2` (0,00), während
`freeze` (0,40) und `fc2` (0,36) dort lernen und die anderen Seeds mit `pcell` meist lösen?

**Gemacht.** Lokal, Skripte in `scripts/route_seed9/`, Logs in `results/route_seed9/`. Stufe 1 (`keep_shift:3000`)
für Seeds 0–9 lokal nachgerechnet, wie im Lehrplan. Sie ist nicht bitgleich zum Worker, aber nahe:
`match_shift` des eingefrorenen Netzes von Seed 9 −0,138 lokal gegen −0,137. Dann ohne Vorhersage:
(1) Größe der Zellzustände und des `pcell`-Befehls je Seed; (2) zweite Stufe mit Blick ins Innere (Gate,
Befehl, Gradienten alle 250 Updates) für Seed 9 `pcell`, Seed 9 `freeze` und Seed 8 `pcell`; (3) Tausch:
eingefrorenes Netz von Seed 9 mit Start und Trainingsfolge anderer Seeds, und umgekehrt (6000 Updates);
(4) lineare Sonden auf das gemerkte Wort aus Bild 0 während der Kandidaten-Bilder 1–3. Zuletzt ein Versuch mit
Vorhersage (wörtlich aus „Laufend / offen“):

> - Phase C, warum Seed 9 von layer_s mit `pcell` scheitert (Auftrag Nutzer 2026-11-21: „Prüfe, warum Seed 9 mit
>   pcell scheitert“). Lokale Diagnose (Stufe 1 lokal nachgerechnet; nicht bitgleich zum Worker, Unterschiede klein),
>   ohne Vorhersage gemacht: Lauf mit Blick ins Innere, Tausch eingefrorenes Netz × Start des neuen Moduls, lineare
>   Sonden auf das gemerkte Wort. Danach ein Versuch mit Vorhersage: Seed 9, `freeze:pcell`, zweite Stufe 24000
>   statt 9000 Updates (lokal, gleiches Skript wie die Diagnose).
>   **Vorhersage vor dem Lauf (2026-11-21):** Seed 9 verlässt die Hochebene (Wert ≥ 0,1) zwischen Update 6000 und
>   14000 der zweiten Stufe und erreicht am Ende mindestens 0,8.

**Ergebnis.**
- (2) Wiederholung lokal: Seed 9 `pcell` 0,00 nach 9000 Updates, Seed 9 `freeze` 0,40, Seed 8 `pcell` 0,98, wie auf
  dem Worker. In allen drei Läufen fällt das Gate innerhalb von 250 Updates auf etwa 0 (Ausgabe fast nur vom
  neuen Modul). Alle starten auf derselben Hochebene (Verlust 0,636, Wert 0, Antwort immer „nein“). Seed 8
  `pcell` und Seed 9 `freeze` verlassen sie bei Update 2000–3000; Seed 9 `pcell` nicht, seine Gradienten bleiben
  3–5 Mal kleiner.
- (3) Tausch, `pcell`, Wert nach 6000 Updates:

  | eingefrorenes Netz | Start des neuen Moduls und Trainingsfolge | Wert |
  |---|---|---|
  | Seed 9 | Seed 9 / Seed 8 / Roll 21 / Roll 22 | 0,00 / 0,00 / 0,00 / 0,00 |
  | Seed 8 | Seed 9 | 0,96 |

- (1) Größe: Die Zellzustände von Seed 9 sind etwas größer als bei den meisten Seeds (Befehl rms 0,62 gegen
  0,36–0,51), gleichauf mit Seed 3 (0,67), der mit `pcell` löst.
- (4) Sonden: Das gemerkte Wort ist bei allen geprüften Seeds aus dem ganzen Zustand fast vollständig lesbar
  (alle Zellen zusammen; Seed 9: 1,00 / 0,98 / 0,90 bei Bild 1 / 2 / 3; Seed 8: 1,00 / 0,94 / 0,78). Aus einer einzelnen Zelle liest
  man bei Seed 9 0,61–0,80 der Bits, bei den anderen Seeds 0,58–0,79. Der Anteil des Worts an der Schwankung
  einer Zelle (R²) ist bei Seed 9 mit 0,09–0,19 mit am größten (alle Seeds 0,03–0,27). Aus den 16 Startwerten
  von `pcell` ist es bei Seed 9 nicht schlechter lesbar (0,60–0,65 gegen 0,56–0,67).
  Hinweis: Eine erste Fassung der Sonden las die Zeile über dem Wort, alle Ziel-Bits waren 0. Die Werte hier
  stammen aus der korrigierten Fassung.
- Langer Lauf: Seed 9 `pcell` mit 24000 Updates in der zweiten Stufe bleibt bis Update 8000 bei 0. Bei 9000 liegt
  er bei 0,10, bei 10000 bei 0,43, bei 14000 bei 0,85 und bei 23000 bei 0,96. Der Befehl wächst schon während
  der Hochebene langsam (rms 0,62 → 1,74 bis Update 8000).

**Vergleich mit der Vorhersage.** Getroffen: Die Hochebene endet bei etwa Update 9000 (vorhergesagt 6000–14000),
der Wert am Ende ist 0,96 (≥ 0,8). Bilanz: 1 von 1 getroffen. Die Diagnose davor hatte keine Vorhersage.

**Schluss.** (a) Seed 9 versagt mit `pcell` nicht grundsätzlich, er braucht nur sehr lange, um die Hochebene zu
verlassen: etwa 9000 Updates. Bei 9000 Updates in der zweiten Stufe und abfallender Lernrate reicht die Zeit
danach nicht mehr. (b) Die lange Anlaufzeit kommt vom eingefrorenen Netz, nicht vom Zufall des neuen Moduls oder
der Trainingsfolge (Tausch: 0 von 4 gegen 1 von 1). (c) Ausgeschlossen sind: das Gate, die Größe der Zellzustände,
fehlende oder schlecht lesbare Information über das gemerkte Wort. Was am eingefrorenen Netz von Seed 9 die
Anlaufzeit verlängert, ist offen. (d) Für die Auswertung heißt das: Die Lösequoten bei festem Budget messen bei
`pcell` zum Teil das Tempo. Ein Lauf auf der Hochebene ist nicht von einem unlösbaren zu unterscheiden, ohne ihn
länger laufen zu lassen. Das gilt für die ungelösten Läufe der vorigen Einträge ebenso (z. B. `pcell` Seed 6
mit 0,40).

**Belege.** `scripts/route_seed9/` (README mit Aufrufen), `results/route_seed9/` (stage1, stats, stage2, swap,
probe_cell, probe_var, long).

## 2026-11-22 — Phase C, lange zweite Stufe: Andocken ohne Signal je Zelle löst auch, nur langsamer; `pcell` ist vor allem schneller

**Frage.** Ist `pcell` beim Andocken von layer_s besser oder nur schneller? (Folge aus dem Seed-9-Eintrag:
Lösequoten bei 9000 Updates messen zum Teil das Tempo.)

**Gemacht.** Job `20261121-230321-route_long` (Commit 2e47e9c), 40 Läufe auf dem Worker mit 14 Prozessen.
Vorhersage vor dem Lauf (wörtlich aus „Laufend / offen“):

> - Phase C, Andocken mit langer zweiter Stufe bei layer_s: Ist `pcell` besser oder nur schneller? (Folge aus dem
>   Seed-9-Eintrag: Lösequoten bei 9000 Updates messen zum Teil das Tempo.) Pläne
>   `keep_shift:3000 freeze[:fc2|:pcell|:pcell+fc2] match_shift:24000`, layer_s, Seeds 0–9, 40 Läufe auf dem
>   Worker -> `results/route.jsonl`. Hinweis: Mit mehr Updates wird auch der Kosinus-Plan der Lernrate gestreckt;
>   der Vergleich ist „mehr Zeit“, nicht „dieselbe Kurve weiter“. Gelöst = `match_shift` ≥ 0,8. Vergleich mit den
>   Läufen mit 9000 Updates (vorige Einträge).
>   **Vorhersage vor dem Lauf (2026-11-21):** (1) `pcell` und `pcell+fc2` lösen je mindestens 9 von 10.
>   (2) `freeze` bleibt deutlich zurück: gelöst höchstens 5 von 10, Mittel mindestens 0,15 unter `pcell`.
>   (3) `fc2` liegt dazwischen: gelöst 4 bis 8 von 10. (4) Jede Variante liegt im Mittel mindestens so hoch wie mit
>   9000 Updates (`freeze` 0,49, `fc2` 0,66, `pcell` 0,77, `pcell+fc2` 0,85).

Stufe 1 ist in allen 40 Läufen dieselbe wie in den Läufen mit 9000 Updates (eingefrorenes Netz gleich, je Seed
geprüft), der Vergleich ist also je Seed gepaart.

**Ergebnis.** layer_s, `match_shift` am Ende, 24000 Updates in der zweiten Stufe:

| Variante | am Ende je Seed 0–9 | Mittel | gelöst | mit 9000 Updates: Mittel / gelöst | erstes ≥ 0,8 (Median, Updates der 2. Stufe) |
|---|---|---|---|---|---|
| `freeze` | 0,99 0,99 0,98 0,98 0,93 1,00 0,68 0,97 1,00 0,59 | 0,911 | 8/10 | 0,490 / 0/10 | 9625 (2 nie) |
| `fc2` | 1,00 1,00 0,97 0,93 0,99 1,00 0,99 1,00 1,00 0,59 | 0,946 | 9/10 | 0,659 / 4/10 | 7375 (1 nie) |
| `pcell` | 1,00 1,00 0,99 1,00 1,00 0,97 0,98 0,99 1,00 0,97 | 0,989 | 10/10 | 0,765 / 7/10 | 7375 |
| `pcell+fc2` | 1,00 1,00 1,00 1,00 1,00 0,99 0,99 1,00 1,00 0,96 | **0,994** | **10/10** | 0,845 / 9/10 | **5875** |

Mittel im Verlauf (Updates der zweiten Stufe; gelöst in Klammern):

| Variante | 6000 | 9000 | 12000 | 18000 |
|---|---|---|---|---|
| `freeze` | 0,40 (0) | 0,69 (4) | 0,80 (7) | 0,89 (8) |
| `fc2` | 0,56 (3) | 0,77 (6) | 0,86 (8) | 0,94 (9) |
| `pcell` | 0,50 (2) | 0,84 (6) | 0,93 (10) | 0,98 (10) |
| `pcell+fc2` | 0,69 (5) | 0,83 (9) | 0,93 (9) | 0,99 (10) |

- `pcell` gegen `freeze` am Ende je Seed: höher in 9 von 10 Seeds, niedriger in einem (Seed 5: 0,97 gegen 1,00).
  Die großen Unterschiede liegen in den Seeds 9 (0,97 gegen 0,59), 6 (0,98 gegen 0,68) und 4 (1,00 gegen 0,93);
  in den übrigen sieben Seeds liegen beide bei 0,97–1,00. Gelöst 10 gegen 8 von 10 (Fisher einseitig p = 0,24,
  nicht gesichert).
- Seed 9 (das eingefrorene Netz mit der langen Anlaufzeit) ist mit `freeze` und `fc2` der schwächste Lauf
  (0,59 beide). Mit `pcell` kommt er auf 0,97, mit `pcell+fc2` auf 0,96, obwohl er bei `pcell+fc2` erst nach
  10000 Updates 0,1 erreicht. Bei `freeze` und `fc2` beginnt er früh (0,1 nach 4750 bzw. 5500), bleibt aber
  um 0,6.
- Erstes ≥ 0,1: `freeze` und `fc2` steigen früher an (Median 2750 bzw. 2125) als `pcell` (4500) und
  `pcell+fc2` (3750). Ohne Signal je Zelle beginnt das Lernen also früher, steigt aber langsamer.
- Die gestreckte Lernrate allein hilft: Bei Update 9000 der zweiten Stufe liegt `freeze` im langen Lauf bei
  0,69, im kurzen Lauf am Ende (auch Update 9000, Lernrate dort schon fast null) bei 0,49. Für die anderen
  Varianten ebenso (`fc2` 0,77 gegen 0,66, `pcell` 0,84 gegen 0,77, `pcell+fc2` 0,83 gegen 0,85).
- `keep_shift` des Verbunds am Ende: bei `pcell` und `pcell+fc2` 0,00–0,07, bei `freeze` und `fc2` 0,01–0,89
  (Seeds 0 und 5 von `fc2` und 5 und 8 von `freeze` behalten 0,64–0,89). Wie im ersten Test: Das Gate kennt die
  Aufgabe nicht, der Verbund verliert die alte Aufgabe; mit Signal je Zelle noch gründlicher.

**Vergleich mit der Vorhersage.** (1) Getroffen: `pcell` und `pcell+fc2` lösen je 10 von 10. (2) Verfehlt:
`freeze` löst 8 von 10 (vorhergesagt höchstens 5), Mittel 0,08 unter `pcell` (vorhergesagt mindestens 0,15).
(3) Verfehlt: `fc2` löst 9 von 10 (vorhergesagt 4 bis 8). (4) Getroffen: Alle Mittel liegen höher als mit 9000
Updates. Bilanz: 2 getroffen, 2 verfehlt.

**Schluss.** (a) Das seitliche Signal „nur oben“ ist kein Engpass, der das Lernen verhindert, sondern einer, der
es verlangsamt: Mit genug Zeit löst auch `freeze` 8 von 10 Seeds. Der Befund des Eintrags „Schwäche der
Gitter“ (`pcell` 9 von 10 gegen `freeze` 4 von 10) war zum großen Teil ein Befund über das Tempo. Ich hatte das
unterschätzt, wie die verfehlten Punkte (2) und (3) zeigen. (b) Es bleibt ein Vorteil von `pcell`, der über das
Tempo hinausgehen könnte: alle 10 Seeds gelöst, auch die zwei, die mit `freeze` bei 0,59 und 0,68 hängen bleiben
(Seeds 9 und 6). Ob diese zwei mit noch mehr Zeit ebenfalls lösen würden, ist offen; ihre Kurven steigen bis
zum Ende noch (Seed 6: 0,40 bei Update 12000, 0,61 bei 18000, 0,68 am Ende), aber langsam. Mit 10 Seeds nicht gesichert (p = 0,24).
(c) Am schnellsten ist `pcell+fc2` (0,8 im Median nach 5875 Updates). Das ist etwa so schnell wie das Feintuning
im ersten Test (0,8 im Mittel vor Update 6000), aber nicht schneller. (d) Für die Bewertung von Architekturen
heißt das: Beim Andocken müssen Lösequoten mit einer Angabe zum Budget kommen, und „nicht gelöst“ nach 9000
Updates sagt wenig. Die Zeit bis 0,8 ist das bessere Maß. (e) Die Folgerung für die Bibliothek (ein Eintrag
veröffentlicht, was jede Zelle weitergibt) bleibt sinnvoll, aber als Beschleunigung, nicht als Bedingung.

**Belege.** `results/route.jsonl` (170 Zeilen; Pläne `keep_shift:3000 freeze[:fc2|:pcell|:pcell+fc2]
match_shift:24000`, layer_s, Seeds 0–9).

## 2026-11-22 — Phase C, Blickschleifen-Leiter `cue → blind`: Andocken hilft dem Gitter, Feintuning hilft mehr; bei vitmem schadet das Andocken

**Frage.** Hilft das eingefrorene Können aus `robot_loop_cue_f32` beim Lernen von `robot_loop_blind_f32`, mit der
neuen Verdrahtung (eigene Netzhaut und eigener Adress-Encoder je Netz, Summe im Port)?

**Gemacht.** Job `20261122-080110-loop_cue_blind` (Commit 5313995), Worker mit 14 Prozessen, 397 Minuten.
Vorhersage vor dem Lauf (wörtlich aus „Laufend / offen“):

> - Phase C, zweiter Prüfstand, erste Sprosse der Blickschleifen-Leiter `cue → blind` (Auftrag Nutzer
>   2026-11-22): Hilft das eingefrorene Können aus `robot_loop_cue_f32` beim Lernen von `robot_loop_blind_f32`?
>   Verdrahtung nach Beschluss des Nutzers (Commit 7179067): jedes Netz mit eigener Netzhaut und eigenem
>   Adress-Encoder, im Port des neuen Moduls die Summe aus seitlichem und eigenem Befehl. Pläne:
>   Feintuning `robot_loop_cue_f32:12000 robot_loop_blind_f32:12000`, Mischen
>   `robot_loop_cue_f32+robot_loop_blind_f32:24000`, `robot_loop_cue_f32:12000 freeze robot_loop_blind_f32:12000`
>   und (nur Gitter) `... freeze:pcell ...`; Netze `layer_s_sp4+cell+refl+rez3` und `vitmem+refl+rez3`, Seeds 0–3
>   (statt 0–4: der Worker ist nur noch bis etwa 23 Uhr frei, 28 Läufe passen in zwei Wellen); beide Aufgaben alle
>   250 Updates gemessen. Von null an liegt vor (`results/loop_refcurve.jsonl`, `robot_loop_blind_f32:12000`,
>   Seeds 0–4): layer_s_sp4 Folgen-Wertung 0,80, `near` 0,94–0,95, erstes ≥ 0,68 nach 2750–4000 Updates (Median
>   3250); vitmem 0,65–0,70, `near` 0,77–0,87, erstes ≥ 0,68 nach 7500–9500 (einer nie). Hauptmaß: Updates der
>   zweiten Stufe bis Folgen-Wertung ≥ 0,68 und `near` von `blind` am Ende; dazu `cue` am Ende (Vergessen).
>   Worker -> `results/route_loop.jsonl`.
>   **Vorhersage vor dem Lauf (2026-11-22):** (1) Feintuning: `blind` ist nach höchstens 1000 Updates der zweiten
>   Stufe ≥ 0,68 (layer_s_sp4 4 von 4, vitmem mindestens 3 von 4); `cue` bleibt am Ende ≥ 0,68 (die Aufgaben
>   teilen das Behalten, wenig Vergessen). (2) `freeze` bei layer_s_sp4: ≥ 0,68 schneller als von null an (Median
>   höchstens 2500 Updates), `near` am Ende ≥ 0,90 in 4 von 4. (3) `freeze:pcell` bei layer_s_sp4 mindestens so
>   schnell wie `freeze` (Median nicht später) und `near` ≥ 0,90 in 4 von 4. (4) vitmem mit `freeze`: ≥ 0,68 in
>   mindestens 3 von 4, im Median schneller als von null an (unter 7500 Updates). (5) Mischen: layer_s_sp4 löst
>   beide Aufgaben (`near` ≥ 0,90 in beiden, 4 von 4).

Die Misch-Läufe (8) sind nicht gelaufen: Der Lehrplan verbietet zwei Schritt-Aufgaben in einer Phase, weil sie
sich die Symbol-Fläche teilen („use its '<name>_bits' form in this phase“). Bei `cue` und `blind` bedeutet die
Fläche dasselbe (der nächste Blickschritt), die Sperre ist hier zu streng; ich habe sie nicht geändert. Die vier
`freeze:pcell`-Läufe von vitmem brachen wie geplant sofort ab (pcell nur für Gitter). Es bleiben 20 Läufe.
„Von null an“: `robot_loop_blind_f32:12000` aus `results/loop_refcurve.jsonl`, Seeds 0–3.

**Ergebnis.** Zweite Stufe (`blind`), je Seed 0 / 1 / 2 / 3. t68 bzw. t75 = Updates der zweiten Stufe bis die
Folgen-Wertung von `blind` erstmals ≥ 0,68 bzw. ≥ 0,75 ist (gemessen alle 250); „nie“ = nicht in 12000.

| Netz, Variante | t68 | t75 | `blind` Folgen-Wertung am Ende | `near` `blind` | `cue` am Ende (Folgen / `near`) |
|---|---|---|---|---|---|
| layer_s_sp4 von null an | 4000 / 2750 / 3250 / 2750 | 5500 / 4750 / 4500 / 5250 | 0,80 / 0,80 / 0,80 / 0,80 | 0,94 / 0,95 / 0,95 / 0,95 | – |
| layer_s_sp4 Feintuning | 250 / 250 / 250 / 250 | 1000 / 1000 / 750 / 500 | 0,82 / 0,82 / 0,83 / 0,83 | **0,96 / 0,96 / 0,97 / 0,96** | 0,65–0,69 / 0,78–0,86 |
| layer_s_sp4 `freeze` | 1250 / 1250 / 750 / 500 | 3250 / 3000 / 2000 / 3750 | 0,78 / 0,78 / 0,81 / 0,78 | 0,94 / 0,94 / 0,95 / 0,94 | 0,63–0,72 / 0,75–0,87 |
| layer_s_sp4 `freeze:pcell` | 1000 / 1000 / 1000 / 750 | 3000 / 2750 / 2250 / 2000 | 0,78 / 0,80 / 0,81 / 0,80 | 0,94 / 0,95 / 0,96 / 0,95 | 0,61–0,73 / 0,73–0,88 |
| vitmem von null an | 8750 / 9500 / 7500 / 9250 | nie | 0,69 / 0,68 / 0,70 / 0,69 | 0,83 / 0,81 / 0,87 / 0,83 | – |
| vitmem Feintuning | 250 / 2750 / 2750 / 2750 | 8250 / 8500 / 8500 / 8250 | 0,76 / 0,76 / 0,75 / 0,76 | **0,92 / 0,92 / 0,92 / 0,92** | 0,71–0,75 / 0,86–0,91 |
| vitmem `freeze` | 250 / nie / nie / 3500 | nie | 0,70 / 0,67 / 0,65 / 0,68 | 0,86 / 0,79 / 0,76 / 0,84 | 0,65–0,69 / 0,76–0,84 |

- Ende der ersten Stufe (`cue` 12000 Updates): layer_s_sp4 Folgen-Wertung 0,79–0,81, vitmem 0,66–0,72. `blind`
  steht dabei schon bei 0,60–0,66 (layer_s_sp4) bzw. 0,56–0,68 (vitmem): Das `cue`-Netz kann `blind` zum Teil.
  Das eingefrorene Netz allein auf `blind` am Ende: layer_s_sp4 0,58–0,65, vitmem 0,56–0,67.
- Medianwerte layer_s_sp4: t68 von null an 3000, Feintuning 250, `freeze` 1000, `freeze:pcell` 1000; t75 4875 /
  875 / 3125 / 2500.
- Vergessen: Feintuning senkt `cue` bei layer_s_sp4 von 0,79–0,81 auf 0,65–0,69 (`near` 0,78–0,86; ein `cue`-Netz von null an
  hat 0,92–0,95). Der Verbund nach `freeze` ebenso (0,61–0,73), obwohl das eingefrorene Netz `cue` allein weiter mit
  0,77–0,80 kann: wie im ersten Test, das Gate kennt die Aufgabe nicht. Bei vitmem steigt `cue` durch das
  Feintuning sogar (0,66–0,72 → 0,71–0,75).
- Nicht gepaart: Die erste Stufe ist nicht in allen Varianten bitgleich. Bei layer_s_sp4 sind Feintuning und
  `freeze` gleich, `freeze:pcell` weicht ab (`cue` 0,79–0,80 statt 0,80–0,81); bei vitmem weichen die Seeds 2 und
  3 ab. Bei `keep_shift` waren alle Varianten gleich. Ursache nicht geprüft (Vermutung: nicht deterministische
  Rechenwege von Faltung oder Attention auf dem Worker). Die Abweichungen sind klein.

**Vergleich mit der Vorhersage.** (1) Verfehlt: layer_s_sp4 erreicht 0,68 nach 250 Updates (4 von 4), vitmem nur
in 1 von 4 nach höchstens 1000 (dreimal 2750); `cue` bleibt bei layer_s_sp4 nur in 1 von 4 ≥ 0,68. (2) Getroffen:
`freeze` Median 1000 (höchstens 2500), `near` 0,94–0,95 in 4 von 4. (3) Getroffen: `freeze:pcell` Median 1000
(nicht später), `near` 0,94–0,96 in 4 von 4. (4) Verfehlt: vitmem mit `freeze` erreicht 0,68 nur in 2 von 4.
(5) Nicht prüfbar, die Misch-Läufe sind nicht gelaufen. Bilanz: 2 getroffen, 2 verfehlt, 1 nicht prüfbar.

**Schluss.** (a) Bei layer_s_sp4 hilft das Andocken: `blind` wird schneller gelernt als von null an (t75 im
Median 3125 bzw. 2500 statt 4875) und erreicht dasselbe `near` (0,94–0,96). Es bleibt aber deutlich hinter dem
Feintuning (t75 875, `near` 0,96–0,97). `pcell` ist hier höchstens etwas schneller als `freeze`. (b) Bei vitmem
schadet das Andocken: `freeze` endet unter „von null an“ (`near` 0,76–0,86 gegen 0,81–0,87), Feintuning liegt
klar darüber (0,92 in allen vier). Ein Grund könnte sein, dass vitmem nur die oberste Darstellung seitlich
weitergeben kann (kein `pcell`), was beim ersten Prüfstand der Engpass war; das ist nicht geprüft. (c) `cue` und
`blind` sind fast dieselbe Aufgabe (das `cue`-Netz kann `blind` schon zu 0,60–0,68). Für solche Nachbarn ist
Weiterlernen derselben Gewichte der natürliche Weg; das Einfrieren lohnt sich erst, wenn die alte Aufgabe
erhalten bleiben muss, und das leistet der Verbund ohne Auswahl nach Aufgabe nicht (`cue` fällt im Verbund wie
beim Feintuning). (d) Der Vergleich „von null an“ hat halb so viele Updates insgesamt; für das Tempo der
zweiten Stufe ist er der richtige, für den Endwert nicht. (e) Offen: Mischen (Sperre im Lehrplan), und ob die
weiteren Sprossen (`two`, `three`), die mehr Neues verlangen, dem Andocken mehr Raum geben.

**Belege.** `results/route_loop.jsonl` (20 Läufe), Rohdaten mit den 12 Fehlzeilen im Ergebnisordner des Jobs
auf dem Share; „von null an“: `results/loop_refcurve.jsonl`.

## 2026-11-22 — Phase C, `cue → blind` mit Mischen: Mischen gibt beide Aufgaben ganz, als einzige Variante

**Frage.** Wie schneidet Mischen beider Aufgaben auf der ersten Sprosse der Blickschleifen-Leiter ab (die Läufe
fehlten im vorigen Eintrag wegen der Sperre im Lehrplan)?

**Gemacht.** Sperre gelockert (Commit 673f9c9: Aufgaben einer Phase, die sich die Symbol-Fläche teilen, müssen
denselben Code haben; mehrere Schritt-Aufgaben im Populations-Code sind erlaubt, `*_parts` neben einer
Schritt-Aufgabe weiter nicht; lokal beides geprüft). Job `20261122-201050-loop_mix`, Worker mit 8 Prozessen,
fertig vor 23 Uhr. Vorhersage vor dem Lauf (wörtlich aus „Laufend / offen“):

> - Phase C, Blickschleifen-Leiter `cue → blind`, die nachgeholten Misch-Läufe (Auftrag Nutzer 2026-11-22): Die
>   Sperre im Lehrplan ist gelockert: Aufgaben einer Phase, die sich die Symbol-Fläche teilen, müssen dort denselben
>   Code haben; mehrere Schritt-Aufgaben im Populations-Code sind erlaubt, eine neben einem anderen Code (z. B.
>   `*_parts`) weiter nicht. Plan `robot_loop_cue_f32+robot_loop_blind_f32:24000`, `layer_s_sp4+cell+refl+rez3`
>   und `vitmem+refl+rez3`, Seeds 0–3, 8 Läufe auf dem Worker -> `results/route_loop.jsonl`. Vergleich mit dem
>   vorigen Eintrag (Feintuning, `freeze`, von null an).
>   **Vorhersage vor dem Lauf (2026-11-22):** (1) layer_s_sp4 löst beide Aufgaben: `near` ≥ 0,90 in `cue` und
>   `blind`, 4 von 4 (Punkt 5 der vorigen Vorhersage). (2) Mischen behält `cue` besser als Feintuning und `freeze`:
>   `cue`-Folgen-Wertung am Ende ≥ 0,75 bei layer_s_sp4 in 4 von 4 (Feintuning 0,65–0,69). (3) vitmem: `near` in
>   `blind` ≥ 0,80 in mindestens 3 von 4, aber unter dem Feintuning (0,92).

**Ergebnis.** Plan `robot_loop_cue_f32+robot_loop_blind_f32:24000` (je Aufgabe 12000 Updates im Wechsel), Seeds
0 / 1 / 2 / 3. t68 = Updates insgesamt bis die Folgen-Wertung erstmals ≥ 0,68 ist.

| Netz | `cue` Folgen / `near` am Ende | `blind` Folgen / `near` am Ende | t68 (beide Aufgaben gleich) |
|---|---|---|---|
| layer_s_sp4 | 0,82 / 0,82 / 0,82 / 0,82 — 0,95–0,96 | 0,81 / 0,82 / 0,82 / 0,81 — 0,95–0,96 | 6250 / 5000 / 4500 / 5000 |
| vitmem | 0,74 / 0,74 / 0,70 / 0,73 — 0,83–0,89 | 0,74 / 0,74 / 0,70 / 0,73 — 0,83–0,89 | 13250 / 12500 / 15000 / 11000 |

Zum Vergleich aus dem vorigen Eintrag (`blind` `near` am Ende / `cue` Folgen-Wertung am Ende):
layer_s_sp4 Feintuning 0,96–0,97 / 0,65–0,69, `freeze` 0,94–0,95 / 0,63–0,72, von null an 0,94–0,95 / –;
vitmem Feintuning 0,92 / 0,71–0,75, `freeze` 0,76–0,86 / 0,65–0,69, von null an 0,81–0,87 / –.

- Die beiden Aufgaben laufen beim Mischen fast deckungsgleich (Unterschied in der Folgen-Wertung höchstens
  0,005): Das Netz lernt sie als eine Aufgabe.
- layer_s_sp4 verlässt die Hochebene nach 4500–6250 Updates insgesamt, also nach 2250–3125 je Aufgabe, so früh
  wie von null an (2750–4000). vitmem nach 11000–15000 insgesamt.

**Vergleich mit der Vorhersage.** (1) Getroffen: layer_s_sp4 `near` 0,95–0,96 in beiden Aufgaben, 4 von 4.
(2) Getroffen: `cue` 0,82 in 4 von 4 (≥ 0,75; Feintuning 0,65–0,69). (3) Getroffen: vitmem `blind` `near`
0,83–0,89 in 4 von 4, unter dem Feintuning (0,92). Bilanz: 3 von 3 getroffen.

**Schluss.** (a) Auf dieser Sprosse ist Mischen die einzige Variante, die beide Aufgaben ganz kann: layer_s_sp4
0,95–0,96 in beiden, während Feintuning und der Verbund nach `freeze` `cue` auf 0,61–0,73 verlieren. Wie im
ersten Test (Vergleichs-Leiter) gilt: Sind die alten Daten da, schlägt Mischen das Einfrieren. (b) Für eine
neue Aufgabe allein ist Feintuning etwas besser (layer_s_sp4 `blind` 0,96–0,97, vitmem 0,92 gegen 0,83–0,89 beim
Mischen), bei der Hälfte der Updates für die neue Aufgabe beim Mischen. (c) Das Andocken hat hier keinen
Vorteil, den nicht eine andere Variante besser liefert; sein Zweck (die alte Aufgabe ohne alte Daten behalten)
scheitert an der fehlenden Auswahl nach Aufgabe. Das ist der nächste Engpass von Phase C, nicht die Verdrahtung.

**Belege.** `results/route_loop.jsonl` (jetzt 28 Läufe; Plan `robot_loop_cue_f32+robot_loop_blind_f32:24000`).

## 2026-11-23 — Phase C, zweite Sprosse `blind → two`: Feintuning und Mischen tragen das Können weiter, das Andocken kaum

**Frage.** Hilft auf der zweiten Sprosse der Blickschleifen-Leiter das Können aus `blind` beim Lernen von `two`
(zwei Ziele behalten und nacheinander ansteuern), und wie schneiden Feintuning, `freeze`, `freeze:pcell` und
Mischen ab?

**Gemacht.** Job `20261122-225827-loop_blind_two` (Commit d974235), Worker, eine Welle mit 14 Läufen (die zwei
vitmem-`pcell`-Läufe brechen wie gewollt vor dem Training ab, vitmem hat kein `pcell`). Vorhersage vor dem Lauf
(wörtlich aus „Laufend / offen“):

> - Phase C, Blickschleifen-Leiter, zweite Sprosse `blind → two` (Leiter beschlossen 2026-11-21, Nutzer erlaubte
>   2026-11-22 ohne Rückfrage weiterzumachen): `two` verlangt mehr Neues (zwei Ziele behalten und nacheinander
>   ansteuern); hilft dort das Können aus `blind`, und wie schneiden die Varianten ab? Pläne Feintuning
>   `robot_loop_blind_f32:12000 robot_loop_two_f32:12000`, `... freeze ...`, `... freeze:pcell ...` (nur Gitter),
>   Mischen `robot_loop_blind_f32+robot_loop_two_f32:24000`; `layer_s_sp4+cell+refl+rez3` und `vitmem+refl+rez3`,
>   Seeds 0–1 (14 Läufe = eine Welle, der Worker ist bis 7 Uhr frei); beide Aufgaben alle 250 Updates. Von null an
>   liegt vor (`results/loop_refcurve.jsonl`, `robot_loop_two_f32:12000`, Seeds 0–2): layer_s_sp4 Folgen-Wertung
>   0,69–0,71, `near` 0,89–0,91, erstes ≥ 0,68 nach 7000–7250 Updates; vitmem 0,56–0,62, `near` 0,70–0,80, nie
>   ≥ 0,65. Worker -> `results/route_loop.jsonl`.
>   **Vorhersage vor dem Lauf (2026-11-22):** (1) layer_s_sp4 Feintuning: `two` ≥ 0,68 nach höchstens 3500 Updates
>   der zweiten Stufe und `near` am Ende ≥ 0,89, je 2 von 2. (2) layer_s_sp4 `freeze` und `freeze:pcell`: `two`
>   ≥ 0,68 früher als von null an (vor 7000) und `near` ≥ 0,85, je 2 von 2. (3) vitmem: Mit Feintuning erreicht
>   `two` ≥ 0,65 in 2 von 2 (von null an nie); mit `freeze` in höchstens 1 von 2. (4) Mischen bei layer_s_sp4:
>   `blind` bleibt am Ende ≥ 0,75 und `two` `near` ≥ 0,85, je 2 von 2; nach Feintuning liegt `blind` am Ende unter
>   0,75 (2 von 2).

**Ergebnis.** Seeds 0 / 1. Erste Stufe (`blind`, 12000 Updates) am Ende (Update 11750): layer_s_sp4 `blind`
0,80 / 0,80, vitmem 0,71 / 0,69; `two` können die Netze dann noch nicht (0,30–0,38). t68 = Updates der zweiten
Stufe bis die Folgen-Wertung in `two` erstmals ≥ 0,68 ist (beim Mischen: Updates insgesamt, die Hälfte davon
für `two`).

| Netz, Variante | `two` Folgen am Ende | `two` `near` | t65 (Seed 0 / 1) — t68 (Seed 0 / 1) | `blind` Folgen am Ende (Verbund) | eingefroren allein `blind` |
|---|---|---|---|---|---|
| layer_s_sp4 Feintuning | 0,74 / 0,73 | 0,92 / 0,92 | 1000 / 2000 — 2250 / 4000 | 0,55 / 0,56 | – |
| layer_s_sp4 `freeze` | 0,69 / 0,69 | 0,89 / 0,90 | 4500 / 5250 — 6750 / 7500 | 0,39 / 0,44 | 0,80 / 0,80 |
| layer_s_sp4 `freeze:pcell` | 0,70 / 0,70 | 0,91 / 0,91 | 4000 / 4250 — 5000 / 7500 | 0,55 / 0,51 | 0,80 / 0,80 |
| layer_s_sp4 Mischen (24000) | 0,74 / 0,74 | 0,92 / 0,93 | 7250 / 6250 — 9500 / 9000 insgesamt | 0,82 / 0,83 (`near` 0,96 / 0,97) | – |
| layer_s_sp4 von null an (Seeds 0–2) | 0,69–0,71 | 0,89–0,91 | – / 7000–7250 | – | – |
| vitmem Feintuning | 0,69 / 0,68 | 0,91 / 0,90 | 5750 / 6250 — 7750 / 8000 | 0,63 / 0,69 | – |
| vitmem `freeze` | 0,59 / 0,59 | 0,80 / 0,78 | nie | 0,39 / 0,34 | 0,69 / 0,68 |
| vitmem Mischen (24000) | 0,64 / 0,58 | 0,82 / 0,70 | nie | 0,72 / 0,66 | – |
| vitmem von null an (Seeds 0–2) | 0,56–0,62 | 0,70–0,80 | nie | – | – |

- Feintuning: Das Können aus `blind` trägt bei beiden Netzen. layer_s_sp4 erreicht 0,68 nach 2250 / 4000
  statt 7000–7250 Updates und endet höher (0,73–0,74 gegen 0,69–0,71). vitmem schafft `two` erstmals (≥ 0,65 in
  2 von 2, `near` 0,90–0,91 gegen 0,70–0,80 von null an). `blind` geht dabei zum Teil verloren (layer_s_sp4
  0,80 → 0,55–0,56).
- `freeze`: bei layer_s_sp4 etwa so schnell und so gut wie von null an; `pcell` etwas schneller (einmal 5000).
  Bei vitmem besser als von null an, aber klar unter dem Feintuning. Der Verbund verliert `blind` stärker als
  das Feintuning (0,34–0,55); das eingefrorene Netz allein kann es unverändert.
- Mischen: layer_s_sp4 hat beide Aufgaben (`two` so gut wie Feintuning, `blind` sogar über dem Stand von `blind` allein
  nach 12000 Updates, 0,80). vitmem lernt `two` beim Mischen langsamer (nie ≥ 0,65).

**Vergleich mit der Vorhersage.** (1) Verfehlt: `near` 0,92 in 2 von 2, aber t68 2250 und 4000, nur einer
unter 3500. (2) Verfehlt: `freeze` t68 6750 / 7500, `pcell` 5000 / 7500, je nur einer vor 7000 (`near`
0,89–0,91 erfüllt). (3) Getroffen: vitmem Feintuning ≥ 0,65 in 2 von 2, `freeze` in 0 von 2. (4) Getroffen:
Mischen `blind` 0,82 / 0,83, `two` `near` 0,92 / 0,93; nach Feintuning `blind` 0,55 / 0,56. Bilanz: 2 getroffen,
2 verfehlt.

**Schluss.** (a) Auf dieser Sprosse verlangt die neue Aufgabe mehr Neues, und das Vorwissen hilft deutlich, aber
über das Weiterlernen derselben Gewichte: Feintuning halbiert bei layer_s_sp4 die Zeit bis 0,68 und hebt vitmem
erstmals über die Schwelle. (b) Das Andocken nutzt das eingefrorene Können kaum: layer_s_sp4 so schnell wie von
null an, mit `pcell` etwas schneller; bei vitmem hilft es etwas, aber weniger als Feintuning. Die Vermutung
der vorigen Einträge, dass Andocken mehr Raum bekommt, wenn die Aufgabe mehr Neues verlangt, ist hier nicht
bestätigt (zwei Seeds). (c) Wie auf der ersten Sprosse ist Mischen bei layer_s_sp4 die einzige Variante mit
beiden Aufgaben ganz; bei vitmem kostet es auf `two` Tempo. (d) Damit bleibt der Befund: Ohne Auswahl nach
Aufgabe hat der Verbund keinen eigenen Vorteil, er verliert die alte Aufgabe sogar stärker als Feintuning
(Gate mischt beide Ausgänge). Nur zwei Seeds; die Zeiten streuen stark (layer_s_sp4 Feintuning 2250 / 4000).

**Belege.** `results/route_loop.jsonl` (jetzt 42 Läufe; die 14 neuen mit `robot_loop_two_f32` im Plan), Rohdaten
mit den 2 Fehlzeilen im Ergebnisordner des Jobs auf dem Share; „von null an“: `results/loop_refcurve.jsonl`.

## 2026-11-23 — Vorarbeit Phase D: `prev` mit 64 Beispielen ist die Aufgabe „Kopf reicht nicht“, grün / blau scheidet aus

**Frage.** Welche schnelle Aufgabe trennt für layer_s@25k die Regeln so, wie Phase D es braucht: Schreiben am
Kopf scheitert (`rls_rf`), `dfa` im Inneren ist schwach, Backprop auf schnelle Gewichte im Inneren (`grad`)
löst sie? (Review Gemini 2026-11-23, Vorarbeit 2; schon in der AGENDA aus dem Review agy 2026-11-21.)

**Gemacht.** Probe grün / blau (`adapt.py` Fälle `robot_green` / `robot_blue`, Commit a592bbe), dann
`fastweights inner` lokal auf `prev` und `plus1` (numseq, Eingaben wie die Basis, nur die Ausgabe neu; k = 64
/ 512 Trainingsbeispiele, 200 Updates, 2 Varianten je Lauf, 144 Läufe, 20 Minuten mit 4 Prozessen), Regeln ohne
Gate. Vorhersage vor dem Lauf (wörtlich aus „Laufend / offen“):

> - Vorarbeit für Phase D (Auftrag Nutzer 2026-11-23, nach Review Gemini): eine Aufgabe, bei der Schreiben am
>   Kopf scheitert (`rls_rf`), `dfa` im Inneren schwach ist und Backprop auf schnelle Gewichte im Inneren (`grad`)
>   sie löst, für layer_s@25k (ES auf der CPU). Erster Kandidat grün / blau auf den Roboter-Bildern
>   (`adapt.py` Fälle `robot_green` / `robot_blue`, Basis = die gepinnten Bit-Netze `robot_gaze`) als Probe ohne
>   Vorhersage gemessen (layer_s, Seed 0, bis 2000 Updates, `results/` nicht, Probe im Scratch): mit 64 / 512
>   Beispielen lernt KEINE Regel, auch volles Feintuning nicht (exakt 0,01–0,03); scheidet aus. Jetzt die
>   vorhandenen Fälle mit innerer Änderung `prev` und `plus1` (numseq, k = 64 / 512, 200 Updates), Regeln
>   `delta_head`, `rls_head`, `rls_rf`, `dfa`, `grad`, `adam`, Netze layer_s und layer_s@25k, Seeds 0–2, lokal
>   -> `results/phase_d_pre.jsonl`. Bisher (results/fastinner.jsonl, layer_s, mit Orakel-Gate, s20 / s200):
>   `prev` k = 64 Kopf 0,02 / 0,12, `dfa` 0,25 / 0,78, `grad` 0,87 / 0,96; `plus1` k = 64 Kopf 0,32 / 0,39,
>   `dfa` 0,01 / 0,01, `grad` 0,16 / 0,18.
>   **Vorhersage vor dem Lauf (2026-11-23):** (1) `prev`, k = 64, layer_s: `rls_rf` nach 200 Updates < 0,5,
>   `grad` ≥ 0,9, `dfa` bei s20 mindestens 0,4 unter `grad` (Mittel über Seeds). (2) layer_s@25k zeigt dasselbe
>   Muster (`rls_rf` < 0,5, `grad` ≥ 0,8, `dfa` bei s20 klar unter `grad`); dann ist `prev` k = 64 der
>   Kandidat. (3) `plus1` taugt nicht: `grad` < 0,5 bei k = 64, oder der Kopf (`rls_rf`) erreicht ≥ `grad`.

**Ergebnis.** Testwertung (exakt, ungesehene Folgen) nach 20 / 200 Updates, Mittel über Seeds 0–2 × 2 Varianten
(Spanne der 6 Läufe bei s200):

| Fall, k | Netz | `delta_head` | `rls_head` | `rls_rf` | `dfa` | `grad` innen | `adam` (ganzes Netz) |
|---|---|---|---|---|---|---|---|
| `prev`, 64 | layer_s | 0,02 / 0,12 | 0,21 / 0,21 | 0,21 / 0,21 (0,14–0,26) | 0,11 / 0,56 (0,38–0,68) | 0,84 / 0,95 (0,92–0,98) | 0,81 / 0,95 |
| `prev`, 64 | layer_s@25k | 0,05 / 0,13 | 0,20 / 0,20 | 0,21 / 0,21 (0,14–0,25) | 0,07 / 0,56 (0,34–0,79) | 0,78 / 0,94 (0,90–0,99) | 0,78 / 0,98 |
| `prev`, 512 | layer_s | 0,08 / 0,72 | 0,91 / 0,82 | 0,93 / 0,92 | 0,20 / 0,88 | 1,00 / 1,00 | 1,00 / 1,00 |
| `prev`, 512 | layer_s@25k | 0,18 / 0,66 | 0,85 / 0,84 | 0,80 / 0,77 | 0,16 / 0,85 | 0,99 / 1,00 | 0,99 / 1,00 |
| `plus1`, 64 | layer_s | 0,33 / 0,45 | 0,42 / 0,42 | 0,44 / 0,44 | 0,03 / 0,02 | 0,17 / 0,17 | 0,28 / 0,32 |
| `plus1`, 64 | layer_s@25k | 0,34 / 0,32 | 0,18 / 0,17 | 0,25 / 0,25 | 0,01 / 0,01 | 0,19 / 0,20 | 0,29 / 0,28 |
| `plus1`, 512 | layer_s | 0,39 / 0,66 | 0,55 / 0,43 | 0,68 / 0,66 | 0,09 / 0,07 | 0,60 / 0,72 | 0,66 / 0,81 |
| `plus1`, 512 | layer_s@25k | 0,41 / 0,48 | 0,43 / 0,40 | 0,49 / 0,45 | 0,01 / 0,03 | 0,48 / 0,62 | 0,53 / 0,65 |

- Grün / blau (Probe, layer_s, Seed 0, k = 64 / 512, bis 2000 Updates): keine Regel lernt es, auch volles
  Feintuning nicht (exakt 0,01–0,03). Das Basisnetz trägt die Lage des roten Würfels; die der anderen neu zu
  lernen braucht viel mehr Daten (von null an mit Ziel-Eingang 6000 Updates zu 64 Bildern für grün 0,40).
  Gemessen in Bits (gepinnte Basisnetze `robot_gaze`, alter Code).
- `prev`, k = 64: Die Kopf-Regeln passen die 64 Beispiele an, verallgemeinern aber nicht (0,21); mit k = 512
  reicht der Kopf (`rls_rf` 0,77–0,92). Die Trennung gilt also nur bei wenigen Beispielen.
- Zeit (layer_s@25k, `prev`, k = 64, je Lauf mit 2 Varianten und Auswertungen): `grad` 20 s für 200 Updates,
  `dfa` 5 s. Eine Episode von 20 Updates (`grad` dort schon 0,78) kostet etwa 1 s.
- Die Spalte „Vergessen“ ist hier ohne Bedeutung (schnelle Gewichte ohne Gate wirken auch auf die Basis).

**Vergleich mit der Vorhersage.** (1) Getroffen: `rls_rf` 0,21, `grad` 0,95, `dfa` bei s20 0,73 unter `grad`.
(2) Getroffen: layer_s@25k `rls_rf` 0,21, `grad` 0,94, `dfa` s20 0,07 gegen 0,78. (3) Getroffen: `plus1` `grad`
0,17–0,20 bei k = 64, der Kopf ist dort so gut oder besser. Bilanz: 3 von 3 getroffen (die Probe grün / blau lief
ohne Vorhersage).

**Schluss.** (a) Kandidat für Phase D: `prev` mit k = 64 auf layer_s@25k. Kopf 0,21, `dfa` 0,07 nach 20 / 0,56
nach 200 Updates, `grad` 0,78 / 0,94. Ein gelernter Teacher hat damit eine klare Messlatte: zwischen `dfa` (lokal)
und `grad` (Backprop), mit Episoden von etwa 1 s. (b) Die Lücke zu `dfa` ist vor allem Tempo (bei 200 Updates
erreicht `dfa` 0,34–0,79), die Lücke zum Kopf ist Verallgemeinerung bei wenigen Beispielen. (c) Grün / blau ist
keine Aufgabe für schnelles Anpassen; „anderes Ziel“ gehört in den Ziel-Eingang (wie 2026-11-10 gefunden), nicht
in schnelle Gewichte. (d) numseq ist keine Schritt-Aufgabe, `prev` liegt also schon im heutigen Code; die
Umstellung der Anpassungs-Studien auf den Populations-Code (Vorarbeit 1) betrifft servo und robot.

**Belege.** `results/phase_d_pre.jsonl` (144 Läufe), Zusammenfassung `python -m netresearch.fastweights summary
--file results/phase_d_pre.jsonl`; Vergleich mit Orakel-Gate: `results/fastinner.jsonl`.

## 2026-11-23 — Phase C, Auswahl nach Aufgabe (`freeze:sel`): die alte Aufgabe bleibt ganz, aber nur wo sich die Eingaben unterscheiden

**Frage.** Kann der Verbund aus eingefrorenem Netz und neuem Modul die alte Aufgabe behalten, wenn er selbst
erkennt, welche Aufgabe gerade läuft (Statistik der eigenen Aufgabe im Eintrag, keine alten Daten danach), ohne
die neue Aufgabe schlechter zu lernen?

**Gemacht.** Job `20261123-073442-loop_select` (Commit 66a9638), Worker, 12 Läufe. Danach lokal die
Aufschlüsselung je Schritt für layer_s_sp4 Seed 0 (das `blind`-Netz neu trainiert, Wertung 0,7971 wie im Job;
Skript im Scratchpad, nur das eingefrorene Netz und die Statistik entscheiden die Auswahl). Der zweite lokale
Versuch mit beiden Netzen zugleich wurde wegen Speichermangel abgebrochen; vitmem ist nicht aufgeschlüsselt.
Vorhersage vor dem Lauf (wörtlich aus „Laufend / offen“):

> - Phase C, Auswahl nach Aufgabe (`freeze:sel`, Auftrag Nutzer 2026-11-23): Beim Einfrieren legt der Eintrag eine
>   Statistik seiner eigenen Aufgabe ab (Mittelwert und Kovarianz der obersten Darstellung über 4096 Episoden der
>   Phase davor; keine alten Daten danach). Der Verbund führt je Episode den mittleren Mahalanobis-Abstand dazu mit;
>   bleibt er unter dem 99-%-Quantil der alten Aufgabe (je Schrittzahl), gibt er die Ausgabe des eingefrorenen Netzes
>   allein weiter, sonst die des Verbunds. Hart, ohne Gradient, nach dem Einfrieren fest. Pläne `cue → freeze:sel →
>   blind`, `cue → freeze:pcell+sel → blind`, `blind → freeze:sel → two`, `blind → freeze:pcell+sel → two` (je
>   12000 + 12000), `layer_s_sp4+cell+refl+rez3` und `vitmem+refl+rez3` (vitmem ohne `pcell`), Seeds 0–1, 12 Läufe,
>   Worker mit 6 Prozessen -> `results/route_loop.jsonl`. Neu in der Zeile: `selected` = Anteil der gewerteten
>   Schritte je Aufgabe, die das eingefrorene Netz allein beantwortet. Ohne `sel` bitgleich zum alten Code (geprüft).
>   Kurztest (300 + 200 Updates): alte Aufgabe 0,99 beim eingefrorenen Netz, neue 0,00. Obergrenze aus den
>   vorhandenen `freeze`-Läufen (alte Aufgabe = eingefrorenes Netz allein): layer_s_sp4 `cue → blind` 0,77–0,80 /
>   0,78–0,81, `blind → two` 0,80 / 0,69–0,70; Mischen 0,82 / 0,81–0,82 und 0,82–0,83 / 0,74.
>   **Vorhersage vor dem Lauf (2026-11-23):** (1) Die Auswahl trifft: Anteil beim eingefrorenen Netz ≥ 0,95 auf der
>   alten und ≤ 0,05 auf der neuen Aufgabe, in allen 12 Läufen. (2) Die alte Aufgabe bleibt: Folgen-Wertung des
>   Verbunds auf ihr höchstens 0,02 unter der des eingefrorenen Netzes allein, in allen 12 Läufen (ohne Auswahl
>   layer_s_sp4 0,61–0,73 auf `cue`, 0,39–0,55 auf `blind`). (3) Die neue Aufgabe leidet nicht: Folgen-Wertung am
>   Ende höchstens 0,03 unter dem `freeze`-Lauf ohne Auswahl desselben Netzes und Seeds, in mindestens 10 von 12.
>   (4) Mischen bleibt bei layer_s_sp4 auf `blind → two` in der neuen Aufgabe besser (um ≥ 0,03, 2 von 2 je
>   Variante); die Auswahl macht den Verbund also gleich gut im Behalten, nicht besser im Lernen.

**Ergebnis.** Seeds 0 / 1, Folgen-Wertung am Ende. „Anteil alt“ = `selected`, Anteil der gewerteten Schritte,
die das eingefrorene Netz allein beantwortet. Vergleich = derselbe Plan ohne `sel` (`freeze` bzw. `freeze:pcell`).

| Plan, Netz, Variante | Anteil alt auf alter / neuer Aufgabe | alte Aufgabe: Verbund (eingefroren allein) | alte Aufgabe ohne `sel` | neue Aufgabe mit `sel` | neue Aufgabe ohne `sel` |
|---|---|---|---|---|---|
| `cue → blind`, layer_s_sp4 `sel` | 0,98 / 0,98 — 0,23 / 0,15 | 0,779 / 0,781 (0,781 / 0,783) | 0,63 / 0,68 | 0,775 / 0,778 | 0,779 / 0,781 |
| `cue → blind`, layer_s_sp4 `pcell+sel` | 0,98 / 0,98 — 0,23 / 0,15 | 0,780 / 0,781 | 0,61 / 0,65 | 0,785 / 0,784 | 0,785 / 0,799 |
| `cue → blind`, vitmem `sel` | 0,99 / 0,99 — 0,92 / 0,26 | 0,707 / 0,649 (0,707 / 0,650) | 0,69 / 0,65 | 0,678 / 0,665 | 0,698 / 0,666 |
| `blind → two`, layer_s_sp4 `sel` | 0,99 / 0,98 — 0,28 / 0,17 | 0,794 / 0,793 (0,797 / 0,795) | 0,39 / 0,44 | 0,550 / 0,607 | 0,693 / 0,689 |
| `blind → two`, layer_s_sp4 `pcell+sel` | 0,99 / 0,98 — 0,28 / 0,17 | 0,794 / 0,792 | 0,55 / 0,51 | 0,562 / 0,616 | 0,696 / 0,699 |
| `blind → two`, vitmem `sel` | 0,99 / 0,99 — 0,97 / 0,99 | 0,690 / 0,670 (0,693 / 0,671) | 0,39 / 0,34 | 0,275 / 0,338 | 0,588 / 0,588 |
| Mischen layer_s_sp4 (`cue+blind` / `blind+two`) | – | `cue` 0,82 / 0,82, `blind` 0,82 / 0,83 | – | `blind` 0,81 / 0,82, `two` 0,74 / 0,74 | – |

- Die alte Aufgabe bleibt in allen 12 Läufen so gut wie beim eingefrorenen Netz allein (höchstens 0,004
  darunter). Ohne Auswahl verlor der Verbund dort 0,1–0,4.
- `cue` als dritte, nie trainierte Aufgabe (Eingabe schon in Schritt 0 anders) erkennt die `blind`-Statistik
  bei layer_s_sp4 als fremd (Anteil alt 0,02 / 0,02), bei vitmem nicht (0,26 / 0,12).
- Auf `blind → two` kostet die Auswahl die neue Aufgabe viel: layer_s_sp4 0,55–0,62 statt 0,69–0,70, vitmem
  0,27–0,34 statt 0,59. Bei vitmem hält die Statistik `two` fast immer für `blind` (0,97–0,99); bei `cue → blind`
  in einem der zwei Seeds `blind` für `cue` (0,92), ohne großen Schaden, weil das eingefrorene `cue`-Netz `blind`
  dort schon fast kann (0,67).
- Aufschlüsselung je Schritt, layer_s_sp4 Seed 0, `blind`-Statistik (eine `blind`-Episode hat 5 Schritte, eine
  `two`-Episode 8; gewertet ab Schritt 1 bzw. 2). Anteil alt je Schritt:

  | Schritt | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 |
  |---|---|---|---|---|---|---|---|---|
  | `blind` (alt) | 0,99 | 0,98 | 0,99 | 0,99 | 0,99 | – | – | – |
  | `two` (neu) | 0,99 | 0,06 | 0,03 | 0,09 | 0,29 | 0,47 | 0,36 | 0,25 |
  | `cue` (nie trainiert) | 0,00 | 0,00 | 0,00 | 0,01 | 0,05 | – | – | – |

  Schritt 0 ist bei `blind` und `two` gleich (gleiche Eingabe), danach trennt die Statistik gut. Ab Schritt 4
  hält sie `two` wieder für vertraut: Der laufende Mittelwert sinkt, die oberste Darstellung des eingefrorenen
  Netzes kommt in den späten `two`-Schritten also wieder in die Nähe der `blind`-Zustände. Ab Schritt 5 gilt
  außerdem die Schwelle von Schritt 5 weiter (die alte Aufgabe hat keine längeren Episoden). Über alle
  gewerteten Schritte 0,25 (im Job für dasselbe Netz 0,28; das neu trainierte Netz hat dieselbe Wertung, die
  Abweichung ist nicht geklärt).

**Vergleich mit der Vorhersage.** (1) Verfehlt: Auf der alten Aufgabe ≥ 0,95 in 12 von 12 (0,98–0,99), auf der
neuen ≤ 0,05 in 0 von 12 (0,15–0,99). (2) Getroffen: 12 von 12, höchstens 0,004 unter dem eingefrorenen Netz.
(3) Verfehlt: 6 von 12 (alle 6 bei `cue → blind`, keiner bei `blind → two`, dort 0,08–0,31 darunter).
(4) Getroffen: Mischen `two` 0,74 gegen 0,55 / 0,61 (`sel`) und 0,56 / 0,62 (`pcell+sel`). Bilanz: 2
getroffen, 2 verfehlt.

**Schluss.** (a) Erstmals behält ein Verbund die alte Aufgabe ganz, ohne alte Daten: Die Statistik der eigenen
Aufgabe im Eintrag reicht dafür. Das Behalten war die Lücke der vorigen Einträge. (b) Die Auswahl über
Vertrautheit der Eingabe trennt aber nur Aufgaben, deren Darstellung sich unterscheidet. Bei `cue → blind`
(Eingabe ab Schritt 0 anders) geht das mit kleinem Schaden; bei `blind → two` (gleicher Anfang, späte Zustände
ähnlich) schickt sie gerade die späten `two`-Schritte zum alten Netz, und die neue Aufgabe leidet stark. Das
bestätigt den Hinweis aus dem Review Gemini 2026-11-23 (späte Schritte). Aufgaben mit gleicher Eingabe brauchen
eine Auswahl nach Fehler (welcher Eintrag sagt gerade richtig voraus, wie in `slots.py`), nicht nach Eingabe.
(c) Bei vitmem trennt die Statistik schlechter (auch `cue` nur teilweise fremd); die oberste Darstellung von
vitmem trägt weniger Aufgabenwissen. (d) Mischen bleibt die beste Variante, wenn alte Daten da sind. (e) Wie mit
dem Nutzer nach dem Review Gemini vereinbart, schließt dieser Lauf Phase C: keine weiteren Varianten von
`route.py`, kein `two → three`. Weiter mit Phase D. Nur zwei Seeds; Aufschlüsselung je Schritt nur für ein Netz.

**Belege.** `results/route_loop.jsonl` (jetzt 54 Läufe; die 12 neuen mit `freeze:sel` bzw. `freeze:pcell+sel`
im Plan, Feld `selected`). Aufschlüsselung je Schritt: lokales `blind`-Netz (Checkpoint `selprobe_blind`, nicht
im Repo), Auswertung wie `route.selection_share`, aber je Schritt.

## 2026-11-23 — Vorarbeit 1 Phase D: Anpassungs-Studien im Populations-Code; die Kopf-Regel rls_rf löst jede servo-Kalibrierung mit einem Update, grün / blau bleibt unlernbar

**Frage.** Wie schneiden die schnellen Regeln und die Bibliothek ab, wenn die servo- und robot-Fälle den Schritt
wie ihre Basis-Aufgaben im Populations-Code ausgeben statt in 8 Bits? Liegt die Grenze „Rechnen auf dem
Ausgabe-Code“ (Phase B) am Bit-Code?

**Gemacht.** Umbau Commit 2debc26 (bitgleich für die Bit-Fälle, geprüft), Startnetze Job
`20261123-164358-pop_base_nets` festgelegt in Commit 068a1f5, dann Job `20261123-165540-pop_fastinner` (320
Läufe, `fastweights inner`) und Job `20261123-165541-pop_library` (108 Läufe, Bibliothek), Worker, Commit
f58517e. Vorhersage vor dem Lauf (wörtlich aus „Laufend / offen“; Job 1 war beim Schreiben schon gestartet, ohne
gesehenes Ergebnis):

> - Vorarbeit 1 für Phase D: Anpassungs-Studien auf den Populations-Code (Auftrag Nutzer 2026-11-23, Review
>   Gemini / agy). Die Schritt-Aufgaben rechnen seit 2026-11-14 im Populations-Code, die Anpassungs-Studien
>   (`fastinner_servo`, Bibliothek Suiten servo / robot) noch in Bits auf Bit-Startnetzen. Umbau (bitgleich für
>   die Bit-Fälle, geprüft an einer alten `fastinner_servo`-Zeile): Fälle `servo_<Gerät>`, `robot_green / blue`
>   und Suiten `servo`, `robot` geben den Schritt jetzt im Populations-Code (Breite 0,5, 32 Ausgänge), Wertung
>   stärkste Einheit je Achse; die alten heißen `<Fall>_bits`, Suiten `servo_bits`, `robot_bits`; Bit-Startnetze
>   nach `data/base_nets/servo_bits`, `robot_gaze_bits`. Job 1 (`20261123-164358-pop_base_nets`, schon gestartet,
>   noch kein Ergebnis gesehen): neue Startnetze `servo`, `robot_gaze`, layer_s / hier_s / layer_s_sp4, Seeds 0–2,
>   5, 6, je 6000 Updates, werden danach in `data/base_nets` festgelegt. Job 2: `fastweights inner` auf den sechs
>   servo-Geräten und `robot_green / blue` (layer_s, hier_s, Seeds 5–6, k = 64 / 512, Regeln adam, grad@task,
>   dfa@task, delta_head@task, rls_rf@task) -> `results/fastinner_servo_pop.jsonl`; Bibliothek Suiten servo und
>   robot (layer_s, hier_s, layer_s_sp4, Seeds 0–2, Regeln delta_head, rls_head, rls_rf, Modi k6cfne und oracle)
>   -> `results/library_pop.jsonl`. Bezug in Bits: PLAN_TRAINER Phase B (servo k = 512 nach 200 Updates: delta_head
>   0,50–0,61 bei flipx, offx, rot90, strong, 0,93–0,94 bei swap, weak; dfa ≤ 0,10; Adam 0,12–0,67; Bibliothek
>   servo delta_head 0,63 / Orakel 0,65, rls_rf 0,91 / 0,94; robot Kalibrierungen rls_rf 0,91 / 0,96, grün / blau
>   0,00–0,01).
>   **Vorhersage vor dem Lauf (2026-11-23):** (1) Startnetze: `servo` ≥ 0,97 und `robot_gaze` ≥ 0,93 bei
>   mindestens 28 der 30 Netze. (2) Im Populations-Code sind alle sechs Geräte eine lineare Umordnung der Ausgänge
>   (Spiegeln, Verschieben, Tauschen, Stauchen); deshalb erreicht delta_head@task bei k = 512 nach 200 Updates auf
>   jedem Gerät ≥ 0,85 (Mittel über Netze und Seeds) und rls_rf@task ≥ 0,90. (3) dfa@task bleibt auf jedem Gerät
>   unter delta_head@task. (4) Adam (alles) bei k = 512 erreicht auf jedem Gerät ≥ 0,70. (5) grün / blau bleibt
>   unlernbar: alle Regeln einschließlich Adam ≤ 0,10 bei k = 512. (6) Bibliothek servo: delta_head ≥ 0,85 und
>   rls_rf ≥ 0,93 im zweiten Besuch, Abstand zum Orakel ≤ 0,03; robot Kalibrierungen rls_rf ≥ 0,91, grün / blau
>   ≤ 0,02.

**Ergebnis.**
- Startnetze (30): `servo` 1,00 (hier_s 0,9995), `robot_gaze` layer_s / layer_s_sp4 0,98–0,99, hier_s 0,95–0,97.
- `fastweights inner`, k = 512, 200 Updates, ungesehene Situationen, Mittel über layer_s / hier_s, Seeds 5–6
  und je 2 Varianten (in Klammern: Bits, `results/fastinner_servo.jsonl`, gleiche Netze und Seeds, aber
  Bit-Startnetze):

| Gerät | Adam (alles) | grad@task | dfa@task | delta_head@task | rls_rf@task nach 200 / 1 Update (neu, ohne Bits) |
|---|---|---|---|---|---|
| flipx | 0,90 (0,56) | 0,90 (0,63) | 0,02 (0,01) | 0,92 (0,51) | 0,90 / 0,90 |
| swap | 0,20 (0,12) | 0,31 (0,16) | 0,02 (0,01) | 0,79 (0,93) | 0,91 / 0,89 |
| rot90 | 0,23 (0,12) | 0,34 (0,17) | 0,02 (0,01) | 0,79 (0,50) | 0,91 / 0,89 |
| strong | 0,76 (0,62) | 0,78 (0,65) | 0,08 (0,03) | 0,98 (0,60) | 1,00 / 1,00 |
| weak | 0,89 (0,67) | 0,94 (0,73) | 0,12 (0,11) | 0,91 (0,93) | 0,91 / 0,91 |
| offx | 0,93 (0,46) | 0,95 (0,50) | 0,02 (0,00) | 0,91 (0,56) | 0,91 / 0,89 |
| robot grün / blau | 0,06 / 0,05 | 0,04 / 0,03 | 0,02 / 0,02 | 0,01 / 0,01 | 0,01 / 0,01 |

  layer_s liegt bei den Kopf-Regeln unter hier_s (delta_head swap 0,69 / 0,89, rls_rf 0,82–0,84 / 0,97–0,98
  außer strong). Adam vergisst die Basis fast ganz (0,74–0,99), die schnellen Gewichte mit Orakel-Gate nicht
  (0,00). Bei k = 64 erreicht keine Regel auf einem Gerät mehr als 0,68 (rls_rf strong); rls_rf 0,31–0,68,
  delta_head 0,26–0,54.
- Bibliothek, Test-Seeds 0–2, layer_s / hier_s / layer_s_sp4, zweiter Besuch, Bibliothek (k6cfne) / Orakel (in
  Klammern Bits aus PLAN_TRAINER Phase B):

| Suite | delta_head | rls_head | rls_rf |
|---|---|---|---|
| servo | 0,64 / 0,79 (0,63 / 0,65) | 0,93 / 0,96 (0,86 / 0,88) | 0,96 / 0,99 (0,91 / 0,94) |
| robot, Kalibrierungen | 0,93 / 0,96 (0,88 / 0,93) | 0,94 / 0,98 (0,91 / 0,95) | 0,94 / 0,98 (0,91 / 0,96) |
| robot, grün / blau | 0,00 / 0,01 (0,00 / 0,01) | 0,01 / 0,01 (0,01 / 0,01) | 0,01 / 0,01 (0,01 / 0,01) |

  servo je Gerät mit rls_rf 0,96–0,97 (Bits 0,87–0,95). Mit delta_head verwaltet die Bibliothek schlecht:
  13,3 Allokationen für 6 Geräte, Auswahl 0,79, flipx 0,57, offx 0,30 gegen 0,72–0,83 beim Orakel. Mit den
  rls-Regeln 6,0 Allokationen, Auswahl 0,98. Auf robot liegt die Auswahl im zweiten Besuch bei allen Regeln
  bei 0,65, weil grün und blau nicht gelernt werden.

**Vergleich mit der Vorhersage.** (1) Getroffen: 30 von 30. (2) Verfehlt: rls_rf@task ≥ 0,90 auf allen sechs
Geräten (0,90–1,00), delta_head@task aber nur auf vier (swap und rot90 0,79). (3) Getroffen: dfa@task auf jedem
Gerät weit unter delta_head@task (≤ 0,12). (4) Verfehlt: Adam auf swap 0,20 und rot90 0,23. (5) Getroffen:
höchstens 0,06. (6) Verfehlt: rls_rf 0,96 / Orakel 0,99 und robot wie vorhergesagt, delta_head aber 0,64 statt
≥ 0,85 (Orakel 0,79). Bilanz: 3 getroffen, 3 verfehlt.

**Schluss.** (a) Im Populations-Code sind die servo-Kalibrierungen für den Kopf leicht: rls_rf löst jedes Gerät
mit einem einzigen Update (0,89–1,00), die Bibliothek mit rls_rf liegt bei 0,96 (Bits 0,91). Die Phase-B-Grenze
„Überträge zwischen Bits brauchen einen nichtlinearen Kopf“ war zum großen Teil eine Grenze des Bit-Codes:
delta_head steigt auf flipx, offx, strong von 0,51–0,60 auf 0,91–0,98, Adam von 0,46–0,62 auf 0,76–0,93.
(b) Was bleibt: Achsen tauschen (swap, rot90) lernen Adam und Gradient in 200 Updates kaum (0,20–0,34), die
Delta-Regel langsamer als in Bits (0,79 statt 0,93); nur rls_rf ist schnell. (c) Ein anderes Ziel (grün / blau)
bleibt in jedem Code unlernbar, auch für Adam; das liegt also nicht am Ausgabe-Code (wie 2026-11-23 Vorarbeit 2).
(d) Für Phase D heißt das: servo und robot sind im heutigen Code keine Aufgaben „Kopf reicht nicht“; die
Messlatte bleibt `prev` mit 64 Beispielen. Die Bezugswerte der Anpassungs-Studien liegen jetzt im heutigen
Code vor. (e) delta_head braucht in der Bibliothek viele Allokationen (13 für 6 Geräte); ungeklärt, ob das am
Populations-Code liegt (Fehlermaß über 32 Ausgänge) oder an der langsamen Regel. Nur 2 Seeds (inner) bzw. 3
(Bibliothek).

**Belege.** `results/fastinner_servo_pop.jsonl` (320 Zeilen, Zusammenfassung `python -m netresearch.fastweights
summary --file results/fastinner_servo_pop.jsonl`), `results/library_pop.jsonl` (108 Zeilen, `python -m
netresearch.library summary --file results/library_pop.jsonl --suites servo robot`); Startnetze
`data/base_nets/servo`, `data/base_nets/robot_gaze`; Bit-Bezug `results/fastinner_servo.jsonl`,
`results/library.jsonl`.

## 2026-11-23 — Phase D, D.0: die numseq-Familie teilt sich in „Kopf reicht“, „nur Backprop innen löst“ und „niemand löst“; `dfa` zerstört die Kopf-Aufgaben

**Frage.** Welche Aufgaben der numseq-Familie eignen sich für das Meta-Training des Teachers und welche für den
Meta-Test? Wo reicht Schreiben am Kopf, wo braucht es innere Änderungen, die nur Backprop findet?

**Gemacht.** Job `20261123-184213-d0_ladder` (Commit 2464fcd), Worker, 360 Läufe, alle ohne Fehler. Vorhersage
vor dem Lauf (wörtlich aus „Laufend / offen“):

> - Phase D, Stufe D.0 (Konzept PLAN_TRAINER, Freigabe Nutzer 2026-11-23 mit allen Empfehlungen): die Leiter auf
>   der numseq-Familie der Bibliothek, um Meta-Train- und Meta-Test-Aufgaben zu wählen. Neue Fälle `lib_<Name>`
>   in `adapt.py` (die zwölf Ausgaben von `library.TASKS`, jetzt `adapt.NUMSEQ_TASKS`; k Trainingsfolgen,
>   Test auf 512 ungesehenen). Startnetze layer_s@25k numseq Seeds 0–2, 5, 6 festgelegt in
>   `data/base_nets/numseq` (0,90–0,94). `fastweights inner`, layer_s@25k, Seeds 0–2 (die Meta-Train-Netze;
>   5–6 bleiben für den Meta-Test), k = 64 / 512, Regeln adam, grad@task, dfa@task, delta_head@task,
>   rls_rf@task, 200 Updates, Worker -> `results/phase_d_ladder.jsonl`. Bezug: `prev` k = 64 (Vorarbeit 2) Kopf
>   `rls_rf` 0,21, `dfa` 0,07 / 0,56, `grad` 0,78 / 0,94 (s20 / s200); xormask (layer_s, k = 64) Kopf
>   delta_head 0,48 / 0,85, `grad` 0,04.
>   **Vorhersage vor dem Lauf (2026-11-23),** k = 64, Mittel über Seeds und Varianten: (1) `prev`, `prev2`,
>   `prev3`: „Kopf reicht nicht, `grad` löst“, d. h. grad@task nach 200 Updates ≥ 0,7 und rls_rf@task ≤ 0,4,
>   3 von 3. (2) `xm0F`, `xmA5`, `xm33`, `xmFF`: „Kopf reicht“, rls_rf@task nach 200 Updates ≥ 0,5 und über
>   grad@task, 4 von 4. (3) `plus1`, `minus1`, `plus2`, `minus2`, `diff`: „niemand löst“, keine Regel (auch Adam)
>   ≥ 0,5 nach 200 Updates, 5 von 5. (4) dfa@task nach 20 Updates ≤ 0,15 auf allen 12 Aufgaben.

**Ergebnis.** Testwertung (exakt, 512 ungesehene Folgen) nach 20 / 200 Updates, Mittel über Seeds 0–2 und je 2
Varianten:

| k = 64 | rls_rf@task | delta_head@task | dfa@task | grad@task | Adam |
|---|---|---|---|---|---|
| xm0F | 0,59 / 0,59 | 0,57 / 0,78 | 0,01 / 0,01 | 0,03 / 0,04 | 0,04 / 0,05 |
| xmA5 | 0,57 / 0,57 | 0,52 / 0,75 | 0,01 / 0,01 | 0,03 / 0,03 | 0,02 / 0,04 |
| xm33 | 0,58 / 0,58 | 0,51 / 0,76 | 0,01 / 0,01 | 0,03 / 0,04 | 0,02 / 0,04 |
| xmFF | 0,52 / 0,52 | 0,33 / 0,66 | 0,01 / 0,01 | 0,01 / 0,03 | 0,01 / 0,03 |
| prev | 0,25 / 0,24 | 0,06 / 0,16 | 0,21 / 0,70 | 0,79 / 0,94 | 0,81 / 0,99 |
| prev2 | 0,23 / 0,23 | 0,05 / 0,15 | 0,13 / 0,72 | 0,80 / 0,96 | 0,86 / 0,99 |
| prev3 | 0,09 / 0,09 | 0,02 / 0,06 | 0,08 / 0,66 | 0,71 / 0,90 | 0,72 / 0,96 |
| plus1 / minus1 | 0,23–0,24 | 0,30–0,34 / 0,30–0,31 | 0,01 | 0,21 / 0,19–0,20 | 0,27–0,28 / 0,27–0,29 |
| plus2 / minus2 | 0,22–0,24 | 0,34 / 0,28–0,30 | 0,01 | 0,13–0,17 / 0,13–0,18 | 0,18–0,23 / 0,19–0,25 |
| diff | 0,03 / 0,03 | 0,02 / 0,03 | 0,01 / 0,04 | 0,15 / 0,21 | 0,14 / 0,25 |

- Mit k = 512 reicht der Kopf auch für `prev` / `prev2` (rls_rf 0,77–0,79), und `diff` wird mit Backprop lösbar
  (grad 0,34 / 0,87, Adam 0,24 / 0,94; Kopf 0,18, dfa 0,12).
- Fitness des Teachers (Mittel der Testwertung nach 1, 5, 10, 20 Updates) auf den gewählten Meta-Train-Aufgaben
  (prev2, prev3, xm0F, xmA5, xm33): dfa@task 0,019, delta_head@task 0,12, grad@task 0,165, rls_rf@task 0,42
  (Kopf, zweite Ordnung, ein Update reicht); je Aufgabe die bessere aus delta_head und grad: 0,27.
- `prev` hier dfa 0,21 / 0,70 statt 0,07 / 0,56 in der Vorarbeit 2: andere Ziehungen der 64 Beispiele (Fall
  `lib_prev` statt `prev`) und Orakel-Gate; die Streuung der Ziehungen ist also groß.

**Vergleich mit der Vorhersage.** (1) Getroffen: grad@task 0,90–0,96, rls_rf@task 0,09–0,24. (2) Getroffen:
rls_rf@task 0,52–0,59, grad@task ≤ 0,04. (3) Getroffen: höchstens 0,34 (delta_head bei minus1, plus2).
(4) Verfehlt: 11 von 12, `prev` 0,21. Bilanz: 3 getroffen, 1 verfehlt.

**Schluss.** (a) Die Familie trennt sauber: Kopf-Aufgaben (XOR mit einer Maske), Aufgaben für innere Änderungen
(Kopieren einer früheren Zahl) und bei k = 64 unlösbare (Rechnen mit Übertrag, Differenz). (b) `dfa` schadet den
Kopf-Aufgaben (0,01 gegen delta_head 0,75–0,78): Die inneren Updates zerstören, was der Kopf lernt. Backprop auf
die schnellen Gewichte lernt sie ebenfalls nicht (0,03–0,04). Ein guter Teacher muss also je Episode
entscheiden, ob er innen schreibt; das ist das Meta-Lernziel, nicht nur „schneller als dfa“. (c) Wahl für
Phase D: Meta-Train xm0F, xmA5, xm33 (Kopf) und prev2, prev3 (innen), Startnetze Seeds 0–2. Meta-Test `prev`
(nah), `xmFF` (Kopf, ausgelassen) und `diff` mit k = 512 (fern, eine innere Rechnung), auf Seeds 5–6.

**Belege.** `results/phase_d_ladder.jsonl` (360 Zeilen), Zusammenfassung `python -m netresearch.fastweights summary
--file results/phase_d_ladder.jsonl`.

## 2026-11-23 — Phase D, D.2 / D.3 / D.5: die gelernte Regel löst das ausgelassene `prev` ohne Backprop schneller als Backprop, aber keine Regel kann Kopf- und Innen-Aufgaben zugleich

**Frage.** Findet ES eine lokale Regel für die inneren schnellen Gewichte, die mehr ist als eine bessere
Schrittweite? Hält sie auf dem Meta-Test (ausgelassene Aufgaben, eigene Startnetze) und über ihren
Trainings-Horizont von 20 Updates hinaus?

**Gemacht.** Jobs `20261123-185537-d2_eta` und `20261123-185538-d3_full` (Commit 1cb6dd9), Worker, je 4
Prozesse, D.2 54 Min, D.3 2,7 h. Meta-Test lokal (Commit ac1392b, gleicher Code für `teacher.py eval`): die
besten validierten θ beider Läufe und als Bezug `fastweights inner` (dfa@task, grad@task, delta_head@task,
rls_rf@task) auf lib_prev, lib_xmFF, lib_diff, k = 64 und 512, Seeds 5–6, je 2 Ziehungen, bis 200 Updates.
Vorhersage vor dem Lauf (wörtlich aus „Laufend / offen“):

> - Phase D, Stufen D.2 und D.3 (Konzept PLAN_TRAINER, freigegeben 2026-11-23): `netresearch/teacher.py`
>   (Commit nach D.0; bei θ = 0 bitgleich zu dfa@task geprüft). Meta-Train wie im D.0-Eintrag (prev2, prev3, xm0F,
>   xmA5, xm33; Seeds 0–2; k = 64), Fitness = Testwertung nach 1, 5, 10, 20 Updates gemittelt, 8 Episoden je
>   Generation, Population 48. D.2 (Kontrolle, nur die drei Schrittweiten je Abbildung): 100 Generationen,
>   σ 0,1, lr 0,05. D.3 (Teacher-MLP, 469 Parameter): 300 Generationen, σ 0,05, lr 0,02. Worker ->
>   `results/teacher.jsonl`. Bezug Fitness auf den Meta-Train-Aufgaben: dfa 0,019, delta_head 0,12, grad 0,165,
>   je Aufgabe das Bessere aus delta_head und grad 0,27, rls_rf (Kopf, zweite Ordnung) 0,42. Danach D.5 auf
>   dem Meta-Test (Seeds 5–6): `prev` und `xmFF` mit k = 64, `diff` mit k = 512, bis 200 Updates.
>   **Vorhersage vor dem Lauf (2026-11-23):** (1) D.2: Validierungs-Fitness am Ende ≤ 0,13 (eine Schrittweite
>   kann nur zwischen „innen lernen“ für prev und „innen aus“ für die Kopf-Aufgaben wählen). (2) D.3:
>   Validierungs-Fitness ≥ 0,15, also über dfa, delta_head und D.2, aber unter 0,27. (3) D.5 `prev` mit der
>   D.3-Regel nach 20 Updates ≥ 0,40 (Erfolgskriterium des Konzepts). (4) Über den Trainings-Horizont hinaus
>   verliert die D.3-Regel: `prev` nach 200 Updates unter dfa@task (0,70).

**Ergebnis.**
- Validierung (Meta-Train-Aufgaben, Seeds 0–2, feste Episoden; Fitness = Mittel nach 1, 5, 10, 20 Updates):

| | gesamt | xm0F / xmA5 / xm33 | prev2 / prev3 | Schrittweite fc1 / fc2 / Kopf (× dfa) |
|---|---|---|---|---|
| Start (= dfa@task) | 0,019 | 0,006 | 0,05 / 0,03 | 1 / 1 / 1 |
| D.2 (nur Schrittweiten), Gen. 100 | **0,44** | 0,72 / 0,68 / 0,69 | 0,08 / 0,03 | 0,16 / 0,014 / 34 |
| D.3 (Teacher-MLP), Gen. 300 | 0,17 | 0,04 / 0,03 / 0,04 | **0,39 / 0,34** | 0,34 / 0,15 / 3,0 |

  D.2 stieg bis Gen. 90 und blieb dann bei 0,44; D.3 stieg bis zum Ende (Gen. 250: 0,156, Gen. 300: 0,169).
- Meta-Test, Seeds 5–6, Testwertung nach 1 / 5 / 10 / 20 / 200 Updates (Mittel über 4 Episoden):

| Fall | dfa@task | grad@task | delta_head@task | rls_rf@task | D.2 | D.3 |
|---|---|---|---|---|---|---|
| prev, k = 64 | 0,00 / 0,02 / 0,08 / 0,16 / 0,75 | 0,01 / 0,37 / 0,60 / 0,79 / 0,95 | 0,00 / 0,00 / 0,02 / 0,05 / 0,16 | 0,23 / 0,23 / 0,23 / 0,24 / 0,24 | 0,01 / 0,07 / 0,13 / 0,14 / 0,16 | 0,01 / 0,17 / 0,60 / **0,85 / 0,99** |
| xmFF, k = 64 | 0,00 / 0,00 / 0,01 / 0,01 / 0,01 | 0,00 / 0,00 / 0,01 / 0,01 / 0,02 | 0,00 / 0,00 / 0,12 / 0,45 / 0,71 | 0,60 / 0,57 / 0,57 / 0,57 / 0,56 | **0,60 / 0,68 / 0,68 / 0,68 / 0,68** | 0,01 / 0,02 / 0,01 / 0,00 / 0,01 |
| diff, k = 512 | 0,00 / 0,00 / 0,01 / 0,02 / 0,11 | 0,01 / 0,10 / 0,20 / 0,35 / 0,86 | 0,01 / 0,01 / 0,01 / 0,04 / 0,13 | 0,21 / 0,21 / 0,19 / 0,18 / 0,16 | 0,01 / 0,03 / 0,03 / 0,05 / 0,12 | 0,01 / 0,02 / 0,01 / 0,01 / 0,01 |
| diff, k = 64 | 0,00 / 0,01 / 0,01 / 0,02 / 0,03 | 0,01 / 0,06 / 0,12 / 0,15 / 0,19 | 0,01 / 0,01 / 0,01 / 0,02 / 0,03 | 0,04 / 0,03 / 0,03 / 0,03 / 0,03 | 0,00 / 0,02 / 0,01 / 0,02 / 0,03 | 0,01 / 0,01 / 0,02 / 0,01 / 0,00 |

  D.3 auf `prev` je Episode nach 20 Updates 0,80 / 0,87 / 0,90 / 0,83, nach 200 Updates 0,98–1,00 (grad
  0,93–0,96, dfa 0,60–0,88).

**Vergleich mit der Vorhersage.** (1) Verfehlt: D.2 0,44 statt ≤ 0,13. Eine Schrittweite je Abbildung wählt
nicht nur zwischen „innen lernen“ und „innen aus“: Kopf schnell und innen fast aus löst die Kopf-Aufgaben und
übertrifft sogar rls_rf (0,42). (2) Formal getroffen (0,17, unter 0,27), aber nicht über D.2; der Teil „über
D.2“ ist verfehlt. (3) Getroffen: `prev` nach 20 Updates 0,85 (≥ 0,40; grad 0,79, dfa 0,16). (4) Verfehlt:
nach 200 Updates 0,99, über dfa (0,75) und grad (0,95); keine Kurzhorizont-Falle. Bilanz: 1 getroffen, 1 halb,
2 verfehlt.

**Schluss.** (a) Erstmals findet ES eine lokale Regel, die mehr ist als eine Schrittweite: Auf dem
ausgelassenen `prev`, eigenen Startnetzen und ungesehenen Folgen lernt sie innen ohne Backprop schneller als
Backprop auf dieselben schnellen Gewichte (0,85 gegen 0,79 nach 20 Updates, 0,99 gegen 0,95 nach 200), mit
fester Zufalls-Rückprojektion wie dfa (dfa 0,16). Das Erfolgskriterium des Konzepts ist erfüllt, für die nahe
Übertragung (Verwandte prev2 / prev3 im Training). (b) Die Kontrolle D.2 ist auf den Kopf-Aufgaben unschlagbar
einfach: Kopf × 34, innen aus; sie überträgt sich auf das ausgelassene xmFF (0,68 nach 5 Updates, rls_rf 0,57).
(c) Keine der beiden Regeln kann beides. D.3 hat die Kopf-Schrittweite nicht gefunden (σ 0,05 und lr 0,02 zu
klein für die Größenordnung, ×3 statt ×34), D.2 hat keine innere Regel. Die Auswahl je Episode „innen
schreiben ja / nein“ ist offen; Idealwert beider zusammen etwa 0,57. (d) Fern gibt es keine Übertragung: `diff`
(Rechnen mit Differenz) lernt keine Regel außer Backprop (grad 0,86 nach 200 bei k = 512; D.3 0,01). Die
D.3-Regel ist also auf „frühere Zahl kopieren“ spezialisiert, nicht allgemein. (e) Nächster Schritt: die
Positions-Ablation (map / blind / split mit σ 0,1, lr 0,05) läuft; `map` dort zeigt auch, ob größere ES-Schritte
beides zugleich finden. D.4 (gelernte Rückprojektion) erst, wenn `diff` das Ziel wird. Nur 2 Meta-Test-Seeds
und 2 Ziehungen; ein ES-Lauf je Variante.

**Belege.** `results/teacher.jsonl` (D.2 101 Zeilen, D.3 301; letzte Zeile mit θ), Checkpoints
`results/checkpoints/teacher/d2_eta.pt`, `d3_full.pt` (nicht im Repo), Meta-Test `results/phase_d_test.jsonl`
(80 Zeilen; Bezug mit `python -m netresearch.fastweights summary --file results/phase_d_test.jsonl`, Regeln
`teach:*` mit eigenem Skript, da ohne Gedächtnis-Spalte).

## 2026-11-24 — Phase D, Position im Netz: der Teacher braucht die Schicht-Kennung, ein eigener je Schicht bringt nichts; mit größeren ES-Schritten kann eine Regel Kopf- und Innen-Aufgaben zugleich

**Frage.** (Nutzer 2026-11-23) Braucht der Teacher eine Information über die Position im Netz, kann er alle
Neuronen gleich behandeln, oder braucht jede Schicht einen eigenen Teacher? Nebenbei: Findet ES mit größeren
Schritten eine Regel, die die Kopf-Aufgaben (wie D.2) und die Innen-Aufgaben (wie D.3) zugleich kann?

**Gemacht.** Jobs `20261123-223727-pos_map`, `-223728-pos_blind`, `-223729-pos_split` (Commit ebe5129), Worker,
je 4 Prozesse, je etwa 2,4 h. Danach lokal Meta-Test wie im D.5-Eintrag (lib_prev, lib_xmFF mit k = 64,
lib_diff mit k = 512; Seeds 5–6, je 2 Ziehungen, bis 200 Updates) und für `map` Ausschalt-Proben der Regelteile
(Skripte im Scratchpad: Teacher-Ausgang je Teil auf null bzw. Mittelwert, s20, Seeds 0–2 bzw. 5–6, je 2
weitere Ziehungen). Vorhersage vor dem Lauf (wörtlich aus „Laufend / offen“):

> - Phase D, Position im Netz (Frage des Nutzers 2026-11-23: braucht der Teacher die Position, oder je Schicht
>   einen eigenen?): `teacher.py --pos` (Commit ac1392b; alle drei Varianten bei Start bitgleich zu dfa@task).
>   `map` = ein MLP für fc1, fc2 und Kopf mit Schicht-Kennung im Eingang und eigener Schrittweite je Schicht (wie
>   D.3), `blind` = dasselbe MLP ohne Kennung und mit einer gemeinsamen Schrittweite (die Schicht ist nur noch an
>   der Telemetrie erkennbar), `split` = ein eigenes MLP je Schicht (1401 Parameter). Ausgangslage aus D.2 / D.3:
>   D.2 (nur Schrittweiten, σ 0,1, lr 0,05) erreicht Validierung 0,44 mit Kopf × 34 und innen fast aus (fc1 × 0,16,
>   fc2 × 0,014): Kopf-Aufgaben 0,68–0,72, prev2 / prev3 0,08 / 0,03. D.3 (σ 0,05, lr 0,02) nur 0,17, steigt
>   aber noch: prev2 / prev3 0,39 / 0,34, Kopf-Aufgaben 0,03–0,04, Kopf × 3. Die kleinen Schritte von D.3 fanden
>   die Kopf-Schrittweite in 300 Generationen nicht. Damit die drei Varianten vergleichbar sind und nicht alle an
>   der ES-Einstellung scheitern, laufen alle drei mit σ 0,1, lr 0,05, 300 Generationen, sonst wie D.3 (`map`
>   also als D.3b neu). Worker -> `results/teacher.jsonl`. Idealwert bei Auswahl je Episode (Kopf-Aufgaben wie
>   D.2, prev2 / prev3 wie D.3): etwa 0,57.
>   **Vorhersage vor dem Lauf (2026-11-23):** (1) `map` (D.3b) übertrifft D.2: Validierung am Ende ≥ 0,46, mit
>   prev2 ≥ 0,15 bei Kopf-Aufgaben ≥ 0,60; die Episoden-Telemetrie (S, ΔS) reicht für eine teilweise Auswahl
>   „innen schreiben ja / nein“. (2) `blind` bleibt um ≥ 0,05 unter `map`: ohne Kennung und mit einer
>   Schrittweite lässt sich „Kopf schnell, innen vorsichtig“ nur über die Telemetrie ausdrücken. (3) `split`
>   liegt höchstens 0,02 über `map` (dreifache Parameterzahl, mehr ES-Rauschen; die Schicht-Kennung reicht).

**Ergebnis.**
- Validierung (Meta-Train, Fitness = Mittel nach 1, 5, 10, 20 Updates), Gen. 300 (bestes θ in Klammern):

| Variante | gesamt | xm0F / xmA5 / xm33 | prev2 / prev3 | Schrittweite fc1 / fc2 / Kopf (× dfa, bestes θ) |
|---|---|---|---|---|
| `map` (D.3b) | 0,54 (0,54) | 0,67 / 0,62 / 0,63 | 0,46 / 0,33 | 0,056 / 0,002 / 2,6 |
| `blind` | 0,07 (0,08) | 0,002 | 0,20 / 0,14 | 0,30 gemeinsam |
| `split` | 0,55 (0,55) | 0,67 / 0,60 / 0,61 | 0,49 / 0,36 | 0,055 / 0,008 / 2,4 |
| zum Vergleich D.2 / D.3 | 0,44 / 0,17 | 0,68–0,72 / 0,03–0,04 | 0,08 / 0,03 bzw. 0,39 / 0,34 | |

  `map` und `split` sprangen zwischen Gen. 60 und 120 (map) bzw. 180 und 210 (split) von der Innen-Lösung
  (prev2 / prev3 0,45–0,57, Kopf-Aufgaben 0,01) auf beides; `blind` blieb bis zum Ende bei der Innen-Lösung
  und erreichte sie nur halb.
- Meta-Test, Seeds 5–6, nach 1 / 5 / 10 / 20 / 200 Updates (Mittel über 4 Episoden):

| Fall | `map` | `split` | `blind` | D.3 | D.2 | grad@task | rls_rf@task |
|---|---|---|---|---|---|---|---|
| prev, k = 64 | 0,01 / 0,33 / 0,45 / 0,66 / 0,80 | 0,01 / 0,40 / 0,56 / 0,77 / 0,91 | 0,00 / 0,07 / 0,27 / 0,42 / 0,06 | 0,01 / 0,17 / 0,60 / 0,85 / 0,99 | 0,01 / 0,07 / 0,13 / 0,14 / 0,16 | 0,01 / 0,37 / 0,60 / 0,79 / 0,95 | 0,23 / 0,23 / 0,23 / 0,24 / 0,24 |
| xmFF, k = 64 | 0,40 / 0,54 / 0,54 / 0,58 / 0,60 | 0,48 / 0,54 / 0,54 / 0,57 / **0,01** | 0,00 | 0,01 | 0,60 / 0,68 / 0,68 / 0,68 / 0,68 | 0,00 / 0,00 / 0,01 / 0,01 / 0,02 | 0,60 / 0,57 / 0,57 / 0,57 / 0,56 |
| diff, k = 512 | 0,02 / 0,01 / 0,01 / 0,00 / 0,01 | 0,02 / 0,02 / 0,02 / 0,12 / 0,00 | 0,01 / 0,03 / 0,04 / 0,06 / 0,00 | 0,01 / 0,02 / 0,01 / 0,01 / 0,01 | 0,01 / 0,03 / 0,03 / 0,05 / 0,12 | 0,01 / 0,10 / 0,20 / 0,35 / 0,86 | 0,21 / 0,21 / 0,19 / 0,18 / 0,16 |

  Über den Trainings-Horizont hinaus: `split` bricht auf xmFF zwischen 50 und 100 Updates in allen 4 Episoden
  zusammen (0,50–0,59 → 0,00–0,02), `blind` auf prev (0,32–0,49 nach 20 → 0,01–0,13 nach 200). `map` bleibt
  stabil (prev 0,70–0,96, xmFF 0,50–0,65 nach 200).
- Was die Regel von `map` tut (Ausschalt-Proben, s20): prev2 voll 0,71, ohne Hebb-Term 0,14, Teacher auf fc1
  aus (reines dfa bei gefundener Schrittweite) 0,11, alle inneren Updates aus 0,11, Faktor a ohne Modulation je
  Einheit (Mittel der Abbildung) 0,73; prev genauso (0,75 / 0,15 / 0,10 / 0,10 / 0,72). xm0F 0,71 voll und
  0,72 mit inneren Updates aus; xmFF 0,56 voll, 0,63 mit inneren Updates aus. Die Stärke der inneren
  Fehler-Updates ist bei prev- und xm-Episoden gleich (fc1 etwa 0,24 × dfa, fc2 etwa 0,005 × dfa, Kopf etwa
  16 × dfa). Der Hebb-Faktor h auf fc1 hängt dagegen vom Episoden-Zustand ab: bei prev2 nach 5 Updates im
  Mittel −9 (fast alle Einheiten gleich, anti-hebbisch), bei xm0F +2,5 (hebbisch, schwach); innerhalb eines
  Updates korreliert h mit −d (−0,4 bis −0,8).

**Vergleich mit der Vorhersage.** (1) Getroffen: `map` 0,54 (≥ 0,46), prev2 0,46 (≥ 0,15), Kopf-Aufgaben
0,62–0,67 (≥ 0,60). (2) Getroffen: `blind` 0,07, also 0,47 unter `map`. (3) Getroffen: `split` 0,007 über
`map`. Bilanz: 3 getroffen.

**Schluss.** (a) Zur Frage des Nutzers: Der Teacher braucht die Position, zumindest die Unterscheidung der
Schichten. Ohne Kennung und mit gemeinsamer Schrittweite (`blind`) findet ES nur eine halbe Innen-Lösung und
kann den Kopf nicht schnell machen; die Telemetrie allein (echter Fehler am Kopf, rückprojizierter innen,
gelu' nur bei fc1) verrät die Schicht nicht genug. Eine Kennung im Eingang reicht aber: ein eigener Teacher je
Schicht (`split`, dreifache Parameterzahl) ist in der Validierung gleich gut und auf prev etwas besser (0,77
gegen 0,66 nach 20), bricht aber über den Trainings-Horizont hinaus auf der Kopf-Aufgabe zusammen. Die
geteilte Regel mit Kennung ist robuster. (b) Mit größeren ES-Schritten (σ 0,1, lr 0,05) findet ES eine Regel
für beide Aufgabenarten: Validierung 0,54 (Idealwert etwa 0,57), auf dem Meta-Test prev 0,66 / 0,80 und xmFF
0,58 / 0,60 nach 20 / 200 Updates, also beide ausgelassenen Aufgaben mit einer Regel; einzeln sind D.3 auf prev
(0,85) und D.2 auf xmFF (0,68) besser. (c) Die Regel entscheidet nicht über die Stärke der Fehler-Updates je
Episode, sondern über einen Hebb-Term auf fc1, dessen Vorzeichen und Stärke vom Episoden-Zustand (Verlust,
Verlaufsänderung, Update-Nummer) abhängen: bei prev stark anti-hebbisch, bei xm schwach hebbisch. Dieser Term
trägt den ganzen Innen-Gewinn (ohne ihn 0,14 statt 0,71); das Fehlersignal über B nutzt innen nichts mehr. Die
gefundene Regel ist also keine verbesserte Rückprojektion, sondern Hebb mit globalem Modulator (drei Faktoren:
Eingang, Ausgang, Episoden-Signal). (d) `diff` lernt weiter keine Regel. (e) Ein ES-Lauf je Variante; ob
`split` gegenüber `map` auf prev wirklich besser ist, ist mit 4 Meta-Test-Episoden offen. Der Zusammenbruch von
`split` liegt vermutlich an t / T > 1 jenseits des Trainings (ungeprüft).

**Belege.** `results/teacher.jsonl` (je 301 Zeilen `pos_map`, `pos_blind`, `pos_split`; letzte Zeile mit θ),
Checkpoints `results/checkpoints/teacher/pos_*.pt` (nicht im Repo), Meta-Test `results/phase_d_test.jsonl`
(jetzt 116 Zeilen, Regeln `teach:pos_*:best`).

## 2026-11-24 — Phase D, Übertragung auf andere Netze: die gefundene Regel überträgt sich auf ein viermal größeres Netz derselben Architektur fast verlustfrei, auf die Hierarchie nur am Kopf

**Frage.** Ist die gefundene lokale Regel an das Netz gebunden, auf dem ES sie gesucht hat (layer_s@25k), oder
überträgt sie sich unverändert auf Netze, die der Teacher nie gesehen hat?

**Gemacht.** Jobs `20261124-073356-tr_teach_hier_s`, `-073357-tr_base_hier_s`, `-073357-tr_teach_layer_s`,
`-073358-tr_base_layer_s` (Commit 7973cf9), Worker mit 6 Prozessen, 640 Zeilen, alle ohne Fehler. θ der Regeln
aus der letzten Zeile von `results/teacher.jsonl` (auf 10⁻⁶ gerundet). Danach lokal Proben auf hier_s und
layer_s (Seeds 5–6, je 2 Ziehungen, s20): Hebb-Ausgang des Teachers auf fc1 / fc2 mit Faktor 0 bis 1000
skaliert (Skript im Scratchpad). Vorhersage vor dem Lauf (wörtlich aus „Laufend / offen“):

> - Phase D, Übertragung auf andere Netze (Auftrag Nutzer 2026-11-24, D.5 „anderes Netz“): die gefundenen Regeln
>   unverändert (θ aus `results/teacher.jsonl`, nur Auswertung, kein neues ES) auf zwei Startnetze, die der
>   Teacher nie gesehen hat: hier_s (andere Architektur, 4 × Parameter, fc1 236→118, fc2 118→236, Kopf 472) und
>   layer_s (gleiche Architektur wie layer_s@25k, anders trainiert), beide aus `data/base_nets/numseq`. Regeln
>   `teach:pos_map`, `d3_full`, `d2_eta`, `pos_split`; Bezug dfa@task, grad@task, delta_head@task, rls_rf@task
>   auf demselben Netz. Fälle lib_prev, lib_prev2, lib_xmFF, lib_xm0F, k = 64, Seeds 0–2, 5, 6, je 2 Ziehungen,
>   bis 200 Updates, Worker -> `results/phase_d_transfer.jsonl`. Stichprobe vorab (hier_s, Seed 0, prev, eine
>   Ziehung): pos_map 0,06, d3_full 0,13, dfa 0,16 nach 20 Updates.
>   **Vorhersage vor dem Lauf (2026-11-24):** (1) Der Kopf-Teil überträgt sich: auf xmFF und xm0F liegen
>   `pos_map` und `d2_eta` nach 20 Updates auf beiden Netzen über delta_head@task. (2) Der Innen-Teil überträgt
>   sich nur auf die gleiche Architektur: auf layer_s erreicht `pos_map` auf prev nach 20 Updates mindestens das
>   Doppelte von dfa@task; auf hier_s liegt er höchstens 0,05 über dfa@task. (3) Auf hier_s erreicht keine
>   gefundene Regel auf prev nach 20 Updates grad@task.

Korrektur zur Beschreibung in der Vorhersage: layer_s ist nicht nur anders trainiert, sondern auch breiter
(fc1 345→138, fc2 138→69, Kopf 552, 101 080 Parameter gegenüber 24 712 bei layer_s@25k; je 8 Zellen). hier_s
hat 99 656 Parameter (fc1 236→118, fc2 118→236, Kopf 472, 4 Zellen, fc1 / fc2 je Schritt 6-mal statt 4-mal
aufgerufen).

**Ergebnis.** Testwertung nach 1 / 5 / 20 / 200 Updates, k = 64, Mittel über Seeds 0–2, 5, 6 und je 2
Ziehungen (10 Episoden); in Klammern Spanne der 10 Episoden nach 20 Updates.

| Netz, Fall | dfa@task | grad@task | delta_head@task | rls_rf@task | D.2 | D.3 | `map` | `split` |
|---|---|---|---|---|---|---|---|---|
| layer_s, prev | 0,00 / 0,03 / 0,24 / 0,77 (0,02–0,42) | 0,00 / 0,41 / 0,82 / 0,95 (0,71–0,92) | 0,00 / 0,00 / 0,02 / 0,12 | 0,19 / 0,20 / 0,20 / 0,20 | 0,01 / 0,05 / 0,11 / 0,13 | 0,01 / 0,08 / 0,47 / 0,93 | 0,01 / 0,25 / **0,81** / 0,89 (0,73–0,87) | 0,01 / 0,31 / 0,83 / 0,95 |
| layer_s, prev2 | 0,00 / 0,04 / 0,25 / 0,81 | 0,01 / 0,51 / 0,89 / 0,98 | 0,00 / 0,00 / 0,02 / 0,09 | 0,15 | 0,01 / 0,04 / 0,09 / 0,10 | 0,00 / 0,06 / 0,46 / 0,93 | 0,01 / 0,15 / 0,73 / 0,82 | 0,01 / 0,31 / 0,85 / 0,75 |
| layer_s, xm0F | 0,01 | 0,00 / 0,02 / 0,04 / 0,04 | 0,00 / 0,00 / 0,56 / 0,90 | 0,90 | 0,86 / 0,89 / 0,89 / 0,89 | 0,04 / 0,23 / 0,05 / 0,01 | 0,71 / 0,79 / 0,83 / 0,85 | 0,77 / 0,82 / 0,84 / **0,09** |
| layer_s, xmFF | 0,00 / 0,00 / 0,01 / 0,01 | 0,00 / 0,00 / 0,01 / 0,03 | 0,00 / 0,00 / 0,27 / 0,80 | 0,81 | 0,63 / 0,73 / 0,74 / 0,75 | 0,00 / 0,02 / 0,03 / 0,00 | 0,22 / 0,35 / 0,46 / 0,47 (0,29–0,66) | 0,33 / 0,47 / 0,54 / **0,00** |
| hier_s, prev | 0,00 / 0,01 / 0,14 / 0,62 (0,01–0,21) | 0,01 / 0,22 / 0,56 / 0,72 (0,49–0,66) | 0,00 / 0,00 / 0,03 / 0,10 | 0,13 | 0,01 / 0,06 / 0,09 / 0,10 | 0,01 / 0,04 / 0,10 / 0,29 | 0,01 / 0,04 / **0,06** / 0,07 (0,04–0,08) | 0,01 / 0,04 / 0,06 / 0,06 |
| hier_s, prev2 | 0,00 / 0,01 / 0,05 / 0,54 | 0,01 / 0,13 / 0,46 / 0,65 | 0,00 / 0,00 / 0,02 / 0,05 | 0,08 | 0,00 / 0,03 / 0,05 / 0,05 | 0,01 / 0,03 / 0,07 / 0,28 | 0,01 / 0,02 / 0,03 / 0,04 | 0,01 / 0,02 / 0,04 / 0,04 |
| hier_s, xm0F | 0,00 / 0,01 / 0,04 / 0,01 | 0,00 / 0,02 / 0,04 / 0,04 | 0,00 / 0,00 / 0,48 / 0,74 | 0,64 / 0,63 / 0,63 / 0,63 | 0,62 / 0,69 / 0,72 / 0,72 | 0,07 / 0,30 / 0,26 / 0,00 | 0,61 / 0,69 / **0,70** / 0,71 | 0,61 / 0,69 / 0,71 / 0,68 |
| hier_s, xmFF | 0,00 / 0,00 / 0,01 / 0,01 | 0,00 / 0,00 / 0,01 / 0,02 | 0,00 / 0,00 / 0,20 / 0,57 | 0,52 | 0,44 / 0,55 / 0,56 / 0,58 | 0,00 / 0,10 / 0,15 / 0,00 | 0,23 / 0,44 / 0,49 / 0,54 | 0,31 / 0,45 / 0,49 / 0,51 |

- Mit k = 512 (nur die Bezugsregeln): grad@task löst prev auf beiden Netzen nach 20 Updates (0,99–1,00),
  rls_rf@task 0,74 (hier_s) und 0,94 (layer_s).
- Proben zum Hebb-Term (prev, s20): layer_s ×0 0,08, ×0,1 0,10, ×0,3 0,24, ×1 0,83, ×3 0,00; prev2 ×0 0,06,
  ×0,3 0,26, ×1 0,75, ×3 0,00. hier_s ×0 bis ×3 durchweg 0,06–0,07 (prev2 0,03–0,04), ×10 bis ×1000
  0,00–0,01. Auf hier_s ist der Hebb-Term in keiner Stärke nützlich; dort wirkt `map` nur über den Kopf.

**Vergleich mit der Vorhersage.** (1) Getroffen: Auf xm0F und xmFF liegen `map` und D.2 nach 20 Updates auf
beiden Netzen über delta_head@task (layer_s 0,83 / 0,89 und 0,46 / 0,74 gegen 0,56 und 0,27; hier_s 0,70 / 0,72
und 0,49 / 0,56 gegen 0,48 und 0,20). (2) Getroffen: layer_s prev `map` 0,81, dfa 0,24 (3,4-fach); hier_s 0,06,
dfa 0,14 (darunter). (3) Getroffen: auf hier_s höchstens 0,10 (D.3), grad 0,56. Bilanz: 3 getroffen.

**Schluss.** (a) Die gefundene Regel ist nicht an ihr Netz gebunden: Auf layer_s, viermal so viele Parameter,
breitere Abbildungen, anders trainiert, nie im Meta-Training, lernt `map` prev nach 20 Updates so schnell wie
Backprop auf dieselben schnellen Gewichte (0,81 gegen 0,82; dfa 0,24) und xm0F fast wie rls_rf. Die
Normierungen der Telemetrie (d / rms, tanh(y), Fehler je Abbildung) machen sie unabhängig von der Breite. (b) Sie
ist aber an die Architektur gebunden: Auf der Hierarchie hier_s (gleiche Größe wie layer_s) überträgt sich nur
der Kopf-Teil (xm0F 0,70 gegen delta_head 0,48); der Innen-Teil hilft in keiner Stärke, und die Regel liegt auf
prev unter dfa (0,06 gegen 0,14), weil sie die inneren Fehler-Updates fast abschaltet. Der anti-hebbische Schub
auf fc1 setzt eine bestimmte Rolle von fc1 voraus, die die Hierarchie nicht hat (fc2 weitet dort auf, fc1 / fc2
werden je Schritt 6-mal statt 4-mal aufgerufen; welcher Unterschied entscheidet, ist ungeprüft). (c) Nach der
Positions-Ablation passt das Bild zusammen: Der Teacher braucht die Rolle der Schicht, und diese Rolle ist eine
Eigenschaft der Architektur, nicht der Größe. Eine Regel für mehrere Architekturen braucht Meta-Training auf
mehreren Architekturen oder eine Kennung, die die Rolle beschreibt statt den Namen. (d) `split` bricht auch
auf layer_s auf den Kopf-Aufgaben nach mehr als 20 Updates zusammen (xm0F 0,84 → 0,09), `map` nicht: Der
geteilte Teacher bleibt die robustere Form. (e) D.2 bleibt auf den Kopf-Aufgaben vorn (layer_s xmFF 0,74
gegen `map` 0,46); D.3 überträgt sich auf layer_s schwächer als `map` (prev 0,47).

**Belege.** `results/phase_d_transfer.jsonl` (640 Zeilen; Bezugsregeln auch k = 512), Zusammenfassung wie im
Skript der Auswertung (Mittel über `runs` je Netz, Fall, k, Regel). Ausführliche Darstellung der ganzen
Phase D: `PHASE_D.md`.

## 2026-11-25 — Phase D, zweite ES-Saat und Meta-Training auf zwei Architekturen: „beides zugleich“ ist wiederholbar; mit hier_s im Training findet ES dort trotzdem keine Innen-Regel und verliert sie teilweise auf layer_s@25k; die Rollen-Kennung ist gleich gut lernbar, aber auf einer ausgelassenen Aufgabe instabil

**Frage.** (1) Hängt das Ergebnis „eine Regel für Kopf- und Innen-Aufgaben“ (`pos_map`) an der Saat der Suche?
(2) Lernt eine Regel, die auf layer_s@25k *und* hier_s meta-trainiert wird, auch auf hier_s im Inneren? (3) Ist
eine Kennung, die die Rolle der Schicht beschreibt statt ihren Namen, ebenso gut lernbar?

**Gemacht.** ES-Jobs `20261124-091813-pos_map_s1`, `-091814-arch_map`, `-091814-arch_role` (Commit 6b2161b),
Worker mit 6 Prozessen, nacheinander; Laufzeit 3,8 h (`pos_map_s1`) und je etwa 8 h für die beiden Läufe mit
hier_s (etwa 100 s je Generation, hier_s ist viermal so groß und ruft fc1 / fc2 6-mal je Update auf). Meta-Test
auf den Worker-Jobs `20261125-062731-ev_arch_layer_s25k`, `-062732-ev_arch_hier_s`, `-062733-ev_arch_layer_s`
(Fälle prev, prev2, xmFF, xm0F; Seeds 5–6, je 2 Ziehungen, k = 64), dazu für layer_s@25k die fehlenden
Bezugswerte auf prev2 / xm0F (`-062741-ev_base_l25k`, `-062742-ev_pm_l25k`). Ein erster Satz Eval-Jobs ist
an einem Fehler beim Abschicken gescheitert (Befehl `run` statt `eval`, Argumentfehler nach Sekunden) und
wurde unverändert neu abgeschickt. Danach eine lokale Ausschalt-Probe zu `arch_role` auf xmFF (Skript im
Scratchpad). Vorhersage vor dem Lauf (wörtlich aus „Laufend / offen“):

> - Phase D, zweite ES-Saat und Meta-Training auf zwei Architekturen (Auftrag Nutzer 2026-11-24, `PHASE_D.md`
>   Abschnitt 8): `teacher.py run --seed`, `--models`, `--pos role` (Commit nach diesem Eintrag; Lauf mit einem
>   Netz bitgleich zum alten Code geprüft, alle Varianten bei Start = dfa@task). `role` ersetzt die
>   Schicht-Kennung durch eine Beschreibung der Rolle: [Kopf ja / nein, log2(n_out / n_in), log2(Aufrufe der
>   Abbildung je Update) / 2]; layer_s@25k fc1 / fc2 / Kopf [0, −1,32, 1] / [0, −1, 1] / [1, −1,70, 0], hier_s
>   [0, −1, 1,29] / [0, +1, 1,29] / [1, −2,88, 0]; die drei Schrittweiten bleiben je Name. Drei Läufe, je 300
>   Generationen, σ 0,1, lr 0,05, Meta-Train-Aufgaben und Seeds 0–2 wie bisher: (A) `pos_map_s1` = `pos_map` mit
>   ES-Saat 1, nur layer_s@25k; (B) `arch_map` Kennung wie `map`, Episoden aus layer_s@25k und hier_s; (C)
>   `arch_role` dasselbe mit Rollen-Kennung. Worker (6 Prozesse, nacheinander, je etwa 2 h) ->
>   `results/teacher.jsonl`; danach Meta-Test auf Seeds 5–6 (prev, xmFF, k = 64) auf layer_s@25k, hier_s und
>   layer_s (nie im Training). Bezug: `pos_map` Validierung 0,54; Meta-Test layer_s@25k prev / xmFF 0,66 / 0,58
>   nach 20 Updates; hier_s prev dfa 0,14, grad 0,56, `pos_map` 0,06.
>   Einschränkung vorab: Eine dritte Architektur mit anderer Rollen-Verteilung gibt es unter den festgelegten
>   numseq-Startnetzen nicht; ob `role` auf ungesehene Architekturen besser überträgt als `map`, lässt sich hier
>   nicht prüfen, nur ob die Rollen-Kennung ebenso gut lernbar ist.
>   **Vorhersage vor dem Lauf (2026-11-24):** (1) Die zweite Saat bestätigt „beides zugleich“: `pos_map_s1`
>   Validierung ≥ 0,45 und Meta-Test layer_s@25k prev ≥ 0,50 und xmFF ≥ 0,45 nach 20 Updates. (2) Mit hier_s im
>   Training lernt die Regel auch dort innen: `arch_map` Meta-Test hier_s prev ≥ 0,25 nach 20 Updates (über dfa
>   0,14) bei layer_s@25k prev ≥ 0,50. (3) Die Rollen-Kennung ist ebenso gut lernbar: `arch_role` und `arch_map`
>   liegen in der Validierung höchstens 0,03 auseinander.

**Ergebnis.** Validierung auf den Meta-Train-Aufgaben (Seeds 0–2, je 2 feste Ziehungen):

| Lauf | Netze im Training | Kennung | Validierung (Gen 300) | layer_s@25k | hier_s | prev2 | xm0F |
|---|---|---|---|---|---|---|---|
| `pos_map` | layer_s@25k | Name | 0,54 | – | – | 0,46 | 0,67 |
| `pos_map_s1` | layer_s@25k | Name | 0,53 | – | – | 0,36 | 0,71 |
| `arch_map` | layer_s@25k, hier_s | Name | 0,46 | 0,53 | 0,38 | 0,17 | 0,70 |
| `arch_role` | layer_s@25k, hier_s | Rolle | 0,46 | 0,54 | 0,39 | 0,18 | 0,70 |

Bei `arch_map` / `arch_role` steigt die Validierung auf hier_s schon bis Generation 50 auf 0,36 und bleibt dann
bei 0,38; der Anstieg auf layer_s@25k kommt erst ab Generation 70.

Meta-Test: Testwertung nach 20 Updates (in Klammern nach 200), Mittel über 4 Episoden (Seeds 5–6 × 2 Ziehungen):

| Netz, Fall | dfa@task | grad@task | delta_head@task | rls_rf@task | `pos_map` | `pos_map_s1` | `arch_map` | `arch_role` |
|---|---|---|---|---|---|---|---|---|
| layer_s@25k, prev | 0,16 (0,75) | 0,79 (0,95) | 0,05 (0,16) | 0,24 | **0,66** (0,80) | **0,60** (0,63) | 0,41 (0,43) | 0,45 (0,52) |
| layer_s@25k, prev2 | 0,20 (0,76) | 0,79 (0,97) | 0,04 (0,10) | 0,14 | 0,73 (0,90) | 0,65 (0,67) | 0,48 (0,50) | 0,53 (0,59) |
| layer_s@25k, xmFF | 0,01 | 0,01 | 0,45 (0,71) | 0,57 | 0,58 (0,60) | **0,68** (0,69) | 0,60 (0,62) | **0,01 (0,00)** |
| layer_s@25k, xm0F | 0,01 | 0,05 | 0,67 (0,83) | 0,62 | 0,77 (0,75) | 0,79 (0,78) | 0,79 (0,78) | 0,80 (**0,53**) |
| hier_s, prev | 0,10 (0,60) | 0,59 (0,75) | 0,03 (0,10) | 0,13 | 0,06 (0,07) | 0,07 (0,07) | **0,07 (0,07)** | 0,07 (0,08) |
| hier_s, prev2 | 0,06 (0,53) | 0,46 (0,66) | 0,02 (0,05) | 0,07 | 0,03 (0,04) | 0,04 (0,04) | 0,03 (0,04) | 0,03 (0,04) |
| hier_s, xmFF | 0,01 | 0,01 | 0,24 (0,63) | 0,57 | 0,55 (0,61) | 0,62 (0,64) | 0,61 (0,63) | 0,64 (0,65), nach 1 Update 0,00 |
| hier_s, xm0F | 0,07 | 0,04 | 0,51 (0,79) | 0,70 | 0,74 (0,76) | 0,76 (0,77) | 0,77 (0,77) | 0,77 (0,76) |
| layer_s, prev | 0,30 (0,78) | 0,81 (0,95) | 0,02 (0,10) | 0,18 | 0,83 (0,90) | 0,67 (0,72) | 0,54 (0,58) | 0,68 (0,72) |
| layer_s, prev2 | 0,25 (0,78) | 0,90 (0,99) | 0,01 (0,07) | 0,13 | 0,75 (0,83) | 0,72 (0,73) | 0,42 (0,44) | 0,76 (0,80) |
| layer_s, xmFF | 0,01 | 0,01 | 0,32 (0,82) | 0,79 | 0,52 (0,54) | 0,80 (0,83) | 0,67 (0,69) | 0,34 (**0,00**) |
| layer_s, xm0F | 0,01 | 0,04 | 0,60 (0,92) | 0,90 | 0,84 (0,87) | 0,91 (0,92) | 0,90 (0,90) | 0,90 (0,90) |

Probe zu `arch_role` auf xmFF (lokal, Seeds 5–6, je Ziehung 0, Testwertung nach 1 / 20 Updates): vollständig
layer_s@25k 0,00 / 0,00; Hebb-Term am Kopf auf null 0,00 / 0,00; Fehler-Faktor am Kopf auf null 0,01 / 0,27;
**Hebb-Term innen (fc1, fc2) auf null 0,00 / 0,67**. hier_s vollständig 0,00 / 0,64, Hebb innen auf null
0,00 / 0,65. Bei `arch_map` ändert keine dieser Ausschaltungen viel (layer_s@25k 0,45 / 0,63, Hebb innen auf
null 0,49 / 0,65). Auf xm0F (im Meta-Training) verhalten sich beide Regeln unauffällig (0,80 / 0,80).

**Vergleich mit der Vorhersage.** (1) Getroffen: `pos_map_s1` Validierung 0,53 (≥ 0,45), Meta-Test layer_s@25k
prev 0,60 (≥ 0,50), xmFF 0,68 (≥ 0,45). (2) Verfehlt: `arch_map` auf hier_s prev 0,07 (gefordert ≥ 0,25, dfa
0,10), und auf layer_s@25k prev 0,41 (gefordert ≥ 0,50). (3) Getroffen: Validierung `arch_role` 0,464,
`arch_map` 0,457 (Abstand 0,007). Bilanz: 2 getroffen, 1 verfehlt.

**Schluss.** (a) Das Ergebnis „beides zugleich“ ist wiederholbar: Eine zweite Suche landet bei derselben
Validierung (0,53 gegen 0,54) und löst wieder beide ausgelassenen Aufgaben. Die Gewichtung zwischen Kopf und
Innen ist aber eine Sache der Saat: `pos_map_s1` ist auf den Kopf-Aufgaben besser (layer_s@25k xmFF 0,68 gegen
0,58; layer_s xmFF 0,80 gegen 0,52, so gut wie rls_rf), im Inneren schwächer und bleibt dort nach 20 Updates
stehen (prev 0,60 → 0,63 nach 200, `pos_map` 0,66 → 0,80). (b) hier_s im Meta-Training hilft auf hier_s im
Inneren nicht: prev bleibt bei allen vier Regeln bei 0,07 (dfa 0,10, Backprop 0,59). ES gibt das Innere von
hier_s schon früh auf und zahlt dafür im Inneren von layer_s@25k (prev 0,66 / 0,60 → 0,41 / 0,45). Innerhalb
dieser Regel-Familie (lokale Telemetrie, Fehler-Faktor, Hebb-Term, Schrittweite je Abbildung) gibt es für beide
Architekturen offenbar keine gemeinsame Innen-Regel, oder ES findet sie in 300 Generationen nicht. Am Kopf
ändert das Training auf hier_s nichts Messbares: Die Gewinne auf hier_s xmFF / xm0F hat auch `pos_map_s1`, das
hier_s nie gesehen hat. (c) Die Rollen-Kennung ist auf den Meta-Train-Aufgaben gleich gut lernbar, auf dem
breiteren layer_s im Inneren etwas besser als `arch_map` (prev 0,68 gegen 0,54; 4 Episoden, `arch_map` mit großer
Spanne 0,17–0,72). Sie hat aber einen neuen Fehler, den die Validierung nicht zeigt: Auf der ausgelassenen
Aufgabe xmFF fällt sie auf layer_s@25k schon nach dem ersten Update auf 0,00 und bleibt dort; auf hier_s erholt
sie sich nach dem ersten Update. Die Probe verortet das im inneren Hebb-Term (auf null gesetzt: 0,00 → 0,67).
Vermutung, nicht geprüft: Die Rollen-Kennung ist stetig (Werte bis |2,88|), und das MLP interpoliert zwischen
den Rollen auf eine Weise, die auf einer neuen Telemetrie-Lage kippt; mit dem Namen als One-hot gibt es diese
Zwischenwerte nicht. (d) Damit ist die Antwort auf die Frage aus der Positions-Ablation vorläufig: Für ein
Netz derselben Architektur reicht ein geteilter Teacher mit Namen der Schicht. Für eine zweite Architektur
reicht weder mehr Meta-Training noch eine Rollen-Kennung; das Innere der Hierarchie bleibt für diese Regel-Familie
unerreicht. Die saubere nächste Frage ist, ob ES auf hier_s *allein* überhaupt eine Innen-Regel findet.

**Belege.** `results/teacher.jsonl` (Zeilen `pos_map_s1`, `arch_map`, `arch_role`; je Generation, Validierung je
Fall und je Netz, letzte Zeile mit θ und bestem θ), `results/phase_d_arch.jsonl` (184 Zeilen), Bezugswerte aus
`results/phase_d_test.jsonl` und `results/phase_d_transfer.jsonl` (Seeds 5–6). Ausführlich: `PHASE_D.md`
Abschnitt 5.6.

## 2026-11-25 — Phase D, ES auf hier_s allein: auch ohne Zielkonflikt findet ES für die Hierarchie keine Innen-Regel; am Kopf ist die Regel dort die beste bisher, überträgt sich aber nicht zurück auf layer_s

**Frage.** Gibt es für die Hierarchie hier_s in der bisherigen Regel-Familie überhaupt eine Innen-Regel, wenn ES
nur auf hier_s sucht (kein Zielkonflikt mit layer_s@25k wie in `arch_map`)?

**Gemacht.** ES-Job `20261125-075342-hier_map` (Commit d0357f2), Worker zuerst mit 6 Prozessen, ab 17:11 nach
Neustart mit 14 Prozessen; der Lauf setzte am Prüfpunkt Generation 180 fort (`resume hier_map at gen 180` im
Log; 301 Zeilen, jede Generation genau einmal). Rechenzeit 265 min nach dem Neustart, davor etwa 9 h (etwa
190 s je Generation mit 6 Prozessen). Meta-Test: `20261125-214404-ev_hier_hier_s`, `-214405-ev_hier_layer_s25k`,
`-214406-ev_hier_layer_s` (Fälle prev, prev2, xmFF, xm0F; Seeds 5–6, je 2 Ziehungen, k = 64). Vorhersage vor dem
Lauf (wörtlich aus „Laufend / offen“):

> - Phase D, ES auf hier_s allein (Auftrag Nutzer 2026-11-25, `PHASE_D.md` Abschnitt 8, Punkt 1): Gibt es für
>   die Hierarchie in dieser Regel-Familie überhaupt eine Innen-Regel? Lauf `hier_map`: `teacher.py run --pos map
>   --models hier_s`, 300 Generationen, σ 0,1, lr 0,05, ES-Saat 0, Meta-Train-Aufgaben und Seeds 0–2 wie
>   bisher, Episoden nur aus hier_s. Neu im Code (Commit nach diesem Eintrag): ein unterbrochener ES-Lauf setzt
>   nach einem Neustart des Workers am letzten Prüfpunkt (alle 10 Generationen) fort; geprüft bitgleich zu einem
>   ununterbrochenen Lauf (20 Generationen, Unterbrechung bei 10). Worker mit 6 Prozessen, etwa 150 s je
>   Generation, also etwa 13 h; nach einem Neustart mit 14 Prozessen schneller. Danach Meta-Test auf Seeds 5–6
>   (prev, prev2, xmFF, xm0F, k = 64) auf hier_s, layer_s@25k und layer_s. Bezug hier_s nach 20 Updates:
>   prev dfa 0,10, grad 0,59, rls_rf 0,13, `arch_map` 0,07; xmFF delta_head 0,24, rls_rf 0,57, `arch_map` 0,61;
>   xm0F delta_head 0,51, rls_rf 0,70, `arch_map` 0,77; Validierung `arch_map` auf hier_s 0,38.
>   **Vorhersage vor dem Lauf (2026-11-25):** (1) Auch allein auf hier_s findet ES keine Innen-Regel: Meta-Test
>   hier_s prev nach 20 Updates ≤ 0,15 (dfa 0,10, Backprop 0,59). (2) Die Kopf-Aufgaben lernt die Regel wie
>   bisher: hier_s xmFF ≥ 0,55 und xm0F ≥ 0,70 nach 20 Updates. (3) Validierung (nur hier_s) am Ende zwischen
>   0,35 und 0,45. Trifft (1) nicht zu, ist die Hierarchie für diese Familie erreichbar und das Problem in
>   `arch_map` war der Zielkonflikt zwischen den Architekturen; trifft (1) zu, fehlt dem Teacher eine Eingabe.

**Ergebnis.** Validierung (nur hier_s, Seeds 0–2): Generation 40 0,36, danach langsam auf 0,41 bei Generation
300 (prev2 durchweg 0,03–0,05, prev3 0,02–0,03; xm0F 0,62 → 0,69, xmA5 0,66, xm33 0,60). Meta-Test, Testwertung
nach 20 (200) Updates, 4 Episoden je Feld:

| Netz, Fall | dfa@task | grad@task | delta_head@task | rls_rf@task | `arch_map` | `hier_map` |
|---|---|---|---|---|---|---|
| hier_s, prev | 0,10 (0,60) | 0,59 (0,75) | 0,03 (0,10) | 0,13 | 0,07 (0,07) | **0,13 (0,14)** |
| hier_s, prev2 | 0,06 (0,53) | 0,46 (0,66) | 0,02 (0,05) | 0,07 | 0,03 (0,04) | 0,07 (0,08) |
| hier_s, xmFF | 0,01 | 0,01 | 0,24 (0,63) | 0,57 | 0,61 (0,63) | **0,71 (0,71)** |
| hier_s, xm0F | 0,07 | 0,04 | 0,51 (0,79) | 0,70 | 0,77 (0,77) | 0,78 (0,77) |
| layer_s@25k, prev | 0,16 (0,75) | 0,79 (0,95) | 0,05 (0,16) | 0,24 | 0,41 (0,43) | 0,13 (0,51) |
| layer_s@25k, prev2 | 0,20 (0,76) | 0,79 (0,97) | 0,04 (0,10) | 0,14 | 0,48 (0,50) | 0,03 (0,71) |
| layer_s@25k, xmFF | 0,01 | 0,01 | 0,45 (0,71) | 0,57 | 0,60 (0,62) | **0,00 (0,01)** |
| layer_s@25k, xm0F | 0,01 | 0,05 | 0,67 (0,83) | 0,62 | 0,79 (0,78) | 0,73 (**0,00**) |
| layer_s, prev | 0,30 (0,78) | 0,81 (0,95) | 0,02 (0,10) | 0,18 | 0,54 (0,58) | 0,07 (0,55) |
| layer_s, prev2 | 0,25 (0,78) | 0,90 (0,99) | 0,01 (0,07) | 0,13 | 0,42 (0,44) | 0,04 (0,57) |
| layer_s, xmFF | 0,01 | 0,01 | 0,32 (0,82) | 0,79 | 0,67 (0,69) | **0,01 (0,00)** |
| layer_s, xm0F | 0,01 | 0,04 | 0,60 (0,92) | 0,90 | 0,90 (0,90) | 0,93 (0,94) |

**Vergleich mit der Vorhersage.** (1) Getroffen: hier_s prev 0,13 nach 20 Updates (≤ 0,15; dfa 0,10, Backprop
0,59). (2) Getroffen: hier_s xmFF 0,71 (≥ 0,55), xm0F 0,78 (≥ 0,70). (3) Getroffen: Validierung 0,41 (zwischen
0,35 und 0,45). Bilanz: 3 getroffen.

**Schluss.** (a) Auch ohne Zielkonflikt findet ES für das Innere der Hierarchie keine Regel: prev 0,13 liegt
knapp über dfa (0,10), weit unter Backprop (0,59), und die Validierung auf prev2 / prev3 bewegt sich in 300
Generationen nicht. Der Unterschied zu `arch_map` (0,07) ist nur, dass die Regel das Innere nicht mehr unter
dfa drückt. Damit liegt es nicht am Meta-Training, sondern an der Regel-Familie: Dem Teacher fehlt für die
Hierarchie eine Eingabe oder eine Form des Updates. Kandidaten (ungeprüft): welcher der 6 Aufrufe je Update
gerade läuft (die Telemetrie mittelt bisher über die Aufrufe einer Abbildung), oder ein Fehler je Aufruf statt
je Abbildung. (b) Am Kopf ist `hier_map` auf hier_s die beste Regel bisher (xmFF 0,71 gegen rls_rf 0,57 und
`arch_map` 0,61). (c) Die Bindung an die Architektur gilt in beide Richtungen, und für `hier_map` sogar am
Kopf: Auf layer_s@25k und layer_s fällt xmFF auf 0,00 bis 0,01, und auf layer_s@25k kippt xm0F nach 20 Updates
(0,73 → 0,00 nach 200). `pos_map` (auf layer_s@25k gefunden) hatte seinen Kopf-Teil noch auf hier_s übertragen.
Warum die hier_s-Regel auf den layer-Netzen instabil ist, ist nicht geprüft. (d) Zusammen mit dem Eintrag
davor: Für eine Architektur findet ES eine Regel, die Kopf- und, bei layer_s, Innen-Aufgaben in 20 Updates
lernt; über die Grenze der Architektur trägt höchstens der Kopf-Teil und das nur in eine Richtung.

**Belege.** `results/teacher.jsonl` (Zeilen `hier_map`), `results/phase_d_arch.jsonl` (+48 Zeilen, jetzt 232),
Bezugswerte wie im Eintrag davor. Ausführlich: `PHASE_D.md` Abschnitt 5.7.

## 2026-11-26 — Phase D, Telemetrie je Aufruf auf hier_s: auch mit Index des Aufrufs und eigener Rückprojektion je Aufruf findet ES keine Innen-Regel für die Hierarchie; am Kopf etwas schwächer als `hier_map`

**Frage.** Fehlt dem Teacher für das Innere der Hierarchie die Unterscheidung der 6 Aufrufe von fc1 / fc2 je
Update? Bisher bekam jeder Aufruf einer Abbildung denselben rückprojizierten Fehler und keine Kennung des Aufrufs.

**Gemacht.** Neue Variante `--pos call` (Commit bf3355c): Index des Aufrufs als zehnte Eingabe des Teachers
(485 Parameter) und eigene feste Zufalls-Rückprojektion je Aufruf. ES-Job `20261125-220255-hier_call`
(200 Generationen, nur hier_s, sonst wie `hier_map`; Worker mit 14 Prozessen, 22:03 bis 05:22, etwa 2,2 min je
Generation). Meta-Test: `20261126-052317-ev_call_hier_s`, `-052318-ev_call_layer_s25k`, `-052319-ev_call_layer_s`
(Commit 23e4ec0; prev, prev2, xmFF, xm0F; Seeds 5–6, je 2 Ziehungen, k = 64). Lokal vor dem Lauf, nicht Teil der
Vorhersage: dfa mit Rückprojektion je Aufruf (θ = 0 der neuen Variante) auf hier_s prev, Seeds 5–6 × 2:
0,11 nach 20 Updates, 0,70 nach 200 (dfa wie bisher 0,10 / 0,60). Vorhersage vor dem Lauf (wörtlich aus
„Laufend / offen“):

> - Phase D, Telemetrie je Aufruf auf hier_s (Auftrag Nutzer 2026-11-25, `PHASE_D.md` Abschnitt 8, Punkt 1).
>   Befund vorab beim Bau: In beiden Netzen sind die Aufrufe einer Abbildung die Schritte der Rekurrenz
>   (layer_s@25k 4 × fc1 / fc2, hier_s 6 ×), und alle Aufrufe einer Abbildung bekamen bisher *denselben*
>   rückprojizierten Fehler d = e B (eine Zufallsmatrix je Abbildung, wie bei `dfa`); der Teacher konnte die
>   Aufrufe nur über Aktivität und Eingang unterscheiden. Neue Variante `--pos call` (Commit nach diesem Eintrag):
>   wie `map`, dazu (i) der Index des Aufrufs (0 … 1) als zehnte Eingabe des Teachers (485 statt 469 Parameter)
>   und (ii) eine eigene feste Zufalls-Rückprojektion je Aufruf. Bei θ = 0 ist das dfa mit Rückprojektion je
>   Aufruf, nicht mehr bitgleich zu dfa@task (alle alten Varianten weiter bitgleich, `check`). Beide Änderungen
>   zugleich, weil nur eine Nacht Rechenzeit da ist; trägt es, folgt die Trennung. Lauf `hier_call`: `--pos call
>   --models hier_s`, 200 Generationen (Worker mit 14 Prozessen bis 7 Uhr; `hier_map` stand bei Generation 200
>   auf Validierung 0,40, prev2 0,04), sonst wie `hier_map`. Danach Meta-Test wie bei `hier_map`. Bezug hier_s
>   nach 20 Updates: prev dfa 0,10, grad 0,59, `hier_map` 0,13; xmFF `hier_map` 0,71.
>   **Vorhersage vor dem Lauf (2026-11-25):** (1) Die Telemetrie je Aufruf erschließt das Innere von hier_s
>   nicht: Meta-Test prev nach 20 Updates ≤ 0,20 und Validierung prev2 ≤ 0,10 bei Generation 200. Begründung:
>   Die fehlende Unterscheidung der Aufrufe erklärt nicht, warum schon auf layer_s@25k (auch 4 gleiche Aufrufe)
>   eine Innen-Regel gefunden wurde. (2) Die Kopf-Aufgaben bleiben wie bei `hier_map`: xmFF ≥ 0,60, xm0F ≥ 0,70
>   nach 20 Updates. (3) ES nutzt den Index des Aufrufs: Die Gewichte der zehnten Eingabe in W1 sind am Ende im
>   Betrag größer als das Mittel der übrigen sechs Kennungs- und Rundfunk-Zeilen.

**Ergebnis.** Validierung (nur hier_s, Seeds 0–2) bei Generation 200: 0,405, prev2 0,049, prev3 0,035
(`hier_map` bei Generation 200: 0,399, prev2 0,041). Der Verlauf ist bis auf einen langsameren Start
(Generation 20: 0,08 gegen 0,16) gleich. Meta-Test, Testwertung nach 20 (200) Updates, 4 Episoden je Feld:

| Netz, Fall | dfa@task | grad@task | rls_rf@task | `hier_map` | `hier_call` |
|---|---|---|---|---|---|
| hier_s, prev | 0,10 (0,60) | 0,59 (0,75) | 0,13 | 0,13 (0,14) | 0,10 (0,12) |
| hier_s, prev2 | 0,06 (0,53) | 0,46 (0,66) | 0,07 | 0,07 (0,08) | 0,06 (0,08) |
| hier_s, xmFF | 0,01 | 0,01 | 0,57 | **0,71 (0,71)** | 0,58 (0,62) |
| hier_s, xm0F | 0,07 | 0,04 | 0,70 | 0,78 (0,77) | 0,78 (0,77) |
| layer_s@25k, prev | 0,16 (0,75) | 0,79 (0,95) | 0,24 | 0,13 (0,51) | 0,17 (0,41) |
| layer_s@25k, prev2 | 0,20 (0,76) | 0,79 (0,97) | 0,14 | 0,03 (0,71) | 0,14 (0,38) |
| layer_s@25k, xmFF | 0,01 | 0,01 | 0,57 | 0,00 (0,01) | 0,01 (0,00) |
| layer_s@25k, xm0F | 0,01 | 0,05 | 0,62 | 0,73 (0,00) | 0,33 (0,01) |
| layer_s, prev | 0,30 (0,78) | 0,81 (0,95) | 0,18 | 0,07 (0,55) | 0,21 (0,27) |
| layer_s, prev2 | 0,25 (0,78) | 0,90 (0,99) | 0,13 | 0,04 (0,57) | 0,14 (0,22) |
| layer_s, xmFF | 0,01 | 0,01 | 0,79 | 0,01 (0,00) | 0,01 (0,01) |
| layer_s, xm0F | 0,01 | 0,04 | 0,90 | 0,93 (0,94) | 0,90 (0,90) |

Gewichte der ersten Teacher-Schicht (bestes θ), mittlerer Betrag der Änderung gegenüber dem Start je
Eingabe-Zeile: Index des Aufrufs 0,63; Mittel der sechs Kennungs- und Rundfunk-Zeilen 0,53 (S 0,75, ΔS 0,51,
t 0,54, fc1 0,33, fc2 0,42, Kopf 0,61). Absolute Beträge: 0,64 gegen 0,58.

**Vergleich mit der Vorhersage.** (1) Getroffen: hier_s prev 0,10 nach 20 Updates (≤ 0,20), Validierung prev2
0,049 (≤ 0,10). (2) Nicht getroffen: xmFF 0,58 liegt unter 0,60 (xm0F 0,78 ≥ 0,70 getroffen). (3) Getroffen,
aber knapp: Die Zeile des Aufruf-Index ist größer als das Mittel der übrigen sechs (0,64 gegen 0,58; Änderung
0,63 gegen 0,53), aber nicht die größte (S 0,76). Bilanz: 2 von 3 getroffen.

**Schluss.** (a) Die fehlende Unterscheidung der Aufrufe ist nicht der Grund, warum ES für die Hierarchie keine
Innen-Regel findet: Mit Index und eigener Rückprojektion je Aufruf bleibt prev nach 20 Updates auf dfa-Niveau
(0,10), die Validierung auf prev2 bewegt sich in 200 Generationen nicht. Eine Trennung der beiden Änderungen
lohnt deshalb nicht. (b) Die Rückprojektion je Aufruf hilft dfa auf hier_s nur über lange Zeit (0,70 statt
0,60 nach 200 Updates, nach 20 gleich). Die gefundene Regel nutzt das nicht, sie hält das Innere still
(0,12 nach 200). ES sieht in der Fitness nur 20 Updates; ein Innen-Gewinn, der erst nach 100 und mehr Updates
entsteht, ist für ES unsichtbar. Für die Hierarchie wird damit der längere Trainings-Horizont (`PHASE_D.md`
Abschnitt 8, Punkt 2) zum nächsten Kandidaten. (c) Am Kopf kostet die neue Variante: xmFF 0,58 gegen 0,71 bei
`hier_map` (die 4 Episoden 0,52–0,62 gegen 0,67–0,74), xm0F gleich. Ob das an der Variante oder an nur 200
statt 300 Generationen liegt, ist offen; die Validierung auf xm0F / xmA5 / xm33 ist bei Generation 200 gleich.
(d) Auf den layer-Netzen bleibt die Regel wie `hier_map` ohne Kopf-Übertragung (xmFF 0,00–0,01).

**Belege.** `results/teacher.jsonl` (Zeilen `hier_call`, 201), `results/phase_d_arch.jsonl` (+48 Zeilen,
jetzt 280), Bezugswerte wie im Eintrag davor. Ausführlich: `PHASE_D.md` Abschnitt 5.8.

## 2026-11-26 — Phase D, längerer Trainings-Horizont auf hier_s: mit Horizont 100 lernt die Regel das Innere der Hierarchie zum ersten Mal über dfa hinaus (bis 50 Updates), bleibt dann aber bei 0,26–0,30 stehen; der Kopf wird dabei besser

**Frage.** Findet ES für das Innere von hier_s eine Regel, wenn die Fitness 100 statt 20 Updates sieht?

**Gemacht.** `teacher.py run --horizon / --init` (Commit df7ebce). ES-Job `20261126-064618-hier_h100`
(`--pos map --models hier_s --horizon 100 --init hier_map`, 60 Generationen; Worker mit 6 Prozessen, 06:46 bis
21:17, 871 min, etwa 14,5 min je Generation). Meta-Test `20261126-212646-ev_h100_hier_s` (Commit 6fea877;
prev, prev2, xmFF, xm0F; Seeds 5–6, je 2 Ziehungen, k = 64). Vorhersage vor dem Lauf (wörtlich aus
„Laufend / offen“):

> - Phase D, längerer Trainings-Horizont auf hier_s (Auftrag Nutzer 2026-11-26, `PHASE_D.md` Abschnitt 8,
>   Punkt 2). Auf hier_s lernt schon dfa das Innere erst spät (prev 0,10 / 0,22 / 0,47 / 0,60 nach 20 / 50 /
>   100 / 200 Updates; Backprop 0,59 / 0,69 / 0,72 / 0,75), die Fitness sah bisher nur 20 Updates. Neu im Code
>   (Commit nach diesem Eintrag): `teacher.py run --horizon H` (Updates je Fitness-Episode; der Zeit-Eingang
>   t / T des Teachers läuft über die H Updates von 0 bis 1; Fitness = Mittel der Testwertung nach H/10, H/5,
>   H/2 und H Updates) und `--init NAME` (Start vom besten θ eines früheren Laufs); `eval` nimmt den Horizont
>   der Regel mit. Voreinstellung unverändert (`check` weiter bitgleich). Lauf `hier_h100`: `--pos map --models
>   hier_s --horizon 100 --init hier_map`, 60 Generationen, sonst wie `hier_map` (σ 0,1, lr 0,05, Population 48,
>   8 Episoden). Warmstart, weil der Worker nur einen Tag mit 6 Prozessen läuft (lokal gemessen etwa 12 s je
>   Episode, also etwa 13 min je Generation); `hier_map` brauchte von null etwa 40 Generationen bis zum Kopf.
>   `hier_map` drückt die Schrittweite im Inneren (p fc1 −3,0, fc2 −4,2, Kopf +1,7); ES kann sie wieder heben.
>   Danach Meta-Test wie bisher (hier_s, Schritte bis 200).
>   **Vorhersage vor dem Lauf (2026-11-26):** (1) Mit Horizont 100 holt ES auf hier_s wenigstens das dfa-Innere
>   zurück: Meta-Test prev nach 100 Updates ≥ 0,40 (dfa 0,47, `hier_map` 0,13). (2) Eine schnelle Innen-Regel
>   entsteht nicht: prev nach 20 Updates ≤ 0,20 und nach 100 Updates ≤ 0,60 (Backprop 0,59 / 0,72). (3) Der Kopf
>   bleibt: xmFF ≥ 0,60 und xm0F ≥ 0,70 nach 20 Updates. Trifft (1) nicht zu, hält der Warmstart die Suche in
>   der Lösung „innen aus“ fest, oder dfa-artiges Lernen schadet in der Fitness dem Kopf mehr, als es innen bringt.

**Ergebnis.** Validierung (hier_s, Seeds 0–2, Horizont 100) steigt ohne Pause von 0,43 (Generation 0, θ von
`hier_map`) auf 0,49 bei Generation 60; prev2 0,085 → 0,195, prev3 0,055 → 0,192, xm0F 0,69 → 0,73. Schrittweite
im Inneren: p fc1 −3,03 → −1,76, fc2 −4,18 → −4,56, Kopf 1,74 → 1,25. Meta-Test, Testwertung nach 20 / 50 / 100 /
200 Updates, 4 Episoden je Feld:

| Fall | dfa@task | grad@task | `hier_map` | `hier_h100` |
|---|---|---|---|---|
| prev | 0,10 / 0,22 / 0,47 / 0,60 | 0,59 / 0,69 / 0,72 / 0,75 | 0,13 / 0,13 / 0,13 / 0,14 | **0,20 / 0,26 / 0,26 / 0,30** |
| prev2 | 0,06 / 0,18 / 0,37 / 0,53 | 0,46 / 0,61 / 0,64 / 0,66 | 0,07 / 0,07 / 0,07 / 0,08 | 0,05 / **0,26** / 0,28 / 0,31 |
| xmFF | 0,01 / 0,02 / 0,02 / 0,01 | 0,01 / 0,01 / 0,01 / 0,02 | 0,71 / 0,71 / 0,71 / 0,71 | **0,74 / 0,74 / 0,74 / 0,74** |
| xm0F | 0,07 / 0,02 / 0,02 / 0,01 | 0,04 / 0,04 / 0,05 / 0,05 | 0,78 / 0,78 / 0,77 / 0,77 | **0,84 / 0,84 / 0,83 / 0,83** |

prev nach 20 Updates je Episode 0,16 / 0,22 / 0,18 / 0,23 (Mittel 0,198), nach 100 Updates 0,34 / 0,27 / 0,21 /
0,24.

**Vergleich mit der Vorhersage.** (1) Nicht getroffen: prev nach 100 Updates 0,26, nicht ≥ 0,40 (dfa 0,47).
(2) Getroffen, knapp: prev nach 20 Updates 0,198 (≤ 0,20), nach 100 Updates 0,26 (≤ 0,60). (3) Getroffen:
xmFF 0,74, xm0F 0,84. Bilanz: 2 von 3 getroffen.

**Schluss.** (a) Der kurze Horizont war ein Teil des Problems: Zum ersten Mal lernt eine gefundene Regel das
Innere von hier_s über dfa hinaus, solange das Lernen kurz ist (prev 0,20 nach 20 Updates, dfa 0,10; prev2 0,26
nach 50, dfa 0,18). ES hat dafür die Schrittweite von fc1 um das 3,5-Fache geöffnet (p −3,0 → −1,8), nicht die
von fc2; wie auf layer_s sitzt der Innen-Teil in der ersten Abbildung. (b) Die Regel bleibt dann aber stehen:
von 50 bis 200 Updates nur 0,26 → 0,30, während dfa auf 0,60 weiterläuft. Es entsteht ein Plateau, keine
anhaltende Innen-Regel; jenseits von etwa 60 Updates ist dfa besser. Vorhersage (1) hatte angenommen, ES hole
zuerst das dfa-Verhalten zurück; stattdessen findet ES einen schnellen, früh gesättigten Innen-Teil. (c) Der Kopf
leidet nicht, er wird besser: xmFF 0,74 und xm0F 0,84 sind die besten Kopf-Werte auf hier_s bisher. (d) Die
Suche ist nicht fertig: Die Validierung steigt bis zur letzten Generation (prev2 / prev3 in 60 Generationen
etwa verdoppelt). Ob eine Fortsetzung das Plateau hebt oder nur früher erreicht, ist offen. Offen bleibt auch,
ob der Warmstart von `hier_map` die Suche einschränkt.

**Belege.** `results/teacher.jsonl` (Zeilen `hier_h100`, 61), `results/phase_d_arch.jsonl` (+16 Zeilen, jetzt
296). Ausführlich: `PHASE_D.md` Abschnitt 5.9.

## 2026-11-27 — Phase D, Fortsetzung von `hier_h100`: das Plateau im Inneren der Hierarchie steigt (prev 0,39 nach 100 Updates, dfa 0,47), der schnelle Teil nach 20 Updates geht dafür zurück; die Validierung ist für Innen-Aufgaben auf hier_s nicht genau reproduzierbar

**Frage.** Hebt eine längere Suche das Plateau des Innen-Teils auf hier_s, oder erreicht sie es nur früher?

**Gemacht.** ES-Job `20261126-220116-hier_h100b` (Commit 6a05511; `--pos map --models hier_s --horizon 100
--init hier_h100`, 60 Generationen; Worker mit 6 Prozessen, 22:01 bis 09:16, 675 min, etwa 11 min je
Generation; ohne Neustart durchgelaufen). Meta-Test `20261127-092510-ev_h100b_hier_s` (Commit 7c89e0c; prev,
prev2, xmFF, xm0F; Seeds 5–6, je 2 Ziehungen, k = 64). Vorhersage vor dem Lauf (wörtlich aus „Laufend / offen“):

> - Phase D, Fortsetzung von `hier_h100` (Auftrag Nutzer 2026-11-26, `PHASE_D.md` Abschnitt 8, Punkt 2): Hebt
>   eine längere Suche das Plateau des Innen-Teils auf hier_s (prev 0,26 / 0,30 nach 100 / 200 Updates), oder
>   erreicht sie es nur früher? Lauf `hier_h100b`: `--pos map --models hier_s --horizon 100 --init hier_h100`,
>   60 Generationen, sonst wie `hier_h100` (Start vom besten θ, Adam-Momente neu bei null). Worker mit 6
>   Prozessen über Nacht, etwa 14,5 min je Generation; um 7 Uhr startet der Nutzer den Worker neu, der Lauf
>   setzt am letzten Prüfpunkt fort (etwa Generation 30–40). Danach Meta-Test auf hier_s wie bei `hier_h100`.
>   Bezug `hier_h100`: Validierung 0,49 (prev2 0,195, prev3 0,192); Meta-Test prev 0,20 / 0,26 / 0,26 / 0,30 nach
>   20 / 50 / 100 / 200 Updates, prev2 0,05 / 0,26 / 0,28 / 0,31, xmFF 0,74, xm0F 0,84; dfa prev 0,10 / 0,22 /
>   0,47 / 0,60.
>   **Vorhersage vor dem Lauf (2026-11-26):** (1) Die Validierung steigt weiter: am Ende ≥ 0,51. (2) Das Plateau
>   steigt, bleibt aber unter dfa auf lange Sicht: Meta-Test prev nach 100 Updates ≥ 0,32 und nach 200 Updates
>   ≤ 0,50. (3) Der Kopf bleibt: xmFF ≥ 0,70 und xm0F ≥ 0,80 nach 20 Updates.

**Ergebnis.** Validierung 0,476 (Generation 0) → 0,511 (Generation 50 und 60); prev2 0,186 → 0,247, prev3
0,140 → 0,223, xm0F 0,73, xmA5 0,70, xm33 0,66. Schrittweiten p fc1 −1,71 → −1,61, fc2 −4,61 → −4,81, Kopf
1,30 → 0,89. Meta-Test auf hier_s, Testwertung nach 20 / 50 / 100 / 200 Updates, 4 Episoden je Feld:

| Fall | dfa@task | grad@task | `hier_h100` | `hier_h100b` |
|---|---|---|---|---|
| prev | 0,10 / 0,22 / 0,47 / 0,60 | 0,59 / 0,69 / 0,72 / 0,75 | 0,20 / 0,26 / 0,26 / 0,30 | 0,13 / 0,28 / **0,39 / 0,42** |
| prev2 | 0,06 / 0,18 / 0,37 / 0,53 | 0,46 / 0,61 / 0,64 / 0,66 | 0,05 / 0,26 / 0,28 / 0,31 | 0,05 / **0,34 / 0,38** / 0,40 |
| xmFF | 0,01 / 0,02 / 0,02 / 0,01 | 0,01 / 0,01 / 0,01 / 0,02 | **0,74 / 0,74 / 0,74 / 0,74** | 0,68 / 0,70 / 0,72 / 0,72 |
| xm0F | 0,07 / 0,02 / 0,02 / 0,01 | 0,04 / 0,04 / 0,05 / 0,05 | 0,84 / 0,84 / 0,83 / 0,83 | 0,85 / 0,84 / 0,84 / 0,82 |

prev nach 100 Updates je Episode 0,33 / 0,35 / 0,28 / 0,59; nach 20 Updates 0,19 / 0,07 / 0,14 / 0,12.

Reproduzierbarkeit: Für dasselbe θ (bestes θ von `hier_h100`) gibt die Validierung 0,4879 (Worker, `hier_h100` Generation 60),
0,4757 (Worker, `hier_h100b` Generation 0) und 0,4854 (lokal). Die Kopf-Aufgaben stimmen dabei bitgleich überein,
nur die Innen-Aufgaben weichen ab (prev2 0,195 / 0,186 / 0,183, prev3 0,192 / 0,140 / 0,191). Ursache nicht
geprüft; vermutet: kleine Rechenunterschiede, die 100 Updates Innen-Lernen auf hier_s verstärken (geprüft nur,
dass eine Episode auf layer_s@25k mit 20 Updates im selben Prozess unabhängig von der Reihenfolge gleich ist).

**Vergleich mit der Vorhersage.** (1) Getroffen, aber nicht belastbar: Validierung 0,511 (≥ 0,51); der Abstand
liegt innerhalb der oben gemessenen Abweichung für dasselbe θ (0,012). (2) Getroffen: prev nach 100 Updates
0,39 (≥ 0,32), nach 200 Updates 0,42 (≤ 0,50). (3) Nicht getroffen: xmFF 0,68 nach 20 Updates (Vorhersage
≥ 0,70); xm0F 0,85 (≥ 0,80) getroffen. Bilanz: 2 von 3 getroffen.

**Schluss.** (a) Das Plateau steigt: prev nach 100 Updates 0,26 → 0,39, prev2 0,28 → 0,38 (dfa 0,47 / 0,37).
Auf prev2 ist die Regel jetzt nach 50 Updates fast doppelt so gut wie dfa (0,34 gegen 0,18) und nach 100
gleichauf. Nach 200 Updates bleibt sie unter dfa (prev 0,42 gegen 0,60) und weit unter Backprop. (b) Den
Gewinn bezahlt die Regel mit dem schnellen Teil (prev nach 20 Updates 0,20 → 0,13) und etwas Kopf (xmFF
0,74 → 0,68); ES verschiebt das Lernen innerhalb des Horizonts nach hinten, wie es die Fitness (Mittel nach
10, 20, 50, 100) erlaubt. (c) Die Validierung stieg in der zweiten Hälfte kaum noch (0,511 bei 50 und 60),
und ihre Messgenauigkeit für die Innen-Aufgaben liegt bei etwa ±0,01; mehr Generationen versprechen wenig.
(d) Für Vergleiche auf hier_s mit 100 Updates sind Unterschiede der Innen-Werte unter etwa 0,05 nicht sicher;
die Ursache der Abweichung ist offen. (e) Gesamtbild für die Hierarchie: Mit Horizont 100 findet ES eine
Innen-Regel, die bis 100 Updates mit dfa mithält oder es schlägt und dabei den Kopf gut lernt; eine schnelle
Innen-Regel wie auf layer_s (0,66 nach 20) gibt es für hier_s in dieser Familie nicht.

**Belege.** `results/teacher.jsonl` (Zeilen `hier_h100b`, 61), `results/phase_d_arch.jsonl` (+16 Zeilen, jetzt
312). Ausführlich: `PHASE_D.md` Abschnitt 5.9.

## 2026-11-27 — Phase D, Ursache der Messabweichung auf hier_s: gerundetes θ auf dem Worker und ein Innen-Lernen, das auf winzige Änderungen von θ stark reagiert; mit 12 Episoden trägt der Gewinn der Fortsetzung knapp

**Frage.** Warum gibt die Validierung für dasselbe θ auf hier_s verschiedene Werte, und trägt der Unterschied
zwischen `hier_h100` und `hier_h100b` trotzdem?

**Gemacht.** Lokale Prüfung (Skript außerhalb des Repos), Korrektur im Code (Commit 6079f25), Meta-Test beider
Regeln mit 6 Ziehungen: Job `20261127-101513-ev_noise_h100` (prev, prev2; Seeds 5–6; k = 64; 12 Episoden je
Feld, die 4 Episoden des bisherigen Meta-Tests eingeschlossen). Vorhersage und Vorab-Befund vor dem Lauf
(wörtlich aus „Laufend / offen“):

> - Phase D, Ursache der Messabweichung auf hier_s (Auftrag Nutzer 2026-11-27, `PHASE_D.md` 5.9). Vorab lokal
>   geklärt (Skript außerhalb des Repos, 12 Innen-Episoden der Validierung von `hier_h100`, Horizont 100):
>   (i) Mit demselben θ sind die Episoden lokal bitgleich, unabhängig von Reihenfolge, Prozess und Pool (frischer
>   Pool, umgekehrte Reihenfolge, nacheinander im Hauptprozess mit einem Thread). (ii) Der Worker legt für jeden
>   Job eigene Prüfpunkte an; `--init` und `eval` lesen θ dort deshalb aus `results/teacher.jsonl`, wo θ auf 10⁻⁶
>   gerundet war. Diese Rundung (höchstens 5·10⁻⁷) ändert einzelne Episoden um bis zu 0,09 (Streuung der
>   Differenz etwa 0,05), das Mittel von prev2 um 0,01. Das Innen-Lernen über 100 Updates auf hier_s ist also
>   empfindlich gegen winzige Änderungen von θ. (iii) Mit exakt demselben θ weicht der Worker vom lokalen PC noch
>   ab (0,4879 gegen 0,4854); vermutlich andere Rechenwege der CPU, nicht geprüft. Neu im Code (Commit nach diesem
>   Eintrag): θ in `results/teacher.jsonl` exakt (float32) statt gerundet. Prüfung, ob der Unterschied
>   `hier_h100` → `hier_h100b` trotz der Empfindlichkeit trägt: Meta-Test beider Regeln auf hier_s mit 6 statt 2
>   Ziehungen (prev, prev2; Seeds 5–6, also 12 Episoden je Feld), in `results/phase_d_noise.jsonl`.
>   **Vorhersage vor dem Lauf (2026-11-27):** (1) Der Unterschied trägt: prev nach 100 Updates bei `hier_h100b`
>   um mindestens 0,08 über `hier_h100` (mit 4 Episoden: 0,39 gegen 0,26). (2) Die Streuung je Episode nach 100
>   Updates (Standardabweichung über die 12 Episoden) ist bei beiden Regeln ≥ 0,05.

**Ergebnis.** Meta-Test auf hier_s, 12 Episoden je Feld (Mittel):

| Fall, Regel | nach 20 | nach 50 | nach 100 | nach 200 | Streuung je Episode nach 100 |
|---|---|---|---|---|---|
| prev, `hier_h100` | 0,15 | 0,27 | 0,30 | 0,31 | 0,08 |
| prev, `hier_h100b` | 0,10 | 0,32 | 0,38 | 0,40 | 0,14 |
| prev2, `hier_h100` | 0,08 | 0,26 | 0,27 | 0,28 | 0,08 |
| prev2, `hier_h100b` | 0,11 | 0,30 | 0,36 | 0,38 | 0,10 |

Gepaarter Unterschied `hier_h100b` − `hier_h100` (gleiche Startnetze und Ziehungen, 12 Paare): prev nach 20
Updates −0,05 ± 0,02 (4 von 12 positiv), nach 100 +0,08 ± 0,04 (8 von 12), nach 200 +0,09 ± 0,05 (7 von 12);
prev2 nach 100 +0,09 ± 0,04 (9 von 12), nach 200 +0,09 ± 0,05 (7 von 12) (± Standardfehler).

**Vergleich mit der Vorhersage.** (1) Getroffen, knapp: prev nach 100 Updates +0,08 (0,38 gegen 0,30; mit 4
Episoden waren es 0,39 gegen 0,26). (2) Getroffen: Streuung je Episode nach 100 Updates 0,08 und 0,14 (≥ 0,05).
Bilanz: 2 von 2 getroffen.

**Schluss.** (a) Ursache der Abweichung: Auf dem Worker hat jeder Job eigene Prüfpunkte, `--init` und `eval`
lasen θ deshalb aus `results/teacher.jsonl`, wo es auf 10⁻⁶ gerundet war. Das Innen-Lernen über 100 Updates
auf hier_s reagiert auf so kleine Änderungen von θ mit Änderungen einzelner Episoden um bis zu 0,09. Lokal ist
alles bitgleich (Reihenfolge, Prozess, Pool). Dazu kommt ein kleiner Unterschied zwischen Worker und lokalem
PC bei exakt gleichem θ (Ursache nicht geprüft). θ wird jetzt exakt gespeichert; ältere Zeilen bleiben
gerundet. (b) Die Empfindlichkeit ist eine Eigenschaft der Regel auf hier_s, nicht nur ein Rechenfehler: Wer
mit 4 Episoden misst, misst auf etwa ±0,04 genau. Für hier_s mit langen Episoden braucht der Meta-Test
mindestens 12 Episoden. (c) Der Gewinn der Fortsetzung im Inneren trägt, aber kleiner als mit 4 Episoden
gemessen: +0,08 bis +0,09 nach 100 Updates bei etwa 2 Standardfehlern; der Verlust nach 20 Updates (−0,05) ist
ebenso deutlich. (d) Die Aussagen von `PHASE_D.md` 5.9 bleiben in der Richtung gültig; die Zahlen dort mit 4
Episoden sind auf etwa ±0,04 genau.

**Belege.** `results/phase_d_noise.jsonl` (48 Zeilen). Ausführlich: `PHASE_D.md` Abschnitt 5.9.

## Laufend / offen

- Phase F, erster Versuch Wach- und Schlafphase (Auftrag Nutzer 2026-11-27, PLAN_TRAINER Phase F): Lässt sich
  eine im Wachen schnell gelernte Fähigkeit (schnelle Gewichte F, Regel `pos_map`, 20 Updates, k = 64) im
  Schlaf in ein zweites Modul S übertragen, nur aus Träumen, die das wache Netz beschriftet, sodass F danach
  wegfallen kann? `netresearch/sleep.py` (Commit nach diesem Eintrag): layer_s@25k, Fälle lib_prev und lib_xmFF,
  Seeds 5–6 × 3 Ziehungen (6 Episoden je Fall), Schlaf 200 Adam-Schritte zu je 64 Traum-Eingaben auf S
  (Gate „task“ wie in Phase D), gemessen W + S auf ungesehenen Sequenzen. Quellen: replay (die 64
  Trainings-Eingaben), dream_mem (Rollouts des Basis-Netzes aus den 64 Eingaben, 16 Schritte), dream_rand
  (Rollouts aus Zufall), noise (Zufalls-Tripel), real (frische Basis-Sequenzen); je 1024 Eingaben außer
  replay. Vorab gesehen: `check` (Basis-Netz sagt die nächste Zahl zu 0,94 richtig; Traum-Fenster echte
  Basis-Sequenzen: dream_mem 0,75, dream_rand 0,43, noise 0,005) und eine Probe-Episode (lib_prev, Seed 5,
  Ziehung 0): wach 0,67; nach dem Schlaf replay 0,93, dream_mem 0,76, dream_rand 0,74, noise 0,71, real 0,75.
  Einschränkung: Weil S nur bei Gate „task“ wirkt, ist Vergessen der Basis-Aufgabe hier nicht messbar.
  **Vorhersage vor dem Lauf (2026-11-27):** (1) Die Fähigkeit wandert ohne gespeicherte Daten in S: dream_rand
  nach dem Schlaf im Mittel ≥ wach − 0,05, auf beiden Fällen. (2) replay ist auf prev die beste Quelle
  (≥ 0,85; dort sind die Beschriftungen fast die wahren, und der Schlaf ist Backprop auf gespeicherten Daten).
  (3) Das Weltmodell zählt: Auf mindestens einem Fall ist noise um ≥ 0,05 schlechter als dream_mem.

- Noch in Bits: `*_parts` (die Anpassungs-Studien servo / robot sind seit 2026-11-23 umgestellt); nicht neu gerechnet:
  Größen-Studie, langsame Gitter, `in12`, Lehrpläne mit `*_parts`.
