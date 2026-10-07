# Inhalte bearbeiten und ergänzen

Jede Einheit ist eine JSON-Datei, z. B. `A1/A1-01.json`. Neue Einheiten einfach als weitere Datei anlegen (`A1/A1-02.json`, `A2/A2-01.json` …); die Reihenfolge ergibt sich aus dem Dateinamen. Nach Änderungen die App neu starten.

**Aufbau einer Einheit**
- `id`, `level`, `titel`, `beschreibung`
- `vokabeln`: Liste mit `id`, `pt`, `de`, `emoji`, `beispiel_pt`, `beispiel_de`, optional `hinweis` und `alternativen` (weitere akzeptierte Antworten)
- `lektionen`: Liste mit `id` (z. B. `A1-01-L01`), `titel`, `vokabeln` (IDs aus der Liste oben), `grammatik`, `hoeren`, `sprechen`, `saetze`

**Übungstypen** (`grammatik.uebungen`)
| typ | Felder |
|---|---|
| `auswahl` | `frage`, `optionen`, `richtig` (Index ab 0), optional `audio` |
| `luecke` | `satz` mit `___`, `loesungen`, `de` |
| `uebersetzen` | `de`, `loesungen` |
| `satzbau` | `de`, `loesung` |
| `diktat` | `pt` |

Alle Übungen können `erklaerung` (wird bei Fehlern gezeigt) und `kategorie` (für die Fehleranalyse, z. B. „ser/estar“) haben.

**Sprechen & Schreiben** (`sprechen.typ`): `nachsprechen` (`saetze`), `schreiben` (`aufgaben` mit `de` + `loesungen`), `rollenspiel` (`zeilen`: Sätze des Gegenübers mit `sprecher`, `stimme` f/m, `pt`, `de` – und eigene Züge mit `"ich": true`, `aufgabe`, `loesungen`).

**Prüfen:** Im Terminal im App-Ordner `.werkzeuge/bin/uv run python -m backend.inhalt_check` ausführen. Das findet Formfehler und typisch brasilianische Formen (z. B. *ônibus*, *Me chamo*, *estou fazendo*).
