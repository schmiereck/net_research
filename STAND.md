# Stand der Forschung

Kurzfassung, Stand 2026-11-12. Der Weg dahin steht chronologisch in [`LOGBUCH.md`](LOGBUCH.md). Details:
[`AGENDA.md`](AGENDA.md) (alle Themen mit Status),
[`PLAN_TRAINER.md`](PLAN_TRAINER.md) (Trainer-Netz, Messungen je Phase), [`results/report.md`](results/report.md)
(Benchmark-Tabellen).

## Ziel

**Übergeordnet (festgehalten 2026-11-12): eine Benchmark-Pipeline, die früh sagt, ob sich eine Architektur lohnt.**
Viele Netz-Architekturen werden auf kleinen, billigen Aufgaben verglichen; nur die interessanten gehen auf die
teuren Roboter-Aufgaben. Dafür muss bekannt sein, welche kleine Aufgabe welche Roboter-Aufgabe vorhersagt. Jede
neue Architektur läuft deshalb auf beiden Seiten der Paare unten, und die Prognose wird VOR dem Roboter-Lauf
notiert und danach geprüft (`scripts/forecast.py`, Abschnitt „Prognose“ unten).

Inhaltlich:
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
    **Im Populations-Code (2026-11-23) zum großen Teil aufgehoben:** Die Kalibrierungen sind dort Umordnungen
    der Ausgänge; `rls_rf` löst jedes servo-Gerät mit einem Update (0,89–1,00), Delta-Regel 0,79–0,98, Adam
    auf flipx, offx, weak 0,89–0,93. Bibliothek servo mit `rls_rf` 0,96 / Orakel 0,99 (Bits 0,91 / 0,94),
    robot-Kalibrierungen 0,94 / 0,98. Achsen tauschen (swap, rot90) lernen Adam und Gradient in 200 Updates
    kaum (0,20–0,34). Ein anderes Ziel (grün / blau) bleibt in jedem Code unlernbar.
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
- Nachgemessen mit vierfacher Trainingszeit (`results/grid_slow.jsonl`): Die Spaltenzahl ändert vor allem das
  Lerntempo, und zwar je Aufgabe verschieden. 16 Spalten lernen Roboter-Bilder am schnellsten und `servo` am
  langsamsten (am Ende trotzdem 0.96); 4 Spalten umgekehrt.
- Gedächtnis (`cycle_mem`): Gitter-Netze 1.00 ab 100k, `vit` / `cnn` 0.00 in jeder Größe, `gru` erst mit 400k.
  `hier_s` bricht mit 400k ein (0.01), Ursache offen.

**5. Brücke zum Roboter-Projekt (rdf_thalamus_sml)**
- Fovea-Bilder des MuJoCo-Arms sind als Aufgaben eingehängt. „Wo ist der rote Würfel“ (`robot_gaze`) lösen die
  Netze (0.93–1.00), „Schritt von der Hand zum Würfel“ (`robot_reach`) noch nicht (um 0.10).
- `robot_reach` scheitert am Verrechnen: Hand (0.90) und Würfel (0.70) werden einzeln gelesen.
- Die Bibliothek lernt auf Roboter-Bildern Kalibrierungen des Blicks (0.91, Orakel 0.96), aber kein anderes
  Ziel (grün statt rot: 0.01). Das geht mit Schreiben nur am Kopf prinzipiell nicht.
- Mit einem **Ziel-Eingang** (Kommando = Farbe des gesuchten Würfels als Vektor) finden die Netze den
  kommandierten Würfel (cnn 0.72, Gitter-Netze ~0.5, ohne Eingang 0.04) und folgen dem Kommando. Mit
  gewürfelten Farben im Training verallgemeinert das Kommando auf einen nie gesehenen Farbton (cnn 0.31
  gegen 0.42 bei trainierten Farbtönen). Mit vierfacher Trainingszeit: vit 0.64, cnn 0.62, Gitter-Netz 0.56
  (16 Spalten 0.59); die Gitter-Netze brauchen dafür etwa dreimal so viele Updates wie das cnn.
- Das Ziel kann auch als **Bild des Objekts** gezeigt werden: Ein kleiner Encoder bildet daraus selbst eine
  Adresse (16 Werte). Das ist so gut wie die vorgegebene Farbe (vit 0.59) und verallgemeinert besser auf einen
  nie gesehenen Farbton (92–97 % der Kontrolle).
- Bei Objekten gleicher Farbe und verschiedener Form trägt die Adresse die Form (zwei Bilder desselben
  Körpers geben in 74–83 % die nächstliegende Adresse), aber die Suche in einem einzigen Blick scheitert
  (0.05–0.09).
- **Anschauen und vergleichen** löst das: Erst das Bild des gesuchten Körpers, dann der Blick nacheinander
  auf die drei Kandidaten. Der Attention-Speicher wählt in 82 % den richtigen Körper (beim nie gesehenen Y
  56 %), das GRU in 68 %. Die Gitter-Netze scheitern daran vollständig, auch mit Notizblock: Sie können
  Gespeichertes wiedergeben, aber nicht mit dem Gesehenen vergleichen. Synthetische Aufgaben zeigen den Grund
  (`results/match.jsonl`): Steht das Muster immer am selben Ort (`match`), vergleichen alle Gitter-Netze
  fehlerfrei. Wandert es (`match_shift`), bleiben sie bei „immer nein“; GRU und Attention-Speicher
  schaffen dort etwa die Hälfte.
- Die Zerlegung (`results/match_parts.jsonl`) zeigt: Lesen und Merken eines wandernden Musters können die
  Gitter-Netze fehlerfrei. Gebrochen ist das Vergleichen zweier wandernder Muster, schon in einem einzigen
  Bild und bei allen Architekturen (auch vit und cnn). Mit vierfacher Trainingszeit lösen es die
  Gitter-Netze dann doch, und zwar am besten von allen (Hierarchie-Gitter 0.96, GRU 0.71, vit / cnn /
  Attention-Speicher höchstens 0.13). Die Teilleistungen sind da, das Zusammensetzen wird nur sehr spät
  gefunden: ein Fall für Lehrplan und Teacher, nicht für einen Umbau der Netze.
