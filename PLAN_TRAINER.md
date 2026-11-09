# Plan: Trainer-Netz und World-Model – schnelles Lernen ohne Backprop

Entwurf vom 2026-11-06, ergänzt am 2026-11-08 um das Konzept „Modulare Teacher-Actor-Architekturen“
(erarbeitet mit Gemini, Abschnitt 4c). Baut auf der Benchmark-Plattform auf (PLAN.md), auf den Ergebnissen
von Phase 3 (Weight-Sharing, Multi-Task) und auf dem Benchmark-Sieb (netresearch/sieve.py).

## 1. Ziel

Gesucht ist ein Netz, das eine neue Aufgabe oder ein neues Muster **mit wenigen Beispielen** lernt, ohne
dabei seine Fähigkeit zur Generalisierung zu verlieren.

Die Idee dahinter:

1. Ein **World-Model** (Basisnetz) hat aus vielen Aufgaben allgemeine Strukturen gelernt. Es löst ein neues
   Muster schon teilweise, aus der Generalisierung heraus.
2. Ein **Trainer-Netz** beobachtet das Basisnetz. Es sieht die Gewichte, die Aktivierungen und den
   Fehler beziehungsweise die Überraschung. Daraus erzeugt es direkt eine Gewichtsänderung, sodass das neue
   Muster danach „aus dem Gedächtnis“ gelöst wird.
3. Die Änderung darf das Allgemeinwissen nicht zerstören. Neues wird zuerst **schnell und lokal**
   gespeichert und später **langsam konsolidiert**.

Das Training selbst, also die innere Schleife, soll **ohne Backprop** auskommen. Das Trainer-Netz ersetzt den
Optimierer.

## 2. Einordnung: was es schon gibt

Die Idee hat Vorläufer. Wir können Bausteine übernehmen und uns klar abgrenzen.

| Richtung | Kernidee | Was wir übernehmen |
|---|---|---|
| Fast Weights / Fast Weight Programmers (Schmidhuber 1992, Ba et al. 2016) | Ein Netz schreibt kurzlebige Gewichte eines anderen Netzes | schnelle, abklingende Gewichtsschicht |
| Differentiable Plasticity (Miconi et al. 2018) | Hebb-Regel mit gelernter Stärke je Synapse | Plastizität als Grundmechanismus |
| Gelernte Lernregeln (Bengio 1990, Metz et al. 2019, Kirsch & Schmidhuber 2021) | Eine kleine, geteilte Regel je Synapse oder Neuron wird meta-gelernt, oft per Evolution | **lokale, geteilte Trainer-Regel** |
| Learned Optimizers (VeLO, 2022) | Ein Netz erzeugt aus Gradienten die Updates | Trainer liest Statistiken |
| Weight-Space-Netze (Navon et al. 2023, Zhou et al. 2023) | Netze, die Gewichte anderer Netze lesen und deuten, unter Beachtung der Permutationssymmetrie | Trainer „liest“ Gewichte |
| Meta-Learning (MAML, Reptile) | Eine Startinitialisierung, von der aus wenige Schritte genügen | Vergleichsbasis |
| Complementary Learning Systems (Hippocampus/Kortex, McClelland 1995) | schnelles episodisches Speichern, langsame Konsolidierung | **zweistufiges Gedächtnis** |
| EWC, Replay | Vergessen verhindern | Schutz der Generalisierung |

**Was hier neu ist:** Unsere Architektur ist modular mit **geteilten Modulen**. Bei layer_s oder hier_s
besteht das Basisnetz im Kern aus *einem* kleinen Modul (~10–30k Parameter), das an allen Positionen
wiederverwendet wird.
- Der Trainer muss dadurch nur einen kleinen Gewichtsraum lesen und verändern. Das ist eine riesige
  Vereinfachung gegenüber einem Trainer für ein ganzes Netz.
- Der Trainer kann selbst als **geteiltes Modul** an jeder Position sitzen. Er wird dann eine lokale
  Lernregel, die an jeder Stelle dieselbe ist, wie eine biologische Plastizitätsregel.
- Die Phase-3-Messungen zum Gradientenkonflikt zwischen Positionen zeigen, wo eine einzelne Regel an ihre
  Grenzen stoßen kann.

## 3. Die ehrliche Kernfrage: woher lernt der Trainer?

Der Trainer muss selbst gelernt werden. Dafür gibt es eine **äußere Schleife**, die über viele Aufgaben
optimiert, wie gut das Basisnetz *nach* der Anpassung durch den Trainer ist. Für sie gibt es drei Wege:

| Äußere Schleife | Backprop-frei? | Kosten | Bemerkung |
|---|---|---|---|
| **Evolution Strategies (ES)** | ja, komplett | hoch, aber gut parallelisierbar | sinnvoll, weil der Trainer klein ist (1–10k Parameter) |
| Meta-Gradient (Backprop durch die innere Schleife) | nein, nur außen | Speicher wächst mit der Zahl innerer Schritte | gut als Vergleich und zum Vorlernen |
| Selbstreferenz (der Trainer trainiert sich selbst) | ja | experimentell | Fernziel |

