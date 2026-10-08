"""Wiederholungslektionen, Einheitentests und Level-Tests.

Diese Lektionen werden größtenteils automatisch aus den Inhalten der Einheit
zusammengestellt. Für Tests liefert jede Einheit in ihrer JSON-Datei einen
Abschnitt "test" mit neuem Hörtext, Lesetext, Schreib- und Sprechaufgaben.

Lektionstypen (Feld "typ" in der Inhaltsdatei):
  neu           normale Lektion (lesson.py)
  wiederholung  Wiederholung der ganzen Einheit, Schwerpunkt auf Schwächen
  test          Einheitentest – bestanden ab 80 %
  leveltest     Level-Test, optional nur einzelne Bereiche ("bloecke")
"""

import random
import sqlite3
from datetime import datetime, timedelta

from . import content, db
from .lesson import (_de_pt_schritt, _diktat_schritt, _karte_holen_oder_anlegen, _block_status,
                     sprechen_schritte, uebung_schritt, wiederholung_schritte)

BESTANDEN_AB = 0.8

# Blöcke eines Tests mit Dauer (Minuten bei 30-Minuten-Lektion)
TEST_BLOECKE = [
    ("hoeren", "Hören", 7),
    ("lesen", "Lesen", 6),
    ("grammatik", "Wortschatz & Grammatik", 7),
    ("schreiben", "Schreiben", 5),
    ("sprechen", "Sprechen", 4),
    ("abschluss", "Ergebnis", 1),
]

WIEDERHOLUNG_BLOECKE = [
    ("wiederholung", "Fällige Karten", 6),
    ("wortschatz", "Wortschatz festigen", 6),
    ("grammatik", "Grammatik gemischt", 7),
    ("hoeren", "Hören", 5),
    ("sprechen", "Sprechen & Schreiben", 4),
    ("abschluss", "Abschluss", 2),
]


def _als_liste(wert) -> list:
    if not wert:
        return []
    return wert if isinstance(wert, list) else [wert]


def _neue_lektionen(unit: dict) -> list[dict]:
    return [l for l in unit.get("lektionen", []) if l.get("typ", "neu") == "neu"]


def _uebungs_pool(units: list[dict]) -> list[tuple[str, int, dict]]:
    """Alle Grammatikübungen der Einheiten: (lesson_id, index, übung)."""
    pool = []
    for u in units:
        for l in _neue_lektionen(u):
            for i, ueb in enumerate((l.get("grammatik") or {}).get("uebungen", [])):
                pool.append((l["id"], i, ueb))
    return pool


def _grammatik_aus_pool(pool, anzahl: int, rng: random.Random, hinweis: bool = False) -> list[dict]:
    schritte = []
    for lid, i, u in rng.sample(pool, min(anzahl, len(pool))):
        ref = {"item_id": f"{lid}:g:{i}", "kind": "uebung", "kategorie": u.get("kategorie", "")}
        s = uebung_schritt(u, ref, rng)
        if hinweis:
            s["wiederholt"] = f"Aus: {content.lesson(lid)['titel']}"
        schritte.append(s)
    return schritte


def _vokabel_ids(units: list[dict]) -> list[str]:
    """Aktiv zu lernende Wörter (passive Wörter werden nicht abgefragt)."""
    return [content.vocab_item_id(u["id"], v["id"]) for u in units for v in u.get("vokabeln", [])
            if not v.get("passiv")]


def _hoer_schritte(dialog: dict, ref_basis: str, rng: random.Random, diktate: int = 1) -> list[dict]:
    schritte = [{"typ": "dialog", "titel": dialog["titel"], "situation": dialog.get("situation", ""),
                 "zeilen": dialog["zeilen"]}]
    for i, f in enumerate(dialog.get("fragen", [])):
        schritte.append({"typ": "auswahl", "frage": f["frage"], "optionen": f["optionen"],
                         "richtig": f["richtig"], "erklaerung": f.get("erklaerung", ""),
                         "ref": {"item_id": f"{ref_basis}:{i}", "kind": "hoeren"}})
    kurz = [z for z in dialog["zeilen"] if 2 <= len(z["pt"].split()) <= 8]
    for j, z in enumerate(rng.sample(kurz, min(diktate, len(kurz)))):
        schritte.append({"typ": "eingabe", "art": "diktat", "anweisung": "Diktat: Hör zu und schreib den Satz.",
                         "audio": z["pt"], "loesungen": [z["pt"]], "uebersetzung": z["de"],
                         "ref": {"item_id": f"{ref_basis}:d{j}", "kind": "hoeren"}})
    return schritte


