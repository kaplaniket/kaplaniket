#!/usr/bin/env python3
"""TK Eisvogel – aus dem ganzen bisherigen Verlauf lernen (Claude 17.11.2026, Auftrag Tekin 06:29:
„Nutze alle Fragen und Informationen, die ich bisher … in unserem ganzen Verlauf im Obsidian-Wiki durchgegangen bin“).

Sammelt jede Frage, die Tekin je gestellt hat, zusammen mit der Antwort, die er damals bekommen hat:
  Littlebird-Chats und Claude-Chats (06 Wiki/raw/transcripts), TK Vogel (~/gedaechtnis/vogel), TK-Vogel-Handy, Karteikarten von TK Eisvogel.
Ergebnis: index/verlauf.jsonl → der Indexer nimmt die Fragen auf. Stellt Tekin dieselbe Frage wieder, zeigt TK Eisvogel sofort:
„Schon einmal gefragt (Quelle, Datum) – Antwort damals: …“. Nichts wird neu formuliert oder erfunden; es ist wörtlich der Verlauf.
Aufruf: verlauf.py [--zeigen]   (läuft auch automatisch im Indexer, wenn sich eine Quelle geändert hat)
"""
import json, os, re, sys, time
from datetime import datetime
from pathlib import Path

H = Path.home()
B = Path("/media/tekin/Disk2/TK-KI")
ZIEL = B / "index/verlauf.jsonl"
ARCHIV = H / "Obsidian/06 Wiki/raw/transcripts"
GEHEIM = re.compile(r"(?i)passw|kennwort|\bpin\b|\btan\b|\bpuk\b|iban|\bDE\d{2}[ \d]{12,}|token|api.?key|k=[0-9a-f]{16,}")
FRAGEWORT = re.compile(r"(?i)^\s*(wer|was|wann|wo|wohin|woher|wie|wieso|warum|weshalb|welche[mnrs]?|wieviel|kann|kannst|ist|sind|war|hat|hast|habe|hab|gibt|gab|wurde|wird|werde|soll|sollte|muss|darf|kennst|weißt|weisst|lohnt|stimmt|brauche|brauch)\b")
AUFTRAG = re.compile(r"(?i)^\s*(!|schreib|schick|sende|mach|erstell|öffne|zeig|such|lösch|start|installier|änder|füge|bau|prüf|repar|richte|leg|trag|verschieb|kopier|lade|merk|notier|hier|ok|ja|nein|danke|weiter|test)\b")
LEER = re.compile(r"(?i)nichts zu (berichten|melden)|nothing to report|keine[nr]? neue[nrs]? ")


def ist_frage(t):
    if not (10 <= len(t) <= 240) or GEHEIM.search(t) or "(Test von Claude)" in t or t.count("http") > 0: return False
    if re.match(r"(?i)^\s*(!|ok\b|test\b|f:)", t) or len(t.split()) < 4: return False
    if re.search(r"(?i)\b(gerade|jetzt|heute|morgen|gestern|aktuell|momentan|eben|vorhin|wie ist die lage)\b|\(test", t): return False   # Momentaufnahmen veralten sofort
    # Rückfragen mitten im Gespräch („und wie kommst du darauf?“, „kannst du dich jetzt verbinden?“) sind ohne das Gespräch nichts wert:
    if re.search(r"(?i)\b(kannst|könntest|hast|bist|wirst|machst|siehst|kommst|meinst|willst|sollst) du\b|\bdu (kannst|hast|bist)\b|^\s*(und|aber|also|okay|ok|nein|ja|doch)\b", t): return False
    anker = [w for i, w in enumerate(re.findall(r"[A-Za-zÄÖÜäöüß0-9\-]{3,}", t)) if (i > 0 and w[0].isupper()) or any(c.isdigit() for c in w)]
    if not anker: return False                                         # kein Name, kein Hauptwort, keine Zahl → kein eigenständiges Thema
    if "?" in t: return True
    return bool(FRAGEWORT.match(t)) and not AUFTRAG.match(t)


