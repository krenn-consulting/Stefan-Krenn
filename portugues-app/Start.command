#!/bin/bash
# =====================================================================
#  Português-App starten – einfach per Doppelklick im Finder öffnen.
#
#  Beim ersten Start richtet dieses Skript automatisch alles ein
#  (dauert ein paar Minuten, braucht Internet). Danach startet es nur
#  noch die App und öffnet Google Chrome.
#
#  Alles wird im Projektordner abgelegt (Ordner .werkzeuge und .venv),
#  am System wird nichts verändert. Löschen = Ordner in den Papierkorb.
#
#  Hinweis: macOS liefert die alte Bash 3.2 mit – deshalb nur einfache
#  Shell-Befehle verwenden.
# =====================================================================

APP_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$APP_DIR" || exit 1

TOOLS="$APP_DIR/.werkzeuge"
UV="$TOOLS/bin/uv"
VENV_PY="$APP_DIR/.venv/bin/python"
LOG="$APP_DIR/data/app.log"
PID_FILE="$APP_DIR/data/server.pid"
UPDATE_STAMP="$TOOLS/letztes-update"

# uv (Paketverwaltung) und Python ausschließlich im Projektordner
export UV_UNMANAGED_INSTALL="$TOOLS/bin"       # uv-Installer: hierhin, PATH nicht anfassen
export UV_PYTHON_INSTALL_DIR="$TOOLS/python"
export UV_CACHE_DIR="$TOOLS/cache"
export UV_PROJECT_ENVIRONMENT="$APP_DIR/.venv"
export UV_PYTHON_PREFERENCE=only-managed       # nie das Apple-Python benutzen (würde Xcode-Dialog auslösen)

mkdir -p "$TOOLS" "$APP_DIR/data"

# ---------------------------------------------------------------------
#  Hilfsfunktionen
# ---------------------------------------------------------------------

meldung() { echo "  $1"; }

# Verständliche Fehlermeldung, dann warten, damit das Fenster offen bleibt.
fehler() {
    echo
    echo "  ❌  $1"
    echo
    echo "  👉  $2"
    echo
    echo "  (Technische Details stehen in: data/app.log)"
    echo
    read -r -p "  Zum Schließen Enter drücken … " _
    exit 1
}

ist_mac() { [ "$(uname)" = "Darwin" ]; }

internet_ok() {
    curl -sS --max-time 8 -o /dev/null https://pypi.org/simple/ 2>/dev/null \
        || curl -sS --max-time 8 -o /dev/null https://github.com 2>/dev/null
}

# Läuft auf diesem Port unsere App?
unsere_app_auf() {
    curl -s --max-time 2 "http://127.0.0.1:$1/api/health" 2>/dev/null | grep -q '"portugues-app"'
}

# Ist der Port von irgendeinem Programm belegt?
port_belegt() {
    (echo > "/dev/tcp/127.0.0.1/$1") >/dev/null 2>&1
}

browser_oeffnen() {
    local url="$1"
    if ist_mac; then
        if open -Ra "Google Chrome" >/dev/null 2>&1; then
            open -a "Google Chrome" "$url"
        else
            echo
            meldung "⚠️  Google Chrome ist nicht installiert."
            meldung "    Die App funktioniert am besten in Chrome (Sprachausgabe und Mikrofon)."
            meldung "    Chrome gibt es kostenlos unter: https://www.google.com/chrome/"
            meldung "    Bis dahin öffne ich die App in deinem Standard-Browser."
            echo
            open "$url"
        fi
    else
        meldung "Bitte im Browser öffnen: $url"
    fi
}

# Alte Protokolle klein halten (max. ca. 2 MB)
if [ -f "$LOG" ] && [ "$(wc -c < "$LOG")" -gt 2000000 ]; then
    tail -n 2000 "$LOG" > "$LOG.tmp" && mv "$LOG.tmp" "$LOG"
fi
echo "===== Start $(date '+%Y-%m-%d %H:%M:%S') =====" >> "$LOG"

clear 2>/dev/null
echo
echo "  🇵🇹  Português-App"
echo

