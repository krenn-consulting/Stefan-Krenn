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

## Etappe (b) – Lektionsablauf und Wiederholungssystem (7. Oktober 2026)

### Automatische Tests
`uv run pytest`: **67 von 67 bestanden.** Dazu gehört auch ein Test, dass eine Datenbank aus Etappe (a) automatisch ergänzt wird, ohne dass Lernstand verloren geht.

| Bereich | Was geprüft wird |
|---|---|
| Wiederholungssystem (`test_srs.py`, 16 Tests) | Lernstufen, wachsende Abstände, „fast richtig“, Vergessen halbiert den Abstand statt ihn zu löschen, Grenzen für Leichtigkeit und Abstand, Fälligkeit ab Tagesbeginn, Tageslimit und Lastbremse |
| Antwortprüfung (`test_pruefen.py`, 12 Tests) | Groß-/Kleinschreibung und Satzzeichen, Alternativen, fehlende Akzente und Tippfehler als „fast richtig“, keine Toleranz bei kurzen Wörtern (sou ≠ são) |
| Lektionsablauf (`test_lektion.py`, 20 Tests) | 6 Blöcke mit Zeitanteilen, Vorstellen vor Abrufen, Fehler kommen als Karte wieder und gelten nach zweimal richtig als behoben, Überspringen wird gemerkt, Abschluss und nächste Lektion, eingestreute alte Übungen, Wiederholungstag, kompletter Ablauf über die API |
| Inhalte (`test_inhalte.py`, 4 Tests) | Format aller Inhaltsdateien, Erkennung brasilianischer Formen |

### Im Browser (Chromium, automatisch durchgeklickt)
- **Lektionen 1–3:** vollständig durchgespielt, mit absichtlich falschen Antworten, ohne einen einzigen Browserfehler. Die zweite und dritte Lektion enthielten fällige Karten, neue Satzmuster und eingestreute Übungen aus früheren Lektionen.
- **Überspringen, Verlassen und Fortsetzen:** Die App setzt beim richtigen Block fort, übersprungene Blöcke lassen sich im Abschluss nachholen.
- **Wiederholungstag:** funktioniert.
- **Dunkelmodus:** funktioniert.

### Gefunden und behoben
- Die Einstellung Hell/Dunkel hatte keine Wirkung (Fehler aus Etappe a).
- Satzmuster wären an Lerntagen nie eingeführt worden, weil die Lektionsvokabeln das Tageslimit schon ausschöpften. Jetzt kommen mindestens 3 Satzmuster pro Tag dazu, und das Standardlimit liegt bei 15.
- Die Inhaltsprüfung erkannte „Estou fazendo“ am Satzanfang nicht.

### Noch nicht geprüft
- **Sprachausgabe:** Sie nutzt in dieser Etappe die Mac-Stimme über Chrome. Im Test-Browser gibt es keine Stimmen, deshalb wurde nur geprüft, dass nichts abstürzt. Etappe (c) bringt die hochwertigen Stimmen.

## Etappe (c) – Stimmen und Sprechübungen (7. Oktober 2026)

- **Automatische Tests** (`test_audio.py`, 13 Tests):
  - Stimmenwahl und Cache-Dateinamen
  - Ein zweiter Abruf kommt aus dem Cache, ohne Internet.
  - Fällt der Dienst aus, gibt die App eine verständliche Fehlermeldung (503) statt abzustürzen.
  - Gesprochene Antworten: Zahlen wie „12“ zählen wie „doze“; nur eine exakte Antwort gilt als „richtig“ (z. B. *Bom tarde* ≠ *Boa tarde*).
- **Im Browser:**
  - Mikrofon-Übungen mit simulierter Spracherkennung, je eine richtige und eine falsche Antwort.
  - Ohne Mikrofon erscheint „Selbst bewerten“.
  - Taste M startet das Zuhören.
- **Nicht testbar in der Cloud:** Der Microsoft-Sprachdienst (edge-tts) ist hier gesperrt. Geprüft wurde deshalb nur der Rückfall: Nach 23 ms übernimmt die Mac-Stimme. **Auf dem Mac bitte prüfen:** Klingt die Stimme europäisch-portugiesisch (Raquel/Duarte)? Ohne Internet spricht die Mac-Stimme „Joana“, falls sie installiert ist (Systemeinstellungen → Bedienungshilfen → Gesprochene Inhalte).

