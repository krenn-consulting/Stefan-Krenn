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


# --- Gesprochene Antworten (Spracherkennung) --------------------------------

_ZAHLEN = {
    "0": "zero", "1": "um", "2": "dois", "3": "três", "4": "quatro", "5": "cinco", "6": "seis",
    "7": "sete", "8": "oito", "9": "nove", "10": "dez", "11": "onze", "12": "doze", "13": "treze",
    "14": "catorze", "15": "quinze", "16": "dezasseis", "17": "dezassete", "18": "dezoito",
    "19": "dezanove", "20": "vinte", "30": "trinta", "40": "quarenta", "50": "cinquenta",
    "100": "cem",
}


def _fuer_sprache(text: str) -> str:
    """Spracherkennung schreibt Zahlen oft als Ziffern und setzt Akzente anders."""
    woerter = [_ZAHLEN.get(w, w) for w in normalisieren(text).split()]
    return ohne_akzente(" ".join(woerter))


def pruefen_gesprochen(varianten: list[str], loesungen: list[str]) -> dict:
    """Großzügiger als beim Tippen: Akzente egal, mehr Toleranz, Wortübereinstimmung.

    Die Spracherkennung macht selbst Fehler – du sollst nicht für ihre
    Fehler bestraft werden.
    """
    if not loesungen:
        raise ValueError("Keine Lösung angegeben")
    bestes = {"ergebnis": "falsch", "loesung": loesungen[0], "hinweis": "", "erkannt": varianten[0] if varianten else ""}
    rang = {"falsch": 0, "fast": 1, "richtig": 2}
    for v in varianten:
        a = _fuer_sprache(v)
        for l in loesungen:
            nl = _fuer_sprache(l)
            if not a:
                continue
            if a == nl:
                e = "richtig"
            elif levenshtein(a, nl) <= max(1, len(nl) // 12):
                e = "fast"      # z. B. "bom tarde" statt "boa tarde" – kleiner, aber echter Fehler
            else:
                ziel = nl.split()
                treffer = sum(1 for w in ziel if w in a.split())
                e = "fast" if ziel and treffer / len(ziel) >= 0.7 else "falsch"
            if rang[e] > rang[bestes["ergebnis"]]:
                bestes = {"ergebnis": e, "loesung": l, "erkannt": v,
                          "hinweis": "Fast – einzelne Wörter waren noch nicht klar." if e == "fast" else ""}
    return bestes
