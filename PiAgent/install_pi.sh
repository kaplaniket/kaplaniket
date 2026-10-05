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

# 2. Claude Code (offizieller nativer Installer, falls noch nicht vorhanden)
export PATH="$HOME/.local/bin:$PATH"
if ! command -v claude >/dev/null 2>&1; then
  echo "==> Installiere Claude Code …"
  curl -fsSL https://claude.ai/install.sh | bash
fi
# Tatsächlichen Pfad merken (kann z. B. auch eine npm-Installation sein)
CLAUDE_BIN="$(command -v claude || true)"
if [ -z "$CLAUDE_BIN" ]; then
  echo "Claude Code wurde nicht gefunden. Bitte installieren: curl -fsSL https://claude.ai/install.sh | bash"
  exit 1
fi
# bewusst nicht readlink: ~/.local/bin/claude zeigt auf eine Version, die Auto-Updates austauschen
# PATH für den Dienst: Ordner von claude (+ node, falls npm-Installation)
SERVICE_PATH="$(dirname "$CLAUDE_BIN"):$HOME/.local/bin:/usr/local/bin:/usr/bin:/bin"
if command -v node >/dev/null 2>&1; then
  SERVICE_PATH="$(dirname "$(readlink -f "$(command -v node)")"):$SERVICE_PATH"
fi
echo "==> Claude Code: $CLAUDE_BIN"
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
#    pi-agent-remote   → Status/Start/Stopp der Remote-Control-Sitzung
sudo tee /usr/local/bin/pi-agent >/dev/null <<EOF
#!/usr/bin/env bash
cd "$INSTALL_DIR" && exec "$CLAUDE_BIN" "\$@"
EOF
sudo tee /usr/local/bin/pi-agent-remote >/dev/null <<'EOF'
#!/usr/bin/env bash
case "${1:-status}" in
  start)   sudo systemctl enable --now pi-agent-remote ;;
  stop)    sudo systemctl disable --now pi-agent-remote ;;
  restart) sudo systemctl restart pi-agent-remote ;;
  attach)  exec tmux attach -t pi-agent ;;
  log)     tail -n 40 "$HOME/pi-agent/remote.log" ;;
  status)  systemctl --no-pager status pi-agent-remote | head -5 ;;
  *) echo "Nutzung: pi-agent-remote [status|start|stop|restart|attach|log]"; exit 1 ;;
esac
EOF
# Startskript für den Dienst: schreibt Claudes Ausgabe (inkl. Fehlermeldungen)
# nach remote.log und hält die Sitzung nach einem Absturz kurz offen,
# damit man sie mit "pi-agent-remote attach" noch lesen kann
sudo tee /usr/local/bin/pi-agent-remote-run >/dev/null <<EOF
#!/usr/bin/env bash
cd "$INSTALL_DIR"
echo "=== \$(date '+%F %T') Start claude remote-control ===" >> remote.log
export PATH="$SERVICE_PATH:\$PATH"
script -qfae -c "$CLAUDE_BIN remote-control" remote.log
rc=\$?
echo "=== \$(date '+%F %T') beendet (Code \$rc) – Neustart folgt ===" | tee -a remote.log
sleep 20
EOF
sudo chmod +x /usr/local/bin/pi-agent /usr/local/bin/pi-agent-remote /usr/local/bin/pi-agent-remote-run

# 5. Autostart: Remote Control startet bei jedem Boot in einer tmux-Sitzung
#    (tmux, damit man mit "pi-agent-remote attach" hineinschauen kann)
sudo tee /etc/systemd/system/pi-agent-remote.service >/dev/null <<EOF
[Unit]
Description=PiAgent – Claude Code Remote Control
After=network-online.target
Wants=network-online.target
StartLimitIntervalSec=0

[Service]
Type=forking
User=$USER
Environment=HOME=$HOME
Environment=PATH=$SERVICE_PATH
WorkingDirectory=$INSTALL_DIR
ExecStartPre=-/usr/bin/tmux kill-session -t pi-agent
ExecStart=/usr/bin/tmux new-session -d -s pi-agent -c $INSTALL_DIR /usr/local/bin/pi-agent-remote-run
ExecStop=-/usr/bin/tmux kill-session -t pi-agent
Restart=always
RestartSec=30

[Install]
WantedBy=multi-user.target
EOF
# eine von Hand gestartete Sitzung (ältere Version) beenden, damit der Dienst übernimmt
tmux kill-session -t pi-agent 2>/dev/null || true
sudo systemctl daemon-reload
sudo systemctl enable pi-agent-remote >/dev/null 2>&1
sudo systemctl restart pi-agent-remote || true

echo
echo "✅ Fertig!"
echo "   1. Einmal anmelden:    pi-agent   (Login mit deinem Claude-Konto öffnet einen Link)"
echo "   2. Im Terminal nutzen: pi-agent"
echo "   3. Vom Handy steuern:  startet automatisch bei jedem Boot → Sitzung in der Claude-App"
echo "      Status: pi-agent-remote   Log: pi-agent-remote log   Hineinschauen: pi-agent-remote attach (Strg+B, D)"
echo "   Kontext anpassen: $INSTALL_DIR/CLAUDE.md"