- **Lehrplan** (`scripts/curriculum.py`, erster Durchgang auf den Abstimm-Seeds): Lernt ein Netz erst Merken und
  Vergleichen wandernder Muster, löst es danach den Vergleich mit Gedächtnis (Gitter-Netze 0.00 → 1.00).
  Dieselbe synthetische Vorstufe öffnet auch die Roboter-Aufgabe mit den drei Kandidaten: Das
  Hierarchie-Gitter wählt danach in 86 % den richtigen Körper (nie gesehenes Y: 60 %) und ist damit das
  beste Netz auf dieser Aufgabe (Attention-Speicher 82 % / 56 %; Test-Seeds 0–2). Das flache Gitter-Netz
  schafft es in zwei von drei Seeds.
- Bestätigt auf den Test-Seeds für acht Netze: Der Vergleich mit Gedächtnis (`match_shift`) geht allein bei
  keinem Gitter-Netz (0.00) und mit Vorstufe bei allen (0.97–1.00), bei gleicher Gesamtzahl an Updates. Als
  Vorstufe reichen 3000 Updates „ein wanderndes Muster merken“. Beim Vergleichen in einem Bild hebt Lesen als
  Nebenaufgabe das cnn von 0.00 auf 1.00.
- **Einfrieren und Andocken (Phase C, erster Test 2026-11-21, `results/route.jsonl`):** Ein eingefrorenes Netz
  mit dem Können `keep_shift`, seitlich gelesen von einem neuen Modul, macht `match_shift` lernbar (ohne Können 0
  von 9, mit 0,32–0,97). Für die Gitter ist es aber schwächer und langsamer als Feintuning (gelöst 2 von 6 gegen 6
  von 6). Feintuning vergisst `keep_shift` sofort und ganz. Mischen beider Aufgaben gibt den Gittern beides (keep
  1,00, match 0,73–1,00): Sind die alten Daten da, schlägt Mischen das Einfrieren. Der Verbund verliert
  `keep_shift`, weil das Gate die Aufgabe nicht kennt; es fehlt die Auswahl nach Aufgabe.
- **Schwäche der Gitter beim Andocken geklärt (2026-11-21):** Der Engpass ist, dass das neue Modul nur die
  oberste Darstellung liest. Liest jede neue Zelle ihre eingefrorene Zelle (`freeze:pcell`), lösen beide Gitter
  `match_shift` in 9 von 10 Läufen (sonst 4 von 10, Mittel 0,90 statt 0,63), am Ende fast wie Feintuning, aber
  langsamer. Ein breiterer Port hilft nicht (64 Werte gleich, die ganze Darstellung schadet hier_s). Der
  Null-Start der zweiten Zellschicht von layer_s erklärt einen Teil (2 von 5 Seeds). Das Gate ist zum Lernen
  nicht nötig.
  Beides zusammen (`freeze:pcell+fc2`) macht layer_s schneller und sicherer: 9 von 10 Seeds gelöst (`pcell`
  allein 7, `freeze` 0), bei Update 7500 im Mittel 0,56 statt 0,33. Das Feintuning bleibt schneller.
  Der einzige ungelöste Seed braucht nur länger (etwa 9000 Updates Anlauf, mit 24000 Updates 0,96); die lange
  Anlaufzeit kommt vom eingefrorenen Netz, warum ist offen.
  **Mit langer zweiter Stufe (24000 Updates, 2026-11-22) relativiert:** Auch `freeze` löst dann 8 von 10, `fc2`
  9, `pcell` und `pcell+fc2` 10 von 10. „Nur oben“ verlangsamt also vor allem; `pcell` bleibt schneller und
  rettet die zwei langsamsten Seeds (0,97 statt 0,59/0,68), nicht gesichert. `pcell+fc2` erreicht 0,8 im Median
  nach 5875 Updates, etwa so schnell wie Feintuning. Lösequoten beim Andocken brauchen eine Budgetangabe.
- **Blickschleifen-Leiter, erste Sprosse `cue → blind` (2026-11-22):** Mit eigener Netzhaut und eigenem
  Adress-Encoder je Netz und der Summe im Port hilft das Andocken layer_s_sp4 (`blind` schneller als von null an,
  `near` 0,94–0,96), aber Feintuning ist klar besser (schneller, `near` 0,96–0,97). Bei vitmem schadet das
  Andocken (`near` 0,76–0,86 gegen 0,81–0,87 von null an; Feintuning 0,92). Der Verbund verliert `cue` wie das
  Feintuning. Die beiden Aufgaben sind fast gleich. Mischen (Sperre gelockert) gibt als einzige Variante beide
  Aufgaben ganz (layer_s_sp4 `near` 0,95–0,96 in beiden). Nächster Engpass: die Auswahl nach Aufgabe.
- **Zweite Sprosse `blind → two` (2026-11-23, Seeds 0–1):** Das Können aus `blind` hilft über Feintuning:
  layer_s_sp4 erreicht 0,68 nach 2250 / 4000 statt 7000–7250 Updates (Ende 0,73–0,74, `near` 0,92), vitmem
  schafft `two` erstmals (0,68–0,69, `near` 0,90–0,91 gegen 0,70–0,80 von null an). Das Andocken nutzt es kaum
  (layer_s_sp4 `freeze` so schnell wie von null an, `pcell` etwas schneller; vitmem `near` 0,78–0,80), und der
  Verbund verliert `blind` stärker als das Feintuning. Mischen gibt layer_s_sp4 wieder beide Aufgaben ganz
  (`two` 0,74, `blind` 0,82–0,83); vitmem lernt `two` beim Mischen langsamer.
