"""Tests für Fortschritt/Wortschatz (statistik.py) und die optionale Claude-Anbindung (ai.py)."""

import json
import random
import types
from datetime import date, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from backend import ai, db, lesson, statistik

TAG = datetime(2026, 10, 7, 9, 0)


@pytest.fixture
def con(tmp_path):
    c = db.connect(tmp_path / "s.sqlite")
    db.init_db(c)
    yield c
    c.close()


def lernen(con, now, ergebnis="richtig"):
    p = lesson.plan(con, now=now, rng=random.Random(1))
    for b in p["bloecke"][:-1]:
        for s in b["schritte"]:
            if s.get("ref"):
                lesson.antwort_verbuchen(con, {"lesson_id": p["id"], "block": b["id"], "ergebnis": ergebnis,
                                               "antwort": "x", "schritt": s}, now=now)
    db.add_study_time(con, seconds=1800, day=now.date().isoformat())
    lesson.lektion_abschliessen(con, p["id"], 4, now=now)


def test_leere_statistik(con):
    s = statistik.fortschritt(con, heute=TAG.date())
    assert s["wortschatz"]["woerter"] == 0
    assert s["genauigkeit"]["gesamt"] is None
    assert len(s["lernzeit"]["tage"]) == 30
    assert len(s["kalender"]) >= 7 * 15
    assert date.fromisoformat(s["kalender"][0]["tag"]).weekday() == 0   # Kalender beginnt montags


def test_statistik_nach_lernen(con):
    lernen(con, TAG - timedelta(days=1))
    lernen(con, TAG, "falsch")
    s = statistik.fortschritt(con, heute=TAG.date())
    assert s["wortschatz"]["woerter"] > 0
    assert 0 < s["genauigkeit"]["gesamt"] < 1
    assert {b["id"] for b in s["genauigkeit"]["je_block"]} >= {"wortschatz", "grammatik"}
    assert s["lernzeit"]["tage"][-1]["minuten"] >= 30
    assert s["serie"]["aktuell"] == 2 and s["serie"]["laengste"] == 2
    assert s["schwaechen"]["fehler"]            # falsche Antworten tauchen als Schwäche auf
    assert all(k["kategorie"] != "Sonstiges" for k in s["schwaechen"]["kategorien"])


def test_wortschatz_suche_ohne_akzente(con):
    lernen(con, TAG)
    alle = statistik.wortschatz(con)
    assert len(alle) == 11                  # die Wörter der ersten Lektion; neue Satzkarten noch nicht
    treffer = statistik.wortschatz(con, "ate")   # findet "até logo", "até amanhã"
    assert {t["pt"] for t in treffer} >= {"até logo", "até amanhã"}
    assert statistik.wortschatz(con, "Wiedersehen")[0]["pt"] == "adeus"   # auch deutsch
    assert statistik.wortschatz(con, art="saetze") == []   # Sätze erst, wenn sie eingeführt sind


def test_laengste_serie():
    assert statistik._laengste_serie(["2026-10-01", "2026-10-02", "2026-10-04", "2026-10-05", "2026-10-06"]) == 3
    assert statistik._laengste_serie([]) == 0


def test_statistik_api(tmp_path, monkeypatch):
    monkeypatch.setenv("PORTUGUES_DB", str(tmp_path / "api.sqlite"))
    from backend.main import app
    with TestClient(app) as c:
        assert c.get("/api/statistik").status_code == 200
        assert c.get("/api/wortschatz", params={"q": "x"}).json() == []


# --- Claude (Attrappe statt echter API) -----------------------------------------

class FalscheAntwort:
    def __init__(self, daten, stop="end_turn"):
        self.stop_reason = stop
        self.content = [types.SimpleNamespace(type="text", text=json.dumps(daten))]


class FalscherClient:
    letzte = {}
    antwort = None

    def __init__(self, **kw):
        def erstellen(**argumente):
            FalscherClient.letzte = argumente
            return FalscherClient.antwort
        self.messages = types.SimpleNamespace(create=erstellen)
        self.beta = types.SimpleNamespace(messages=types.SimpleNamespace(create=erstellen))


@pytest.fixture
def claude(monkeypatch):
    import anthropic
    monkeypatch.setattr(anthropic, "Anthropic", FalscherClient)
    monkeypatch.setenv("CLAUDE_AKTIV", "ja")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    monkeypatch.setenv("CLAUDE_MODELL", "claude-opus-5-5")
    return FalscherClient


def test_gespraech(claude):
    claude.antwort = FalscheAntwort({"antwort_pt": "Bom dia! O que deseja?", "uebersetzung_de": "Guten Morgen! Was wünschen Sie?", "korrektur": ""})
    r = ai.gespraech([], "cafe", "A1")
    assert r["antwort_pt"].startswith("Bom dia")
    a = claude.letzte
    assert a["model"] == "claude-opus-5-5"
    assert a["fallbacks"] == "default"                        # Fallback bei Ablehnung aktiv
    assert a["messages"][0]["role"] == "user"                  # Claude beginnt trotzdem korrekt
    assert "europäisches Portugiesisch" in a["system"] and "Café" in a["system"]
    assert a["output_config"]["format"]["type"] == "json_schema"


def test_gespraech_verlauf_und_rollen(claude):
    claude.antwort = FalscheAntwort({"antwort_pt": "Muito bem.", "uebersetzung_de": "Sehr gut.", "korrektur": "„Estou bem“ statt „Sou bem“"})
    verlauf = [{"rolle": "claude", "text": "Como está?"}, {"rolle": "ich", "text": "Sou bem"}]
    r = ai.gespraech(verlauf, "frei", "A1")
    rollen = [m["role"] for m in claude.letzte["messages"]]
    assert rollen == ["user", "assistant", "user"]
    assert r["korrektur"]


def test_korrektur_und_haiku_ohne_fallback(claude, monkeypatch):
    monkeypatch.setenv("CLAUDE_MODELL", "claude-haiku-4-5")
    claude.antwort = FalscheAntwort({"korrigiert": "Chamo-me Stefan.", "fehler": [], "punkte": 90, "urteil": "Gut!"})
    r = ai.korrigieren("Me chamo Stefan.", "", "A1")
    assert r["punkte"] == 90
    assert "fallbacks" not in claude.letzte and "effort" not in claude.letzte["output_config"]


def test_ablehnung_und_ausgeschaltet(claude, monkeypatch):
    claude.antwort = FalscheAntwort({}, stop="refusal")
    with pytest.raises(ai.KIFehler):
        ai.korrigieren("x", "", "A1")
    monkeypatch.setenv("CLAUDE_AKTIV", "nein")
    with pytest.raises(ai.KIFehler, match="nicht eingeschaltet"):
        ai.gespraech([], "frei", "A1")


def test_ki_api_ohne_key(tmp_path, monkeypatch):
    monkeypatch.setenv("PORTUGUES_DB", str(tmp_path / "api.sqlite"))
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    from backend.main import app
    with TestClient(app) as c:
        assert c.post("/api/ki/gespraech", json={}).status_code == 503
        assert c.post("/api/ki/korrektur", json={"text": ""}).status_code == 400
