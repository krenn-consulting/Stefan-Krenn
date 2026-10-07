"""Optionale Einstellungen aus der Datei einstellungen.env (siehe einstellungen.beispiel.env)."""

import os
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent.parent


def load_env(path: Path | None = None) -> None:
    """Liest einfache KEY=WERT-Zeilen. Bereits gesetzte Umgebungsvariablen gewinnen."""
    path = path or APP_DIR / "einstellungen.env"
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def claude_enabled() -> bool:
    return (os.environ.get("CLAUDE_AKTIV", "nein").lower() in ("ja", "true", "1")
            and bool(os.environ.get("ANTHROPIC_API_KEY")))


def claude_model() -> str:
    return os.environ.get("CLAUDE_MODELL", "claude-opus-5-5")
