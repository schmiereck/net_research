# Phase D: eine per Evolution gefundene lokale Lernregel für die inneren schnellen Gewichte

Stand 2026-11-27. Ausführliche Darstellung als Grundlage für das Ergebnis-Papier. Die knappen, datierten
Einträge mit den Vorhersagen vor jedem Lauf stehen im `LOGBUCH.md` (2026-11-23 Vorarbeit 2, D.0, D.2 / D.3 /
D.5; 2026-11-24 Position im Netz, Übertragung; 2026-11-25 zweite Saat und zwei Architekturen, ES auf hier_s allein; 2026-11-26 Telemetrie je Aufruf, längerer Horizont; 2026-11-27 Fortsetzung des längeren Horizonts). Das Konzept steht in `PLAN_TRAINER.md`, Phase D.

## 1. Kurzfassung

Ein eingefrorenes, auf eine Zahlenfolgen-Aufgabe trainiertes Netz soll aus 64 Beispielen eine neue Ausgabe
lernen, nur über schnelle Zusatzgewichte F (W_eff = W + F) und ohne Backpropagation. Für Aufgaben, die eine
Änderung im Inneren des Netzes verlangen, versagt die bekannte lokale Regel *Direct Feedback Alignment* (dfa:
Fehler über eine feste Zufallsmatrix ins Innere) in kurzer Zeit (0,16 nach 20 Updates), Backprop auf dieselben
schnellen Gewichte schafft 0,79. Wir lassen eine Evolutionsstrategie (ES) einen kleinen Teacher suchen: ein MLP
mit 469 Parametern, das für jede Einheit jeder Schicht aus lokaler Telemetrie (rückgegebener Fehler, Aktivität,
Verlust und Lernfortschritt der Episode, Schicht) die Änderung ihrer Gewichte bestimmt.

Ergebnisse:

1. **Die gefundene Regel lernt eine ausgelassene Aufgabe auf eigenen Startnetzen ohne Backprop so schnell wie
   oder schneller als Backprop** (Regel D.3: 0,85 nach 20 Updates, 0,99 nach 200; Backprop 0,79 / 0,95; dfa
   0,16 / 0,75). Sie verliert über ihren Trainings-Horizont von 20 Updates hinaus nichts.
2. **Eine Regel für zwei Aufgabenarten:** Mit größeren ES-Schritten findet ES eine Regel, die Aufgaben, die nur
   eine neue Auslese verlangen, und Aufgaben, die eine Änderung im Inneren verlangen, zugleich lernt (beide
   ausgelassenen Test-Aufgaben: 0,66 und 0,58 nach 20 Updates; Validierung 0,54 bei einem Idealwert von etwa
   0,57).
3. **Was die Regel tut:** Sie nutzt den rückgegebenen Fehler im Inneren nicht. Den ganzen Gewinn im Inneren
   trägt ein Hebb-Term auf der ersten Schicht, dessen Vorzeichen und Stärke ein globales Signal aus dem
   Lernverlauf der Episode setzt (Drei-Faktor-Regel: Eingang × Ausgang × Modulator). Ohne diesen Term fällt die
   Leistung von 0,71 auf 0,14.
4. **Position im Netz:** Der Teacher braucht eine Kennung der Schicht (ohne sie 0,07 statt 0,54), aber keinen
   eigenen Teacher je Schicht (gleich gut, jenseits des Trainings-Horizonts instabil).
5. **Übertragung:** Unverändert auf ein viermal größeres Netz derselben Architektur übertragen, lernt die Regel
   so schnell wie Backprop (0,81 gegen 0,82; dfa 0,24). Auf eine andere Architektur (Hierarchie) überträgt sich
   nur der Teil am Ausgang; der Innen-Teil hilft dort in keiner Stärke. Auch Meta-Training auf beiden
   Architekturen, mit Schicht-Name oder mit einer Kennung der Rolle, findet für die Hierarchie keine Innen-Regel
   (0,07, dfa 0,10) und kostet auf dem ersten Netz einen Teil des Innen-Gewinns (0,66 → 0,41). Selbst eine
   Suche allein auf der Hierarchie findet dort keine Innen-Regel (0,13, Backprop 0,59), auch nicht, wenn der
   Teacher die wiederholten Aufrufe einer Abbildung unterscheiden kann (0,10). Erst mit einer Fitness über 100
   statt 20 Updates findet ES dort einen Innen-Teil: schneller als dfa bis etwa 50 Updates (prev 0,20 nach 20,
   dfa 0,10), dann ein Plateau bei 0,26–0,30; eine Fortsetzung der Suche hebt es auf 0,39 nach 100 Updates
   (dfa 0,47) und kostet dafür den schnellen Teil (0,13 nach 20).
6. **Wiederholbarkeit:** Eine zweite ES-Suche mit anderer Saat findet wieder eine Regel für beide
   Aufgabenarten (Validierung 0,53 gegen 0,54); die Gewichtung zwischen Kopf und Innen hängt von der Saat ab.
7. **Grenze:** Eine fernere Aufgabe (Differenz zweier Zahlen) lernt keine gefundene Regel; nur Backprop.

## 2. Fragestellung und Einordnung

Das Gesamtvorhaben (PLAN_TRAINER.md) ist ein Teacher, der einem trainierten Netz schnell Neues beibringt, ohne
das Alte zu zerstören. Phase B hat gezeigt: Für Anpassungen, die nur eine neue Auslese verlangen, reichen
schnelle Gewichte am Ausgang (Kopf) mit einer Regel zweiter Ordnung (`rls_rf`, ein Update genügt). Für
Anpassungen, die im Inneren etwas ändern müssen, gab es keine schnelle lokale Regel: Kopf-Regeln passen die
64 Beispiele an, verallgemeinern aber nicht; dfa lernt innen, aber langsam; Backprop lernt schnell, ist aber
nicht lokal.

Phase D fragt: **Lässt sich eine lokale Regel für die inneren schnellen Gewichte durch Meta-Lernen finden, die
die Lücke zwischen dfa und Backprop schließt, und ist sie mehr als eine bessere Schrittweite?**

Festlegungen (vom Nutzer freigegeben, 2026-11-23):

