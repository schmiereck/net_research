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
- **Kontext aus Fehlervergleich statt Orakel, 2026-11-09** (netresearch/context.py, results/context.jsonl):
  - Strom aus Batches zu 16 Beispielen, in Phasen: Basis 50 → neu 200 → Basis 50 → neu 50.
    - Das Netz sagt jeden Batch erst voraus (Online-Genauigkeit) und sieht danach die Antworten.
    - L0 = Fehler des eingefrorenen Netzes, L1 = Fehler mit schnellen Gewichten.
    - r = die schnellen Gewichte sind klar besser (L1 < 0.67 L0); s = Überraschung, das Basisnetz ist
      schlechter als auf der eigenen Aufgabe (über Mittel + 3 sd).
    - Der Kontext c ist der gleitende Mittelwert von max(r, s). Er entscheidet hart, ob die schnellen Gewichte
      beim nächsten Batch wirken (c > 0.5).
  - Modi:
    - err: lernt aus jedem Batch mit max(r, s) > 0.5.
    - err_c: lernt nur, wenn zusätzlich der Kontext an ist.
    - oracle: perfekter Kontext.
    - always: kein Gate.
  - Getestet mit layer_s, hier_s und layer_s_sp4, 3 Seeds × 2 Varianten, je Fall die besten Regeln aus dem
    Inneren-Lauf. Online-Genauigkeit je Phase:

  | Fall / Regel | Modus | Basis 1 | neu 2 (Ende) | Basis 3 | neu 4 |
  |---|---|---|---|---|---|
  | prev / dfa | always | 0.41 | 0.94 | 0.01 | 0.55 |
  |  | err_c | 0.95 | 0.96 | 0.89 | 0.93 |
  |  | oracle | 0.95 | 0.95 | 0.95 | 0.97 |
  | prev / grad | always | 0.56 | 1.00 | 0.00 | 0.05 |
  |  | err | 0.95 | 1.00 | 0.89 | 0.81 |
  |  | err_c | 0.95 | 1.00 | 0.89 | 0.95 |
  |  | oracle | 0.95 | 1.00 | 0.95 | 1.00 |
  | xormask / delta_head | always | 0.94 | 0.94 | 0.75 | 0.78 |
  |  | err_c | 0.95 | 0.94 | 0.89 | 0.90 |
  |  | oracle | 0.95 | 0.94 | 0.95 | 0.94 |
  | plus1 / delta_head | err_c | 0.95 | 0.61 | 0.89 | 0.63 |
  |  | oracle | 0.95 | 0.61 | 0.95 | 0.65 |
  | plus1 / grad | err_c | 0.95 | 0.55 | 0.89 | 0.54 |
  |  | oracle | 0.95 | 0.58 | 0.95 | 0.59 |

  - **Der Fehlervergleich ersetzt das Orakel fast verlustfrei.** Er kostet je Aufgabenwechsel 2–3
    falsch gegatete Batches, im Mittel 2 beim Wechsel auf die neue Aufgabe und 3 zurück zur Basis.
    - Beim zweiten Mal erkennen die schnellen Gewichte „ihre“ Aufgabe selbst (r), auch das in etwa 2 Batches.
    - Danach liegen Basis und neue Aufgabe auf Orakel-Niveau.
  - **Ohne Gate (always) zerstören DFA und grad die Basisaufgabe**, schon in der ersten Basis-Phase: Lernen
    auf bereits Gekonntem senkt die Basis von 0.95 auf 0.41 (dfa) bzw. 0.56 (grad). Schnelle Gewichte müssen
    also abgeschaltet sein, wenn sie nicht gebraucht werden; das betrifft auch ihr Lernen.
    - Die Delta-Regel am Kopf ist robuster: Die Basis sinkt nach der Rückkehr nur auf 0.75 und erholt sich
      in der Phase wieder auf 0.92.
  - **Lernen nur bei eingeschaltetem Kontext (err_c) ist nötig.** Die Überraschung allein feuert auf etwa
    2 von 50 Basis-Batches (schwere Batches, die Verlustverteilung hat einen langen Schwanz). In err trainiert
    das die schnellen Gewichte auf Basisdaten und trägt mit Adam die neue Aufgabe ab (prev / grad, neu 4:
    0.81 statt 0.95). Die Integration über mehrere Batches filtert solche Ausreißer.
  - **Bezug zum Teacher:** Damit ist eine erste Telemetrie gefunden, nämlich die zwei Fehler L0 und L1 und
    die Überraschung. Daraus entsteht ein Kontextsignal, das „wann wirken“ und „wann lernen“ steuert. Das
    ist die einfachste Form des Port-Interfaces; ein gelernter Teacher könnte TAU, ALPHA und die Schwellen
    ersetzen.
  - Vorbehalte:
    - Die Schwellen (M, TAU, ALPHA, mean + 3 sd) sind von Hand gesetzt und nicht abgestimmt. Die Smoke-Tests
      liefen auf Seed 5, der im Lauf nicht vorkommt.
    - Es gibt nur zwei Kontexte (Basis und ein Satz schneller Gewichte), und Aufgaben wechseln nur blockweise.
      Batch-weise Wechsel oder mehrere neue Aufgaben sind nicht getestet.
    - Codex-Review des Moduls: Zwei Fehler im ersten Lauf, beide behoben und neu gerechnet. DFA lief mit
      η = 1 statt 3, und die Umschalt-Verzögerung wurde auf gerundeten c-Werten gemessen.
- **Mehrere Sätze schneller Gewichte, Auswahl per Fehlervergleich, 2026-11-09** (netresearch/slots.py,
  results/slots.jsonl):
  - Der Strom (Batches zu 16) läuft so: Basis 30, dann xormask, prev und plus1 mit je 150 Batches, Basis 30,
    dann ein zweiter Besuch jeder Aufgabe mit je 40 Batches. Alle Aufgaben haben dieselben Eingaben.
    Variante 1 ändert die Reihenfolge.
  - Hypothesen je Batch:
    - Basis.
    - Satz i: er erklärt den Batch, wenn sein Fehler klar unter dem des Basisnetzes liegt UND nahe an seinem
      eigenen gelernten Niveau (unter 2 × Niveau + Überraschungs-Schwelle).
    - NEU: Das Basisnetz ist überrascht und kein Satz erklärt den Batch. Ein junger Satz (unter 30 Updates)
      bekommt diese Stimmen und lernt weiter.
    - Der gleitende Mittelwert der Stimmen wählt die aktive Hypothese. NEU legt einen Satz an (frei, sonst den
      am längsten nicht benutzten, mit Reset). Es lernt nur der aktive Satz, und nur, wenn der Batch für ihn
      stimmt.
  - Modi:
    - multi: bis zu 4 Sätze.
    - single: 1 Satz, Reset bei jeder neuen Aufgabe.
    - shared: 1 Satz für alles, ohne Reset.
    - oracle: perfekte Zuordnung.
  - Getestet mit layer_s, hier_s und layer_s_sp4, 3 Seeds × 2 Reihenfolgen. Online-Genauigkeit beim
    ZWEITEN Besuch (Auswahl-Trefferquote in Klammern):

  | Regel | Aufgabe | multi | single | shared | oracle |
  |---|---|---|---|---|---|
  | delta_head | xormask | **0.87** (0.94) | 0.54 | 0.65 | 0.93 |
  | delta_head | prev | **0.70** (0.95) | 0.07 | 0.31 | 0.74 |
  | delta_head | plus1 | **0.60** (0.95) | 0.30 | 0.27 | 0.64 |
  | grad | prev | **0.95** (0.95) | 0.31 | 0.13 | 1.00 |
  | grad | plus1 | **0.52** (0.95) | 0.18 | 0.00 | 0.57 |
  | grad | xormask | 0.22 (0.68) | 0.01 | 0.01 | 0.32 |
  | dfa | prev | **0.78** (0.90) | 0.07 | 0.25 | 0.95 |

  - Die Basis nach den drei Aufgaben liegt in allen Fehlervergleichs-Modi bei 0.88, beim Orakel bei 0.95.
    Der Unterschied sind die Umschalt-Batches; am Phasenende stehen alle Modi bei 0.96.
  - **Eine Bibliothek aus schnellen Gewichten funktioniert mit dem Fehlervergleich fast auf
    Orakel-Niveau.** Jede Aufgabe bekommt ihren Satz (3.2–3.4 Anlagen für 3 Aufgaben), beim zweiten Besuch
    wird zu 90–95 % der richtige gewählt.
    - Mit einem einzigen Satz sind frühere Aufgaben verloren (single), oder sie stören sich gegenseitig
      (shared). Beim zweiten Besuch liegen beide weit unter multi, zum Beispiel prev mit grad: 0.31 / 0.13
      gegen 0.95.
    - Die Kosten stecken in den ersten Batches nach einem Wechsel. Beim zweiten Besuch von xormask mit
      delta_head sind die ersten 10 Batches bei 0.71 statt 0.92.
  - **Die Auswahl ist nur so gut wie das Gelernte.** Aufgaben, die ein Satz kaum gelernt hat, erkennt der
    Fehlervergleich schlechter: xormask mit grad (Genauigkeit 0.25) wird nur zu 0.68 getroffen. Was eine
    Regel gar nicht lernt (dfa auf xormask und plus1, 0.02), ist auch beim Orakel 0.02.
  - **Das Kompetenz-Kriterium braucht eine absolute Untergrenze.** Nur relativ (unter 2 × Niveau) feuerte es
    nahe Fehler 0 auf normale Ausreißer. delta_head legte dann 6.4 Sätze für 3 Aufgaben an, und durch die
    Wiederverwendung ging prev verloren (zweiter Besuch 0.35, Treffer 0.47; results/slots_nofloor.jsonl).
    Mit der Untergrenze sind es 3.4 Sätze.
  - Vorbehalte:
    - Die Schwellen (M, LVL, Y, ALPHA, Mittel + 3 sd) sind von Hand gesetzt. Die Untergrenze kam nach dem
      ersten vollen Lauf dazu, auf denselben Seeds (nicht auf einem getrennten Abstimmungs-Seed).
    - Nur blockweise Wechsel und nur 3 Aufgaben bei 4 Plätzen; Verdrängung bei vollem Speicher ist kaum
      getestet.
    - Codex-Review des Moduls, drei Fehler, alle vor dem gewerteten Lauf behoben:
      - `sel` zählte eine nie gelernte Aufgabe (auf Basis abgebildet) als Treffer.
      - Beim Wiederverwenden eines Satzes ging Masse im gleitenden Mittel verloren.
      - LRU zählte nur Lernschritte, nicht die Nutzung.
      - Bestätigt hat Codex: Die Sätze stören sich gegenseitig nicht (mit einer Einzelinstanz exakt gleich),
        es gibt kein Antwort-Leck, und erster und zweiter Besuch überschneiden sich nicht.
  - Nächste Fragen: Bibliothek unter Druck (siehe unten); schnellere Wiedererkennung beim zweiten Besuch.