Mein Vorschlag ist, die innere Schleife strikt ohne Backprop zu bauen. Sie läuft dann zur Nutzungszeit,
schnell und lokal. Außen wird ES verwendet, und der Meta-Gradient dient als Vergleich. Damit bleibt
Backprop allenfalls ein Werkzeug, um das Verfahren zu *finden*. Das Verfahren selbst braucht es nicht.

## 4. Architektur-Entwurf

```
                 ┌──────────────── Basisnetz (World-Model) ────────────────┐
 Input ─► Enc ─► │ geteiltes Modul M an allen Positionen                    │ ─► Output-Bereiche
                 │   W_eff = W_slow + W_fast(Position, Zeit)                │    (Motorik / Klasse /
                 └───────▲───────────────────────────┬─────────────────────┘     Bits / Symbol)
                         │ ΔW_fast (Low-Rank)         │ Aktivierungen, Fehler/Überraschung
                 ┌───────┴───────────────────────────▼─────────────────────┐
                 │ Trainer T (geteilt je Position): liest W_slow-Statistik,  │
                 │ prä/post-Aktivität, lokales Fehler-/Neuheitssignal        │
                 └──────────────────────────────────────────────────────────┘
                         Konsolidierung (langsam): W_fast ─► W_slow
```

**Bausteine:**

1. **W_slow:** Langsame Gewichte, vorgelernt als World-Model (siehe Abschnitt 6).
2. **W_fast:** Schnelle Gewichte je Position, als niedrigrangige Korrektur (rank 1–4). Sie klingen langsam ab
   und dienen als Kurzzeit- oder episodisches Gedächtnis.
3. **Trainer T:** Ein kleines Netz, das an jeder Position dasselbe ist.
   - Eingänge: prä- und post-Aktivierung des Moduls, ein Fehler- oder Neuheitssignal, Statistiken der
     eigenen Gewichte (Norm, Projektionen auf die Aktivierung) und die bisherige Lernhistorie (ein eigener
     kleiner Zustand).
   - Ausgabe: Faktoren u, v und eine Lernstärke η für das Update ΔW_fast = η · u vᵀ.
   - So „liest“ der Trainer die Gewichte in der Form, in der sie gerade wirken, nämlich als Projektion der
     aktuellen Aktivität. Er muss die Gewichtsmatrix nicht als Ganzes betrachten. Das umgeht die
     Permutationssymmetrie elegant.
4. **Fehlersignal ohne Backprop:**
   - Am Ausgang ist der Fehler direkt bekannt (Ziel minus Vorhersage).
   - Ins Innere gelangt er über eine *feste zufällige Rückprojektion* (Feedback Alignment) oder über eine
     Rückprojektion, die der Trainer selbst lernt.
   - Unsere Gitter-Netze haben bereits Rückverbindungen (ILS, laterale Eingänge). Das Fehlersignal könnte
     als zusätzlicher Kanal durch genau diese Verbindungen laufen, ohne neue Struktur.
   - Bei Spielen ist das Signal die Expertenaktion oder die Belohnung.
5. **Überraschung als Schalter:** Der Trainer schreibt nur, wenn das Basisnetz unsicher ist oder falsch liegt.
   Bei hoher Konfidenz und richtiger Antwort bleibt alles, wie es ist. Das ist der Mechanismus „Lösung ist
   teilweise da → gezielt nachschärfen“.
6. **Konsolidierung:** In Pausen, etwa nach einer Episode, wird W_fast in W_slow übertragen.
   - Das geschieht durch eine Regel des Trainers oder durch Replay der gespeicherten Episoden.
   - Eine Bremse schützt dabei Gewichte, die für die Generalisierung wichtig sind (ähnlich EWC, aber als
     gelernte Bremse).

## 4b. Zwei Lernsignale: Überraschung (negativ) und Wiedererkennen (positiv)

Predictive Coding und energiebasierte Modelle liefern ein messbares **Überraschungssignal** S. Es steht für den
Vorhersagefehler beziehungsweise eine hohe Energie. Die Reaktion darauf ist: „Lernen, um S zu senken.“

Ergänzend suchen wir ein positives Signal R, das **Wiedererkennen aus Generalisierung** misst. Gemeint ist
„das kann ich teilweise, in diese Richtung will ich besser werden“. Kandidaten, die lokal in einem Modul
messbar sind:

| Signal R | Messung im Knoten | Vorbild |
|---|---|---|
| **Übereinstimmung** | Die Vorhersagen von unten (Input), von der Seite und von oben (Rückverbindungen, vorheriger Tick) stimmen überein | Predictive Coding: Erklärung passt; Konsens in Säulen |
| **Flüssigkeit / Einschwinggeschwindigkeit** | Bei mehreren Ticks pro Frame: Wie schnell wird der Zustand stabil? Schnelles Einrasten in einen Attraktor heißt bekannt. | Energiemodelle, Hopfield; „processing fluency“ und das Vertrautheitsgefühl in der Gedächtnispsychologie |
| **Bekannter Unterraum** | Anteil der aktuellen Aktivität, der im Hauptunterraum der langsamen Gewichte liegt (Projektion auf die führenden Singulärvektoren), gegenüber dem unbekannten Rest | wörtlich „in die Richtung, die ich schon kann“ |
| **Robustheit** | Die Antwort bleibt bei kleinen Störungen des Inputs gleich | Generalisierung statt Zufallstreffer |
| **Lernfortschritt** | Die Überraschung sinkt gerade, d. h. S(t) < S(t−k) | Intrinsische Motivation durch Lernfortschritt (Oudeyer & Kaplan, Schmidhuber) |
| **Besser als erwartet** | positiver Vorhersagefehler der Belohnung beziehungsweise Konfidenz (Spiele) | Dopamin-Signal; Drei-Faktor-Lernregeln (Hebb × Neuromodulator × Eligibility-Trace) |

