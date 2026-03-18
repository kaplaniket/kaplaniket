#!/bin/bash
# SteuerApp – Starter (Doppelklick zum Öffnen)
# ─────────────────────────────────────────────
# Dieses Skript startet SteuerApp.
# WICHTIG: Beim ersten Start Rechtsklick → Öffnen

# In das App-Verzeichnis wechseln
cd "$(dirname "$0")"

# Python finden
PYTHON_CMD=""
for cmd in python3.12 python3.11 python3.10 python3.9 python3; do
    if command -v "$cmd" &> /dev/null; then
        PYTHON_CMD="$cmd"
        break
    fi
done

if [ -z "$PYTHON_CMD" ]; then
    osascript -e 'display alert "Python nicht gefunden" message "Bitte install_mac.sh ausführen." as critical'
    exit 1
fi

# Homebrew-Pfad für Apple Silicon
if [ -f /opt/homebrew/bin/brew ]; then
    eval "$(/opt/homebrew/bin/brew shellenv)"
fi

echo "Starte SteuerApp..."
$PYTHON_CMD main.py