- **Bibliothek unter Druck, 2026-11-09** (netresearch/library.py, results/library.jsonl):
  - Sechs Aufgaben mit denselben Eingaben, in drei verwandten Paaren:
    - xm0F / xmA5 (XOR-Maske);
    - plus1 / minus1;
    - prev / prev2 (letzte / vorletzte Zahl kopieren).
  - Der Strom: jede Aufgabe einmal (100 Batches), dann der zweite Besuch in UMGEKEHRTER Reihenfolge (40).
    Mit K Plätzen und LRU sind dann die letzten K Aufgaben noch gespeichert.
  - Neu gegenüber slots.py:
    - Ein Arbeitspuffer: K + 1 Sätze, davon höchstens K fertige (≥ 30 Updates). Verdrängt wird erst, wenn
      ein neuer Satz reif ist.
    - LRU zählt nur bestätigte Nutzung, also wenn aktiver Satz und Batch-Stimme übereinstimmen.
    - Regel `pick`: Ein junger Satz trainiert delta_head und dfa parallel und behält nach 60 Updates den
      genaueren.
  - Alle drei Mechanismen kamen aus Smoke-Tests auf Seed 5:
    - Ohne Puffer verdrängte ein kurzer Fehlalarm innerhalb von minus1 einen fertigen Satz.
    - Mit LRU nach jeder Nutzung schützte eine Fehlauswahl (plus1 während minus1) den falschen Satz.
    - Nach Verlust gewählt, siegte delta_head zu früh.
  - Getestet mit layer_s, hier_s und layer_s_sp4, 3 Seeds × 2 Reihenfolgen, je 6 Aufgaben. Online-Genauigkeit
    beim zweiten Besuch, Mittel über die Aufgaben:

  | Regel | K = 2 | K = 3 | K = 6 | Orakel | erhalten (K = 2 / 3 / 6) |
  |---|---|---|---|---|---|
  | delta_head | 0.47 | 0.48 | 0.62 | 0.72 | 0.33 / 0.64 / 1.00 |
  | dfa | 0.11 | 0.22 | 0.23 | 0.30 | (lernt nur prev / prev2) |
  | pick | 0.51 | 0.53 | **0.68** | **0.79** | 0.33 / 0.64 / 1.00 |

  - **Verdrängung verhält sich wie geplant.** Erhalten bleiben genau so viele Aufgaben, wie Plätze da sind
    (K = 2: 2 von 6, K = 6: alle). Bei K = 3 sind es etwas mehr als 3, weil verwandte Aufgaben sich teilweise
    einen Satz teilen (siehe unten). Verdrängte Aufgaben werden im zweiten Besuch neu gelernt.
  - **Die Regelwahl je Satz (`pick`) lohnt sich, ist aber unzuverlässig.** Sie ist besser als jede feste
    Regel (Orakel 0.79 gegen 0.72 für delta_head und 0.30 für dfa).
    - Für die Ausgangs-Änderungen (XOR, ±1) wählt sie immer delta_head.
    - Für die Kopier-Aufgaben wählt sie DFA nur in 44 % (prev) bzw. 72–83 % (prev2) der Fälle; DFA wäre
      dort besser (Orakel: dfa 0.86 gegen delta_head 0.65 bei prev).
  - **Neuer Befund: verwandte Aufgaben teilen sich einen Satz und überschreiben sich dann.** In 15 von 18
    Läufen (K = 6) landet minus1 im Satz von plus1.
    - Ursache: Der plus1-Satz kann seine Aufgabe nur halb (Genauigkeit 0.6). Er ist deshalb tolerant genug,
      um auch minus1 zu „erklären“ (besser als das Basisnetz, nahe am eigenen, hohen Fehlerniveau), und lernt
      minus1 dazu.
    - Folge beim zweiten Besuch von plus1: Der Satz wird richtig gewählt (0.92), liefert aber nur 0.28
      (Orakel 0.64).
    - Bei XOR-Masken und Kopier-Aufgaben passiert das nicht; diese Sätze können ihre Aufgabe gut.
    - Wann „ähnlich genug zum Teilen“ gilt, ist die zentrale offene Frage einer Fähigkeiten-Bibliothek.
      Das Kompetenz-Kriterium allein entscheidet sie hier falsch, weil es an der Qualität des Satzes hängt.
  - Kosten der Wiedererkennung: Die ersten 10 Batches des zweiten Besuchs liegen bei K = 6 / pick bei 0.55,
    beim Orakel bei 0.78.
  - Vorbehalte:
    - Die Schwellen stammen aus slots.py, die drei neuen Mechanismen aus Smoke-Tests auf Seed 5 (nicht im
      Lauf). Sie waren nötig, damit die Verdrängung überhaupt wie geplant wirkt.
    - Codex-Review des Moduls: keine Fehler. Gezielte Checks bestanden: die Kandidaten trennen sauber,
      der verworfene Kandidat bleibt wirkungslos, die Daten sind getrennt.
- **Teilen nur ohne Schaden, 2026-11-09** (library.py, Modi k3c / k6c, results/library.jsonl):
  - **Erster Ansatz, verworfen: Probe-Update mit Ankern.**
    - Jeder Satz hält 32 eigene Beispiele als Anker. Ein Probe-Update (3 Schritte) auf dem neuen Batch
      wird an den Ankern gemessen und wieder zurückgenommen.
    - Das trennt nicht. Gemessen auf den Abstimmungs-Seeds 5 / 6 senkt bei einem schwach gelernten Satz
      schon ein Update der EIGENEN Aufgabe die Anker-Genauigkeit so stark wie ein fremdes. Zum Beispiel
      prev / plus1 mit delta_head: Median 0.03–0.06, p90 0.16. minus1 auf dem plus1-Satz: Median 0.00,
      p90 0.12. Auch das Verhältnis der Anker-Fehler überlappt (BCE).
    - Das Rauschen der Lernregel überdeckt den Konflikt. Mit H = 0.2 erzeugte die Probe 15 statt 7
      Anlagen (Seed 5).
    - Der Modus bleibt als k3p / k6p im Code, ist aber nicht im Lauf.
  - **Zweiter Ansatz: Konsistenztest.** Ein fertiger Satz erklärt einen Batch nur, wenn seine exakte
    Genauigkeit darauf mindestens halb so hoch ist wie auf seiner eigenen Aufgabe (gleitender Mittelwert
    über die Batches, aus denen er gelernt hat; nur geprüft, wenn dieser Wert ≥ 0.1 ist).
    - Die exakte Übereinstimmung ist scharf, wo der BCE-Fehler es nicht ist: Der plus1-Satz sagt +1 voraus
      und trifft bei minus1 fast nie exakt, obwohl die meisten der 8 Bits stimmen.
    - Er braucht keinen Beispielspeicher.
    - Abgestimmt nur auf Seed 6; dort steigt der zweite Besuch von plus1 von 0.18 auf 0.60.
  - Ergebnis auf den 3 Test-Seeds × 3 Modellen × 2 Reihenfolgen:

  | Regel | Modus | 2. Besuch Mittel | plus1 | minus1 | plus1 / minus1 im selben Satz | Anlagen |
  |---|---|---|---|---|---|---|
  | delta_head | k6 | 0.62 | 0.29 | 0.56 | 15 / 18 | 6.0 |
  | delta_head | **k6c** | **0.68** | **0.60** | 0.60 | **0 / 18** | 6.7 |
  | delta_head | oracle | 0.72 | 0.64 | 0.63 | – | – |
  | pick | k6 | 0.68 | 0.28 | 0.55 | 15 / 18 | 5.9 |
  | pick | **k6c** | **0.72** | **0.60** | 0.60 | **0 / 18** | 7.2 |
  | pick | oracle | 0.79 | 0.64 | 0.63 | – | – |

  - **Der Konsistenztest verhindert das schädliche Teilen vollständig.** plus1 und minus1 landen in 0 statt
    15 von 18 Läufen im selben Satz. plus1 beim zweiten Besuch: 0.60 statt 0.29, das Orakel liegt bei 0.64.
    Die Lücke zum Orakel schrumpft im Mittel auf 0.04 (delta_head) bzw. 0.07 (pick).
  - Kosten: etwas mehr Anlagen (6.7–7.2 statt 6 für 6 Aufgaben). Einzelne Fehlalarme landen jetzt im
    Arbeitspuffer und kosten keine fertigen Sätze.
  - Bei K = 3 bleiben nun genau 3 von 6 erhalten (Treffer 0.50 statt 0.64). Das frühere „mehr als K“ kam
    vom Teilen, das die Aufgaben dann gegenseitig beschädigt hat. Im Mittel bleibt der zweite Besuch gleich
    (0.49 gegen 0.48).
  - **Lehre für das Kriterium „ähnlich genug zum Teilen“:** Ein Maß für die Wirkung des Lernens (Probe)
    taugt bei verrauschten lokalen Regeln nicht. Ein Maß für die Vorhersagequalität auf dem neuen Batch,
    relativ zum eigenen Niveau des Satzes und in der Metrik der Aufgabe (exakt), taugt.
  - Offen bleibt: Geteilt wird jetzt praktisch nie; echtes Teilen bei wirklich gleicher Aufgabe (zweiter
    Besuch) funktioniert über die normale Auswahl. Ob zwei verwandte, verträgliche Aufgaben sich einen Satz
    sinnvoll teilen könnten, ist mit diesen Aufgaben nicht testbar, denn alle Paare widersprechen sich in
    der Ausgabe.
  - Codex-Review:
    - Die Konsistenz-Modi sind fehlerfrei; die Buchführung des Genauigkeitsniveaus stimmt.
    - Bei den Probe-Modi fand Codex vier Punkte, alle behoben:
      - Doku und Code verwendeten verschiedene Kriterien.
      - Die Probe entschied die Regelwahl von `pick` verfrüht.
      - Snapshot und Restore sichern keinen Optimizer-Zustand; das ist jetzt dokumentiert, die
        Bibliothek nutzt nur lokale Regeln ohne Optimizer.
      - Anker wurden auch in Modi gesammelt, die sie nicht brauchen.
    - Die alten Modi liefern nachweislich exakt die gespeicherten Ergebnisse (Vergleich der Logs).
  - Nächste Fragen:
    - Regelwahl stabiler machen (DFA bei prev nur in 53–56 % gewählt), etwa nach Genauigkeit über mehr
      Updates oder mit einem gelernten Prior.
    - Schnellere Wiedererkennung beim zweiten Besuch (die ersten 10 Batches: 0.59 gegen 0.78 beim Orakel).