**Kombination: vier Fälle mit verschiedener Lernreaktion**

| | R niedrig (nicht erkannt) | R hoch (erkannt) |
|---|---|---|
| **S niedrig** (kein Fehler) | unwichtig → nichts tun | kann ich → höchstens leicht konsolidieren |
| **S hoch** (Fehler) | wirklich neu → vorsichtig, episodisch speichern, Allgemeines *nicht* überschreiben | **„fast gekonnt“ → stark und schnell lernen, *innerhalb* des bekannten Unterraums** |

Der Fall „S hoch, R hoch“ ist genau das gesuchte Szenario: Die Struktur wird erkannt, aber das Detail stimmt
noch nicht. Weil das Update dann auf den bekannten Unterraum beschränkt wird, schützt es zugleich die
Generalisierung. Es baut das Vorhandene aus und verbiegt es nicht.

Für den Trainer heißt das: S und R sind seine wichtigsten Eingänge. Die feste Grundstruktur ist fest
verdrahtet, so wie ein evolutionär entstandener Lernmechanismus: zwei Modulatoren und eine Drei-Faktor-Regel.
Die Evolution (ES) optimiert nur, *wie* S und R zu Lernstärke, Richtung und Konsolidierung verrechnet werden.

**Erster Test, ohne neuen Trainer:** Sagen die R-Signale voraus, was schnell lernbar ist?
- Mit den vorhandenen Checkpoints (z. B. layer_s und hier_s auf cycle und count) werden für ungesehene Muster
  zuerst S und R gemessen.
- Danach wird jedes Muster einzeln nachtrainiert, und wir messen, wie schnell es gelernt wird und wie viel
  vom Rest dabei verloren geht.
- Korrelieren hohes R und schnelles, schonendes Lernen, dann taugt R als Steuersignal für den Trainer.

## 4c. Teacher-Actor-Konzept: einheitliches Port-Interface und vier Teacher-Kandidaten

Ergänzung vom 2026-11-08, aus einer Diskussion mit Gemini. Der „Teacher“ entspricht hier dem Trainer T.

### Einheitliches Port-Interface je Modul

Damit verschiedene Teacher ohne Umbau der Module gegeneinander getestet werden können, bekommt jedes Modul
zwei standardisierte Zusatz-Ports:

- **Telemetrie s_m (Modul → Teacher):** ein kompakter Status über die letzten t Takte, etwa mittlere
  Aktivierung, Varianz oder Entropie und ein lokaler Vorhersagefehler. Hier gehören auch S und R aus 4b hin.
- **Modulation c_m (Teacher → Modul):** ein Skalar oder kurzer Vektor, plus ein Freeze-Flag.

Das Interface ist der erste Baustein, den wir implementieren: Danach sind die Phasen B bis E nur noch
verschiedene Teacher an denselben Ports.

### Vier Kandidaten

| Kandidat | Eingriff des Teachers | Signal je Modul | Entspricht im Plan |
|---|---|---|---|
| **T1** lokale 3-Faktor-Plastizität | Skalar m ∈ [−1, 1] auf eine lokale Eligibility-Trace E (abklingend, x_i·y_j): ΔW = η·m·E | 1 Wert | Phase B, 4b (Drei-Faktor-Regel) |
| **T2** Low-Rank Fast-Weights | Vektoren u, v: W_eff = W_base + u vᵀ | 2N Werte | W_fast, Phase B |
| **T3** Freeze & Route | Freeze-Flag für gemeisterte Module, danach nur noch Bus-Gates zwischen eingefrorenen Modulen plus ein freies Kombinationsmodul | Gate-Vektor | **neu** |
| **T4** semantischer State-Critic | intrinsischer Leitvektor, der T1–T3 antreibt: Langeweile (perfekt vorhersagbar), Freude (Lernfortschritt), Gefahr (Verlust möglicher Folgezustände, Empowerment), Muster-Bonus (wiederholbare Aktionsfolgen) | Reward-Vektor | 4b, erweitert um Gefahr und Muster-Bonus |

Der Teacher bleibt klein und geteilt, bewertet seinen Eingriff nach kurzen Fenstern (t = 5…20 Schritte) und
wird per ES trainiert (wie Abschnitt 3).

### Bewusst ausgeschlossen

- **Volle Hypernetze**, die alle N×N Gewichte eines Moduls erzeugen: quadratische Kosten, langsame Konvergenz.
- **Naive Neugier**, die jede Unvorhersagbarkeit belohnt (Noisy-TV-Problem). Belohnt wird nur Lernfortschritt.
- **Tiefe Backprop-Ketten durch den Teacher** über viele Zeitschritte: Das verschiebt den Flaschenhals nur eine
  Ebene nach oben.

