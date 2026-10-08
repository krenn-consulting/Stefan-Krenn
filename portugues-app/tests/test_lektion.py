"""Tests für den Lektionsablauf (lesson.py) und die Lektions-API."""

import random
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from backend import db, lesson

TAG1 = datetime(2026, 10, 7, 9, 0)


@pytest.fixture
def con(tmp_path):
    c = db.connect(tmp_path / "lektion.sqlite")
    db.init_db(c)
    yield c
    c.close()


def plan(con, **kw):
    kw.setdefault("now", TAG1)
    kw.setdefault("rng", random.Random(42))
    return lesson.plan(con, **kw)


def block(p, bid):
    return next(b for b in p["bloecke"] if b["id"] == bid)


def beantworte(con, p, bid, ergebnis="richtig", now=TAG1):
    """Beantwortet alle Fragen eines Blocks mit dem gegebenen Ergebnis."""
    n = 0
    for s in block(p, bid)["schritte"]:
        if s.get("ref"):
            lesson.antwort_verbuchen(con, {"lesson_id": p["id"], "block": bid, "ergebnis": ergebnis,
                                           "antwort": "x", "schritt": s}, now=now)
            n += 1
    return n


def lektion_komplett(con, now=TAG1, ergebnis="richtig"):
    p = plan(con, now=now)
    for b in p["bloecke"][:-1]:
        beantworte(con, p, b["id"], ergebnis, now)
        lesson.block_speichern(con, p["id"], b["id"], "fertig", 60)
    return p, lesson.lektion_abschliessen(con, p["id"], 4, now=now)


# --- Aufbau ------------------------------------------------------------------

def test_erste_lektion_hat_sechs_bloecke_und_30_minuten(con):
    p = plan(con)
    assert p["id"] == "A1-01-L01"
    assert [b["id"] for b in p["bloecke"]] == [
        "wiederholung", "wortschatz", "grammatik", "hoeren", "sprechen", "abschluss"]
    assert sum(b["minuten"] for b in p["bloecke"]) == 30
    assert block(p, "wiederholung")["schritte"] == []      # am ersten Tag nichts fällig


def test_lektionsdauer_aus_einstellungen(con):
    db.save_settings(con, {"lektionsdauer_min": 15})
    p = plan(con)
    assert sum(b["minuten"] for b in p["bloecke"]) == 15
    assert block(p, "grammatik")["minuten"] == 3.5


def test_wortschatz_erst_vorstellen_dann_abrufen(con):
    schritte = block(plan(con), "wortschatz")["schritte"]
    vorgestellt = set()
    for s in schritte:
        if s["typ"] == "vokabel":
            vorgestellt.add(s["item_id"])
        else:
            # jedes Wort wird erst abgefragt, nachdem es gezeigt wurde
            assert s["ref"]["item_id"] in vorgestellt
            assert s["art"] == "de-pt"   # aktives Abrufen, nicht nur Wiedererkennen
    assert len(vorgestellt) == 11


def test_alle_schritttypen_der_lektion_sind_gueltig(con):
    erlaubt = {"info", "vokabel", "eingabe", "auswahl", "satzbau", "dialog", "nachsprechen"}
    for lid in ["A1-01-L01", "A1-01-L02", "A1-01-L03", "A1-01-L04", "A1-01-L05", "A1-01-L06"]:
        for b in plan(con, lesson_id=lid)["bloecke"]:
            for s in b["schritte"]:
                assert s["typ"] in erlaubt
                if s["typ"] in ("eingabe", "satzbau"):
                    assert s["loesungen"], s


# --- Antworten, Karten, Fehler -----------------------------------------------

def test_antwort_legt_karte_an_und_plant_sie(con):
    p = plan(con)
    s = next(x for x in block(p, "wortschatz")["schritte"] if x["typ"] == "eingabe")
    r = lesson.antwort_verbuchen(con, {"lesson_id": p["id"], "block": "wortschatz",
                                       "ergebnis": "richtig", "schritt": s}, now=TAG1)
    assert r["karte"]["state"] == "learning"
    karte = con.execute("SELECT * FROM cards WHERE item_id = ?", (s["ref"]["item_id"],)).fetchone()
    assert karte["kind"] == "vocab" and karte["unit_id"] == "A1-01"