- **Stabilere Regelwahl und schnellere Wiedererkennung, 2026-11-09** (library.py, Regel pickm, Modi
  k3cf / k6cf, results/library.jsonl):
  - **Diagnose Wiedererkennung** (gespeicherte k6c-Läufe):
    - Die Abstimmung zeigt schon im ersten Batch einer zurückkehrenden Aufgabe zu 97–99 % auf den richtigen
      Satz.
    - Der Kontext (EMA, ALPHA 0.3) braucht aber genau 2 Batches, um 0.5 zu überschreiten; diese 2 Batches
      liegen bei ~0.01.
    - Ab Batch 3 liegt delta_head beim Orakel (0.70 gegen 0.71). Die ganze Lücke der ersten 10 Batches ist
      Umschaltverzögerung.
  - **Diagnose Regelwahl** (Seeds 5 / 6, beide Kandidaten 140 Updates auf jeder Aufgabe allein):
    - Bei den Kopier-Aufgaben lernt DFA anfangs langsamer und schwankt stark; delta_head führt oft noch bei
      Update 60.
    - Am Ende ist DFA in 11 von 12 Kopier-Läufen klar besser. Die feste Entscheidung bei Update 60 trifft das
      nur in 8 von 12.
  - **Sofort-Umschalten (Flag f):** Der Kontext springt sofort, wenn zwei Bedingungen zusammen gelten:
    - Die aktive Hypothese scheitert klar: bei der Basis Fehler über der Überraschungsschwelle, bei einem
      fertigen Satz exakte Genauigkeit unter RHO × sein Niveau.
    - Die Abstimmung zeigt auf eine andere gespeicherte Hypothese, also die Basis oder einen fertigen,
      konsistenten Satz.
    - Eine Neu-Anlage braucht weiter die EMA; ein einzelner Fehlalarm legt also nichts an.
    - Die Antworten des aktuellen Batches wirken erst auf den nächsten Batch (von Codex geprüft).
  - **Sequentielle Regelwahl (pickm):**
    - Entschieden wird ab Update 60, aber erst, wenn ein Kandidat im langsamen Genauigkeitsmittel (EMA-Rate
      0.05) um mehr als 0.15 führt; spätestens nach 120 Updates.
    - Bis dahin sagt der Satz mit dem gerade besseren Kandidaten voraus.
    - Die Schwellen wurden an den 36 Lernkurven von Seed 5 / 6 gewählt; dort ergab das 0 Fehlwahlen statt 3,
      im Mittel bei Update ~66.
  - **Abstimmung, Seeds 5 / 6:**
    - Erste 10 Batches mit f: 0.56 → 0.63 (delta_head), 0.62 → 0.70 (pick).
    - pickm wählt DFA für prev in 100 % statt 75 %.
  - Ergebnis auf den Test-Seeds 0–2 (zweiter Besuch, Mittel über die Aufgaben):

  | Regel | Modus | 2. Besuch | erste 10 | Kopier-Aufgaben | Anlagen | Sofort-Wechsel |
  |---|---|---|---|---|---|---|
  | delta_head | k6c | 0.68 | 0.56 | 0.55 | 6.7 | – |
  | delta_head | **k6cf** | **0.70** | **0.63** | 0.57 | 6.7 | 6.9 |
  | delta_head | oracle | 0.72 | 0.71 | 0.60 | – | – |
  | pick | k6c | 0.72 | 0.59 | 0.68 | 7.2 | – |
  | pick | **k6cf** | **0.74** | **0.66** | 0.70 | 7.2 | 6.8 |
  | pick | oracle | 0.79 | 0.78 | 0.81 | – | – |
  | pickm | k6c | 0.72 | 0.59 | 0.69 | 7.2 | – |
  | pickm | **k6cf** | **0.75** | **0.67** | 0.71 | 7.1 | 6.8 |
  | pickm | oracle | 0.80 | 0.78 | 0.83 | – | – |
  | alle drei | k3c → k3cf | +0.01 | +0.03–0.04 | | unverändert | ~4 |

  Der Testlauf wurde auf dem Haupt-PC wegen Speichermangel abgebrochen. Die 12 fehlenden pickm-Jobs liefen
  auf dem Worker-PC (jobs submit --module library). Einer brach dort zuerst ab, weil parallele Prozesse
  denselben Basis-Checkpoint schrieben und lasen. Seither schreibt train.py Checkpoints atomar.
  - **Sofort-Umschalten wirkt wie geplant und kostet nichts:**
    - Erste 10 Batches +0.07 bei K = 6 in beiden Regeln, +0.03–0.04 bei K = 3.
    - Keine zusätzlichen Anlagen.
    - ~7 Sofort-Wechsel pro Lauf, das entspricht der Zahl der Aufgabenwechsel; Fehlwechsel innerhalb einer
      Aufgabe sind also selten.
    - Die Restlücke der ersten 10 Batches zum Orakel ist jetzt ~1 Batch Verzögerung plus der Lernrückstand
      der Sätze.
  - **pickm wählt die Regel richtiger, bringt in der Bibliothek aber wenig:**
    - DFA-Wahl bei prev / prev2: 0.58 → 0.77 (k6c), Orakel 0.67 → 0.75.
    - Im Orakel steigen die Kopier-Aufgaben von 0.81 auf 0.83.
    - In der Bibliothek von 0.68 auf 0.69 (k6c) bzw. 0.70 auf 0.71 (k6cf). Die verbleibende Lücke zum Orakel
      (0.71 gegen 0.83) liegt also nicht mehr an der Regelwahl.
    - Bester Modus insgesamt: pickm / k6cf, zweiter Besuch 0.75 gegen 0.80 beim Orakel.
    - Kandidat für die Ursache: Kopier-Sätze, die erst spät entscheiden, gehen unentschieden in die
      Verdrängung oder lernen weniger Batches. Das ist nicht geprüft.
  - Codex-Review: keine Fehler. Codex hat auch deterministisch geprüft (mit Attrappen statt echtem Training):
    - Die alten Modi sind in 24 Kombinationen unverändert.
    - Die Grenzfälle von pickm (Mindestalter, Marge, Horizont) verhalten sich wie vorgesehen.
    - Snapshot / Restore und Reset sichern bzw. setzen die neuen Werte.
    - Kein Durchsickern der Antworten in die Vorhersage desselben Batches.
  - Nächste Frage: Warum bleiben die Kopier-Aufgaben in der Bibliothek 0.12 unter dem Orakel, obwohl die
    Auswahl zu 97 % stimmt und die Regelwahl jetzt meist richtig ist?
- **Lücke bei den Kopier-Aufgaben, 2026-11-09** (library.py, Flag n, Modi k3cfn / k6cfn, results/library.jsonl):
  - **Diagnose:**
    - Beim ersten Besuch einer Kopier-Aufgabe wird der Satz im Mittel 0.8-mal neu begonnen, bei den anderen
      Aufgaben fast nie.
    - Die Neustarts kommen 35–97 Batches nach dem Anlegen, also kurz nach der Reife (30 Updates), bei einer
      Trefferquote von ~0.12. 19 der 30 Neustarts betreffen hier_s.
  - **Ursache** (Diagnose-Log NETRESEARCH_LIB_DIAG=1, Seeds 5 / 6):
    - Der Konsistenztest verwirft den schwachen Kopier-Satz auf einzelnen verrauschten Batches, obwohl der
      Satz den Fehler 6–8-fach senkt (log L0/L ≈ 2).
    - Typischer Fall: 1 von 16 Beispielen richtig (0.06) gegen 0.5 × Niveau ≈ 0.08.
    - Zwei solche Batches hintereinander legen einen neuen Satz an; der Lernfortschritt ist weg.
    - Ein seltenerer zweiter Auslöser: Der Fehler liegt knapp über der Kompetenzgrenze (Faktor 1.0–1.35),
      bei plus1 / minus1 (layer_s). Nicht behandelt.
  - **Änderung (Flag n):** Inkonsistent ist ein Satz erst, wenn seine exakte Genauigkeit um mehr als eine
    Binomial-Standardabweichung, sqrt(p (1 − p) / m), unter RHO × Niveau liegt.
    - plus1 auf minus1 wird weiter verworfen: Schwelle 0.18, Genauigkeit ≈ 0.
    - Z_CONS = 1 ist ohne Abstimmung gesetzt. Auf Seed 5 / 6 geprüft: Die Kopier-Aufgaben erreichen das
      Orakel, plus1 / minus1 bleiben unverändert.
  - Ergebnis auf den Test-Seeds 0–2 (zweiter Besuch, Lauf auf dem Worker-PC):

  | Regel | Modus | 2. Besuch | erste 10 | Kopier-Aufgaben | plus1 / minus1 | XOR | Anlagen |
  |---|---|---|---|---|---|---|---|
  | delta_head | k6cf | 0.70 | 0.63 | 0.57 | 0.62 | 0.91 | 6.7 |
  | delta_head | **k6cfn** | **0.70** | 0.64 | 0.58 | 0.62 | 0.91 | **6.1** |
  | delta_head | oracle | 0.72 | 0.71 | 0.60 | 0.64 | 0.93 | – |
  | pick | k6cf | 0.74 | 0.66 | 0.70 | 0.62 | 0.90 | 7.2 |
  | pick | **k6cfn** | **0.76** | 0.69 | **0.76** | 0.62 | 0.91 | **6.2** |
  | pick | oracle | 0.79 | 0.78 | 0.81 | 0.64 | 0.93 | – |
  | pickm | k6cf | 0.75 | 0.67 | 0.71 | 0.62 | 0.91 | 7.1 |
  | pickm | **k6cfn** | **0.77** | **0.70** | **0.80** | 0.62 | 0.91 | **6.1** |
  | pickm | oracle | 0.80 | 0.78 | 0.83 | 0.64 | 0.93 | – |
  | alle drei | k3cf → k3cfn | +0.01–0.02 | +0.02–0.03 | | | +0.02 | −1.1 |

  - **Die Lücke bei den Kopier-Aufgaben schließt sich weitgehend:** pickm 0.71 → 0.80 (Orakel 0.83).
  - Es werden praktisch nur noch so viele Sätze angelegt wie Aufgaben (6.1 für 6). Fehlanlagen gibt es also
    kaum noch.
  - plus1 / minus1 bleiben unverändert: Das Teilen bleibt verhindert.
  - **Bester Modus: pickm / k6cfn, zweiter Besuch 0.77 gegen 0.80 beim Orakel.** Die Restlücke:
    - erste 10 Batches 0.70 gegen 0.78 (~1 Batch Umschaltverzögerung bleibt)
    - plus1 / minus1 0.62 gegen 0.64
    - XOR 0.91 gegen 0.93
  - **Lehre:** Tests auf Batch-Statistiken brauchen eine Rauschgrenze, die mit dem Niveau des Satzes
    skaliert. Eine feste relative Schwelle verwirft genau die schwachen, langsam lernenden Sätze, die Schutz
    am nötigsten haben.
  - Codex-Review: Kern unverändert korrekt.
    - Ohne Flag n sind beide Prädikate gleich wie vorher (245 Grenzfälle geprüft).
    - m = mask.sum() ist der richtige Zähler.
    - Gefunden und behoben: Das Diagnose-Log zeigte den Abstand ohne Rauschzuschlag; es loggt jetzt auch
      das tatsächlich angewendete Testergebnis.

