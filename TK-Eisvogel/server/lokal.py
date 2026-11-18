#!/usr/bin/env python3
"""TK Eisvogel – Antworten ohne fremde KI (Claude 17.11.2026, Auftrag Tekin: „nur noch die lokale KI, schnell und genau“).

Grundsatz: Auf dem eigenen Rechner (6 Kerne, keine Grafikkarte) liest ein Sprachmodell nur ~40 Wörter je Sekunde. Deshalb sucht
hier kein Sprachmodell, sondern die Suche selbst – und das Modell bekommt am Ende nur die wenigen besten Sätze:
 1. Begriffe der Frage: die seltensten Wörter (Namen, Nummern, Fachwörter) – ohne KI, aus der Worthäufigkeit des Index.
 2. Speicher von TK Vogel durchsuchen (Volltext über Wiki, 16.000 Dokumente, Mail- und Chat-Archiv) + Mails + Nachrichten.
 3. Die Sätze heraussuchen, die die Frage beantworten: Stichworte + Antwortart (wann → Datum, wie viel → Betrag, wo → Ort/Ordner).
Das Ergebnis sind wörtliche Belege mit Quelle – in Zehntelsekunden. Das Sprachmodell formuliert daraus nur noch einen Satz.
Test: python3 lokal.py "Wie viel Taschengeld bekommt Anna?"
"""
import importlib.util, math, os, re, subprocess, sys
from importlib.machinery import SourceFileLoader
from pathlib import Path

H = Path.home()
STOPPW = set("""wann welche welcher welches welchen meine meinen meiner mein habe hast haben hat hatte steht stehen noch eine einen einem einer über oder und der die das
ist sind war waren von für mit bei zum zur wie was wer wem wen wo wohin woher warum wieso weshalb liegt liegen gibt wird werden wurde kann soll muss denn mal bitte dem den des ein ich mir mich du dir
sein seine seinen ihre ihren ihr laut unterlagen aktuell jetzt gerade genau eigentlich viel viele hoch kurz erkläre erklär sag zeig nenne nenn auf aus an in im am es nicht auch nur schon
mache macht machen tun gehen geht alle alles man sich nach vor bis seit""".split())
FRAGEART = [("wann", r"\bwann\b|\bbis wann\b|\bab wann\b|\bseit wann\b|welche[mnrs]? (datum|tag|uhrzeit)|um wie ?viel uhr"), ("wo", r"\bwo\b|\bwohin\b|\bwoher\b|\bwelche[mnrs]? (ort|adresse|straße)"),
            ("wer", r"\bwer\b|\bwem\b|\bwen\b|\bwessen\b"), ("betrag", r"wie ?viel|wie hoch|wie teuer|was kostet|welche[mnrs]? (betrag|preis|summe)"),
            ("dauer", r"wie lange|wie oft"), ("warum", r"\bwarum\b|\bwieso\b|\bweshalb\b|\bweswegen\b"), ("welche", r"\bwelche[mnrs]?\b"), ("wie", r"\bwie\b"), ("was", r"\bwas\b")]
ANTWORTART = {   # woran man einen Satz erkennt, der diese Frageart beantwortet
    "wann": r"\b\d{1,2}\.\d{1,2}\.(\d{2,4})?|\b\d{4}-\d{2}-\d{2}\b|\b(januar|februar|märz|april|mai|juni|juli|august|september|oktober|november|dezember)\b|\b\d{1,2}:\d{2}\b|\b(19|20)\d{2}\b",
    "betrag": r"\d[\d.,]*\s?(€|eur\b|euro\b)|(€|eur)\s?\d|\b\d+[.,]\d{2}\b|\b\d+\s?(%|prozent)",
    "wo": r"\bstr\.|straße|\b\d{5}\s+[A-ZÄÖÜ]|\bordner\b|/[\w\-]+/|`[^`]+`|\bgemeldet\b|\bwohn(t|haft|ung|sitz)\b|\badresse\b|\banschrift\b",
    "wer": r"\b[A-ZÄÖÜ][a-zäöüß]+\s+[A-ZÄÖÜ][a-zäöüß]+|\b(herr|frau|dr\.)\s",
}
RANG = {"Wiki": 0, "Obsidian": 1, "iCloud-Dokument": 1, "Dokument": 1, "Steuer": 1, "WG 157": 1, "Mail": 2, "Mail-Archiv": 2, "Meeting": 2, "Journal": 3, "Chat-Archiv": 3,
        "WhatsApp": 3, "Claude-Chat": 4, "Littlebird-Chat": 4}