def _lese_schritte(text: dict, ref_basis: str) -> list[dict]:
    schritte = [{"typ": "lesen", "titel": text["titel"], "situation": text.get("situation", ""),
                 "absaetze": _als_liste(text["text"])}]
    for i, f in enumerate(text.get("fragen", [])):
        schritte.append({"typ": "auswahl", "frage": f["frage"], "optionen": f["optionen"],
                         "richtig": f["richtig"], "erklaerung": f.get("erklaerung", ""),
                         "ref": {"item_id": f"{ref_basis}:{i}", "kind": "uebung", "kategorie": "Leseverstehen"}})
    return schritte


def _minuten(bloecke, settings) -> dict:
    faktor = settings["lektionsdauer_min"] / 30
    return {bid: round(m * faktor, 1) for bid, _, m in bloecke}


# ---------------------------------------------------------------------------
#  Wiederholungslektion der Einheit
# ---------------------------------------------------------------------------

def wiederholungslektion(con: sqlite3.Connection, lesson: dict, now: datetime, rng: random.Random,
                         settings: dict) -> list[dict]:
    unit = content.unit(lesson["unit_id"])

    # Wortschatz festigen: zuerst die Wörter, die am häufigsten vergessen wurden
    ids = _vokabel_ids([unit])
    gewicht = {r["item_id"]: (r["lapses"], -r["ease"]) for r in con.execute(
        f"SELECT item_id, lapses, ease FROM cards WHERE item_id IN ({','.join('?' * len(ids))})", ids)} if ids else {}
    rng.shuffle(ids)
    ids.sort(key=lambda i: gewicht.get(i, (0, 0)), reverse=True)
    wortschatz = []
    for n, item_id in enumerate(ids[:12]):
        it = content.item(item_id)
        f = _diktat_schritt if n % 3 == 2 else _de_pt_schritt
        wortschatz.append(f(item_id, it, "vocab"))

    # Hören: ein Dialog aus der Einheit, Sprechen: eine Sprechaufgabe der Einheit
    neue = _neue_lektionen(unit)
    mit_dialog = [l for l in neue if l.get("hoeren")]
    hoeren = []
    if mit_dialog:
        l = rng.choice(mit_dialog)
        hoeren = _hoer_schritte(l["hoeren"], f"{l['id']}:h", rng, diktate=2)
    mit_sprechen = [l for l in neue if l.get("sprechen")]
    sprechen = sprechen_schritte(rng.choice(mit_sprechen)) if mit_sprechen else []

    return {
        "wiederholung": wiederholung_schritte(con, now, rng, settings),
        "wortschatz": wortschatz,
        "grammatik": _grammatik_aus_pool(_uebungs_pool([unit]), 10, rng, hinweis=True),
        "hoeren": hoeren,
        "sprechen": sprechen,
        "abschluss": [],
    }


# ---------------------------------------------------------------------------
#  Tests
# ---------------------------------------------------------------------------

