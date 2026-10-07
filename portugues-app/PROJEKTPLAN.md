# Projektplan: Português-App

## Deine Entscheidungen (aus den Rückfragen)
- **Ablage:** Ordner `portugues-app/` in diesem Repo. Du lädst ihn als ZIP über GitHub herunter, die bestehende App bleibt unberührt.
- **Anrede:** Zuerst formell (*o senhor/a senhora*, Verb ohne Pronomen), *tu* ab Einheit A1-2. Danach werden beide Formen durchgehend geübt.
- **Einstieg:** Start bei A1-1. Jeder Einheitentest kann vorgezogen werden; wer ihn mit mindestens 80 % besteht, überspringt die Einheit.
- **Audio:** edge-tts (neuronale pt-PT-Stimmen Raquel/Duarte) mit lokalem Speicher. Ohne Internet übernimmt die macOS-Stimme „Joana" im Browser.

## Architektur (bewusst einfach)

```
portugues-app/
├── Start.command          Doppelklick: installiert beim ersten Mal, startet danach nur die App
├── Stop.command           beendet die App sauber
├── LIES-MICH.md           Anleitung (max. 10 Zeilen)
├── curriculum.md          Lehrplan
├── einstellungen.beispiel.env  optional: Claude-API-Key und Modell
├── pyproject.toml         Python-Abhängigkeiten (uv)
├── backend/               Python + FastAPI
│   ├── main.py            Webserver, API-Routen
│   ├── db.py              SQLite-Datenmodell
│   ├── srs.py             Wiederholungs-Algorithmus (SM-2, angepasst)
│   ├── lesson.py          Zusammenstellung der Tageslektion
│   ├── content.py         Lädt Lektionen aus den JSON-Dateien
│   ├── tts.py             Audio über edge-tts mit Cache
│   └── ai.py              optional: Claude für Gespräche und Korrektur
├── content/               Lektionen als JSON, frei erweiterbar
│   ├── A1/A1-01.json …    eine Datei pro Einheit
│   └── A2/ … (später)
├── frontend/              HTML, CSS und JS ohne Build-Schritt, Alpine.js als lokale Datei
├── data/                  wird erzeugt: lernstand.sqlite, audio-cache/, backups/
└── tests/                 pytest: SRS, Lektionsablauf, Inhaltsprüfung
```

**Start.command:** Prüft zuerst die Internetverbindung, aber nur, wenn Downloads nötig sind. Danach installiert es `uv` lokal ohne Admin-Rechte, `uv sync` legt Python und alle Pakete im Projektordner an (`.venv`). Dann startet der Server, `open -a "Google Chrome"` öffnet die App, und es setzt sich selbst `chmod +x` und entfernt die Quarantäne. Ein Port-Konflikt wird erkannt; läuft die App schon, wird nur Chrome geöffnet. Beim Schließen des Terminalfensters fährt der Server über einen Trap sauber herunter.

**Datenmodell (SQLite):**
- `cards`: Karteikarten-Zustand (Fälligkeit, Intervall, Leichtigkeit, Fehlerzahl)
- `reviews`: jede Antwort mit Zeitpunkt, Ergebnis und Übungstyp; daraus entstehen die Statistiken
- `mistakes`: falsche Antworten mit deiner Eingabe und der richtigen Lösung; sie kommen automatisch zurück
- `lessons_done` und `block_state`: Fortschritt und übersprungene Blöcke pro Lektion
- `tests`: Ergebnisse der Einheiten- und Level-Tests je Fertigkeit
- `daily_log`: Lernzeit pro Tag (für Streak und Kalender)
- `settings`

Backup und Export als JSON auf Knopfdruck. Vor jedem Update entsteht automatisch eine Sicherung.

**SRS:** SM-2 in einer angepassten Form, einfach nachvollziehbar und gut testbar. Es hat Lernstufen für neue Karten (1 Min. → 10 Min. → 1 Tag) und eine Fehlerbehandlung, die das Intervall bei einem Fehler nicht ganz auf null setzt. Pro Tag gibt es ein festes Limit neuer Karten (Standard 10). Dazu kommt eine **Lastbremse**: Wenn mehr als ~60 Wiederholungen fällig sind, kommen automatisch weniger neue Karten dazu. Bewertet wird automatisch aus der Antwort: richtig, beinahe richtig (z. B. nur ein fehlender Akzent) oder falsch.

