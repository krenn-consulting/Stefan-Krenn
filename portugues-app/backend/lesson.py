"""Stellt die tägliche Lektion zusammen und verbucht die Antworten.

Eine Lektion besteht aus sechs Blöcken. Jeder Block ist eine Liste von
"Schritten" – ein Schritt ist genau ein Bildschirm (eine Erklärung, eine
neue Vokabel, eine Übung …). Die Oberfläche geht die Schritte einfach der
Reihe nach durch.

Schritt-Typen (Feld "typ"):
  info        Erklärung (Grammatik)
  vokabel     neue Vokabel oder neuer Satz vorstellen
  eingabe     Antwort tippen (art: de-pt | luecke | diktat | rolle)
  auswahl     Multiple Choice
  satzbau     Wörter in die richtige Reihenfolge bringen
  dialog      Hörtext
  nachsprechen  Satz hören und nachsprechen (Selbstbewertung)

Jeder beantwortbare Schritt hat "ref" = {item_id, kind, kategorie}. Damit
weiß der Server beim Antworten, welche Karte bzw. welcher Fehler gemeint ist.
"""

import json
import random
import sqlite3
from datetime import date, datetime

from . import content, db, srs

# Die sechs Blöcke mit ihrer Dauer bei einer 30-Minuten-Lektion
BLOECKE = [
    ("wiederholung", "Wiederholung", 5),
    ("wortschatz", "Neuer Wortschatz", 5),
    ("grammatik", "Grammatik", 7),
    ("hoeren", "Hören", 5),
    ("sprechen", "Sprechen & Schreiben", 5),
    ("abschluss", "Abschluss", 3),
]

MAX_WIEDERHOLUNGEN = 60     # mehr Karten passen ohnehin nicht in den Block
EINGESTREUTE_UEBUNGEN = 2   # Interleaving: alte Übungen im Grammatikblock
WIEDERHOLUNGSTAG_AB = 80    # so viele fällige Karten → Wiederholungstag empfehlen

KARTEN_ARTEN = ("vocab", "sentence", "mistake")


# ---------------------------------------------------------------------------
#  Welche Lektion ist dran?
# ---------------------------------------------------------------------------

def erledigte_lektionen(con: sqlite3.Connection) -> set[str]:
    return {r["lesson_id"] for r in con.execute("SELECT lesson_id FROM lessons_done")}


def naechste_lektion(con: sqlite3.Connection) -> dict | None:
    """Die erste noch nicht erledigte Lektion in Lernreihenfolge."""
    erledigt = erledigte_lektionen(con)
    for lid in content.lesson_order():
        if lid not in erledigt:
            l = content.lesson(lid)
            begonnen = con.execute("SELECT 1 FROM block_state WHERE lesson_id = ? LIMIT 1",
                                   (lid,)).fetchone() is not None
            return {"id": lid, "titel": l["titel"], "einheit": l["unit_titel"],
                    "level": l["level"], "begonnen": begonnen}
    return None


def heute_erledigt(con: sqlite3.Connection) -> int:
    heute = date.today().isoformat()
    return con.execute("SELECT COUNT(*) AS n FROM lessons_done WHERE finished_at >= ?",
                       (heute,)).fetchone()["n"]


# ---------------------------------------------------------------------------
#  Schritte aus Inhalten bauen
# ---------------------------------------------------------------------------

def _loesungen(item: dict) -> list[str]:
    return [item["pt"]] + item.get("alternativen", [])


def _vokabel_schritt(item_id: str, item: dict, neu_text: str = "Neues Wort") -> dict:
    return {
        "typ": "vokabel", "titel": neu_text, "item_id": item_id,
        "pt": item["pt"], "de": item["de"], "emoji": item.get("emoji", ""),
        "beispiel_pt": item.get("beispiel_pt", ""), "beispiel_de": item.get("beispiel_de", ""),
        "hinweis": item.get("hinweis", ""),
    }


def _de_pt_schritt(item_id: str, item: dict, kind: str) -> dict:
    return {
        "typ": "eingabe", "art": "de-pt",
        "anweisung": "Wie heißt das auf Portugiesisch?",
        "frage": item["de"], "emoji": item.get("emoji", ""),
        "loesungen": _loesungen(item), "audio": item["pt"],
        "ref": {"item_id": item_id, "kind": kind},
    }


