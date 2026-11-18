#!/usr/bin/env python3
"""TK Eisvogel – Gesamtprüfung (Claude 16.11.2026). Stellt feste Fragen an den laufenden Server und misst:
Zeit bis zum ersten Wort, Gesamtzeit, Weg (Quellen), Stichworte in der Antwort. Legt nichts an (Feld test=true).
Aufruf: python3 pruefung.py [--kurz] [--json]
"""
import json, sys, time, urllib.request
import json as _json, os as _os
def _privat(name, beispiel):
    p = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "privat", name)
    try: return [tuple(x) for x in _json.load(open(p, encoding="utf-8"))]
    except Exception: return beispiel

import os
URL = os.environ.get("EISVOGEL_URL", "http://127.0.0.1:8811")
# --lokal: Prüflauf erzwingt den Weg „Nur lokal“ (ohne die Einstellung zu ändern) · --mehr: zusätzlich 10 schwierigere Fragen
# Echte Prüffragen (mit persönlichen Antworten) liegen nur auf dem HP in privat/pruefung-mehr.json; hier Beispiele.
MEHR = _privat("pruefung-mehr.json", [("Was ist 17 mal 23?", "391", 10), ("Erkläre kurz, was eine Steuer-ID ist.", "identifikation|elf|11", 10)])
# Echte Prüffragen (mit persönlichen Antworten) liegen nur auf dem HP in privat/pruefung.json; hier Beispiele.
FRAGEN = _privat("pruefung.json", [("Welche Termine habe ich diese Woche?", "", 1), ("Was ist offen?", "offen", 1), ("Was ist die Hauptstadt von Australien?", "canberra", 8)])

def frage(f, verlauf=None):
    d = json.dumps({"frage": f, "verlauf": verlauf or [], "test": True, "quelle": "lokal" if "--lokal" in sys.argv else ""}).encode()
    t0 = time.time(); erst = None; txt = ""; quellen = []; fehler = ""; status = []
    try:
        r = urllib.request.urlopen(urllib.request.Request(URL + "/api/frage", d, {"Content-Type": "application/json"}), timeout=180)
        for z in r:
            try: o = json.loads(z)
            except Exception: continue
            if o.get("status"): status.append(o["status"])
            if o.get("reset"): txt = ""
            if o.get("quellen"): quellen = [q.get("seite") for q in o["quellen"]]
            if o.get("fehler"): fehler = o["fehler"]
            if o.get("t"):
                if erst is None: erst = time.time() - t0
                txt += o["t"]
    except Exception as e:
        fehler = str(e)
    return {"frage": f, "erst": erst, "gesamt": time.time() - t0, "text": txt, "quellen": quellen, "fehler": fehler}

def main():
    kurz = "--kurz" in sys.argv; aus = []; gut = 0
    for f, stich, grenze in (FRAGEN[:6] if kurz else FRAGEN + (MEHR if "--mehr" in sys.argv else [])):
        e = frage(f)
        ok_inhalt = (not stich) or any(s in e["text"].lower() for s in stich.split("|"))
        ok_tempo = e["erst"] is not None and e["erst"] <= grenze
        e.update(inhalt=ok_inhalt, tempo=ok_tempo); aus.append(e); gut += ok_inhalt and bool(e["text"].strip())
        if "--json" not in sys.argv:
            print(f"{'✓' if ok_inhalt and e['text'].strip() else '✗'} {'⚡' if ok_tempo else '🐢'} {(e['erst'] if e['erst'] is not None else -1):5.1f}s / {e['gesamt']:5.1f}s  {f}")
            print("      " + " ".join(e["text"].split())[:230] + (f"  [FEHLER: {e['fehler']}]" if e["fehler"] else ""))
            print("      Quellen: " + ", ".join(str(q) for q in e["quellen"][:5]))
    if "--json" in sys.argv: print(json.dumps(aus, ensure_ascii=False))
    else:
        zeiten = [e["erst"] for e in aus if e["erst"] is not None]
        print(f"\n{gut}/{len(aus)} inhaltlich richtig · erstes Wort im Mittel {sum(zeiten)/max(len(zeiten),1):.1f} s · längste {max(zeiten or [0]):.1f} s")

if __name__ == "__main__":
    main()
