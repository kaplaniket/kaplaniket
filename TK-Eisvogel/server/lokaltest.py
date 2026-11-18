#!/usr/bin/env python3
"""TK Eisvogel – Genauigkeitstest für „Nur lokal“ (Claude 17.11.2026). 30 Fragen mit bekannter richtiger Antwort aus dem Wiki.
Gewertet wird streng: Der richtige Wert muss in der Antwort stehen, ein bekannter falscher darf nicht darin stehen.
Legt nichts an (test=true). Aufruf: lokaltest.py [--modell=NAME] [--threads=N] [--vogel] [--url=http://127.0.0.1:8812] [--kurz]
"""
import json, re, sys, time, urllib.request
import json as _json, os as _os
def _privat(name, beispiel):
    p = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "privat", name)
    try: return [tuple(x) for x in _json.load(open(p, encoding="utf-8"))]
    except Exception: return beispiel

ARG = {a.split("=")[0].lstrip("-"): (a.split("=", 1)[1] if "=" in a else True) for a in sys.argv[1:]}
URL = ARG.get("url", "http://127.0.0.1:8811")
# Echte Prüffragen (mit persönlichen Antworten) liegen nur auf dem HP in privat/lokaltest.json; hier Beispiele.
FRAGEN = _privat("lokaltest.json", [("Wie heißt meine Frau?", r"vorname", ""), ("Was ist die Hauptstadt von Australien?", r"canberra", r"sydney"), ("Was ist 17 mal 23?", r"391", "")])

def frage(f):
    d = {"frage": f, "test": True}
    if not ARG.get("vogel"): d["quelle"] = "lokal"
    if ARG.get("modell"): d["modell"] = ARG["modell"]
    if ARG.get("threads"): d["threads"] = int(ARG["threads"])
    t0 = time.time(); erst = None; txt = ""; weg = ""; fehler = ""
    try:
        r = urllib.request.urlopen(urllib.request.Request(URL + "/api/frage", json.dumps(d).encode(), {"Content-Type": "application/json"}), timeout=240)
        for z in r:
            try: o = json.loads(z)
            except Exception: continue
            if o.get("reset"): txt = ""
            if o.get("t"):
                if erst is None: erst = time.time() - t0
                txt += o["t"]
            if o.get("fertig"): weg = o.get("weg", "")
            if o.get("fehler"): fehler = o["fehler"]
    except Exception as e: fehler = str(e)
    return txt, weg, erst, time.time() - t0, fehler

def main():
    gut = 0; zeiten = []; modellzeiten = []; liste = FRAGEN[:10] if ARG.get("kurz") else FRAGEN
    for f, muss, nicht in liste:
        txt, weg, erst, ges, fehler = frage(f)
        # gewertet wird die eigentliche Antwort: der Satz nach „Kurz:“, sonst alles (ohne die angehängte Personen-Akte)
        kern = txt.split("Kurz:")[-1] if "Kurz:" in txt else txt
        kern = kern.split("\n\n—\n")[0] if "Kurz:" in txt else kern
        if weg == "beleg" and txt.startswith("**"): kern = txt.split("\n")[0]      # hervorgehobene Angabe: die muss stimmen, nicht irgendein Beleg darunter
        t = kern.lower()
        ok = bool(re.search(muss, t)) and not (nicht and re.search(nicht, t))
        beleg_ok = bool(re.search(muss, txt.lower()))
        gut += ok; zeiten.append(ges)
        if weg.startswith("lokal"): modellzeiten.append(ges)
        print(f"{'✓' if ok else '✗'}{'b' if beleg_ok and not ok else ' '} {weg:10s} {(erst if erst is not None else -1):5.1f}s {ges:5.1f}s  {f}")
        print("       → " + " ".join(kern.split())[:200] + (f" [FEHLER {fehler}]" if fehler else ""), flush=True)
    print(f"\n{ARG.get('modell') or ('TK Vogel' if ARG.get('vogel') else 'Standardmodell')}: {gut}/{len(liste)} richtig · alle Fragen Ø {sum(zeiten)/len(zeiten):.1f} s · "
          f"mit Modell formuliert: {len(modellzeiten)} Fragen, Ø {sum(modellzeiten)/max(len(modellzeiten),1):.1f} s, längste {max(modellzeiten or [0]):.1f} s")

if __name__ == "__main__":
    main()
