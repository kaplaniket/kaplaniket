#!/usr/bin/env python3
"""TK KI – Tempo messen: Zeit bis zum ersten Wort und bis zum Ende."""
import json, sys, time, urllib.request
FR = sys.argv[1:] or ["Was ist die Hauptstadt von Australien?", "Wie heißt meine Frau?", "Welche Regel gilt für Änderungen am TKonnektor?"]
for f in FR:
    t0 = time.time(); erst = None; txt = ""
    r = urllib.request.urlopen(urllib.request.Request("http://127.0.0.1:8811/api/frage", data=json.dumps({"frage": f, "test": True}).encode(),
                               headers={"Content-Type": "application/json"}), timeout=600)
    for z in r:
        j = json.loads(z)
        if j.get("t"):
            erst = erst or time.time() - t0
            txt += j["t"]
    print(f"erstes Wort {erst or 0:5.1f}s · fertig {time.time()-t0:5.1f}s | {f} → {txt.strip()[:90]}", flush=True)
