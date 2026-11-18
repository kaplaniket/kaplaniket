#!/usr/bin/env python3
"""TK Eisvogel – Server, Fassung 3.0 (Claude 17.11.2026, Gesamtprüfung im Auftrag von Tekin).
Eine App aus „TK KI“ (eigene KI auf dem HP) und „TK Vogel“ (Gedächtnis: Wiki, Mails, Nachrichten, Bildschirm, Gespräche).
Läuft auf dem HP (tk-ki-hp), erreichbar nur im Tailnet (EISVOGEL_ADRESSEN, Port 8811) und lokal. Dienst: tk-ki.service.

Weg einer Frage (der erste passende gilt):
 0 Befehle („!…“ → Hermes, „Merk dir …“, Routinen) und Fotos → direkt an TK Vogel
 1 Antwortspeicher (nur bei „Nur lokal“: dieselbe Frage, Unterlagen unverändert) sofort
 2 Termine / Offenes ohne besonderes Thema (live.py)                    sofort
 3 Personen-Akte bei reiner Personenfrage (person.py)                   sofort
 4 Gelerntes: Merkseite tk-ki-gelerntes oder geprüftes Paar aus dem Wiki sofort, wörtlich
 5 TK Vogel (DeepSeek + ganzes Gedächtnis), Antwort läuft stückweise ein – bekommt die Wiki-Treffer der
   Bedeutungssuche und selbst gelesene Dokumente mit (dokumente.py)
 6 lokales Modell (Ollama), wenn „Nur lokal“ gewählt ist oder TK Vogel ausfällt
Einstellungen: index/einstellungen.json · Name/Version/Inhaber: app/marke.json · Aussehen: seiten.py + zusatz.css
"""
import array, base64, json, math, os, re, subprocess, sys, threading, time, urllib.request, urllib.error
from collections import Counter
from datetime import datetime
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse, parse_qs
import numpy as np
import live, person, dokumente, antwortspeicher, seiten, lokal

BASIS = "/media/tekin/Disk2/TK-KI"
H = Path.home()
OLLAMA = "http://127.0.0.1:11434"
EMB_MODELL = "bge-m3"
PORT = int(os.environ.get("EISVOGEL_PORT", "8811"))   # Probelauf: EISVOGEL_PORT=8812 → nur lokal, stört den laufenden Dienst nicht
ADRESSEN = ["127.0.0.1"] + [a for a in os.environ.get("EISVOGEL_ADRESSEN", "").split(",") if a]   # z. B. Tailnet-IP des HP
# Nur unter diesen Namen wird geantwortet (Schutz davor, dass eine fremde Webseite den Browser heimlich hierher schickt)
HOSTS = {"127.0.0.1", "localhost", "tk-ki-hp", "tk-ki-hp.local"} | set(ADRESSEN) | {h for h in os.environ.get("EISVOGEL_HOSTS", "").split(",") if h}
AKTIV = "/tmp/tk-ki-aktiv"
AUSZUG_LEN = 350
MIN_COS = 0.50          # darunter passt eine Unterlage nicht gut genug
GELERNT_COS = 0.84      # ab hier darf ein geprüftes gelerntes Paar wörtlich antworten – zusätzlich müssen Frageart und Stichworte in beide Richtungen passen.
                        # Gemessen 17.11.2026: richtige Treffer 0,85–0,91; falsche („Wo wohnt Anna?“ → „Wo hat Anna 2025 gewohnt?“) bis 0,81.
SYNONYME = {"frau": "ehefrau", "mann": "ehemann", "auto": "fahrzeug kfz", "wohnung": "immobilie miete", "handy": "iphone telefon",
            "geld": "konto bank finanzen", "rechner": "pi hp imac geräte", "steuer": "steuern finanzamt", "arzt": "gesundheit", "vertrag": "verträge abo",
            "wohnt": "gemeldet wohnung adresse anschrift", "wohne": "gemeldet wohnung adresse anschrift", "kostet": "beitrag preis betrag", "tüv": "hu hauptuntersuchung",
            "kennzeichen": "amtliches kennzeichen do", "läuft": "endet vertragsende ablauf gekündigt", "endet": "vertragsende ablauf gekündigt läuft",
            "gekündigt": "kündigung gekündigt", "bezahlt": "überwiesen gezahlt zahlung", "überwiesen": "bezahlt gezahlt zahlung", "telefon": "handy mobil", "nummer": "telefon handy"}
try: SYNONYME.update(json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "privat", "synonyme.json"), encoding="utf-8")))   # Namen der Familie nur auf dem HP
except Exception: pass
WOCHENTAGE = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"]

SYSTEM = """Du bist TK Eisvogel, die persönliche KI von Tekin Kaplan. Du läufst bei ihm zu Hause auf seinem eigenen Rechner, ganz ohne Cloud.

Wie du antwortest:
- Natürlich, freundlich und immer auf Deutsch (niemals Chinesisch oder Englisch, außer Tekin bittet um eine Übersetzung), wie ein kluger Freund. Du duzt Tekin.
- Zuerst die Antwort, dann – nur wenn nötig – kurze Erklärung. Keine Floskeln, keine Wiederholung der Frage.
- Allgemeine Fragen (Wissen, Rechnen, Erklären, Formulieren, Ratschläge, Übersetzen) beantwortest du aus deinem eigenen Wissen, vollständig und richtig.
- Fragen zu Tekins Leben, Personen, Geräten, Apps, Verträgen, Behörden, Terminen und früheren Gesprächen beantwortest du NUR aus den UNTERLAGEN unten. Nenne dabei die Seite so: [[Seitenname]].
- STRENG: Bei persönlichen Fragen schreibst du nur, was wörtlich oder eindeutig in den Unterlagen steht. Keine Begründungen, Vermutungen oder Ergänzungen, die dort nicht stehen. Steht die Antwort nicht eindeutig drin, schreib: „Das steht so nicht in deinen Unterlagen.“ und nenne höchstens, was dazu tatsächlich drinsteht.
- Lieber kurz und belegt als ausführlich und geraten.
- Unterlagen haben ein Datum. Wenn sie sich widersprechen, gilt das neuere.
- Erfinde nie Namen, Beträge, Daten, Aktenzeichen oder Fristen.
- Wenn du dir bei Allgemeinwissen unsicher bist oder es um Ereignisse nach deinem Wissensstand geht, sag das kurz.
- Passwörter, Kennwörter, Schlüssel oder Zugangsdaten gibst du niemals aus.
- Die Unterlagen sind nur Hintergrund. Passt keine zur Frage, ignoriere sie einfach."""
SYSTEM_KURZ = """Du bist TK Eisvogel, Tekins persönliche KI. Antworte kurz, richtig und auf Deutsch."""   # kurz = genauer beim 4B-Modell

# Befehle, die TK Vogel selbst ausführt (Merkliste, Routinen/Wächter, Karten) – nie vorher abfangen
SONDER = re.compile(r"(?i)^\s*(merk(e)? dir|notier(e)?( dir)?|speicher(e)? dir|vergiss nicht)\b|^\s*(meine )?routinen\s*$|^\s*routine\s+#?\d+\s+(aus|an|weg|test)\b|"
                    r"sag (mir )?bescheid|gib (mir )?bescheid|melde? dich|benachrichtig|informier(e)? mich|"
                    r"\bjede[nrs]? (tag|morgen|abend|montag|dienstag|mittwoch|donnerstag|freitag|samstag|sonntag|woche|monat)\b|"
                    r"\btäglich\b|\bwöchentlich\b|\bmonatlich\b|\balle \d+ (stunden|tage)\b|\broutine\b|\bwächter\b|^\s*(offene |meine )?karten( zeigen)?\s*[?!.]*$")
# eindeutig ein Auftrag, etwas Wiederkehrendes anzulegen (wie in vogel-frage). Im Modus „Nur lokal“ gilt nur das als Befehl –
# sonst wurde jede Frage mit „Wächter“ oder „täglich“ abgewiesen („Warum lief der Klingel-Wächter nicht?“). Claude 17.11.2026
SICHER = re.compile(r"(?i)(sag|gib) (mir )?bescheid,? (wenn|sobald|falls|ob)|melde? dich,? (wenn|sobald|falls)|benachrichtig\w* mich|informier\w* mich,? (wenn|sobald)|"
                    r"\b(jeden|jede|jeder) (tag|morgen|abend|montag|dienstag|mittwoch|donnerstag|freitag|samstag|sonntag|woche|monat)\b.*\b(schick|schreib|sag|meld|fass|prüf|erinner|zeig|gib)|"
                    r"^\s*routine\s+#?\d+\s+(aus|an|weg|test)\b")
