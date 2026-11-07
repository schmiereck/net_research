# Rechen-PC als Worker

Der zweite PC holt sich Aufträge selbst ab. Er braucht nur ausgehenden Zugriff auf GitHub (das Repo
ist öffentlich, also ohne Zugangsdaten) und denselben OneDrive-Ordner. Von außen muss nichts erreichbar sein.

```
Haupt-PC                         OneDrive-Ordner                     Rechen-PC
jobs submit  ──────────────────► jobs/queue/<id>.json ─────────────► worker (git checkout <commit>,
git push     ──► GitHub ───────────────────────────────────────────►         bench ...)
jobs status / fetch ◄────────── results/<id>/runs.jsonl, bench.log ◄─ alle 60 s gespiegelt
                                 workers/<host>.json (Herzschlag)
```

## Einrichten (einmalig, auf dem Rechen-PC)

Voraussetzung: Python 3.12 und git.

```powershell
cd C:\Users\<user>\Projekte
git clone https://github.com/schmiereck/net_research.git NetResearchWorker
cd NetResearchWorker
python -m venv .venv
.venv\Scripts\python -m pip install torch --index-url https://download.pytorch.org/whl/cpu
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python -m pytest -q tests          # sollte durchlaufen
```

Diesen Klon nur für den Worker benutzen. Er wird auf den Commit des jeweiligen Auftrags umgeschaltet;
lokale Änderungen am Code verhindern das (der Auftrag schlägt dann mit einer Meldung fehl).

## Starten

```powershell
cd C:\Users\<user>\Projekte\NetResearchWorker
.venv\Scripts\python -m netresearch.worker --share "C:\Users\<user>\OneDrive\Dokumente\#Projekte\NetResearch" --workers 14
```

* `--share`: der OneDrive-Ordner auf diesem PC (der Pfad kann sich vom Haupt-PC unterscheiden).
* `--workers`: parallele Läufe. 16 Kerne / 32 GB: 14 für Einzel-Aufgaben; für Multi-Task-Aufträge setzt der
  Auftrag selbst eine kleinere Zahl (~1 GB pro Prozess).
* Das Fenster offen lassen. Der Worker wartet, wenn die Warteschlange leer ist, und prüft jede Minute neu.
* Stoppen: Strg+C (der laufende Auftrag geht zurück in die Warteschlange und wird später fortgesetzt),
  oder im OneDrive-Ordner eine Datei `workers/STOP` anlegen (stoppt nach dem laufenden Auftrag; danach
  löschen).
* Den PC nicht in den Ruhezustand gehen lassen, solange Aufträge laufen.

Optional: automatisch bei der Anmeldung starten (Aufgabenplanung → Aufgabe erstellen → Trigger
„Bei Anmeldung“, Aktion: die `python.exe` aus `.venv\Scripts` mit den Argumenten oben, „Starten in“ = Klon).

## Benutzen (auf dem Haupt-PC)

```powershell
git push                                                          # der Worker holt den Code von GitHub
python -m netresearch.jobs submit seeds12 -- --models all --tasks all --seeds 1 2
python -m netresearch.jobs submit multi_s1 --workers 3 -- --multitask --models layer_s hier_s --seeds 1
python -m netresearch.jobs status
python -m netresearch.jobs fetch <id> --into results/runs.jsonl [--checkpoints]
```

Ergebnisse, Log und Checkpoints eines Auftrags liegen im OneDrive-Ordner unter `results/<id>/`.
