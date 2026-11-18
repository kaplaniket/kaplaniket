#!/usr/bin/env python3
"""TK KI – Personen-Akte (16.11.2026, Vorgabe Tekin: „Wenn ich nach einer Person suche, sofort alle
Informationen mitliefern“). Erkennt bekannte Namen in der Frage und liefert sofort (ohne Sprachmodell):
Wer ist das (Wiki), Kontakt, Termine/Fristen, offene Punkte, Mails, WhatsApp/Telegram, weitere Wiki-Fundstellen.
Nur lesend. Test: python3 person.py "Zeki"
"""
import os, re, sqlite3, subprocess, sys, time
from datetime import date, datetime
from pathlib import Path

H = Path.home()
WIKI = H / "Obsidian"
TKDB = H / "postamt/postamt.db"
GDB = H / "gedaechtnis/gedaechtnis.db"   # WhatsApp/iMessage (TK Vogel)
EIGEN = {"kaplan"}                        # Tekins Nachname: nicht allein danach suchen
FIRMEN = set("amazon paypal dhl hermes telekom vodafone sparkasse check24 ebay kleinanzeigen apple google microsoft adac allianz otto klarna netflix spotify immoscout tk claude".split())
ORTE = set("dortmund düsseldorf bochum essen köln berlin hamburg münchen heimatort türkei deutschland nrw stadt amt bank schule verein gruppe familie haus wohnung".split())
GEHEIM = re.compile(r"passw|kennwort|\bpin\b|\btan\b|iban|\bde\d{2}[ \d]{12,}|kontonummer|steuer-?id|ausweisnummer|token|api.?key", re.I)
FUELL = set("frau herr dr prof von van der die das den dem und mit bei für team gmbh ag kg info service noreply no-reply kundenservice support newsletter".split())
STOPP = set("wer was wann wie wo ist sind mein meine meinen meiner über zu von alles infos info akte gibt es erzähl mir sag zeig mal bitte kennst du weißt ich habe hast hat der die das ein eine einen und oder noch schon".split())
_NAMEN = {"zeit": 0, "liste": []}

def _db():
    return sqlite3.connect(f"file:{TKDB}?mode=ro", uri=True, timeout=3)

def namen():
    """Bekannte Personen: Wiki-Personenseiten, Kontakte, Chat-Partner, häufige Mail-Absender. 10 Min. zwischengespeichert."""
    if time.time() - _NAMEN["zeit"] < 600 and _NAMEN["liste"]:
        return _NAMEN["liste"]
    L = {}
    def dazu(name, quelle, seite=None):
        name = re.sub(r"[\U0001F000-\U0001FFFF☀-➿]", "", name or "").strip(" \"'<>")
        if len(name) < 4 or "@" in name or not re.search(r"[A-Za-zÄÖÜäöüß]{3}", name): return
        k = name.lower()
        e = L.setdefault(k, {"name": name, "quellen": set(), "seite": None})
        e["quellen"].add(quelle)
        if seite: e["seite"] = seite
    for p in (WIKI / "06 Wiki/personen").glob("*.md"):
        t = p.read_text(errors="ignore")
        m = re.search(r"^title:\s*(.+)$", t, re.M)
        dazu(m.group(1).strip() if m else p.stem.replace("-", " ").title(), "wiki", p)
    try:
        c = _db()
        for (n,) in c.execute("select name from kontakte_auto"): dazu(n, "kontakt")
        for (n,) in c.execute("select name from chats"): dazu(n, "chat")
        for (n,) in c.execute("select from_name from msgs where from_name<>'' and is_bulk=0 group by from_name having count(*)>=2"): dazu(n, "mail")
        c.close()
    except Exception:
        pass
    try:
        g = sqlite3.connect(f"file:{GDB}?mode=ro", uri=True, timeout=3)
        for (n,) in g.execute("select partner from nachrichten group by partner having count(*)>=2"): dazu(n, "whatsapp")
        g.close()
    except Exception:
        pass
    _NAMEN.update(zeit=time.time(), liste=list(L.values()))
    return _NAMEN["liste"]