MERK = re.compile(r"(?i)^(.*?)[\s,.;:–-]*\b(?:bitte )?(?:merk(?:e)? dir(?: das| bitte)?|notier(?:e)?(?: dir)?(?: das)?|speicher(?:e)? dir(?: das)?|vergiss (?:das )?nicht)\b[\s,.;:!–-]*(.*)$", re.S)
AUFTRAG = re.compile(r"(?i)^\s*(kannst|könntest|würdest|kanst) du\b.*\b(sortier|aufräum|aufraeum|lösch|verschieb|schick|sende|schreib|erstell|installier|richte|änder|erledig|kopier|umbenenn|sicher[en ]|leg |trag |buch|bestell|überweis|kündig)")
OHNE_NETZ = re.compile(r"(?i)^\s*(merk(e)? dir|notier(e)?( dir)?|speicher(e)? dir|vergiss nicht)\b|^\s*(meine )?routinen\s*$|^\s*(offene |meine )?karten( zeigen)?\s*[?!.]*$")

IDX = {}
lock = threading.Lock()
RECHNEN = threading.Lock()      # immer nur eine lokale Sprachmodell-Rechnung gleichzeitig (6 Kerne)
LADEN = threading.Lock()
ZUSTAND = {"vogel_fehler": 0.0, "speicher": (0, 0)}


# ───────────────────────── Einstellungen ─────────────────────────
def einstellungen():
    try: return json.load(open(f"{BASIS}/index/einstellungen.json"))
    except Exception: return {"modell": "qwen3:4b-instruct-2507-q4_K_M", "quelle": "vogel"}

def quelle():
    return "lokal" if einstellungen().get("quelle") == "lokal" else "vogel"

def modell(mit_unterlagen=False):
    e = einstellungen()
    if mit_unterlagen and e.get("modell_unterlagen"): return e["modell_unterlagen"]
    return e.get("modell", "qwen3:4b-instruct-2507-q4_K_M")

def einstellungen_schreiben(neu):
    e = einstellungen()
    if neu.get("quelle") in ("vogel", "lokal"): e["quelle"] = neu["quelle"]
    tmp = f"{BASIS}/index/einstellungen.json.tmp"; json.dump(e, open(tmp, "w")); os.replace(tmp, f"{BASIS}/index/einstellungen.json")
    if e.get("quelle") == "lokal": threading.Thread(target=aufwaermen, daemon=True).start()
    return e

def ollama_geladen():
    try: return [m["name"] for m in json.load(urllib.request.urlopen(OLLAMA + "/api/ps", timeout=3))["models"]]
    except Exception: return None

def einstellungen_info():
    e = einstellungen(); m = seiten.marke()
    def zeilen(p):
        try: return sum(1 for _ in open(p))
        except Exception: return 0
    if time.time() - ZUSTAND["speicher"][0] > 300:
        try:
            import sqlite3
            c = sqlite3.connect(f"file:{H}/gedaechtnis/speicher.db?mode=ro", uri=True, timeout=2)
            ZUSTAND["speicher"] = (time.time(), c.execute("select count(*) from stand").fetchone()[0]); c.close()
        except Exception: ZUSTAND["speicher"] = (time.time(), 0)
    return {"quelle": quelle(), "modell_lokal": e.get("modell"), "modell_unterlagen": e.get("modell_unterlagen"), "geladen": ollama_geladen() or [],
            "wissen": IDX.get("stand", {}), "karteikarten": zeilen(KARTEN), "speicher_dateien": ZUSTAND["speicher"][1],
            "rechner": "HP EliteDesk 800 G4 (tk-ki-hp)", "version": f"{m['name']} {m['version']} · {m['stand']}"}

def gesund():
    g = ollama_geladen(); q = quelle()
    if q == "vogel":
        gestoert = time.time() - ZUSTAND["vogel_fehler"] < 300
        return {"ok": True, "bereit": not gestoert or (g is not None), "quelle": q, "geladen": g or [],
                "text": "TK Vogel gerade nicht erreichbar – antworte lokal" if gestoert else "Bereit"}
    bereit = g is not None and modell() in g
    return {"ok": g is not None, "bereit": bereit, "quelle": q, "geladen": g or [],
            "text": "Bereit · nur lokal" if bereit else ("Lokales Modell lädt …" if g is not None else "Ollama antwortet nicht")}


# ───────────────────────── Wissensindex ─────────────────────────
def tokens(t):
    return re.findall(r"[a-zäöüß0-9]{2,}", t.lower())

def laden(erzwingen=False):
    """Index von der Platte holen. Tut nichts, wenn sich die Dateien nicht geändert haben (vorher: jedes Mal alles neu)."""
    with LADEN:
        try: sig = (os.path.getmtime(f"{BASIS}/index/stuecke.json"), os.path.getmtime(f"{BASIS}/index/vektoren.npy"))
        except OSError: return False
        if not erzwingen and IDX.get("sig") == sig: return False
        st = json.load(open(f"{BASIS}/index/stuecke.json")); vek = np.load(f"{BASIS}/index/vektoren.npy")
        if len(st) != len(vek): return False          # Indexer schreibt gerade – beim nächsten Mal
        try: stand = json.load(open(f"{BASIS}/index/stand.json"))
        except Exception: stand = {}
        n = len(st); dl = np.zeros(n, dtype=np.float32); post = {}
        for i, s in enumerate(st):                    # Stichwortsuche: Wort → (Abschnitte, Häufigkeit)
            c = Counter(tokens(s["text"])); dl[i] = sum(c.values())
            for w, tf in c.items():
                e = post.get(w)
                if e is None: e = post[w] = (array.array("i"), array.array("f"))
                e[0].append(i); e[1].append(tf)
        post = {w: (np.frombuffer(a, dtype=np.int32), np.frombuffer(b, dtype=np.float32)) for w, (a, b) in post.items()}
        jetzt = time.time()
        # neuere Seiten bevorzugen (+15 % frisch, klingt über Wochen ab); Chat-Mitschriften nachrangig
        frisch = np.array([1.0 + 0.15 * math.exp(-max(0.0, jetzt - (s.get("geaendert") or 0)) / (30 * 86400)) for s in st], dtype=np.float32)
        roh = np.array([0.8 if "/raw/" in s.get("pfad", "") else 1.0 for s in st], dtype=np.float32)
        gew = np.array([s.get("gewicht", 1.0) for s in st], dtype=np.float32) * frisch * roh
        woertlich = np.array([bool(s.get("quelle") == "Gelernt" and s.get("woertlich")) for s in st])
        verlauf = np.array([s.get("quelle") == "Verlauf" for s in st])       # Tekins frühere Fragen mit der damaligen Antwort
        neu = dict(st=st, vek=vek, post=post, dl=dl, avg=float(dl.mean()) if n else 1.0, n=n, stand=stand, gew=gew, woertlich=woertlich, verlauf=verlauf, sig=sig)
        with lock:
            IDX.clear(); IDX.update(neu)
        return True

def ollama(pfad, daten, stream=False, timeout=900):
    req = urllib.request.Request(OLLAMA + pfad, data=json.dumps(daten).encode(), headers={"Content-Type": "application/json"})
    r = urllib.request.urlopen(req, timeout=timeout)
    return r if stream else json.load(r)

def suchen(frage, k=4, rein=None):
    """Bedeutung (bge-m3) + Stichwort (BM25). rein = die Frage ohne Gesprächsverlauf (für die Prüfung „dieselbe Frage?“).
    Rückgabe: (Treffer, geprüftes gelerntes Paar oder None, früher schon gestellte Frage mit Antwort oder None)."""
    with lock:
        ix = dict(IDX)
    if not ix.get("n"): return [], None, None
    rein = rein or frage
    zus = " ".join(v for w, v in SYNONYME.items() if re.search(r"\b" + w + r"\b", frage.lower()))
    frage_s = (frage + " " + zus).strip()
    q = np.array(ollama("/api/embed", {"model": EMB_MODELL, "input": [frage_s], "keep_alive": -1}, timeout=20)["embeddings"][0], dtype=np.float32)
    q /= np.linalg.norm(q) + 1e-9
    cos = ix["vek"] @ q
    n, dl, avg = ix["n"], ix["dl"], ix["avg"]
    bm = np.zeros(n, dtype=np.float32)
    for w in set(tokens(frage_s)):
        e = ix["post"].get(w)
        if e is None: continue
        idx, tf = e
        idf = math.log(1 + (n - len(idx) + .5) / (len(idx) + .5))
        bm[idx] += idf * tf * 2.2 / (tf + 1.2 * (.25 + .75 * dl[idx] / avg))
    if bm.max() > 0: bm /= bm.max()
    score = (0.7 * cos + 0.3 * bm) * ix["gew"]
    if ix["verlauf"].any(): score = np.where(ix["verlauf"], -1.0, score)     # der Verlauf wird unten eigens geprüft, nicht untergemischt
    st = ix["st"]; aus, je = [], Counter()
    for i in np.argsort(-score)[:k * 8]:
        s = st[i]
        if je[s["pfad"]] >= 2 or cos[i] < MIN_COS: continue
        if s.get("quelle") == "Gelernt":          # höchstens ein gelerntes Paar – sonst verdrängen sie die eigentlichen Wiki-Abschnitte
            if je["#gelernt"]: continue
            je["#gelernt"] += 1
        je[s["pfad"]] += 1
        aus.append(dict(s, score=float(score[i]), cos=float(cos[i])))
        if len(aus) >= k: break
    gelernt = None
    if ix["woertlich"].any():       # nur geprüfte, eindeutige Paare aus Wiki-Seiten kommen für wörtliche Antworten in Frage
        c2 = np.where(ix["woertlich"], cos, -1.0)
        for i in np.argsort(-c2)[:5]:           # nicht nur das ähnlichste: das erste, das wirklich dieselbe Frage ist
            if c2[i] < GELERNT_COS: break
            g = dict(st[i], cos=float(c2[i]))
            if gelernt_passt(rein, g): gelernt = g; break
    frueher = None
    if ix["verlauf"].any():
        c3 = np.where(ix["verlauf"], cos, -1.0)
        for i in np.argsort(-c3)[:5]:
            if c3[i] < 0.80: break
            v = dict(st[i], cos=float(c3[i]))
            if gelernt_passt(rein, v): frueher = v; break
    return aus, gelernt, frueher