- **Orakel-Gate (`@task`):** Wann gelernt wird, ist gegeben (in der Bibliothek aus Phase B gelöst); Phase D
  lernt nur das *Wie*. Das Grundnetz bleibt eingefroren, die alte Aufgabe kann nicht vergessen werden.
- **Telemetrie als Eingang:** rückgegebener Fehler, Aktivität, Verlust S der Episode und seine Änderung ΔS.
- **ES als äußere Schleife**, Meta-Gradient höchstens als späterer Bezug.
- Gelernte Rückprojektion (D.4) nur, wenn D.3 nicht reicht.

Einordnung in die Literatur (zur Orientierung; die Arbeiten sind nicht mit unseren Zahlen verglichen):
feste Zufalls-Rückprojektion (Lillicrap et al. 2016, *Random synaptic feedback weights*; Nøkland 2016,
*Direct Feedback Alignment*); gelernte oder evolvierte Plastizitätsregeln (Miconi et al. 2018, *Differentiable
plasticity*; Najarro & Risi 2020, *Meta-learning through Hebbian plasticity in random networks*; Confavreux et
al. 2020, *A meta-learning approach to (re)discover plasticity rules*; Metz et al. 2019, *Meta-learning update
rules for unsupervised representation learning*); Drei-Faktor-Regeln mit Neuromodulator (Frémaux & Gerstner
2016); ES nach Salimans et al. 2017. Neu an unserem Aufbau ist die Kombination: eingefrorenes, für eine andere
Aufgabe trainiertes Netz; Lernen aus 64 Beispielen in 20 Updates; Regel je Einheit aus normierter Telemetrie,
die dfa als Sonderfall enthält; Bewertung auf ausgelassenen Aufgaben, ungesehenen Startnetzen und fremden Netzen.

## 3. Aufbau

### 3.1 Grundnetz und schnelle Gewichte

- **Grundnetz:** `layer_s@25k`, ein Gitter aus 8 Zellen mit geteiltem Modul (fc1 130→52 mit GELU, fc2 52→26)
  und linearem Kopf 208→64; 24 712 Parameter; trainiert auf die numseq-Aufgabe (Zahlenfolgen; Startnetze je
  Seed festgelegt in `data/base_nets/numseq`). Eingefroren.
- **Schnelle Gewichte** F auf fc1, fc2 und Kopf (`fastweights.py`): W_eff = W + F, F startet bei null.
- **Ausgabe-Fehler** e = sigmoid(Logits) − Ziel. Am Kopf wird e direkt benutzt; ins Innere gelangt er wie bei
  dfa über feste Zufallsmatrizen B (eine je Abbildung, Gauß, Skala 1/√dim e): d = e·B.

### 3.2 Der Teacher (die gesuchte Regel)

Für jede Ausgangseinheit j jeder Abbildung (fc1, fc2, Kopf) und jede Zelle berechnet dasselbe kleine MLP
(9 → 16 → 16 → 2, tanh) aus der Telemetrie zwei Zahlen a_j, h_j.

Eingänge (Telemetrie):

| Eingang | Bedeutung |
|---|---|
| d_j / rms(d) | rückgegebener Fehler der Einheit, normiert über die Abbildung (am Kopf der echte Fehler) |
| tanh(y_j) | Ausgang der Einheit (Aktivität) |
| gelu'(z_j) bzw. 1 | Ableitung der Aktivierung (nur fc1), sonst 1 |
| S | Verlust der Episode auf den 64 Beispielen (für alle Einheiten gleich) |
| 10·ΔS | Änderung des Verlusts seit dem letzten Update |
| t / T | Update-Nummer, T = 20 |
| Kennung (3) | One-hot der Abbildung fc1 / fc2 / Kopf |

Update (für jede Abbildung mit Eingang x):

    δ_j = base_j · d_j · (1 + a_j) + h_j · tanh(y_j) · rms(d)
    ΔF  = − η_map · xᵀ δ / mittleres |x|²          mit η_map = η_dfa · exp(p_map)

base_j = gelu'(z_j) für fc1, sonst 1. Die letzte MLP-Schicht und p starten bei null: **θ = 0 ist exakt dfa**
(geprüft bitgleich, `teacher.py check`). Der erste Summand ist dfa mit einer gelernten Verstärkung je Einheit,
der zweite ein Hebb-Term (Eingang x mal Ausgang tanh(y)), dessen Vorzeichen und Stärke h_j der Teacher setzt.
Insgesamt 469 Parameter (MLP 466, Schrittweiten p 3).

Varianten der Position im Netz (`--pos`): `map` wie oben; `blind` ohne Kennung (Nullen) und mit einer
gemeinsamen Schrittweite für alle Abbildungen; `split` ein eigenes MLP je Abbildung (1401 Parameter).
Kontrolle D.2 (`--mode eta`): nur die drei Schrittweiten p werden gesucht, das MLP bleibt null (also dfa mit
anderer Schrittweite je Schicht).

### 3.3 Äußere Schleife (ES)

- Antithetische Paare, zentrierte Ränge, Adam auf dem Mittelwert; Population 48, 8 Episoden je Generation;
  beide Hälften eines Paars sehen dieselben Episoden.
- **Episode:** eine Aufgabe, ein Startnetz, eine Ziehung von k = 64 Beispielen; 20 Updates der Regel.
- **Fitness:** Testwertung auf 512 ungesehenen Folgen (exakt richtig), gemittelt nach 1, 5, 10 und 20 Updates
  (Fläche unter der Lernkurve).
- **Validierung:** alle 10 Generationen auf festen Episoden (5 Aufgaben × 3 Startnetze × 2 Ziehungen);
  gespeichert wird das beste validierte θ.
- Aufwand: eine Episode etwa 1 s auf einem CPU-Kern; 300 Generationen etwa 2,4–2,7 h mit 4 Prozessen.
- Einstellungen: D.2 σ 0,1, lr 0,05, 100 Generationen; D.3 σ 0,05, lr 0,02, 300 Generationen; Positions-Ablation
  (`map`, `blind`, `split`) σ 0,1, lr 0,05, 300 Generationen.

## 4. Aufgaben und Messung

### 4.1 Die Aufgaben-Familie (D.0)