- **Auswahl nach Aufgabe (`freeze:sel`, 2026-11-23, Seeds 0–1), Phase C damit abgeschlossen:** Der Eintrag legt
  beim Einfrieren eine Statistik seiner Aufgabe ab; der Verbund gibt die Ausgabe des eingefrorenen Netzes allein
  weiter, solange die Episode vertraut aussieht. Die alte Aufgabe bleibt so in allen 12 Läufen ganz (höchstens
  0,004 unter dem eingefrorenen Netz, ohne Auswahl 0,1–0,4 Verlust). Die Auswahl über Vertrautheit trennt aber
  nur Aufgaben mit verschiedener Darstellung: `cue → blind` fast ohne Schaden an der neuen Aufgabe, bei
  `blind → two` (gleicher Anfang, späte Zustände ähnlich) gehen gerade die späten `two`-Schritte ans alte Netz
  (Schritt 5: 47 %), `two` fällt auf 0,55–0,62 (vitmem 0,27–0,34). Gleiche Eingaben brauchen eine Auswahl nach
  Fehler (wie `slots.py`). Mischen bleibt am besten, wenn alte Daten da sind.
- **Lesart:** Die langen Plateaus sind fehlende Zwischenziele. Verlangt eine Hilfsaufgabe die Zwischengröße als
  Ausgabe, verschwinden sie bei allen Architekturen. Das ist die Rolle, die ein Teacher übernehmen soll.
- Auf den Roboter-Aufgaben trägt das Prinzip bisher nur teilweise: Bei „Hand zum Würfel“ hebt die Hilfsaufgabe
  (Zelle der Hand, Zelle des Würfels) das vit von 0.12 auf 0.40; danach begrenzt das genaue Lesen, nicht mehr
  das Verrechnen. Bei der Form-Suche in einem Blick hilft sie nicht (0.03–0.10): Die
  Netze erkennen die Form im Zeigebild (0.96), lesen aber in der Szene mit drei gleichfarbigen Körpern weder
  deren Positionen (0.10–0.21) noch deren Formen (kaum über Zufall). Der Engpass ist die Wahrnehmung in einem
  Blick. Und die kurze Vorstufe, die
  bei den Pixel-Wörtern reichte, reicht den Gitter-Netzen auf Roboter-Bildern nicht. Dort braucht die Vorstufe
  Merken UND Vergleichen zusammen (je allein: 0.00 bzw. höchstens 0.32); 6000 Updates davon genügen.
- `robot_reach` liest seit 2026-11-12 den Datensatz `reachcells_*` (gleicher Generator, andere Szenen).
- **„Hand zum Würfel“ hängt an der Datenmenge und am Lesen des Würfels** (reach_read, Seeds 5 / 6, bestätigt
  auf Seeds 0–2: vit 0.62, vitmem 0.59, layer_s 0.44, cnn 0.40, hier_s 0.24 mit 48000 Bildern und Hilfsaufgabe; 24000
  Updates je Aufgabe). Viermal so viele Bilder (48000) heben jedes Netz: allein 0.08–0.13 → 0.18–0.31, mit der
  Hilfsaufgabe 0.12–0.45 → 0.23–0.64 (vit 0.59, vit@400k 0.64, cnn@400k 0.50, layer_s 0.45, hier_s 0.23).
  Viermal so viele Parameter bringen wenig (+0.03 bis +0.08). Mit Hilfsaufgabe liegt die Hauptaufgabe beim vit
  fast auf der Höhe des Lesens (0.59 gegen 0.61): Das Verrechnen ist gelöst, begrenzt wird durch das Lesen.
  Gelesen wird die Hand zu 0.78–0.92, der Würfel nur zu 0.54–0.72.
- **Die Auflösung der Fovea begrenzt das Erkennen der Form nicht, wenn der Blick auf dem Körper liegt**
  (`robot_shape`, 5 Formen, Zufall 0.2, Seeds 0–2, 6000 Updates): Standard-Fovea 0.93–0.99, doppelte
  Vergrößerung 0.94–0.99, vierfache 0.91–0.98. Mit 32 × 32 über dasselbe Blickfeld und zwei bis drei gelernten
  Schichten davor 0.98–1.00, mit bloßem Mitteln 0.93–0.98 (wie Standard), mit nur einer Schicht schlechter
  (0.76–0.94). Der Gewinn durch doppelte Auflösung ist also klein (rund ein Prozentpunkt beim cnn, fünf beim
  vit und beim Hierarchie-Gitter). Einschränkung: Der Blick liegt hier höchstens eine Zelle neben dem Körper;
  die Netze können die Form auch an der Fläche statt am Umriss erkennen.
- **Abseits der Mitte lohnt die doppelte Auflösung** (`robot_shape_edge`, ein Körper bis 7 Zellen neben der
  Mitte, Seeds 0–2): Standard-Fovea 0.55–0.62, 32 × 32 mit drei gelernten Schichten davor 0.65–0.77. In den
  zwei groben Außenringen fallen beide ab (0.43–0.55 gegen 0.54–0.72). Vorbehalte: Vier von zwölf Läufen mit
  Vorschalt-Stufe lernen gar nicht, und die Netze lernen die 12000 Bilder auswendig.
  Mit 48000 statt 12000 Bildern: Standard-Fovea 0,58–0,73, 32×32 mit `+rez3` 0,78–0,89 (innerhalb Ring 5
  0,88–0,98). Mehr Bilder allein helfen der Standard-Fovea kaum; der Engpass ist die Auflösung.
- **Die Form-Suche gewinnt deutlich durch doppelte Auflösung** (`robot_finds_f32`, Seeds 0–2): von 0,07–0,09
  auf 0,21–0,35 (vit 0,35, Gitter 0,23–0,32, cnn 0,21). Meine Vorhersage vor dem Lauf (kein Netz über
  0,25) war falsch. Gelöst ist die Aufgabe damit nicht; die Hilfsaufgabe schadet mit 32×32.
- **In der Suchszene wird die Form kaum gelesen** (`robot_shape_at`: Ort eines Körpers als Kommando ->
  Form, Seeds 0–2): 0,22–0,41 bei Zufall 0,2. Die Fehler sind blind, keine Verwechslung der Körper.
  70 % der Körper liegen außerhalb von Ring 5; innen liest nur cnn brauchbar (0,63).
