"""Optional: Claude als Gesprächspartner und Korrektor (nur mit API-Key).

Einschalten in einstellungen.env:
    CLAUDE_AKTIV=ja
    ANTHROPIC_API_KEY=sk-ant-...
    CLAUDE_MODELL=claude-opus-5-5     (Standard, frei wählbar)

Ohne Key bleibt alles andere voll funktionsfähig; die entsprechenden
Seiten erscheinen dann einfach nicht.
"""

import json

from . import config

# Modelle, die den serverseitigen Fallback bei Ablehnungen ("refusal") kennen.
# Für sie wird er automatisch aktiviert – das Gespräch läuft dann auf einem
# anderen Modell weiter, statt abzubrechen.
FALLBACK_MODELLE = {"claude-opus-5-5", "claude-opus-5", "claude-fable-5-1", "claude-sonnet-5-5"}

THEMEN = {
    "frei": "ein freies Alltagsgespräch",
    "cafe": "eine Bestellung im Café (du bist der Kellner / die Kellnerin)",
    "vizinha": "ein Gespräch mit der älteren Nachbarin Dona Fernanda im Treppenhaus",
    "canalizador": "ein Telefonat mit einem Klempner wegen eines tropfenden Wasserhahns",
    "financas": "ein Termin bei den Finanças (Finanzamt) wegen der NIF bzw. einer Adressänderung",
    "medico": "ein Arztbesuch im Centro de Saúde",
    "mercado": "ein Einkauf auf dem Markt (Obst, Gemüse, Fisch)",
    "negocios": "ein kurzes geschäftliches Gespräch mit einem portugiesischen Kunden",
}

GESPRAECH_SYSTEM = """Du bist ein geduldiger Gesprächspartner für einen deutschsprachigen Lerner, \
der in Portugal (Algarve) lebt und europäisches Portugiesisch lernt. Sein aktuelles Niveau: {level}.

Situation: {thema}. Bleib in deiner Rolle und führe das Gespräch natürlich weiter.

Sprache: ausschließlich europäisches Portugiesisch (pt-PT), nie brasilianische Formen \
(also z. B. "estou a fazer", "Chamo-me", "autocarro", "telemóvel"). Formelle Anrede mit \
"o senhor" bzw. Verb in der 3. Person, außer die Situation ist ausdrücklich informell.

Passe dich dem Niveau an: bei A1/A2 kurze, einfache Sätze (1–3 Sätze, häufige Wörter), \
bei B1/B2 natürlicher und länger. Stell am Ende meist eine Frage, damit das Gespräch weitergeht.

Korrektur: Wenn die letzte Nachricht des Lerners Fehler enthält, erkläre sie kurz auf \
Deutsch im Feld "korrektur" (richtige Form + ein Satz warum). Kleinigkeiten wie fehlende \
Akzente nur nebenbei erwähnen. Ohne Fehler bleibt "korrektur" leer."""

KORREKTUR_SYSTEM = """Du korrigierst Texte eines deutschsprachigen Lerners, der europäisches \
Portugiesisch (pt-PT) lernt. Aktuelles Niveau: {level}.

Korrigiere in Richtung natürliches europäisches Portugiesisch (keine brasilianischen Formen). \
Erkläre jeden Fehler kurz auf Deutsch, mit Bezug zur Grammatik, wo es hilft (z. B. ser/estar, \
Pronomenstellung, Genus). Bewerte fair für das Niveau: Inhalt und Verständlichkeit zählen mehr \
als jede Kleinigkeit. Schließe mit einem kurzen, ermutigenden Gesamturteil auf Deutsch."""

GESPRAECH_SCHEMA = {
    "type": "object",
    "properties": {
        "antwort_pt": {"type": "string", "description": "Deine Antwort auf Portugiesisch"},
        "uebersetzung_de": {"type": "string", "description": "Deutsche Übersetzung deiner Antwort"},
        "korrektur": {"type": "string", "description": "Korrektur der letzten Lernernachricht auf Deutsch, oder leer"},
    },
    "required": ["antwort_pt", "uebersetzung_de", "korrektur"],
    "additionalProperties": False,
}