**Inhaltsformat (JSON pro Einheit):** Metadaten, Wortschatz (PT, DE, Emoji, Beispielsatz, Genus), Lektionen mit Grammatikerklärung, Übungen (Lücke, Übersetzen, Satzbau, Multiple Choice), Hörtext mit Fragen, Sprech- und Schreibaufgaben sowie der Einheitentest. Ein Prüfskript meldet Formatfehler, damit neue Inhalte für A2–B2 sicher ergänzt werden können.

**Spracherkennung:** Chrome Web Speech API (`pt-PT`). Wichtig: Chrome schickt das Audio dafür an Google, du brauchst also Internet. Fallback: „Selbst bewerten" (Aufnahme anhören und vergleichen).

**Claude (optional):** In `einstellungen.env` schaltest du ihn mit `CLAUDE_AKTIV=ja`, `ANTHROPIC_API_KEY=…` und `CLAUDE_MODELL=…` ein. Ohne Key verschwinden die entsprechenden Knöpfe einfach.

## Etappen

| Etappe | Ergebnis | So probierst du es aus |
|---|---|---|
| a | Grundgerüst, Start/Stop.command, Datenmodell, leere Startseite | Doppelklick auf Start.command, Chrome öffnet die Startseite |
| b | Lektionsablauf mit 6 Blöcken, Timer, Überspringen, SRS | erste Lektion A1-1 komplett durchspielen |
| c | Audio (edge-tts und Cache), Sprechübungen | Leertaste spielt Audio, Mikrofon-Übungen |
| d | Seiten Fortschritt, Wortschatz, Einstellungen, Backup | Statistiken, Wörterbuch, JSON-Export |
| e | Vollständiger A1-Inhalt (12 Einheiten, ≈ 600 Wörter) und A1-Level-Test | 98 Lektionen spielbar |
| f | Tests (SRS, Lektionsablauf, Inhalte) und Erststart-Test | Testbericht in `TESTBERICHT.md` |

Nach jeder Etappe schiebe ich den Stand nach GitHub und erkläre dir kurz, wie du ihn ausprobierst.

## Ehrliche Einschränkungen
- **Erststart-Test:** Ich arbeite in einer Linux-Cloud-Umgebung, nicht auf einem Mac. Den Erststart ohne Python teste ich unter Linux in einer frischen, leeren Umgebung (gleiche Logik mit uv). Die macOS-spezifischen Teile (Doppelklick, Gatekeeper, `open -a`, `xattr`) kann ich nur per Code-Prüfung absichern. Im Testbericht steht genau, was geprüft wurde und was du beim ersten Start beobachten solltest.
- **edge-tts** nutzt eine inoffizielle Microsoft-Schnittstelle. Sollte sie eines Tages nicht mehr funktionieren, übernimmt automatisch die Mac-Stimme. Falls „Joana" fehlt, erkläre ich in LIES-MICH.md, wie du sie in den Systemeinstellungen lädst.
- **Inhaltsqualität:** Ich schreibe alle Sätze sorgfältig in europäischem Portugiesisch und prüfe sie automatisch auf typisch brasilianische Formen (z. B. *ônibus, trem, você* als Standard, Proklise im Hauptsatz). Bei rund 600 Wörtern und Hunderten von Sätzen empfehle ich trotzdem, dass eine portugiesische Muttersprachlerin oder ein Muttersprachler einmal querliest. Fehler kannst du direkt in den JSON-Dateien korrigieren.
- **B1/B2-Last:** Dort reichen 5 Minuten Wiederholung nicht für alle fälligen Karten. Die Lastbremse und der passive Wortschatz (siehe curriculum.md) fangen das ab. An manchen Tagen werden es trotzdem 35 statt 30 Minuten.
