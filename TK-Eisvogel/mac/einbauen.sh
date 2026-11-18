#!/bin/bash
# TK Eisvogel – gebautes Mac-Programm nach /Applications legen und im Dock an die Stelle von „TK KI“ setzen (am iMac ausführen).
# Das bisherige Programm wird nicht gelöscht, sondern in die Sicherung verschoben. Claude 17.11.2026
set -e
Q="$(cd "$(dirname "$0")" && pwd)"
NEU="$Q/fertig/TK Eisvogel.app"
[ -d "$NEU" ] || { echo "erst bauen.sh ausführen"; exit 1; }
S="$HOME/backups/spiegel/$(date +%F_%H%M%S)-claude-eisvogel"; mkdir -p "$S"
pkill -x TKKI 2>/dev/null || true
pkill -x TKEisvogel 2>/dev/null || true
[ -d "/Applications/TK KI.app" ] && mv "/Applications/TK KI.app" "$S/"
[ -d "/Applications/TK Eisvogel.app" ] && mv "/Applications/TK Eisvogel.app" "$S/TK Eisvogel.app.alt"
cp -R "$NEU" "/Applications/TK Eisvogel.app"
cp -p "$HOME/Library/Preferences/com.apple.dock.plist" "$S/com.apple.dock.plist"
/usr/bin/python3 - <<'E'
import plistlib, os, subprocess
p = os.path.expanduser("~/Library/Preferences/com.apple.dock.plist")
d = plistlib.loads(subprocess.run(["defaults", "export", "com.apple.dock", "-"], capture_output=True).stdout)
neu, n = "file:///Applications/TK%20Eisvogel.app/", 0
for a in d.get("persistent-apps", []):
    t = a.get("tile-data", {}); u = t.get("file-data", {}).get("_CFURLString", "")
    if u.endswith("/Applications/TK%20KI.app/") and "/Users/" not in u:
        t["file-data"]["_CFURLString"] = neu; t["file-label"] = "TK Eisvogel"; t.pop("bundle-identifier", None); n += 1
if n:
    subprocess.run(["defaults", "import", "com.apple.dock", "-"], input=plistlib.dumps(d)); subprocess.run(["killall", "Dock"])
print("Dock-Einträge umgestellt:", n)
E
/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister -f "/Applications/TK Eisvogel.app" 2>/dev/null || true
echo "eingebaut: /Applications/TK Eisvogel.app · Sicherung: $S"