# ---------------------------------------------------------------------
#  1. macOS-Sperren lösen (Ausführungsrechte, Download-Quarantäne)
# ---------------------------------------------------------------------
chmod +x "$APP_DIR"/*.command 2>/dev/null
if ist_mac; then
    xattr -dr com.apple.quarantine "$APP_DIR" 2>/dev/null
fi

# ---------------------------------------------------------------------
#  2. Läuft die App schon? Dann nur Chrome öffnen.
# ---------------------------------------------------------------------
WUNSCH_PORT=8000
if [ -f "$APP_DIR/einstellungen.env" ]; then
    ENV_PORT="$(grep -E '^[[:space:]]*PORT=[0-9]+' "$APP_DIR/einstellungen.env" | tail -n 1 | cut -d= -f2 | tr -d '[:space:]')"
    [ -n "$ENV_PORT" ] && WUNSCH_PORT="$ENV_PORT"
fi

for p in $(seq "$WUNSCH_PORT" $((WUNSCH_PORT + 9))); do
    if unsere_app_auf "$p"; then
        meldung "Die App läuft bereits – ich öffne sie in Chrome."
        browser_oeffnen "http://localhost:$p"
        sleep 2
        exit 0
    fi
done

# ---------------------------------------------------------------------
#  3. Erstinstallation: uv (lädt danach Python selbst)
# ---------------------------------------------------------------------
if [ ! -x "$UV" ]; then
    meldung "Erster Start: Ich richte alles ein. Das dauert ein paar Minuten …"
    echo
    if ! internet_ok; then
        fehler "Für die Einrichtung beim ersten Start brauche ich eine Internetverbindung." \
               "Bitte WLAN prüfen und Start.command danach erneut per Doppelklick öffnen."
    fi
    meldung "⏳ Lade Werkzeug „uv“ …"
    # Installer erst in eine Datei laden (bei "curl | sh" würde ein
    # fehlgeschlagener Download nicht bemerkt), notfalls von GitHub.
    INSTALLER="$TOOLS/uv-installer.sh"
    for quelle in https://astral.sh/uv/install.sh \
                  https://github.com/astral-sh/uv/releases/latest/download/uv-installer.sh; do
        if curl -LsSf --retry 2 -o "$INSTALLER" "$quelle" >> "$LOG" 2>&1 \
           && sh "$INSTALLER" >> "$LOG" 2>&1 && [ -x "$UV" ]; then
            break
        fi
    done
    rm -f "$INSTALLER"
    if [ ! -x "$UV" ]; then
        fehler "Das Werkzeug „uv“ konnte nicht geladen werden." \
               "Bitte später erneut versuchen. Wenn es dauerhaft scheitert: data/app.log an deinen Entwickler schicken."
    fi
fi

# ---------------------------------------------------------------------
#  4. Python und Pakete installieren bzw. aktualisieren
#     - erstes Mal oder fehlende Umgebung: vollständige Einrichtung
#     - danach: einmal pro Woche automatisch auf neue Versionen prüfen
# ---------------------------------------------------------------------
ONLINE=""
internet_ok && ONLINE="ja"

LOCK_SICHERUNG="$TOOLS/uv.lock.vorher"
UPDATE_GEMACHT=""

if [ ! -x "$VENV_PY" ]; then
    if [ -z "$ONLINE" ]; then
        fehler "Für die Einrichtung beim ersten Start brauche ich eine Internetverbindung." \
               "Bitte WLAN prüfen und Start.command danach erneut per Doppelklick öffnen."
    fi
    meldung "⏳ Lade Python und die benötigten Pakete …"
    if ! "$UV" sync --no-dev >> "$LOG" 2>&1; then
        fehler "Die Einrichtung von Python ist fehlgeschlagen." \
               "Bitte Internetverbindung prüfen und Start.command erneut öffnen. Es wird dort weitergemacht, wo es aufgehört hat."
    fi
    date +%s > "$UPDATE_STAMP"
    meldung "✅ Einrichtung abgeschlossen."
elif [ -n "$ONLINE" ]; then
    JETZT=$(date +%s)
    LETZTES=$(cat "$UPDATE_STAMP" 2>/dev/null || echo 0)
    if [ $((JETZT - LETZTES)) -gt 604800 ]; then      # 7 Tage
        meldung "⏳ Suche nach Updates …"
        [ -f uv.lock ] && cp uv.lock "$LOCK_SICHERUNG"
        if "$UV" lock --upgrade >> "$LOG" 2>&1 && "$UV" sync --no-dev >> "$LOG" 2>&1; then
            UPDATE_GEMACHT="ja"
        else
            # Update fehlgeschlagen: alten Stand behalten
            [ -f "$LOCK_SICHERUNG" ] && cp "$LOCK_SICHERUNG" uv.lock
            "$UV" sync --no-dev >> "$LOG" 2>&1
        fi
        date +%s > "$UPDATE_STAMP"
    else
        # Schneller Abgleich, z. B. nach einer neuen App-Version
        "$UV" sync --no-dev >> "$LOG" 2>&1
    fi
else
    # Offline: vorhandene Umgebung einfach benutzen
    "$UV" sync --no-dev --offline >> "$LOG" 2>&1
fi

# ---------------------------------------------------------------------
#  5. Freien Port suchen und Server starten
# ---------------------------------------------------------------------
PORT=""
for p in $(seq "$WUNSCH_PORT" $((WUNSCH_PORT + 9))); do
    if ! port_belegt "$p"; then PORT="$p"; break; fi
done
if [ -z "$PORT" ]; then
    fehler "Kein freier Port zwischen $WUNSCH_PORT und $((WUNSCH_PORT + 9)) gefunden." \
           "Bitte den Mac neu starten und es dann erneut versuchen."
fi

SERVER_PID=""
aufraeumen() {
    if [ -n "$SERVER_PID" ] && kill -0 "$SERVER_PID" 2>/dev/null; then
        kill "$SERVER_PID" 2>/dev/null
        # bis zu 5 Sekunden auf sauberes Beenden warten
        for _ in 1 2 3 4 5 6 7 8 9 10; do
            kill -0 "$SERVER_PID" 2>/dev/null || break
            sleep 0.5
        done
        kill -9 "$SERVER_PID" 2>/dev/null
    fi
    rm -f "$PID_FILE"
}
trap aufraeumen EXIT
trap 'exit 0' HUP INT TERM     # Fenster geschlossen / Ctrl+C → EXIT-Trap räumt auf

server_starten() {
    "$VENV_PY" -m uvicorn backend.main:app --host 127.0.0.1 --port "$PORT" >> "$LOG" 2>&1 &
    SERVER_PID=$!
    echo "$SERVER_PID" > "$PID_FILE"
    # bis zu 30 Sekunden warten, bis die App antwortet
    for _ in $(seq 1 60); do
        unsere_app_auf "$PORT" && return 0
        kill -0 "$SERVER_PID" 2>/dev/null || return 1
        sleep 0.5
    done
    return 1
}

if ! server_starten; then
    aufraeumen
    if [ -n "$UPDATE_GEMACHT" ] && [ -f "$LOCK_SICHERUNG" ]; then
        # Das Update hat etwas kaputt gemacht → zurück zur vorherigen Version
        meldung "Das letzte Update funktioniert nicht – ich stelle die vorherige Version wieder her …"
        cp "$LOCK_SICHERUNG" uv.lock
        "$UV" sync --no-dev >> "$LOG" 2>&1
        server_starten || fehler "Die App ließ sich nicht starten." \
            "Bitte den Mac neu starten und Start.command erneut öffnen. Hilft das nicht: data/app.log an deinen Entwickler schicken."
    else
        fehler "Die App ließ sich nicht starten." \
               "Bitte den Mac neu starten und Start.command erneut öffnen. Hilft das nicht: data/app.log an deinen Entwickler schicken."
    fi
fi

# ---------------------------------------------------------------------
#  6. Chrome öffnen und laufen lassen
# ---------------------------------------------------------------------
URL="http://localhost:$PORT"
browser_oeffnen "$URL"

echo
echo "  ✅  App läuft – Fenster zum Beenden schließen."
echo "      Adresse: $URL"
echo

# Warten, bis der Server beendet wird (Fenster schließen oder Stop.command)
wait "$SERVER_PID"
SERVER_PID=""
rm -f "$PID_FILE"
echo "  App beendet."