Alle Aufgaben haben dieselben Eingaben wie die Grundaufgabe numseq (drei sichtbare Zahlen einer Folge); nur
die gewünschte Ausgabe ist neu. D.0 hat für jede Aufgabe die Leiter der bekannten Regeln gemessen (k = 64,
Testwertung nach 20 / 200 Updates, Startnetze 0–2):

| Aufgabe | Kopf, zweite Ordnung (`rls_rf`) | Delta-Regel am Kopf | dfa | Backprop auf F (`grad`) | Gruppe |
|---|---|---|---|---|---|
| xm0F, xmA5, xm33, xmFF (XOR mit Maske) | 0,52–0,59 | 0,33–0,57 / 0,66–0,78 | 0,01 | ≤ 0,04 | Kopf reicht |
| prev, prev2, prev3 (frühere Zahl ausgeben) | 0,09–0,25 | ≤ 0,06 / ≤ 0,16 | 0,08–0,21 / 0,66–0,72 | 0,71–0,80 / 0,90–0,96 | nur Backprop innen löst |
| plus / minus 1, 2; diff | ≤ 0,24 | ≤ 0,34 | ≤ 0,04 | ≤ 0,21 | bei k = 64 löst niemand |

Wichtiger Nebenbefund: **dfa zerstört die Kopf-Aufgaben** (0,01 gegen 0,78 mit der Delta-Regel am Kopf): Die
inneren Updates verschieben die Darstellung, die der Kopf gerade lernt. Ein guter Teacher muss also auch
wissen, wann er innen *nicht* schreiben soll.

### 4.2 Aufteilung

- **Meta-Train:** xm0F, xmA5, xm33 (Kopf) und prev2, prev3 (innen), Startnetze Seeds 0–2.
- **Meta-Test:** prev (nah; Verwandte im Training), xmFF (Kopf-Aufgabe, ausgelassen), diff mit k = 512 (fern,
  eine innere Rechnung); Startnetze Seeds 5–6, die im Meta-Training nie vorkamen.
- **Übertragung:** layer_s (gleiche Architektur, 101 080 Parameter, fc1 345→138, fc2 138→69, anders trainiert)
  und hier_s (Hierarchie, 99 656 Parameter, fc1 236→118, fc2 118→236), Seeds 0–2, 5, 6.

Bezugswerte der Fitness auf den Meta-Train-Aufgaben: dfa 0,019, Delta-Regel am Kopf 0,12, grad 0,165, je
Aufgabe das Bessere aus beiden 0,27, `rls_rf` 0,42.

## 5. Ergebnisse

### 5.1 Schrittweite gegen gelernte Regel (D.2, D.3)

| | Validierung | Kopf-Aufgaben | prev2 / prev3 | Schrittweite fc1 / fc2 / Kopf (× dfa) |
|---|---|---|---|---|
| Start = dfa | 0,019 | 0,006 | 0,05 / 0,03 | 1 / 1 / 1 |
| D.2 (nur Schrittweiten) | **0,44** | 0,68–0,72 | 0,08 / 0,03 | 0,16 / 0,014 / 34 |
| D.3 (Teacher, kleine ES-Schritte) | 0,17 | 0,03–0,04 | **0,39 / 0,34** | 0,34 / 0,15 / 3,0 |

Unerwartet: Schon die Wahl der Schrittweiten je Schicht schlägt alle bekannten Regeln auf den Kopf-Aufgaben,
indem sie den Kopf 34-mal schneller macht und innen fast abschaltet. Der Teacher D.3 hat das Gegenteil
gefunden: eine echte Innen-Regel, aber mit zu kleinem Kopf-Tempo. Mit σ 0,05 und lr 0,02 kam ES in 300
Generationen nicht zu der großen Kopf-Schrittweite.

### 5.2 Meta-Test (D.5)

Testwertung nach 1 / 5 / 10 / 20 / 200 Updates, Startnetze 5–6, je 2 Ziehungen:

| Fall | dfa | grad | rls_rf | D.2 | D.3 | `map` |
|---|---|---|---|---|---|---|
| prev, k = 64 | 0,00 / 0,02 / 0,08 / 0,16 / 0,75 | 0,01 / 0,37 / 0,60 / 0,79 / 0,95 | 0,23 / … / 0,24 | 0,01 / 0,07 / 0,13 / 0,14 / 0,16 | 0,01 / 0,17 / 0,60 / **0,85 / 0,99** | 0,01 / 0,33 / 0,45 / 0,66 / 0,80 |
| xmFF, k = 64 | 0,00 / … / 0,01 | 0,00 / … / 0,02 | 0,60 / 0,57 / 0,57 / 0,57 / 0,56 | **0,60 / 0,68 / 0,68 / 0,68 / 0,68** | 0,01 | 0,40 / 0,54 / 0,54 / 0,58 / 0,60 |
| diff, k = 512 | 0,00 / 0,00 / 0,01 / 0,02 / 0,11 | 0,01 / 0,10 / 0,20 / 0,35 / 0,86 | 0,21 / … / 0,16 | 0,01 / 0,03 / 0,03 / 0,05 / 0,12 | 0,01 / … / 0,01 | 0,02 / … / 0,01 |

- D.3 auf prev je Episode nach 20 Updates 0,80–0,90, nach 200 Updates 0,98–1,00. Das Erfolgskriterium des
  Konzepts (≥ 0,40 nach 20 Updates, nach 200 nicht unter dfa) ist klar erfüllt.
- Keine Kurzhorizont-Falle: Obwohl ES nur bis 20 Updates bewertet hat, lernt die Regel bis 200 weiter.
- D.2 überträgt sich auf die ausgelassene Kopf-Aufgabe xmFF besser als `rls_rf`.
- diff lernt keine gefundene Regel.

### 5.3 Position im Netz

| Variante | Validierung | Kopf-Aufgaben | prev2 / prev3 | Meta-Test prev (20 / 200) | Meta-Test xmFF (20 / 200) |
|---|---|---|---|---|---|
| `map` (Kennung, ein MLP) | 0,54 | 0,62–0,67 | 0,46 / 0,33 | 0,66 / 0,80 | 0,58 / 0,60 |
| `blind` (keine Kennung, eine Schrittweite) | 0,07 | 0,00 | 0,20 / 0,14 | 0,42 / **0,06** | 0,00 |
| `split` (ein MLP je Schicht) | 0,55 | 0,60–0,67 | 0,49 / 0,36 | 0,77 / 0,91 | 0,57 / **0,01** |

