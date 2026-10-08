"""Prüft die Inhaltsdateien auf Formfehler und typisch brasilianische Formen.

Aufruf (zeigt alle Probleme an):  uv run python -m backend.inhalt_check
Wird auch von den automatischen Tests benutzt.
"""

import re
import sys

from . import content

# Typisch brasilianische Wörter/Formen, die in pt-PT-Inhalten nicht vorkommen
# sollen (in Erklärungen dürfen sie als Gegenbeispiel stehen – geprüft werden
# nur portugiesische Sätze und Lösungen).
BRASILIANISMEN = [
    (r"\bônibus\b", "ônibus → autocarro"),
    (r"\btrem\b", "trem → comboio"),
    (r"\bcelular\b", "celular → telemóvel"),
    (r"\bbanheiro\b", "banheiro → casa de banho"),
    (r"\bcafé da manhã\b", "café da manhã → pequeno-almoço"),
    (r"\bgeladeira\b", "geladeira → frigorífico"),
    (r"\bdezesseis\b|\bdezessete\b|\bdezenove\b", "dezesseis/… → dezasseis/dezassete/dezanove"),
    (r"\bvocê\b", "você nur bewusst verwenden – Standard: o senhor/a senhora oder tu"),
    (r"(?i)\b(estou|está|estamos|estão|estás) \w+ndo\b", "estar + Gerundium → estar a + Infinitiv"),
    # Ausnahmen: „Se faz favor“ (= bitte), „Se calhar“ (= vielleicht) und
    # „Se“ als Bindewort „wenn“ (Se precisar …, Se tivesse …, Se não …)
    (r"(^|[.!?–]\s*)(?!Se faz favor)(?!Se (calhar|não|eu|tu|ele|ela|nós|vocês|eles|elas|o|a|os|as|um|uma|[a-zà-ú]+(r|rmos|rem|sse|ssem|ssemos))\b)"
     r"(Me|Te|Se|Lhe|Nos) [a-zà-ú]+", "Pronomen am Satzanfang → Enklise (Chamo-me …)"),
    (r"\bequipe\b", "equipe → equipa"),
    (r"\btela\b", "tela → ecrã"),
    (r"\bfato\b(?! de banho)", "fato (BR = Tatsache) → facto"),
]

PFLICHT_LEKTION = ["id", "titel"]
UEBUNG_FELDER = {
    "auswahl": ["frage", "optionen", "richtig"],
    "luecke": ["satz", "loesungen"],
    "uebersetzen": ["de", "loesungen"],
    "satzbau": ["de", "loesung"],
    "diktat": ["pt"],
}


def _liste(wert) -> list:
    if not wert:
        return []
    return wert if isinstance(wert, list) else [wert]


def _portugiesische_texte(unit: dict):
    """Alle portugiesischen Sätze einer Einheit mit Fundort."""
    for v in unit.get("vokabeln", []):
        yield f"Vokabel {v.get('id')}", v.get("pt", "")
        yield f"Vokabel {v.get('id')} (Beispiel)", v.get("beispiel_pt", "")
        for a in v.get("alternativen", []):
            yield f"Vokabel {v.get('id')} (Alternative)", a
    for l in unit.get("lektionen", []):
        g = l.get("grammatik") or {}
        for b in g.get("beispiele", []):
            yield f"{l['id']} Beispiel", b.get("pt", "")
        for i, u in enumerate(g.get("uebungen", [])):
            for x in u.get("loesungen", []) + [u.get("loesung", ""), u.get("pt", ""), u.get("satz", "")]:
                yield f"{l['id']} Übung {i}", x
        for z in (l.get("hoeren") or {}).get("zeilen", []):
            yield f"{l['id']} Hören", z.get("pt", "")
        s = l.get("sprechen") or {}
        for z in s.get("saetze", []) + s.get("zeilen", []):
            yield f"{l['id']} Sprechen", z.get("pt", "")
            for x in z.get("loesungen", []):
                yield f"{l['id']} Sprechen", x
        for a in s.get("aufgaben", []):
            for x in a.get("loesungen", []):
                yield f"{l['id']} Schreiben", x
        for x in l.get("saetze", []):
            yield f"{l['id']} Satz {x.get('id')}", x.get("pt", "")
    test = unit.get("test") or {}
    for d in _liste(test.get("hoeren")):
        for z in d.get("zeilen", []):
            yield "Test Hören", z.get("pt", "")
    for txt in _liste(test.get("lesen")):
        for absatz in _liste(txt.get("text")):
            yield "Test Lesen", absatz
    for a in test.get("schreiben", []):
        for x in a.get("loesungen", []):
            yield "Test Schreiben", x
    for s in test.get("sprechen", []):
        yield "Test Sprechen", s.get("pt", "")


