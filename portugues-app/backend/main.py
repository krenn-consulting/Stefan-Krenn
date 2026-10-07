"""Webserver der App: liefert die Oberfläche (frontend/) und die API (/api/...)."""

import asyncio
import os
from contextlib import asynccontextmanager
from datetime import date
from pathlib import Path

from fastapi import Body, Depends, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import ai, config, content, db, lesson, pruefen, statistik, tts

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"


def db_path() -> Path:
    # Für Tests lässt sich eine andere Datenbank-Datei setzen.
    return Path(os.environ.get("PORTUGUES_DB", db.DB_PATH))


def get_db():
    """Eine eigene Verbindung pro Anfrage – so gibt es keine Thread-Probleme."""
    con = db.connect(db_path())
    try:
        yield con
    finally:
        con.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    config.load_env()
    con = db.connect(db_path())
    db.init_db(con)
    con.close()
    db.daily_backup(db_path(), db_path().parent / "backups")
    yield


app = FastAPI(title="Português-App", lifespan=lifespan)


@app.middleware("http")
async def no_cache(request: Request, call_next):
    # Nach Updates soll Chrome immer die neuen Dateien laden.
    response = await call_next(request)
    if not request.url.path.startswith("/api/audio"):
        response.headers["Cache-Control"] = "no-store"
    return response


# --- API -------------------------------------------------------------------

@app.get("/api/health")
def health():
    """Wird von Start.command genutzt, um zu erkennen, ob die App läuft."""
    return {"app": "portugues-app", "ok": True}


@app.get("/api/overview")
def overview(con=Depends(get_db)):
    """Alle Zahlen für die Startseite."""
    done = {r["lesson_id"] for r in con.execute("SELECT lesson_id FROM lessons_done")}
    today = con.execute("SELECT seconds FROM daily_log WHERE day = ?",
                        (date.today().isoformat(),)).fetchone()
    faellig = db.due_count(con)
    return {
        "streak": db.streak(con),
        "faellig": faellig,
        "naechste_lektion": lesson.naechste_lektion(con),
        "heute_erledigt": lesson.heute_erledigt(con),
        "wiederholungstag_empfohlen": faellig >= lesson.WIEDERHOLUNGSTAG_AB,
        "fortschritt": content.level_progress(done),
        "lektionen_erledigt": len(done),
        "heute_minuten": round((today["seconds"] if today else 0) / 60),
        "claude_aktiv": config.claude_enabled(),
    }


@app.get("/api/settings")
def read_settings(con=Depends(get_db)):
    return db.get_settings(con)


@app.put("/api/settings")
def write_settings(changes: dict = Body(...), con=Depends(get_db)):
    return db.save_settings(con, changes)


@app.get("/api/export")
def export(con=Depends(get_db)):
    filename = f"portugues-sicherung-{date.today().isoformat()}.json"
    return JSONResponse(db.export_json(con),
                        headers={"Content-Disposition": f'attachment; filename="{filename}"'})


@app.post("/api/import")
def import_backup(data: dict = Body(...), con=Depends(get_db)):
    db.copy_db_before_import(db_path())
    try:
        db.import_json(con, data)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"ok": True}


# --- Fortschritt und Wortschatz -------------------------------------------

@app.get("/api/statistik")
def statistik_seite(con=Depends(get_db)):
    daten = statistik.fortschritt(con)
    daten["audio_mb"] = tts.cache_groesse_mb()
    return daten


@app.get("/api/wortschatz")
def wortschatz_seite(q: str = "", art: str = "alle", con=Depends(get_db)):
    return statistik.wortschatz(con, q, art)


# --- Claude (optional) -----------------------------------------------------

def _aktuelles_level(con) -> str:
    done = {r["lesson_id"] for r in con.execute("SELECT lesson_id FROM lessons_done")}
    return content.level_progress(done)["level"]


@app.post("/api/ki/gespraech")
def ki_gespraech(daten: dict = Body(...), con=Depends(get_db)):
    try:
        return ai.gespraech(daten.get("verlauf", []), daten.get("thema", "frei"), _aktuelles_level(con))
    except ai.KIFehler as e:
        raise HTTPException(503, str(e))