def _diktat_schritt(item_id: str, item: dict, kind: str) -> dict:
    return {
        "typ": "eingabe", "art": "diktat",
        "anweisung": "Hör zu und schreib, was du hörst.",
        "audio": item["pt"], "loesungen": _loesungen(item),
        "uebersetzung": item["de"],
        "ref": {"item_id": item_id, "kind": kind},
    }


def _luecke_aus_satz(item_id: str, item: dict, kind: str, rng: random.Random) -> dict:
    """Ein Wort (mind. 3 Buchstaben) aus dem Satz wird zur Lücke."""
    woerter = item["pt"].split()
    kandidaten = [i for i, w in enumerate(woerter) if len(w.strip(".,!?–")) >= 3]
    if not kandidaten:
        return _de_pt_schritt(item_id, item, kind)
    i = rng.choice(kandidaten)
    wort = woerter[i].strip(".,!?–")
    luecke = woerter[i].replace(wort, "___")
    satz = " ".join(woerter[:i] + [luecke] + woerter[i + 1:])
    return {
        "typ": "eingabe", "art": "luecke",
        "anweisung": "Ergänze die Lücke.",
        "satz": satz, "de": item["de"], "loesungen": [wort], "audio": item["pt"],
        "ref": {"item_id": item_id, "kind": kind},
    }


def uebung_schritt(uebung: dict, ref: dict, rng: random.Random) -> dict:
    """Wandelt eine Übung aus der Inhaltsdatei in einen Schritt um."""
    typ = uebung["typ"]
    basis = {"erklaerung": uebung.get("erklaerung", ""), "ref": ref}
    if typ == "auswahl":
        return {**basis, "typ": "auswahl", "frage": uebung["frage"],
                "optionen": uebung["optionen"], "richtig": uebung["richtig"],
                "audio": uebung.get("audio", "")}
    if typ == "luecke":
        return {**basis, "typ": "eingabe", "art": "luecke", "anweisung": "Ergänze die Lücke.",
                "satz": uebung["satz"], "de": uebung.get("de", ""), "loesungen": uebung["loesungen"],
                "audio": uebung["satz"].replace("___", uebung["loesungen"][0])}
    if typ == "uebersetzen":
        return {**basis, "typ": "eingabe", "art": "de-pt",
                "anweisung": "Übersetze ins Portugiesische.",
                "frage": uebung["de"], "loesungen": uebung["loesungen"],
                "audio": uebung["loesungen"][0]}
    if typ == "satzbau":
        woerter = uebung.get("woerter") or uebung["loesung"].split()
        gemischt = woerter[:]
        while len(gemischt) > 1 and gemischt == woerter:
            rng.shuffle(gemischt)
        return {**basis, "typ": "satzbau", "anweisung": "Bring die Wörter in die richtige Reihenfolge.",
                "de": uebung["de"], "woerter": gemischt, "loesungen": [uebung["loesung"]],
                "audio": uebung["loesung"]}
    if typ == "diktat":
        return {**basis, "typ": "eingabe", "art": "diktat",
                "anweisung": "Hör zu und schreib, was du hörst.",
                "audio": uebung["pt"], "loesungen": uebung.get("loesungen", [uebung["pt"]]),
                "uebersetzung": uebung.get("de", "")}
    raise ValueError(f"Unbekannter Übungstyp: {typ}")


def _karten_schritt(card: sqlite3.Row, rng: random.Random) -> list[dict]:
    """Schritt(e) für eine fällige oder neue Karte im Wiederholungsblock."""
    item = content.item(card["item_id"])
    if item is None:          # Inhalt wurde gelöscht/umbenannt
        return []
    kind = card["kind"]
    if card["state"] == "new":
        # Neue Satzkarte: erst zeigen, dann abrufen
        return [_vokabel_schritt(card["item_id"], item, "Neuer Satz"),
                _de_pt_schritt(card["item_id"], item, kind)]
    if kind == "vocab":
        if card["reps"] < 2:
            return [_de_pt_schritt(card["item_id"], item, kind)]
        return [rng.choice([_de_pt_schritt, _de_pt_schritt, _diktat_schritt])(card["item_id"], item, kind)]
    # Sätze: abwechselnd Lücke, Übersetzen, Diktat
    wahl = rng.choice(["luecke", "de-pt", "diktat"])
    if wahl == "luecke":
        return [_luecke_aus_satz(card["item_id"], item, kind, rng)]
    if wahl == "diktat":
        return [_diktat_schritt(card["item_id"], item, kind)]
    return [_de_pt_schritt(card["item_id"], item, kind)]


