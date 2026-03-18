#!/bin/bash
# ================================================================
# SteuerApp – macOS .app Bundle erstellen mit PyInstaller
# Erstellt eine universal Binary (Intel + Apple Silicon)
# ================================================================

set -e

GRUEN='\033[0;32m'
GELB='\033[1;33m'
BLAU='\033[0;34m'
RESET='\033[0m'

echo -e "${BLAU}SteuerApp – Build-Skript${RESET}"
echo ""

# PyInstaller installieren
pip3 install pyinstaller --quiet

# Build
pyinstaller \
    --name "SteuerApp" \
    --windowed \
    --onedir \
    --clean \
    --noconfirm \
    --add-data "src:src" \
    --hidden-import "PIL._tkinter_finder" \
    --hidden-import "pkg_resources.py2_warn" \
    --target-arch universal2 \
    main.py

echo ""
echo -e "${GRUEN}Build fertig!${RESET}"
echo "App liegt in: dist/SteuerApp.app"
echo ""
echo "Zum Verteilen:"
echo "  cp -r dist/SteuerApp.app /Applications/"