- **Bibliothek unter härteren Bedingungen, Stufe 1, 2026-11-09** (library.py, Suiten twelve / drift,
  results/library.jsonl mit Feld suite; alle Läufe auf dem Worker-PC):
  - **Suite twelve:** 12 Aufgaben, die bisherigen sechs plus xm33, xmFF, plus2, minus2, prev3 und diff
    (Schrittweite der Folge, eine innere Rechnung). Ablauf wie bisher: jede Aufgabe 100 Batches, Pause,
    alle in umgekehrter Reihenfolge je 40.
  - **Suite drift:** xm0F, prev, plus1 je 100 Batches.
    - Dann geht plus1 über 100 Batches schrittweise in plus2 über: Der Anteil der plus2-Beispiele steigt im
      Batch i auf (i + 0.5) / 100.
    - Danach plus2 50 Batches, Pause. Zweiter Besuch: plus2, die anderen und zuletzt plus1.
    - Das Orakel nimmt im Übergang je Batch die Mehrheitsaufgabe.
  - Ergebnis (zweiter Besuch, 3 Seeds × 3 Modelle × 2 Reihenfolgen):

  | Suite | Regel | Bibliothek | 2. Besuch | erste 10 | Anlagen | Orakel |
  |---|---|---|---|---|---|---|
  | twelve | delta_head | 6 Plätze | 0.47 | 0.32 | 14.9 | 0.65 |
  | twelve | delta_head | 12 Plätze | 0.61 | 0.55 | 11.6 | 0.65 |
  | twelve | pickm | 6 Plätze | 0.48 | 0.31 | 16.3 | 0.72 |
  | twelve | pickm | 12 Plätze | **0.67** | 0.60 | 11.9 | **0.72** |
  | drift | delta_head | 6 Plätze | 0.60 | 0.47 | 4.4 | 0.68 |
  | drift | pickm | 6 Plätze | **0.65** | 0.52 | 4.4 | **0.73** |

  - **twelve mit 12 Plätzen:** Die Mechanismen tragen auch bei doppelt so vielen, enger verwandten
    Aufgaben.
    - Lücke zum Orakel 0.05 (pickm), Anlagen 11.9 für 12 Aufgaben.
    - Nach Familie: XOR 0.89 (Orakel 0.92), ±1 / ±2 0.54 (0.59), Kopieren 0.77 (0.82).
    - diff lernt niemand (≤ 0.17): eine Sprosse über dem Leiter-Ende für 100 Batches.
  - **twelve mit 6 Plätzen:** Treffer 0.53, es bleiben also wie geplant etwa 6 von 12 Aufgaben erhalten.
    Die Lücke (0.48 gegen 0.72) ist Kapazität, kein Fehler der Auswahl.
  - **Drift, der eigentliche Befund:** Der plus1-Satz folgt dem Übergang und wird dabei zu plus2.
    - Im Übergang ist die Bibliothek sogar etwas besser als das Orakel (0.37 gegen 0.34; am Ende 0.49 gegen
      0.45), weil sie sich laufend anpasst.
    - plus2 bekommt aber nie einen eigenen Satz (4.4 Anlagen für 4 Aufgaben). Als plus1 zurückkommt, ist es
      verloren: 0.34 gegen 0.61 beim Orakel, obwohl der Satz formal noch lebt (Treffer 1.00).
    - Die anderen Aufgaben sind nicht betroffen (0.86 gegen 0.89).
    - Ein schleichender Wechsel überschreibt also eine Fähigkeit, ohne dass einer der Tests (Fehlervergleich,
      Konsistenz) anschlägt. Das gleitende Niveau des Satzes wandert mit.
  - Vorbehalt: Die Worker-Basisnetze weichen leicht von denen des Haupt-PCs ab (Gewichte bis 0.02,
    Basis-Genauigkeit gleich auf ~3 Stellen). Die Suiten twelve / drift liefen komplett auf dem Worker und
    sind in sich vergleichbar.
  - Nächster Schritt: **Abspalten bei Drift.**
    - Ein Satz merkt sich sein bestes Niveau und einen Schnappschuss davon.
    - Fällt sein laufendes Niveau deutlich darunter, obwohl er weiter erklärt und lernt, wird der
      Schnappschuss als eigener Satz eingefroren, und das Lernen geht in einer Kopie weiter.
    - Messlatte: plus1 beim Wiederkommen (0.34 → Orakel 0.61), ohne Verlust im Übergang.

- **Abspalten bei Drift, 2026-11-09** (library.py, Flag e, Modi k6cfne / k12cfne, results/library.jsonl mit
  nets = pinned):
  - **Mechanismus:** Ein fertiger Satz merkt sich sein bestes Genauigkeitsniveau und einen Schnappschuss davon.
    - Fällt das laufende Niveau unter Bestwert − max(0.4 × Bestwert, 3 sd der Niveau-EMA), wird
      abgespalten: Der aktuelle Stand lernt in einem freien oder jungen Platz weiter, der alte Satz geht
      auf seinen Schnappschuss zurück.
    - Die alte Fähigkeit behält damit ihre Identität.
    - Der Schnappschuss stammt immer vom besten Zustand, eine strengere Schwelle verzögert also nur.
  - **Abstimmung** (Seeds 5 / 6): Schwelle 0.25 (Flag d) gegen 0.4 (Flag e).
    - Beide retten plus1 im Drift.
    - 0.25 spaltet in Kaskaden (2.9 je Lauf) und kostet bei twelve 0.02.
    - 0.4 spaltet 1.7-mal und kostet nichts.
  - **Basis-Netze jetzt im Repository** (data/base_nets/numseq): Worker und Haupt-PC starten aus identischen
    Gewichten. Datensätze tragen nets = pinned; alle Vergleiche dieses Abschnitts nur unter pinned.
  - **Codex-Review fand fünf Fehler im Abspalten und einen in der Auswertung, alle behoben:**
    - Die Kopie übernahm bei DFA nicht die zufälligen Rückkopplungsmatrizen und deren Generator, lernte also
      mit einer anderen Regel weiter. Jetzt lernt sie für alle drei Regeln bitgenau wie das Original; selbst
      geprüft.
    - Veraltete Messwerte des Vorbesitzers des Platzes konnten sofort zurückschalten.
    - Die Kontext-Gutschrift ging an den alten Satz.
    - Mit Kapazität 1 stürzte es ab.
    - Schnappschüsse waren nachträglich veränderbar.
    - Die Auswertung mischte pinned und eigene Netze.
    - Die Läufe mit dem Fehler wurden verworfen und neu gerechnet.
  - Ergebnis auf den Test-Seeds 0–2 (zweiter Besuch, 18 Läufe je Zeile):

  | Suite | Regel | ohne Abspalten | mit Abspalten (e) | Orakel | Abspaltungen je Lauf |
  |---|---|---|---|---|---|
  | drift, plus1 beim Wiederkommen | pickm | 0.34 | **0.62** | 0.61 | 1.4 |
  | drift, plus1 beim Wiederkommen | delta_head | 0.32 | **0.62** | 0.61 | 1.6 |
  | drift, zweiter Besuch gesamt | pickm | 0.65 | **0.72** | 0.73 | |
  | drift, im Übergang | pickm | 0.37 | 0.37 | 0.33 | |
  | six | pickm | 0.77 | 0.77 | | 0.0 |
  | twelve, 12 Plätze | pickm | 0.68 | 0.68 | 0.72 | 0.9 |
  | twelve, 12 Plätze | delta_head | 0.62 | 0.62 | 0.65 | 2.4 |

  - **Das Abspalten löst den Drift vollständig:**
    - plus1 kommt auf Orakel-Niveau zurück.
    - Der zweite Besuch insgesamt liegt 0.01 unter dem Orakel.
    - Im Übergang bleibt die Bibliothek so gut wie vorher, also besser als das Orakel, das je Batch hart
      wechselt.
  - Ohne Drift (six) wird nie abgespalten.
  - Bei twelve spaltet es gelegentlich, ohne Schaden. Etwa die Hälfte schützt einen fremden Satz, der von
    einer verwandten Aufgabe mitbenutzt wird (plus2 / minus2, prev2 / prev3). Der Rest trifft vor allem diff,
    das niemand lernt und dessen Niveau nur schwankt (delta_head 23 von 43 Abspaltungen).
  - **Lehre:** Gegen schleichende Veränderung hilft kein Test auf den einzelnen Batch, sondern nur ein
    Gedächtnis für den eigenen besten Zustand. Abgespalten wird erst, wenn der Satz sich messbar
    verschlechtert, nicht schon, wenn er sich verändert.

