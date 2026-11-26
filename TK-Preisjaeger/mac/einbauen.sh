#!/bin/bash
# TK Preisjäger – gebautes Programm nach /Applications legen und die Adressen des HP eintragen (am Mac ausführen).
# Aufruf: einbauen.sh "http://<Heimnetz-IP>:8815,http://<Tailnet-IP>:8815"
# Eine vorhandene Fassung wird nicht gelöscht, sondern in die Sicherung verschoben. Claude 26.11.2026
set -e
Q="$(cd "$(dirname "$0")" && pwd)"
NEU="$Q/fertig/TK Preisjäger.app"
[ -d "$NEU" ] || { echo "erst bauen.sh ausführen"; exit 1; }
pkill -x TKPreisjaeger 2>/dev/null || true
if [ -d "/Applications/TK Preisjäger.app" ]; then
  S="$HOME/backups/spiegel/$(date +%F_%H%M%S)-claude-preisjaeger"; mkdir -p "$S"
  mv "/Applications/TK Preisjäger.app" "$S/"
fi
cp -R "$NEU" "/Applications/TK Preisjäger.app"
[ -n "$1" ] && defaults write de.tekin.preisjaeger adressen "$1"
/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister -f "/Applications/TK Preisjäger.app" 2>/dev/null || true
echo "eingebaut: /Applications/TK Preisjäger.app · Adressen: $(defaults read de.tekin.preisjaeger adressen 2>/dev/null || echo 'Vorgabe')"