### Einordnung und Korrekturen (Abgleich mit unseren Messungen)

1. **Der Teacher löst nicht die Grid-World.** Das Konzept begründet sich mit schlecht skalierendem Backprop.
   Unsere Daten zeigen andere Ursachen:
   - Die Grid-Aufgaben scheitern am Bezugsrahmen: Mit zentriertem Bild erreichen alle Modelle 0.80–0.99,
     mit demselben Training (Frame-Test, results/frame.jsonl).
   - Das Gedächtnis scheitert an der Architektur: `delay` schaffen nur Modelle mit Scratchpad.

   Ziel des Teachers bleibt daher, wie in Abschnitt 1: **schnelles Nachlernen ohne Vergessen**.
2. **„Modul“ heißt bei uns Position, nicht Fähigkeit.** In layer und hier ist ein Modul eine Gitterposition.
   Bei geteilten Gewichten (`_s`) gibt es nur ein einziges Modul; ein Freeze friert dort alles ein.
   - T3 braucht deshalb individuelle Module (`_i`) oder eine eigene Fähigkeiten-Bibliothek am Bus.
   - Das ist eine offene Architekturentscheidung (Abschnitt 9).
3. **T4 braucht Reinforcement Learning.** Wir trainieren durch Imitation eines Experten (DAgger). Erkunden
   ohne Schritt-Rewards setzt eine RL-Schleife voraus (AGENDA P3). T4 kommt daher zuletzt.
4. **Messgröße:** „Wall-Clock bis 90 % gegen Backprop, von null an“ würde ein lokales Verfahren sehr
   wahrscheinlich verlieren. Gemessen wird wie in Abschnitt 5: k-shot-Anpassung und Erhalt.

### T3 als Lehrplan-Test über das Sieb

Die Sieb-Stufen sind ein fertiger Lehrplan (A1 → A2 → A3, A1 → M1 → M2 → M3). Testablauf:

1. Auf den Aufgaben einer Stufe trainieren, bis sie bestanden ist.
2. Gemeisterte Module einfrieren.
3. Die nächste Stufe lernen, wobei nur Gates und ein freies Kombinationsmodul trainiert werden.
4. Messen: Lerngeschwindigkeit der neuen Stufe und Erhalt der alten, gegen (a) von null an,
   (b) Feintuning ohne Freeze und (c) Multi-Task über beide Stufen.

## 5. Messprotokoll: was heißt „schnell und gut“?

Wir brauchen einen **Adaptions-Benchmark**. Er unterscheidet sich vom bisherigen Benchmark: Das Netz kennt die
Aufgabenfamilie bereits und muss sich auf eine *neue Variante* einstellen.

| Familie | Meta-Train | Meta-Test (neu) |
|---|---|---|
| cycle / cycle_mem | Zyklen der Train-Hälfte | ungesehene Zyklen; **ein einzelner** fester Zyklus soll in k Schritten gemerkt werden |
| count / numseq | Schrittweiten der Train-Menge | neue Schrittweiten, neue Regeln (z. B. ×2, Differenzfolgen) |
| digits / shapes | bekannte Fonts / Formen | neue Fonts; **neue Klassen** (k-shot: 1, 5 Beispiele je Klasse) |
| Spiele | Standardparameter | Varianten: andere Geschwindigkeit, gespiegelt, andere Farben, neue Hindernisse |
| ganz neue Aufgabe | 14 Tasks | die 15. Task (leave-one-out) |

**Metriken je Methode:**

- **Adaptionskurve:** Score nach k = 1, 5, 20, 100 Beispielen beziehungsweise Schritten. Daraus ergeben sich
  die Fläche unter der Kurve und die Zahl der Beispiele bis 80 % des Endwerts.
- **Erhalt (kein Vergessen):** Score auf den alten Aufgaben nach der Anpassung, als Differenz zu vorher.
- **Generalisierung des Gelernten:** Die Anpassung an ein Muster muss verwandte, ungesehene Varianten
  ebenfalls verbessern. Die Antwort darf also nicht nur auswendig gelernt sein.
- **Kosten:** Rechenzeit je Anpassungsschritt.

**Vergleichsverfahren (Baselines):**

1. Feintuning mit Adam beziehungsweise SGD, also Backprop als Referenz.
2. MAML- oder Reptile-Initialisierung plus SGD.
3. In-Context-Lernen ohne Gewichtsänderung (GRU, attnmem, also Gedächtnis im Zustand).
4. Hebb-Plastizität mit fester Regel.
5. Unser Trainer (Varianten in Abschnitt 7).

## 6. World-Model

Damit „Lösung teilweise erkennen“ überhaupt möglich ist, muss das Basisnetz breit vorgelernt sein:

- **Multi-Task-Training über alle 15 Tasks.** Dafür ist der heutige Nachtlauf die Grundlage. Er zeigt, welche
  Architektur das am besten verkraftet.