- **Bibliothek Stufe 2: Servo-Aufgabe, 2026-11-10** (tasks/servo.py, library.py Suite servo, results/library.jsonl,
  results/servo_arch.jsonl, results/fastinner_servo.jsonl, results/servo_readout.jsonl):
  - **Aufgabe:** Zeiger (grün) und Ziel (rot) als je ein Pixel im Bild; Ausgabe ist der Schritt (dx, dy), je
    4 Bit mit Vorzeichen, in den 8 „bits“-Ausgängen. Ein Kommando, kein Regelkreis (erste, langsame Stufe).
    - Basis-Aufgabe: ideales Gerät (Kommando = Abstand).
    - Geräte als Kalibrierungen bei gleichen Eingaben: flipx (Motor gespiegelt), swap (Achsen vertauscht),
      rot90, strong (doppelte Verstärkung, Kommando halbiert), weak (halbe Verstärkung, Kommando verdoppelt,
      mit Anschlag), offx (Versatz +1). Verzögerung fehlt noch (braucht Gedächtnis, eigene Stufe).
  - **Basis-Netze:** Mit 1500 Updates lernt die Aufgabe niemand (bestes: vit 0.31). Mit 6000 Updates (Seed 5):
    vit 1.00, hier_s 1.00, layer_s 0.99, cnn_coord 0.99, cnn 0.97, mlp 0.23.
    - vit erreicht 0.96 nach 2000 Updates, cnn nach 3000, die Gitter-Netze nach 4500.
    - Basis-Netze (6000 Updates) liegen in data/base_nets/servo. hier_s Seed 2 ist schwächer (0.82).
  - **Bibliothek, unverändert aus Stufe 1** (Test-Seeds 0–2, zweiter Besuch, 18 Läufe je Zeile):

  | Regel | 3 Plätze | 6 Plätze | 6 Plätze + Abspalten | Orakel |
  |---|---|---|---|---|
  | delta_head | 0.41 | 0.63 | 0.63 | 0.65 |
  | pickm | 0.41 | 0.63 | 0.63 | 0.65 |
  | dfa | 0.01 | 0.01 | 0.01 | 0.02 |

    - Wiedererkennen und Verwalten übertragen sich ohne Anpassung: Auswahl 0.97, 6.2 Allokationen für 6 Geräte,
      erste 10 Batches beim Wiederkommen 0.57 (Orakel 0.63).
    - Je Gerät (6 Plätze): swap 0.89, weak 0.89, strong 0.56, offx 0.50, rot90 0.49, flipx 0.47.
    - pickm wählt immer delta_head. Zu Recht: dfa zerstört hier die Ausgabe (auch mit Orakel 0.02).
  - **Die Grenze ist das Lernen, nicht das Verwalten** (fastweights inner, Seeds 5 / 6, 512 Beispiele,
    200 Updates, ungesehene Testsituationen):

  | Gerät | Adam (alles) | Gradient auf schnelle Gewichte | delta_head | dfa |
  |---|---|---|---|---|
  | swap | 0.12 | 0.16 | 0.93 | 0.01 |
  | weak | 0.67 | 0.73 | 0.94 | 0.10 |
  | strong | 0.62 | 0.65 | 0.61 | 0.02 |
  | flipx | 0.56 | 0.63 | 0.51 | 0.01 |
  | offx | 0.46 | 0.47 | 0.55 | 0.00 |
  | rot90 | 0.12 | 0.17 | 0.50 | 0.01 |

    - Die lokale Regel am Kopf ist in 200 Updates so gut wie oder besser als der Gradient durch das Netz.
      Adam vergisst dabei die Basis-Aufgabe fast ganz (0.8–0.99), die schnellen Gewichte mit Kontext nicht.
    - swap und weak sind Umordnungen der Ausgabe-Bits und gehen linear. Vorzeichen, Versatz und Halbieren
      brauchen Überträge zwischen Bits.
  - **Auslese-Test** (scripts/servo_readout.py, Seeds 5 / 6, Korrektur der 8 Logits aus dem Kopf-Eingang,
    1600 Beispiele, ungesehene Testsituationen):

  | Merkmale | Anpassung | flipx | offx | rot90 | strong | swap | weak |
  |---|---|---|---|---|---|---|---|
  | linear | voll (Adam, 300 Schritte) | 0.74 | 0.76 | 0.74 | 0.71 | 0.98 | 0.98 |
  | linear + 4096 Zufallsmerkmale | voll | 0.93 | 0.94 | 0.94 | 0.90 | 0.98 | 0.98 |
  | linear | online, 100 Batches | 0.22 | 0.49 | 0.37 | 0.42 | 0.75 | 0.63 |
  | linear + 4096 Zufallsmerkmale | online | 0.10 | 0.32 | 0.22 | 0.17 | 0.46 | 0.34 |

    - Zwei Grenzen: (1) Die lineare Auslese des Kopf-Eingangs trägt bei den Übertrags-Geräten höchstens
      0.74; eine feste nichtlineare Erweiterung hebt das auf 0.93. (2) Die Online-Regel erreicht in 100
      Batches keine der beiden Obergrenzen; mit den Zufallsmerkmalen wird sie sogar langsamer (Schrittweite
      nicht abgestimmt, eigene Nachbildung der Regel, nicht die der Bibliothek).
    - **Folgerung für den Teacher:** Das Schreibziel „linearer Kopf“ reicht für Umordnungen, nicht für
      Rechnungen auf dem Ausgabe-Code. Kandidaten: nichtlinearer schneller Kopf (Erweiterung + lokale
      Regel mit besserer Schrittweite), oder ein Ausgabe-Code, in dem Geräte-Unterschiede linear sind.
  - **Architektur-Vergleich** (Worker, Nacht 2026-11-10; results/size.jsonl, scripts/size_summary.py): Befunde in
    AGENDA (Netzgröße und Modulzahl) und STAND.md. Für servo: vit löst es schon mit 25k; layer mit 16 Spalten
    nur 0.41; alle 400k-Netze 0.99–1.00.

- **Lernregel zweiter Ordnung am Kopf, 2026-11-10** (fastweights.py Regeln rls_head / rls_rf, library.py,
  results/library.jsonl mit nets = pinned):
  - **Anlass:** Auf servo erreicht die Delta-Regel am Kopf 0.5 bei Geraeten mit Rechnung; lineare Obergrenze
    bei voller Anpassung 0.74, mit Zufallsmerkmalen 0.93.
  - **Vorversuch** (Seeds 5 / 6, Korrektur der Logits aus dem Kopf-Eingang, ein Durchgang ueber 1600 Beispiele):
    Delta-Regel mit bester Schrittweite 0.66, kleinste Quadrate (Ridge) 0.85, Ridge mit 4096 Zufallsmerkmalen
    0.95. Der groessere Hebel ist die Regel, nicht die Erweiterung: Die Kopf-Eingaenge sind stark korreliert,
    ein Schritt erster Ordnung ist schlecht konditioniert.
  - **rls_head:** rekursive kleinste Quadrate am Kopf auf Logit-Ziele +-4. Je Satz schneller Gewichte eine
    Schaetzung der inversen Eingangs-Kovarianz P (Start I / 10). Kein Backprop; gebraucht werden Kopf-Eingang
    und Ausgabe-Fehler.
  - **rls_rf:** dasselbe auf [x, tanh(x R + b)] mit 1024 festen Zufallsmerkmalen (nichtlinearer schneller Kopf,
    gelernt wird weiter nur eine lineare Auslese). Etwa 3x Rechenzeit, 10 MB Zustand je Satz.
  - **Einzelfall** (512 Beispiele, EIN Update, ungesehene Tests): servo flipx 0.71 / 0.74, swap 0.95 / 0.96,
    numseq plus1 0.70 / 0.75, prev 0.95 / 0.95 (rls_head / rls_rf); Delta-Regel nach 200 Updates 0.53-0.91.
    Wird derselbe Batch wiederholt gezeigt, sinkt rls_head wieder (zaehlt Wiederholungen als neue Evidenz).
  - **Drift:** Ohne Vergessen wird die Regel steif. Die abgespaltene Kopie konnte nicht folgen und spaltete in
    Kaskaden (Seeds 5 / 6: 0.56, 4 Abspaltungen). Abhilfe ohne neue Konstante: Die abgespaltene Kopie startet
    mit frischem P. Damit 0.80; ein Vergessensfaktor (0.99 / 0.97) wirkte gleich gut, veraendert aber auch
    die ruhigen Aufgaben und wurde nicht genommen.
  - **Ergebnis auf den Test-Seeds 0-2** (zweiter Besuch, 18 Laeufe je Zelle, Bibliothek / Orakel):

  | Suite | delta_head | pickm | rls_head | rls_rf |
  |---|---|---|---|---|
  | servo | 0.63 / 0.65 | 0.63 / 0.65 | 0.86 / 0.88 | **0.91** / 0.94 |
  | six | 0.70 | 0.77 | 0.87 / 0.89 | **0.89** / 0.92 |
  | drift | 0.67 / 0.68 | 0.72 / 0.73 | 0.81 / 0.83 | **0.86** / 0.88 |
  | twelve (12 Plaetze) | 0.62 / 0.65 | 0.68 / 0.72 | 0.81 / 0.83 | **0.85** / 0.88 |

    - servo je Geraet (rls_rf): flipx 0.90, offx 0.90, rot90 0.90, strong 0.87, swap 0.95, weak 0.95
      (Delta-Regel: 0.47-0.56 und 0.89).
    - Das Verwalten bleibt nahe am Orakel (Luecke 0.02-0.03), Auswahl 0.97-0.98, erste 10 Batches beim
      Wiederkommen 0.79-0.84 auf servo.
    - Die Regel ist kein Servo-Spezialfall: Sie hebt alle vier Suiten.
    - twelve: auch `diff`, das bisher niemand lernte (0.05-0.18), erreicht 0.48 / 0.54. Abspaltungen 0.06 / 0.00
      je Lauf (Delta-Regel 2.4).
  - **Bedeutung fuer den Teacher:** Was der Teacher lernen muesste, ist zum grossen Teil die Konditionierung
    des Updates (Kovarianz der Eingaenge), nicht nur dessen Richtung. Offen: dieselbe Idee fuer innere
    Schichten (dfa versagt auf servo), und P ueber Saetze teilen (die Eingaenge sind in allen Aufgaben einer
    Suite dieselben).