def sauber(t, n=650):
    t = re.sub(r"<copyable[^>]*>|</copyable>", "", t)
    t = re.sub(r"`🔧[^`]*`[^\n]*?(?=\s`🔧|\s…\s|$)", "", t)             # Werkzeugaufrufe mitten im Text (Claude-Archiv)
    t = re.sub(r"(?m)^.*🔧.*$|^\s*🗂 .*$|^\s*…\s*", "", t)             # Werkzeugzeilen, Karten-Hinweise
    t = re.sub(r"\[([^\]]+)\]\((https?://[^)]+)\)", r"\1", t)          # Verweise: nur der Text
    t = "\n".join(z.rstrip() for z in t.splitlines() if not GEHEIM.search(z))
    t = re.sub(r"\n{3,}", "\n\n", t).strip()
    if len(t) > n:
        schnitt = max(t.rfind(". ", 0, n), t.rfind("\n", 0, n))
        t = t[:schnitt + 1 if schnitt > n // 2 else n].rstrip() + " …"
    return t


def antwort_waehlen(teile):
    """Von mehreren Antwort-Teilen (erst „Ich schaue kurz nach …“, dann das Ergebnis) den letzten gehaltvollen nehmen."""
    gut = [a for a in teile if len(a.strip()) >= 40]
    if not gut: return ""
    return max(gut[-2:], key=len) if len(gut[-1]) < 120 else gut[-1]


def aus_chats(datei, kopf, sprecher, herkunft):
    """Chat-Archiv im Wiki: Abschnitte je Chat, Wortbeiträge als Zitatblock."""
    aus = []; datum = ""; wer = None; puffer = []; frage = None; antworten = []; titel = ""
    def beitrag_fertig():
        nonlocal frage, antworten
        text = "\n".join(puffer).strip()
        if wer == "tekin":
            if frage and antworten: paar(frage, antworten)
            frage, antworten = (re.sub(r"\s+", " ", text), []) if text else (None, [])
        elif wer == "ki" and frage and text: antworten.append(text)
    def paar(fr, antw):
        a = antwort_waehlen(antw)
        if ist_frage(fr) and a and not LEER.search(titel): aus.append({"frage": fr, "antwort": sauber(a), "zeit": datum, "herkunft": herkunft, "pfad": str(datei), "chat": titel})
    for z in datei.read_text(errors="ignore").splitlines():
        m = kopf.match(z)
        if m:
            beitrag_fertig()
            if frage and antworten: paar(frage, antworten)
            frage, antworten, wer, puffer = None, [], None, []
            datum, titel = m.group(1), (m.group(2) if m.lastindex >= 2 else "")
            continue
        m = sprecher.match(z)
        if m:
            beitrag_fertig(); puffer = []
            wer = "tekin" if "Tekin" in m.group(1) else "ki"
            if m.lastindex >= 2 and re.match(r"\d{4}-\d{2}-\d{2}", m.group(2) or ""): datum = m.group(2)[:10]
            continue
        if z.startswith(">"):
            t = z[1:].lstrip()
            if t not in ("---", "[!chat]- Verlauf öffnen") and not t.startswith("**Chat vom"): puffer.append(t)
    beitrag_fertig()
    if frage and antworten: paar(frage, antworten)
    return aus


def sammeln():
    aus = []
    lb = ARCHIV / "littlebird-chats"
    if lb.is_dir():
        for f in sorted(lb.glob("*.md")):
            aus += aus_chats(f, re.compile(r"^## (\d{4}-\d{2}-\d{2}) · (.*)$"), re.compile(r"^> \*\*(Tekin|Littlebird)\*\* \((\d{2}:\d{2})\):"), "Littlebird-Chat")
    cl = ARCHIV / "claude-chats"
    if cl.is_dir():
        for f in sorted(cl.glob("*.md")):
            aus += aus_chats(f, re.compile(r"^## ((?:\d{4}-\d{2}-\d{2})?)\s*(.*)$"), re.compile(r"^> \*\*(🧑 Tekin|🤖 Claude)\*\* · (\d{4}-\d{2}-\d{2}) \d{2}:\d{2}"), "Claude-Chat")
    # TK Vogel (Fragefenster am iMac, Handy, Telegram)
    for f in sorted((H / "gedaechtnis/vogel").glob("20*.md")):
        for block in re.split(r"(?m)^### ", f.read_text(errors="ignore"))[1:]:
            m = re.search(r"\*\*Frage:\*\* (.*?)\n\n(.*)", block, re.S)
            # ältere Einträge, bei denen Unterlagen an die Frage angehängt waren (dann stünden die als „Antwort“ da), überspringen
            if m and ist_frage(re.sub(r"\s+", " ", m.group(1)).strip()) and len(m.group(2).strip()) >= 40 and not re.match(r"\s*---|\s*(DOKUMENTE|WIKI-AUSZÜGE|HINWEIS VON)", m.group(2)):
                aus.append({"frage": re.sub(r"\s+", " ", m.group(1)).strip(), "antwort": sauber(m.group(2)), "zeit": f.stem, "herkunft": "TK Vogel", "pfad": str(f), "chat": ""})
    # Karteikarten von TK Eisvogel bleiben draußen: darunter sind alte Antworten des kleinen lokalen Modells, auch falsche.
    # gleiche Frage mehrfach gestellt → die neueste Antwort gilt
    norm = lambda t: re.sub(r"[^a-zäöüß0-9]", "", t.lower())
    neueste = {}
    for x in aus:
        if not x["antwort"] or re.search(r"(?i)^(kein zugang|fehler|ich sehe den bildschirm gerade nicht)", x["antwort"]): continue
        k = norm(x["frage"])
        if k not in neueste or x["zeit"] >= neueste[k]["zeit"]: neueste[k] = x
    return sorted(neueste.values(), key=lambda x: x["zeit"])


def quellen_stand():
    """Zeitpunkt der letzten Änderung an einer Quelle (zum Erkennen, ob neu gesammelt werden muss)."""
    t = 0
    for p in list(ARCHIV.rglob("*.md")) + list((H / "gedaechtnis/vogel").glob("20*.md")) + [B / "index/karteikarten.jsonl"]:
        try: t = max(t, p.stat().st_mtime)
        except OSError: pass
    return t


def auffrischen(erzwingen=False):
    """Schreibt index/verlauf.jsonl neu, wenn sich eine Quelle geändert hat. Rückgabe: Anzahl Paare."""
    if not erzwingen and ZIEL.exists() and ZIEL.stat().st_mtime >= quellen_stand():
        return sum(1 for _ in open(ZIEL, encoding="utf-8"))
    paare = sammeln()
    tmp = str(ZIEL) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        for x in paare: f.write(json.dumps(x, ensure_ascii=False) + "\n")
    os.replace(tmp, ZIEL)
    return len(paare)


if __name__ == "__main__":
    t0 = time.time(); n = auffrischen(erzwingen=True)
    from collections import Counter
    alle = [json.loads(z) for z in open(ZIEL, encoding="utf-8")]
    print(f"{n} Fragen mit Antwort aus dem Verlauf ({time.time()-t0:.1f} s):", dict(Counter(x["herkunft"] for x in alle)))
    if "--zeigen" in sys.argv:
        import random; random.seed(3)
        for x in random.sample(alle, min(14, len(alle))): print(f"\n[{x['herkunft']} {x['zeit']}] {x['frage'][:150]}\n   → {' '.join(x['antwort'].split())[:230]}")