def _fehler_schritt(con: sqlite3.Connection, card: sqlite3.Row) -> list[dict]:
    """Eine früher falsch beantwortete Übung noch einmal stellen."""
    basis_id = card["item_id"].removeprefix("fehler:")
    row = con.execute("SELECT payload FROM mistakes WHERE item_id = ?", (basis_id,)).fetchone()
    if not row or not row["payload"]:
        return []
    schritt = json.loads(row["payload"])
    schritt["ref"] = {**schritt.get("ref", {}), "item_id": card["item_id"], "kind": "mistake"}
    schritt["wiederholt"] = "Das war beim letzten Mal falsch – neuer Versuch!"
    return [schritt]


def wiederholung_schritte(con: sqlite3.Connection, now: datetime, rng: random.Random,
                          settings: dict) -> list[dict]:
    now_s = now.isoformat(timespec="seconds")
    faellig = con.execute(
        """SELECT * FROM cards WHERE state IN ('learning', 'review') AND due <= ?
           ORDER BY due LIMIT ?""", (now_s, MAX_WIEDERHOLUNGEN)).fetchall()

    # Neue Satzkarten – nur so viele, wie das Tageslimit erlaubt
    erlaubt = srs.neue_karten_erlaubt(settings["neue_karten_pro_tag"],
                                      heute_eingefuehrt(con, now), db.due_count(con, now_s))
    neue = con.execute("SELECT * FROM cards WHERE state = 'new' ORDER BY id LIMIT ?",
                       (erlaubt,)).fetchall() if erlaubt else []

    schritte = []
    karten = list(faellig)
    rng.shuffle(karten)   # gemischt statt nach Thema sortiert (Interleaving)
    for card in karten + list(neue):
        if card["kind"] == "mistake":
            schritte += _fehler_schritt(con, card)
        else:
            schritte += _karten_schritt(card, rng)
    return schritte


def heute_eingefuehrt(con: sqlite3.Connection, now: datetime) -> int:
    """Wie viele Karten wurden heute zum ersten Mal beantwortet?"""
    heute = now.date().isoformat()
    return con.execute(
        """SELECT COUNT(*) AS n FROM (SELECT card_id, MIN(ts) AS erste FROM reviews
           WHERE card_id IS NOT NULL GROUP BY card_id) WHERE erste >= ?""",
        (heute,)).fetchone()["n"]


def wortschatz_schritte(lesson: dict, rng: random.Random) -> list[dict]:
    """Erst jedes neue Wort vorstellen, dann alle aktiv abrufen (gemischt)."""
    vorstellen, abrufen = [], []
    for vid in lesson.get("vokabeln", []):
        item_id = content.vocab_item_id(lesson["unit_id"], vid)
        item = content.item(item_id)
        vorstellen.append(_vokabel_schritt(item_id, item))
        abrufen.append(_de_pt_schritt(item_id, item, "vocab"))
    rng.shuffle(abrufen)
    # In Dreiergruppen: 3 Wörter zeigen, dann diese 3 abfragen – das hält
    # die Wörter im Kopf, ohne zu überfordern.
    schritte = []
    for i in range(0, len(vorstellen), 3):
        gruppe = vorstellen[i:i + 3]
        schritte += gruppe
        ids = {s["item_id"] for s in gruppe}
        abruf = [s for s in abrufen if s["ref"]["item_id"] in ids]
        rng.shuffle(abruf)
        schritte += abruf
    return schritte


