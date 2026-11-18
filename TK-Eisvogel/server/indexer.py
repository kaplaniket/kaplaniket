#!/usr/bin/env python3
"""TK Eisvogel (TK KI) – Wissensindex aus allen Obsidian-Beständen. Fassung 3 (Claude 16.11.2026, Gesamtprüfung).
Liest alle .md-Dateien, zerlegt sie in Abschnitte, berechnet Vektoren (bge-m3 über Ollama auf dem HP) und speichert auf Disk2.

Neu in Fassung 3:
- Es läuft immer nur EIN Indexer (Sperre /tmp/tk-ki-indexer.lock). Vorher liefen bis zu drei gleichzeitig
  (lernen.sh, Dauertraining, Cron) und bremsten jede Frage aus.
- Vorfahrt: solange Tekin fragt (/tmp/tk-ki-aktiv jünger als 45 s), wartet der Indexer.
- Vektor-Zwischenspeicher binär (cache_ids.json + cache_vek.npy) statt 110 MB JSON → Start in Millisekunden.
- Gelernte Frage-Antwort-Paare (qa.jsonl): nur gültig, solange der Abschnitt, aus dem sie stammen, unverändert
  im Wiki steht; doppelte Fragen mit verschiedenen Antworten gelten als mehrdeutig. Nur eindeutige Paare aus
  Wiki-Seiten (nicht aus Chat-Mitschriften) dürfen später wörtlich ausgegeben werden (Feld „woertlich“).
- Für gelernte Paare wird nur die Frage eingebettet (genauer beim Wiedererkennen, 3× schneller).
Aufruf: indexer.py [--warten]   (--warten: auf einen laufenden Indexer warten statt sofort zu enden)
"""
import fcntl, hashlib, json, os, re, sys, time, urllib.request
import numpy as np

BASIS = "/media/tekin/Disk2/TK-KI"
IDX = f"{BASIS}/index"
OLLAMA = "http://127.0.0.1:11434"
EMB_MODELL = "bge-m3"
SPERRE = "/tmp/tk-ki-indexer.lock"
AKTIV = "/tmp/tk-ki-aktiv"

# (Pfad, Name, Gewicht) – aktuelles Wiki zählt am meisten
QUELLEN = [
    ("/home/tekin/Obsidian", "Obsidian (aktuell)", 1.0),
    ("/media/tekin/Disk2/Dokumente/Sonstiges/Von_Pi/Obsidian", "Obsidian alte Pi-Kopie (Disk2)", 0.85),
    ("/media/tekin/Disk2/Sonstiges/Von_iMac/Documents/Obsidian Vault", "Obsidian Vault iMac (Disk2)", 0.85),
]
AUSLASSEN = {".obsidian", ".trash", "_archiv", ".git"}
GEHEIM = re.compile(r"(passw|kennwort|token|api[_-]?key|secret|geheim\s*[:=])", re.I)


def tekin_fragt():
    try: return time.time() - os.path.getmtime(AKTIV) < 45
    except OSError: return False


def embed(texte):
    req = urllib.request.Request(f"{OLLAMA}/api/embed",
        data=json.dumps({"model": EMB_MODELL, "input": texte, "keep_alive": -1}).encode(),
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=600) as r:
        return json.load(r)["embeddings"]


def frontmatter_weg(t):
    if t.startswith("---"):
        e = t.find("\n---", 3)
        if e != -1:
            return t[e + 4:]
    return t