## Etappe (d) – Fortschritt, Wortschatz, Einstellungen, Claude (7. Oktober 2026)

- **Automatische Tests** (`test_fortschritt.py`, 10 Tests):
  - Statistiken, Lernkalender, Genauigkeit je Bereich, Schwächenliste
  - Wörterbuch mit Suche und Filter
  - Ein fehlender oder ungültiger Claude-Key führt zu einer deutschen Meldung statt eines Fehlers.
- **Im Browser:**
  - Mit einer simulierten Datenbank (3 Wochen Lernen) die Seiten Fortschritt, Wortschatz und Einstellungen geprüft, hell und dunkel.
  - Export und Import funktionieren.
  - Ein ungültiger API-Key wurde live getestet: verständliche Meldung, die App läuft weiter.

## Etappe (e) – Vollständiger A1-Inhalt (7. Oktober 2026)

- **Inhalt:**
  - 12 Einheiten plus Abschlusstest, zusammen **98 Lektionen**: je Einheit 6 neue Lektionen, eine Wiederholung und ein Einheitentest.
  - 709 Wörter und Wendungen, 217 Satzmuster, 511 Grammatikübungen, dazu Hördialoge, Lesetexte und Rollenspiele.
- **Inhaltsprüfung** (`python -m backend.inhalt_check`):
  - Alle Dateien sind fehlerfrei.
  - Geprüft werden das Format sowie brasilianische Formen (*ônibus*, *Me chamo*, Gerundium …).
  - Kein Wort ist doppelt in zwei Einheiten.
- **Automatische Tests** (`test_pruefungen.py`, 6 Tests, sowie `test_lektion.py`):
  - Die Wiederholungslektion nimmt nur Wörter der Einheit.
  - Ein nicht bestandener Test bleibt die nächste Lektion; beim nächsten Versuch zählen die alten Antworten nicht mehr.
  - Ein vorgezogener, bestandener Test überspringt die Einheit, und ihre Wörter kommen in 3 Tagen zur Wiederholung.
  - Ein übersprungener Testbereich zählt 0 %.
  - Der Level-Test hat zwei Teile mit Wörtern aus allen Einheiten.
  - **Ganz A1 wird einmal komplett durchlaufen**, alle 98 Lektionen in der richtigen Reihenfolge.
- **Im Browser:**
  - Vorgezogener Einheitentest A1-01: bestanden mit 86,5 %, 7 Lektionen übersprungen.
  - Level-Test Teil 1 mit absichtlichen Fehlern: 78 %, nicht bestanden, mit verständlicher Auswertung je Bereich.
  - Danach Teil 1 und Teil 2 bestanden; die Startseite zeigt „Alle vorhandenen Lektionen sind erledigt“ und Level A2.
- **Gefunden und behoben:**
  - Die Inhaltsprüfung meldete das Bindewort *Se* („wenn“, z. B. *Se precisar …*) fälschlich als brasilianisch.
  - Einige Wörter kamen in zwei Einheiten vor (Monate, *casado* …) und hätten doppelte Karten erzeugt.
- **Bitte beachten:** Die Texte sind sorgfältig in europäischem Portugiesisch geschrieben, aber nicht von einem Muttersprachler geprüft. Wenn dir etwas komisch vorkommt, frag gern deine Nachbarn. Korrekturen sind in den JSON-Dateien leicht möglich (siehe `content/INHALTE.md`).

## Etappe (f) – Abschlussprüfung (7. Oktober 2026)

- **Automatische Tests:** `uv run pytest`, **98 von 98 bestanden**, in etwa 10 Sekunden.
- **Erststart-Test wiederholt:** Wie in Etappe (a) mit einer frischen Kopie des Repos in einer leeren Umgebung ohne Python und uv.
  - App nach **14 s** bereit, mit dem vollständigen A1-Inhalt inklusive Level-Test.
  - Stop.command beendet sie sauber.
  - Der Benutzerordner blieb leer.
