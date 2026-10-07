"""Tests für die Antwortprüfung (pruefen.py)."""

import pytest

from backend.pruefen import levenshtein, normalisieren, pruefen


@pytest.mark.parametrize("antwort", [
    "Chamo-me Stefan.", "chamo-me stefan", "  Chamo-me   Stefan!  ", "Chamo-me Stefan",
])
def test_gross_klein_und_satzzeichen_egal(antwort):
    assert pruefen(antwort, ["Chamo-me Stefan."])["ergebnis"] == "richtig"


def test_alternative_loesungen():
    r = pruefen("O meu nome é Stefan", ["Chamo-me Stefan.", "O meu nome é Stefan."])
    assert r["ergebnis"] == "richtig" and r["loesung"] == "O meu nome é Stefan."


def test_fehlender_akzent_ist_fast_richtig():
    r = pruefen("ate amanha", ["Até amanhã!"])
    assert r["ergebnis"] == "fast"
    assert "Akzent" in r["hinweis"]


def test_kleiner_tippfehler_ist_fast_richtig():
    assert pruefen("obrigdo", ["obrigado"])["ergebnis"] == "fast"


def test_kurze_woerter_ohne_tippfehler_toleranz():
    # "sou" und "são" sind verschiedene Wörter – kein "fast"
    assert pruefen("sao", ["sou"])["ergebnis"] == "falsch"


def test_falsch_und_leer():
    assert pruefen("bom dia", ["boa noite"])["ergebnis"] == "falsch"
    assert pruefen("", ["boa noite"])["ergebnis"] == "falsch"


def test_apostrophe_vereinheitlicht():
    assert normalisieren("d’água") == normalisieren("d'água")


def test_levenshtein():
    assert levenshtein("casa", "casa") == 0
    assert levenshtein("casa", "cama") == 1
    assert levenshtein("", "abc") == 3


def test_ohne_loesung():
    with pytest.raises(ValueError):
        pruefen("x", [])
