"""Prüft alle Inhaltsdateien (Format und europäisches Portugiesisch)."""

from backend import content, inhalt_check


def test_alle_inhalte_fehlerfrei():
    probleme = inhalt_check.pruefe_alle()
    assert probleme == [], "\n".join(probleme)


def test_a1_01_vorhanden():
    assert content.lesson("A1-01-L01") is not None
    assert content.item("A1-01:v:bom-dia")["pt"] == "bom dia"


def test_brasilianismen_werden_erkannt():
    einheit = {
        "id": "X1-01", "titel": "Test",
        "vokabeln": [{"id": "a", "pt": "o ônibus", "de": "der Bus"},
                     {"id": "b", "pt": "Me chamo Ana.", "de": "Ich heiße Ana."},
                     {"id": "c", "pt": "Estou trabalhando.", "de": "Ich arbeite gerade."},
                     {"id": "d", "pt": "dezesseis", "de": "16"}],
        "lektionen": [],
    }
    probleme = " ".join(inhalt_check.pruefe_einheit(einheit))
    for erwartet in ("autocarro", "Enklise", "estar a", "dezasseis"):
        assert erwartet in probleme


def test_formfehler_werden_erkannt():
    einheit = {
        "id": "X1-01", "titel": "Test", "vokabeln": [{"id": "a", "pt": "olá", "de": "hallo"}],
        "lektionen": [{"id": "X1-01-L01", "titel": "T", "vokabeln": ["a", "fehlt"],
                       "grammatik": {"titel": "G", "uebungen": [
                           {"typ": "auswahl", "frage": "?", "optionen": ["a"], "richtig": 3},
                           {"typ": "luecke", "satz": "ohne Lücke", "loesungen": ["x"]}]}}],
    }
    probleme = " ".join(inhalt_check.pruefe_einheit(einheit))
    assert "'fehlt'" in probleme
    assert "keine Option" in probleme
    assert "ohne ___" in probleme