- **Liegen alle Körper im scharfen Bereich, wird die Suchszene gelesen** (`gazeshapein`, Seeds 0–2): Form an
  genannter Stelle 0,88–0,95 mit `+rez3` und 48000 Szenen (vit 0,69). Die Form-Suche steigt von 0,07–0,09
  auf 0,63–0,70 (layer_s 0,70). Der richtige Körper wird dabei in 0,87–0,90 der Fälle gefunden; was zur
  exakten Wertung fehlt, ist fast nur eine Zelle Schrittgenauigkeit. Der Vergleich mit dem Zeigebild kostet
  0,00–0,07, ein falscher Körper wird in 0,02–0,03 gewählt.
  Die fehlende Zelle hat zwei Ursachen: die Zellgrenze (dort ist der Schritt ein Münzwurf; ein Fünftel der
  Körper liegt weniger als 0,5 px daneben) und die Form (T und L 0,15–0,29 schlechter als der Würfel).
  Der Formeffekt kommt aus der Zielgröße: Der Körper-Ursprung liegt bei U, T, L 1,8–3,5 px neben dem
  Schwerpunkt. Schritt-Aufgaben melden seit 2026-11-14 neben der exakten Wertung `near` und `step_err`.
- **Die Bit-Kodierung des Schritts ist selbst ein Hindernis** (2026-11-14): Mit 16 Ausgängen je Achse statt
  4 Bits lernen vier von fünf Netzen servo in 1500 Updates (0,96–1,00 statt 0,03–0,84); die Formsuche steigt
  exakt auf 0,71–0,79 (`_hot`), der richtige Körper wird in 0,93–0,97 gefunden. Varianten `*_pop` / `*_hot`;
  seit 2026-11-14 sind die Schritt-Aufgaben umgestellt (Glocke; zuerst Breite 1 nach Regel auf Seeds 5 / 6,
  dann auf Entscheidung des Nutzers Breite 0,5; servo als Stufe mit 1500 Updates);
  die alte Form heißt `<name>_bits`. Alle Schritt-Zahlen in diesem Dokument vor diesem Datum sind Bit-Werte.
  Neu gerechnet (Seeds 0–2, `results/step_pop_compare.json`): exakt meist +0,05 bis +0,22 (robot_reach_big
  0,41–0,52 statt 0,18–0,33, `near` 0,94–0,97); vit / vitmem verlieren bis 0,05; servo steht bei 6000 Updates
  für alle lernenden Netze auf 1,00 und trennt nicht mehr.
  Mit Breite 0,5 (2026-11-15, `results/step_p05_compare.json`; **das sind die gültigen Zahlen**): Suchaufgaben
  exakt +0,04 bis +0,11 gegenüber Breite 1 (robot_findc cnn+cmd 0,77, vit+cmd 0,72; robot_finds_in_f32 cnn
  0,78, layer_s 0,77; robot_finds_c_f32 layer_s 0,80, cnn 0,79, vit 0,77, hier_s 0,76); vit / vitmem liegen
  nirgends mehr unter ihrem Bit-Wert. robot_reach_big unverändert (0,41–0,52), robot_reach exakt 0,21–0,29
  (bis 0,05 schlechter als mit Breite 1: die schmale Glocke kostet dort, wo das Netz den Ort nur ungefähr
  kennt). servo mit 1500 Updates trennt (vit, vitmem, attnmem 1,00; Gitter 0,90–0,97; gru 0,55; mlp 0,40;
  lstm 0,37; cnn 0,01), misst aber Lerntempo: cnn erreicht nach 6000 Updates 1,00.