GEHEIM = re.compile(r"(?i)passw|kennwort|\bpin\b|\btan\b|\bpuk\b|iban|\bDE\d{2}[ \d]{12,}|token|api.?key")
_gd = None


def gd():
    """Das Gedächtnis-Modul von TK Vogel (~/bin/gedaechtnis): Volltextsuche, Mails, Nachrichten – alles lokal."""
    global _gd
    if _gd is None:
        sys.path.insert(0, str(H / "bin"))
        l = SourceFileLoader("gd_eisvogel", str(H / "bin/gedaechtnis")); s = importlib.util.spec_from_loader(l.name, l)
        m = importlib.util.module_from_spec(s); l.exec_module(m); _gd = m
    return _gd


def frageart(f):
    f = f.lower()
    for name, muster in FRAGEART:
        if re.search(muster, f): return name
    return ""


def kern(t):
    return {w[:5] for w in re.findall(r"[a-zäöüß0-9]{2,}", t.lower()) if w not in STOPPW}


def begriffe(frage, haeufigkeit=None, n_gesamt=20000, hoechstens=3):
    """Die aussagekräftigsten Wörter der Frage (selten im Wiki = wichtig). haeufigkeit(wort) → in wie vielen Abschnitten es vorkommt."""
    kand, schon = [], set()
    for i, w in enumerate(re.findall(r"[A-Za-zÄÖÜäöüß0-9][\wÄÖÜäöüß\-]*", frage)):
        w = w.strip("-_"); k = w.lower()
        if len(k) < 3 or k in STOPPW or k in schon: continue
        df = haeufigkeit(k) if haeufigkeit else 0
        if df == 0 and k.endswith("s") and len(k) >= 5 and haeufigkeit and haeufigkeit(k[:-1]) > 0:   # „Marias“ → „Maria“
            w, k = w[:-1], k[:-1]; df = haeufigkeit(k)
        gewicht = math.log((n_gesamt + 1) / (df + 1))
        if re.search(r"\d", w): gewicht += 1.5                      # Nummern, Kennzeichen, Jahre
        if w[0].isupper() and i > 0: gewicht += 1.0                 # Namen und Hauptwörter
        if df == 0 and not re.search(r"\d", w): gewicht -= 2.0      # kommt im Wiki gar nicht vor → eher Füllwort oder Tippfehler
        schon.add(k); kand.append((gewicht, w))
    kand.sort(reverse=True)
    return [w for _, w in kand[:hoechstens]]


def _reinigen(t):
    t = re.sub(r"[»«]", "", t)
    t = re.sub(r"\[\[([^\]|]+)\|([^\]]+)\]\]", r"\2", t).replace("**", "")
    return "\n".join(z for z in t.splitlines() if not GEHEIM.search(z))