- **Bruecke zum Roboter-Projekt, Stufe a, 2026-11-10** (tasks/robot.py, data/robot, results/robot.jsonl;
  Export im Roboter-Projekt: src/pc_cvnn/export_netresearch.py, dort wiki/fragen/netresearch-bruecke.md):
  - Fovea-Bilder (16x16 Hex-Zellen, Graustufen-RGB, Arm sichtbar) aus dem MuJoCo-Arm, je 12000 Trainings-
    und 3000 Test-Beispiele aus getrennten Szenen. Ausgabe wie servo: Schritt (dx, dy) in Zellen.
    - robot_gaze: Lage des roten Wuerfels relativ zur Bildmitte (Blickverschiebung).
    - robot_reach: Schritt vom Greifpunkt zum roten Wuerfel.
  - Erster Lauf, Seed 0, 6000 Updates (Test, exakt richtig):

  | Netz | robot_gaze | robot_reach |
  |---|---|---|
  | layer_s_c16 | 1.00 | 0.10 |
  | layer_s / layer_s_sp4 / cnn | 0.98 | 0.11 / 0.10 / 0.08 |
  | vit | 0.97 | 0.13 |
  | hier_s | 0.93 | 0.09 |
  | gru / mlp | 0.44 / 0.38 | 0.06 / 0.05 |

    - robot_gaze ist geloest. robot_reach nicht: innerhalb von +-1 Zelle liegen etwa 50 % (vit 57 %), der
      mittlere Fehler ist 1.1-1.5 Zellen. Der Greifpunkt ist im Bild kein markierter Punkt, sondern muss aus
      der Armform gelesen werden.
  - **Fehler in der Bewertung gefunden und behoben:** eval_set wandelte Bilder in uint8 und setzte damit alle
    Graustufen auf 0 (erste Anzeige: gaze 0.13). Jetzt nur noch bei binaeren Bildern. Die Tabelle stammt aus
    der Neubewertung der gespeicherten Netze.

  - **Warum robot_reach scheitert** (scripts/robot_reach_probe.py, results/robot_reach_probe.jsonl; gleiche
    Bilder, drei Fragen; cnn und layer_s, Seed 0, Test-Szenen, exakt richtig):

  | Frage | 12000 Beispiele | 48000 Beispiele | 48000, 24000 Updates |
  |---|---|---|---|
  | Zelle der Hand | 0.82-0.85 | 0.90 | |
  | Zelle des Wuerfels | 0.56-0.62 | 0.70 | |
  | Schritt Hand -> Wuerfel | 0.08-0.11 | 0.15 | 0.21-0.24 |

    - Die Hand wird gut gelesen (innerhalb +-1 Zelle 0.95), obwohl der Greifpunkt nicht markiert ist.
    - Der Wuerfel schlechter als in robot_gaze (0.98): der Arm steht ueber ihm.
    - Engpass ist das Verrechnen: Aus beiden Ablesungen waeren ~0.6 zu erwarten, erreicht werden 0.15-0.24,
      und der Trainingsfehler bleibt hoch (0.15-0.36). Mehr Daten und 4x Training helfen nur wenig.
    - Der groessere Datensatz (48000, anderer Zufallsstrom als data/robot) liegt nicht im Repository.
  - **Bibliothek auf Roboter-Bildern** (library.py Suite robot, Basis robot_gaze, Bilder aus
    data/robot/gazemulti_train.npz mit allen drei Wuerfeln im Blickfeld; Basis-Netze in
    data/base_nets/robot_gaze, 0.93-0.98). Sechs Aufgaben bei gleichen Bildern: Kalibrierungen des
    Blick-Kommandos (eye_flipx, eye_swap, eye_offx, eye_rot90) und ein anderes Ziel (green, blue).
    Zweiter Besuch, Seeds 0-2, Bibliothek / Orakel:

  | Regel | Kalibrierungen | anderes Ziel (gruen / blau) |
  |---|---|---|
  | delta_head | 0.88 / 0.93 | 0.00 / 0.01 |
  | rls_head | 0.91 / 0.95 | 0.01 / 0.01 |
  | rls_rf | 0.91 / 0.96 | 0.01 / 0.01 |

    - Kalibrierungen uebertragen sich auf echte Kamerabilder. Seeds 5 / 6 gleich (0.88-0.90 / 0.93-0.95).
    - **Ein anderes Ziel lernt keine Kopf-Regel**, auch nicht mit Orakel: Der Kopf-Eingang des Basis-Netzes
      traegt die Lage des roten Wuerfels, nicht die der anderen. Das ist die Grenze "nur am Kopf schreiben":
      Dafuer braucht es Aenderungen im Inneren oder einen Ziel-Eingang (Kommando), den das Netz von Anfang
      an mitlernt.
    - **Schwaeche der rls-Regeln gefunden** (Lauf layer_s, Seed 0): Der Satz, der an gruen gescheitert war,
      wurde fuer die naechste Aufgabe weiterbenutzt und war zu steif (eye_flipx 0.64, eye_swap 0.68 beim
      zweiten Besuch). Abhilfe ohne neue Konstante: Solange ein Satz nach je 30 Updates unter dem
      Kompetenz-Boden 0.1 liegt, wird seine Kovarianz zurueckgesetzt (0.91 / 0.94). An einem Test-Seed
      gefunden; die Seeds 1 / 2 und 5 / 6 zeigen dasselbe Niveau wie Seed 0.