def erkennen(frage):
    """Gibt den passendsten bekannten Personen-Eintrag zurück oder None."""
    f = frage.lower()
    woerter = [w for w in re.findall(r"[a-zäöüß][a-zäöüß\-]{2,}", f) if w not in STOPP]
    woerter += [w[:-1] for w in woerter if w.endswith("s") and len(w) >= 5]   # Genitiv: „Marias“ → „maria“
    if not woerter: return None
    best, bscore = None, 0
    for e in namen():
        teile = [t for t in re.findall(r"[a-zäöüß][a-zäöüß\-]{2,}", e["name"].lower()) if t not in FUELL]
        if not teile: continue
        treff_w = [t for t in teile if any(w == t or (len(t) >= 5 and len(w) >= 5 and (w.startswith(t[:5]) and t.startswith(w[:5]))) for w in woerter)]
        treffer = len(treff_w)
        if not treffer: continue
        # Claude 17.11.2026 (Gesamtprüfung): Verwechslungen vermeiden –
        if all(t in ORTE or t in EIGEN or t in FIRMEN for t in treff_w): continue        # „Dortmund“ oder „Amazon“ ist keine Person
        familie = len(teile) > 1 and teile[-1] in EIGEN                                   # Familie Kaplan hat Vorrang vor gleichnamigen Kontakten
        if len(teile) == 1 and e["quellen"] <= {"mail"}: continue                         # einzelner Absendername (Amazon, Vodafone …) ist eine Firma
        if treffer == 1 and len(teile) > 1 and "wiki" not in e["quellen"] and treff_w[0] not in (teile[0], teile[-1]): continue   # zweiter Vorname allein („Ben“ ≠ „Mehmet Ben S.“)
        score = treffer * 10 + (5 if treffer == len(teile) else 0) + (4 if "wiki" in e["quellen"] else 0) + len(e["quellen"])
        # ein einzelnes Allerweltswort (z. B. Vorname) reicht nur bei Wiki/Kontakt/Chat
        if familie: score += 8
        if treffer == 1 and len(teile) > 1 and not familie and not (e["quellen"] & {"wiki", "kontakt", "chat", "whatsapp"}): continue
        if treffer == 1 and all(t in EIGEN for t in teile if any(w == t for w in woerter)) : continue   # nur „Kaplan“ reicht nicht
        if score > bscore: best, bscore = e, score
    # Personenfrage ohne bekannten Namen: „wer ist X“
    if not best:
        m = re.search(r"(?i)(wer ist|was weiß ich über|was wei[sß]t du über|infos? (über|zu)|akte (zu|über|von)|alles (über|zu)) ([A-ZÄÖÜa-zäöüß][\wäöüß\-]+(?: [A-ZÄÖÜa-zäöüß][\wäöüß\-]+)?)", frage)
        if m:
            nm = m.group(m.lastindex).strip()
            # Claude 17.11.2026: „Wer ist mein Steuerberater?“ ist keine Person namens „mein Steuerberater“ (ergab eine Akte aus Zufallstreffern zu „mein“)
            if nm.split()[0].lower() in STOPP | {"mein", "meine", "meinem", "meinen", "meiner", "dein", "deine", "unser", "unsere", "ein", "eine", "einer", "dieser", "diese", "zuständig", "jetzt", "hier", "da"}: return None
            return {"name": nm, "quellen": set(), "seite": None}
    return best

def _such(name):
    teile = [t for t in name.split() if t.lower() not in FUELL and len(t) >= 3]
    if not teile: return name
    if teile[-1].lower() in EIGEN and len(teile) > 1: return teile[0]   # „Maria Kaplan“ → nach „Maria“ suchen
    return teile[-1]  # Nachname ist meist eindeutiger

def _rein(t):
    return "" if GEHEIM.search(t or "") else re.sub(r"\s+", " ", t or "").strip()