def speicher_treffer(frage, haeufigkeit=None, n_gesamt=20000, n=6):
    """Volltext-Treffer aus dem Speicher von TK Vogel. Rückgabe: [(Quelle, Text)] – beste zuerst, Wiki und Dokumente vor Chats."""
    bg = begriffe(frage, haeufigkeit, n_gesamt)
    if not bg: return [], []
    roh = []
    for versuch in ([bg[:3], bg[:2], bg[:1]] if len(bg) >= 3 else [bg[:2], bg[:1]] if len(bg) == 2 else [bg]):
        try: roh = gd().speicher_voll(" ".join(versuch), n, 1100)
        except Exception: roh = []
        if roh: break
    aus = []
    for x in roh:
        m = re.match(r"=== \[([^\]]+)\] (.*?) ===\n(.*)", x, re.S)
        if not m: continue
        art, titel, text = m.group(1), m.group(2), _reinigen(m.group(3))
        if re.search(r"(?i)tk-ki|tk-eisvogel|/log\.md|tagesjournal|/journal/|06 Wiki/index\.md", titel): continue     # Arbeitsnotizen über die App selbst, Inhaltsübersicht
        name = Path(titel.split(" › ")[0]).stem if art in ("Wiki", "Obsidian", "Journal", "Meeting") else os.path.basename(titel.split(" › ")[0])
        aus.append((RANG.get(art, 3), art, name, text))
    aus.sort(key=lambda a: a[0])
    return [((name if art in ("Wiki", "Obsidian") else f"{art}: {name}"), text) for _, art, name, text in aus], bg


def post_treffer(frage, bg, n=3):
    """Mails und Nachrichten zum wichtigsten Begriff – nur wenn die Frage danach klingt."""
    if not bg or not re.search(r"(?i)geschrieben|schrieb|geantwortet|antwort von|nachricht von|mail von|whatsapp|gemeldet|gesagt|gekommen|eingegangen", frage): return []
    aus = []
    try:
        for z in gd().mail(bg[0], 3650, n): aus.append(("Mail", _reinigen(z)))
        for z in gd().nachrichten(bg[0], 3650, n): aus.append(("Nachricht", _reinigen(z)))
    except Exception: pass
    return aus


def gesendet_treffer(frage, bg, n=4):
    """„Wurde die Mail … schon gesendet?“ → im Ausgang von TKMail nachsehen (alle Konten), neueste zuerst."""
    if not re.search(r"(?i)gesendet|versendet|verschickt|geschickt|abgeschickt|rausgegangen|raus\b", frage): return []
    w = [x for x in bg if x.lower() not in ("mail", "e-mail", "email", "nachricht")][:3]
    if not w: return []
    import sqlite3, datetime as dt
    try:
        c = sqlite3.connect(f"file:{H}/postamt/postamt.db?mode=ro", uri=True, timeout=3)
        for versuch in ([w, w[:2], w[:1]] if len(w) > 2 else [w, w[:1]] if len(w) > 1 else [w]):
            sql = "select date_ts,to_addrs,subject,acc from msgs where is_sent=1"; par = []
            for x in versuch:
                sql += " and (subject like ? or to_addrs like ? or vorschau like ?)"; par += [f"%{x}%"] * 3
            rows = c.execute(sql + " order by date_ts desc limit ?", par + [n]).fetchall()
            if rows: break
        c.close()
    except Exception:
        return []
    if not rows: return [("Ausgang TKMail", "Im Ausgang von TKMail steht keine gesendete Mail mit " + " und ".join(w) + " – weder im Betreff noch beim Empfänger noch im Text.")]
    return [("Ausgang TKMail", "\n".join(f"Gesendet am {dt.datetime.fromtimestamp(ts):%d.%m.%Y um %H:%M} Uhr an {(an or '?')[:60]}: „{(su or '')[:110]}“ – {' '.join(w)}" for ts, an, su, acc in rows))]


