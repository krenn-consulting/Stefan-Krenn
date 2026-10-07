"""Wiederholungssystem (Spaced Repetition), angelehnt an SM-2.

So funktioniert es, in einfachen Worten:

* Neue Karten durchlaufen zuerst kurze Lernstufen (1 Min., 10 Min.).
  Wer alle Stufen richtig beantwortet, "besteht" die Karte: Sie kommt
  morgen wieder.
* Danach wächst der Abstand mit jeder richtigen Antwort um den
  Leichtigkeitsfaktor (anfangs 2,5): 1 Tag → 3 Tage → 7 Tage → 18 Tage …
* "Fast richtig" (z. B. Akzent vergessen) lässt den Abstand nur wenig
  wachsen und macht die Karte etwas "schwerer".
* Bei einer falschen Antwort wird die Karte neu gelernt – der bisherige
  Abstand wird aber nur halbiert und nicht ganz verworfen. So kostet ein
  Ausrutscher bei einer gut bekannten Karte nicht wochenlange Arbeit.

Bewertet wird automatisch aus der Antwort: richtig | fast | falsch.
"""

from datetime import datetime, timedelta

LERNSTUFEN_MIN = [1, 10]      # Abstände der Lernstufen in Minuten
START_LEICHTIGKEIT = 2.5
MIN_LEICHTIGKEIT = 1.3
MAX_INTERVALL_TAGE = 365

RICHTIG, FAST, FALSCH = "richtig", "fast", "falsch"


def _tagesbeginn_plus(now: datetime, tage: float) -> datetime:
    """Fälligkeit für Wiederholkarten: Beginn des Zieltages.

    So ist eine Karte mit Abstand 1 Tag morgen den ganzen Tag fällig – egal,
    ob du morgens oder abends lernst.
    """
    ziel = now + timedelta(days=round(tage))
    return ziel.replace(hour=0, minute=0, second=0, microsecond=0)


def schedule(card: dict, ergebnis: str, now: datetime) -> dict:
    """Berechnet den neuen Zustand einer Karte nach einer Antwort.

    `card` enthält state, step, ease, interval_days, reps, lapses.
    Gibt ein neues Dictionary zurück (die Eingabe bleibt unverändert).
    """
    if ergebnis not in (RICHTIG, FAST, FALSCH):
        raise ValueError(f"Unbekanntes Ergebnis: {ergebnis}")

    c = dict(card)
    c["reps"] = c.get("reps", 0) + 1
    c["last_review"] = now.isoformat(timespec="seconds")
    ease = c.get("ease") or START_LEICHTIGKEIT
    intervall = c.get("interval_days") or 0

    if c.get("state", "new") in ("new", "learning"):
        # --- Lernphase (neu oder nach einem Fehler neu lernen) ---
        step = c.get("step", 0)
        if ergebnis == FALSCH:
            step = 0
        elif ergebnis == RICHTIG:
            step += 1
        # FAST: Stufe wiederholen

        if step >= len(LERNSTUFEN_MIN):
            # Bestanden → ab jetzt in Tagen. Nach einem Fehler gilt der
            # (halbierte) alte Abstand, mindestens aber 1 Tag.
            c["state"] = "review"
            c["step"] = 0
            c["interval_days"] = max(1.0, intervall)
            c["due"] = _tagesbeginn_plus(now, c["interval_days"]).isoformat(timespec="seconds")
        else:
            c["state"] = "learning"
            c["step"] = step
            c["due"] = (now + timedelta(minutes=LERNSTUFEN_MIN[step])).isoformat(timespec="seconds")
        c["ease"] = ease
        return c

    # --- Wiederholphase ---
    if ergebnis == FALSCH:
        c["lapses"] = c.get("lapses", 0) + 1
        c["ease"] = max(MIN_LEICHTIGKEIT, ease - 0.2)
        c["interval_days"] = max(1.0, intervall * 0.5)
        c["state"] = "learning"
        c["step"] = 0
        c["due"] = (now + timedelta(minutes=LERNSTUFEN_MIN[0])).isoformat(timespec="seconds")
        return c

    if ergebnis == FAST:
        c["ease"] = max(MIN_LEICHTIGKEIT, ease - 0.15)
        neu = intervall * 1.2
    else:  # RICHTIG
        c["ease"] = ease
        neu = intervall * ease

    # Immer mindestens einen Tag mehr als vorher, höchstens ein Jahr.
    neu = min(MAX_INTERVALL_TAGE, max(intervall + 1, neu))
    c["interval_days"] = round(neu, 2)
    c["due"] = _tagesbeginn_plus(now, neu).isoformat(timespec="seconds")
    return c


MIN_NEUE_SAETZE = 3   # so viele Satzmuster kommen täglich mindestens dazu


def neue_karten_erlaubt(limit: int, heute_eingefuehrt: int, faellig: int) -> int:
    """Wie viele neue Satzkarten dürfen heute noch in die Wiederholung?

    Das Tageslimit gilt für alle neuen Karten zusammen (Vokabeln der
    Lektion + Satzmuster). Damit Satzmuster trotzdem nicht liegen bleiben,
    kommen täglich mindestens MIN_NEUE_SAETZE dazu.

    Lastbremse: Sind schon viele Wiederholungen fällig, kommen weniger bzw.
    keine neuen Karten dazu – sonst wächst der Berg immer weiter.
    """
    if limit <= 0 or faellig > 80:
        return 0
    erlaubt = max(MIN_NEUE_SAETZE, limit - heute_eingefuehrt)
    if faellig > 50:
        return erlaubt // 2
    return erlaubt