- **Formsuche in der Schleife** (2026-11-15, `scripts/finds_loop_eval.py`, `results/finds_loop.jsonl`): Der
  Blickschritt wird ausgeführt, das nächste Bild kommt vom neuen Blickpunkt (`netresearch/tasks/fovea.py`,
  bitgenaue Kopie der Roboter-Fovea; Kamerabilder aus dem Export mit `--images`). Mit den gespeicherten
  Einzelschritt-Netzen: Schritt 1 landet in 0,94–0,96 höchstens eine Zelle neben dem Körper, danach verlassen
  die Netze ihn wieder (`near` nach 4 Schritten cnn 0,88, layer_s 0,67, vit 0,63, hier_s 0,57; Blick auf einem
  anderen Körper bis 0,33). Ursache: Im Trainingssatz liegt der gesuchte Körper nie in der Mitte (0,2 % der
  Ziele höchstens eine Zelle entfernt), „bleiben“ wurde nie gelernt. Das Orakel erreicht 1,00 nach zwei
  Schritten. **Die Einzelschritt-Zahl sagt die Schleife nicht vorher, solange die Szenen die Zustände der
  Schleife nicht enthalten.**
  Mit solchen Szenen (`robot_finds_m_f32`: halb `gazeshapec`, halb `gazeshapeu` mit dem Ziel 0–5 Zellen von der
  Mitte, 2026-11-15): alle vier Netze bleiben auf dem Körper, `near` nach 4 Schritten cnn 0,95, layer_s 0,94,
  vit 0,93, hier_s 0,90 (exakt 0,58–0,69), und der Einzelschritt sagt das je Netz auf 0,02 vorher. Die Schleife
  bringt aber nichts über den ersten Schritt hinaus: falscher Körper bleibt (0,04–0,09), und die Netze sagen
  „bleib“, auch wenn der Körper eine Zelle daneben liegt (Orakel: exakt 1,00 nach zwei Schritten).
  Mit Training auf Blickfolgen (`robot_loop_f32`, verrauschter Lehrer, 2026-11-15) wird der zweite Schritt
  nützlich: exakt nach 4 Schritten cnn 0,75, layer_s_sp4 0,75, layer_s 0,74 (`near` 0,93–0,94); der falsche
  Körper bleibt (0,06–0,07). **Gedächtnis bringt hier keinen Vorteil** (beste Netze mit Gedächtnis = cnn;
  vitmem 0,82, attnmem 0,76 in `near`). Die Netze mit Gedächtnis hängen trotzdem am Zustand (gelöscht: `near`
  0,60–0,72), aber als Schrittzähler („frischer Zustand = erster Schritt, weit springen“), nicht als Erinnerung.
  **Schleife, die ohne Erinnerung nicht lösbar ist** (`robot_loop_cue_f32`, `robot_loop_blind_f32`: Vorlage nur
  an einem Hinweis-Schritt vor dem Lauf, 2026-11-15): ohne Gedächtnis `near` 0,32–0,33; gelöste Läufe von layer_s
  und layer_s_sp4 0,91–0,93 (wie mit Vorlage). Ein Lauf löst ganz oder gar nicht: hier_s 6 von 6 (0,83–0,88),
  layer_s 3, sp4 4, am4 4, attnmem 4, vitmem 3 von 6. Engpass ist das Finden der Lösung im Training, nicht das
  Behalten. Mittel über Seeds taugt hier nicht; Lösequote und Wert der gelösten Läufe berichten.
  Mit acht Seeds (2026-11-16): hier_s löst 16 von 16 Läufen, layer_s 11, layer_s_sp4 11, attnmem 11,
  layer_s_am4 10, vitmem 7. hier_s lernt zuverlässiger, endet aber tiefer (`near` 0,80–0,88 gegen 0,89–0,93 bei
  layer_s). Der Hinweis-Schritt mit Bild ist für die layer_s-Familie schwerer (10 von 24 gegen 22 von 24).
  **Ursache der ungelösten Gitter-Läufe (2026-11-16): der Eingang, nicht das Gedächtnis.** Der Vorlagen-Encoder
  (`+ref`, endet in tanh) gibt dort für jede Vorlage dasselbe gesättigte Muster aus (15 von 15 Läufen am Boden;
  bei gelösten nie); im Zustand kommt nichts an. Die Lösequoten messen also, wie oft der Eingang hängen bleibt.
  vitmem und attnmem scheitern auch mit lebendem Encoder.
  Reihenfolge belegt (2026-11-16, `ref_curve`): Die layer_s-Familie sättigt den Encoder in den ersten 500–1000
  Updates, gelöst wird frühestens ab 2750. Sättigung bei Update 1000 von mindestens 0,96 = bleibt hängen (6 von
  6), höchstens 0,65 = löst (4 von 4). hier_s sättigt in dieser Phase gar nicht.
  **Ursache belegt (2026-11-16): Variante `+refl` (Encoder ohne tanh), gleiche Seeds und Startgewichte: 9 von 9
  Läufen der layer_s-Familie lösen** (mit tanh 3), auch alle 6 zuvor ungelösten; hier_s unverändert. Die
  Lösequoten mit `+ref` beschreiben also den Eingang, nicht das Gedächtnis.
  **Vergleich mit `+refl`, Seeds 0–2 (2026-11-17), `near` nach 4 Schritten `cue` / `blind`:** layer_s 0,89 / 0,91,
  layer_s_sp4 0,88 / 0,91, hier_s 0,86 / 0,86, layer_s_am4 0,81 / 0,85, attnmem 0,68 / 0,72, vitmem 0,53 / 0,65
  (3 von 6 Läufen gelöst), ohne Gedächtnis 0,32. Alle 24 Gitter-Läufe gelöst. Die Reihenfolge ist die des
  ersten Schritts; sp4 und am4 bringen keinen Vorteil; nur vitmem leidet deutlich unter dem Merken. Für die
  Gitter-Netze ist die Aufgabe als Gedächtnis-Test zu leicht (ein Inhalt, vier Schritte).
  **`+refl` ist ab 2026-11-17 der Standard für Aufgaben mit Vorlage** (Entscheidung des Nutzers); `+ref` nur noch
  für den Vergleich mit älteren Ergebnissen.
  **Zwei Ziele nacheinander (`robot_loop_two_f32`, 2026-11-17, Seeds 0–2):** beide Vorlagen nur vor dem Lauf,
  3 Schritte zu A, 3 zu B. `near_both` layer_s = layer_s_sp4 0,72 > layer_s_am4 0,57 ≈ hier_s 0,55 >> attnmem
  0,25 ≈ vitmem 0,23 (A 0,77–0,86, B 0,65–0,79 bei den Gitter-Netzen). Diese Stufe trennt die Bauarten; alle 12
  Gitter-Läufe lösen beide Ziele, attnmem und vitmem in 4 von 6 Läufen nur Zufall. Notizblock und
  Inhaltsadressierung bringen nichts gegenüber layer_s.
  **Fehler aufgeteilt:** Der Wechsel A → B gelingt immer (bei gelöstem A bleiben höchstens 2 % bei A). Fehler
  der Gitter-Netze: Reihenfolge vertauscht 0,05–0,09, Form verwechselt (dritter Körper) 0,13–0,20 am Ende.
  attnmem und vitmem in den gescheiterten Läufen: verlassen A sicher, wählen dann blind zwischen B und C, sie
  behalten keine Form.
  **Drei Ziele nacheinander (`robot_loop_three_f32`, 2026-11-18, Seeds 0–2, 12000 Updates):** Folgen A, B, C und
  A, B, A (das letzte Ziel nicht per Ausschluss). `near_all` layer_s = sp4 0,44 > vitmem 0,28 ≈ attnmem 0,25 >
  am4 0,19 > hier_s 0,14 (Zufall 0,08). Die Stufe ist für 12000 Updates zu steil: layer_s und sp4 streuen je Seed
  von 0,18 bis 0,61, Seed 2 bricht bei beiden ein (A gelingt, B und das dritte Ziel nahe Zufall, Trainingskurve
  bleibt stehen). hier_s und am4 neigen dazu, zum ersten Ziel zurückzukehren. attnmem und vitmem lernen je Seed
  ganz oder gar nicht (je 2 von 3), verlieren dann aber über die drei Ziele nichts.
  **Mit 24000 Updates (2026-11-18, nur layer_s und sp4):** sp4 löst alle drei Seeds, `near_all` 0,71–0,75
  (Mittel 0,73), drittes Ziel bei gelöstem A und B 0,91–0,93. layer_s Mittel 0,52, wieder 2 von 3 gelöst, aber
  ein anderer Seed bricht ein (Seed 1 0,21 statt Seed 2): Ob der Sprung gelingt, hängt bei layer_s vom
  Trainingsweg ab. Erstmals liegt der Notizblock (sp4) klar vor layer_s; auf dieser Stufe entscheidet die
  Trainingslänge über die Rangfolge.
  **Lösequote mit sechs Seeds (2026-11-18, 24000 Updates):** sp4 6 von 6 gelöst (`near_all` 0,71–0,76), layer_s
  3 von 6 (gelöste 0,64–0,74, eingebrochene 0,21–0,24; Fisher einseitig p = 0,09). Eingebrochene Läufe behalten nur
  A und gehen beim dritten Ziel meist zurück; der Trainingswert trennt beide Zustände sauber (0,651 gegen 0,717).
  Der Notizblock hilft beim Lernen, kaum beim Ergebnis (gelöste Läufe +0,04).
  **Warum layer_s nur A behält (Auslese des Zustands, 2026-11-18):** Alle Läufe schreiben die drei Formen ins
  Gedächtnis (nach den Hinweisen 0,86–0,97 lesbar). Die eingebrochenen verlieren B und C in den ersten Schritten
  des Laufs (nach drei Schritten am Boden), die gelösten halten sie (B 0,50–0,61), sp4 am besten direkt nach dem
  Losgehen. Ursache: Die ersten echten Bilder verdrängen die gemerkten Formen; der Encoder ist es nicht.
  **Form oder Lage (2026-11-18):** Gemerkt wird die Form, nicht die Lage. Alle Netze, auch die eingebrochenen,
  bauen über die Schritte eine Karte der Szene mit Verlauf (wo A war, welcher Körper noch nicht besucht ist); ohne
  die Form können sie A, B, C aber nicht von A, B, A unterscheiden. Bei sp4 teilt sich die Arbeit von selbst:
  Gitter = Karte, Notizblock = Formen (B direkt nach dem Losgehen aus 128 Notizblock-Werten 0,66–0,75 lesbar,
  aus 128 Gitter-Werten 0,42–0,47).
  **attnmem und vitmem, ganz oder gar nicht (2026-11-18):** Die Läufe bei Zufall scheitern am Eingang: Der
  Vorlagen-Encoder bleibt fast ohne Streuung (0,04 gegen 0,09–0,24), die Form kommt kaum ins Gedächtnis. Alle
  Encoder beginnen bei 0,01; bei den Gitter-Netzen wächst die Streuung in den ersten 2000 Updates, bei attnmem und
  vitmem erst ab etwa 4000. (Korrigiert 2026-11-19: Dass sie die Formen „besser halten“, folgt aus dem Bau. Ihr
  Zustand ist ein Puffer der rohen Bild-Einbettungen, die Auslese misst dort nur den Encoder.) Die Ports sind nicht
  gleich: Bei attnmem und vitmem erreicht die Vorlage die Laufschritte nur als ein 48-Werte-Eintrag im Puffer, und
  `ref_enc(0)` liegt als konstantes Muster auf jedem Bild. Ihr Rückstand ist zum Teil eine Frage der
  Schnittstelle.
  Prüfung mit breitem Port-Anfang (`+pw`, 2026-11-19): **negativ**, 0 von 12 Läufen lösen (ohne: attnmem 3/6,
  vitmem 2/6); die größere Anfangs-Streuung wird im Training zuerst wieder gedämpft. Die Henne-Ei-Deutung ist in
  dieser Form nicht bestätigt; `+pw` vergrößert auch das Muster auf dem Bild, beides ist nicht getrennt.
  **Variante `+rv` (2026-11-19 bis 21, kein Standard):** Ein Schritt ohne Vorlage sendet keinen Befehl mehr (vorher ging
  `ref_enc(0)` als konstanter Befehl in den Port). Etappe 1, drei Ziele: Bei 24000 Updates gleicher Endstand (sp4
  6/6, layer_s 3/6, gelöste Läufe −0,02). Bei 12000 Updates liegen die Gitter-Netze eher etwas tiefer (Mittel
  layer_s −0,13, sp4 −0,06, am4 −0,05, hier_s 0), vor allem bei den Zielen 2 und 3. attnmem und vitmem 4 von 12
  gelöst (ohne 5), aber andere Seeds: Ob sie lernen, ist dort Zufall des einzelnen Laufs. Etappe 2 (2026-11-20):
  Mit nur einem Hinweis-Schritt (cue, blind) lernen mehr Läufe die Adresse nicht (vitmem 4 von 6 auf Zufall, ohne
  0 von 6; sp4 Seed 0 halb), bei zwei Hinweis-Schritten (two) löst vitmem dagegen 3 von 3 (ohne 1 von 3). `+rv`
  ist also nicht neutral; ob es Standard wird, ist offen. Ungeprüfte Vermutung: Ohne `+rv` gab `ref_enc(0)` in
  jedem Laufschritt Gradient in den Vorlagen-Weg und half, ihn früh in Gang zu bringen.
  Nachmessung mit 6 Seeds je Variante (2026-11-21): bei vitmem bestätigt (cue und blind zusammen 6 von 12 auf
  Zufall, ohne 0 von 12, p = 0,007), bei sp4 nicht (2 von 12, beide Seed 0, p = 0,24). Die Wirkung von `+rv` hängt
  an Bauart und Zahl der Hinweis-Schritte. Gelerntes Zeichen „keine Vorlage“ statt `ref_enc(0)` (`+rvt`,
  2026-11-21): vitmem weiter 4 von 12 auf Zufall (ohne `+rv` 0 von 12, p = 0,047; gegen `+rv` kein messbarer
  Unterschied), sp4 2 von 12 eingebrochen. Ein Zeichen allein ersetzt also nicht, was ohne `+rv` da war; das passt
  zur Gradient-Vermutung, belegt sie aber nicht.
  **Beschluss (Nutzer, 2026-11-21): Port-Standard bleibt ohne `+rv`** (`+refl`; Schritte ohne Vorlage senden
  `ref_enc(0)` als konstanten Befehl, das ist eine bekannte Eigenschaft, kein Fehler). `+rv` und `+rvt` bleiben als
  geprüfte Varianten im Code. Das Thema Vorlagen-Port ist geschlossen; die Ursache bleibt ungeprüft.
  **Falscher Körper (2026-11-18, nachgemessen 2026-11-19 auf allen Stufen):** Wer nach dem ersten Schritt auf einem
  falschen Körper steht, bleibt dort meist (`robot_loop_f32` 0,64–0,89, mit gemerkter Vorlage und bei drei Zielen
  0,80–0,98); Netze ohne Gedächtnis kommen öfter weg (0,26–0,32) als Netze mit (0,03–0,18). Vom richtigen Körper
  driftet praktisch niemand weg (höchstens 0,009). Die Schleife korrigiert keine Verwechslung.
  **Erster Live-Test im Roboter-Simulator (2026-11-19, Brücke Stufe b):** Drei Ziele, 12 gespeicherte Netze steuern
  den Blick in MuJoCo (`rdf_thalamus_sml/src/pc_cvnn/netresearch_live_loop.py` gegen `scripts/policy_server.py`;
  150 frische Szenen). Mit ruhendem Arm gleich dem Prüfstand (Abweichung höchstens 0,04); Prüfstand ordnet die
  Netze auch live richtig (Spearman 0,97). Fährt der Arm nach jedem Ziel über den angeblickten Körper (Hand im
  Bild), verlieren die Gitter-Netze 0,14–0,21 `near_all` (21–28 %), vitmem / attnmem 13–18 %; sp4 verliert am
  meisten (live 0,55–0,56, layer_s Seed 0 0,60). **Der Prüfstand sagt die Rangfolge vorher, nicht die Größe der
  Störung durch den Arm.**
  Kontrolle (2026-11-19, Bedingung `away`): Schwebt die Hand über einer freien Stelle im Bild statt über dem
  Körper, ist der Verlust gleich groß (0,96–1,17-fach). **Der Arm stört durch Ablenkung, nicht durch Verdecken**;
  mit Arm im Bild bleibt der Blick auch öfter auf dem gerade gefundenen Körper hängen (verfehlte Strecken 0,07–0,16
  statt 0,01–0,05). Arm-Bilder gehören in Training oder Prüfung des Prüfstands.
  **Neu gemessen mit richtiger Szenenfarbe (2026-11-21):** Bis dahin lief jede Szene in der Farbe der zuletzt
  erzeugten (Robot-Commit 17c0b19 korrigiert). Die Befunde halten: Spearman Prüfstand–live 0,95, Gitter-Netze
  verlieren mit Arm 23–30 %, `away` gleich `live` (0,92–1,05) bei allen 10 Netzen über Zufall. Die falsche Farbe
  kostete nur sp4 etwas (`static` +0,02–0,04). Zahlen: `results/robot_live_loop_v3.jsonl`. Video einzelner Läufe:
  `rdf_thalamus_sml/src/pc_cvnn/netresearch_live_video.py`.
