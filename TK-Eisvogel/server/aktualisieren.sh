#!/bin/bash
# TK KI: Index neu berechnen und Server neu laden (Cron 4:40)
B=/media/tekin/Disk2/TK-KI
echo "== $(date '+%d.%m.%Y %H:%M')" >> $B/logs/index.log
/usr/bin/python3 $B/app/indexer.py >> $B/logs/index.log 2>&1 && curl -s -X POST 127.0.0.1:8811/api/neu-laden >> $B/logs/index.log; echo >> $B/logs/index.log
