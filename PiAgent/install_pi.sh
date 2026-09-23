#!/usr/bin/env bash
# PiAgent – Claude Code auf dem Raspberry Pi installieren (Raspberry Pi OS 64-bit)
#
#   bash install_pi.sh
set -euo pipefail

INSTALL_DIR="$HOME/pi-agent"
SRC_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "==> PiAgent (Claude Code) – Installation"

if [ "$(uname -m)" != "aarch64" ] && [ "$(uname -m)" != "x86_64" ]; then
  echo "Claude Code benötigt ein 64-bit-Betriebssystem (aktuell: $(uname -m))."
  echo "Bitte Raspberry Pi OS (64-bit) installieren."
  exit 1
fi

# 1. Hilfsprogramme (git für Projekte, tmux für den Hintergrundbetrieb)
echo "==> Installiere git, tmux, curl …"
sudo apt-get update -qq
sudo apt-get install -y -qq git tmux curl ripgrep >/dev/null

# 2. Claude Code (offizieller nativer Installer)
if ! command -v claude >/dev/null 2>&1 && [ ! -x "$HOME/.local/bin/claude" ]; then
  echo "==> Installiere Claude Code …"
  curl -fsSL https://claude.ai/install.sh | bash
fi
export PATH="$HOME/.local/bin:$PATH"
if ! grep -q '.local/bin' "$HOME/.bashrc" 2>/dev/null; then
  echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$HOME/.bashrc"
fi

# 3. Arbeitsverzeichnis mit Pi-Kontext (CLAUDE.md) und Berechtigungen
mkdir -p "$INSTALL_DIR/.claude" "$INSTALL_DIR/projekte"
# vorhandene (evtl. angepasste) Dateien nicht überschreiben
[ -e "$INSTALL_DIR/CLAUDE.md" ] || cp "$SRC_DIR/workspace/CLAUDE.md" "$INSTALL_DIR/"
[ -e "$INSTALL_DIR/.claude/settings.json" ] || cp "$SRC_DIR/workspace/.claude/settings.json" "$INSTALL_DIR/.claude/"

# 4. Befehle
#    pi-agent          → Claude Code im Terminal (im Pi-Arbeitsverzeichnis)
#    pi-agent-remote   → Remote Control im Hintergrund (tmux), steuerbar über die Claude-App
sudo tee /usr/local/bin/pi-agent >/dev/null <<EOF
#!/usr/bin/env bash
cd "$INSTALL_DIR" && exec "$HOME/.local/bin/claude" "\$@"
EOF
sudo tee /usr/local/bin/pi-agent-remote >/dev/null <<EOF
#!/usr/bin/env bash
if tmux has-session -t pi-agent 2>/dev/null; then
  echo "Läuft bereits. Anzeigen mit: tmux attach -t pi-agent"
else
  tmux new-session -d -s pi-agent -c "$INSTALL_DIR" "$HOME/.local/bin/claude remote-control"
  echo "Remote Control gestartet. Anzeigen mit: tmux attach -t pi-agent (verlassen: Strg+B, D)"
fi
EOF
sudo chmod +x /usr/local/bin/pi-agent /usr/local/bin/pi-agent-remote

echo
echo "✅ Fertig!"
echo "   1. Einmal anmelden:   pi-agent   (Login mit deinem Claude-Konto öffnet einen Link)"
echo "   2. Im Terminal nutzen: pi-agent"
echo "   3. Vom Handy steuern: pi-agent-remote  → Sitzung erscheint in der Claude-App"
echo "   Kontext anpassen: $INSTALL_DIR/CLAUDE.md"