- **Blickziel am Flächenschwerpunkt** (`robot_finds_c_f32`, 2026-11-14): exakt +0,04–0,05 (layer_s 0,74), der
  Formeffekt schrumpft von bis zu 0,29 auf bis zu 0,18, verschwindet aber nicht (L und U bleiben zurück).
  Zusammen mit einem Ausgang je Wert addiert sich beides: Formsuche exakt 0,76–0,81 (layer_s 0,81).
- **Die Greif-Decke von 0,62 ist großteils Wertung:** Die besten Netze liegen in 0,79–0,87 der Fälle
  höchstens eine Zelle daneben (`results/step_error.jsonl`).
- **Vorlauf im Spiele-Training (Review agy 3.1) ändert die Rangfolgen nicht:** Nur layer_i_sp4 gewinnt auf den
  Gedächtnis-Spielen (+0,06 / +0,08); die Gitter mit geteilten Gewichten und `push_easy` bleiben innerhalb der
  Streuung. Die Option `--burn` ist aus; alte Zahlen gelten weiter.
- **Null-Start des Restpfads hilft dem Hierarchie-Gitter nicht** (`hier_sz`, cycle_mem 0,03 gegen 0,80);
  der Einbruch von `hier_s@400k` bleibt ungeklärt.
- **`vitmem` (vit je Bild, dann Aufmerksamkeit über die letzten Bilder) löst „Anschauen und vergleichen“ ohne
  Vorstufe am besten:** richtiger Körper in 93 % (12000 Updates, Seeds 0–2), beim nie gesehenen Y 64 %. Die
  Vorstufe bringt ihm nichts (90 %). Das Y bleibt bei allen Netzen um 60 %.