def gelernt_passt(frage, g):
    """Ein gelerntes Paar darf nur wörtlich antworten, wenn es wirklich dieselbe Frage ist: gleiche Frageart (wann ≠ wo)
    und die Stichworte passen in beide Richtungen. Ähnlichkeit allein unterscheidet „Wann ist die Prüfung?“ nicht von „Wo ist die Prüfung?“."""
    a, b = lokal.frageart(frage), lokal.frageart(g.get("titel", ""))
    if a and b and a != b: return False
    if not a and g["cos"] < 0.80: return False
    fw, gw = lokal.kern(frage), lokal.kern(g.get("titel", ""))
    ziel = gw | lokal.kern(g.get("seite", "") + " " + g.get("antwort", ""))
    if fw and len(fw & ziel) / len(fw) < 0.6: return False     # die Frage fragt nach etwas, das im Paar gar nicht vorkommt
    if gw and len(gw & fw) / len(gw) < 0.5: return False       # das Paar meint etwas Engeres (anderes Jahr, anderer Zusatz)
    return True

def selbst(frage):
    """Fragen an die App über sich selbst – aus dem geprüften eigenen Stand, sofort, ohne Sprachmodell. Rückgabe Text oder None."""
    f = frage.lower()
    if not re.search(r"\b(du|dich|dir|dein|deine[mnrs]?)\b|\b(die|diese) (app|ki)\b|eisvogel|tk ki\b", f): return None
    w = IDX.get("stand", {}); m = seiten.marke(); q = quelle()
    def lernstand():
        try:
            l = json.load(open(f"{BASIS}/logs/lernstand.json"))[-1]
            return f"Letzte Lernprüfung ({l['zeit']}): {l['richtig']} von {l['fragen']} richtig, erstes Wort im Mittel nach {l['erstes_wort_schnitt']} s."
        except Exception: return ""
    if re.search(r"trainier|lernst|dazugelernt|lernen\b|gelernt", f):
        return (f"Ja, ich lerne laufend weiter – von selbst.\n• Wissen: {w.get('seiten','?')} Wiki-Seiten in {w.get('abschnitte','?')} Abschnitten, Stand {w.get('stand','?')}.\n"
                f"• Gelernte Antworten: {w.get('gelernt','?')}, davon {w.get('gelernt_woertlich','?')} geprüft aus dem Wiki; {w.get('gelernt_veraltet',0)} veraltete werden nicht mehr benutzt.\n"
                f"• Aus deinem Verlauf: {w.get('verlauf',0)} Fragen, die du schon einmal gestellt hast, mit der damaligen Antwort.\n"
                f"• Jede neue oder geänderte Wiki-Seite wird nachgelernt" + (" – in der Einstellung „Nur lokal“ ohne fremde KI, das dauert ein bis zwei Minuten je Abschnitt." if q == "lokal" else ".")
                + ("\n• " + lernstand() if lernstand() else "")
                + "\nDas Sprachmodell selbst wird dadurch nicht klüger; es wächst der Vorrat an geprüften Antworten.")
    if re.search(r"wer bist du|was bist du|wie heißt du|dein name|wie nennst du dich", f):
        return (f"Ich bin {m['name']} (Fassung {m['version']}) – dein Gedächtnis und deine KI in einer App, entstanden aus TK KI und TK Vogel. "
                "Ich laufe bei dir zu Hause auf dem HP EliteDesk und bin nur in deinem eigenen Netz erreichbar.")
    if re.search(r"was kannst du|was kann ich dich fragen|wobei kannst du|wie funktionierst du|was weißt du alles|wissensstand", f):
        return (f"Das kann ich:\n• Termine, Fristen und Offenes – sofort („Was steht am Mittwoch an?“, „Was ist offen?“).\n• Personen – alles zu einem Namen („Wer ist Anna?“).\n"
                "• Fragen zu deinen Unterlagen – Wiki, Dokumente, Mails, Nachrichten, mit Quelle („Wann wurde mein Führerschein ausgestellt?“).\n"
                "• Nachsehen, ob eine Mail gesendet wurde, und Rückblicke („Was war gestern los?“).\n• Dokumente und Fotos lesen (Texterkennung).\n• Merken („Merk dir …“).\n"
                f"Wissen: {w.get('seiten','?')} Wiki-Seiten, {w.get('gelernt','?')} gelernte Antworten, {w.get('verlauf',0)} Fragen aus deinem Verlauf.\n"
                + ("Du hast „Nur lokal“ gewählt: Aufträge an Hermes, neue Routinen und Bilder ohne Text gehen damit nicht." if q == "lokal" else "Aufträge an Hermes: ein „!“ an den Anfang setzen."))
    if re.search(r"welches modell|welche ki|läufst du|wo läufst du|deepseek|(daten|fragen) .*(internet|raus|weiter|verlassen)|\bbist du (lokal|offline|online)\b|arbeitest du (lokal|offline|ohne internet)", f):
        if q == "lokal":
            return (f"Du hast „Nur lokal – privat“ gewählt: Deine Fragen bleiben auf dem eigenen Rechner (HP EliteDesk). Suche und Belege laufen ohne Sprachmodell; "
                    f"den zusammenfassenden Satz schreibt das lokale Modell {modell()}. Hermes, Routinen und das Fragefenster von TK Vogel am iMac arbeiten unabhängig davon weiter über DeepSeek.")
        return (f"Du hast „TK Vogel – schnell“ gewählt: Freie Fragen gehen mit den passenden Auszügen an DeepSeek (Internet). Termine, Offenes, Personen-Akten und Gelerntes "
                f"beantworte ich ohne das Internet. Ganz ohne fremde KI: Reiter Einstellungen › „Nur lokal – privat“ (lokales Modell {modell()}).")
    return None

def heute():
    d = datetime.now()
    return f"{WOCHENTAGE[d.weekday()]}, {d:%d.%m.%Y}, {d:%H:%M} Uhr"


# ───────────────────────── TK Vogel ─────────────────────────
class KartenFilter:
    """Gibt den einlaufenden Text sofort weiter – außer Zeilen „KARTE: {…}“ (Aktionskarten; die legt TK Vogel an)."""
    def __init__(self, aus): self.aus, self.z, self.raus, self.gesamt = aus, "", 0, []
    def _los(self):
        if len(self.z) > self.raus:
            t = self.z[self.raus:]; self.raus = len(self.z); self.gesamt.append(t); self.aus(t)
    def rein(self, t):
        for teil in re.split(r"(\n)", t):
            if not teil: continue
            if teil == "\n":
                if not self.z.lstrip().startswith("KARTE:"):
                    self._los(); self.gesamt.append("\n"); self.aus("\n")
                self.z, self.raus = "", 0; continue
            self.z += teil; k = self.z.lstrip()
            if not k or k.startswith("KARTE:") or "KARTE:".startswith(k): continue      # könnte eine Karten-Zeile werden → zurückhalten
            self._los()
    def text(self): return "".join(self.gesamt)