def rueckblick(frage):
    """„Was war gestern los?“ ohne KI: Wiki-Protokoll, Mails und Nachrichten des Tages, sofort. Rückgabe Text oder None."""
    import sqlite3, datetime as dt
    f = frage.lower()
    if not re.search(r"was (war|ist) .*(los|passiert|gewesen|gelaufen)|was hab(e)? ich .*(gemacht|erledigt|geschafft)|was wurde .*(gemacht|erledigt)|rückblick|was gab es", f): return None
    heute = dt.date.today(); tag = None
    if "vorgestern" in f: tag = heute - dt.timedelta(days=2)
    elif "gestern" in f: tag = heute - dt.timedelta(days=1)
    elif re.search(r"\bheute\b", f): tag = heute
    else:
        m = re.search(r"\b(\d{1,2})\.(\d{1,2})\.(\d{4})?", f)
        if m:
            try: tag = dt.date(int(m[3] or heute.year), int(m[2]), int(m[1]))
            except ValueError: return None
        else:
            wt = re.search(r"\b(montag|dienstag|mittwoch|donnerstag|freitag|samstag|sonntag)\b", f)
            if wt:
                nr = ["montag", "dienstag", "mittwoch", "donnerstag", "freitag", "samstag", "sonntag"].index(wt[1])
                tag = heute - dt.timedelta(days=((heute.weekday() - nr) % 7) or 7)
    if not tag: return None
    a = dt.datetime.combine(tag, dt.time()).timestamp(); e = a + 86400
    WT = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"]
    aus = [f"**{WT[tag.weekday()]}, {tag:%d.%m.%Y}** – aus Protokoll, Mails und Nachrichten:"]
    try:    # Wiki-Protokoll: jede erledigte Arbeit steht dort als Zeile
        z = [x for x in (H / "Obsidian/06 Wiki/log.md").read_text(errors="ignore").splitlines() if x.startswith(f"- {tag:%d.%m.%Y}")]
        z = [re.sub(r"^- \d{2}\.\d{2}\.\d{4} ?", "", x) for x in z]
        z = [re.sub(r"^(\d{2}:\d{2}) (Claude|Hermes|TK Vogel): (Claude: |\d{2}\.\d{2}\.\d{4} \d{2}:\d{2} Claude: )?", r"\1 ", x) for x in z if not GEHEIM.search(x)]
        if z: aus += ["", f"Erledigt und festgehalten ({len(z)} Einträge):"] + [f"• {x[:190]}" for x in z[-18:]]
    except Exception: pass
    try:
        c = sqlite3.connect(f"file:{H}/postamt/postamt.db?mode=ro", uri=True, timeout=3)
        ein = c.execute("select from_name,from_addr,subject from msgs where is_bulk=0 and is_sent=0 and date_ts>=? and date_ts<? and folder not in('Trash','Junk','Spam','Werbung') order by date_ts", (a, e)).fetchall()
        ausg = c.execute("select to_addrs,subject from msgs where is_sent=1 and date_ts>=? and date_ts<? order by date_ts", (a, e)).fetchall()
        c.close()
        if ein: aus += ["", f"Mails erhalten ({len(ein)}):"] + [f"• {(n or ad or '?')[:32]}: {(su or '')[:95]}" for n, ad, su in ein[:8]]
        if ausg: aus += ["", f"Mails gesendet ({len(ausg)}):"] + [f"• an {(an or '?')[:40]}: {(su or '')[:95]}" for an, su in ausg[:8]]
    except Exception: pass
    try:
        g = sqlite3.connect(f"file:{H}/gedaechtnis/gedaechtnis.db?mode=ro", uri=True, timeout=3)
        n = g.execute("select partner,count(*) from nachrichten where ts>=? and ts<? group by partner order by 2 desc limit 6", (a, e)).fetchall()
        g.close()
        if n: aus += ["", "Nachrichten (WhatsApp/iMessage): " + ", ".join(f"{p[:28]} ({k})" for p, k in n)]
    except Exception: pass
    if len(aus) == 1: return f"Für {WT[tag.weekday()]}, {tag:%d.%m.%Y} finde ich weder Protokoll-Einträge noch Mails oder Nachrichten."
    return "\n".join(aus)