def grammatik_schritte(con: sqlite3.Connection, lesson: dict, rng: random.Random) -> list[dict]:
    g = lesson.get("grammatik")
    if not g:
        return []
    schritte = [{"typ": "info", "titel": g["titel"], "absaetze": g.get("erklaerung", []),
                 "vergleich": g.get("vergleich", ""), "beispiele": g.get("beispiele", [])}]
    for i, u in enumerate(g.get("uebungen", [])):
        ref = {"item_id": f"{lesson['id']}:g:{i}", "kind": "uebung", "kategorie": u.get("kategorie", "")}
        schritte.append(uebung_schritt(u, ref, rng))

    # Interleaving: Übungen aus früheren Lektionen einstreuen
    frueher = [lid for lid in erledigte_lektionen(con) if lid != lesson["id"] and content.lesson(lid)]
    pool = []
    for lid in frueher:
        alt = content.lesson(lid).get("grammatik") or {}
        for i, u in enumerate(alt.get("uebungen", [])):
            pool.append((lid, i, u))
    for lid, i, u in rng.sample(pool, min(EINGESTREUTE_UEBUNGEN, len(pool))):
        ref = {"item_id": f"{lid}:g:{i}", "kind": "uebung", "kategorie": u.get("kategorie", "")}
        s = uebung_schritt(u, ref, rng)
        s["wiederholt"] = f"Zur Wiederholung aus: {content.lesson(lid)['titel']}"
        # vor dem letzten Drittel einstreuen, nicht alles ans Ende
        schritte.insert(rng.randint(2, len(schritte)), s)
    return schritte


def hoeren_schritte(lesson: dict, rng: random.Random) -> list[dict]:
    h = lesson.get("hoeren")
    if not h:
        return []
    schritte = [{"typ": "dialog", "titel": h["titel"], "situation": h.get("situation", ""),
                 "zeilen": h["zeilen"]}]
    for i, f in enumerate(h.get("fragen", [])):
        schritte.append({"typ": "auswahl", "frage": f["frage"], "optionen": f["optionen"],
                         "richtig": f["richtig"], "erklaerung": f.get("erklaerung", ""),
                         "ref": {"item_id": f"{lesson['id']}:h:{i}", "kind": "hoeren"}})
    # Hören und Schreiben: eine kurze Zeile aus dem Dialog als Diktat
    kurz = [z for z in h["zeilen"] if 2 <= len(z["pt"].split()) <= 7]
    if kurz:
        z = rng.choice(kurz)
        schritte.append({"typ": "eingabe", "art": "diktat", "anweisung": "Diktat: Hör zu und schreib den Satz.",
                         "audio": z["pt"], "loesungen": [z["pt"]], "uebersetzung": z["de"],
                         "ref": {"item_id": f"{lesson['id']}:h:diktat", "kind": "hoeren"}})
    return schritte


def sprechen_schritte(lesson: dict) -> list[dict]:
    s = lesson.get("sprechen")
    if not s:
        return []
    lid = lesson["id"]
    if s["typ"] == "nachsprechen":
        return [{"typ": "nachsprechen", "anweisung": s.get("anweisung", "Hör zu und sprich nach."),
                 "pt": z["pt"], "de": z["de"],
                 "ref": {"item_id": f"{lid}:sp:{i}", "kind": "sprechen"}}
                for i, z in enumerate(s["saetze"])]
    if s["typ"] == "schreiben":
        return [{"typ": "eingabe", "art": "de-pt", "anweisung": s.get("anweisung", "Schreib auf Portugiesisch."),
                 "frage": a["de"], "loesungen": a["loesungen"], "audio": a["loesungen"][0],
                 "ref": {"item_id": f"{lid}:sp:{i}", "kind": "uebung"}}
                for i, a in enumerate(s["aufgaben"])]
    if s["typ"] == "rollenspiel":
        schritte, kontext = [], []
        for i, z in enumerate(s["zeilen"]):
            if z.get("ich"):
                schritte.append({"typ": "eingabe", "art": "rolle", "anweisung": "Rollenspiel – du bist dran.",
                                 "situation": s.get("situation", ""), "kontext": kontext,
                                 "frage": z["aufgabe"], "loesungen": z["loesungen"],
                                 "audio": z["loesungen"][0],
                                 "ref": {"item_id": f"{lid}:sp:{i}", "kind": "uebung"}})
                kontext = []
            else:
                kontext = kontext + [z]
        if kontext:   # Gesprächsende nach deiner letzten Antwort
            schritte.append({"typ": "dialog", "titel": "Ende des Gesprächs",
                             "situation": s.get("situation", ""), "zeilen": kontext})
        return schritte
    raise ValueError(f"Unbekannter Sprechen-Typ: {s['typ']}")


