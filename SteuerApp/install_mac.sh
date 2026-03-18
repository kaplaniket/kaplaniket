#!/bin/bash
# ================================================================
# SteuerApp – macOS Installations-Skript
# Unterstützt: Intel (2020+) und Apple Silicon (M1–M5)
# ================================================================

set -e

GRUEN='\033[0;32m'
GELB='\033[1;33m'
ROT='\033[0;31m'
BLAU='\033[0;34m'
RESET='\033[0m'

echo ""
echo -e "${BLAU}╔══════════════════════════════════════════════════╗${RESET}"
echo -e "${BLAU}║       SteuerApp – Installations-Assistent        ║${RESET}"
echo -e "${BLAU}╚══════════════════════════════════════════════════╝${RESET}"
echo ""

# ── System erkennen ──────────────────────────────────────────────
ARCH=$(uname -m)
OS_VER=$(sw_vers -productVersion 2>/dev/null || echo "unbekannt")

echo -e "${BLAU}System-Info:${RESET}"
echo "  macOS Version: $OS_VER"
echo "  Architektur:   $ARCH"
if [ "$ARCH" = "arm64" ]; then
    echo "  Chip:          Apple Silicon (M1/M2/M3/M4/M5)"
else
    echo "  Chip:          Intel"
fi
echo ""

# ── Homebrew prüfen/installieren ────────────────────────────────
echo -e "${BLAU}[1/5] Homebrew prüfen...${RESET}"
if ! command -v brew &> /dev/null; then
    echo -e "${GELB}Homebrew nicht gefunden. Installiere...${RESET}"
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

    # Apple Silicon: Homebrew-Pfad setzen
    if [ "$ARCH" = "arm64" ]; then
        eval "$(/opt/homebrew/bin/brew shellenv)"
        echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >> ~/.zprofile
    fi
else
    echo -e "${GRUEN}✓ Homebrew bereits installiert${RESET}"
fi

# ── Python 3 prüfen/installieren ─────────────────────────────────
echo ""
echo -e "${BLAU}[2/5] Python 3 prüfen...${RESET}"

PYTHON_CMD=""
for cmd in python3.12 python3.11 python3.10 python3.9 python3; do
    if command -v "$cmd" &> /dev/null; then
        VERSION=$($cmd --version 2>&1 | grep -oP '\d+\.\d+')
        MAJOR=$(echo $VERSION | cut -d. -f1)
        MINOR=$(echo $VERSION | cut -d. -f2)
        if [ "$MAJOR" -ge 3 ] && [ "$MINOR" -ge 8 ]; then
            PYTHON_CMD="$cmd"
            break
        fi
    fi
done

if [ -z "$PYTHON_CMD" ]; then
    echo -e "${GELB}Python 3.8+ nicht gefunden. Installiere Python 3.12...${RESET}"
    brew install python@3.12
    PYTHON_CMD="python3.12"
fi

PYTHON_VERSION=$($PYTHON_CMD --version)
echo -e "${GRUEN}✓ $PYTHON_VERSION gefunden${RESET}"

# ── pip aktualisieren ────────────────────────────────────────────
echo ""
echo -e "${BLAU}[3/5] pip aktualisieren...${RESET}"
$PYTHON_CMD -m pip install --upgrade pip --quiet
echo -e "${GRUEN}✓ pip aktualisiert${RESET}"

# ── Python-Bibliotheken installieren ────────────────────────────
echo ""
echo -e "${BLAU}[4/5] Python-Bibliotheken installieren...${RESET}"
echo "Installiere: PyMuPDF, Pillow, pytesseract, python-docx, openpyxl, reportlab"
echo ""

$PYTHON_CMD -m pip install -r "$(dirname "$0")/requirements.txt" --quiet --no-warn-script-location

echo -e "${GRUEN}✓ Python-Bibliotheken installiert${RESET}"

# ── Tesseract OCR installieren ──────────────────────────────────
echo ""
echo -e "${BLAU}[5/5] Tesseract OCR installieren...${RESET}"

if ! command -v tesseract &> /dev/null; then
    echo "Installiere Tesseract und Deutsche Sprachdaten..."
    brew install tesseract
    brew install tesseract-lang
    echo -e "${GRUEN}✓ Tesseract installiert${RESET}"
else
    echo -e "${GRUEN}✓ Tesseract bereits installiert${RESET}"
    # Deutsche Sprachdaten prüfen
    if ! tesseract --list-langs 2>/dev/null | grep -q "deu"; then
        echo "Installiere Deutsche Sprachdaten..."
        brew install tesseract-lang
    fi
fi

# ── Zusammenfassung ──────────────────────────────────────────────
echo ""
echo -e "${GRUEN}╔══════════════════════════════════════════════════╗${RESET}"
echo -e "${GRUEN}║           Installation abgeschlossen!             ║${RESET}"
echo -e "${GRUEN}╚══════════════════════════════════════════════════╝${RESET}"
echo ""
echo "Starten Sie die App mit:"
echo ""
echo -e "  ${BLAU}cd $(dirname "$0")${RESET}"
echo -e "  ${BLAU}$PYTHON_CMD main.py${RESET}"
echo ""
echo "Oder doppelklicken Sie auf:"
echo -e "  ${BLAU}SteuerApp.command${RESET}"
echo ""

# run.command erstellen
RUN_SCRIPT="$(dirname "$0")/SteuerApp.command"
cat > "$RUN_SCRIPT" << EOF
#!/bin/bash
cd "$(dirname "$0")"
$PYTHON_CMD main.py
EOF
chmod +x "$RUN_SCRIPT"

echo -e "${GELB}Hinweis: Beim ersten Start der .command-Datei:${RESET}"
echo "  Rechtsklick → Öffnen (da das Skript nicht von Apple signiert ist)"
echo ""