- **Eine selbstüberwachte Vorhersage als zusätzliche Aufgabe:** das nächste Bild, oder kompakter das nächste
  Bild in der Repräsentation des Encoders. Das ist das eigentliche World-Model, denn bei Spielen lernt das
  Netz dabei die Dynamik ohne Experte.
- **Ausgabe:** Dafür bräuchte die einheitliche Ausgabe einen fünften Bereich „Welt-Vorhersage“. 64 Slots
  reichen für ein ganzes Bild nicht. Es gibt zwei Optionen, die zu entscheiden sind:
  - (a) Vorhersage in den latenten Raum, ohne neue Ausgabe-Slots.
  - (b) Die Ausgabe wird um einen eigenen Bereich (768 Bits) erweitert.

## 7. Phasen

Reihenfolge seit 2026-11-08 (mit dem Teacher-Actor-Konzept aus 4c):

**Phase A – Adaptions-Benchmark (Grundlage)**
- Aufgabenfamilien mit Meta-Train- und Meta-Test-Varianten bauen (Tabelle in Abschnitt 5).
- Ein Protokoll für k-shot-Anpassung und Vergessen schreiben, mit einem eigenen Report.
- Startnetze sind die Checkpoints aus dem Sieb (results/checkpoints).
- Baselines: Adam-Feintuning und In-Context (GRU/attnmem, Gedächtnis-Gitter).
- **Erster Lauf, 2026-11-09** (netresearch/adapt.py, results/adapt.jsonl): 12 Modelle, 3 Seeds,
  200 Updates. Die Methoden sind Adam (lr 1e-3), Adam mit lr 1e-4, Replay und ein Netz von null an.
  - **fixcycle** (einen neuen Zyklus aus 6 Wörtern merken): Alle Methoden erreichen nach 200 Updates 1.00.
    - Von null an geht es am schnellsten: Die Gitter-Modelle stehen nach 5 Updates bei 0.6–0.67, nach 20
      bei 1.00. Das vortrainierte Netz liegt bei Adam nach 5 Updates bei 0.03 und nach 20 bei 0.5–0.86.
    - Das Vortraining bremst also das Nachlernen, statt es zu beschleunigen.
    - Vergessen mit Adam: Der Basis-Zyklus fällt bei layer_s um 0.90, bei mlp und gru um 0.50.
    - Geteilte Gewichte vergessen am stärksten, weil jede Position dasselbe Modul ist.
    - lr 1e-4 halbiert das Vergessen (0.4–0.5), ist aber viel langsamer.
    - Replay hält es bei 0.07–0.14 bei voller Leistung. Replay braucht aber die alten Daten.
  - **double / trib / countbig** (neue Rechenregel, k = 8 / 64 / 512 Beispiele): Keine Methode lernt die
    Regel in 200 Updates.
    - Die besten Werte: double 0.37 (layer_s_sp4, k = 512), countbig 0.26 (layer_s, Replay), trib 0.05.
    - Auch das Netz von null an bleibt bei ≤ 0.15. Das ist das „unmögliche“ Ende der Leiter.
    - Das Vergessen ist trotzdem voll: numseq fällt bei layer_s von 0.98 auf 0.02–0.15.
  - Messlatte für den Teacher (Phase B ff.): fixcycle in ≤ 5 Updates mit < 0.1 Vergessen und ohne Replay.
    Die Rechenregeln dienen als Gradmesser: Eine Methode, die sie schafft, lernt etwas, das Adam nicht schafft.

**Phase B – Port-Interface und feste Regeln (T1, T2 ohne gelernten Teacher)**
- Telemetrie- und Modulations-Ports (4c) in layer_s einbauen; W_slow + W_fast.
- T2: Low-Rank-Update u vᵀ; T1: Eligibility-Trace mit fehlergesteuertem Skalar (Feedback Alignment).
- Erster Fall: „einen neuen Zyklus merken“. Vergleich mit Adam-Feintuning.
- Die Frage dabei: Bringt eine schnelle Gewichtsschicht allein schon k-shot-Fähigkeit? Das ist die
  Untergrenze für den Teacher.