- Der Vergleich über die Adresse aus dem Zeigebild („ist es das?“ in einem Blick) gelingt keinem Netz (0.50).
- Plan: Stufe b MuJoCo-Regelkreis mit Teacher als Experten, Stufe c Lieferquote als End-Benchmark; dazu die
  Servo-Stufe in Gelenkwinkeln (Fernziel physischer Arm, Abgleich über die Kamera).

## Prognose: welche kleine Aufgabe sagt welche Roboter-Aufgabe vorher?

Stand 2026-11-12 abends, `python scripts/forecast.py` (Rangübereinstimmung rho über die Architekturen, die
beides gerechnet haben; 6–14 Architekturen je Paar, also eine Beschreibung, noch kein Beweis).

| kleine Aufgabe | Roboter-Aufgabe | rho | Befund |
|---|---|---|---|
| `match_shift` | `robot_lookmem` (Kandidaten nacheinander vergleichen) | +0.88 | Dieselben zwei Netze kommen ohne Hilfe durch (attnmem, gru), alle anderen 0. Auch das Heilmittel (Vorstufe) übertrug sich. Aber: nach dem Roboter-Befund gebaut, keine blinde Prognose |
| `push_easy` | `robot_findc` (Ziel per Kommando suchen) | +0.70 (n = 14) | Gleiche Rangfolge über cnn und die Gitter-Varianten; attnmem, gru, mlp scheitern an beidem. **Die blinde Prognose für das vit ist gescheitert:** `push_easy` 0.11, `robot_findc` 0.65 (bestes Netz). Auch hier_s fällt heraus (−0.01 gegen 0.43). Die Aufgabe sagt also nur für cnn und flache Gitter vorher |
| `count` | `robot_findc` | +0.65 (n = 14) | ähnlich: stimmt für die Gitter, vit ist die Ausnahme (0.19 gegen 0.65) |
| `servo` | `robot_gaze` (Blick zentrieren) | +0.21 (n = 11) | Sieb in einer Richtung: wer `servo` nicht löst (mlp, gru), löst `robot_gaze` nicht. Umgekehrt gilt es nicht: attnmem löst `servo` (1.00) und bleibt auf `robot_gaze` bei 0.51. 16 Spalten sind nur langsam auf `servo`. Das sind Bit-Werte. Im Populations-Code (1500 Updates, 2026-11-15): Rangkorrelation +0,27 (n = 13), ohne cnn +0,53; cnn lernt `servo` langsam (0,01) und ist auf `robot_gaze` das beste Netz |
| `servo` | `robot_reach` (Hand zum Würfel) | (+0.81) | Scheinbar: `robot_reach` löst niemand (0.05–0.13). `servo` ist als Vorhersage zu leicht |
| `servo` | `robot_findc` | +0.31 | keine Vorhersage |
| `cycle_mem`, `recall`, `keep_shift`, `same_shift` | `robot_lookmem` | −0.5 … +0.3 | **keine Vorhersage**: Die Gitter lösen die Gedächtnis-Batterie und scheitern am Vergleichen auf Roboter-Bildern |

