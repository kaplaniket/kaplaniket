#!/usr/bin/env bash
# PiAgent – Installation auf dem Raspberry Pi (Raspberry Pi OS 64-bit)
#
#   bash install_pi.sh            # Installation, Modell je nach RAM
#   bash install_pi.sh qwen2.5:7b # bestimmtes Modell erzwingen
set -euo pipefail

INSTALL_DIR="$HOME/pi-agent"
SRC_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "==> PiAgent-Installation"

if [ "$(uname -m)" != "aarch64" ] && [ "$(uname -m)" != "x86_64" ]; then
  echo "Ollama benötigt ein 64-bit-Betriebssystem (aktuell: $(uname -m))."
  echo "Bitte Raspberry Pi OS (64-bit) installieren."
  exit 1
fi

# Modell passend zum Arbeitsspeicher wählen
RAM_MB=$(awk '/MemTotal/ {print int($2/1024)}' /proc/meminfo)
if [ -n "${1:-}" ]; then
  MODEL="$1"
elif [ "$RAM_MB" -ge 7000 ]; then
  MODEL="qwen2.5:3b"      # Pi 5 / Pi 4 mit 8 GB
elif [ "$RAM_MB" -ge 3500 ]; then
  MODEL="qwen2.5:1.5b"    # 4 GB
else
  MODEL="qwen2.5:0.5b"    # 2 GB – sehr einfach, aber lauffähig
fi
echo "==> RAM: ${RAM_MB} MB → Modell: $MODEL"

# 1. Ollama
if ! command -v ollama >/dev/null 2>&1; then
  echo "==> Installiere Ollama …"
  curl -fsSL https://ollama.com/install.sh | sh
fi
sudo systemctl enable --now ollama >/dev/null 2>&1 || true
for _ in $(seq 1 30); do
  curl -fs http://127.0.0.1:11434/api/tags >/dev/null && break
  sleep 1
done

# 2. Modell laden
echo "==> Lade Modell $MODEL (kann einige Minuten dauern) …"
ollama pull "$MODEL"

# 3. Agent kopieren
mkdir -p "$INSTALL_DIR"
cp "$SRC_DIR/agent.py" "$SRC_DIR/web.html" "$INSTALL_DIR/"
chmod +x "$INSTALL_DIR/agent.py"
cat > "$INSTALL_DIR/pi-agent.env" <<EOF
PI_AGENT_MODEL=$MODEL
PI_AGENT_HOST=0.0.0.0
PI_AGENT_PORT=8765
# 1 = Web-Oberfläche darf Shell-Befehle ausführen und Dateien schreiben
PI_AGENT_ALLOW_SHELL=0
EOF

# 4. Befehl "pi-agent" für das Terminal
sudo tee /usr/local/bin/pi-agent >/dev/null <<EOF
#!/usr/bin/env bash
set -a; . "$INSTALL_DIR/pi-agent.env"; set +a
exec python3 "$INSTALL_DIR/agent.py" "\$@"
EOF
sudo chmod +x /usr/local/bin/pi-agent

# 5. Web-Oberfläche als Dienst
sudo tee /etc/systemd/system/pi-agent.service >/dev/null <<EOF
[Unit]
Description=PiAgent – lokaler KI-Agent (Web)
After=network-online.target ollama.service
Wants=ollama.service

[Service]
User=$USER
EnvironmentFile=$INSTALL_DIR/pi-agent.env
ExecStart=/usr/bin/python3 $INSTALL_DIR/agent.py --web
Restart=on-failure

[Install]
WantedBy=multi-user.target
EOF
sudo systemctl daemon-reload
sudo systemctl enable --now pi-agent

IP=$(hostname -I 2>/dev/null | awk '{print $1}')
echo
echo "✅ Fertig!"
echo "   Terminal:  pi-agent"
echo "   Browser:   http://${IP:-<pi-ip>}:8765"
echo "   Einstellungen: $INSTALL_DIR/pi-agent.env (danach: sudo systemctl restart pi-agent)"