# ---------------------------------------------------------------------------
#  Die ganze Lektion
# ---------------------------------------------------------------------------

def _block_minuten(settings: dict) -> dict:
    faktor = settings["lektionsdauer_min"] / 30
    return {bid: round(min * faktor, 1) for bid, _, min in BLOECKE}


def _block_status(con: sqlite3.Connection, lesson_id: str) -> dict:
    return {r["block"]: r["status"] for r in
            con.execute("SELECT block, status FROM block_state WHERE lesson_id = ?", (lesson_id,))}


def plan(con: sqlite3.Connection, lesson_id: str | None = None, modus: str = "lektion",
         now: datetime | None = None, rng: random.Random | None = None) -> dict | None:
    """Stellt die Lektion zusammen. modus: "lektion" oder "wiederholung"."""
    now = now or datetime.now()
    rng = rng or random.Random()
    settings = db.get_settings(con)
    minuten = _block_minuten(settings)

    if modus == "wiederholung":
        # Wiederholungstag: fast die ganze Zeit für fällige Karten
        lid = f"WH-{now.date().isoformat()}"
        status = _block_status(con, lid)
        gesamt = settings["lektionsdauer_min"]
        return {
            "id": lid, "modus": "wiederholung", "titel": "Wiederholungstag",
            "einheit": "Fällige Karten und Fehler", "level": "",
            "bloecke": [
                {"id": "wiederholung", "titel": "Wiederholung", "minuten": round(gesamt * 0.9, 1),
                 "status": status.get("wiederholung"),
                 "schritte": wiederholung_schritte(con, now, rng, settings)},
                {"id": "abschluss", "titel": "Abschluss", "minuten": round(gesamt * 0.1, 1),
                 "status": status.get("abschluss"), "schritte": []},
            ],
        }

    if lesson_id is None:
        naechste = naechste_lektion(con)
        if naechste is None:
            return None
        lesson_id = naechste["id"]
    lesson = content.lesson(lesson_id)
    if lesson is None:
        return None

    status = _block_status(con, lesson_id)
    schritte = {
        "wiederholung": wiederholung_schritte(con, now, rng, settings),
        "wortschatz": wortschatz_schritte(lesson, rng),
        "grammatik": grammatik_schritte(con, lesson, rng),
        "hoeren": hoeren_schritte(lesson, rng),
        "sprechen": sprechen_schritte(lesson),
        "abschluss": [],
    }
    return {
        "id": lesson_id, "modus": "lektion", "titel": lesson["titel"],
        "einheit": lesson["unit_titel"], "level": lesson["level"],
        "bloecke": [{"id": bid, "titel": titel, "minuten": minuten[bid],
                     "status": status.get(bid), "schritte": schritte[bid]}
                    for bid, titel, _ in BLOECKE],
    }


# ---------------------------------------------------------------------------
#  Antworten und Fortschritt verbuchen
# ---------------------------------------------------------------------------

def _karte_holen_oder_anlegen(con: sqlite3.Connection, item_id: str, kind: str,
                              now_s: str) -> sqlite3.Row:
    row = con.execute("SELECT * FROM cards WHERE item_id = ?", (item_id,)).fetchone()
    if row is None:
        unit_id = item_id.removeprefix("fehler:").split(":")[0]
        unit_id = unit_id.split("-L")[0]   # "A1-01-L01" → "A1-01"
        con.execute("INSERT INTO cards(item_id, kind, unit_id, created_at) VALUES (?, ?, ?, ?)",
                    (item_id, kind, unit_id, now_s))
        row = con.execute("SELECT * FROM cards WHERE item_id = ?", (item_id,)).fetchone()
    return row