**Blinde Prognose für die drei neuen Netze** (aufgeschrieben 2026-11-12 vor den Roboter-Läufen; kleine
Ergebnisse in results/new3.jsonl, Seeds 0–2):

| Netz | kleine Aufgaben | Prognose `robot_lookmem` | Prognose `robot_findc` | Prognose `robot_gaze` |
|---|---|---|---|---|
| vitmem | `match_shift` 0.50, `push_easy` 0.61, `servo` 1.00 | deutlich über 0 (um 0.4–0.5, je Seed verschieden) | 0.5–0.6, bei cnn und Gittern | über 0.9 |
| lstm | `match_shift` 0.60, `push_easy` 0.09, `servo` 0.61 | deutlich über 0 (um 0.5) | um 0.1 | um 0.4–0.5 wie gru |
| esn | `match_shift` 0.00, `push_easy` −0.03, `servo` 0.01 | 0.00 | um 0.1 | unter 0.4 |

Für `robot_reach` gibt es keine kleine Entsprechung, also keine Prognose.

**Ergebnis** (2026-11-12, results/new3.jsonl und new3_lookmem.jsonl, Seeds 0–2): acht von neun Prognosen
treffen, eine nur in der Richtung.

| Netz | `robot_lookmem` (6000) | `robot_findc` (24000) | `robot_gaze` (6000) | `robot_reach` (6000) |
|---|---|---|---|---|
| vitmem | 0.87 (alle Seeds; Richtung richtig, Höhe unterschätzt) | 0.61 (trifft) | 0.97 (trifft) | 0.10 |
| lstm | 0.21 (0.29 / 0.00 / 0.33; schwächer als vorhergesagt) | 0.09 (trifft) | 0.40 (trifft) | 0.04 |
| esn | 0.00 (trifft) | 0.03 (trifft) | 0.09 (trifft) | 0.02 |

Damit über 10 bzw. 17 Netze: `match_shift` → `robot_lookmem` rho +0.86, `push_easy` → `robot_findc` +0.76,
`servo` → `robot_gaze` +0.43. **vitmem ist das beste Netz auf `robot_lookmem` ohne Vorstufe** (0.87 gegen
attnmem / gru 0.48 bei gleichen Updates) und zugleich vorn auf `robot_findc` und `robot_gaze`.

Erfahrungen, die in die Pipeline gehören:
- **Das Trainingsprotokoll entscheidet mit.** Rangfolgen kippen zwischen 6000 und 24000 Updates und mit einer
  Vorstufe (Hierarchie-Gitter auf `robot_lookmem`: 0.00 allein, bestes Netz mit Vorstufe). Ein „lohnt sich
  nicht“ gilt erst, wenn auch die Variante mit Zwischenzielen gescheitert ist.
- **Eine kleine Aufgabe sagt nur vorher, wenn sie denselben Engpass hat** wie die Roboter-Aufgabe. Die alte
  Gedächtnis-Batterie prüft Wiedergeben, die Roboter-Aufgabe braucht Vergleichen.
- **Für `robot_reach` und `robot_finds` gibt es noch keine kleine Entsprechung**, und beide löst bisher niemand:
  Dort kann die Pipeline noch nichts unterscheiden.

## Wo wir stehen

- Erledigt: Benchmark-Plattform, Gedächtnis-Varianten, Phase A, Phase B bis zur Bibliothek mit Servo-Stufe 1.
- Als Nächstes: `robot_reach` verstehen, die Bibliothek auf den Roboter-Aufgaben, die Regel zweiter Ordnung
  für innere Schichten.
- Danach: Servo mit Verzögerung und Regelkreis, Wahrnehmung als eigene Stufe, Lehrplan ohne Freeze,
  einheitliches Port-Interface, dann der gelernte Teacher (Phasen D–F).
- Gelernter Teacher (Phase D) begonnen 2026-11-23: Eine per ES gefundene lokale Regel für die inneren schnellen
  Gewichte von layer_s@25k lernt die ausgelassene Aufgabe `prev` (64 Beispiele) ohne Backprop schneller als
  Backprop (0,85 nach 20 Updates, grad 0,79, dfa 0,16). Sie überträgt sich nicht auf eine fernere Aufgabe
  (`diff`). Ein geteilter Teacher mit Schicht-Kennung kann Kopf- und Innen-Aufgaben zugleich (prev 0,66,
  xmFF 0,58 nach 20 Updates); ohne Kennung scheitert er. Der Innen-Gewinn kommt aus einem Hebb-Term mit
  globalem Modulator, nicht aus dem rückprojizierten Fehler.
- Noch nicht begonnen: Weltmodell, Reinforcement Learning.
