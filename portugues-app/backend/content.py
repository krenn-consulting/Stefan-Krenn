"""Lädt die Lektionsinhalte aus content/<Level>/<Einheit>.json.

Die Inhalte sind nicht im Code, sondern in JSON-Dateien – so lassen sich
A2–B2 später einfach als weitere Dateien ergänzen. Nach Änderungen an den
Dateien die App neu starten.

Jedes lernbare Element hat eine eindeutige ID:
  Vokabel:  "A1-01:v:bom-dia"
  Satz:     "A1-01:s:muito-obrigado"
  Übung:    "A1-01-L01:g:3"   (Grammatik-Übung Nr. 3 der Lektion)
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
def load_units() -> list[dict]:
    """Alle Einheiten, sortiert nach Level und Dateiname."""
    units = []
    for level in LEVELS:
        for path in sorted((CONTENT_DIR / level).glob("*.json")):
            unit = json.loads(path.read_text(encoding="utf-8"))
            unit.setdefault("level", level)
            units.append(unit)
    return units


@lru_cache(maxsize=1)
def _index() -> dict:
    """Nachschlagetabellen für schnellen Zugriff."""
    items, lessons, order = {}, {}, []
    for unit in load_units():
        for v in unit.get("vokabeln", []):
            items[f"{unit['id']}:v:{v['id']}"] = {**v, "art": "vocab", "unit_id": unit["id"]}
        for lesson in unit.get("lektionen", []):
            lessons[lesson["id"]] = {**lesson, "unit_id": unit["id"], "unit_titel": unit["titel"],
                                     "level": unit["level"]}
            order.append(lesson["id"])
            for s in lesson.get("saetze", []):
                items[f"{unit['id']}:s:{s['id']}"] = {**s, "art": "sentence", "unit_id": unit["id"]}
    return {"items": items, "lessons": lessons, "order": order}


def unit(unit_id: str) -> dict | None:
    return next((u for u in load_units() if u["id"] == unit_id), None)


def units_in_level(level: str) -> list[dict]:
    return [u for u in load_units() if u["level"] == level]


def reload() -> None:
    """Cache leeren (z. B. in Tests oder nach Änderungen an den Inhalten)."""
    load_units.cache_clear()
    _index.cache_clear()


def item(item_id: str) -> dict | None:
    return _index()["items"].get(item_id)


def lesson(lesson_id: str) -> dict | None:
    return _index()["lessons"].get(lesson_id)


def lesson_order() -> list[str]:
    """Alle Lektions-IDs in Lernreihenfolge."""
    return list(_index()["order"])


def vocab_item_id(unit_id: str, vocab_id: str) -> str:
    return f"{unit_id}:v:{vocab_id}"


def sentence_item_id(unit_id: str, sentence_id: str) -> str:
    return f"{unit_id}:s:{sentence_id}"


def lessons_in_level(level: str) -> list[str]:
    return [lid for lid in lesson_order() if lesson(lid)["level"] == level]


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