def zerlegen(text, max_len=900):
    """Nach Überschriften, zu lange Teile nach Absätzen."""
    teile, titel, puffer = [], "", []
    def flush():
        s = "\n".join(puffer).strip()
        if len(s) < 40:
            return
        while len(s) > max_len:
            schnitt = s.rfind("\n", 0, max_len)
            if schnitt < max_len // 2:
                schnitt = max_len
            teile.append((titel, s[:schnitt].strip()))
            s = s[schnitt - 100 if schnitt > 200 else schnitt:].strip()
        if s:
            teile.append((titel, s))
    for zeile in text.splitlines():
        if re.match(r"^#{1,4} ", zeile):
            flush(); puffer = []
            titel = zeile.lstrip("#").strip()
        if GEHEIM.search(zeile) and re.search(r"[:=]\s*\S{8,}", zeile):
            continue  # mögliche Zugangsdaten nie in den Index
        puffer.append(zeile)
    flush()
    return teile


# ---------- Zwischenspeicher der Vektoren (binär) ----------
def cache_laden():
    ids_p, vek_p = f"{IDX}/cache_ids.json", f"{IDX}/cache_vek.npy"
    if os.path.exists(ids_p) and os.path.exists(vek_p):
        ids = json.load(open(ids_p)); vek = np.load(vek_p)
        if len(ids) == len(vek):
            return {i: n for n, i in enumerate(ids)}, vek
    alt = f"{IDX}/cache.json"   # einmalige Übernahme aus der alten JSON-Datei
    if os.path.exists(alt):
        c = json.load(open(alt))
        if c:
            ids = list(c); vek = np.array([c[i] for i in ids], dtype=np.float32)
            return {i: n for n, i in enumerate(ids)}, vek
    return {}, np.zeros((0, 1024), dtype=np.float32)


def gelernte_paare(gesehen):
    """qa.jsonl → Abschnitte „Gelernt“. Prüft, ob der Quell-Abschnitt noch unverändert im Wiki steht."""
    qa = f"{IDX}/qa.jsonl"
    if not os.path.exists(qa):
        return [], {}
    try:
        sys.path.insert(0, f"{BASIS}/app")
        from training import abschnitte as tr_abschnitte   # dieselbe Zerlegung wie beim Erzeugen
        from pathlib import Path
    except Exception:
        tr_abschnitte = None
    gueltig_je_datei = {}
    def gueltig(pfad, h):
        if tr_abschnitte is None or not h: return True
        if pfad not in gueltig_je_datei:
            try: gueltig_je_datei[pfad] = {hashlib.sha1(tx.encode()).hexdigest() for _, tx in tr_abschnitte(Path(pfad))}
            except Exception: gueltig_je_datei[pfad] = set()      # Datei weg oder unlesbar → Paare ungültig
        return h in gueltig_je_datei[pfad]
    roh, stat = [], {"gesamt": 0, "veraltet": 0, "mehrdeutig": 0, "woertlich": 0}
    for z in open(qa, encoding="utf-8"):
        try: x = json.loads(z)
        except Exception: continue
        if not x.get("frage") or not x.get("antwort"): continue
        if x.get("seite") in ("tk-eisvogel", "tk-ki", "log"): continue     # Arbeitsnotizen über die App (enthalten Prüffragen und Fehlerberichte) sind kein Wissen
        stat["gesamt"] += 1
        if not gueltig(x.get("pfad", ""), x.get("hash")):
            stat["veraltet"] += 1; continue
        roh.append(x)
    # gleiche Frage mit verschiedenen Antworten = mehrdeutig (z. B. Tagesmeldungen) → nie wörtlich ausgeben
    norm = lambda t: re.sub(r"[^a-zäöüß0-9]", "", t.lower())
    antworten = {}
    for x in roh:
        antworten.setdefault(norm(x["frage"]), set()).add(norm(x["antwort"]))
    aus, schon = [], set()
    for x in roh:
        nf = norm(x["frage"])
        if nf in schon: continue
        schon.add(nf)
        pfad = x.get("pfad", ""); aus_chat = "/raw/" in pfad
        mehrdeutig = len(antworten[nf]) > 1
        if mehrdeutig: stat["mehrdeutig"] += 1
        # vom kleinen lokalen Modell erzeugte Paare sind Hintergrund, keine wörtliche Antwort (es verliest sich gelegentlich)
        woertlich = not aus_chat and not mehrdeutig and x.get("erzeugt") != "lokal"
        stat["woertlich"] += woertlich
        einbetten = f"{x.get('seite','')}: {x['frage']}"
        h = hashlib.sha1(("qa3:" + einbetten).encode()).hexdigest()
        if h in gesehen: continue
        gesehen.add(h)
        try: geaendert = os.path.getmtime(pfad)
        except OSError: geaendert = 0
        aus.append({"id": h, "quelle": "Gelernt", "gewicht": 1.0, "pfad": pfad, "seite": x.get("seite", ""),
                    "titel": x["frage"], "antwort": x["antwort"], "geaendert": geaendert, "woertlich": woertlich,
                    "einbetten": einbetten, "text": f"[{x.get('seite','')} – {x['frage']}]\n{x['antwort']}"})
    return aus, stat