KORREKTUR_SCHEMA = {
    "type": "object",
    "properties": {
        "korrigiert": {"type": "string", "description": "Der vollständige korrigierte Text"},
        "fehler": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "original": {"type": "string"},
                    "korrektur": {"type": "string"},
                    "erklaerung": {"type": "string"},
                },
                "required": ["original", "korrektur", "erklaerung"],
                "additionalProperties": False,
            },
        },
        "punkte": {"type": "integer", "description": "0–100, gemessen am Niveau"},
        "urteil": {"type": "string", "description": "Kurzes Gesamturteil auf Deutsch"},
    },
    "required": ["korrigiert", "fehler", "punkte", "urteil"],
    "additionalProperties": False,
}


class KIFehler(Exception):
    pass


def _anfrage(system: str, messages: list[dict], schema: dict, effort: str) -> dict:
    """Eine Anfrage an Claude; Antwort als Dictionary nach dem Schema."""
    if not config.claude_enabled():
        raise KIFehler("Claude ist nicht eingeschaltet (siehe einstellungen.env).")
    import anthropic

    client = anthropic.Anthropic(timeout=90.0)   # liest ANTHROPIC_API_KEY aus der Umgebung
    modell = config.claude_model()
    argumente = dict(
        model=modell, max_tokens=4000, system=system, messages=messages,
        output_config={"format": {"type": "json_schema", "schema": schema}},
    )
    if not modell.startswith("claude-haiku"):
        argumente["output_config"]["effort"] = effort
    try:
        if modell in FALLBACK_MODELLE:
            antwort = client.beta.messages.create(
                betas=["server-side-fallback-2026-07-01"], fallbacks="default", **argumente)
        else:
            antwort = client.messages.create(**argumente)
    except anthropic.AuthenticationError:
        raise KIFehler("Der API-Key wurde nicht akzeptiert. Bitte in einstellungen.env prüfen.")
    except anthropic.NotFoundError:
        raise KIFehler(f"Das Modell „{modell}“ ist nicht verfügbar. Bitte CLAUDE_MODELL prüfen.")
    except anthropic.RateLimitError:
        raise KIFehler("Zu viele Anfragen – bitte in einer Minute noch einmal versuchen.")
    except anthropic.APIConnectionError:
        raise KIFehler("Keine Verbindung zu Claude – bitte Internet prüfen.")
    except anthropic.APIStatusError as e:
        raise KIFehler(f"Claude hat mit einem Fehler geantwortet ({e.status_code}).")

    if antwort.stop_reason == "refusal":
        raise KIFehler("Claude hat diese Anfrage abgelehnt. Bitte anders formulieren.")
    text = "".join(b.text for b in antwort.content if b.type == "text")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        raise KIFehler("Die Antwort von Claude war unvollständig. Bitte noch einmal versuchen.")


def gespraech(verlauf: list[dict], thema: str, level: str) -> dict:
    """verlauf: [{"rolle": "ich"|"claude", "text": "..."}]. Leerer Verlauf = Claude beginnt."""
    system = GESPRAECH_SYSTEM.format(level=level, thema=THEMEN.get(thema, THEMEN["frei"]))
    messages = []
    for v in verlauf[-30:]:   # die letzten 30 Beiträge reichen als Kontext
        rolle = "user" if v.get("rolle") == "ich" else "assistant"
        messages.append({"role": rolle, "content": v.get("text", "")})
    if not messages or messages[0]["role"] != "user":
        messages.insert(0, {"role": "user", "content": "(Bitte beginne das Gespräch.)"})
    # Die Antworten von Claude werden als reiner portugiesischer Text weitergegeben
    return _anfrage(system, messages, GESPRAECH_SCHEMA, effort="low")


def korrigieren(text: str, aufgabe: str, level: str) -> dict:
    system = KORREKTUR_SYSTEM.format(level=level)
    inhalt = f"Aufgabe: {aufgabe or '(freies Schreiben)'}\n\nText des Lerners:\n{text}"
    return _anfrage(system, [{"role": "user", "content": inhalt}], KORREKTUR_SCHEMA, effort="medium")