def vogel_frage(frage, verlauf, aus, test=False, bild=None, zeit=120, zusatz=""):
    """Frage an TK Vogel (~/bin/vogel-frage). Text läuft über aus(teil) stückweise ein. Rückgabe: fertige Antwort oder None."""
    vl, v = [], list(verlauf or [])
    for i in range(0, len(v) - 1, 2):
        if v[i].get("role") == "user": vl.append({"frage": str(v[i].get("content", ""))[:500], "antwort": str(v[i + 1].get("content", ""))[:800]})
    auftrag = {"frage": frage, "unterwegs": True, "app": seiten.marke()["name"], "herkunft": seiten.marke()["name"], "verlauf": vl, "test": bool(test)}
    if bild: auftrag["bild_lokal"] = bild
    if zusatz: auftrag["zusatz"] = zusatz      # Unterlagen getrennt von der Frage (sonst deutet TK Vogel Wörter daraus als Teil der Frage)
    p = None
    try:
        p = subprocess.Popen(["/usr/bin/python3", str(H / "bin/vogel-frage")], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                             text=True, env=dict(os.environ, VOGEL_STROM="1"))
        waechter = threading.Timer(zeit, p.kill); waechter.daemon = True; waechter.start()
        p.stdin.write(json.dumps(auftrag)); p.stdin.close()
        filt, fertig, klartext = KartenFilter(aus), None, []
        for zeile in p.stdout:
            try:
                o = json.loads(zeile)
                if not isinstance(o, dict): raise ValueError
            except Exception:
                klartext.append(zeile); continue
            if "t" in o: filt.rein(str(o["t"]))
            if "fertig" in o: fertig = str(o["fertig"])
        p.wait(timeout=5); waechter.cancel()
        t = (fertig if fertig is not None else "".join(klartext)).strip()
        t = re.sub(r"\n*🗂 (\d+) Karte\(n\) bereit.*$", lambda m: f"\n\n({m.group(1)} Aktionskarte{'n' if m.group(1) != '1' else ''} angelegt – im Reiter „Karten“ freigeben)", t, flags=re.S)
        if len(t) < 2 or t.lower().startswith(("traceback", "fehler:")):
            ZUSTAND["vogel_fehler"] = time.time(); return None
        ZUSTAND["vogel_fehler"] = 0.0
        if t != filt.text().strip(): aus(None, ersetzen=t)        # endgültige Fassung (Karten-Hinweis, bereinigt)
        return t
    except (BrokenPipeError, ConnectionResetError):
        raise
    except Exception:
        ZUSTAND["vogel_fehler"] = time.time(); return None
    finally:
        try:
            if p and p.poll() is None: p.kill()
        except Exception: pass

VOGEL = "http://127.0.0.1:8796"
VOGEL_GET = {"/karten", "/gespraeche", "/mitschriften", "/imac", "/mehr", "/api/suche", "/api/termine", "/api/imac", "/api/imac.jpg"}
VOGEL_POST = {"/karten", "/api/mitschrift", "/api/mitschrift-loeschen", "/api/routine"}

def _vogel_schluessel():
    sys.path.insert(0, str(H / "bin"))
    import karten as _k
    return _k.schluessel()

def vogel_weiter(handler, methode, pfad_q, body=None):
    """Leitet eine TK-Vogel-Seite durch (der Zugangsschlüssel wird hier ergänzt) und passt Name, Reiter und Aussehen an."""
    code = 200
    try:
        h = {"Cookie": "vk=" + _vogel_schluessel()}
        if body is not None: h["Content-Type"] = handler.headers.get("Content-Type", "application/x-www-form-urlencoded")
        r = urllib.request.urlopen(urllib.request.Request(VOGEL + pfad_q, data=body, method=methode, headers=h), timeout=120)
        daten, typ = r.read(), r.headers.get("Content-Type", "text/html; charset=utf-8")
    except urllib.error.HTTPError as e:
        daten, typ, code = e.read(), e.headers.get("Content-Type", "text/html"), e.code
    except Exception as e:
        daten = (seiten.kopf("Nicht erreichbar", "") + f"<main><div class=leer>Dieser Bereich antwortet gerade nicht ({seiten.E(e)}). "
                 "Der Dienst „karten-web“ auf dem Rechner läuft vermutlich nicht.</div></main>" + seiten.fuss("")).encode()
        typ, code = "text/html; charset=utf-8", 502
    if typ.startswith("text/html") and b"<nav class=tabs" in daten:
        daten = seiten.vogel_umbauen(daten.decode("utf-8", "replace"), pfad_q.split("?")[0]).encode()
    handler.antwort(code, typ, daten)


# ───────────────────────── Karteikarten und Protokoll ─────────────────────────
KARTEN = f"{BASIS}/index/karteikarten.jsonl"   # jede Frage + Antwort als Karteikarte (Auftrag Tekin 16.11.2026)
_klock = threading.Lock()

def bewertung(frage, text, gut):
    """👍: Antwort gilt als richtig → im Antwortspeicher als „von Tekin bestätigt“ (auch für „Nur lokal“).
    👎: Antwort raus aus dem Speicher, Frage+Antwort auf die Fehlerliste im Wiki (themen/tk-ki-fehler.md) – dort wird sie geprüft und korrigiert."""
    if not frage.strip() or not text.strip(): return {"fehler": "leer"}
    with open(f"{BASIS}/index/bewertungen.jsonl", "a") as f:
        f.write(json.dumps({"zeit": time.strftime("%Y-%m-%d %H:%M:%S"), "frage": frage, "text": text, "gut": gut}, ensure_ascii=False) + "\n")
    k = antwortspeicher.schluessel(frage)
    if gut:
        try: antwortspeicher.ablegen(frage, text, [{"seite": "von Tekin bestätigt"}], [])
        except Exception: pass
        return {"ok": True, "meldung": "Gemerkt – diese Antwort gilt als richtig."}
    try:
        with antwortspeicher._lock:
            antwortspeicher._laden().pop(k, None); antwortspeicher._speichern()
    except Exception: pass
    p = Path.home() / "Obsidian/06 Wiki/themen/tk-ki-fehler.md"
    if not p.exists():
        p.write_text("---\ntitle: TK KI – von Tekin als falsch markierte Antworten\n---\n# TK KI – falsche Antworten\n"
                     "Hier landet jede Antwort, die Tekin mit 👎 markiert. Claude prüft sie, korrigiert die Quelle im Wiki und hakt ab.\n\n")
    with open(p, "a") as f:
        f.write(f"- [ ] {time.strftime('%d.%m.%Y %H:%M')} **Frage:** {frage.strip()[:300]}\n  **Antwort (falsch):** {' '.join(text.split())[:600]}\n")
    return {"ok": True, "meldung": "Danke – als falsch markiert und zum Korrigieren notiert."}

def karte_ablegen(frage, text, quellen):
    text = (text or "").strip()
    if not frage or not text: return
    neu = {"zeit": time.strftime("%Y-%m-%d %H:%M"), "frage": frage, "antwort": text, "quellen": [q.get("seite") for q in (quellen or []) if q.get("seite")]}
    with _klock:
        try:
            with open(KARTEN, "rb") as f:               # dieselbe Frage mit derselben Antwort nicht doppelt ablegen
                f.seek(max(0, os.path.getsize(KARTEN) - 20000)); letzte = f.read().decode("utf-8", "replace").strip().split("\n")[-1]
            l = json.loads(letzte)
            if l.get("frage") == frage and l.get("antwort") == text: return
        except Exception: pass
        with open(KARTEN, "a", encoding="utf-8") as f: f.write(json.dumps(neu, ensure_ascii=False) + "\n")

def karten_suchen(q="", n=200):
    try: alle = [json.loads(z) for z in open(KARTEN, encoding="utf-8") if z.strip()]
    except Exception: return []
    alle.reverse()
    if q:
        w = re.findall(r"[a-zäöüß0-9]{2,}", q.lower())
        alle = [k for k in alle if all(x in (k.get("frage", "") + " " + k.get("antwort", "") + " " + " ".join(k.get("quellen") or [])).lower() for x in w)]
    return alle[:n]

def protokoll(eintrag):
    try:
        with open(f"{BASIS}/logs/fragen.jsonl", "a") as f: f.write(json.dumps(eintrag, ensure_ascii=False) + "\n")
    except Exception: pass


# ───────────────────────── Webserver ─────────────────────────
STATISCH = {"/app.js": ("app.js", "text/javascript; charset=utf-8"), "/zusatz.css": ("zusatz.css", "text/css; charset=utf-8"),
            "/icon.png": ("icon.png", "image/png"), "/apple-touch-icon.png": ("icon.png", "image/png"), "/favicon.ico": ("icon.png", "image/png")}