def pruefe_einheit(unit: dict) -> list[str]:
    probleme = []
    uid = unit.get("id", "?")
    for feld in ("id", "titel", "vokabeln", "lektionen"):
        if feld not in unit:
            probleme.append(f"{uid}: Feld '{feld}' fehlt")
    vokabel_ids = [v.get("id") for v in unit.get("vokabeln", [])]
    doppelt = {i for i in vokabel_ids if vokabel_ids.count(i) > 1}
    if doppelt:
        probleme.append(f"{uid}: doppelte Vokabel-IDs {sorted(doppelt)}")
    for v in unit.get("vokabeln", []):
        for feld in ("id", "pt", "de"):
            if not v.get(feld):
                probleme.append(f"{uid}: Vokabel {v.get('id')} ohne '{feld}'")

    typen = [l.get("typ", "neu") for l in unit.get("lektionen", [])]
    if ("test" in typen or "leveltest" in typen):
        test = unit.get("test") or {}
        for teil in ("hoeren", "lesen", "schreiben", "sprechen"):
            if not test.get(teil):
                probleme.append(f"{uid}: Abschnitt test.{teil} fehlt (wird für den Test gebraucht)")
        for d in _liste(test.get("hoeren")) + _liste(test.get("lesen")):
            for i, f in enumerate(d.get("fragen", [])):
                if not (0 <= f.get("richtig", -1) < len(f.get("optionen", []))):
                    probleme.append(f"{uid} Test „{d.get('titel')}“ Frage {i}: 'richtig' zeigt auf keine Option")

    for l in unit.get("lektionen", []):
        lid = l.get("id", "?")
        if not lid.startswith(uid + "-L"):
            probleme.append(f"{lid}: Lektions-ID muss mit '{uid}-L' beginnen")
        if l.get("typ", "neu") not in ("neu", "wiederholung", "test", "leveltest"):
            probleme.append(f"{lid}: unbekannter Lektionstyp '{l.get('typ')}'")
        if l.get("typ", "neu") == "neu":
            for teil in ("vokabeln", "grammatik", "hoeren", "sprechen"):
                if not l.get(teil):
                    probleme.append(f"{lid}: Teil '{teil}' fehlt")
        for vid in l.get("vokabeln", []):
            if vid not in vokabel_ids:
                probleme.append(f"{lid}: Vokabel '{vid}' ist in der Einheit nicht definiert")
        for i, u in enumerate((l.get("grammatik") or {}).get("uebungen", [])):
            felder = UEBUNG_FELDER.get(u.get("typ"))
            if felder is None:
                probleme.append(f"{lid} Übung {i}: unbekannter Typ '{u.get('typ')}'")
                continue
            for f in felder:
                if f not in u:
                    probleme.append(f"{lid} Übung {i}: Feld '{f}' fehlt")
            if u.get("typ") == "auswahl" and not (0 <= u.get("richtig", -1) < len(u.get("optionen", []))):
                probleme.append(f"{lid} Übung {i}: 'richtig' zeigt auf keine Option")
            if u.get("typ") == "luecke" and "___" not in u.get("satz", ""):
                probleme.append(f"{lid} Übung {i}: Lückensatz ohne ___")
        for i, f in enumerate((l.get("hoeren") or {}).get("fragen", [])):
            if not (0 <= f.get("richtig", -1) < len(f.get("optionen", []))):
                probleme.append(f"{lid} Hörfrage {i}: 'richtig' zeigt auf keine Option")
        s = l.get("sprechen")
        if s and s.get("typ") not in ("nachsprechen", "schreiben", "rollenspiel"):
            probleme.append(f"{lid}: unbekannter Sprechen-Typ '{s.get('typ')}'")

    for ort, text in _portugiesische_texte(unit):
        for muster, hinweis in BRASILIANISMEN:
            if text and re.search(muster, text):
                probleme.append(f"{uid} {ort}: „{text}“ – {hinweis}")
    return probleme


def _normal(pt: str) -> str:
    return pt.strip().lower().rstrip(".!?")


def doppelte_woerter(units: list[dict]) -> list[str]:
    """Wörter, die schon in einer früheren Einheit vorkommen (würden doppelte Karten erzeugen)."""
    gesehen, probleme = {}, []
    for unit in units:
        for v in unit.get("vokabeln", []):
            schluessel = _normal(v.get("pt", ""))
            if schluessel in gesehen and gesehen[schluessel] != unit["id"]:
                probleme.append(f"{unit['id']}: Vokabel „{v.get('pt')}“ gibt es schon in {gesehen[schluessel]}")
            gesehen.setdefault(schluessel, unit["id"])
    return probleme


def pruefe_alle() -> list[str]:
    content.reload()
    probleme = []
    lektions_ids = []
    units = content.load_units()
    for unit in units:
        probleme += pruefe_einheit(unit)
        lektions_ids += [l.get("id") for l in unit.get("lektionen", [])]
    doppelt = {i for i in lektions_ids if lektions_ids.count(i) > 1}
    if doppelt:
        probleme.append(f"Doppelte Lektions-IDs: {sorted(doppelt)}")
    probleme += doppelte_woerter(units)
    return probleme


def pruefe_dateien(pfade: list[str]) -> list[str]:
    """Nur die angegebenen Dateien prüfen (plus doppelte Wörter gegenüber allen anderen Einheiten)."""
    import json
    from pathlib import Path
    probleme, eigene = [], []
    for pfad in pfade:
        try:
            unit = json.loads(Path(pfad).read_text(encoding="utf-8"))
        except (OSError, ValueError) as e:
            probleme.append(f"{pfad}: kein gültiges JSON ({e})")
            continue
        unit.setdefault("level", Path(pfad).parent.name)
        probleme += pruefe_einheit(unit)
        eigene.append(unit)
    andere = []
    for level in content.LEVELS:
        for p in sorted((content.CONTENT_DIR / level).glob("*.json")):
            if any(Path(x).resolve() == p.resolve() for x in pfade):
                continue
            try:
                andere.append(json.loads(p.read_text(encoding="utf-8")))
            except ValueError:
                pass
    reihenfolge = sorted(andere + eigene, key=lambda u: (content.LEVELS.index(u.get("level", "A1")), u["id"]))
    ids = {u["id"] for u in eigene}
    probleme += [p for p in doppelte_woerter(reihenfolge) if p.split(":")[0] in ids]
    return probleme


if __name__ == "__main__":
    gefunden = pruefe_dateien(sys.argv[1:]) if len(sys.argv) > 1 else pruefe_alle()
    for p in gefunden:
        print("⚠️ ", p)
    print("✅ Alle Inhalte in Ordnung." if not gefunden else f"{len(gefunden)} Problem(e) gefunden.")
    sys.exit(1 if gefunden else 0)