def test_schritte(lesson: dict, rng: random.Random) -> dict:
    """Schritte für Einheitentest oder Level-Test."""
    unit = content.unit(lesson["unit_id"])
    test = unit.get("test") or {}
    lid = lesson["id"]
    if lesson.get("typ") == "leveltest":
        quellen = [u for u in content.units_in_level(unit["level"]) if u["id"] != unit["id"]]
        n_vok, n_gram = 10, 12
    else:
        quellen = [unit]
        n_vok, n_gram = 6, 8

    hoeren = []
    for j, d in enumerate(_als_liste(test.get("hoeren"))):
        hoeren += _hoer_schritte(d, f"{lid}:t:h{j}", rng, diktate=2 if j == 0 else 1)
    lesen = []
    for j, t in enumerate(_als_liste(test.get("lesen"))):
        lesen += _lese_schritte(t, f"{lid}:t:l{j}")

    vokabeln = _vokabel_ids(quellen)
    grammatik = [_de_pt_schritt(i, content.item(i), "vocab") for i in rng.sample(vokabeln, min(n_vok, len(vokabeln)))]
    grammatik += _grammatik_aus_pool(_uebungs_pool(quellen), n_gram, rng)
    rng.shuffle(grammatik)

    schreiben = [{"typ": "eingabe", "art": "de-pt", "anweisung": "Schreib auf Portugiesisch.",
                  "frage": a["de"], "loesungen": a["loesungen"], "audio": a["loesungen"][0],
                  "ref": {"item_id": f"{lid}:t:s:{i}", "kind": "uebung", "kategorie": "Schreiben"}}
                 for i, a in enumerate(test.get("schreiben", []))]
    sprechen = [{"typ": "nachsprechen", "anweisung": "Lies den Satz laut vor – oder sprich ihn nach dem Hören nach.",
                 "pt": s["pt"], "de": s["de"], "ref": {"item_id": f"{lid}:t:sp:{i}", "kind": "sprechen"}}
                for i, s in enumerate(test.get("sprechen", []))]
    return {"hoeren": hoeren, "lesen": lesen, "grammatik": grammatik,
            "schreiben": schreiben, "sprechen": sprechen, "abschluss": []}


def test_bloecke(lesson: dict) -> list[tuple[str, str, int]]:
    gewuenscht = lesson.get("bloecke")
    bloecke = [b for b in TEST_BLOECKE if not gewuenscht or b[0] in gewuenscht or b[0] == "abschluss"]
    return bloecke


def versuch_starten(con: sqlite3.Connection, lesson_id: str, now: datetime) -> str:
    con.execute("INSERT OR IGNORE INTO test_versuche(lesson_id, start) VALUES (?, ?)",
                (lesson_id, now.isoformat(timespec="seconds")))
    con.commit()
    return con.execute("SELECT start FROM test_versuche WHERE lesson_id = ?", (lesson_id,)).fetchone()["start"]


def plan(con: sqlite3.Connection, lesson: dict, now: datetime, rng: random.Random, settings: dict) -> dict:
    """Plan für Lektionen vom Typ wiederholung, test oder leveltest."""
    typ = lesson.get("typ")
    status = _block_status(con, lesson["id"])
    extra = {}
    if typ == "wiederholung":
        bloecke = WIEDERHOLUNG_BLOECKE
        schritte = wiederholungslektion(con, lesson, now, rng, settings)
    else:
        bloecke = test_bloecke(lesson)
        schritte = test_schritte(lesson, rng)
        extra = {"versuch_start": versuch_starten(con, lesson["id"], now), "bestanden_ab": BESTANDEN_AB}
    minuten = _minuten(bloecke, settings)
    return {
        "id": lesson["id"], "modus": "lektion", "typ": typ, "titel": lesson["titel"],
        "einheit": lesson["unit_titel"], "level": lesson["level"], **extra,
        "bloecke": [{"id": bid, "titel": titel, "minuten": minuten[bid], "status": status.get(bid),
                     "schritte": schritte[bid]} for bid, titel, _ in bloecke],
    }