class Anfrage(BaseHTTPRequestHandler):
    server_version = "TKEisvogel/3"
    def log_message(self, *a): pass

    def antwort(self, code, typ, body, halten=0):
        b = body if isinstance(body, bytes) else body.encode()
        self.send_response(code); self.send_header("Content-Type", typ); self.send_header("Content-Length", str(len(b)))
        self.send_header("Cache-Control", f"private, max-age={halten}" if halten else "no-store")
        self.send_header("X-Content-Type-Options", "nosniff"); self.send_header("Referrer-Policy", "no-referrer"); self.send_header("X-Frame-Options", "DENY")
        self.end_headers()
        if self.command != "HEAD": self.wfile.write(b)

    def js(self, obj, code=200):
        self.antwort(code, "application/json; charset=utf-8", json.dumps(obj, ensure_ascii=False))

    def _name_ok(self, wert):
        return (wert or "").rsplit("@", 1)[-1].split(":")[0].strip("[]").lower() in HOSTS

    def erlaubt(self):
        """Nur der eigene Name, und Schreibzugriffe nur von den eigenen Seiten (nicht von fremden Webseiten im selben Browser)."""
        if not self._name_ok(self.headers.get("Host")):
            self.antwort(403, "text/plain; charset=utf-8", "Unbekannter Name. TK Eisvogel antwortet nur unter seiner eigenen Adresse."); return False
        if self.command == "POST":
            o = self.headers.get("Origin")
            if o is not None and not self._name_ok(urlparse(o).netloc):
                self.antwort(403, "text/plain; charset=utf-8", "Abgelehnt: Anfrage kommt von einer fremden Seite."); return False
        return True

    def koerper(self, grenze=12_000_000):
        n = int(self.headers.get("Content-Length") or 0)
        if n > grenze: raise ValueError("zu groß")
        return self.rfile.read(n) if n else b""

    def do_HEAD(self): self.do_GET()

    def do_GET(self):
        if not self.erlaubt(): return
        u = urlparse(self.path); p = u.path
        try:
            if p in VOGEL_GET: return vogel_weiter(self, "GET", self.path)
            if p in ("/", "/index.html"): return self.antwort(200, "text/html; charset=utf-8", seiten.seite_fragen())
            if p == "/einstellungen": return self.antwort(200, "text/html; charset=utf-8", seiten.seite_einstellungen())
            if p in seiten.RECHT: return self.antwort(200, "text/html; charset=utf-8", seiten.RECHT[p]())
            if p == "/stil.css": return self.antwort(200, "text/css; charset=utf-8", seiten.stil(), halten=86400 if u.query else 0)
            if p in STATISCH:
                datei, typ = STATISCH[p]
                return self.antwort(200, typ, open(f"{BASIS}/app/{datei}", "rb").read(), halten=86400 if (u.query or typ == "image/png") else 0)
            if p == "/schrift.woff2":
                f = H / "gedaechtnis/vogel/schrift.woff2"
                return self.antwort(200, "font/woff2", f.read_bytes(), halten=2592000) if f.exists() else self.antwort(404, "text/plain", "")
            if p == "/manifest.json": return self.antwort(200, "application/manifest+json", seiten.manifest())
            if p == "/robots.txt": return self.antwort(200, "text/plain", "User-agent: *\nDisallow: /\n")
            if p == "/api/karten": return self.js(karten_suchen((parse_qs(u.query).get("q") or [""])[0]))
            if p == "/api/gesund": return self.js(gesund())
            if p == "/api/stand": return self.js(dict(IDX.get("stand", {}), modell=modell(), quelle=quelle()))
            if p == "/api/einstellungen": return self.js(einstellungen_info())
            self.antwort(404, "text/html; charset=utf-8", seiten.kopf("Nicht gefunden", "") + "<main><div class=leer>Diese Seite gibt es nicht. <a href='/'>Zu den Fragen</a></div></main>" + seiten.fuss(""))
        except (BrokenPipeError, ConnectionResetError):
            pass
        except Exception as e:
            try: self.antwort(500, "text/plain; charset=utf-8", f"Fehler: {e}")
            except Exception: pass

    def do_POST(self):
        if not self.erlaubt(): return
        p = urlparse(self.path).path
        try:
            if p == "/vogel/api/frage": return vogel_weiter(self, "POST", "/api/frage", self.koerper())
            if p in VOGEL_POST: return vogel_weiter(self, "POST", self.path, self.koerper())
            if p == "/api/speicher-leeren": antwortspeicher.leeren(); return self.js({"ok": True})
            if p == "/api/neu-laden":
                self.koerper(); laden(); return self.js(IDX.get("stand", {}))
            if p == "/api/einstellungen":
                try: d = json.loads(self.koerper() or b"{}")
                except Exception: return self.js({"fehler": "ungültige Eingabe"}, 400)
                return self.js(einstellungen_schreiben(d if isinstance(d, dict) else {}))
            if p == "/api/bewertung":       # 👍/👎 unter jeder Antwort – Tekin sagt, was gut und was falsch war (Claude 17.11.2026)
                try: d = json.loads(self.koerper() or b"{}"); assert isinstance(d, dict)
                except Exception: return self.js({"fehler": "ungültige Eingabe"}, 400)
                return self.js(bewertung(str(d.get("frage", ""))[:2000], str(d.get("text", ""))[:20000], bool(d.get("gut"))))
            if p == "/api/frage":
                try: d = json.loads(self.koerper() or b"{}"); assert isinstance(d, dict)
                except Exception: return self.js({"fehler": "ungültige Eingabe"}, 400)
                return self.frage(d)
            self.antwort(404, "text/plain; charset=utf-8", "nicht gefunden")
        except (BrokenPipeError, ConnectionResetError):
            pass
        except Exception as e:
            try: self.antwort(500, "text/plain; charset=utf-8", f"Fehler: {e}")
            except Exception: pass

    def modell_strom(self, nachrichten, senden, mit_unterlagen, dauerhaft, hoechstens=300):
        """Lokales Sprachmodell (Ollama), Antwort läuft stückweise ein. Immer nur eine Rechnung gleichzeitig."""
        if not RECHNEN.acquire(blocking=False):
            senden({"status": "Warte kurz – beantworte noch eine andere Frage …"}); RECHNEN.acquire()
        r = None
        try:
            for versuch in (1, 2):      # qwen rutscht selten ins Chinesische: erkennen, verwerfen, einmal strenger wiederholen
                if versuch == 2: nachrichten = nachrichten[:-1] + [{"role": "user", "content": nachrichten[-1]["content"] + "\n(Antworte ausschließlich auf Deutsch.)"}]
                probe = getattr(self, "probe", None) or {}
                opt = {"temperature": 0.0, "num_ctx": 4096, "num_predict": hoechstens}
                if probe.get("threads"): opt["num_thread"] = probe["threads"]
                r = ollama("/api/chat", {"model": probe.get("modell") or modell(mit_unterlagen), "messages": nachrichten, "stream": True,
                                          "keep_alive": "10m" if probe.get("modell") else (-1 if dauerhaft else "30m"), "think": False, "options": opt}, stream=True)
                fremd = False; stuecke = []
                for zeile in r:
                    teil = json.loads(zeile); txt = teil.get("message", {}).get("content", "")
                    if txt and versuch == 1 and re.search(r"[\u3040-\u30ff\u4e00-\u9fff\uac00-\ud7af]", txt):
                        fremd = True; r.close(); break
                    if txt: stuecke.append(txt); senden({"t": txt})
                    if teil.get("error"): senden({"fehler": teil["error"]})
                    if teil.get("done"): break
                if not fremd: break
                senden({"zurueck": len("".join(stuecke)), "status": "Formuliere neu …"})
        finally:
            try: r.close()
            except Exception: pass
            RECHNEN.release()

    # ---------- eine Frage beantworten ----------
    def frage(self, daten):
        frage = str(daten.get("frage") or "").strip()[:4000]
        verlauf = [m for m in (daten.get("verlauf") or []) if isinstance(m, dict)][-6:]
        test = bool(daten.get("test"))
        self.send_response(200); self.send_header("Content-Type", "application/x-ndjson; charset=utf-8")
        self.send_header("Cache-Control", "no-store"); self.send_header("X-Accel-Buffering", "no"); self.end_headers()
        t0 = time.time(); z = {"text": [], "quellen": [], "erst": None, "weg": ""}
        def senden(obj):
            if obj.get("zurueck"):          # verworfene Formulierung: die letzten n Zeichen zurücknehmen
                alt = "".join(z["text"]); obj = dict(obj, reset=True, t=alt[:len(alt) - obj.pop("zurueck")])
            if obj.get("reset"): z["text"].clear()
            if obj.get("t"):
                if z["erst"] is None: z["erst"] = round(time.time() - t0, 2)
                z["text"].append(obj["t"])
            if "quellen" in obj: z["quellen"] = obj["quellen"] or []
            self.wfile.write((json.dumps(obj, ensure_ascii=False) + "\n").encode()); self.wfile.flush()
        def strom(teil, ersetzen=None):
            if ersetzen is not None: senden({"reset": True, "t": ersetzen})
            elif teil: senden({"t": teil})
        def fertig(weg):
            z["weg"] = weg; senden({"fertig": True, "weg": weg})
        try:
            if not frage and not daten.get("bild"):
                senden({"fehler": "Die Frage ist leer"}); return
            try: open(AKTIV, "w").close()            # Training und Indexer machen Platz, solange Tekin fragt
            except Exception: pass
            lokal_modus = (str(daten.get("quelle")) if test and daten.get("quelle") else quelle()) == "lokal"   # Prüflauf darf den Weg vorgeben
            self.probe = {"modell": str(daten["modell"]) if test and daten.get("modell") else None, "threads": int(daten["threads"]) if test and daten.get("threads") else None}
            # Foto vom Handy ablegen
            bild = None
            if daten.get("bild"):
                try:
                    roh = base64.b64decode(str(daten["bild"]).split(",", 1)[-1]); ordner = H / "gedaechtnis/vogel/handy-fotos"; ordner.mkdir(parents=True, exist_ok=True)
                    bild = str(ordner / f"{datetime.now():%Y-%m-%d_%H%M%S}.jpg"); open(bild, "wb").write(roh)
                except Exception: bild = None
                if not frage: frage = "Was ist auf dem Foto, und was muss ich tun?"

            # 0) Befehle und Fotos: direkt an TK Vogel (nichts davor darf sie abfangen)
            mm = None if frage.startswith("!") else MERK.match(frage)
            if mm and (mm.group(1).strip() or mm.group(2).strip()) and "?" not in frage:      # Merken, egal wo „merk dir“ im Satz steht
                inhalt = (mm.group(2).strip() or mm.group(1).strip()).strip(" .,;:")
                if len(inhalt) >= 4: frage = "Merk dir: " + inhalt
            befehl = frage.startswith("!") or bool((SICHER.search(frage) or OHNE_NETZ.search(frage)) if lokal_modus else SONDER.search(frage))
            if lokal_modus and not befehl and AUFTRAG.search(frage):      # ein Auftrag ist keine Frage – nicht das kleine Modell raten lassen
                senden({"t": "Das ist ein Auftrag, keine Frage – ausführen kann ich selbst nichts. Zwei Wege:\n• Hermes: ein „!“ davor setzen. Das geht nur mit „TK Vogel – schnell“ (Reiter Einstellungen), weil Hermes über das Internet arbeitet.\n"
                             "• Claude im Claude-Chat, für alles Größere.\nFragen dazu beantworte ich gern, zum Beispiel wo etwas liegt oder was dazu im Wiki steht."}); return fertig("hinweis")
            if bild and lokal_modus and not befehl:      # Foto ohne fremde KI: Text erkennen, lokales Modell wertet aus
                senden({"status": "Lese das Foto (Texterkennung auf dem eigenen Rechner) …"})
                ft = lokal.foto_text(bild)
                if len(ft) < 30:
                    senden({"t": "Auf dem Foto konnte ich keinen Text erkennen. Bitte näher herangehen, gerade halten und für gutes Licht sorgen. "
                                 "Bilder ohne Text (Gegenstände, Bildschirme) versteht nur „TK Vogel – schnell“."}); return fertig("hinweis")
                senden({"quellen": [{"seite": "Foto (Texterkennung)"}], "status": "Werte den Text aus …"})
                self.modell_strom([{"role": "system", "content": SYSTEM_KURZ}, {"role": "user", "content":
                    f"Heute ist {heute()}.\nTEXT AUF DEM FOTO (Texterkennung, kann Lesefehler enthalten):\n{ft[:1800]}\n\nFRAGE: {frage}\n\n"
                    "Sag kurz: Was ist das, von wem, welche Beträge und Fristen stehen darin, was ist zu tun? Nur was im Text steht, nichts ergänzen."}], senden, True, True, 260)
                return fertig("lokal-foto")
            if befehl or bild:
                if lokal_modus and not OHNE_NETZ.search(frage):
                    senden({"t": "Das geht nur mit TK Vogel: Aufträge an Hermes, neue Routinen und Fotos laufen über das Internet (DeepSeek). "
                                 "Du hast „Nur lokal – privat“ gewählt. Umschalten: Reiter Einstellungen › „TK Vogel – schnell“."}); return fertig("hinweis")
                senden({"status": "Hermes arbeitet – das kann ein paar Minuten dauern …" if frage.startswith("!") else ("Sehe mir das Foto an …" if bild else "Wird erledigt …")})
                va = vogel_frage(frage, verlauf, strom, test=test, bild=bild, zeit=640 if frage.startswith("!") else 150)
                if va is None: senden({"fehler": "TK Vogel hat nicht geantwortet"}); return
                senden({"quellen": [{"seite": "Hermes" if frage.startswith("!") else "TK Vogel"}]}); return fertig("befehl")

            sa = selbst(frage)
            if sa:
                senden({"quellen": [{"seite": "eigener Stand"}]}); senden({"t": sa}); return fertig("selbst")
            if lokal_modus:                       # Rückblick auf einen Tag ohne KI (mit TK Vogel fasst DeepSeek zusammen)
                rb = lokal.rueckblick(frage)
                if rb:
                    senden({"quellen": [{"seite": "Wiki-Protokoll"}, {"seite": "TKMail"}, {"seite": "Nachrichten"}]}); senden({"t": rb}); return fertig("rueckblick")

            # 1) Antwortspeicher
            gm = antwortspeicher.holen(frage) if (lokal_modus and not verlauf) else None
            if gm:
                senden({"quellen": gm.get("quellen") or []}); senden({"t": gm["text"]}); return fertig("speicher")

            # 2) Termine / Offenes
            vorspann = ""
            art = live.absicht(frage)
            if art:
                if not live.thema(frage):       # allgemeine Frage → ganze Liste, sofort, ohne Sprachmodell
                    senden({"quellen": [{"seite": "Kalender"}, {"seite": "TKMail-Fristen"}, {"seite": "Karten"}, {"seite": "offene-punkte"}]})
                    senden({"t": live.antwort(art, frage)}); return fertig("termine")
                zeilen = live.zum_thema(frage)  # Frage mit Thema („Termin beim Finanzamt“) → passende Einträge zeigen, dann richtig antworten
                if zeilen: vorspann = "Dazu in Kalender, Fristen und Offenem:\n" + "\n".join(zeilen) + "\n\n—\n"

            # 3) Person
            pe = person.erkennen(frage); pakte = person.akte(pe) if pe else None
            if pakte:
                rest = re.sub(r"(?i)\b(" + "|".join(re.escape(w) for w in pe["name"].split()) + r")s?\b", "", frage)
                rest = [w for w in re.findall(r"[a-zäöüß]{3,}", rest.lower()) if w not in person.STOPP and w not in person.FUELL and w not in ("mit", "los", "denn", "eigentlich", "akte", "zeig", "alles")]
                if not rest:                    # reine Personenfrage → ganze Akte
                    senden({"quellen": [{"seite": "Personen-Akte"}, {"seite": "Wiki"}, {"seite": "Kontakte"}, {"seite": "Mails"}, {"seite": "Nachrichten"}]})
                    senden({"t": pakte}); return fertig("akte")

            # 4) Wiki-Suche; Gelerntes wörtlich
            senden({"status": "Schaue in deine Unterlagen …"})
            vor = " ".join(str(m.get("content", "")) for m in verlauf if m.get("role") == "user")[-300:]
            try: treffer, gelernt, frueher = suchen((vor + " " + frage).strip(), rein=frage)
            except Exception: treffer, gelernt, frueher = [], None, None        # Suche gestört (Ollama startet neu) → TK Vogel sucht selbst
            frueher_text = ""
            if frueher and not verlauf:
                try: datum = datetime.strptime(frueher.get("zeit", "")[:10], "%Y-%m-%d").strftime("%d.%m.%Y")
                except Exception: datum = frueher.get("zeit", "")
                frueher_text = f"Schon einmal gefragt ({frueher['seite']}, {datum}): „{frueher['titel']}“\nAntwort damals:\n{frueher['antwort']}"
            # Arbeitsnotizen über die App selbst (enthalten die Prüffragen wörtlich) und Tagesprotokolle sind keine Belege;
            # gelernte Paare zählen nur, wenn sie wirklich dieselbe Frage meinen („Wo wohnt Anna?“ ≠ „Wo hat Anna 2025 gewohnt?“)
            treffer = [t for t in treffer if t["seite"] not in ("tk-ki", "tk-eisvogel", "log", "tagesjournal", "index") and "/journal/" not in t.get("pfad", "")
                       and (t.get("quelle") != "Gelernt" or (t["cos"] >= 0.72 and gelernt_passt(frage, t)))]
            quellen = [{"seite": t["seite"], "titel": t.get("titel", ""), "quelle": t["quelle"]} for t in treffer if t.get("quelle") != "Gelernt"]
            wiki = [t for t in treffer if t.get("quelle") != "Gelernt"]     # die von Hand gepflegte Merkseite geht vor automatisch Gelerntem
            g = wiki[0] if wiki and wiki[0]["seite"] == "tk-ki-gelerntes" and wiki[0]["cos"] >= 0.60 and wiki[0].get("titel") else None
            if g and not gelernt_passt(frage, dict(g, cos=max(g["cos"], 0.80), antwort=g["text"])): g = None      # … und nur bei derselben Frage
            if g and not verlauf:
                antw = "\n".join(x for x in g["text"].split("\n")[1:] if not x.startswith("#")).strip().replace("**", "")
                senden({"quellen": [{"seite": "tk-ki-gelerntes"}]}); senden({"t": vorspann + antw}); return fertig("gelerntes")
            if gelernt and not verlauf and gelernt_passt(frage, gelernt):
                senden({"quellen": [{"seite": gelernt["seite"]}]})
                senden({"t": vorspann + gelernt["antwort"] + f"\n\n(gelernt aus [[{gelernt['seite']}]])"}); return fertig("gelernt")
            if vorspann: senden({"t": vorspann})
            schon = "".join(z["text"])            # was bis hier gezeigt wurde, bleibt stehen, wenn die Antwort ersetzt wird
            kurzakte = [x for x in pakte.split("\n") if x.strip()][1:7] if pakte else []

            # 5) TK Vogel
            if not lokal_modus:
                vf = ("\n\n---\nHINWEIS VON TK EISVOGEL: Die folgenden Unterlagen gehören zur Frage. Antworte daraus; biete nichts für später an und versprich nichts "
                      "(kein „ich trage ein“, „ich prüfe“, „schick mir …, dann …“) – sag nur, was feststeht und was fehlt.")
                if treffer:
                    vf += ("\n\n---\nWIKI-AUSZÜGE, die TK Eisvogel per Bedeutungssuche gefunden hat (mit Stand; bei Widerspruch gilt der neuere, Chat-Mitschriften sind nachrangig):\n"
                           + "\n\n".join(f"[[{t['seite']}]] (Stand {datetime.fromtimestamp(t['geaendert']).strftime('%d.%m.%Y') if t.get('geaendert') else '?'}"
                                         f"{', Chat-Mitschrift' if '/raw/' in t.get('pfad', '') else ''}):\n{t['text'][:700]}" for t in treffer))
                if dokumente.relevant(frage):     # selbst in der Ablage suchen und lesen (auch Scans per Texterkennung)
                    senden({"status": "Suche und lese deine Dokumente …"})
                    try: dk = dokumente.kontext(frage)
                    except Exception: dk = ""
                    if dk:
                        vf += ("\n\n---\nDOKUMENTE, die TK Eisvogel gerade SELBST in Tekins Ablage gefunden und gelesen hat (Texterkennung bei Scans, kann Lesefehler enthalten). "
                               "Beantworte die Frage daraus und nenne die Datei. Verweise NICHT an Claude oder Tekin zum Nachsehen – du hast die Dateien hier. "
                               "Fehlt die Angabe wirklich, sag genau, welche Dateien du gelesen hast und was drinsteht."
                               + (" Hinweis: Das Feld „Nächste HU“ im Fahrzeugschein wird bei späteren Hauptuntersuchungen nicht aktualisiert – maßgeblich ist die Plakette bzw. der letzte HU-Bericht." if re.search(r"(?i)tüv|\bhu\b|hauptunters", frage) else "")
                               + "\n\n" + dk[:9000])
                        quellen = quellen + [{"seite": os.path.basename(x[7:].split("\n")[0])} for x in dk.split("### ")[1:] if x.startswith("Datei: ")]
                if frueher_text:
                    vf += "\n\n---\nDIESELBE FRAGE HAT TEKIN FRÜHER SCHON GESTELLT (die Antwort von damals kann überholt sein – neuere Unterlagen gehen vor):\n" + frueher_text[:1200]
                if pakte:                         # Detailfrage zu einer Person: die Akte ist Grundlage der Antwort …
                    vf += "\n\n---\nPERSONEN-AKTE (von TK Eisvogel aus Wiki, Kontakten, Terminen, Mails und Nachrichten zusammengestellt):\n" + pakte[:3000]
                senden({"status": "Denke nach …", "quellen": quellen + [{"seite": "TK Vogel"}]})
                va = vogel_frage(frage, verlauf, strom if not schon else (lambda teil, ersetzen=None: strom(teil, None if ersetzen is None else schon + ersetzen)), test=test, zusatz=vf.strip() if (treffer or pakte or frueher_text or "DOKUMENTE, die" in vf) else "")
                if va:
                    # Natürliche, geprüfte TK-Vogel-Antwort auch für „Nur lokal“ merken: dieselbe Frage später sofort, ohne Internet,
                    # solange sich die zugrunde liegenden Seiten nicht ändern (Claude 17.11.2026, Auftrag Tekin „natürlich wie die KI, ohne Fantasieren“)
                    if not verlauf and not test and not pakte and not art and not frage.startswith("!") and not re.search(r"(?i)weiß ich nicht|steht (dort|so|da|hier)? ?nicht|nicht in deinen unterlagen|frag claude|keine angabe|nicht gefunden", va):
                        try: antwortspeicher.ablegen(frage, va, quellen + [{"seite": "TK Vogel (gemerkt)"}], [t["pfad"] for t in treffer if t.get("pfad")])
                        except Exception: pass
                    if kurzakte:                  # … und steht danach kurz darunter (Antwort zuerst, dann die Person)
                        senden({"t": f"\n\n—\n{pe['name']} in Kürze:\n" + "\n".join(kurzakte) + "\n(ganze Akte: frag nur nach dem Namen)"})
                    return fertig("vogel")
                senden({"reset": True, "t": schon, "status": "TK Vogel antwortet nicht – ich antworte lokal …"})

            # 6) lokal – ohne fremde KI (lokal.py): erst wörtliche Belege aus Wiki, Speicher, Mails, Dokumenten; dann ein Satz vom Modell
            haeuf = lambda w: (len(IDX["post"][w][0]) if w in IDX.get("post", {}) else 0)
            stuecke = []
            if pe and pe.get("seite"):            # Frage zu einer Person: ihre Wiki-Seite ist die beste Quelle
                try: stuecke.append((Path(pe["seite"]).stem, re.sub(r"^---.*?---\s*", "", Path(pe["seite"]).read_text(errors="ignore"), flags=re.S)[:4000], pe["name"]))
                except Exception: pass
            for t in treffer:
                if t.get("quelle") == "Gelernt": stuecke.append((t["seite"], t.get("titel", "").rstrip("?") + ": " + t.get("antwort", "")))
                else: stuecke.append((t["seite"], t["text"].split("\n", 1)[-1], t.get("titel", "")))
            try: sp, bg = lokal.speicher_treffer(frage, haeuf, IDX.get("n", 20000))
            except Exception: sp, bg = [], []
            if not bg: bg = lokal.begriffe(frage, haeuf, IDX.get("n", 20000))
            stuecke = lokal.gesendet_treffer(frage, bg) + stuecke + sp + lokal.post_treffer(frage, bg)     # „schon gesendet?“ → Ausgang von TKMail zuerst
            if dokumente.relevant(frage):
                senden({"status": "Suche und lese deine Dokumente …"})
                try: dk = dokumente.kontext(frage, n=3, frist=8)
                except Exception: dk = ""
                for x in dk.split("### ")[1:]:
                    if x.startswith("Datei: "):
                        kopf, _, rest = x.partition("\n"); stuecke.append((os.path.basename(kopf[7:]), rest[:1500]))
            auch = " ".join(v for w, v in SYNONYME.items() if re.search(r"\b" + w + r"\b", frage.lower()))
            blp = lokal.belege_punkte(frage, stuecke, n=4, auch=auch)
            bl = [(s, q) for s, q, _ in blp]
            quellen = [{"seite": q} for q in dict.fromkeys([q for _, q in bl] + [t["seite"] for t in treffer if t.get("quelle") != "Gelernt"][:2])]
            if not bl and not treffer and frueher_text:      # aktuell nichts in den Unterlagen, aber die Frage gab es schon → Antwort von damals, sofort
                senden({"quellen": [{"seite": f"{frueher['seite']} {frueher.get('zeit', '')}"}]})
                senden({"t": frueher_text + "\n\n(Stand von damals – in den heutigen Unterlagen finde ich dazu nichts Neueres.)"}); return fertig("verlauf")
            # Fragen nach einem Datum oder Betrag: Die Angabe steht wörtlich im Beleg. Das kleine Modell verliest sich gerade hier
            # (gemessen 17.11.2026: Kündigungsfrist statt Vertragsende) – deshalb antwortet der Beleg selbst, sofort und ohne Modell.
            # Auch bei wer / wo / welche / ja-nein-Fragen steht die Antwort im Beleg; das Modell formuliert nur noch bei offenen
            # Fragen (was ist …, wie …, warum …) und bei Wissensfragen. Gemessen: 4 von 15 formulierten Sätzen waren falsch, die Belege richtig.
            art = lokal.frageart(frage)
            ja_nein = bool(re.match(r"(?i)\s*(wurde|wurden|ist|sind|war|waren|hat|habe|hab|haben|gibt|kann|darf|muss|soll|läuft|steht|liegt|kommt|geht|fehlt)\b", frage))
            offen = bool(re.search(r"(?i)^\s*(erklär|erläuter|beschreib|fass)|was (ist|sind|bedeutet|heißt) (ein|eine|einen|der unterschied|eigentlich)\b|wie funktioniert|was versteht man|wofür steht|definition|\bwarum\b|\bwieso\b|\bweshalb\b", frage))
            if bl and not verlauf and not offen and (art in ("wann", "betrag", "wo", "wer", "welche", "dauer") or ja_nein):
                # Bewusst keine herausgehobene Einzelangabe: Welches von mehreren Daten gemeint ist (Kündigungsfrist oder Vertragsende),
                # entscheidet der Wortlaut des Belegs – deshalb stehen die Belege selbst da, das Gefragte fett.
                senden({"quellen": quellen})
                senden({"t": "Laut deinen Unterlagen:\n" + "\n".join(f"• {lokal.hervorheben(s, frage)} ([[{q}]])" for s, q in bl)})
                if frueher_text: senden({"t": "\n\n—\n" + frueher_text})
                if kurzakte: senden({"t": f"\n\n—\n{pe['name']} in Kürze:\n" + "\n".join(kurzakte) + "\n(ganze Akte: frag nur nach dem Namen)"})
                return fertig("beleg")
            if bl:
                senden({"t": "Laut deinen Unterlagen:\n" + "\n".join(f"• {lokal.hervorheben(s, frage)} ([[{q}]])" for s, q in bl) + "\n\n—\nKurz: "})
            senden({"quellen": quellen, "status": "Formuliere die Antwort …" if (bl or treffer) else "Antworte aus meinem Wissen …"})
            lk = live.kontext(frage)
            unterlagen = [f"{i+1}. {s[:240]} (Quelle: {q})" for i, (s, q) in enumerate(bl[:3])]   # wenig Text = schnell (das Modell liest ~45 Wörter/s)
            aufzaehlung = bool(re.search(r"(?i)\bwelche\b|\balle\b|\bliste\b|übersicht|\bwie viele\b", frage))
            if treffer and (not bl or aufzaehlung):   # keine einzelnen Sätze gefunden oder Frage nach einer Aufzählung → die besten Abschnitte im Ganzen
                unterlagen = [f"{i+1}. {t['text'][:500 if aufzaehlung else AUSZUG_LEN]} (Quelle: {t['seite']})" for i, t in enumerate(treffer[:2])]
            mit = bool(unterlagen or lk or pakte)
            erklaeren = bool(re.search(r"(?i)^\s*(erklär|erläuter|beschreib)|was (ist|sind|bedeutet|heißt) (ein|eine|einen|der unterschied|eigentlich)\b|wie funktioniert|was versteht man|wofür steht|definition", frage))
            if mit and erklaeren and not pakte:   # allgemeine Erklärung: eigenes Wissen, die Unterlagen nur als Zusatz
                auftrag = (frage + "\n\nErkläre es kurz und richtig aus deinem Wissen (zwei bis drei Sätze)."
                           + ("\nFalls es hilft, steht dazu in Tekins Unterlagen:\n" + "\n".join(unterlagen[:2]) if unterlagen else ""))
            elif mit:
                auftrag = (f"Heute ist {heute()}.\n" + (lk + "\n\n" if lk else "") + ("ZUR PERSON:\n" + "\n".join(kurzakte[:4])[:500] + "\n\n" if kurzakte else "")
                           + ("UNTERLAGEN (wörtliche Auszüge aus Tekins Unterlagen):\n" + "\n".join(unterlagen) + "\n\n" if unterlagen else "")
                           + f"FRAGE: {frage}\n\nAntworte " + ("mit einer kurzen Aufzählung" if aufzaehlung else "in EINEM kurzen Satz") + " ausschließlich aus dem, was oben steht. Übernimm Namen, Daten und Beträge genau. "
                             "Steht die Antwort dort nicht, schreib nur: „Das steht so nicht in deinen Unterlagen.“")
            else:   # reine Wissensfrage: kurzer Auftrag, Datum nur bei Zeitfragen (sonst verschlechtert es beim 4B-Modell die Antworten)
                zeitfrage = re.search(r"(?i)\b(heute|morgen|gestern|datum|uhr|wochentag|welcher tag|jahr|monat|wann|wie spät|zeit)\b", frage)
                auftrag = (f"Heute ist {heute()}. " if zeitfrage else "") + frage
            nachrichten = [{"role": "system", "content": SYSTEM_KURZ}]
            nachrichten += [{"role": m["role"], "content": str(m.get("content", ""))[:500]} for m in verlauf if m.get("role") in ("user", "assistant")]
            nachrichten.append({"role": "user", "content": auftrag})
            _vorher = len("".join(z["text"]))
            self.modell_strom(nachrichten, senden, mit, lokal_modus, 200 if (mit and erklaeren) else ((110 if aufzaehlung else 70) if mit else 260))
            if mit and not erklaeren:   # Faktenwache: Zahlen/Daten, die das lokale Modell schreibt, müssen in den Unterlagen stehen (Claude 17.11.2026)
                _neu = "".join(z["text"])[_vorher:]
                _norm = lambda x: re.sub(r"[\s.,:]", "", x)
                _quelle = _norm(auftrag)
                _fremd = [w for w in dict.fromkeys(re.findall(r"\d[\d.,:/]*\d|\d", _neu)) if _norm(w) and _norm(w) not in _quelle]
                if _fremd:
                    senden({"t": "\n⚠️ Nicht belegt: " + ", ".join(_fremd[:4]) + " steht so nicht in deinen Unterlagen – bitte nicht verwenden."})
            if bl:   # ehrlich bleiben: das kleine lokale Modell verliest sich gelegentlich (gemessen 17.11.: Kündigungsfrist statt Vertragsende)
                senden({"t": "\n(vom lokalen Modell formuliert – maßgeblich sind die Belege darüber)"})
            if frueher_text:                      # dieselbe Frage gab es schon: die Antwort von damals dazu (wörtlich, mit Datum)
                senden({"t": "\n\n—\n" + frueher_text})
            if kurzakte:                          # Antwort zuerst, die Person kurz darunter
                senden({"t": f"\n\n—\n{pe['name']} in Kürze:\n" + "\n".join(kurzakte) + "\n(ganze Akte: frag nur nach dem Namen)"})
            fertig("lokal")
            if lokal_modus and not verlauf and not lk and not pakte and not test:   # Live-Daten und Akten ändern sich → nicht merken
                try: antwortspeicher.ablegen(frage, "".join(z["text"]), quellen, [t["pfad"] for t in treffer])
                except Exception: pass
        except (BrokenPipeError, ConnectionResetError):
            z["weg"] = z["weg"] or "abgebrochen"
        except Exception as e:
            z["weg"] = "fehler"
            try: senden({"fehler": str(e)})
            except Exception: pass
        finally:
            text = "".join(z["text"])
            if not test:
                if z["weg"] not in ("", "fehler", "abgebrochen", "hinweis"):
                    try: karte_ablegen(frage, text, z["quellen"])
                    except Exception: pass
                protokoll({"zeit": time.strftime("%d.%m.%Y %H:%M:%S"), "frage": frage, "weg": z["weg"], "erst": z["erst"], "gesamt": round(time.time() - t0, 2),
                           "quellen": [q.get("seite") for q in z["quellen"]][:8]})


