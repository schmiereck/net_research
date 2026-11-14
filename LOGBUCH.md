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

## Laufend / offen

- Auftrag des Nutzers (2026-11-14): Schritt-Aufgaben auf die neue Kodierung umstellen. Vorher Wahl der
  Kodierung auf den Abstimm-Seeds 5 und 6: `_pop` (Glocke, Breite 1 Zelle), `_p05` (Breite 0,5: Nachbar 0,14
  statt 0,61) und `_hot` auf servo (5 Netze, 1500 Updates), robot_findc (4 Netze) und robot_finds_in_f32
  (4 Netze, je 24000 Updates). **Regel, vorab festgelegt:** Es gewinnt die Kodierung mit der höchsten exakten
  Wertung, gemittelt erst über die Netze je Aufgabe, dann über die drei Aufgaben. Liegen zwei innerhalb 0,02,
  entscheidet `near` im selben Mittel.
  **Vorhersage vor dem Lauf (2026-11-14):** `_p05` gewinnt: auf den Roboter-Aufgaben exakt innerhalb ±0,03
  von `_hot`, auf servo wie `_pop` (layer_s, hier_s, mlp mindestens 0,85; `_hot` dort im Mittel mindestens
  0,15 darunter).