def akte(e):
    name = e["name"]; q = _such(name); ql = q.lower(); aus = [f"**{name}** – das weiß ich:"]
    # 1) Wer ist das (Wiki-Personenseite)
    if e.get("seite"):
        t = Path(e["seite"]).read_text(errors="ignore")
        t = re.sub(r"^---.*?---\s*", "", t, flags=re.S)
        zeilen = [z.strip() for z in t.splitlines() if z.strip() and not z.startswith("#") and not GEHEIM.search(z)]
        aus += ["", f"Wer – laut [[{Path(e['seite']).stem}]]:"] + [("• " + z.lstrip("-* ").replace("**", "")) for z in zeilen[:10]]
    else:   # keine eigene Seite: passende Zeilen aus Familie/Personen/Themen
        try:
            r = subprocess.run(["grep", "-rIi", "-w", "--include=*.md", "--exclude-dir=raw", "--exclude-dir=_archiv", "--exclude-dir=journal", "--exclude=tk-ki*.md", "--exclude=tagesjournal.md", "--exclude=log.md",
                                "-e", name.split()[0], str(WIKI / "06 Wiki/themen"), str(WIKI / "06 Wiki/personen")], capture_output=True, text=True, timeout=5).stdout
            zeilen, seen = [], set()
            vorrang = lambda z: (0 if "/familie" in z else 1, len(z))
            for z in sorted(r.splitlines(), key=vorrang):
                pfad, _, txt = z.partition(":")
                txt = re.sub(r"\s+", " ", txt.replace("**", "").strip(" |-*#"))
                if len(txt) < 15 or GEHEIM.search(txt) or txt[:60] in seen or txt.count("|") >= 3: continue
                seen.add(txt[:60]); zeilen.append(f"• {txt[:200]} ([[{Path(pfad).stem}]])")
                if len(zeilen) >= 6: break
            if zeilen: aus += ["", "Wer / wo erwähnt:"] + zeilen
        except Exception:
            pass
        # Steckbrief aus ALLEN Unterlagen inkl. Chat-Mitschriften: Sätze mit Angaben zur Person
        try:
            r = subprocess.run(["grep", "-rIhi", "-o", "-E", r".{0,90}\b" + re.escape(name.split()[0]) + r"\b.{0,170}", str(WIKI)], capture_output=True, text=True, timeout=8).stdout
            KEY = re.compile(r"(?i)tochter|sohn|ehefrau|ehemann|bruder|schwester|mutter|vater|geb\.|geboren|wohnt|gemeldet|adresse|str\.|studiert|studium|arbeitet|beruf|firma|handy|telefon|mail|@|mieter|vermieter|anwalt|steuerberater|arzt")
            s, seen = [], set()
            for z in r.splitlines():
                z = re.sub(r"\s+", " ", z.replace("**", "").strip(" >|-*#`"))
                if len(z) < 30 or not KEY.search(z) or GEHEIM.search(z) or re.search(r"(?i)rclone|curl|adb |cdp\.py|\.zip|\.apk|start_process|selin.?(tv|player|webdav)|claude:|tk ki|gedaechtnis|teilnamen|karten erledigt", z): continue
                k = z[:50].lower()
                if k in seen: continue
                seen.add(k); s.append((len(KEY.findall(z)), z))
            s.sort(key=lambda x: -x[0])
            if s: aus += ["", "Steckbrief (aus Chats und Unterlagen):"] + [f"• {z[:230]}" for _, z in s[:7]]
        except Exception:
            pass
    # 2) Kontakt
    try:
        c = _db(); k = c.execute("select name,email,telefon,kategorie from kontakte_auto where lower(name) like ?", (f"%{ql}%",)).fetchall()
        adr = c.execute("select from_addr,count(*) from msgs where lower(from_name) like ? and is_bulk=0 group by from_addr order by 2 desc limit 2", (f"%{ql}%",)).fetchall()
        kon = [f"{n}: " + ", ".join(x for x in (tel, mail, kat and f"({kat})") if x) for n, mail, tel, kat in k]
        kon += [f"Mail: {a}" for a, _ in adr if a]
        if kon: aus += ["", "Kontakt:"] + [f"• {x}" for x in dict.fromkeys(kon)][:4]
    except Exception:
        c = None
    # 3) Termine, Fristen, offene Punkte
    try:
        import live
        E, _ = live.sammeln(); heute = date.today()
        tr = [live._zeile(x, heute) for x in E if ql in x["text"].lower() or name.lower() in x["text"].lower()]
        if tr: aus += ["", "Termine / offen:"] + tr[:8]
    except Exception:
        pass
    # 4) Mails (neueste zuerst)
    if c:
        try:
            ms = c.execute("""select date_ts,is_sent,from_name,subject,vorschau from msgs where is_bulk=0 and
                 (lower(from_name) like :q or lower(from_addr) like :q or (is_sent=1 and lower(to_addrs) like :q) or lower(subject) like :v) order by date_ts desc""", {"q": f"%{ql}%", "v": f"%{name.lower()}%"}).fetchall()
            if ms:
                erst = datetime.fromtimestamp(ms[-1][0]).strftime("%d.%m.%Y")
                aus += ["", f"Mails: {len(ms)} (seit {erst}), die neuesten:"]
                for ts, ges, von, betr, vor in ms[:6]:
                    aus.append(f"• {datetime.fromtimestamp(ts):%d.%m.%Y} {'du' if ges else 'von ' + (von or '?')[:28]}: {_rein(betr)[:80]}")
        except Exception:
            pass
        # 5) WhatsApp / Telegram
        try:
            na = c.execute("""select n.ts,n.aus_mir,n.text,n.quelle from nachrichten n join chats ch on ch.quelle=n.quelle and ch.chat_id=n.chat_id
                 where lower(ch.name) like ? and n.text<>'' order by n.ts desc limit 5""", (f"%{ql}%",)).fetchall()
            if na:
                aus += ["", "Letzte Nachrichten:"] + [f"• {datetime.fromtimestamp(ts):%d.%m. %H:%M} {'Du' if mir else name.split()[0]} ({qu}): {_rein(t)[:110]}" for ts, mir, t, qu in na]
        except Exception:
            pass
        c.close()
    try:
        g = sqlite3.connect(f"file:{GDB}?mode=ro", uri=True, timeout=3)
        n_ges = g.execute("select count(*) from nachrichten where lower(partner) like ?", (f"%{ql}%",)).fetchone()[0]
        wa = g.execute("select ts,app,ich,text from nachrichten where lower(partner) like ? order by ts desc limit 6", (f"%{ql}%",)).fetchall()
        g.close()
        if wa:
            aus += ["", f"WhatsApp/iMessage ({n_ges} Nachrichten), die letzten:"] + [f"• {datetime.fromtimestamp(int(ts)):%d.%m. %H:%M} {'Du' if ich else name.split()[0]}: {_rein(tx)[:110]}" for ts, app, ich, tx in wa]
    except Exception:
        pass
    # 6) weitere Wiki-Fundstellen (Seitennamen)
    try:
        r = subprocess.run(["grep", "-rlI", "-i", "--include=*.md", "--exclude-dir=raw", "--exclude-dir=_archiv", q, str(WIKI)], capture_output=True, text=True, timeout=5).stdout.split("\n")
        seiten = [Path(p).stem for p in r if p and Path(p).stem not in ("log", "index") and not re.match(r"\d{4}-\d{2}-\d{2}$", Path(p).stem)]
        if e.get("seite"): seiten = [s for s in seiten if s != Path(e["seite"]).stem]
        if seiten: aus += ["", "Steht auch in: " + " · ".join(f"[[{s}]]" for s in seiten[:10])]
    except Exception:
        pass
    if len(aus) == 1:
        return None
    return "\n".join(aus)

if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    t = time.time(); e = erkennen(" ".join(sys.argv[1:]))
    print("erkannt:", e and e["name"], e and e["quellen"])
    if e: print(akte(e))
    print(f"({time.time()-t:.2f} s)")