def test_auswerten(con: sqlite3.Connection, lesson: dict, now: datetime) -> dict:
    """Wertet den laufenden Testversuch aus, speichert das Ergebnis und räumt auf."""
    lid = lesson["id"]
    now_s = now.isoformat(timespec="seconds")
    row = con.execute("SELECT start FROM test_versuche WHERE lesson_id = ?", (lid,)).fetchone()
    start = row["start"] if row else "0000"
    zeilen = con.execute("SELECT block, result FROM reviews WHERE lesson_id = ? AND ts >= ?",
                         (lid, start)).fetchall()

    bereiche = []
    for bid, titel, _ in test_bloecke(lesson):
        if bid == "abschluss":
            continue
        teil = [z for z in zeilen if z["block"] == bid]
        anteil = round(sum(z["result"] in ("richtig", "fast") for z in teil) / len(teil), 3) if teil else 0.0
        bereiche.append({"id": bid, "titel": titel, "anteil": anteil, "anzahl": len(teil)})
    gesamt = round(sum(b["anteil"] for b in bereiche) / len(bereiche), 3) if bereiche else 0.0
    bestanden = gesamt >= BESTANDEN_AB

    for b in bereiche + [{"id": "gesamt", "anteil": gesamt}]:
        con.execute("INSERT INTO tests(test_id, ts, skill, score, passed) VALUES (?, ?, ?, ?, ?)",
                    (lid, now_s, b["id"], b["anteil"], int(b["anteil"] >= BESTANDEN_AB)))

    uebersprungen = 0
    if bestanden:
        con.execute("""INSERT INTO lessons_done(lesson_id, finished_at, score) VALUES (?, ?, ?)
                       ON CONFLICT(lesson_id) DO UPDATE SET finished_at = excluded.finished_at,
                           score = excluded.score""", (lid, now_s, gesamt))
        if lesson.get("typ") == "test":
            uebersprungen = _einheit_als_erledigt(con, lesson, now)
        db.add_study_time(con, lessons=1, day=now.date().isoformat())

    # Nächster Versuch beginnt frisch
    con.execute("DELETE FROM test_versuche WHERE lesson_id = ?", (lid,))
    con.execute("DELETE FROM block_state WHERE lesson_id = ?", (lid,))
    con.commit()

    schwach = [b for b in bereiche if b["anteil"] < BESTANDEN_AB]
    unit = content.unit(lesson["unit_id"])
    wdh = next((l["id"] for l in unit.get("lektionen", []) if l.get("typ") == "wiederholung"), None)
    return {"test": {"gesamt": gesamt, "bestanden": bestanden, "bestanden_ab": BESTANDEN_AB,
                     "bereiche": bereiche, "schwach": [b["titel"] for b in schwach],
                     "uebersprungene_lektionen": uebersprungen, "wiederholung_id": wdh},
            "score": gesamt, "gesamt": len(zeilen),
            "gut": sum(z["result"] in ("richtig", "fast") for z in zeilen), "neue_saetze": 0}


def _einheit_als_erledigt(con: sqlite3.Connection, test_lesson: dict, now: datetime) -> int:
    """Test bestanden: noch offene Lektionen der Einheit gelten als erledigt.

    Wer den Test vorzieht und besteht, überspringt die Einheit. Damit die
    Wörter trotzdem gelegentlich wiederkommen, landen sie als Karten mit
    3 Tagen Abstand in der Wiederholung.
    """
    now_s = now.isoformat(timespec="seconds")
    unit = content.unit(test_lesson["unit_id"])
    neu_erledigt = 0
    for l in unit.get("lektionen", []):
        if l["id"] != test_lesson["id"]:
            cur = con.execute("INSERT OR IGNORE INTO lessons_done(lesson_id, finished_at) VALUES (?, ?)",
                              (l["id"], now_s))
            neu_erledigt += cur.rowcount
        for s in l.get("saetze", []):
            con.execute("INSERT OR IGNORE INTO cards(item_id, kind, unit_id, created_at) VALUES (?, 'sentence', ?, ?)",
                        (content.sentence_item_id(unit["id"], s["id"]), unit["id"], now_s))
    faellig = (now + timedelta(days=3)).replace(hour=0, minute=0, second=0).isoformat(timespec="seconds")
    for item_id in _vokabel_ids([unit]):
        karte = _karte_holen_oder_anlegen(con, item_id, "vocab", now_s)
        if karte["state"] == "new":
            con.execute("UPDATE cards SET state='review', interval_days=3, due=?, reps=1 WHERE id=?",
                        (faellig, karte["id"]))
    return neu_erledigt