- **Erster Lauf, 2026-11-09** (netresearch/fastweights.py, results/fastweights.jsonl):
  - Aufbau: Die langsamen Gewichte bleiben eingefroren; schnelle Gewichte F liegen auf fc1, fc2 und Kopf.
  - Getestet auf fixcycle mit layer_s, hier_s, layer_s_sp4 und layer_s_am4, 3 Seeds × 4 Zyklen.
  - Die Schrittweiten sind vorher per Sweep gewählt (results/fastweights_sweep.jsonl).

  | Regel | Signal | nach 5 Updates | nach 20 | vergessen nach 20 | vergessen nach 200 |
  |---|---|---|---|---|---|
  | Adam (alles) | Gradient | 0.00–0.03 | 0.50–0.86 | 0.64–0.92 | 0.73–0.91 |
  | T2 lora (Rang 4, Adam) | Gradient | 0.01–0.06 | 0.06–0.31 | 0.87–0.97 | 0.87–0.97 |
  | T1 delta_head (nur Kopf, lokal) | Fehler am Ausgang | 0.01–0.13 | 0.89–0.97 | 0.71–0.80 | 0.81–0.90 |
  | T1 dfa (Feedback Alignment) | Fehler über feste Zufallsmatrix | 0.00–0.01 | 0.18–0.38 | 0.80–0.95 | 0.87–0.97 |
  | T1 np3 (skalarer 3. Faktor) | eine Zahl je Beispiel | 0.00 | 0.00 | 0.07–0.62 | 0.41–0.82 |
  | Kontrolle delta_gated | wie delta_head, wirkt nur bei ähnlicher Eingabe | 0.01–0.13 | 0.89–0.97 | 0.00 | 0.00 |

  - **Keine feste Regel schafft k-shot.** Nach 5 Updates stehen alle bei höchstens 0.13. Das Netz von null an
    lag in Phase A bei 0.6–0.67.
  - **Die lokale Delta-Regel am Kopf ist schneller als Adam auf dem ganzen Netz.** Nach 20 Updates erreicht sie
    0.89–0.97, Adam 0.50–0.86. Die gelernte Repräsentation reicht also für eine neue Ausleseschicht.
  - **Wie die Änderung gelernt wird, entscheidet nicht über das Vergessen.**
    - Low-Rank vergisst am meisten, weil seine wenigen Richtungen für alle Eingaben gelten.
    - Der skalare 3. Faktor lernt in 200 Updates nichts.
  - **Entscheidend ist, wo die Änderung wirkt.** Wenn dieselbe Kopf-Änderung nur bei Eingaben greift, die den
    gelernten ähneln, verschwindet das Vergessen ganz (0.00), bei unveränderter Lerngeschwindigkeit.
  - **Einschränkung:** Das Gate ist ein Speicher der Trainings-Eingaben, also ein episodisches Gedächtnis.
    - Bei fixcycle sind Training und Test dieselben 6 Eingaben, Generalisierung wird hier nicht geprüft.
    - Ein gelerntes Gate (Teacher, T3 Freeze & Route) müsste das „Wann“ aus dem Kontext ableiten, ohne die
      Eingaben einzeln zu speichern.
  - **Folgerung für den Teacher:** Ein Teacher muss vor allem entscheiden, wann und wo eine Änderung gelten
    soll (Kontext-Gate), nicht in erster Linie, wie sie gelernt wird. Den Lernschritt kann eine lokale
    Delta-Regel am Ausgang übernehmen.
  - **Vorbehalte** (Codex-Review):
    - Bei fixcycle lagen 2 von 12 Episoden je Modell und Regel schon im Schrittweiten-Sweep.
    - Der skalare 3. Faktor (np3) machte bei gleichem η 8-mal kleinere Schritte als die Delta-Regel. Selbst der
      größte Sweep-Wert entspricht nur etwa η = 0.4 der Delta-Regel; „lernt nichts“ gilt nur für diesen Bereich.
    - DFA nutzt eine Rückkopplungsmatrix je Spalte, für alle Zeilen gemeinsam.
- **Gelernte Kontext-Gates, 2026-11-09** (results/fastgate.jsonl):
  - Aufbau: dieselbe Delta-Regel am Kopf; die Änderung wirkt mit g(x) ∈ [0, 1].
  - Getestet mit layer_s, hier_s und layer_s_sp4, 3 Seeds; fixcycle sowie double, trib und countbig mit
    k = 8 / 64 / 512.
  - Keines der beiden gelernten Gates speichert Einzelbeispiele, die Basisaufgabe geht nur als Statistik ein
    (Mittelwert und Kovarianz der Kopf-Eingaben):
    - `novel`: Abstand zur Basisverteilung.
    - `lda`: Diskriminante zwischen Basis-Statistik und den k neuen Eingaben.

  | Fall | Vergessen 200 ohne Gate | mit `lda` | mit `novel` | Gate auf neuen Test-Eingaben (lda / novel / kNN) |
  |---|---|---|---|---|
  | fixcycle | 0.81–0.90 | 0.00–0.01 | 0.02–0.06 | 0.98 / 0.51–1.00 / 1.00 (Test = Training) |
  | double | 0.50–0.98 | 0.00–0.14 | 0.04–0.21 | 0.07–0.68 / 0.50–0.73 / 0.00 |
  | trib | 0.58–0.98 | 0.00–0.19 | 0.02–0.35 | 0.06–0.64 / 0.49–0.79 / 0.00 |
  | countbig | 0.21–0.39 | 0.00–0.06 | 0.03–0.11 | 0.09–0.72 / 0.40–0.50 / 0.00 |

  - **Das „Wann“ ist mit einfachen gelernten Gates lösbar.** Das Vergessen sinkt in allen Fällen auf nahe 0.
    - Bei fixcycle bleibt die Lerngeschwindigkeit dabei unverändert (lda).
    - Das novel-Gate ist bei layer_s auf fixcycle zu vorsichtig (Gate 0.5–0.6): Das neue Wissen ist nach
      200 Updates erst zu 0.90 erreicht statt 1.00.
  - **Die gelernten Gates generalisieren auf unbekannte Eingaben derselben neuen Aufgabe, das kNN-Gate nicht**
    (Gate 0.00 auf den Testfolgen).
    - Überraschend: Auch double und trib, die dieselbe Eingabeform wie numseq haben, werden erkannt. Die
      Kopf-Eingaben der neuen Folgen liegen also außerhalb der Basisverteilung.
    - lda braucht dafür viele Beispiele (k = 8: Gate 0.06–0.14; k = 512: 0.6–0.7); novel ist von k unabhängig.
  - **Das „Wie“ bleibt offen.** double und trib lernt keine Methode, die nur den Kopf ändert (≤ 0.04). Auch
    Adam auf dem ganzen Netz erreicht nur 0.35–0.37 (double, k = 512).
    - Bei countbig verschlechtert die ungegatete Delta-Regel den Ausgangswert (k = 8, layer_s: 0.16 → 0.10). Mit Gate bleibt er
      erhalten.
