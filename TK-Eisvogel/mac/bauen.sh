#!/bin/bash
# TK Eisvogel – Mac-Programm bauen (am iMac ausführen). Claude 17.11.2026
# Baut in einem Arbeitsordner und legt das fertige Programm als „TK Eisvogel.app“ neben dieses Skript (Unterordner fertig/).
# Einbau nach /Applications macht einbauen.sh.
set -e
Q="$(cd "$(dirname "$0")" && pwd)"
A="$Q/fertig/TK Eisvogel.app"
rm -rf "$Q/fertig"; mkdir -p "$A/Contents/MacOS" "$A/Contents/Resources"
swiftc -O "$Q/main.swift" -o "$A/Contents/MacOS/TKEisvogel" -framework Cocoa -framework WebKit
cp "$Q/Info.plist" "$A/Contents/Info.plist"
# Symbol: das Eisvogel-Zeichen (aus dem bisherigen Programm bzw. aus TK Vogel)
for I in "/Applications/TK Eisvogel.app/Contents/Resources/TKEisvogel.icns" "/Applications/TK KI.app/Contents/Resources/TKKI.icns" "$HOME/Applications/TK Vogel.app/Contents/Resources/AppIcon.icns"; do
  [ -f "$I" ] && { cp "$I" "$A/Contents/Resources/TKEisvogel.icns"; break; }
done
codesign --force --deep -s - "$A" 2>/dev/null
echo "gebaut: $A"