def test_falsche_uebung_kommt_als_fehlerkarte_wieder(con):
    p = plan(con)
    uebung = next(x for x in block(p, "grammatik")["schritte"] if x.get("ref"))
    lesson.antwort_verbuchen(con, {"lesson_id": p["id"], "block": "grammatik", "ergebnis": "falsch",
                                   "antwort": "falsch!", "schritt": uebung}, now=TAG1)
    fehler = con.execute("SELECT * FROM mistakes").fetchone()
    assert fehler["given"] == "falsch!" and fehler["resolved"] == 0

    # Am nächsten Tag taucht die Übung im Wiederholungsblock auf
    morgen = plan(con, now=TAG1 + timedelta(days=1))
    wdh = block(morgen, "wiederholung")["schritte"]
    fehler_schritte = [s for s in wdh if s["ref"]["kind"] == "mistake"]
    assert len(fehler_schritte) == 1
    assert fehler_schritte[0]["wiederholt"]

    # Zweimal richtig → behoben, Fehlerkarte ruht
    for _ in range(2):
        lesson.antwort_verbuchen(con, {"lesson_id": "x", "block": "wiederholung", "ergebnis": "richtig",
                                       "schritt": fehler_schritte[0]}, now=TAG1 + timedelta(days=1))
    assert con.execute("SELECT resolved FROM mistakes").fetchone()["resolved"] == 1
    assert con.execute("SELECT state FROM cards WHERE kind='mistake'").fetchone()["state"] == "erledigt"


def test_selbstbewertung_beim_sprechen_ist_kein_fehler(con):
    p = plan(con)
    beantworte(con, p, "sprechen", "falsch")
    assert con.execute("SELECT COUNT(*) FROM mistakes").fetchone()[0] == 0


# --- Blöcke überspringen und fortsetzen ---------------------------------------

def test_uebersprungener_block_wird_gemerkt(con):
    p = plan(con)
    lesson.block_speichern(con, p["id"], "wiederholung", "fertig", 30)
    lesson.block_speichern(con, p["id"], "wortschatz", "uebersprungen", 5)
    p2 = plan(con)
    assert block(p2, "wiederholung")["status"] == "fertig"
    assert block(p2, "wortschatz")["status"] == "uebersprungen"
    assert block(p2, "grammatik")["status"] is None
    assert lesson.naechste_lektion(con)["begonnen"] is True


def test_ungueltiger_blockstatus(con):
    with pytest.raises(ValueError):
        lesson.block_speichern(con, "A1-01-L01", "grammatik", "halb")


# --- Abschluss, nächste Lektion, Interleaving ---------------------------------

def test_abschluss_und_naechste_lektion(con):
    p, ergebnis = lektion_komplett(con)
    assert ergebnis["score"] == 1.0
    assert ergebnis["neue_saetze"] == 3
    assert lesson.naechste_lektion(con)["id"] == "A1-01-L02"
    assert lesson.heute_erledigt(con) >= 0
    # Lernzeit und Lektion im Tageslog
    log = con.execute("SELECT * FROM daily_log WHERE day = ?", (TAG1.date().isoformat(),)).fetchone()
    assert log["lessons"] == 1
    # Blockzeiten werden auf den echten heutigen Tag gebucht
    assert con.execute("SELECT SUM(seconds) AS s FROM daily_log").fetchone()["s"] > 0


def test_score_zaehlt_fast_als_richtig(con):
    p = plan(con)
    beantworte(con, p, "wortschatz", "fast")
    beantworte(con, p, "grammatik", "falsch")
    e = lesson.lektion_abschliessen(con, p["id"], 3, now=TAG1)
    assert 0 < e["score"] < 1
    assert e["je_block"]["wortschatz"]["gut"] == e["je_block"]["wortschatz"]["gesamt"]
    assert e["je_block"]["grammatik"]["gut"] == 0


def test_interleaving_streut_alte_uebungen_ein(con):
    lektion_komplett(con)
    p2 = plan(con, now=TAG1 + timedelta(hours=1))
    assert p2["id"] == "A1-01-L02"
    alt = [s for s in block(p2, "grammatik")["schritte"] if s.get("wiederholt")]
    assert len(alt) == lesson.EINGESTREUTE_UEBUNGEN
    assert all(s["ref"]["item_id"].startswith("A1-01-L01") for s in alt)


