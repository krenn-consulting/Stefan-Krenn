"""Tests für Wiederholungslektionen, Einheitentests und den Level-Test (pruefungen.py)."""

import random
from datetime import datetime, timedelta

import pytest

from backend import content, db, lesson, pruefungen

TAG1 = datetime(2026, 10, 7, 9, 0)
SPAETER = TAG1 + timedelta(hours=2)


@pytest.fixture
def con(tmp_path):
    c = db.connect(tmp_path / "pruefung.sqlite")
    db.init_db(c)
    yield c
    c.close()


def plan(con, lesson_id=None, now=TAG1):
    return lesson.plan(con, lesson_id=lesson_id, now=now, rng=random.Random(7))


def bearbeiten(con, p, ergebnis="richtig", ueberspringen=(), now=TAG1):
    """Alle Blöcke einer Lektion beantworten (oder überspringen) und abschließen."""
    for b in p["bloecke"][:-1]:
        if b["id"] in ueberspringen:
            lesson.block_speichern(con, p["id"], b["id"], "uebersprungen")
            continue
        for s in b["schritte"]:
            if s.get("ref"):
                lesson.antwort_verbuchen(con, {"lesson_id": p["id"], "block": b["id"], "ergebnis": ergebnis,
                                               "antwort": "x", "schritt": s}, now=now)
        lesson.block_speichern(con, p["id"], b["id"], "fertig", 60)
    return lesson.lektion_abschliessen(con, p["id"], 4, now=now)


def bis_vor(con, lesson_id):
    """Alle Lektionen vor lesson_id richtig erledigen."""
    while lesson.naechste_lektion(con)["id"] != lesson_id:
        bearbeiten(con, plan(con))


def test_wiederholungslektion(con):
    bis_vor(con, "A1-01-L07")
    p = plan(con)
    assert p["typ"] == "wiederholung"
    assert [b["id"] for b in p["bloecke"]] == [b[0] for b in pruefungen.WIEDERHOLUNG_BLOECKE]
    bloecke = {b["id"]: b["schritte"] for b in p["bloecke"]}
    assert len(bloecke["wortschatz"]) == 12
    assert bloecke["grammatik"] and bloecke["hoeren"] and bloecke["sprechen"]
    # nur Wörter dieser Einheit
    assert all(s["ref"]["item_id"].startswith("A1-01:") for s in bloecke["wortschatz"])


def test_einheitentest_nicht_bestanden_und_dann_bestanden(con):
    bis_vor(con, "A1-01-L08")
    p = plan(con)
    assert p["typ"] == "test" and p["bestanden_ab"] == 0.8
    assert [b["id"] for b in p["bloecke"]] == ["hoeren", "lesen", "grammatik", "schreiben", "sprechen", "abschluss"]

    e = bearbeiten(con, p, "falsch")
    assert not e["test"]["bestanden"]
    assert e["test"]["wiederholung_id"] == "A1-01-L07"
    n = lesson.naechste_lektion(con)
    assert n["id"] == "A1-01-L08" and n["test_nicht_bestanden"]

    e = bearbeiten(con, plan(con, now=SPAETER), "richtig", now=SPAETER)
    assert e["test"]["bestanden"] and e["test"]["gesamt"] == 1.0
    assert lesson.naechste_lektion(con)["id"] == "A1-02-L01"


def test_vorgezogener_test_ueberspringt_die_einheit(con):
    assert lesson.naechste_lektion(con)["test_id"] == "A1-01-L08"
    e = bearbeiten(con, plan(con, "A1-01-L08"))
    assert e["test"]["bestanden"]
    assert e["test"]["uebersprungene_lektionen"] == 7
    assert lesson.naechste_lektion(con)["id"] == "A1-02-L01"
    # Wörter der übersprungenen Einheit kommen in 3 Tagen in die Wiederholung
    karte = con.execute("SELECT state, interval_days FROM cards WHERE item_id = 'A1-01:v:bom-dia'").fetchone()
    assert karte["state"] == "review" and karte["interval_days"] == 3


def test_uebersprungener_bereich_zaehlt_null(con):
    e = bearbeiten(con, plan(con, "A1-01-L08"), ueberspringen=("hoeren",))
    bereiche = {b["id"]: b["anteil"] for b in e["test"]["bereiche"]}
    assert bereiche["hoeren"] == 0
    assert e["test"]["gesamt"] == 0.8      # 4 von 5 Bereichen voll
    e = bearbeiten(con, plan(con, "A1-02-L08"), ueberspringen=("hoeren", "lesen"))
    assert not e["test"]["bestanden"]


def test_neuer_versuch_beginnt_frisch(con):
    bearbeiten(con, plan(con, "A1-01-L08"), "falsch")
    e = bearbeiten(con, plan(con, "A1-01-L08", now=SPAETER), "richtig", now=SPAETER)
    assert e["test"]["gesamt"] == 1.0       # alte falsche Antworten zählen nicht mehr


def test_leveltest_teile(con):
    teil1 = plan(con, "A1-13-L01")
    teil2 = plan(con, "A1-13-L02")
    assert teil1["typ"] == "leveltest"
    assert [b["id"] for b in teil1["bloecke"]] == ["hoeren", "lesen", "grammatik", "abschluss"]
    assert [b["id"] for b in teil2["bloecke"]] == ["schreiben", "sprechen", "abschluss"]

    hoeren = next(b for b in teil1["bloecke"] if b["id"] == "hoeren")["schritte"]
    assert sum(s["typ"] == "dialog" for s in hoeren) == 2      # beide Hördialoge
    grammatik = next(b for b in teil1["bloecke"] if b["id"] == "grammatik")["schritte"]
    assert len(grammatik) == 22
    einheiten = {s["ref"]["item_id"].split(":")[0] for s in grammatik if s["ref"]["kind"] == "vocab"}
    assert "A1-13" not in einheiten and len(einheiten) > 1     # Wörter aus dem ganzen Level

    assert bearbeiten(con, teil2)["test"]["bestanden"]
    assert content.lesson("A1-13-L02")["id"] in lesson.erledigte_lektionen(con)