- **Gegatete schnelle Gewichte im Inneren, mittlere Fälle, 2026-11-09** (results/fastinner.jsonl):
  - Neue Fälle (adapt.py), Eingaben = eigene Folgen der Basisaufgabe, nur die verlangte Ausgabe ändert sich,
    bewertet auf ungesehenen Folgen:
    - xormask: nächste Zahl XOR Maske.
    - prev: die letzte sichtbare Zahl kopieren.
    - plus1: nächste Zahl + 1.
    - cycle2: das übernächste Wort im Zyklus.
  - Schnelle Gewichte auf fc1, fc2 und Kopf, Regeln:
    - grad: Gradient durch das eingefrorene Netz (Obergrenze).
    - dfa: lokal, feste Zufalls-Rückkopplung.
    - delta_head: nur Kopf.
  - **Eingabe-Gates versagen hier**, weil neue und alte Aufgabe dieselben Eingaben haben:
    - grad@lda: Gate auf der Basis 0.15–0.33, auf den neuen Testfolgen 0.18–0.56.
    - Folge: Vergessen 0.2–0.5 und gebremstes Lernen.
    - Das „Wann“ muss hier von außen kommen, als Aufgaben- oder Kontextsignal, später als Telemetrie oder
      Modulation des Teachers.
    - Getestet ist deshalb das Orakel-Gate `@task`: g = 1 auf Daten der neuen Aufgabe, 0 auf der Basis.
  - Werte nach 200 Updates, 3 Modelle (layer_s, hier_s, layer_s_sp4) × 3 Seeds × 2 Varianten:

  | Fall | k | Adam (vergisst) | grad@task | dfa@task | delta_head@task |
  |---|---|---|---|---|---|
  | xormask | 64 | 0.05–0.06 (0.84–0.96) | 0.04 | 0.01 | **0.67–0.87** |
  | xormask | 512 | 0.30–0.49 (0.87–0.99) | 0.27–0.38 | 0.03–0.06 | **0.83–0.97** |
  | prev | 64 | 0.61–0.97 (0.86–0.99) | 0.69–0.96 | 0.53–0.84 | 0.09–0.13 |
  | prev | 512 | 1.00 (0.87–0.99) | 1.00 | **0.95–0.99** | 0.53–0.78 |
  | plus1 | 64 | 0.21–0.35 (0.80–0.87) | 0.13–0.19 | 0.01 | **0.34–0.41** |
  | plus1 | 512 | 0.55–0.84 (0.85–0.98) | 0.47–0.75 | 0.03–0.04 | 0.55–0.66 |
  | cycle2 | 64 / 512 | 0.07–0.15 | 0.06–0.12 | ≤ 0.06 | ≤ 0.07 |

  - **Mit Orakel-Gate ist das Vergessen bei allen Regeln exakt 0.00.** Das ist trivial, weil die schnellen
    Gewichte auf der Basis abgeschaltet sind; die Frage ist nur noch, wie gut gelernt wird.
  - **Gelernt wird mit gegateten schnellen Gewichten genauso gut wie mit Adam auf dem ganzen Netz.**
    grad@task erreicht fast Adams Werte (plus1 k = 512: 0.47–0.75 gegen 0.55–0.84), ohne zu vergessen.
  - **Welche lokale Regel passt, hängt davon ab, wo die Änderung sitzt:**
    - Ausgangs-Änderungen (xormask): delta_head ist mit Abstand am besten, besser als Adam und grad.
    - Innere Änderung (prev): DFA lernt sie lokal, ohne Backprop, fast so gut wie grad (k = 512: 0.95–0.99).
      Der Kopf allein erreicht nur 0.53–0.78.
    - plus1: delta_head ist bei k = 64 besser als Adam und grad, bei k = 512 etwas schwächer als Adam.
      DFA steigt bei plus1 kurz an (hier_s k = 512: 0.24 nach 5 Updates) und bricht dann ein; η = 3 ist für
      diesen Fall zu groß.
    - cycle2 lernt keine Methode (Leiter-Stufe über den mittleren Fällen).
  - **Folgerung:** Ein Teacher muss zwei Dinge liefern:
    - das „Wann“ als Kontextsignal, wenn sich die Eingaben nicht unterscheiden;
    - die Wahl des Wirkungsorts und der Regel (Kopf / Delta oder Inneres / DFA). Das ist ein natürlicher
      Kandidat für Modulation durch den Teacher.
  - **Vorbehalte:**
    - Die Schrittweiten sind auf Seed 5 abgestimmt (plus1 k = 512, prev k = 64). DFA bei plus1 ist dabei nicht
      eigens abgestimmt.
    - Codex-Review: Die numseq-Trennung lief im Lauf über die Generator-Parameter. Identische sichtbare
      Eingaben (arithmetisch und fibonacci-artig zugleich, a = k, etwa 1/256 der arithmetischen Folgen)
      konnten deshalb auf beiden Seiten liegen.
      - Danach behoben: Die Trennung läuft jetzt über die sichtbare Eingabe.
      - Zwei Kontroll-Läufe mit der neuen Trennung (layer_s, Seed 0, k = 512) liegen im Rauschen der alten
        Werte: plus1 grad@task 0.71 statt 0.69, xormask delta_head@task 0.97 statt 0.98.
    - Codex-Review: Die Zyklus-Trennung behandelt Perioden-Wiederholungen wie (0,2) und (0,2,0,2) als
      verschieden. Das betrifft auch die Basisaufgabe cycle und ist selten; es bleibt aus Gründen der
      Vergleichbarkeit so.
  - Nächste Fragen:
    - Das Kontextsignal nicht als Orakel, sondern als Port: Woran erkennt ein Teacher eine neue Aufgabe ohne
      neue Eingaben (Fehler-Telemetrie, Überraschung)?
    - Wirkungsort und Regel gemischt (delta_head + dfa zusammen), gewichtet durch eine Modulation.

