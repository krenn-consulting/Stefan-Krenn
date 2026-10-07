"""Datenbank: der gesamte Lernstand liegt in einer SQLite-Datei in data/.

Bewusst ohne ORM gehalten – reines SQL ist hier am leichtesten zu lesen.
"""

import json
import shutil
import sqlite3
from datetime import date, datetime
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = APP_DIR / "data"
DB_PATH = DATA_DIR / "lernstand.sqlite"
BACKUP_DIR = DATA_DIR / "backups"
BACKUPS_BEHALTEN = 14  # so viele automatische Tagessicherungen werden aufbewahrt

SCHEMA_VERSION = 2

SCHEMA = """
-- Eine Karteikarte pro lernbarem Element (Wort, Chunk, Satzmuster, Fehler).
-- item_id verweist auf den Inhalt in content/, z. B. "A1-01:v:bom-dia".
CREATE TABLE IF NOT EXISTS cards (
    id            INTEGER PRIMARY KEY,
    item_id       TEXT NOT NULL UNIQUE,
    kind          TEXT NOT NULL,                 -- vocab | sentence | mistake
    unit_id       TEXT,                          -- z. B. "A1-01"
    state         TEXT NOT NULL DEFAULT 'new',   -- new | learning | review | erledigt
    step          INTEGER NOT NULL DEFAULT 0,    -- Lernstufe für neue Karten
    ease          REAL NOT NULL DEFAULT 2.5,     -- Leichtigkeitsfaktor (SM-2)
    interval_days REAL NOT NULL DEFAULT 0,
    due           TEXT,                          -- ISO-Zeitpunkt der nächsten Fälligkeit
    reps          INTEGER NOT NULL DEFAULT 0,
    lapses        INTEGER NOT NULL DEFAULT 0,    -- wie oft vergessen
    created_at    TEXT NOT NULL,
    last_review   TEXT
);
CREATE INDEX IF NOT EXISTS idx_cards_due ON cards(state, due);

-- Jede einzelne Antwort – Grundlage für Statistik und Genauigkeit.
CREATE TABLE IF NOT EXISTS reviews (
    id          INTEGER PRIMARY KEY,
    card_id     INTEGER REFERENCES cards(id),
    item_id     TEXT,                            -- welches Wort / welche Übung
    lesson_id   TEXT,                            -- in welcher Lektion beantwortet
    block       TEXT,                            -- in welchem Block (für Statistik je Fertigkeit)
    ts          TEXT NOT NULL,
    exercise    TEXT NOT NULL,                   -- tippen | diktat | luecke | auswahl | sprechen …
    result      TEXT NOT NULL,                   -- richtig | fast | falsch
    answer      TEXT,
    duration_ms INTEGER
);
CREATE INDEX IF NOT EXISTS idx_reviews_ts ON reviews(ts);

-- Fehlerspeicher: falsche Antworten kommen gezielt wieder.
CREATE TABLE IF NOT EXISTS mistakes (
    id           INTEGER PRIMARY KEY,
    item_id      TEXT,
    category     TEXT,                           -- z. B. "Genus", "ser/estar", "Akzent"
    prompt       TEXT NOT NULL,
    given        TEXT,
    expected     TEXT NOT NULL,
    explanation  TEXT,
    ts           TEXT NOT NULL,
    times_wrong  INTEGER NOT NULL DEFAULT 1,
    streak       INTEGER NOT NULL DEFAULT 0,     -- seitdem so oft hintereinander richtig
    resolved     INTEGER NOT NULL DEFAULT 0,     -- 1 = zweimal hintereinander richtig
    payload      TEXT                            -- die Übung als JSON, um sie zu wiederholen
);

-- Abgeschlossene Lektionen.
CREATE TABLE IF NOT EXISTS lessons_done (
    lesson_id   TEXT PRIMARY KEY,                -- z. B. "A1-01-L03"
    finished_at TEXT NOT NULL,
    score       REAL,                            -- 0..1
    self_rating INTEGER                          -- Selbsteinschätzung 1..5
);

-- Zustand der sechs Blöcke einer Lektion (fertig / übersprungen).
CREATE TABLE IF NOT EXISTS block_state (
    lesson_id  TEXT NOT NULL,
    block      TEXT NOT NULL,                    -- wiederholung | wortschatz | grammatik | hoeren | sprechen | abschluss
    status     TEXT NOT NULL,                    -- fertig | uebersprungen
    updated_at TEXT NOT NULL,
    PRIMARY KEY (lesson_id, block)
);

-- Einheiten- und Level-Tests, Ergebnis je Fertigkeit.
CREATE TABLE IF NOT EXISTS tests (
    id      INTEGER PRIMARY KEY,
    test_id TEXT NOT NULL,                       -- z. B. "A1-01-T" oder "A1-T"
    ts      TEXT NOT NULL,
    skill   TEXT NOT NULL,                       -- hoeren | lesen | schreiben | sprechen | gesamt
    score   REAL NOT NULL,
    passed  INTEGER NOT NULL
);

-- Lernzeit pro Tag (für Streak, Kalender, Statistik).
CREATE TABLE IF NOT EXISTS daily_log (
    day            TEXT PRIMARY KEY,             -- YYYY-MM-DD
    seconds        INTEGER NOT NULL DEFAULT 0,
    lessons        INTEGER NOT NULL DEFAULT 0,
    cards_reviewed INTEGER NOT NULL DEFAULT 0
);

-- Laufender Testversuch: ab wann zählen die Antworten?
CREATE TABLE IF NOT EXISTS test_versuche (
    lesson_id TEXT PRIMARY KEY,
    start     TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL                          -- als JSON gespeichert
);

CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""

# Standard-Einstellungen. Werden beim ersten Start angelegt und sind in der
# App unter "Einstellungen" änderbar.
DEFAULT_SETTINGS = {
    "lektionsdauer_min": 30,
    "neue_karten_pro_tag": 15,
    "max_wiederholungen_pro_tag": 120,
    "audio_tempo": 1.0,
    "stimme": "pt-PT-RaquelNeural",
    "design": "auto",  # auto | hell | dunkel
}

TABLES = ["cards", "reviews", "mistakes", "lessons_done", "block_state",
          "tests", "daily_log", "settings"]


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def connect(path: Path | None = None) -> sqlite3.Connection:
    """Öffnet die Datenbank. Zeilen lassen sich wie Dictionaries lesen."""
    path = path or DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    # check_same_thread=False: FastAPI öffnet und schließt eine Verbindung
    # manchmal in verschiedenen Threads. Unbedenklich, weil jede Anfrage
    # ihre eigene Verbindung hat und sie nie gleichzeitig benutzt wird.
    con = sqlite3.connect(path, check_same_thread=False, timeout=10)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    return con


# Spalten, die nach der ersten Version dazugekommen sind. Ältere Datenbanken
# werden beim Start automatisch ergänzt – der Lernstand bleibt erhalten.
MIGRATIONEN = [
    ("reviews", "item_id", "TEXT"),
    ("reviews", "lesson_id", "TEXT"),
    ("reviews", "block", "TEXT"),
    ("mistakes", "streak", "INTEGER NOT NULL DEFAULT 0"),
    ("mistakes", "payload", "TEXT"),
]


def _migrieren(con: sqlite3.Connection) -> None:
    for tabelle, spalte, typ in MIGRATIONEN:
        vorhanden = {r[1] for r in con.execute(f"PRAGMA table_info({tabelle})")}
        if vorhanden and spalte not in vorhanden:
            con.execute(f"ALTER TABLE {tabelle} ADD COLUMN {spalte} {typ}")


def init_db(con: sqlite3.Connection) -> None:
    """Legt Tabellen und Standard-Einstellungen an. Mehrfach aufrufbar."""
    con.executescript(SCHEMA)
    _migrieren(con)
    con.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_mistakes_item ON mistakes(item_id)")
    con.execute("UPDATE meta SET value = ? WHERE key = 'schema_version'", (str(SCHEMA_VERSION),))
    for key, value in DEFAULT_SETTINGS.items():
        con.execute("INSERT OR IGNORE INTO settings(key, value) VALUES (?, ?)",
                    (key, json.dumps(value)))
    con.execute("INSERT OR IGNORE INTO meta(key, value) VALUES ('schema_version', ?)",
                (str(SCHEMA_VERSION),))
    con.commit()


# --- Einstellungen ---------------------------------------------------------

def get_settings(con: sqlite3.Connection) -> dict:
    settings = dict(DEFAULT_SETTINGS)
    for row in con.execute("SELECT key, value FROM settings"):
        settings[row["key"]] = json.loads(row["value"])
    return settings


def save_settings(con: sqlite3.Connection, changes: dict) -> dict:
    """Speichert nur bekannte Einstellungen; Unbekanntes wird ignoriert."""
    for key, value in changes.items():
        if key in DEFAULT_SETTINGS:
            con.execute("INSERT OR REPLACE INTO settings(key, value) VALUES (?, ?)",
                        (key, json.dumps(value)))
    con.commit()
    return get_settings(con)


# --- Übersicht für die Startseite -----------------------------------------

def streak(con: sqlite3.Connection, today: date | None = None) -> int:
    """Anzahl aufeinanderfolgender Lerntage bis heute.

    Ist heute noch nicht gelernt worden, zählt die Serie bis gestern –
    sie ist erst gerissen, wenn auch heute nichts passiert.
    """
    today = today or date.today()
    days = {row["day"] for row in
            con.execute("SELECT day FROM daily_log WHERE seconds > 0 OR lessons > 0")}
    count = 0
    current = today if today.isoformat() in days else date.fromordinal(today.toordinal() - 1)
    while current.isoformat() in days:
        count += 1
        current = date.fromordinal(current.toordinal() - 1)
    return count


def due_count(con: sqlite3.Connection, now: str | None = None) -> int:
    """Wie viele bereits gelernte Karten sind jetzt fällig?"""
    now = now or now_iso()
    row = con.execute(
        "SELECT COUNT(*) AS n FROM cards WHERE state IN ('learning', 'review') AND due <= ?",
        (now,)
    ).fetchone()
    return row["n"]


def add_study_time(con: sqlite3.Connection, seconds: int = 0, lessons: int = 0,
                   cards: int = 0, day: str | None = None) -> None:
    day = day or date.today().isoformat()
    con.execute(
        """INSERT INTO daily_log(day, seconds, lessons, cards_reviewed) VALUES (?, ?, ?, ?)
           ON CONFLICT(day) DO UPDATE SET seconds = seconds + excluded.seconds,
               lessons = lessons + excluded.lessons,
               cards_reviewed = cards_reviewed + excluded.cards_reviewed""",
        (day, seconds, lessons, cards))
    con.commit()


# --- Sicherung und Export --------------------------------------------------

def daily_backup(db_path: Path | None = None, backup_dir: Path | None = None) -> Path | None:
    """Legt einmal pro Tag eine Kopie der Datenbank an und löscht alte Kopien."""
    db_path = db_path or DB_PATH
    backup_dir = backup_dir or BACKUP_DIR
    if not db_path.exists():
        return None
    backup_dir.mkdir(parents=True, exist_ok=True)
    target = backup_dir / f"lernstand-{date.today().isoformat()}.sqlite"
    if not target.exists():
        # Die SQLite-Backup-Funktion kopiert auch bei offener Datenbank konsistent.
        src = sqlite3.connect(db_path)
        dst = sqlite3.connect(target)
        with dst:
            src.backup(dst)
        src.close()
        dst.close()
    for old in sorted(backup_dir.glob("lernstand-*.sqlite"))[:-BACKUPS_BEHALTEN]:
        old.unlink()
    return target


def export_json(con: sqlite3.Connection) -> dict:
    """Kompletter Lernstand als JSON-taugliches Dictionary."""
    data = {"app": "portugues-app", "schema_version": SCHEMA_VERSION,
            "exportiert_am": now_iso(), "tabellen": {}}
    for table in TABLES:
        rows = con.execute(f"SELECT * FROM {table}").fetchall()
        data["tabellen"][table] = [dict(r) for r in rows]
    return data


def import_json(con: sqlite3.Connection, data: dict) -> None:
    """Stellt einen Export wieder her. Vorher wird der jetzige Stand gesichert."""
    if data.get("app") != "portugues-app" or "tabellen" not in data:
        raise ValueError("Das ist keine Sicherungsdatei dieser App.")
    con.commit()
    with con:  # alles oder nichts
        for table in TABLES:
            con.execute(f"DELETE FROM {table}")
            for row in data["tabellen"].get(table, []):
                cols = ", ".join(row.keys())
                marks = ", ".join("?" for _ in row)
                con.execute(f"INSERT INTO {table} ({cols}) VALUES ({marks})", list(row.values()))
    init_db(con)  # fehlende Einstellungen ergänzen


def copy_db_before_import(db_path: Path | None = None) -> Path | None:
    db_path = db_path or DB_PATH
    if not db_path.exists():
        return None
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    target = BACKUP_DIR / f"vor-import-{datetime.now():%Y-%m-%d-%H%M%S}.sqlite"
    shutil.copy2(db_path, target)
    return target