def antwort_verbuchen(con: sqlite3.Connection, daten: dict, now: datetime | None = None) -> dict:
    """Speichert eine Antwort: Karte planen, Statistik, Fehlerspeicher.

    daten: lesson_id, block, ergebnis, antwort, schritt (der ganze Schritt)
    """
    now = now or datetime.now()
    now_s = now.isoformat(timespec="seconds")
    ergebnis = daten["ergebnis"]
    schritt = daten.get("schritt") or {}
    ref = schritt.get("ref") or {}
    item_id, kind = ref.get("item_id"), ref.get("kind")
    if not item_id or not kind:
        raise ValueError("Schritt ohne Referenz")

    card_id, karte = None, None
    if kind in KARTEN_ARTEN:
        row = _karte_holen_oder_anlegen(con, item_id, kind, now_s)
        neu = srs.schedule(dict(row), ergebnis, now)
        con.execute(
            """UPDATE cards SET state=?, step=?, ease=?, interval_days=?, due=?, reps=?,
               lapses=?, last_review=? WHERE id=?""",
            (neu["state"], neu["step"], neu["ease"], neu["interval_days"], neu["due"],
             neu["reps"], neu["lapses"], neu["last_review"], row["id"]))
        card_id = row["id"]
        karte = {k: neu[k] for k in ("state", "due", "interval_days")}

    con.execute(
        """INSERT INTO reviews(card_id, item_id, lesson_id, block, ts, exercise, result, answer, duration_ms)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (card_id, item_id, daten.get("lesson_id"), daten.get("block"), now_s,
         schritt.get("art") or schritt.get("typ", ""), ergebnis, daten.get("antwort"),
         daten.get("dauer_ms")))

    _fehler_merken(con, item_id, kind, ergebnis, schritt, daten.get("antwort"), now_s)
    if card_id is not None:
        db.add_study_time(con, cards=1, day=now.date().isoformat())
    con.commit()
    return {"ok": True, "karte": karte}


def _kategorie(schritt: dict, kind: str) -> str:
    """Kategorie für die Fehleranalyse (Seite Fortschritt → Schwächen)."""
    k = (schritt.get("ref") or {}).get("kategorie")
    if k:
        return k
    if schritt.get("art") == "diktat":
        return "Hören & Schreiben (Diktat)"
    return {"vocab": "Wortschatz", "sentence": "Satzmuster", "hoeren": "Hörverstehen",
            "uebung": "Grammatik & Ausdruck"}.get(kind, "Sonstiges")


def _fehler_merken(con, item_id, kind, ergebnis, schritt, antwort, now_s) -> None:
    """Fehlerspeicher pflegen. Falsch beantwortete Übungen kommen als Karte wieder."""
    if kind == "sprechen":       # Selbstbewertung – kein Fehler im engeren Sinn
        return
    basis_id = item_id.removeprefix("fehler:")
    if ergebnis == "falsch":
        loesung = (schritt.get("loesungen") or [""])[0]
        if schritt.get("typ") == "auswahl":
            loesung = schritt["optionen"][schritt["richtig"]]
        if schritt.get("art") == "diktat":
            frage = "🎧 Diktat" + (f" („{schritt['uebersetzung']}“)" if schritt.get("uebersetzung") else "")
        else:
            frage = schritt.get("frage") or schritt.get("satz") or schritt.get("de") or ""
        payload = json.dumps({k: v for k, v in schritt.items() if k != "wiederholt"}, ensure_ascii=False)
        con.execute(
            """INSERT INTO mistakes(item_id, category, prompt, given, expected, explanation, ts, payload)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(item_id) DO UPDATE SET times_wrong = times_wrong + 1, streak = 0,
                   resolved = 0, given = excluded.given, ts = excluded.ts""",
            (basis_id, _kategorie(schritt, kind), frage, antwort, loesung,
             schritt.get("erklaerung", ""), now_s, payload))
        # Übungen haben keine eigene Karte → eine Fehler-Karte anlegen bzw. reaktivieren
        if kind in ("uebung", "hoeren"):
            fehler_id = "fehler:" + basis_id
            karte = _karte_holen_oder_anlegen(con, fehler_id, "mistake", now_s)
            con.execute("UPDATE cards SET state='learning', step=0, due=? WHERE id=?",
                        (now_s, karte["id"]))
    else:
        row = con.execute("SELECT streak FROM mistakes WHERE item_id = ? AND resolved = 0",
                          (basis_id,)).fetchone()
        if row:
            streak = row["streak"] + 1
            con.execute("UPDATE mistakes SET streak = ?, resolved = ? WHERE item_id = ?",
                        (streak, 1 if streak >= 2 else 0, basis_id))
            if streak >= 2:   # behoben → Fehler-Karte ruht
                con.execute("UPDATE cards SET state='erledigt' WHERE item_id = ?",
                            ("fehler:" + basis_id,))


def block_speichern(con: sqlite3.Connection, lesson_id: str, block: str, status: str,
                    sekunden: int = 0) -> None:
    if status not in ("fertig", "uebersprungen"):
        raise ValueError("Status muss 'fertig' oder 'uebersprungen' sein")
    con.execute(
        """INSERT INTO block_state(lesson_id, block, status, updated_at) VALUES (?, ?, ?, ?)
           ON CONFLICT(lesson_id, block) DO UPDATE SET status = excluded.status,
               updated_at = excluded.updated_at""",
        (lesson_id, block, status, db.now_iso()))
    if sekunden:
        db.add_study_time(con, seconds=int(min(sekunden, 3600)))
    con.commit()


def lektion_abschliessen(con: sqlite3.Connection, lesson_id: str, selbsteinschaetzung: int | None,
                         now: datetime | None = None) -> dict:
    """Lektion als erledigt speichern, Satzkarten für später anlegen, Ergebnis berechnen."""
    now = now or datetime.now()
    now_s = now.isoformat(timespec="seconds")
    zeilen = con.execute("SELECT result, block FROM reviews WHERE lesson_id = ?", (lesson_id,)).fetchall()
    gesamt = len(zeilen)
    gut = sum(1 for z in zeilen if z["result"] in ("richtig", "fast"))
    score = round(gut / gesamt, 3) if gesamt else None

    bereits = con.execute("SELECT 1 FROM lessons_done WHERE lesson_id = ?", (lesson_id,)).fetchone()
    con.execute(
        """INSERT INTO lessons_done(lesson_id, finished_at, score, self_rating) VALUES (?, ?, ?, ?)
           ON CONFLICT(lesson_id) DO UPDATE SET finished_at = excluded.finished_at,
               score = excluded.score, self_rating = excluded.self_rating""",
        (lesson_id, now_s, score, selbsteinschaetzung))

    # Satzmuster der Lektion kommen als neue Karten in die Wiederholung
    lesson = content.lesson(lesson_id)
    neue_saetze = 0
    if lesson:
        for s in lesson.get("saetze", []):
            item_id = content.sentence_item_id(lesson["unit_id"], s["id"])
            cur = con.execute(
                "INSERT OR IGNORE INTO cards(item_id, kind, unit_id, created_at) VALUES (?, 'sentence', ?, ?)",
                (item_id, lesson["unit_id"], now_s))
            neue_saetze += cur.rowcount
    if not bereits:
        db.add_study_time(con, lessons=1, day=now.date().isoformat())
    con.commit()

    # Zusammenfassung je Block
    je_block = {}
    for z in zeilen:
        b = je_block.setdefault(z["block"] or "?", {"gesamt": 0, "gut": 0})
        b["gesamt"] += 1
        b["gut"] += z["result"] in ("richtig", "fast")
    return {"score": score, "gesamt": gesamt, "gut": gut, "je_block": je_block,
            "neue_saetze": neue_saetze}


def zusammenfassung(con: sqlite3.Connection, lesson_id: str) -> dict:
    """Für den Abschluss-Bildschirm: Ergebnis bisher und neu gelernte Wörter."""
    zeilen = con.execute("SELECT result, block FROM reviews WHERE lesson_id = ?", (lesson_id,)).fetchall()
    gesamt = len(zeilen)
    gut = sum(1 for z in zeilen if z["result"] in ("richtig", "fast"))
    lesson = content.lesson(lesson_id)
    woerter = []
    if lesson:
        for vid in lesson.get("vokabeln", []):
            it = content.item(content.vocab_item_id(lesson["unit_id"], vid))
            woerter.append({"pt": it["pt"], "de": it["de"], "emoji": it.get("emoji", "")})
    fehler = con.execute(
        """SELECT prompt, expected, given FROM mistakes WHERE resolved = 0 AND item_id IN
           (SELECT REPLACE(item_id, 'fehler:', '') FROM reviews
            WHERE lesson_id = ? AND result = 'falsch')
           LIMIT 5""", (lesson_id,)).fetchall()
    return {"gesamt": gesamt, "gut": gut,
            "anteil": round(gut / gesamt, 3) if gesamt else None,
            "woerter": woerter, "fehler": [dict(f) for f in fehler]}
