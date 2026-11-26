#!/bin/bash
# TK Preisjäger – Mac-Programm bauen (am Mac ausführen). Claude 26.11.2026
# Baut eine Datei für beide Chip-Arten (Intel + Apple) und legt „TK Preisjäger.app“ in den Unterordner fertig/.
set -e
Q="$(cd "$(dirname "$0")" && pwd)"
A="$Q/fertig/TK Preisjäger.app"
T="$(mktemp -d)"
rm -rf "$Q/fertig"; mkdir -p "$A/Contents/MacOS" "$A/Contents/Resources"
for ARCH in x86_64 arm64; do
  swiftc -O -target "$ARCH-apple-macos11.0" "$Q/main.swift" -o "$T/pj-$ARCH" -framework Cocoa -framework WebKit
done
lipo -create "$T/pj-x86_64" "$T/pj-arm64" -output "$A/Contents/MacOS/TKPreisjaeger"
cp "$Q/Info.plist" "$A/Contents/Info.plist"
# Symbol aus symbol.png
I="$T/TKPreisjaeger.iconset"; mkdir -p "$I"
for G in 16 32 128 256 512; do
  sips -z $G $G "$Q/symbol.png" --out "$I/icon_${G}x${G}.png" >/dev/null
  sips -z $((G*2)) $((G*2)) "$Q/symbol.png" --out "$I/icon_${G}x${G}@2x.png" >/dev/null
done
iconutil -c icns "$I" -o "$A/Contents/Resources/TKPreisjaeger.icns"
codesign --force --deep -s - "$A" 2>/dev/null
rm -rf "$T"
echo "gebaut: $A ($(lipo -archs "$A/Contents/MacOS/TKPreisjaeger"))"