AUFWAERMEN = threading.Lock()

def aufwaermen():
    with AUFWAERMEN: _aufwaermen()

def _aufwaermen():
    """Suchmodell immer bereithalten; das Antwortmodell nur dauerhaft, wenn „Nur lokal“ gewählt ist.
    Versucht es weiter, bis Ollama da ist (vorher: ein Fehlversuch beim Start, danach nie wieder → Ampel blieb gelb)."""
    for versuch in range(40):
        try:
            ollama("/api/embed", {"model": EMB_MODELL, "input": ["start"], "keep_alive": -1}, timeout=120)
            if quelle() == "lokal":
                for m in dict.fromkeys([modell(True), modell()]):   # nacheinander, nicht gleichzeitig
                    ollama("/api/chat", {"model": m, "messages": [{"role": "system", "content": SYSTEM_KURZ}, {"role": "user", "content": "hi"}], "think": False,
                                         "stream": False, "keep_alive": -1, "options": {"num_ctx": 4096, "num_predict": 1}}, timeout=300)
            return
        except Exception as e:
            if versuch == 0: print("Aufwärmen: Ollama noch nicht bereit –", e, flush=True)
            time.sleep(15)

def index_waechter():
    """Lädt den Index von selbst neu, sobald der Indexer fertig geschrieben hat."""
    while True:
        time.sleep(20)
        try: laden()
        except Exception as e: print("Index neu laden fehlgeschlagen:", e, flush=True)
        try:    # nach einem Neustart von Ollama (z. B. Speichermangel) die Modelle von selbst wieder bereitstellen
            g = ollama_geladen()
            if g is not None and (not any(x.startswith(EMB_MODELL) for x in g) or (quelle() == "lokal" and modell() not in g)):
                if not AUFWAERMEN.locked(): threading.Thread(target=aufwaermen, daemon=True).start()
        except Exception: pass

if __name__ == "__main__":
    laden()
    threading.Thread(target=aufwaermen, daemon=True).start()
    threading.Thread(target=index_waechter, daemon=True).start()
    try: person.namen()
    except Exception: pass
    for a in ([] if os.environ.get("EISVOGEL_PORT") else ADRESSEN[1:]):
        try:
            s = ThreadingHTTPServer((a, PORT), Anfrage)
            threading.Thread(target=s.serve_forever, daemon=True).start()
        except OSError as e:
            print("Tailnet-Adresse nicht verfügbar:", a, e, flush=True)
    ThreadingHTTPServer((ADRESSEN[0], PORT), Anfrage).serve_forever()
