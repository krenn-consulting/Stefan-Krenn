# Inhalte bearbeiten und ergänzen

Jede Einheit ist eine JSON-Datei, z. B. `A1/A1-01.json`. Neue Einheiten einfach als weitere Datei anlegen (`A1/A1-02.json`, `A2/A2-01.json` …); die Reihenfolge ergibt sich aus dem Dateinamen. Nach Änderungen die App neu starten.

**Aufbau einer Einheit**
- `id`, `level`, `titel`, `beschreibung`
- `vokabeln`: Liste mit `id`, `pt`, `de`, `emoji`, `beispiel_pt`, `beispiel_de`, optional `hinweis` und `alternativen` (weitere akzeptierte Antworten)
- Ab B1: Vokabeln mit `"passiv": true` werden nur gezeigt (zum Verstehen), nicht abgefragt und nicht wiederholt.
- `lektionen`: Liste mit `id` (z. B. `A1-01-L01`), `titel`, `vokabeln` (IDs aus der Liste oben), `grammatik`, `hoeren`, `sprechen`, `saetze`

**Übungstypen** (`grammatik.uebungen`)
| typ | Felder |
|---|---|
| `auswahl` | `frage`, `optionen`, `richtig` (Index ab 0), optional `audio` |
| `luecke` | `satz` mit `___`, `loesungen`, `de` |
| `uebersetzen` | `de`, `loesungen` |
| `satzbau` | `de`, `loesung` |
| `diktat` | `pt` |

Ab B1 kann `grammatik.erklaerung` auf Portugiesisch stehen; `grammatik.erklaerung_de` (Liste) erscheint dann als aufklappbare deutsche Erklärung.

Lektionstypen (`typ`): `neu` (Standard), `wiederholung`, `test` (Einheitentest), `leveltest` (mit optionalem `bloecke`, z. B. `["hoeren", "lesen", "grammatik"]`). Für Tests braucht die Einheit einen Abschnitt `test` mit `hoeren`, `lesen` (je ein Objekt oder eine Liste), `schreiben` und `sprechen`.

Alle Übungen können `erklaerung` (wird bei Fehlern gezeigt) und `kategorie` (für die Fehleranalyse, z. B. „ser/estar“) haben.

**Sprechen & Schreiben** (`sprechen.typ`): `nachsprechen` (`saetze`), `schreiben` (`aufgaben` mit `de` + `loesungen`), `rollenspiel` (`zeilen`: Sätze des Gegenübers mit `sprecher`, `stimme` f/m, `pt`, `de` – und eigene Züge mit `"ich": true`, `aufgabe`, `loesungen`).

**Prüfen:** Im Terminal im App-Ordner `.werkzeuge/bin/uv run python -m backend.inhalt_check` ausführen (optional mit Dateinamen, um nur eine Einheit zu prüfen). Das findet Formfehler und typisch brasilianische Formen (z. B. *ônibus*, *Me chamo*, *estou fazendo*).
