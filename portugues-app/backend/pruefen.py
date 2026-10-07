"""Antworten prüfen: richtig, fast richtig (Akzent/Tippfehler) oder falsch."""

import re
import unicodedata

# Satzzeichen, die beim Vergleich keine Rolle spielen
_SATZZEICHEN = re.compile(r"[.,;:!?¿¡\"“”„«»()…–—]")


def normalisieren(text: str) -> str:
    """Kleinschreibung, einheitliche Apostrophe, ohne Satzzeichen und Doppel-Leerzeichen."""
    text = unicodedata.normalize("NFC", text or "").lower()
    text = text.replace("’", "'").replace("‘", "'").replace("´", "'")
    text = _SATZZEICHEN.sub(" ", text)
    return " ".join(text.split())


def ohne_akzente(text: str) -> str:
    zerlegt = unicodedata.normalize("NFD", text)
    return "".join(z for z in zerlegt if unicodedata.category(z) != "Mn")


def levenshtein(a: str, b: str) -> int:
    """Anzahl Buchstaben-Änderungen, um a in b zu verwandeln."""
    if len(a) < len(b):
        a, b = b, a
    vorher = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        jetzt = [i]
        for j, cb in enumerate(b, 1):
            jetzt.append(min(vorher[j] + 1, jetzt[j - 1] + 1, vorher[j - 1] + (ca != cb)))
        vorher = jetzt
    return vorher[-1]


def _erlaubte_tippfehler(loesung: str) -> int:
    n = len(loesung)
    if n < 5:
        return 0
    if n < 15:
        return 1
    return 2


def pruefen(antwort: str, loesungen: list[str]) -> dict:
    """Vergleicht die Antwort mit allen akzeptierten Lösungen.

    Ergebnis: {"ergebnis": richtig|fast|falsch, "loesung": beste Lösung, "hinweis": Text}
    """
    if not loesungen:
        raise ValueError("Keine Lösung angegeben")
    a = normalisieren(antwort)

    for l in loesungen:
        if a == normalisieren(l):
            return {"ergebnis": "richtig", "loesung": l, "hinweis": ""}

    if not a:
        return {"ergebnis": "falsch", "loesung": loesungen[0], "hinweis": ""}

    for l in loesungen:
        if ohne_akzente(a) == ohne_akzente(normalisieren(l)):
            return {"ergebnis": "fast", "loesung": l,
                    "hinweis": "Fast! Achte auf die Akzente bzw. das ç."}

    for l in loesungen:
        nl = normalisieren(l)
        if levenshtein(ohne_akzente(a), ohne_akzente(nl)) <= _erlaubte_tippfehler(nl):
            return {"ergebnis": "fast", "loesung": l,
                    "hinweis": "Fast! Nur ein kleiner Tippfehler."}

    return {"ergebnis": "falsch", "loesung": loesungen[0], "hinweis": ""}
