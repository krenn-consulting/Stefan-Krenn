"""Webserver der App: liefert die Oberfläche (frontend/) und die API (/api/...)."""

import os
from contextlib import asynccontextmanager
from datetime import date
from pathlib import Path

from fastapi import Body, Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from . import config, content, db

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
    return {
        "streak": db.streak(con),
        "faellig": db.due_count(con),
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


# --- Oberfläche ------------------------------------------------------------
# Muss zuletzt eingebunden werden, sonst würde sie die /api-Routen verdecken.
app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
