"""Sprachausgabe mit europäisch-portugiesischen Stimmen (edge-tts).

Warum edge-tts? Es liefert kostenlos die neuronalen Microsoft-Stimmen
"Raquel" (weiblich) und "Duarte" (männlich) in pt-PT – deutlich natürlicher
als die eingebauten Systemstimmen. Jeder Satz wird nur einmal erzeugt und
dann in data/audio-cache/ gespeichert; danach funktioniert er auch offline.

Ist kein Internet da (oder der Dienst nicht erreichbar), meldet der Server
einen Fehler und die Oberfläche nimmt automatisch die Stimme des Mac.
"""

import asyncio
import hashlib
import os
from pathlib import Path

from . import db

STIMMEN = {"f": "pt-PT-RaquelNeural", "m": "pt-PT-DuarteNeural"}
ERLAUBTE_STIMMEN = set(STIMMEN.values())
MAX_TEXTLAENGE = 600

# Höchstens 3 Audios gleichzeitig erzeugen (Vorladen soll den Dienst nicht fluten)
_gleichzeitig = asyncio.Semaphore(3)


class TTSFehler(Exception):
    pass


def cache_dir() -> Path:
    # Für Tests umlenkbar
    return Path(os.environ.get("PORTUGUES_AUDIO", db.DATA_DIR / "audio-cache"))


def stimme_waehlen(stimme: str, standard: str) -> str:
    """'f' / 'm' / 'standard' oder ein Stimmenname → gültiger Stimmenname."""
    if stimme in STIMMEN:
        return STIMMEN[stimme]
    if stimme in ERLAUBTE_STIMMEN:
        return stimme
    return standard if standard in ERLAUBTE_STIMMEN else STIMMEN["f"]


def cache_pfad(text: str, stimme: str) -> Path:
    schluessel = hashlib.sha1(f"{stimme}|{text}".encode("utf-8")).hexdigest()
    return cache_dir() / schluessel[:2] / f"{schluessel}.mp3"


async def audio_datei(text: str, stimme: str) -> Path:
    """Liefert die MP3-Datei für den Text – aus dem Speicher oder frisch erzeugt."""
    text = " ".join((text or "").split())
    if not text:
        raise TTSFehler("Kein Text")
    if len(text) > MAX_TEXTLAENGE:
        raise TTSFehler("Text zu lang")
    if stimme not in ERLAUBTE_STIMMEN:
        raise TTSFehler("Unbekannte Stimme")

    ziel = cache_pfad(text, stimme)
    if ziel.exists() and ziel.stat().st_size > 0:
        return ziel

    ziel.parent.mkdir(parents=True, exist_ok=True)
    tmp = ziel.with_suffix(f".{os.getpid()}.tmp")
    async with _gleichzeitig:
        if ziel.exists():      # inzwischen von einer anderen Anfrage erzeugt
            return ziel
        try:
            import edge_tts
            await asyncio.wait_for(edge_tts.Communicate(text, stimme).save(str(tmp)), timeout=20)
        except Exception as e:  # kein Internet, Dienst geändert, Zeitüberschreitung …
            tmp.unlink(missing_ok=True)
            raise TTSFehler(f"Audio konnte nicht erzeugt werden: {e}") from e
    if not tmp.exists() or tmp.stat().st_size == 0:
        tmp.unlink(missing_ok=True)
        raise TTSFehler("Leere Audiodatei")
    tmp.replace(ziel)   # erst am Ende umbenennen → nie halbe Dateien im Speicher
    return ziel


async def vorladen(eintraege: list[tuple[str, str]]) -> int:
    """Erzeugt Audios im Voraus (z. B. für die ganze Lektion). Fehler werden ignoriert."""
    erzeugt = 0

    async def eins(text, stimme):
        nonlocal erzeugt
        try:
            await audio_datei(text, stimme)
            erzeugt += 1
        except TTSFehler:
            pass

    await asyncio.gather(*(eins(t, s) for t, s in eintraege))
    return erzeugt


def cache_groesse_mb() -> float:
    d = cache_dir()
    if not d.exists():
        return 0.0
    return round(sum(f.stat().st_size for f in d.rglob("*.mp3")) / 1_000_000, 1)
