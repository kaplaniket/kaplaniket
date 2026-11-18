#!/bin/bash
# TK KI lernt: neue/geänderte Wiki-Abschnitte sofort in den Index, Server neu laden,
# danach Lernfragen prüfen (Genauigkeit + Tempo). Aufruf durch claude-sichern (Hintergrund) oder von Hand.
B=/media/tekin/Disk2/TK-KI
exec 9>/tmp/tk-ki-lernen.lock; flock -n 9 || exit 0
sleep 20   # Spiegel/weitere Schreibvorgänge abwarten
{ echo "== $(date '+%d.%m.%Y %H:%M') lernen"; t0=$(date +%s)
  nice -n 10 /usr/bin/python3 $B/app/indexer.py 2>&1 | tail -2
  curl -s -m 600 -X POST 127.0.0.1:8811/api/neu-laden; echo; echo "Index $(( $(date +%s)-t0 )) s"
  # Prüfung höchstens stündlich (bremst sonst Tekins Fragen)
  # Tempo (Claude 16.11.2026, Tekin: „Antworten wie aus der Pistole“): automatische Prüfung nur nachts 1–6 Uhr
  H=$(date +%-H)
  if [ "${1:-}" = "--pruefen" ] || { [ $H -ge 1 ] && [ $H -lt 6 ] && [ -z "$(find $B/logs/lernstand.json -mmin -60 2>/dev/null)" ]; }; then nice -n 5 /usr/bin/python3 $B/app/lernpruefung.py --kurz; fi
} >> $B/logs/lernen.log 2>&1
