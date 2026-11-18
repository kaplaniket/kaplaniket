#!/usr/bin/env python3
"""TK KI – Lernfragen prüfen. Jede verarbeitete Sache bekommt eine Frage mit erwarteten Stichworten
(app/lernfragen.jsonl). Misst richtig/falsch, Zeit bis zum ersten Wort und Gesamtzeit; schreibt
logs/lernstand.json (Verlauf). Aufruf: lernpruefung.py [--kurz]  ·  Neue Frage: lernpruefung.py --neu "Frage" "wort1|wort2" "Quelle"
"""
import json, sys, time, urllib.request, os
B = "/media/tekin/Disk2/TK-KI"; F = B + "/app/lernfragen.jsonl"; S = B + "/logs/lernstand.json"
if len(sys.argv) > 1 and sys.argv[1] == "--neu":
    with open(F, "a") as f:
        f.write(json.dumps({"frage": sys.argv[2], "muss": sys.argv[3].lower().split("|"),
                            "quelle": sys.argv[4] if len(sys.argv) > 4 else "", "seit": time.strftime("%Y-%m-%d")}, ensure_ascii=False) + "\n")
    print("Lernfrage ergänzt"); sys.exit()
fragen = [json.loads(z) for z in open(F) if z.strip()]
erg = []
for q in fragen:
    t0 = time.time(); erst = None; txt = ""
    try:
        r = urllib.request.urlopen(urllib.request.Request("http://127.0.0.1:8811/api/frage",
            data=json.dumps({"frage": q["frage"], "test": True}).encode(), headers={"Content-Type": "application/json"}), timeout=300)
        for z in r:
            j = json.loads(z)
            if j.get("reset"): txt = ""
            if j.get("t") and erst is None: erst = time.time() - t0
            txt += j.get("t", "")
    except Exception as e:
        txt = f"FEHLER {e}"
    dt = time.time() - t0; ok = any(w in txt.lower() for w in q["muss"])
    erg.append({"frage": q["frage"], "ok": ok, "erstes_wort": round(erst or dt, 1), "gesamt": round(dt, 1), "antwort": txt.strip()[:300]})
    if "--kurz" not in sys.argv or not ok:
        print(f"{'OK' if ok else 'XX'} {erg[-1]['erstes_wort']:5.1f}s/{dt:5.1f}s | {q['frage']}\n   → {txt.strip()[:220]}", flush=True)
n = sum(e["ok"] for e in erg)
zus = {"zeit": time.strftime("%Y-%m-%d %H:%M"), "richtig": n, "fragen": len(erg),
       "erstes_wort_schnitt": round(sum(e["erstes_wort"] for e in erg) / max(len(erg), 1), 1),
       "gesamt_schnitt": round(sum(e["gesamt"] for e in erg) / max(len(erg), 1), 1),
       "falsch": [e["frage"] for e in erg if not e["ok"]]}
verlauf = json.load(open(S)) if os.path.exists(S) else []
verlauf.append(zus); json.dump(verlauf[-200:], open(S, "w"), ensure_ascii=False, indent=1)
print(f"== Lernstand {zus['zeit']}: {n}/{len(erg)} richtig, erstes Wort Ø {zus['erstes_wort_schnitt']} s, gesamt Ø {zus['gesamt_schnitt']} s")