WERT = {"wann": r"\b\d{1,2}\.\d{1,2}\.\d{4}\b|\b\d{4}-\d{2}-\d{2}\b", "betrag": r"\d[\d.]*,\d{2}\s?(?:€|EUR)(?:/\w+)?|\d[\d.]*\s?(?:€|EUR)(?:/\w+)?"}

def werte(satz, frage):
    """Die Angaben im Satz, nach denen gefragt ist (Datum bei „wann“, Betrag bei „wie viel“) – ohne Doppelte, in Lesereihenfolge."""
    m = WERT.get(frageart(frage))
    return list(dict.fromkeys(x.strip() for x in re.findall(m, satz))) if m else []


def hervorheben(satz, frage):
    """Im Beleg das fett machen, wonach gefragt ist (Datum bei „wann“, Betrag bei „wie viel“)."""
    art = frageart(frage)
    m = {"wann": r"\b\d{1,2}\.\d{1,2}\.\d{2,4}\b|\b\d{4}-\d{2}-\d{2}\b|\b\d{1,2}:\d{2} Uhr\b", "betrag": r"\d[\d.]*,\d{2}\s?(?:€|EUR)|\d[\d.,]*\s?(?:€|EUR)(?:/\w+)?"}.get(art)
    if not m or "**" in satz or "`" in satz: return satz
    return re.sub(m, lambda x: f"**{x.group(0)}**", satz)


def saetze(text):
    teile = [s.strip(" -*|>•\t").replace("**", "") for s in re.split(r"\n+|(?<=[.!?])\s+(?=[A-ZÄÖÜ„\"])", text)]
    aus = []
    for s in teile:
        s = re.sub(r"\s*\|\s*", " · ", s).strip(" ·")          # Tabellenzeilen lesbar machen
        if len(s) < 18 or s.startswith("#") or s.endswith("?") or re.fullmatch(r"[\-·: ]+", s): continue
        if re.match(r"(?i)(title|tags|sources|created|updated|type|confidence|aliases|quelle|siehe auch)\s*:", s): continue    # Kopfzeilen, keine Aussagen
        if s.count("[[") >= 3 and len(re.sub(r"\[\[[^\]]*\]\]|[·:\s]|\w+:", "", s)) < 25: continue                       # reine Verweiszeilen
        if s.count(".pdf") + s.count(".csv") + s.count(".xlsx") >= 3: continue                                               # Dateilisten
        if sum(c.isalpha() for c in s) < len(s) * 0.45: continue                                                             # Zahlenkolonnen, Tabellenreste
        aus.append(s)
    return aus


def belege(frage, stuecke, n=4, auch=""):
    return [(s, q) for s, q, _ in belege_punkte(frage, stuecke, n, auch)]