def test_naechster_tag_wiederholt_gelernte_woerter(con):
    lektion_komplett(con)
    morgen = plan(con, now=TAG1 + timedelta(days=1))
    wdh = block(morgen, "wiederholung")["schritte"]
    ids = {s.get("ref", {}).get("item_id") or s.get("item_id") for s in wdh}
    assert any(i and ":v:" in i for i in ids)        # Vokabeln fällig
    assert any(i and ":s:" in i for i in ids)        # neue Satzkarten eingeführt


def test_neue_satzkarten_respektieren_tageslimit(con):
    db.save_settings(con, {"neue_karten_pro_tag": 0})
    lektion_komplett(con)
    morgen = plan(con, now=TAG1 + timedelta(days=1))
    neu = [s for s in block(morgen, "wiederholung")["schritte"] if s.get("titel") == "Neuer Satz"]
    assert neu == []


def test_wiederholungstag(con):
    lektion_komplett(con)
    p = lesson.plan(con, modus="wiederholung", now=TAG1 + timedelta(days=1), rng=random.Random(1))
    assert [b["id"] for b in p["bloecke"]] == ["wiederholung", "abschluss"]
    assert p["id"].startswith("WH-")
    assert block(p, "wiederholung")["schritte"]
    # Ein Wiederholungstag zählt nicht als neue Lektion
    lesson.lektion_abschliessen(con, p["id"], None, now=TAG1 + timedelta(days=1))
    assert lesson.naechste_lektion(con)["id"] == "A1-01-L02"


def test_alle_lektionen_erledigt(con):
    """Ganz A1 durchlaufen (alles richtig): Tests werden bestanden, am Ende ist nichts mehr offen."""
    from backend import content
    gesehen = []
    while lesson.naechste_lektion(con) is not None and len(gesehen) < 200:
        p, ergebnis = lektion_komplett(con)
        gesehen.append(p["id"])
        if p["typ"] in ("test", "leveltest"):
            assert ergebnis["test"]["bestanden"], p["id"]
    assert gesehen == content.lesson_order()
    assert lesson.naechste_lektion(con) is None
    assert lesson.plan(con, now=TAG1) is None


# --- API -----------------------------------------------------------------------

@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("PORTUGUES_DB", str(tmp_path / "api.sqlite"))
    from backend.main import app
    with TestClient(app) as c:
        yield c


def test_api_kompletter_ablauf(client):
    p = client.get("/api/lektion").json()
    assert p["id"] == "A1-01-L01"
    s = next(x for x in p["bloecke"][1]["schritte"] if x["typ"] == "eingabe")

    pr = client.post("/api/pruefen", json={"antwort": s["loesungen"][0], "loesungen": s["loesungen"]}).json()
    assert pr["ergebnis"] == "richtig"
    r = client.post("/api/antwort", json={"lesson_id": p["id"], "block": "wortschatz",
                                          "ergebnis": "richtig", "antwort": "x", "schritt": s})
    assert r.status_code == 200

    for b in p["bloecke"][:-1]:
        assert client.post(f"/api/lektion/{p['id']}/block",
                           json={"block": b["id"], "status": "fertig", "sekunden": 30}).status_code == 200
    z = client.get(f"/api/lektion/{p['id']}/zusammenfassung").json()
    assert z["gesamt"] == 1 and len(z["woerter"]) == 11
    e = client.post(f"/api/lektion/{p['id']}/abschluss", json={"selbsteinschaetzung": 5, "sekunden": 20}).json()
    assert e["score"] == 1.0

    o = client.get("/api/overview").json()
    assert o["naechste_lektion"]["id"] == "A1-01-L02"
    assert o["heute_erledigt"] == 1 and o["fortschritt"]["erledigt"] == 1


def test_api_fehlerhafte_eingaben(client):
    assert client.post("/api/antwort", json={"ergebnis": "vielleicht"}).status_code == 400
    assert client.post("/api/antwort", json={"ergebnis": "richtig", "schritt": {}}).status_code == 400
    assert client.post("/api/pruefen", json={"antwort": "x", "loesungen": []}).status_code == 400
    assert client.post("/api/lektion/A1-01-L01/block", json={"block": "x", "status": "?"}).status_code == 400


def test_satzmuster_kommen_auch_nach_einer_lektion_dazu(con):
    # Die Lektionsvokabeln schöpfen das Tageslimit aus – Sätze kommen trotzdem
    lektion_komplett(con)
    p2 = plan(con, now=TAG1 + timedelta(hours=2))
    neu = [s for s in block(p2, "wiederholung")["schritte"] if s.get("titel") == "Neuer Satz"]
    assert len(neu) == 3
