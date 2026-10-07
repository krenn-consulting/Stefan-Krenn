"""Tests für das Wiederholungssystem (srs.py)."""

from datetime import datetime, timedelta

import pytest

from backend import srs

JETZT = datetime(2026, 10, 7, 9, 30)


def neue_karte():
    return {"state": "new", "step": 0, "ease": 2.5, "interval_days": 0, "reps": 0, "lapses": 0}


def test_neue_karte_durchlaeuft_lernstufen():
    k = srs.schedule(neue_karte(), "richtig", JETZT)
    assert k["state"] == "learning" and k["step"] == 1
    assert k["due"] == (JETZT + timedelta(minutes=10)).isoformat(timespec="seconds")

    k = srs.schedule(k, "richtig", JETZT)
    assert k["state"] == "review"
    assert k["interval_days"] == 1
    # fällig ab Beginn des nächsten Tages – egal zu welcher Uhrzeit gelernt wird
    assert k["due"] == "2026-10-08T00:00:00"


def test_falsch_in_lernphase_beginnt_von_vorn():
    k = srs.schedule(neue_karte(), "richtig", JETZT)
    k = srs.schedule(k, "falsch", JETZT)
    assert k["state"] == "learning" and k["step"] == 0
    assert k["due"] == (JETZT + timedelta(minutes=1)).isoformat(timespec="seconds")


def test_fast_wiederholt_die_stufe():
    k = srs.schedule(neue_karte(), "fast", JETZT)
    assert k["step"] == 0 and k["state"] == "learning"


def _review_karte(intervall=10.0, ease=2.5):
    return {"state": "review", "step": 0, "ease": ease, "interval_days": intervall, "reps": 5, "lapses": 0}


def test_abstaende_wachsen():
    k = _review_karte(intervall=1.0)
    abstaende = []
    for _ in range(4):
        k = srs.schedule(k, "richtig", JETZT)
        abstaende.append(k["interval_days"])
    assert abstaende == sorted(abstaende)
    assert abstaende[0] == 2.5 and abstaende[-1] > 30


def test_fast_waechst_langsamer_und_macht_karte_schwerer():
    richtig = srs.schedule(_review_karte(), "richtig", JETZT)
    fast = srs.schedule(_review_karte(), "fast", JETZT)
    assert fast["interval_days"] < richtig["interval_days"]
    assert fast["ease"] < richtig["ease"]


def test_vergessen_halbiert_statt_alles_zu_verwerfen():
    k = srs.schedule(_review_karte(intervall=20), "falsch", JETZT)
    assert k["state"] == "learning" and k["lapses"] == 1
    assert k["interval_days"] == 10
    assert k["ease"] == pytest.approx(2.3)
    # nach dem Neulernen gilt der halbierte Abstand
    k = srs.schedule(k, "richtig", JETZT)
    k = srs.schedule(k, "richtig", JETZT)
    assert k["state"] == "review" and k["interval_days"] == 10


def test_leichtigkeit_hat_untergrenze():
    k = _review_karte(ease=1.35)
    for _ in range(5):
        k = srs.schedule({**k, "state": "review"}, "falsch", JETZT)
    assert k["ease"] == srs.MIN_LEICHTIGKEIT


def test_intervall_hat_obergrenze():
    k = srs.schedule(_review_karte(intervall=300, ease=2.5), "richtig", JETZT)
    assert k["interval_days"] == srs.MAX_INTERVALL_TAGE


def test_eingabe_bleibt_unveraendert():
    k = neue_karte()
    srs.schedule(k, "richtig", JETZT)
    assert k == neue_karte()


def test_unbekanntes_ergebnis():
    with pytest.raises(ValueError):
        srs.schedule(neue_karte(), "super", JETZT)


@pytest.mark.parametrize("limit, heute, faellig, erwartet", [
    (15, 0, 0, 15),
    (15, 4, 0, 11),
    (15, 14, 0, 3),     # Limit durch Lektionsvokabeln erreicht → trotzdem 3 Satzmuster
    (0, 0, 0, 0),       # 0 = bewusst keine neuen Karten
    (15, 0, 60, 7),     # Lastbremse: halbiert
    (15, 0, 100, 0),    # Lastbremse: keine neuen
])
def test_neue_karten_erlaubt(limit, heute, faellig, erwartet):
    assert srs.neue_karten_erlaubt(limit, heute, faellig) == erwartet
