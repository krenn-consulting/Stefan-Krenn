"""Auswertungen für die Seiten "Fortschritt" und "Wortschatz"."""

import sqlite3
from datetime import date, datetime, timedelta

from . import content, db
from .pruefen import ohne_akzente

BLOCK_NAMEN = {
    "wiederholung": "Wiederholung",
    "wortschatz": "Wortschatz",
    "grammatik": "Grammatik",
    "hoeren": "Hören",
    "sprechen": "Sprechen & Schreiben",
    "lesen": "Lesen",
    "schreiben": "Schreiben",
}

SICHER_AB_TAGEN = 21   # ab diesem Abstand gilt eine Karte als "sicher"


def _status(karte: sqlite3.Row | dict | None) -> str:
    if karte is None or karte["state"] == "new":
        return "neu"
    if karte["state"] == "learning":
        return "lernend"
    if karte["interval_days"] >= SICHER_AB_TAGEN:
        return "sicher"
    return "gefestigt"


def _laengste_serie(tage: list[str]) -> int:
    beste, aktuell, vorher = 0, 0, None
    for t in sorted(tage):
        d = date.fromisoformat(t)
        aktuell = aktuell + 1 if vorher and (d - vorher).days == 1 else 1
        beste = max(beste, aktuell)
        vorher = d
    return beste


def fortschritt(con: sqlite3.Connection, heute: date | None = None) -> dict:
    heute = heute or date.today()
    seit30 = (heute - timedelta(days=29)).isoformat()

    # --- Wortschatz
    karten = con.execute("SELECT kind, state, interval_days FROM cards WHERE kind IN ('vocab', 'sentence')").fetchall()
    zaehl = {"neu": 0, "lernend": 0, "gefestigt": 0, "sicher": 0}
    woerter = saetze = 0
    for k in karten:
        s = _status(k)
        zaehl[s] += 1
        if s != "neu":
            woerter += k["kind"] == "vocab"
            saetze += k["kind"] == "sentence"

    # --- Genauigkeit (letzte 30 Tage), gesamt und je Block
    zeilen = con.execute("SELECT block, result FROM reviews WHERE ts >= ?", (seit30,)).fetchall()
    def anteil(liste):
        return round(sum(r["result"] in ("richtig", "fast") for r in liste) / len(liste), 3) if liste else None
    je_block = []
    for bid, name in BLOCK_NAMEN.items():
        teil = [z for z in zeilen if z["block"] == bid]
        if teil:
            je_block.append({"id": bid, "name": name, "anteil": anteil(teil), "anzahl": len(teil)})

    # --- Lernzeit: letzte 30 Tage und Kalender (16 Wochen)
    log = {r["day"]: r for r in con.execute("SELECT * FROM daily_log")}
    lernzeit = []
    for i in range(29, -1, -1):
        t = (heute - timedelta(days=i)).isoformat()
        lernzeit.append({"tag": t, "minuten": round((log[t]["seconds"] if t in log else 0) / 60)})
    start = heute - timedelta(days=heute.weekday() + 7 * 15)   # Montag vor 15 Wochen
    kalender = []
    d = start
    while d <= heute:
        t = d.isoformat()
        kalender.append({"tag": t, "minuten": round((log[t]["seconds"] if t in log else 0) / 60),
                         "lektionen": log[t]["lessons"] if t in log else 0})
        d += timedelta(days=1)
    gesamt_sek = sum(r["seconds"] for r in log.values())
    lerntage = [t for t, r in log.items() if r["seconds"] > 0 or r["lessons"] > 0]

    # --- Schwächen: offene Fehler nach Kategorie und die häufigsten Einzelfehler
    kategorien = [dict(r) for r in con.execute(
        """SELECT COALESCE(NULLIF(category, ''), 'Sonstiges') AS kategorie, COUNT(*) AS anzahl,
                  SUM(times_wrong) AS falsch FROM mistakes WHERE resolved = 0
           GROUP BY 1 ORDER BY falsch DESC LIMIT 8""")]
    einzelfehler = [dict(r) for r in con.execute(
        """SELECT prompt, expected, given, times_wrong FROM mistakes WHERE resolved = 0
           ORDER BY times_wrong DESC, ts DESC LIMIT 8""")]
    schwere_woerter = []
    for r in con.execute("""SELECT item_id, lapses FROM cards WHERE kind IN ('vocab', 'sentence')
                            AND lapses > 0 ORDER BY lapses DESC LIMIT 8"""):
        it = content.item(r["item_id"])
        if it:
            schwere_woerter.append({"pt": it["pt"], "de": it["de"], "vergessen": r["lapses"]})

    tests = [dict(r) for r in con.execute(
        "SELECT test_id, ts, skill, score, passed FROM tests ORDER BY ts DESC LIMIT 40")]
    for t in tests:
        l = content.lesson(t["test_id"])
        t["titel"] = f"{l['unit_titel']} – {l['titel']}" if l else t["test_id"]

    erledigt = {r["lesson_id"] for r in con.execute("SELECT lesson_id FROM lessons_done")}
    return {
        "wortschatz": {"woerter": woerter, "saetze": saetze, **zaehl},
        "genauigkeit": {"gesamt": anteil(zeilen), "anzahl": len(zeilen), "je_block": je_block},
        "lernzeit": {"tage": lernzeit, "gesamt_stunden": round(gesamt_sek / 3600, 1),
                     "schnitt_minuten_30": round(sum(t["minuten"] for t in lernzeit) / 30, 1)},
        "kalender": kalender,
        "serie": {"aktuell": db.streak(con, heute), "laengste": _laengste_serie(lerntage),
                  "lerntage": len(lerntage)},
        "schwaechen": {"kategorien": kategorien, "fehler": einzelfehler, "woerter": schwere_woerter},
        "tests": tests,
        "level": content.level_progress(erledigt),
    }


def wortschatz(con: sqlite3.Connection, suche: str = "", art: str = "alle") -> list[dict]:
    """Alle Wörter und Sätze, die schon in deiner Wiederholung sind."""
    genau = {r["item_id"]: (r["n"], r["gut"]) for r in con.execute(
        """SELECT item_id, COUNT(*) AS n, SUM(result IN ('richtig', 'fast')) AS gut
           FROM reviews WHERE item_id IS NOT NULL GROUP BY item_id""")}
    suche_n = ohne_akzente(suche.strip().lower())
    eintraege = []
    for k in con.execute("SELECT * FROM cards WHERE kind IN ('vocab', 'sentence') AND state != 'new' ORDER BY id"):
        if art == "woerter" and k["kind"] != "vocab":
            continue
        if art == "saetze" and k["kind"] != "sentence":
            continue
        it = content.item(k["item_id"])
        if it is None:
            continue
        if suche_n and suche_n not in ohne_akzente(f"{it['pt']} {it['de']}".lower()):
            continue
        n, gut = genau.get(k["item_id"], (0, 0))
        eintraege.append({
            "item_id": k["item_id"], "art": "Wort" if k["kind"] == "vocab" else "Satz",
            "pt": it["pt"], "de": it["de"], "emoji": it.get("emoji") or ("💬" if k["kind"] == "sentence" else ""),
            "beispiel_pt": it.get("beispiel_pt", ""), "beispiel_de": it.get("beispiel_de", ""),
            "hinweis": it.get("hinweis", ""), "einheit": it["unit_id"],
            "status": _status(k),
            "faellig": (k["due"] or "")[:10] if k["state"] != "new" else "",
            "genauigkeit": round(gut / n, 2) if n else None, "antworten": n,
        })
    eintraege.sort(key=lambda e: ohne_akzente(e["pt"].lower()))
    return eintraege
