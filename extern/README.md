# Externe Dokumente

Reviews, Einschätzungen und Ideen von außen (andere KI-Agenten wie Gemini / agy oder Codex, auch Menschen).
Sie werden hier abgelegt und nicht verändert, damit später nachvollziehbar ist, worauf sich ein Schritt bezieht.

* Dateiname: `ART-JJJJ-MM-TT.md` oder `ART-quelle-JJJJ-MM-TT.md`, z. B. `REVIEW-2026-11-19.md`,
  `IDEAS-agy-2026-11-14.md`. ART ist z. B. REVIEW, IDEAS, ASSESMENT.
* Inhalt ist Material, kein Auftrag: Was davon übernommen wird, entscheidet der Nutzer. Übernommene Punkte
  stehen mit Verweis auf die Datei in `AGENDA.md`; geprüfte Befunde und Korrekturen im `LOGBUCH.md`.
* Ältere Logbuch-Einträge nennen nur den Dateinamen (die Dateien lagen bis 2026-11-19 im Hauptverzeichnis).

| Datei | Quelle | Inhalt | Was daraus wurde |
|---|---|---|---|
| `REVIEW-2026-11-13.md` | agy | Review von Code und Methode | `ControlLearner`-Fehler (LOGBUCH 2026-11-13), Vorlauf `--burn`, `hier_sz`, Populations-Code |
| `IDEAS-agy-2026-11-14.md` | agy | Ideen zu schnellem Lernen und Anpassen | Populations-Code für Schritte; Rest nur zur Info (AGENDA P3) |
| `REVIEW-2026-11-19.md` | Gemini | Review der Blickschleife und der Live-Brücke | Korrektur Zustands-Auslese attnmem/vitmem, `+rv`, Regel „Bild verlassen“ im Live-Test (LOGBUCH 2026-11-19) |
| `ASSESMENT-2026-11-19.md` | Gemini | Einordnung gegenüber JEPA und VLA-Modellen | in AGENDA: kleines Weltmodell mit latenter Vorhersage; kurze Stellwert-Folgen und zwei Taktraten für die Servo-Stufe; vortrainierter Encoder geparkt (erst bei echter Kamera) |
