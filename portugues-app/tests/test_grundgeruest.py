"""Tests für Etappe (a): Datenbank, Einstellungen, Sicherung und API."""

from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from backend import db


@pytest.fixture
def con(tmp_path):
    c = db.connect(tmp_path / "test.sqlite")
    db.init_db(c)
    yield c
    c.close()


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("PORTUGUES_DB", str(tmp_path / "api.sqlite"))
    from backend.main import app
    with TestClient(app) as c:
        yield c


# --- Datenbank -------------------------------------------------------------

def test_init_ist_mehrfach_ausfuehrbar(con):
    db.init_db(con)
    db.init_db(con)
    assert db.get_settings(con)["neue_karten_pro_tag"] == 15


def test_einstellungen_speichern_nur_bekannte_schluessel(con):
    s = db.save_settings(con, {"neue_karten_pro_tag": 15, "gibt_es_nicht": 1})
    assert s["neue_karten_pro_tag"] == 15
    assert "gibt_es_nicht" not in s


def test_streak_zaehlt_bis_gestern_wenn_heute_noch_nichts(con):
    heute = date(2026, 10, 7)
    for tage_zurueck in (1, 2, 3):
        db.add_study_time(con, seconds=600, day=(heute - timedelta(days=tage_zurueck)).isoformat())
    assert db.streak(con, today=heute) == 3
    db.add_study_time(con, seconds=60, day=heute.isoformat())
    assert db.streak(con, today=heute) == 4


def test_streak_reisst_bei_luecke(con):
    heute = date(2026, 10, 7)
    db.add_study_time(con, seconds=600, day=heute.isoformat())
    db.add_study_time(con, seconds=600, day=(heute - timedelta(days=2)).isoformat())
    assert db.streak(con, today=heute) == 1


def test_lernzeit_wird_aufsummiert(con):
    db.add_study_time(con, seconds=100, day="2026-10-07")
    db.add_study_time(con, seconds=50, lessons=1, day="2026-10-07")
    row = con.execute("SELECT * FROM daily_log WHERE day='2026-10-07'").fetchone()
    assert (row["seconds"], row["lessons"]) == (150, 1)


def test_faellige_karten_zaehlen_nur_gelernte(con):
    jetzt = "2026-10-07T12:00:00"
    con.executemany(
        "INSERT INTO cards(item_id, kind, state, due, created_at) VALUES (?, 'vocab', ?, ?, ?)",
        [("a", "review", "2026-10-06T08:00:00", jetzt),   # fällig
         ("b", "review", "2026-10-09T08:00:00", jetzt),   # noch nicht fällig
         ("c", "new", None, jetzt)])                      # neu – zählt nicht
    assert db.due_count(con, now=jetzt) == 1


def test_export_und_import(con, tmp_path):
    db.save_settings(con, {"neue_karten_pro_tag": 7})
    db.add_study_time(con, seconds=300, day="2026-10-01")
    export = db.export_json(con)

    neu = db.connect(tmp_path / "neu.sqlite")
    db.init_db(neu)
    db.import_json(neu, export)
    assert db.get_settings(neu)["neue_karten_pro_tag"] == 7
    assert neu.execute("SELECT seconds FROM daily_log").fetchone()["seconds"] == 300


def test_import_lehnt_fremde_dateien_ab(con):
    with pytest.raises(ValueError):
        db.import_json(con, {"irgendwas": 1})


def test_tagessicherung(tmp_path):
    c = db.connect(tmp_path / "x.sqlite")
    db.init_db(c)
    c.close()
    ziel = db.daily_backup(tmp_path / "x.sqlite", tmp_path / "backups")
    assert ziel.exists()
    # zweiter Aufruf am selben Tag erzeugt keine weitere Datei
    db.daily_backup(tmp_path / "x.sqlite", tmp_path / "backups")
    assert len(list((tmp_path / "backups").iterdir())) == 1


# --- API -------------------------------------------------------------------

def test_health(client):
    assert client.get("/api/health").json() == {"app": "portugues-app", "ok": True}


def test_overview(client):
    data = client.get("/api/overview").json()
    assert data["streak"] == 0
    assert data["faellig"] == 0
    assert data["fortschritt"]["level"] == "A1"
    assert data["fortschritt"]["gesamt"] == 98


def test_settings_api(client):
    assert client.put("/api/settings", json={"audio_tempo": 0.8}).json()["audio_tempo"] == 0.8
    assert client.get("/api/settings").json()["audio_tempo"] == 0.8


def test_startseite_wird_ausgeliefert(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "big-button" in r.text and "lektion()" in r.text
    assert client.get("/vendor/alpine.min.js").status_code == 200


def test_viele_gleichzeitige_anfragen(client):
    # Regressionstest: Verbindungen wurden in einem anderen Thread geschlossen,
    # als sie geöffnet wurden → Fehler bei parallelen Anfragen.
    from concurrent.futures import ThreadPoolExecutor
    pfade = ["/api/overview", "/api/settings"] * 25
    with ThreadPoolExecutor(max_workers=8) as pool:
        codes = list(pool.map(lambda p: client.get(p).status_code, pfade))
    assert codes == [200] * len(pfade)


def test_export_api_liefert_datei(client):
    r = client.get("/api/export")
    assert "attachment" in r.headers["content-disposition"]
    assert r.json()["app"] == "portugues-app"


def test_alte_datenbank_wird_ergaenzt(tmp_path):
    # Datenbank im Format von Etappe (a): ohne die später ergänzten Spalten
    c = db.connect(tmp_path / "alt.sqlite")
    c.executescript("""
        CREATE TABLE reviews (id INTEGER PRIMARY KEY, card_id INTEGER, ts TEXT NOT NULL,
            exercise TEXT NOT NULL, result TEXT NOT NULL, answer TEXT, duration_ms INTEGER);
        CREATE TABLE mistakes (id INTEGER PRIMARY KEY, item_id TEXT, category TEXT, prompt TEXT NOT NULL,
            given TEXT, expected TEXT NOT NULL, explanation TEXT, ts TEXT NOT NULL,
            times_wrong INTEGER NOT NULL DEFAULT 1, resolved INTEGER NOT NULL DEFAULT 0);
        INSERT INTO reviews(ts, exercise, result) VALUES ('2026-10-01T10:00:00', 'tippen', 'richtig');
    """)
    db.init_db(c)
    spalten = {r[1] for r in c.execute("PRAGMA table_info(reviews)")}
    assert {"item_id", "lesson_id", "block"} <= spalten
    assert {"streak", "payload"} <= {r[1] for r in c.execute("PRAGMA table_info(mistakes)")}
    assert c.execute("SELECT COUNT(*) FROM reviews").fetchone()[0] == 1   # nichts verloren
