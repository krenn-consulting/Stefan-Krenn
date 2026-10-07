# Testbericht

Wird nach jeder Etappe ergänzt.

## Etappe (a) – Grundgerüst und Start.command (7. Oktober 2026)

### Automatische Tests
`uv run pytest`: **15 von 15 bestanden.** Abgedeckt sind Datenbank, Einstellungen, Streak, fällige Karten, Sicherung, Export und Import, die API sowie parallele Anfragen.

### Erststart-Test „frisch eingerichteter Rechner“
**Testumgebung:** Linux-Container. Die App war eine frische Kopie mit nur den Dateien aus dem Repo (wie im ZIP). Die Umgebung war leer (`env -i`), mit leerem Benutzerordner und **ohne uv, Python-Werkzeuge oder Node.js im Suchpfad**.

| Szenario | Ergebnis |
|---|---|
| Erststart mit Internet | ✅ uv geladen, Python 3.12 und Pakete nach `.werkzeuge/` und `.venv/` installiert, App nach **12–16 s** erreichbar. Auf einem Mac mit normalem WLAN rechne mit 1–3 Minuten. |
| Hauptadresse astral.sh nicht erreichbar | ✅ Ausweich-Download über GitHub greift. Dieser Test hat einen Fehler aufgedeckt, der behoben ist. |
| Benutzerordner und System | ✅ unverändert: keine Änderung an PATH oder Shell-Profil, nichts außerhalb des App-Ordners |
| Zweiter Start (schon eingerichtet) | ✅ App nach ~3 s bereit |
| Start, während die App schon läuft | ✅ „Die App läuft bereits“, öffnet nur den Browser |
| Fenster schließen (SIGHUP) | ✅ Server sauber beendet, PID-Datei entfernt |
| Stop.command | ✅ Server beendet, Meldung auf Deutsch |
| Neustart ohne Internet | ✅ App startet mit vorhandener Umgebung |
| Erststart ohne Internet | ✅ verständliche Meldung („WLAN prüfen …“), kein halber Zustand |
| Wöchentliche Update-Prüfung | ✅ `uv lock --upgrade` und Sync laufen, die vorherige Version wird gesichert (bei Problemen automatische Rückkehr) |
| Ansicht hell, dunkel und Einstellungen (Chromium) | ✅ |

**Python:** Das Skript erzwingt ein von uv verwaltetes Python (`UV_PYTHON_PREFERENCE=only-managed`). So wird auf einem frischen Mac nie das Apple-Platzhalter-Python aufgerufen, das sonst den Installationsdialog der Xcode-Tools auslösen würde.

### Nicht in der Cloud testbar (nur per Code-Prüfung abgesichert)
Diese Teile laufen nur auf einem echten Mac:

- **Doppelklick im Finder und die Gatekeeper-Warnung:** siehe LIES-MICH.md, Punkt 4
- **`open -a "Google Chrome"`** und der Hinweis, wenn Chrome fehlt (`open -Ra`)
- **`xattr -dr com.apple.quarantine`:** löst die Quarantäne für alle Dateien nach dem ersten erlaubten Start
- **uv für Apple Silicon und Intel:** Der Installer erkennt die Architektur automatisch.
- **Bash 3.2 (macOS):** Das Skript nutzt bewusst keine Funktionen neuerer Bash-Versionen.

**Bitte beim ersten echten Start beobachten:** Kommt die Gatekeeper-Warnung, und öffnet sich Chrome danach automatisch? Falls etwas hakt, schick mir den Inhalt von `data/app.log`.