- Ohne Kennung findet ES nur eine halbe Innen-Lösung, die nach 20 Updates wieder zerfällt, und keinen
  schnellen Kopf. Die Telemetrie allein (echter Fehler am Kopf, rückgegebener innen, gelu' nur bei fc1) macht
  die Schichten nicht genug unterscheidbar.
- Ein eigenes MLP je Schicht bringt in der Validierung nichts (+0,007), lernt prev etwas schneller, bricht aber
  auf der Kopf-Aufgabe nach 50–100 Updates in allen Episoden zusammen. Vermutete Ursache: Die Update-Nummer t/T
  läuft jenseits des Trainings über 1 hinaus, und drei getrennte MLPs extrapolieren schlechter (ungeprüft).
- `map` und `split` sprangen im ES-Verlauf von einer reinen Innen-Lösung auf eine Lösung für beides (`map`
  zwischen Generation 60 und 120). Mit den größeren ES-Schritten ist das Ziel „beides zugleich“ erreichbar; die
  Spezialisten bleiben einzeln besser (D.3 auf prev, D.2 auf xmFF).

### 5.4 Was die gefundene Regel tut (Ausschalt-Proben an `map`)

Testwertung nach 20 Updates; in jeder Spalte ist ein Teil der Teacher-Ausgabe ersetzt:

| Fall | volle Regel | ohne Hebb-Term (h = 0) | a ohne Modulation je Einheit | fc1 reines dfa | innen aus |
|---|---|---|---|---|---|
| prev2 (Meta-Train) | 0,71 | 0,14 | 0,73 | 0,11 | 0,11 |
| prev (Meta-Test) | 0,75 | 0,15 | 0,72 | 0,10 | 0,10 |
| xm0F | 0,71 | 0,71 | 0,68 | 0,72 | 0,72 |
| xmFF | 0,56 | 0,62 | 0,57 | 0,63 | 0,63 |

Messungen in den Episoden:

- Die Stärke der Fehler-Updates ist in prev- und xm-Episoden gleich: fc1 etwa 0,24 × dfa, fc2 etwa 0,005 × dfa,
  Kopf etwa 16 × dfa. Der Teacher schaltet also nicht die Fehler-Updates je nach Aufgabe ein und aus.
- Der Hebb-Faktor h auf fc1 hängt vom Zustand der Episode ab. Bei prev2 ist er nach 5 Updates im Mittel −9 und
  hat bei fast allen Einheiten dasselbe Vorzeichen (starker anti-hebbischer Schub). Bei xm0F ist er +2,5
  (schwach hebbisch). Innerhalb eines Updates korreliert h mit −d (−0,4 bis −0,8), der Fehler moduliert ihn
  also auch je Einheit.
- Die Wirkung des Hebb-Terms ist scharf abgestimmt (layer_s, prev): ×0 0,08, ×0,3 0,24, ×1 0,83, ×3 0,00.

**Deutung.** Die Regel ist keine bessere Rückprojektion des Fehlers. Sie ist eine **Drei-Faktor-Hebb-Regel**:
Eingang x mal Ausgang tanh(y) mal ein Faktor h, den ein globales Signal aus dem Lernverlauf (S, ΔS, t) setzt und
der Fehler je Einheit leicht moduliert. Der Fehler über B bleibt innen ungenutzt (fc1 reines dfa: 0,11 wie
„innen aus“). Die Entscheidung „innen schreiben oder nicht“ trifft die Regel nicht über die Fehler-Updates,
sondern über Vorzeichen und Stärke des Hebb-Terms. In Episoden, in denen der Kopf allein schnell lernt (xm),
bleibt der Term klein und schadet wenig (xmFF 0,56 gegen 0,63 ohne innere Updates). In Episoden, in denen der
Verlust nach den ersten Updates hoch bleibt (prev), wird er groß und anti-hebbisch. Biologisch entspricht das
einem Neuromodulator, der Plastizität je nach Lernerfolg ein- und umschaltet.

Offen ist, *warum* ein anti-hebbischer Schub auf fc1 prev lösbar macht. Eine Vermutung: Er dekorreliert
die Darstellung der aktuellen Eingaben in fc1, sodass die gesuchte frühere Zahl für den schnellen Kopf linear
auslesbar wird. Geprüft ist das nicht.

### 5.5 Übertragung auf fremde Netze

Testwertung nach 20 (200) Updates, k = 64, 10 Episoden je Feld:

| Netz, Fall | dfa | grad | Delta-Regel am Kopf | rls_rf | D.2 | D.3 | `map` |
|---|---|---|---|---|---|---|---|
| layer_s, prev | 0,24 (0,77) | 0,82 (0,95) | 0,02 (0,12) | 0,20 | 0,11 | 0,47 (0,93) | **0,81 (0,89)** |
| layer_s, prev2 | 0,25 (0,81) | 0,89 (0,98) | 0,02 (0,09) | 0,15 | 0,09 | 0,46 (0,93) | 0,73 (0,82) |
| layer_s, xm0F | 0,01 | 0,04 | 0,56 (0,90) | 0,90 | 0,89 | 0,05 | 0,83 (0,85) |
| layer_s, xmFF | 0,01 | 0,01 | 0,27 (0,80) | 0,81 | 0,74 | 0,03 | 0,46 (0,47) |
| hier_s, prev | 0,14 (0,62) | 0,56 (0,72) | 0,03 (0,10) | 0,13 | 0,09 | 0,10 (0,29) | **0,06 (0,07)** |
| hier_s, prev2 | 0,05 (0,54) | 0,46 (0,65) | 0,02 (0,05) | 0,08 | 0,05 | 0,07 (0,28) | 0,03 (0,04) |
| hier_s, xm0F | 0,04 | 0,04 | 0,48 (0,74) | 0,63 | 0,72 | 0,26 | 0,70 (0,71) |
| hier_s, xmFF | 0,01 | 0,01 | 0,20 (0,57) | 0,52 | 0,56 | 0,15 | 0,49 (0,54) |

- **Gleiche Architektur, viermal größer, anders trainiert (layer_s):** Die Regel überträgt sich fast
  verlustfrei. Auf prev ist sie so schnell wie Backprop (0,81 gegen 0,82, Spanne über 10 Episoden 0,73–0,87).
  Die Normierungen der Telemetrie (d / rms, tanh(y), Fehler je Abbildung, η relativ zu dfa) machen sie
  unabhängig von der Breite.
- **Andere Architektur, gleiche Größe (hier_s):** Nur der Kopf-Teil überträgt sich. Der Hebb-Term ist dort in
  keiner Stärke nützlich (×0 bis ×3: 0,06–0,07; ×10 und mehr: 0,00–0,01). Die Regel liegt auf prev unter dfa,
  weil sie die inneren Fehler-Updates fast abschaltet. In der Hierarchie hat fc1 eine andere Rolle (fc2 weitet
  auf statt zu verdichten, fc1 / fc2 werden je Schritt 6-mal statt 4-mal aufgerufen). Welcher Unterschied
  entscheidet, ist offen.
- Auch auf layer_s bricht `split` auf den Kopf-Aufgaben nach mehr als 20 Updates zusammen (xm0F 0,84 → 0,09),
  `map` nicht.

### 5.6 Zweite Saat und zwei Architekturen im Meta-Training

Drei weitere ES-Läufe mit denselben Einstellungen wie `map` (300 Generationen, σ 0,1, lr 0,05): `pos_map_s1`
(andere Saat der Suche), `arch_map` (Episoden je zur Hälfte aus layer_s@25k und hier_s gezogen, Kennung wie
`map`) und `arch_role` (dasselbe, aber die Schicht wird durch ihre Rolle beschrieben: Kopf ja / nein,
log2(Ausgänge / Eingänge), log2(Aufrufe je Update) / 2; layer_s@25k fc1 / fc2 / Kopf [0, −1,32, 1] /
[0, −1, 1] / [1, −1,70, 0], hier_s [0, −1, 1,29] / [0, +1, 1,29] / [1, −2,88, 0]).

| Lauf | Netze im Training | Kennung | Validierung (Gen 300) | layer_s@25k | hier_s | prev2 | xm0F |
|---|---|---|---|---|---|---|---|
| `pos_map` | layer_s@25k | Name | 0,54 | – | – | 0,46 | 0,67 |
| `pos_map_s1` | layer_s@25k | Name | 0,53 | – | – | 0,36 | 0,71 |
| `arch_map` | layer_s@25k, hier_s | Name | 0,46 | 0,53 | 0,38 | 0,17 | 0,70 |
| `arch_role` | layer_s@25k, hier_s | Rolle | 0,46 | 0,54 | 0,39 | 0,18 | 0,70 |

Meta-Test, Testwertung nach 20 (200) Updates, 4 Episoden je Feld:

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

- **Wiederholbar:** Die zweite Saat erreicht dieselbe Validierung und löst wieder beide ausgelassenen Aufgaben.
  Sie gewichtet den Kopf stärker (layer_s xmFF 0,80, so gut wie rls_rf 0,79) und das Innere schwächer; auf prev
  bleibt sie nach 20 Updates stehen (0,60 → 0,63), `pos_map` nicht (0,66 → 0,80).
- **hier_s im Training hilft hier_s im Inneren nicht.** prev bleibt bei 0,07 (dfa 0,10, Backprop 0,59). Die
  Validierung auf hier_s steigt bis Generation 50 auf das Kopf-Niveau und dann nicht weiter; im Inneren von
  layer_s@25k verliert die Regel einen Teil (prev 0,41 statt 0,60–0,66). Die Kopf-Gewinne auf hier_s hat auch
  `pos_map_s1`, das hier_s nie gesehen hat.
- **Rollen-Kennung:** gleich gut lernbar (0,464 gegen 0,457), auf layer_s im Inneren etwas besser als
  `arch_map`, aber auf der ausgelassenen Aufgabe xmFF instabil: auf layer_s@25k 0,00 ab dem ersten Update, auf
  hier_s 0,00 nach dem ersten und dann Erholung auf 0,64. Ausschalt-Probe (Seeds 5–6): Mit dem inneren
  Hebb-Term auf null erreicht `arch_role` auf layer_s@25k 0,67 statt 0,00; die Ausschaltungen am Kopf retten
  nicht. Bei `arch_map` ändert keine Ausschaltung viel. Vermutung (ungeprüft): Die stetige Kennung lässt das
  MLP zwischen Rollen interpolieren, und dieser Zwischenbereich kippt auf einer neuen Telemetrie-Lage.

### 5.7 ES allein auf der Hierarchie

`hier_map`: wie `map`, aber alle Episoden aus hier_s (300 Generationen). Validierung 0,41; prev2 bleibt über
alle Generationen bei 0,03–0,05. Meta-Test, Testwertung nach 20 (200) Updates, 4 Episoden je Feld:

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

- **Keine Innen-Regel für die Hierarchie**, auch ohne Zielkonflikt: prev 0,13 knapp über dfa 0,10, weit unter
  Backprop 0,59. Es liegt also nicht am gemischten Meta-Training, sondern an der Regel-Familie. Kandidat für
  die fehlende Eingabe (ungeprüft): der Index des Aufrufs (fc1 / fc2 laufen in hier_s 6-mal je Update, die
  Telemetrie fasst diese Aufrufe je Abbildung zusammen) oder ein Fehler je Aufruf.
- **Kopf:** auf hier_s die beste Regel bisher (xmFF 0,71 gegen rls_rf 0,57).
- **Rückwärts keine Übertragung, auch nicht am Kopf:** Auf layer_s@25k und layer_s fällt xmFF auf 0,00–0,01,
  auf layer_s@25k kippt xm0F nach 20 Updates. Die Bindung an die Architektur gilt in beide Richtungen.

### 5.8 Telemetrie je Aufruf auf der Hierarchie

In beiden Netzen sind die mehrfachen Aufrufe einer Abbildung die Schritte der Rekurrenz (layer_s@25k 4 ×,
hier_s 6 × fc1 / fc2 je Update). Bis hier bekam jeder Aufruf einer Abbildung denselben rückprojizierten Fehler
(eine Zufallsmatrix je Abbildung) und keine Kennung. `call` (Commit bf3355c): wie `map`, dazu der Index des
Aufrufs (0 … 1) als zehnte Eingabe (485 Parameter) und eine eigene feste Rückprojektion je Aufruf. Lauf
`hier_call`: nur hier_s, 200 Generationen. Validierung 0,405, prev2 0,049 (`hier_map` bei Generation 200:
0,399, 0,041). Meta-Test, Testwertung nach 20 (200) Updates, 4 Episoden je Feld:

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

Bezug ohne gelernten Anteil (θ = 0 von `call`, also dfa mit Rückprojektion je Aufruf), hier_s prev, Seeds 5–6
× 2: 0,11 nach 20, 0,70 nach 200 Updates (dfa 0,10 / 0,60).

- **Die Unterscheidung der Aufrufe erschließt das Innere nicht:** prev 0,10 nach 20 Updates (dfa 0,10,
  Backprop 0,59). ES nutzt den Index (Änderung der Zeile 0,63 gegen 0,53 im Mittel der übrigen gemeinsamen
  Eingaben), aber ohne Gewinn.
- **Der Innen-Gewinn der Rückprojektion je Aufruf liegt jenseits des Trainings-Horizonts:** Für dfa bringt sie
  erst nach 200 Updates etwas (0,70 statt 0,60). Die Fitness sieht nur 20 Updates; die gefundene Regel hält
  das Innere still (0,12 nach 200).
- **Am Kopf etwas schwächer als `hier_map`:** xmFF 0,58 gegen 0,71 (200 statt 300 Generationen; Ursache offen).

### 5.9 Längerer Trainings-Horizont auf der Hierarchie

Auf hier_s lernt schon dfa das Innere erst spät (prev 0,10 / 0,47 nach 20 / 100 Updates). `hier_h100` (Commit
df7ebce): wie `hier_map`, aber jede Fitness-Episode 100 Updates (Testwertung nach 10, 20, 50 und 100 Updates
gemittelt; der Zeit-Eingang t / T läuft über die 100 Updates), Start vom besten θ von `hier_map`, 60
Generationen. Validierung 0,43 → 0,49, prev2 0,085 → 0,195, noch steigend. Meta-Test auf hier_s, Testwertung
nach 20 / 50 / 100 / 200 Updates, 4 Episoden je Feld:

| Fall | dfa@task | grad@task | `hier_map` | `hier_h100` |
|---|---|---|---|---|
| prev | 0,10 / 0,22 / 0,47 / 0,60 | 0,59 / 0,69 / 0,72 / 0,75 | 0,13 / 0,13 / 0,13 / 0,14 | **0,20 / 0,26 / 0,26 / 0,30** |
| prev2 | 0,06 / 0,18 / 0,37 / 0,53 | 0,46 / 0,61 / 0,64 / 0,66 | 0,07 / 0,07 / 0,07 / 0,08 | 0,05 / **0,26** / 0,28 / 0,31 |
| xmFF | 0,01 / 0,02 / 0,02 / 0,01 | 0,01 / 0,01 / 0,01 / 0,02 | 0,71 / 0,71 / 0,71 / 0,71 | **0,74 / 0,74 / 0,74 / 0,74** |
| xm0F | 0,07 / 0,02 / 0,02 / 0,01 | 0,04 / 0,04 / 0,05 / 0,05 | 0,78 / 0,78 / 0,77 / 0,77 | **0,84 / 0,84 / 0,83 / 0,83** |

- **Ein Innen-Teil, aber ein früh gesättigter:** prev 0,20 nach 20 Updates (dfa 0,10, `hier_map` 0,13), prev2
  0,26 nach 50 (dfa 0,18). Ab etwa 50 Updates steht die Regel (0,26 → 0,30 bis 200), dfa läuft auf 0,60 weiter.
- **ES öffnet fc1, nicht fc2:** p fc1 −3,0 → −1,8, fc2 −4,2 → −4,6. Wie auf layer_s sitzt der Innen-Teil in der
  ersten Abbildung.
- **Der Kopf wird besser:** xmFF 0,74, xm0F 0,84, die besten Kopf-Werte auf hier_s bisher.
- **Nicht fertig gesucht:** Die Validierung steigt bis Generation 60; Warmstart von `hier_map`.

**Fortsetzung `hier_h100b`** (60 weitere Generationen vom besten θ, Adam neu): Validierung 0,476 → 0,511, ab
Generation 50 flach. Meta-Test auf hier_s, Testwertung nach 20 / 50 / 100 / 200 Updates:

| Fall | dfa@task | grad@task | `hier_h100` | `hier_h100b` |
|---|---|---|---|---|
| prev | 0,10 / 0,22 / 0,47 / 0,60 | 0,59 / 0,69 / 0,72 / 0,75 | 0,20 / 0,26 / 0,26 / 0,30 | 0,13 / 0,28 / **0,39 / 0,42** |
| prev2 | 0,06 / 0,18 / 0,37 / 0,53 | 0,46 / 0,61 / 0,64 / 0,66 | 0,05 / 0,26 / 0,28 / 0,31 | 0,05 / **0,34 / 0,38** / 0,40 |
| xmFF | 0,01 / 0,02 / 0,02 / 0,01 | 0,01 / 0,01 / 0,01 / 0,02 | **0,74 / 0,74 / 0,74 / 0,74** | 0,68 / 0,70 / 0,72 / 0,72 |
| xm0F | 0,07 / 0,02 / 0,02 / 0,01 | 0,04 / 0,04 / 0,05 / 0,05 | 0,84 / 0,84 / 0,83 / 0,83 | 0,85 / 0,84 / 0,84 / 0,82 |

- **Das Plateau steigt:** prev nach 100 Updates 0,26 → 0,39, prev2 0,28 → 0,38 (dfa 0,47 / 0,37); prev2 nach
  50 Updates 0,34 gegen dfa 0,18. Nach 200 Updates bleibt die Regel unter dfa (prev 0,42 gegen 0,60).
- **Bezahlt mit dem schnellen Teil und etwas Kopf:** prev nach 20 Updates 0,20 → 0,13, xmFF 0,74 → 0,68.
- **Messgenauigkeit:** Für dasselbe θ (bestes θ von `hier_h100`) gibt die Validierung 0,4879 (Worker, `hier_h100` Generation 60),
  0,4757 (Worker, `hier_h100b` Generation 0) und 0,4854 (lokal). Die Kopf-Aufgaben stimmen dabei bitgleich überein,
  nur die Innen-Aufgaben weichen ab (prev2 0,195 / 0,186 / 0,183, prev3 0,192 / 0,140 / 0,191). Ursache nicht
  geprüft; vermutet: kleine Rechenunterschiede, die 100 Updates Innen-Lernen auf hier_s verstärken (geprüft nur,
  dass eine Episode auf layer_s@25k mit 20 Updates im selben Prozess unabhängig von der Reihenfolge gleich ist). Unterschiede der Innen-Werte
  unter etwa 0,05 sind auf hier_s mit 100 Updates nicht sicher.

**Ursache der Abweichung und Nachmessung mit 12 Episoden** (2026-11-27): Auf dem Worker lasen `--init` und `eval`
θ aus `results/teacher.jsonl`, wo es auf 10⁻⁶ gerundet war (jeder Job hat eigene Prüfpunkte). Schon diese
Rundung ändert einzelne Innen-Episoden auf hier_s mit 100 Updates um bis zu 0,09; lokal ist alles bitgleich.
θ wird seit Commit 6079f25 exakt gespeichert. Die Regel ist auf hier_s also empfindlich gegen winzige Änderungen
von θ; der Meta-Test braucht dort mehr Episoden. Mit 12 Episoden je Feld:

| Fall, Regel | nach 20 | nach 50 | nach 100 | nach 200 | Streuung je Episode nach 100 |
|---|---|---|---|---|---|
| prev, `hier_h100` | 0,15 | 0,27 | 0,30 | 0,31 | 0,08 |
| prev, `hier_h100b` | 0,10 | 0,32 | 0,38 | 0,40 | 0,14 |
| prev2, `hier_h100` | 0,08 | 0,26 | 0,27 | 0,28 | 0,08 |
| prev2, `hier_h100b` | 0,11 | 0,30 | 0,36 | 0,38 | 0,10 |

Gepaarter Unterschied `hier_h100b` − `hier_h100` (gleiche Startnetze und Ziehungen, 12 Paare): prev nach 20
Updates −0,05 ± 0,02 (4 von 12 positiv), nach 100 +0,08 ± 0,04 (8 von 12), nach 200 +0,09 ± 0,05 (7 von 12);
prev2 nach 100 +0,09 ± 0,04 (9 von 12), nach 200 +0,09 ± 0,05 (7 von 12) (± Standardfehler).

Der Gewinn der Fortsetzung im Inneren trägt (+0,08 bis +0,09 nach 100 Updates, etwa 2 Standardfehler), ist
aber kleiner als mit 4 Episoden gemessen; der Verlust nach 20 Updates ebenso.

## 6. Diskussion

1. **Meta-Lernen findet eine lokale Regel, die Backprop im kurzen Lernen erreicht.** Mit 64 Beispielen und 20
   Updates lernt die gefundene Regel eine Aufgabe, die eine Änderung im Inneren verlangt, so schnell wie
   Backprop auf dieselben Gewichte. Das gilt auf ausgelassenen Aufgaben, ungesehenen Startnetzen und einem
   viermal größeren Netz. Die Regel braucht dafür keinen Gradienten durch das Netz, keine symmetrischen
   Rückwärtsgewichte und keine gelernte Rückprojektion.
2. **Gefunden wurde ein bekanntes biologisches Muster, nicht eine bessere Fehler-Rückführung.** Angelegt war die
   Regel als dfa mit gelernter Verstärkung. ES hat den Fehlerweg im Inneren aber fast stillgelegt und das
   Lernen in einen modulierten Hebb-Term verlegt. Das passt zur Theorie der Drei-Faktor-Regeln:
   Plastizität = lokale Koinzidenz × globales Lern-Signal.
3. **Die Rolle einer Schicht ist eine Eigenschaft der Architektur.** Ohne Kennung der Schicht scheitert die
   Suche. Mit Kennung reicht ein geteilter Teacher und überträgt sich über die Größe des Netzes, aber nicht auf
   eine Architektur, in der dieselbe Abbildung eine andere Rolle spielt. Eine Regel für viele Architekturen
   braucht Meta-Training auf mehreren Architekturen oder eine Kennung, die die *Rolle* beschreibt (zum Beispiel
   Verdichten oder Aufweiten, Tiefe, Aufrufe je Schritt) statt des Namens. Beides haben wir geprüft (5.6):
   Keines von beiden erschließt das Innere der Hierarchie, und auch eine Suche allein auf der Hierarchie findet
   dort keine Innen-Regel (5.7), auch nicht mit Telemetrie je Aufruf (5.8). Für diese Regel-Familie ist die Innen-Regel an die Architektur gebunden, und
   für die Hierarchie findet ES mit 20 Updates in der Fitness keine. Dass die Familie eine Abbildung und nicht
   ihre Aufrufe beschreibt, ist nicht der Grund (5.8). Der kurze Trainings-Horizont ist ein Teil davon: Mit
   100 Updates findet ES einen Innen-Teil, der bis etwa 100 Updates mit dfa mithält oder es schlägt und dabei
   den Kopf gut lernt, über 100 Updates hinaus aber hinter dfa zurückfällt (5.9). Eine Innen-Regel auf dem Niveau von Backprop (0,59 nach 20) gibt es für die Hierarchie bisher
   nicht.
4. **Die Schrittweite ist eine starke Kontrolle.** Auf Aufgaben, die nur eine neue Auslese verlangen, ist
   „Kopf schnell, innen aus“ (D.2) schwer zu schlagen. Eine gelernte Regel muss sich deshalb immer gegen diese
   Kontrolle messen, sonst schreibt man einer Regel zu, was eine Schrittweite leistet.
5. **ES-Einstellung entscheidet mit.** Mit kleinen Schritten fand ES nur eine Teillösung (D.3), mit größeren
   beides zugleich (`map`). Eine zweite Saat für `map` bestätigt das Ergebnis, verschiebt aber das Gewicht
   zwischen Kopf und Innen (5.6). Für die übrigen Varianten gibt es je nur einen ES-Lauf.
6. **Die Validierung auf den Meta-Train-Aufgaben reicht nicht.** `arch_role` und `arch_map` sind dort gleich,
   auf einer ausgelassenen Aufgabe kippt `arch_role` aber vollständig. Ohne Meta-Test auf ausgelassenen
   Aufgaben hätten wir die Rollen-Kennung für gleichwertig gehalten.

## 7. Grenzen

- Ein ES-Lauf je Variante außer `map` (zwei Saaten); Meta-Test mit 2 Startnetzen × 2 Ziehungen (4 Episoden), Übertragung mit 10.
- Nur eine Aufgaben-Familie (numseq) mit gleichen Eingaben; nur k = 64 im Meta-Training.
- Orakel-Gate: Wann gelernt wird, ist vorgegeben. Das Zusammenspiel mit der Bibliothek (Erkennen, Auswählen,
  Vergessen) ist nicht geprüft.
- Ferne Aufgaben (diff, plus / minus) lernt keine gefundene Regel.
- Der Mechanismus des anti-hebbischen Schubs ist beschrieben, aber nicht erklärt.
- Auf hier_s mit 100 Updates reagieren Innen-Episoden stark auf winzige Änderungen von θ (Rundung auf 10⁻⁶:
  einzelne Episoden bis 0,09; 5.9). Meta-Tests mit 4 Episoden sind dort auf etwa ±0,04 genau; ältere θ in
  `results/teacher.jsonl` sind gerundet (seit Commit 6079f25 exakt). Worker und lokaler PC weichen bei
  exakt gleichem θ noch leicht ab (nicht geprüft).
- θ für die Übertragung aus `results/teacher.jsonl` (auf 10⁻⁶ gerundet; Abweichung zum Checkpoint ≤ 5·10⁻⁷).

## 8. Offene Fragen und nächste Schritte

1. ~~Mehrere Architekturen im Meta-Training, Rollen-Kennung~~ erledigt (5.6): erschließt das Innere von hier_s
   nicht. ~~ES auf hier_s allein~~ erledigt (5.7): keine Innen-Regel. ~~Telemetrie je Aufruf~~ erledigt (5.8):
   keine Innen-Regel; eine Trennung von Index und Rückprojektion je Aufruf lohnt deshalb nicht.
2. **Längerer Trainings-Horizont:** für hier_s mit 100 Updates erledigt (5.9): ein früh gesättigter Innen-Teil.
   Fortsetzung erledigt (5.9): Plateau steigt auf 0,39 nach 100 Updates, Validierung flach ab Generation 50.
   **Offen:** ein Lauf von null statt Warmstart; Horizont 200; für layer_s@25k, damit `map` auf prev das
   Niveau von D.3 erreicht. Etwa 11–14,5 min je Generation mit 6 Prozessen bei Horizont 100.
3. **Mechanismus:** Ausschalt-Proben je Eingang des Teachers (S, ΔS, t), Darstellung in fc1 vor und nach dem
   anti-hebbischen Schub (Dekorrelation? lineare Auslesbarkeit der früheren Zahl?).
4. ~~Wiederholbarkeit~~ erledigt (5.6). Offen: warum die zweite Saat auf prev nach 20 Updates stehen bleibt.
5. **Rollen-Kennung auf xmFF:** warum der innere Hebb-Term dort kippt; Kennung diskret statt stetig.
6. **Ferne Aufgaben (diff):** erst hier wäre die gelernte Rückprojektion (D.4) oder ein Meta-Gradient als
   Bezug sinnvoll.
7. **Zusammenspiel mit der Bibliothek:** Gate nicht mehr als Orakel, sondern aus der Bibliothek.

## 9. Belege und Reproduktion

| Was | Datei / Commit |
|---|---|
| Code | `netresearch/teacher.py` (D.1 df4998b; `--pos` ac1392b; `--model`, `--names` 7973cf9; `--seed`, `--models`, `--pos role` 6b2161b; Fortsetzen nach Unterbrechung d0357f2; `--pos call` bf3355c; `--horizon`, `--init` df7ebce; θ exakt gespeichert 6079f25), `netresearch/fastweights.py`, `netresearch/adapt.py` (Fälle `lib_<name>`) |
| D.0 Leiter | `results/phase_d_ladder.jsonl` (360 Zeilen), Job `20261123-184213-d0_ladder` |
| ES-Läufe | `results/teacher.jsonl` (eine Zeile je Generation; letzte Zeile mit θ und bestem θ): `d2_eta`, `d3_full`, `pos_map`, `pos_blind`, `pos_split`, `pos_map_s1`, `arch_map`, `arch_role`, `hier_map`, `hier_call`, `hier_h100`, `hier_h100b` |
| Meta-Test | `results/phase_d_test.jsonl` (116 Zeilen) |
| Übertragung | `results/phase_d_transfer.jsonl` (640 Zeilen) |
| Zweite Saat, zwei Architekturen, Hierarchie | `results/phase_d_arch.jsonl` (312 Zeilen) |
| Messabweichung hier_s | `results/phase_d_noise.jsonl` (48 Zeilen) |
| Startnetze | `data/base_nets/numseq/{layer_s@25k,layer_s,hier_s}_s{0,1,2,5,6}.pt` |

Befehle:

    python -m netresearch.teacher check                       # θ = 0 und alle --pos-Varianten bitgleich zu dfa
    python -m netresearch.teacher run --name pos_map --pos map --gens 300 --sigma 0.1 --lr 0.05 --workers 4
    python -m netresearch.teacher eval --names pos_map d3_full --cases lib_prev lib_xmFF --seeds 5 6 --ks 64
    python -m netresearch.teacher eval --names pos_map --model layer_s --cases lib_prev --seeds 0 1 2 5 6
    python -m netresearch.fastweights inner --models layer_s@25k --cases lib_prev --rules dfa@task grad@task --seeds 5 6

Die Ausschalt-Proben (Abschnitt 5.4, 5.5) liefen mit kleinen Skripten außerhalb des Repos. Sie ersetzen in
`Teach.mlp` einen Teil der Ausgabe (h = 0, a = Mittel, fc1 auf null, innen a = −1 und h = 0, h skaliert) und
messen die Testwertung nach 20 Updates. Sie lassen sich mit wenigen Zeilen nachbauen.
