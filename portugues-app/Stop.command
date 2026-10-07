#!/bin/bash
# =====================================================================
#  Português-App beenden – per Doppelklick im Finder.
#  (Alternativ einfach das Terminalfenster der App schließen.)
# =====================================================================

APP_DIR="$(cd "$(dirname "$0")" && pwd)"
PID_FILE="$APP_DIR/data/server.pid"

echo
GESTOPPT=""

if [ -f "$PID_FILE" ]; then
    PID="$(cat "$PID_FILE")"
    if [ -n "$PID" ] && kill -0 "$PID" 2>/dev/null; then
        kill "$PID" 2>/dev/null
        for _ in 1 2 3 4 5 6 7 8 9 10; do
            kill -0 "$PID" 2>/dev/null || break
            sleep 0.5
        done
        kill -9 "$PID" 2>/dev/null
        GESTOPPT="ja"
    fi
    rm -f "$PID_FILE"
fi

# Sicherheitsnetz: falls die PID-Datei fehlt, nach dem Serverprozess
# dieser App suchen (nur Prozesse aus genau diesem Ordner).
if pkill -f "$APP_DIR/.venv/bin/python -m uvicorn backend.main:app" 2>/dev/null; then
    GESTOPPT="ja"
fi

if [ -n "$GESTOPPT" ]; then
    echo "  ✅  Die Português-App wurde beendet."
else
    echo "  ℹ️  Die Português-App lief nicht."
fi
echo "      Dieses Fenster kannst du jetzt schließen."
echo