@app.post("/api/ki/korrektur")
def ki_korrektur(daten: dict = Body(...), con=Depends(get_db)):
    text = (daten.get("text") or "").strip()
    if not text:
        raise HTTPException(400, "Bitte zuerst einen Text schreiben.")
    try:
        return ai.korrigieren(text[:5000], daten.get("aufgabe", ""), _aktuelles_level(con))
    except ai.KIFehler as e:
        raise HTTPException(503, str(e))


# --- Lektion ---------------------------------------------------------------

@app.get("/api/lektion")
def lektion_plan(id: str | None = None, modus: str = "lektion", con=Depends(get_db)):
    """Die heutige (oder eine bestimmte) Lektion mit allen Schritten."""
    plan = lesson.plan(con, lesson_id=id, modus=modus)
    if plan is None:
        raise HTTPException(404, "Alle vorhandenen Lektionen sind erledigt – neue Inhalte folgen.")
    return plan


@app.post("/api/pruefen")
def antwort_pruefen(daten: dict = Body(...)):
    """Prüft eine getippte oder gesprochene Antwort (ohne etwas zu speichern)."""
    try:
        if daten.get("modus") == "sprechen":
            # Spracherkennung liefert mehrere Varianten – die beste zählt
            varianten = daten.get("varianten") or [daten.get("antwort", "")]
            return pruefen.pruefen_gesprochen(varianten, daten.get("loesungen", []))
        return pruefen.pruefen(daten.get("antwort", ""), daten.get("loesungen", []))
    except ValueError as e:
        raise HTTPException(400, str(e))


# --- Audio -----------------------------------------------------------------

@app.get("/api/audio")
async def audio(text: str, stimme: str = "standard", con=Depends(get_db)):
    """MP3 für einen portugiesischen Text. 503 = bitte Mac-Stimme verwenden."""
    standard = db.get_settings(con)["stimme"]
    try:
        pfad = await tts.audio_datei(text, tts.stimme_waehlen(stimme, standard))
    except tts.TTSFehler as e:
        raise HTTPException(503, str(e))
    return FileResponse(pfad, media_type="audio/mpeg",
                        headers={"Cache-Control": "public, max-age=31536000, immutable"})


@app.post("/api/audio/vorladen")
async def audio_vorladen(daten: dict = Body(...), con=Depends(get_db)):
    """Erzeugt die Audios einer Lektion im Hintergrund, damit es später nicht hakt."""
    standard = db.get_settings(con)["stimme"]
    eintraege = [(e.get("text", ""), tts.stimme_waehlen(e.get("stimme", "standard"), standard))
                 for e in (daten.get("texte") or [])[:300] if e.get("text")]
    asyncio.create_task(tts.vorladen(eintraege))
    return {"ok": True, "anzahl": len(eintraege)}


@app.post("/api/antwort")
def antwort_speichern(daten: dict = Body(...), con=Depends(get_db)):
    """Speichert das endgültige Ergebnis einer Antwort (nach evtl. Korrektur)."""
    if daten.get("ergebnis") not in ("richtig", "fast", "falsch"):
        raise HTTPException(400, "Ungültiges Ergebnis")
    try:
        return lesson.antwort_verbuchen(con, daten)
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.post("/api/lektion/{lesson_id}/block")
def block_speichern(lesson_id: str, daten: dict = Body(...), con=Depends(get_db)):
    """Merkt sich, dass ein Block fertig oder übersprungen ist."""
    try:
        lesson.block_speichern(con, lesson_id, daten.get("block", ""), daten.get("status", ""),
                               int(daten.get("sekunden") or 0))
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"ok": True}


@app.get("/api/lektion/{lesson_id}/zusammenfassung")
def lektion_zusammenfassung(lesson_id: str, con=Depends(get_db)):
    return lesson.zusammenfassung(con, lesson_id)


@app.post("/api/lektion/{lesson_id}/abschluss")
def lektion_abschluss(lesson_id: str, daten: dict = Body(...), con=Depends(get_db)):
    # Erst den Block speichern: Ein Test räumt beim Auswerten seine Blöcke für den
    # nächsten Versuch wieder auf.
    lesson.block_speichern(con, lesson_id, "abschluss", "fertig", int(daten.get("sekunden") or 0))
    return lesson.lektion_abschliessen(con, lesson_id, daten.get("selbsteinschaetzung"))


# --- Oberfläche ------------------------------------------------------------
# Muss zuletzt eingebunden werden, sonst würde sie die /api-Routen verdecken.
app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