**Phase C – T3 Freeze & Route als Lehrplan-Test**
- Über die Sieb-Stufen (4c), mit individuellen Modulen oder einer Fähigkeiten-Bibliothek am Bus.

**Phase D – Gelernter Teacher (Stufe 1)**
- Ein kleiner Teacher, geteilt an allen Positionen, liest die Telemetrie und schreibt die Modulation.
- Meta-Training per ES über viele Aufgaben-Episoden aus dem Meta-Train-Teil, mit dem Meta-Gradient als
  Vergleich. Messen auf dem Meta-Test-Teil.

**Phase E – Teacher liest Gewichte (Stufe 2)**
- Zusätzlich eine Zusammenfassung des Moduls selbst (Weight-Space-Encoder, permutationsinvariant) und ein
  eigener Zustand über die Lernhistorie.
- Er entscheidet über das *Wo*: welche Positionen, welche Unterräume.
- Die Frage dabei: Hilft das „Verstehen“ der Gewichte gegenüber der rein lokalen Regel?

**Phase F – Konsolidierung und Schutz der Generalisierung**
- W_fast → W_slow in Ruhephasen, mit gelernter Bremse oder Replay.
- Langzeittest: 20 neue Varianten nacheinander lernen und dabei das Vergessen und die Generalisierung
  verfolgen.

**Phase G – T4 State-Critic und World-Model**
- Setzt eine RL-Schleife voraus.
- Erkunden ohne Schritt-Rewards (Grid-World), Vorhersage des nächsten Bildes, Transfer auf eine ganz neue
  Aufgabe (leave-one-out).

## 8. Rechenaufwand und Risiken

- **CPU-only:**
  - ES braucht viele Auswertungen, typischerweise 32–128 Kandidaten je Generation und Hunderte von
    Generationen.
  - Machbar ist das nur mit kleinen Basisnetzen (10–30k Parameter) und kurzen Episoden; der zweite PC hilft
    dabei.
  - Die Basisnetze bleiben dafür absichtlich klein.
- **Risiko: der Trainer lernt nur „wenig tun“.** Die Meta-Zielfunktion muss Anpassung *und* Erhalt
  belohnen, sonst ist Nichtstun eine bequeme Lösung.
- **Risiko: Überanpassung an die Meta-Train-Familien.** Dagegen hilft die strikte Trennung der Familien und
  der leave-one-out-Test.
- **Realistische Erwartung:** Ein Verfahren, das Backprop *allgemein* schlägt, ist unwahrscheinlich.
  Erreichbar und interessant ist **schnelleres k-shot-Lernen innerhalb bekannter Aufgabenwelten bei weniger
  Vergessen**. Genau das ist das Szenario „Lösung teilweise erkennen und aus dem Gedächtnis festigen“.

## 9. Offene Fragen zur Entscheidung

1. Welches Basisnetz? Kandidaten sind layer_s und hier_s, nach den Multi-Task-Ergebnissen von heute Nacht.
2. ~~Äußere Schleife~~ → entschieden: **evolutionär (ES)**. Die Grundmechanismen sind fest verdrahtet, die
   Evolution stellt ihre Verrechnung ein (siehe 4b). Der Meta-Gradient dient nur als Vergleich.
3. World-Model-Vorhersage: latent (a) oder eigener Ausgabebereich für das nächste Bild (b)?
4. Mit welchem Adaptionsfall anfangen? Mein Vorschlag ist **„einen neuen Zyklus merken“** (cycle_mem mit
   einem festen, ungesehenen Muster). Er ist klein, schnell, gut messbar und entspricht genau deinem
   Beispiel.
5. T3: individuelle Module (`_i`, im Sieb schwächer) oder eine eigene Fähigkeiten-Bibliothek am Bus?
