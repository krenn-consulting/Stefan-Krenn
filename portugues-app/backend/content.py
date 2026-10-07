"""Lädt die Lektionsinhalte aus content/<Level>/<Einheit>.json.

Die Inhalte sind nicht im Code, sondern in JSON-Dateien – so lassen sich
A2–B2 später einfach als weitere Dateien ergänzen.
"""

import json
from functools import lru_cache
from pathlib import Path

CONTENT_DIR = Path(__file__).resolve().parent.parent / "content"

LEVELS = ["A1", "A2", "B1", "B2"]

# Geplante Lektionszahl pro Level laut curriculum.md. Wird verwendet,
# solange ein Level noch nicht (vollständig) als Inhalt vorliegt.
PLANNED_LESSONS = {"A1": 98, "A2": 122, "B1": 170, "B2": 198}


@lru_cache(maxsize=1)
def load_units(content_dir: Path = CONTENT_DIR) -> list[dict]:
    """Alle Einheiten, sortiert nach Level und Dateiname."""
    units = []
    for level in LEVELS:
        for path in sorted((content_dir / level).glob("*.json")):
            unit = json.loads(path.read_text(encoding="utf-8"))
            unit.setdefault("level", level)
            units.append(unit)
    return units


def lessons_in_level(level: str) -> list[str]:
    """IDs aller Lektionen eines Levels in Lernreihenfolge."""
    ids = []
    for unit in load_units():
        if unit["level"] == level:
            ids.extend(lesson["id"] for lesson in unit.get("lessons", []))
    return ids


def level_progress(done_ids: set[str]) -> dict:
    """Aktuelles Level und Fortschritt (0..1) zum nächsten Level."""
    for level in LEVELS:
        planned = max(len(lessons_in_level(level)), PLANNED_LESSONS[level])
        done = len([i for i in done_ids if i.startswith(level + "-")])
        if done < planned:
            return {"level": level, "erledigt": done, "gesamt": planned,
                    "anteil": round(done / planned, 3)}
    return {"level": "B2", "erledigt": PLANNED_LESSONS["B2"],
            "gesamt": PLANNED_LESSONS["B2"], "anteil": 1.0}