- **Ziel-Eingang (Kommando-Port), 2026-11-10** (models/__init__.py attach_cmd, Modellnamen `<netz>+cmd`;
  tasks/robot.py robot_find; results/robot.jsonl, scripts/robot_find_eval.py -> results/robot_find_eval.jsonl):
  - **Anlass:** Ein anderes Ziel bei gleichem Bild lernt keine Kopf-Regel (gruen / blau 0.01). Das Ziel muss
    als Eingang ins Netz, nicht als neue Gewichte.
  - **Port:** Kommando-Vektor mit 16 Werten neben dem Bild; wirkt als gelerntes additives Muster auf das Bild
    (ein Wert je Farbkanal und Spalte, 816 Parameter), also ab der ersten Schicht und fuer jede Architektur
    gleich. Die Aufgabe malt nichts ins Bild. Ohne Kommando unveraendertes Verhalten.
  - **robot_find:** Bild mit allen drei Wuerfeln, Kommando = Farbe des gesuchten Wuerfels (RGB als stetige
    Adresse, keine Klassennummer), Ausgabe = Blickverschiebung zu diesem Wuerfel.
  - Ergebnis (Seeds 0-2, 6000 Updates, Test-Szenen):

  | Netz | gesamt | rot | gruen | blau | innerhalb +-1 (rot / gruen / blau) | falsches Kommando |
  |---|---|---|---|---|---|---|
  | cnn+cmd | 0.72 | 0.94 | 0.66 | 0.57 | 0.97 / 0.90 / 0.87 | 0.00 |
  | layer_s_sp4+cmd | 0.54 | 0.89 | 0.40 | 0.34 | 0.96 / 0.76 / 0.71 | 0.00 |
  | vit+cmd | 0.54 | 0.84 | 0.40 | 0.39 | 0.91 / 0.73 / 0.71 | 0.00 |
  | layer_s+cmd | 0.52 | 0.90 | 0.39 | 0.29 | 0.96 / 0.76 / 0.67 | 0.00 |
  | hier_s+cmd | 0.41 | 0.80 | 0.29 | 0.17 | 0.91 / 0.68 / 0.55 | 0.00 |
  | layer_s / cnn ohne Port | 0.04 / 0.05 | 0.08 / 0.06 | 0.03 / 0.05 | 0.03 / 0.04 | 0.18 / 0.15 | |

    - Der Port traegt: Alle Netze folgen dem Kommando (mit dem Kommando eines anderen Wuerfels wird der rote
      nie mehr getroffen). Ohne Port bleibt die Aufgabe ungeloest.
    - Rot ist leichter als gruen / blau. Das liegt sehr wahrscheinlich an den Daten, nicht an der Farbe: Der
      rote Wuerfel liegt im Export gleichverteilt ueber die Zellen, die anderen liegen, wo sie eben liegen,
      also oefter in der gestauchten Peripherie. Nicht getrennt geprueft.
    - cnn ist hier klar das beste Netz; die Gitter-Netze liegen bei 0.5.
  - **Die Adresse verallgemeinert nicht auf neue Objekte:** Mit der Farbe des L oder des U als Kommando (nie
    trainiert) trifft kein Netz (0.00-0.02 exakt, 0.01-0.10 innerhalb +-1). Mit nur drei Trainingsfarben ist
    das Kommando faktisch eine Klassennummer. Fuer eine stetige Adresse braucht das Training viele Farben
    (Farben je Szene wuerfeln); dann ist "neue Farbe" eine Interpolation.

  - **Stetige Adresse mit gewuerfelten Farben** (robot_findc; data/robot/gazecolor_*.npz, 24000 Trainings-
    szenen; scripts/robot_findc_eval.py -> results/robot_findc_eval.jsonl): Die drei Wuerfel tragen je Szene
    zufaellige Farben, der Farbton 0.25-0.40 (gruen) kommt im Training nie vor. Seeds 0-2, 6000 Updates,
    exakt richtig (in Klammern innerhalb +-1 Zelle):

  | Netz | Test, trainierte Farbtoene | zurueckgehaltener Farbton | Kontrolle (gleiche Szenen, trainierter Farbton) | falsches Kommando |
  |---|---|---|---|---|
  | cnn+cmd | 0.44 (0.75) | 0.31 (0.61) | 0.42 (0.73) | 0.01 |
  | vit+cmd | 0.40 (0.64) | 0.33 (0.61) | 0.38 (0.63) | 0.01 |
  | layer_s_sp4+cmd | 0.18 (0.52) | 0.16 (0.46) | 0.18 (0.52) | 0.02 |
  | layer_s+cmd | 0.14 (0.47) | 0.11 (0.41) | 0.13 (0.47) | 0.01 |

    - **Die Adresse verallgemeinert jetzt:** Ein nie gesehener Farbton wird mit 74-87 % der Trefferquote
      der Kontrolle gefunden (cnn 0.31 gegen 0.42, vit 0.33 gegen 0.38); mit drei festen Farben waren es
      0.00-0.02. Viele Farben im Training machen aus dem Kommando eine Adresse statt einer Klassennummer.
    - Die Aufgabe ist deutlich schwerer als mit drei festen Farben (cnn 0.72 -> 0.44) und nach 6000 Updates
      nicht ausgelernt.
    - **Die Gitter-Netze fallen hier ab** (0.14-0.18 gegen 0.40-0.44). Vermutung, ungeprueft: Der Port als
      additives Muster je Spalte passt schlecht zu Netzen, die das Bild in Spaltenstreifen zerlegen; der
      naheliegende Weg dort ist das Kommando als Eingang jeder Zelle (wie der globale Notizblock).

  - **Kommando als Eingang jeder Zelle** (Gitter-Netze `<netz>+cell`, models/grid.py cmd_cells; Seeds 0-2):
    Die Vermutung "der additive Port passt schlecht zu den Gittern" ist **widerlegt**. Bei 6000 Updates ist
    der Zell-Eingang nicht besser, eher etwas schlechter:

  | Netz | robot_findc `+cmd` | robot_findc `+cell` | robot_find `+cmd` | robot_find `+cell` |
  |---|---|---|---|---|
  | layer_s | 0.14 | 0.13 | 0.52 | 0.53 |
  | layer_s_sp4 | 0.18 | 0.12 | 0.54 | 0.52 |
  | hier_s | | 0.10 | 0.41 | 0.35 |

    (robot_find: Mittel ueber rot / gruen / blau aus scripts/robot_find_eval.py.)
  - **Die Gitter-Netze lernen die Aufgabe nur langsamer.** robot_findc mit 24000 Updates (4x), Seeds 0-2
    (results/robot_findc_eval_long.jsonl), exakt richtig (innerhalb +-1 Zelle):

  | Netz | Test | zurueckgehaltener Farbton | Kontrolle | falsches Kommando |
  |---|---|---|---|---|
  | vit+cmd | 0.64 (0.82) | 0.56 (0.79) | 0.63 (0.82) | 0.01 |
  | cnn+cmd | 0.62 (0.82) | 0.41 (0.64) | 0.61 (0.81) | 0.00 |
  | layer_s_sp4+cell | 0.45 (0.73) | 0.41 (0.70) | 0.43 (0.70) | 0.01 |

    - layer_s_sp4+cell steigt von 0.12 auf 0.45; cnn von 0.44 auf 0.62, vit von 0.40 auf 0.64. Dasselbe Bild
      wie bei servo (Gitter brauchten 4500 Updates, vit 2000): Auf Wahrnehmungs-Aufgaben lernen die Gitter
      2-4x langsamer. Ob `+cmd` bei langem Training besser waere als `+cell`, ist nicht gemessen.
    - Verallgemeinerung auf den nie gesehenen Farbton, relativ zur Kontrolle: layer_s_sp4+cell 95 %,
      vit 89 %, cnn 67 %. Das cnn lernt die trainierten Farben am besten und verallgemeinert am schlechtesten.
    - Die gespeicherten Netze von cnn+cmd, vit+cmd und layer_s_sp4+cell fuer robot_findc sind jetzt die
      24000-Update-Netze.

  - **Adresse aus einem Bild des Objekts** (Netze `<netz>+ref`, models/__init__.py AddressEncoder; Aufgabe
    robot_findi; data/robot/gazecolorref_*.npz, 12000 Trainingsszenen; results/robot_findi_eval.jsonl):
    - **Zeigebild:** je Wuerfel ein Bild, das ihn allein in einer ANDEREN Szene zeigt (Blick auf ihm, Arm in
      anderer Stellung). Suchszene und Zeigebild haben nur das Objekt gemeinsam.
    - **Adress-Encoder:** zwei Faltungen und eine lineare Schicht (etwa 4-6k Parameter), Zeigebild -> 16 Werte
      in [-1, 1], die in den Kommando-Port gehen. Gelernt nur ueber den Fehler der Suchaufgabe; niemand gibt
      vor, was in der Adresse stehen soll. Sie ist auslesbar (model.ref_enc(bild)) und ohne Bild wieder
      eingebbar.
    - Vergleich auf denselben Szenen: `+cmd` bekommt die Farbe als Kommando von aussen. Seeds 0-2, 24000
      Updates, exakt richtig (innerhalb +-1 Zelle):

  | Netz | Test | zurueckgehaltener Farbton | Kontrolle | falsches Bild / Kommando | Farbe aus der Adresse (R2) |
  |---|---|---|---|---|---|
  | vit+ref (Bild) | 0.59 (0.80) | 0.56 (0.79) | 0.58 (0.78) | 0.01 | 0.92 |
  | vit+cmd (Farbe) | 0.59 (0.79) | 0.51 (0.77) | 0.57 (0.77) | 0.01 | |
  | cnn+ref (Bild) | 0.53 (0.78) | 0.46 (0.71) | 0.50 (0.75) | 0.01 | 0.91 |
  | cnn+cmd (Farbe) | 0.48 (0.75) | 0.31 (0.56) | 0.45 (0.73) | 0.01 | |
  | layer_s_sp4+cell+ref (Bild) | 0.45 (0.72) | 0.39 (0.68) | 0.43 (0.71) | 0.01 | 0.94 |

    - **Die selbst gebildete Adresse ist so gut wie oder besser als die vorgegebene Farbe** (vit gleich, cnn
      0.53 gegen 0.48) und verallgemeinert besser auf den nie gesehenen Farbton: relativ zur Kontrolle
      vit 97 % (Farbe 89 %), cnn 92 % (Farbe 69 %), Gitter-Netz 91 %.
    - Mit dem Bild eines anderen Wuerfels wird der gefragte nicht mehr getroffen (0.01): Das Netz folgt dem
      gezeigten Objekt.
    - Die Adresse traegt die Farbe fast linear (R2 0.91-0.94), obwohl das nie verlangt war. Hier unterscheiden
      sich die Objekte nur in der Farbe; ob die Adresse auch FORM traegt, ist der naechste Test.
    - Nicht gemessen: ob zwei Zeigebilder desselben Wuerfels dieselbe Adresse geben (nur ein Zeigebild je
      Wuerfel und Szene im Export).

  - **Formen: die Adresse traegt die Form, aber die Suche nutzt sie nicht** (Aufgabe robot_finds;
    data/robot/gazeshape*.npz, nicht im Repository, per Export neu erzeugbar; scripts/robot_finds_eval.py ->
    results/robot_finds_eval.jsonl). Drei Koerper gleicher Farbe und verschiedener Form (Wuerfel, L, U, T,
    Kreuz; beliebig gedreht), zwei Zeigebilder je Koerper, das Y nie im Training. Seeds 0-2, 24000 Updates:

  | Netz | Suche exakt (+-1) | Y exakt (+-1) | falsches Bild | gleiche Adresse fuer zwei Bilder | ... beim Y | Form aus der Adresse |
  |---|---|---|---|---|---|---|
  | layer_s_sp4+cell+ref | 0.09 (0.28) | 0.05 (0.18) | 0.03 | 0.83 | 0.63 | 0.75 |
  | cnn+ref | 0.06 (0.22) | 0.05 (0.16) | 0.03 | 0.82 | 0.62 | 0.51 |
  | vit+ref | 0.05 (0.19) | 0.04 (0.16) | 0.03 | 0.74 | 0.57 | 0.49 |
  | cnn+cmd / vit+cmd (Form als Kennung) | 0.05 (0.19) | 0.02 / 0.01 | 0.02 / 0.03 | | | |

    ("gleiche Adresse": Ist die Adresse des ersten Zeigebilds der des zweiten Bilds DESSELBEN Koerpers am
    naechsten, unter den drei Koerpern der Szene? Zufall 0.33. "Form aus der Adresse": lineare Auslese, 5
    Formen, Zufall 0.2.)
    - **Die Suche scheitert, ehrliches Negativ:** 0.05-0.09 exakt. Auch mit der Form als fester Kennung
      von aussen (`+cmd`) nicht besser; es liegt also nicht an der Adresse.
    - **Die Adresse selbst traegt Form:** Zwei Bilder desselben Koerpers (andere Szene, andere Drehung) geben
      in 74-83 % die naechstliegende Adresse, beim nie gesehenen Y in 57-63 %. Die Form ist zu 49-75 %
      linear ablesbar. Das Gitter-Netz bildet hier die beste Adresse.
    - **Woran die Suche scheitert** (Zusatzauswertung, innerhalb +-1 Zelle): Die Netze landen in 42-48 % auf
      IRGENDEINEM der drei Koerper, aber nur in 19-28 % auf dem gefragten. Sie finden also Koerper, waehlen
      aber kaum nach der Form aus. Das haengt nicht am Abstand von der Bildmitte (Ziel in der Mitte 0.13-0.36,
      am Rand 0.21-0.30): Es ist nicht nur die gestauchte Peripherie.
    - **Folgerung:** "Ein Blick, gleichzeitig alle Kandidaten gegen die Adresse pruefen" ist fuer Formen zu
      viel. Naheliegend ist das, was eine Fovea ohnehin tut: Kandidaten nacheinander anschauen und das
      zentrierte Bild mit der Adresse vergleichen (derselbe Encoder liefert "was sehe ich gerade"). Das
      braucht mehrere Schritte und Gedaechtnis.

  - **Lernen die Gitter-Netze Wahrnehmung langsam? Nur teilweise** (Rechen-PC 2026-11-10, results/grid_slow.jsonl;
    Seeds 0-2, 24000 Updates, Lernkurve alle 250 Updates). Updates bis Score 0.9 (servo, robot_gaze) bzw. 0.4
    (robot_findc), Spanne ueber die Seeds; dahinter der Endwert:

  | Netz | servo | robot_gaze | robot_findc (+cmd) |
  |---|---|---|---|
  | vit | 1000-2750 (1.00) | 2000-3250 (0.99) | 400k: 5000-8750 (0.66) |
  | cnn | 3250-3500 (1.00) | 1500-1750 (0.99) | 400k: 2500-2750 (0.68) |
  | layer_s | 4000-6250 (1.00) | 1500-2500 (0.99) | 7750-8750 (0.56) |
  | layer_s_c4 (4 Spalten) | 2750-4000 (1.00) | 5750-9500 (0.94) | nie (0.34) |
  | layer_s_c16 (16 Spalten) | 9000-13000 (0.96) | 1000-1250 (1.00) | 6500-8750 (0.59; 400k 0.63) |
  | layer_s_r2 / r8 | 3500-5250 / 4000-6500 | 2000-2500 / 2250-2750 | 12250-14750 (0.44) / 7250-9750 (0.55) |
  | hier_s | 6500-8750 (1.00) | 4500-6750 (0.97) | 14250-16250 (0.43) |

    - **Kein allgemeines Wahrnehmungs-Defizit:** robot_gaze lernt layer_s so schnell wie cnn, mit 16 Spalten
      am schnellsten von allen. servo loesen am Ende alle (1.00).
    - **Die Spaltenzahl ist ein Tausch, kein Regler:** 16 Spalten sind auf Roboter-Bildern am schnellsten und
      auf servo am langsamsten (deshalb 0.41 nach 6000 Updates; mit 24000 0.96); 4 Spalten umgekehrt.
    - **robot_findc:** Der Rueckstand ist kleiner als gedacht. layer_s+cmd 0.56 und layer_s_c16+cmd 0.59
      gegen cnn 0.62 / vit 0.64 (100k). Der fruehere Wert 0.45 gehoerte zum Zell-Eingang (`+cell`), der damit
      klar schlechter ist als der einfache additive Eingang (0.45 gegen 0.56). 400k hilft layer_s nicht
      (0.56), dem cnn schon (0.68). layer_i (individuelle Module) scheitert (0.18).
    - Die Hierarchie (hier_s) ist ueberall die langsamste Gitter-Variante.

  - **Anschauen und vergleichen: mit Gedaechtnis geht die Form-Suche, ueber die Adresse nicht**
    (Aufgaben robot_look, robot_lookmem; Export mit `cands` = Blick auf jedem der drei Koerper;
    scripts/robot_look_eval.py -> results/robot_look*_eval.jsonl; Seeds 0-2).
    - **Stufe 2, robot_lookmem** (Schritt 0: Bild des gesuchten Koerpers als normales Bild; Schritte 1-3: Blick
      nacheinander auf den drei gleichfarbigen Koerpern; je Schritt "ist es der vom Anfang?"; kein
      Zusatz-Eingang). Zufall: Antworten 0.67 ("immer nein"), Wahl des Koerpers 0.33.

  | Netz | Updates | Antworten richtig | richtigen Koerper gewaehlt | ... beim nie gesehenen Y |
  |---|---|---|---|---|
  | attnmem | 6000 / 24000 | 0.82 / 0.92 | 0.60 / 0.82 | 0.38 / 0.56 |
  | gru | 6000 / 24000 | 0.82 / 0.85 | 0.57 / 0.68 | 0.36 / 0.46 |
  | layer_s, layer_s_sp4 | 6000 / 24000 | 0.67 / 0.67 | 0.00 / 0.00 | 0.00 |
  | hier_s, layer_s_am4, vit | 6000 | 0.67 | 0.00 | 0.00 |

      - **Die Form-Suche, die in einem Blick scheiterte (0.05-0.09), gelingt mit Nacheinander-Anschauen:**
        attnmem waehlt in 82 % den richtigen Koerper, beim nie trainierten Y in 56 %.
      - **Die Gitter-Netze scheitern vollstaendig,** auch mit Notizblock, Inhaltsadressierung und vierfacher
        Trainingszeit: Der Verlust verlaesst das Plateau "immer nein" nie. Das ist kein Tempo-Problem. Dieselben
        Netze loesen recall / delay / cycle_mem (Gespeichertes WIEDERGEBEN); hier muss Gespeichertes mit dem
        Gesehenen VERGLICHEN werden. Offen, ob es am Vergleichen liegt oder an den Roboter-Bildern ->
        synthetische Aufgaben `match` / `match_shift` (tasks/memory.py), Laeufe auf dem Rechen-PC.
      - vit ohne Gedaechtnis bleibt wie erwartet bei Zufall (Kontrolle).
    - **Stufe 1, robot_look** (ein Blick auf einen Koerper + Zeigebild ueber den Adress-Encoder `+ref` ->
      ja / nein): **negativ.** vit+ref, cnn+ref, layer_s_sp4+cell+ref bleiben bei 0.50 (12000 und 36000
      Updates), ebenso gru+ref und attnmem+ref (einzelne Seeds kommen kurz auf 0.6-0.65, nicht stabil).
      Die Adresse (16 Werte, additiv eingespeist) reicht zum AUSWAEHLEN nach Farbe, aber nicht zum
      VERGLEICHEN von Formen: Vergleich ist ein Produkt beider Seiten, kein Aufaddieren. Stufe 2 zeigt den
      Ausweg: beide Bilder durch DASSELBE Netz, der Vergleich im Gedaechtnis.
    - Lernkurven beider Stufen: langes Plateau beim Zufallswert, dann ploetzlicher Durchbruch (gru nach etwa
      3000 Updates) oder nie.

  - **Die Gitter-Netze koennen vergleichen, aber nur am selben Ort** (Rechen-PC 2026-11-10/11,
    results/match.jsonl; Aufgaben match / match_shift in tasks/memory.py; Seeds 0-2, 12000 Updates;
    Score 0 = "immer nein", 1 = alles richtig):

  | Netz | match (Wort immer am selben Ort) | match_shift (jedes Wort an anderer Stelle) |
  |---|---|---|
  | attnmem (25k / 100k / 400k) | 1.00 | 0.44 / 0.43 / 0.27 |
  | gru (25k / 100k / 400k) | 0.99 / 1.00 / 0.99 | 0.56 / 0.42 / 0.41 (ein 25k-Seed 0.83) |
  | layer_s, layer_s_sp4, layer_s_c16, hier_s, hier_s_sp4 (auch 25k / 400k) | 1.00 | 0.00 |
  | layer_s_am4 (100k / 400k) | 1.00 | 0.07 / 0.01 |
  | layer_i | 1.00 | 0.25 (Seeds 0.00 / 0.00 / 0.75) |
  | vit, cnn, mlp (ohne Gedaechtnis) | 0.00 | 0.00 |

    - **Vergleichen an sich ist kein Problem:** Alle Gitter-Netze loesen match in 250 Updates, schneller als
      das gru (500).
    - **Sobald das Wort wandert, bleibt jedes Gitter mit geteilten Modulen bei "immer nein",** unabhaengig von
      Groesse, Spaltenzahl und Art des Speichers. Das erklaert robot_lookmem: Zeigebild und Kandidat zeigen
      denselben Koerper anders gedreht, also an anderen Pixeln.
    - Deutung (nicht gemessen): Jede Spalte sieht nur ihren Bildstreifen und vergleicht mit dem, was SIE
      gespeichert hat. Es fehlt eine ortsunabhaengige Beschreibung VOR dem Speichern. gru und attnmem lesen
      das ganze Bild in einen Vektor.
    - Auch gru / attnmem loesen match_shift nur halb (0.42-0.44, sehr stabil ueber Seeds; vermutlich die
      Zufalls-Distraktoren, nicht die mit 1-2 gekippten Bits; nicht aufgeschluesselt). match_shift ist damit
      eine brauchbare offene Leiterstufe.

  - **match_shift zerlegt: es bricht beim VERGLEICHEN zweier ortsunabhaengiger Beschreibungen, bei allen
    Netzen** (lokal 2026-11-11, results/match_parts.jsonl, scripts/match_breakdown.py; Seeds 0-2, 6000 Updates).
    Seit dieser Messung hat jedes Wort eine blaue Linie darunter (Anfang und Ende); ohne sie war ein
    verschobenes Wort nicht eindeutig (00000110 = 00001100 einen Pixel weiter links). Die Worker-Zahlen oben
    sind von vor der Aenderung; match_shift lief hier neu mit.

  | Netz | read_shift (lesen) | same_fixed (vergleichen, fester Ort) | same_shift (vergleichen, ein Bild, wandernd) | keep_fixed | keep_shift (merken, wandernd) | match_shift |
  |---|---|---|---|---|---|---|
  | layer_s, _sp4, _am4, _c16 | 1.00 | 1.00 | 0.04-0.07 | 1.00 | 1.00 | 0.00 |
  | hier_s / layer_i | 1.00 | 1.00 | 0.35 / 0.35 (Seeds 0.04-0.70) | 1.00 | 1.00 | 0.00 |
  | gru | 0.98 | 1.00 | 0.55 (0.27-0.70) | 1.00 | 0.77 | 0.43 |
  | attnmem | 1.00 | 1.00 | 0.02 | 1.00 | 1.00 | 0.43 |
  | vit / cnn | 1.00 | 1.00 | 0.01 | 0.01 | 0.01 | 0.00 |

    - **Die Deutung "den Gittern fehlt eine ortsunabhaengige Beschreibung" war falsch:** Alle Gitter lesen ein
      wanderndes Wort (1.00) und merken es (1.00), besser als das gru (0.77).
    - **Gebrochen ist same_shift, und zwar OHNE Gedaechtnis und bei jeder Architektur,** auch vit und cnn.
      Jedes Netz kann beide Woerter lesen und kann vergleichen, wenn die Orte fest sind, lernt aber nicht,
      beides zu verbinden. Die Kurven zeigen wieder Plateau und spaeten Durchbruch einzelner Seeds: ein
      LERN-Problem (kein Gradient, solange keine der beiden Teilleistungen steht), kein Architektur-Loch.
    - match_shift, nach Kandidaten-Art: gru / attnmem erkennen den gleichen Kandidaten in 0.79-0.80, lehnen
      fast gleiche (1-2 Bits anders) in 0.77-0.78 ab und ferne in 0.91; richtiger Kandidat gewaehlt in
      0.67-0.68. Sie vergleichen also unscharf, nicht nur grob.
    - **same_shift mit 24000 Updates: das Plateau ist lang, nicht endgueltig, und die Gitter sind dann die
      Besten:** hier_s 0.96 (0.93-0.98), layer_s 0.89 (0.86-0.92), layer_i 0.89 (0.87-0.92), layer_s_am4 0.77
      (0.50-0.95), layer_s_sp4 0.61 (0.32-0.86), layer_s_c16 0.32, gru 0.71 (alle Seeds, Decke), attnmem 0.12,
      vit 0.13, cnn 0.00. Fuer vit / cnn / attnmem ist es also mehr als Lerntempo, fuer die Gitter nicht.
    - Folge: kein Umbau am Netz. Das ist ein Fall fuer Lehrplan / Teacher: Teilleistung (lesen) vorhanden,
      Zusammensetzen wird allein nicht gefunden.

  - **Lehrplan: die Vorstufe "merken + vergleichen" oeffnet match_shift und robot_lookmem fuer die Gitter**
    (lokal 2026-11-11, scripts/curriculum.py -> results/curriculum.jsonl; Plan = Phasen "aufgabe[+aufgabe]:updates",
    jede Phase mit eigenem Optimierer; Abstimm-Seeds 5 / 6, wo nicht anders vermerkt).
    - **Uebertrag auf match_shift** (Endwerte je Seed):

  | Plan | layer_s | hier_s | gru |
  |---|---|---|---|
  | match_shift:12000 | 0.00 / 0.00 | 0.00 / 0.00 | 0.43 / 0.44 |
  | same_shift:12000 -> match_shift:12000 | 0.90 / 0.00 | 0.89 / 0.87 | 0.95 / 0.94 |
  | keep_shift+same_shift:12000 -> match_shift:12000 | 1.00 / 1.00 | 1.00 / 1.00 | 0.99 / 0.99 |
  | same_shift+match_shift:24000 (zugleich) | 0.00 / 0.00 | 0.00 / 0.00 | 0.91 / 0.92 |

      Nach der Vorstufe faellt match_shift in 750-1500 Updates. Zugleich lernen hilft den Gittern nicht, nur
      nacheinander. Die Vorstufe wird dabei vergessen (same_shift danach wieder bei Zufall).
    - **Uebertrag auf die Roboter-Aufgabe robot_lookmem** (Score; 0 = "immer nein"; Anteil richtiger Antworten
      = 2/3 + Score/3; ohne Vorstufe 0.00 bei 6000 und 24000 Updates; attnmem ohne Vorstufe, 24000 Updates,
      Seeds 0-2: Score 0.76):

  | Plan | layer_s | hier_s |
  |---|---|---|
  | keep_shift+same_shift:12000 -> robot_lookmem:12000 | 0.68 / 0.56 | 0.77 / 0.80 |
  | ... -> match_shift:4000 -> robot_lookmem:12000 | 0.00 / 0.69 | 0.04 / 0.80 |

      Die synthetische Vorstufe (Woerter aus Pixeln) oeffnet also die Aufgabe auf MuJoCo-Bildern: hier_s
      erreicht das Niveau des Attention-Speichers. Die Zwischenstufe match_shift schadet eher (je ein Seed
      faellt aus). Noch nicht auf den Seeds 0-2 bestaetigt, nicht auf dem Y ausgewertet.
    - **Lehrplan fuer same_shift selbst** (12000 Updates insgesamt): Bei den Gittern gibt
      read_shift+same_fixed:2000 -> same_shift:10000 die besten Endwerte. Seeds 0-2: layer_s 0.92 / 0.95 / 0.60
      gegen allein 0.41 / 0.08 / 0.03; hier_s 0.92 / 0.83 / 0.87 gegen 0.88 / 0.74 / 0.84. Das Plateau wird kaum
      kuerzer (Score 0.5 nach 4500-6750 statt 6250-7500 Updates, Seeds 5 / 6), aber verlaesslicher verlassen.
      vit: read_shift+same_shift zugleich 0.84-0.86 statt Zufall. gru: 0.71 in jeder Variante.
    - Offen: Bestaetigung des match_shift-Uebertrags auf Seeds 0-2 fuer sechs Netze (Lauf vom System wegen
      Speichermangel beendet, nichts fertig).

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
