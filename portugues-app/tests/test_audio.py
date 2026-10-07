"""Tests für Sprachausgabe (tts.py) und Prüfung gesprochener Antworten.

Der echte Stimmen-Dienst wird durch eine Attrappe ersetzt – die Tests
laufen also auch ohne Internet.
"""

import sys
import types

import pytest
from fastapi.testclient import TestClient

from backend import tts
from backend.pruefen import pruefen_gesprochen


class FalscherDienst:
    """Ersetzt edge_tts.Communicate und zählt die Aufrufe."""
    aufrufe = []
    kaputt = False

    def __init__(self, text, voice, **kw):
        self.text, self.voice = text, voice

    async def save(self, pfad):
        FalscherDienst.aufrufe.append((self.text, self.voice))
        if FalscherDienst.kaputt:
            raise ConnectionError("kein Internet")
        with open(pfad, "wb") as f:
            f.write(b"ID3-fake-mp3")


@pytest.fixture(autouse=True)
def attrappe(monkeypatch, tmp_path):
    modul = types.SimpleNamespace(Communicate=FalscherDienst)
    monkeypatch.setitem(sys.modules, "edge_tts", modul)
    monkeypatch.setenv("PORTUGUES_AUDIO", str(tmp_path / "audio"))
    monkeypatch.setenv("PORTUGUES_DB", str(tmp_path / "db.sqlite"))
    FalscherDienst.aufrufe = []
    FalscherDienst.kaputt = False


@pytest.fixture
def client():
    from backend.main import app
    with TestClient(app) as c:
        yield c


def test_audio_wird_erzeugt_und_zwischengespeichert(client):
    r = client.get("/api/audio", params={"text": "Bom dia!", "stimme": "f"})
    assert r.status_code == 200 and r.headers["content-type"] == "audio/mpeg"
    assert r.content == b"ID3-fake-mp3"
    client.get("/api/audio", params={"text": "Bom dia!", "stimme": "f"})
    assert FalscherDienst.aufrufe == [("Bom dia!", "pt-PT-RaquelNeural")]   # nur einmal erzeugt


def test_stimmen_auswahl(client):
    client.get("/api/audio", params={"text": "Olá", "stimme": "m"})
    client.put("/api/settings", json={"stimme": "pt-PT-DuarteNeural"})
    client.get("/api/audio", params={"text": "Adeus", "stimme": "standard"})
    assert [v for _, v in FalscherDienst.aufrufe] == ["pt-PT-DuarteNeural", "pt-PT-DuarteNeural"]
    assert tts.stimme_waehlen("irgendwas", "unbekannt") == "pt-PT-RaquelNeural"


def test_ohne_internet_meldet_503_und_hinterlaesst_nichts(client, tmp_path):
    FalscherDienst.kaputt = True
    r = client.get("/api/audio", params={"text": "Boa noite", "stimme": "f"})
    assert r.status_code == 503
    assert not list((tmp_path / "audio").rglob("*.mp3"))
    assert not list((tmp_path / "audio").rglob("*.tmp"))


def test_zu_langer_oder_leerer_text(client):
    assert client.get("/api/audio", params={"text": "a" * 1000}).status_code == 503
    assert client.get("/api/audio", params={"text": "   "}).status_code == 503


def test_vorladen(client):
    import asyncio
    n = asyncio.run(tts.vorladen([("Um", "pt-PT-RaquelNeural"), ("Dois", "pt-PT-DuarteNeural")]))
    assert n == 2
    r = client.post("/api/audio/vorladen", json={"texte": [{"text": "Três"}, {"text": ""}]})
    assert r.json()["anzahl"] == 1


# --- gesprochene Antworten -----------------------------------------------------

@pytest.mark.parametrize("gesprochen, erwartet", [
    (["bom dia dona fernanda"], "richtig"),          # ohne Satzzeichen/Großschreibung
    (["Tenho o 7"], "richtig"),                       # Ziffer statt Wort
    (["ate amanha"], "richtig"),                      # ohne Akzente
    (["xyz", "boa noite e até amanhã"], "richtig"),   # zweite Variante passt
    (["boa noite e amanhã"], "fast"),                 # ein Wort fehlt
    (["bom noite e até amanhã"], "fast"),             # Genusfehler: nicht "richtig"
    (["obrigado"], "falsch"),
])
def test_gesprochen(gesprochen, erwartet):
    ziel = {
        "bom dia dona fernanda": "Bom dia, Dona Fernanda!",
        "Tenho o 7": "Tenho o sete.",
        "ate amanha": "Até amanhã!",
    }.get(gesprochen[0], "Boa noite e até amanhã!")
    assert pruefen_gesprochen(gesprochen, [ziel])["ergebnis"] == erwartet


def test_gesprochen_ueber_api(client):
    r = client.post("/api/pruefen", json={"modus": "sprechen", "varianten": ["olá ana"], "loesungen": ["Olá, Ana!"]})
    assert r.json()["ergebnis"] == "richtig"
