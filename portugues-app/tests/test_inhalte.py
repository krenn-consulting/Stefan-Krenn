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


def test_se_als_bindewort_ist_kein_brasilianismus():
    def meldet(satz):
        einheit = {"id": "X1-01", "titel": "T", "vokabeln": [{"id": "a", "pt": satz, "de": "x"}], "lektionen": []}
        return any("Enklise" in p for p in inhalt_check.pruefe_einheit(einheit))
    assert meldet("Se chama Ana.")
    assert meldet("Me diga uma coisa.")
    assert not meldet("Se precisar de alguma coisa, diga.")
    assert not meldet("Se calhar chove amanhã.")
    assert not meldet("Se faz favor.")


def test_a1_komplett():
    assert len(content.lessons_in_level("A1")) == content.PLANNED_LESSONS["A1"]
    typen = [content.lesson(l)["typ"] for l in content.lesson_order() if l.startswith("A1-")]
    assert typen.count("test") == 12 and typen.count("leveltest") == 2
