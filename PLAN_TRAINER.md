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

**Phase B – Port-Interface und feste Regeln (T1, T2 ohne gelernten Teacher)**
- Telemetrie- und Modulations-Ports (4c) in layer_s einbauen; W_slow + W_fast.
- T2: Low-Rank-Update u vᵀ; T1: Eligibility-Trace mit fehlergesteuertem Skalar (Feedback Alignment).
- Erster Fall: „einen neuen Zyklus merken“. Vergleich mit Adam-Feintuning.
- Die Frage dabei: Bringt eine schnelle Gewichtsschicht allein schon k-shot-Fähigkeit? Das ist die
  Untergrenze für den Teacher.

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
