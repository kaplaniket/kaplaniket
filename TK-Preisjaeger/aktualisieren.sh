#!/bin/bash
# TK Preisjäger – neuen Stand aus GitHub auf den Server holen und einschalten. Aufruf: aktualisieren.sh [Zweig oder Commit]
# Holt die Programmdateien, lässt die Prüfung laufen und startet den Dienst neu. Die Baunummer zählt dabei von selbst hoch –
# offene Apps (Mac, iPhone, Browser) zeigen dann „Neues Update verfügbar“. Claude 26.11.2026
set -e
STAND="${1:-claude/keen-cannon-t6kf0h}"
B="https://raw.githubusercontent.com/kaplaniket/kaplaniket/$STAND/TK-Preisjaeger/server"
Z="$HOME/preisjaeger"; T="$(mktemp -d)"
for f in server.py kern.py quellen.py sprache.py browser.py verhandler.py verkauf.py anfragen.py pflege.py pruefung.py index.html symbol-180.png symbol-512.png; do
  curl -sfL -o "$T/$f" "$B/$f" || { echo "FEHLT: $f – nichts geändert"; exit 1; }
done
(cd "$T" && python3 pruefung.py | tail -1 | grep -q "alles in Ordnung") || { echo "Prüfung FEHLGESCHLAGEN – nichts geändert"; exit 1; }
S="$HOME/backups/spiegel/$(date +%F_%H%M%S)-claude-preisjaeger"; mkdir -p "$S"; cp -p "$Z"/*.py "$Z"/index.html "$S"/ 2>/dev/null || true
cp "$T"/*.py "$T"/*.html "$T"/*.png "$Z"/; rm -rf "$T"
systemctl --user restart tk-preisjaeger.service; sleep 3
curl -s -m 8 http://127.0.0.1:8815/api/stand | python3 -c "import json,sys; d=json.load(sys.stdin); print('eingespielt: Fassung', d['fassung'], 'Bau', d['bau'], '| Sicherung:', '$S')"