def main():
    os.makedirs(IDX, exist_ok=True)
    sperre = open(SPERRE, "w")
    try:
        fcntl.flock(sperre, fcntl.LOCK_EX if "--warten" in sys.argv else fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        print("Indexer läuft schon – nichts zu tun"); return
    pos, vek_alt = cache_laden()
    stuecke, gesehen = [], set()
    for wurzel, name, gewicht in QUELLEN:
        if not os.path.isdir(wurzel):
            print("fehlt:", wurzel); continue
        for ordner, dirs, dateien in os.walk(wurzel):
            dirs[:] = [d for d in dirs if d not in AUSLASSEN]
            for f in dateien:
                if not f.endswith(".md") or f == "tk-ki-fehler.md":   # als falsch markierte Antworten sind kein Wissen (Claude 17.11.2026)
                    continue
                pfad = os.path.join(ordner, f)
                try:
                    roh = open(pfad, encoding="utf-8", errors="ignore").read()
                    geaendert = os.path.getmtime(pfad)
                except Exception:
                    continue
                seite = f[:-3]
                for titel, txt in zerlegen(frontmatter_weg(roh)):
                    h = hashlib.sha1(txt.encode()).hexdigest()
                    if h in gesehen:   # gleicher Text in alter Kopie → nur einmal
                        continue
                    gesehen.add(h)
                    stuecke.append({"id": h, "quelle": name, "gewicht": gewicht,
                        "pfad": pfad, "seite": seite, "titel": titel, "geaendert": geaendert,
                        "text": f"[{seite}{' – ' + titel if titel else ''}]\n{txt}"})
    gelernt, qstat = gelernte_paare(gesehen)
    stuecke += gelernt
    # Tekins eigener Verlauf: jede früher gestellte Frage mit der damaligen Antwort (verlauf.py). Eingebettet wird nur die Frage.
    frueher = []
    try:
        sys.path.insert(0, f"{BASIS}/app")
        import verlauf as _vl
        _vl.auffrischen()
        for z in open(f"{IDX}/verlauf.jsonl", encoding="utf-8"):
            x = json.loads(z); h = hashlib.sha1(("vl:" + x["frage"]).encode()).hexdigest()
            if h in gesehen: continue
            gesehen.add(h)
            try: ts = time.mktime(time.strptime(x.get("zeit", "")[:10], "%Y-%m-%d"))
            except Exception: ts = 0
            frueher.append({"id": h, "quelle": "Verlauf", "gewicht": 1.0, "pfad": x.get("pfad", ""), "seite": x.get("herkunft", "Verlauf"), "titel": x["frage"],
                            "antwort": x["antwort"], "zeit": x.get("zeit", ""), "geaendert": ts, "woertlich": False, "einbetten": x["frage"],
                            "text": f"[{x.get('herkunft','')} {x.get('zeit','')} – {x['frage']}]\n{x['antwort']}"})
    except Exception as e:
        print("Verlauf nicht aufgenommen:", e)
    stuecke += frueher
    for s in stuecke:
        s["roh"] = "/raw/" in s["pfad"]   # Chat-Mitschriften: Nachrang
    # Reihenfolge beim Berechnen: Wiki-Seiten, dann Gelerntes aus dem Wiki, dann Mitschriften, zuletzt Gelerntes aus Chats
    rang = lambda s: (s["roh"], s["quelle"] == "Gelernt")
    neu = sorted((s for s in stuecke if s["id"] not in pos), key=rang)
    print(f"{len(stuecke)} Abschnitte ({len(gelernt)} gelernt: {qstat}), {len(neu)} neu zu berechnen", flush=True)
    neu_vek = {}

    def speichern(fertig):
        dim = vek_alt.shape[1] if len(vek_alt) else (len(next(iter(neu_vek.values()))) if neu_vek else 1024)
        vek = np.zeros((len(stuecke), dim), dtype=np.float32)
        for n, s in enumerate(stuecke):
            if s["id"] in neu_vek: vek[n] = neu_vek[s["id"]]
            elif s["id"] in pos: vek[n] = vek_alt[pos[s["id"]]]
        mit = int((np.abs(vek).sum(axis=1) > 0).sum())
        roh_vek = vek.copy()
        vek /= np.linalg.norm(vek, axis=1, keepdims=True) + 1e-9
        np.save(f"{IDX}/vektoren.tmp.npy", vek); os.replace(f"{IDX}/vektoren.tmp.npy", f"{IDX}/vektoren.npy")
        schlank = [{k: v for k, v in s.items() if k != "einbetten"} for s in stuecke]
        json.dump(schlank, open(f"{IDX}/stuecke.json.tmp", "w"), ensure_ascii=False); os.replace(f"{IDX}/stuecke.json.tmp", f"{IDX}/stuecke.json")
        hat = [n for n in range(len(stuecke)) if roh_vek[n].any()]
        np.save(f"{IDX}/cache_vek.tmp.npy", roh_vek[hat]); os.replace(f"{IDX}/cache_vek.tmp.npy", f"{IDX}/cache_vek.npy")
        json.dump([stuecke[n]["id"] for n in hat], open(f"{IDX}/cache_ids.json.tmp", "w")); os.replace(f"{IDX}/cache_ids.json.tmp", f"{IDX}/cache_ids.json")
        json.dump({"stand": time.strftime("%d.%m.%Y %H:%M"), "abschnitte": len(stuecke), "mit_vektor": mit, "fertig": fertig,
                   "seiten": len({s["pfad"] for s in stuecke if s["quelle"] != "Gelernt"}),
                   "gelernt": len(gelernt), "gelernt_woertlich": sum(1 for s in gelernt if s["woertlich"]), "verlauf": len(frueher),
                   "gelernt_veraltet": qstat.get("veraltet", 0) if qstat else 0},
                  open(f"{IDX}/stand.json.tmp", "w")); os.replace(f"{IDX}/stand.json.tmp", f"{IDX}/stand.json")

    t0 = time.time(); seit = 0; N = 6       # kleine Päckchen: eine Frage wartet höchstens ~2 s auf das laufende (mit 24 langen Abschnitten waren es bis 12 s)
    for i in range(0, len(neu), N):
        while tekin_fragt(): time.sleep(2)          # Vorfahrt für Tekins Fragen
        teil = neu[i:i + N]
        for s, v in zip(teil, embed([(x.get("einbetten") or x["text"])[:2000] for x in teil])):
            neu_vek[s["id"]] = v
        seit += len(teil)
        if (i // N) % 40 == 0 or i + N >= len(neu):
            print(f"  {min(i+N, len(neu))}/{len(neu)}  {time.time()-t0:.0f}s", flush=True)
        if seit >= 1500:                            # Zwischenstand, damit bei Abbruch nichts verloren geht
            speichern(False); seit = 0
    speichern(True)
    print("fertig")


if __name__ == "__main__":
    main()