def belege_punkte(frage, stuecke, n=4, auch=""):
    """Die Sätze, die die Frage beantworten – wörtlich, mit Quelle. stuecke: [(Quelle, Text[, Abschnittsüberschrift])] in Rangfolge.
    Bewertung: Stichworte der Frage im Satz + passt zur Frageart (wann → Datum, wie viel → Betrag …) + Rang der Quelle."""
    fw = kern(frage + " " + auch); art = frageart(frage); muster = ANTWORTART.get(art)     # auch = Synonyme („Frau“ → „Ehefrau Maria“)
    fl0 = frage.lower(); pflicht = None
    if re.search(r"e-?mail-?adresse|mailadresse|welche (e-?mail|mail)\b|e-?mail von|mail-?adresse", fl0):
        pflicht = muster = r"[\w.\-]+@[\w\-]+\.[\w.\-]+"; fw -= kern("e-mail-adresse mailadresse email mail adresse e-mail")
    elif re.search(r"telefonnummer|handynummer|rufnummer|\bnummer von\b|wie erreiche ich|telefon von|handy von", fl0):
        pflicht = muster = r"(?:\+49|\b0)\d{2,4}[ /\-]?\d{3,}[ \d]*"; fw -= kern("telefonnummer handynummer rufnummer nummer telefon handy erreiche")
    if not fw: return []
    noetig = 2 if len(fw) >= 3 else 1
    fl = frage.lower()      # „seit wann“ und „bis wann“ meinen verschiedene Sätze derselben Seite (ausgestellt/seit … ↔ gültig bis …)
    richtung = ("seit" if re.search(r"\bseit wann\b|\bab wann\b|seit welchem|\bbegonnen\b|\bbeginnt\b", fl) else
                "bis" if re.search(r"\bbis wann\b|gültig|läuft .*\baus\b|\bendet\b|\bablauf|\bfrist\b|\bfällig\b", fl) else "")
    kand, gesehen = [], set()
    for rang, st in enumerate(stuecke):
        quelle, text, titel = st[0], st[1], (st[2] if len(st) > 2 else "")
        zeilen = saetze(text)
        ueberschrift = kern(quelle + " " + titel)                    # Seitenname und Abschnittsüberschrift zählen mit
        for i, s in enumerate(zeilen[:60]):
            sk = kern(s)
            treffer = len(fw & sk)
            mit_titel = len(fw & (sk | ueberschrift))               # „Wo wohnt Anna?“: Seite anna-kaplan, Satz „Seit 01.08. gemeldet: …“
            if mit_titel < noetig or (treffer == 0 and not (muster and re.search(muster, s, re.I))): continue
            if pflicht and not re.search(pflicht, s): continue         # gefragt ist die Adresse/Nummer selbst → nur Sätze, die eine enthalten
            punkte = treffer + 0.6 * (mit_titel - treffer)
            if muster and re.search(muster, s, re.I): punkte += 1.6
            if richtung == "seit": punkte += 1.5 if re.search(r"(?i)\b(seit|ab dem|ab \d|beginn|erstmals)\b", s) else (-1.0 if re.search(r"(?i)\bbis\b", s) else 0)
            if richtung == "bis": punkte += 1.5 if re.search(r"(?i)\b(bis|endet|ende|ablauf|läuft aus|zum \d{1,2}\.)", s) else (-1.0 if re.search(r"(?i)\bseit\b", s) else 0)
            punkte -= 0.15 * rang + 0.01 * i
            if quelle == "Ausgang TKMail": punkte += 3                # „schon gesendet?“ beantwortet der Ausgang selbst am besten
            k = re.sub(r"[^a-zäöüß0-9]", "", s.lower())[:60]
            if k in gesehen: continue
            gesehen.add(k); kand.append((punkte, s[:300], quelle))
    kand.sort(key=lambda x: -x[0])
    aus, je = [], {}
    for p, s, q in kand:
        if p < 0.55 * kand[0][0]: break                              # deutlich schwächer als der beste Satz → weglassen statt auffüllen
        if je.get(q, 0) >= 2: continue
        je[q] = je.get(q, 0) + 1; aus.append((s, q, p))
        if len(aus) >= n: break
    return aus


def foto_text(pfad, zeit=60):
    """Text auf einem Foto (Brief, Rechnung) – Texterkennung auf dem eigenen Rechner."""
    try:
        t = subprocess.run(["tesseract", pfad, "-", "-l", "deu", "--psm", "3"], capture_output=True, text=True, timeout=zeit).stdout
        return "\n".join(z.strip() for z in t.splitlines() if z.strip() and not GEHEIM.search(z))[:2500]
    except Exception:
        return ""


if __name__ == "__main__":
    f = " ".join(sys.argv[1:]) or "Wie viel Taschengeld bekommt Anna?"
    import time; t0 = time.time()
    st, bg = speicher_treffer(f)
    print("Frageart:", frageart(f), "| Begriffe:", bg, "| Fundstellen:", [q for q, _ in st])
    for s, q in belege(f, st + post_treffer(f, bg)): print(f" • {s}  ({q})")
    print(f"({time.time()-t0:.2f} s)")
