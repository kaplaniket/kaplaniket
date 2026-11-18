#!/usr/bin/env python3
"""TK KI – Dauertraining (16.11.2026, Auftrag Tekin: „auf alles trainieren, was wir bis dato unternommen haben, ununterbrochen“).
Geht alle Unterlagen durch (Wiki-Themen, Personen, Orte, Protokolle, Journal, Chat-Mitschriften), neueste zuerst,
und erzeugt pro Abschnitt typische Fragen + belegte Antworten (qwen2.5:7b, Temperatur 0).
Prüfung: jede Zahl/jedes Datum der Antwort muss im Quelltext vorkommen, sonst wird das Paar verworfen.
Ergebnis: index/qa.jsonl → der Indexer nimmt es auf → TK KI antwortet darauf sofort und wörtlich.
Pausiert, solange Tekin TK KI benutzt (Datei /tmp/tk-ki-aktiv jünger als 120 s). Läuft als Dienst tk-ki-training.
"""
import hashlib, json, os, re, subprocess, time, urllib.request
from pathlib import Path

B = Path("/media/tekin/Disk2/TK-KI")
QA = B / "index/qa.jsonl"
STAND = B / "index/training-stand.json"
LOG = B / "logs/training.log"
AKTIV = Path("/tmp/tk-ki-aktiv")
WIKI = Path.home() / "Obsidian"
OLLAMA = "http://127.0.0.1:11434"
MODELL = "qwen2.5:7b"
GEHEIM = re.compile(r"(?i)passw|kennwort|\bpin\b|\btan\b|iban|\bDE\d{2}\s?\d{4}|token|api.?key|geheim")
ORDNER = ["06 Wiki/personen", "06 Wiki/themen", "06 Wiki/orte", "06 Wiki/fragen", "06 Wiki/meetings", "06 Wiki/manifest",
          "05 Claude", "06 Wiki/05 Claude", "06 Wiki/vergleiche", "02 Projekte", "04 Wissen", "01 Tagebuch", "06 Wiki/raw/transcripts"]   # Journal nicht (ändert sich laufend)
AUSLASSEN = re.compile(r"tk-ki-fehler|tk-ki-gelerntes|tk-ki\.md|tk-eisvogel\.md|tagesjournal|/journal/|/log\.md$|\.bak|_archiv|ABLAGE_LOCK")

PROMPT = """Du bekommst einen Abschnitt aus Tekin Kaplans persönlichen Unterlagen (Seite „{seite}“).
Schreibe {n} Fragen, die Tekin später so stellen könnte (kurz, natürlich, auf Deutsch, du-Form aus Tekins Sicht, z. B. „Wann …?“, „Wer ist …?“, „Wo liegt …?“, „Was ist mit …?“),
und zu jeder Frage die Antwort – NUR mit Fakten, die wörtlich im Abschnitt stehen (Namen, Daten, Beträge, Orte, Aktenzeichen genau übernehmen).
Nichts erfinden, nichts schlussfolgern. Keine Passwörter, PINs, IBANs. Wenn der Abschnitt nichts Brauchbares enthält (nur Technik-Befehle, Listen ohne Inhalt), gib [] zurück.
Antwortformat: nur JSON-Liste, z. B. [{{"frage": "...", "antwort": "..."}}]

ABSCHNITT:
{text}"""

def log(t):
    with open(LOG, "a") as f: f.write(time.strftime("%d.%m. %H:%M:%S ") + t + "\n")

def stand():
    try: return json.load(open(STAND))
    except Exception: return {"erledigt": {}}

def speichern(s):
    tmp = str(STAND) + ".tmp"; json.dump(s, open(tmp, "w")); os.replace(tmp, STAND)

def warten_bis_frei():
    while AKTIV.exists() and time.time() - AKTIV.stat().st_mtime < 120:
        time.sleep(10)

def abschnitte(pfad):
    t = pfad.read_text(errors="ignore")
    t = re.sub(r"^---.*?---\s*", "", t, flags=re.S)
    teile, titel, buf = [], "", []
    for z in t.splitlines():
        if re.match(r"^#{1,3} ", z):
            if buf: teile.append((titel, "\n".join(buf)))
            titel, buf = z.lstrip("# ").strip(), [z]
        else:
            buf.append(z)
    if buf: teile.append((titel, "\n".join(buf)))
    aus = []
    for ti, tx in teile:
        tx = "\n".join(z for z in tx.splitlines() if not GEHEIM.search(z)).strip()
        while len(tx) > 2200:
            s = tx.rfind("\n", 0, 2200); s = s if s > 800 else 2200
            aus.append((ti, tx[:s])); tx = tx[s:]
        if len(re.sub(r"\W", "", tx)) >= 120: aus.append((ti, tx))
    return aus

def zahlen(s):
    return set(re.findall(r"\d[\d.,/:-]*\d|\d", s))

import sys as _sys
_sys.path.insert(0, "/home/tekin/bin")
try:
    from ki import frage as ki_frage          # DeepSeek wie TK Vogel/Hermes (Freigabe Tekin 16.11.2026 23:38)
except Exception:
    ki_frage = None

def _json_liste(roh):
    roh = re.sub(r"^```(json)?|```$", "", roh.strip(), flags=re.M).strip()
    try: j = json.loads(roh)
    except Exception:
        m = re.search(r"\[.*\]", roh, re.S)
        try: j = json.loads(m.group(0)) if m else []
        except Exception: j = []
    if isinstance(j, dict): j = next((v for v in j.values() if isinstance(v, list)), [j])
    return j if isinstance(j, list) else []

def nur_lokal():
    """Einstellung „Nur lokal – privat“ in TK Eisvogel: dann lernt auch das Training ohne DeepSeek (langsamer, mit dem lokalen Modell). Claude 17.11.2026"""
    try: return json.load(open(B / "index/einstellungen.json")).get("quelle") == "lokal"
    except Exception: return False

def erzeugen(seite, text):
    n = 3 if len(text) < 700 else 5
    if ki_frage and not nur_lokal():
        try:
            roh = ki_frage("Du erzeugst Lernkarten für Tekins persönliche KI. Antworte nur mit einer JSON-Liste.",
                           PROMPT.format(seite=seite, n=n, text=text), max_tokens=900, temperatur=0, zweck="tk-ki-training")
            return pruefen(_json_liste(roh), text)
        except Exception as e:
            log(f"DeepSeek-Fehler ({e}) – lokal weiter")
    return erzeugen_lokal(seite, text, n)

def lokales_modell():
    """Im Modus „Nur lokal“ das Antwortmodell nehmen, das ohnehin geladen ist. Ein zusätzliches 7B-Modell hat am 17.11.2026 06:37
    den Arbeitsspeicher gesprengt (Linux beendete Ollama: „Out of memory“). Claude 17.11.2026"""
    try: return json.load(open(B / "index/einstellungen.json")).get("modell") or MODELL
    except Exception: return MODELL

def erzeugen_lokal(seite, text, n):
    d = {"model": lokales_modell() if nur_lokal() else MODELL, "stream": False, "keep_alive": "30m", "format": "json", "think": False,
         "messages": [{"role": "user", "content": PROMPT.format(seite=seite, n=n, text=text)}],
         "options": {"temperature": 0, "num_ctx": 4096, "num_predict": 600}}
    r = urllib.request.Request(OLLAMA + "/api/chat", json.dumps(d).encode(), {"Content-Type": "application/json"})
    roh = json.load(urllib.request.urlopen(r, timeout=900))["message"]["content"]
    return pruefen(_json_liste(roh), text)

def pruefen(j, text):
    gut, quelle_z = [], zahlen(text)
    for x in j:
        if not isinstance(x, dict): continue
        f, a = str(x.get("frage", "")).strip(), str(x.get("antwort", "")).strip()
        if len(f) < 8 or len(a) < 12 or GEHEIM.search(a): continue
        if a.lower().strip(" .") in f.lower(): continue                 # Antwort wiederholt nur die Frage
        if re.search(r"(?i)tagesjournal|wurde .* erstellt\?|~/bin/|\.py\b", f): continue
        if not zahlen(a) <= quelle_z: continue            # erfundene Zahl/Datum → verwerfen
        if re.search(r"[一-鿿]", f + a): continue
        gut.append({"frage": f, "antwort": a})
    return gut

EXTRA = [Path("/media/tekin/Disk1/chat-archiv/hermes"), Path("/media/tekin/Disk1/chat-archiv/grok/chats"),
         Path("/media/tekin/Disk1/chat-archiv/claude")]   # Hermes-, Grok- und (neue) Claude-Chats

def dateien():
    alle = []
    for e in EXTRA:
        if e.is_dir(): alle += [("06 Wiki/raw/transcripts", x) for x in e.rglob("*.md")]
    for o in ORDNER:
        p = WIKI / o
        if p.is_dir(): alle += [(o, x) for x in p.rglob("*.md") if not AUSLASSEN.search(str(x))]
    rang = {o: i for i, o in enumerate(ORDNER)}
    # erst nach Ordner-Vorrang, innerhalb neueste zuerst
    return sorted(alle, key=lambda ox: (rang[ox[0]], -ox[1].stat().st_mtime))

import threading as _th
_IXL = _th.Lock()
def index_auffrischen():
    if not _IXL.acquire(blocking=False): return      # läuft schon – nicht doppelt
    try: _index_auffrischen()
    finally: _IXL.release()

def _index_auffrischen():
    subprocess.run(["nice", "-n", "10", "/usr/bin/python3", str(B / "app/indexer.py")], capture_output=True, timeout=1800)
    try: urllib.request.urlopen(urllib.request.Request("http://127.0.0.1:8811/api/neu-laden", method="POST"), timeout=300).read()
    except Exception: pass

def main():
    import threading
    from concurrent.futures import ThreadPoolExecutor
    log("Training gestartet (DeepSeek, 6 parallel)" if ki_frage else "Training gestartet (lokal)")
    sperre = threading.Lock()
    while True:
        s = stand(); offen = []
        for o, p in dateien():
            for ti, tx in abschnitte(p):
                h = hashlib.sha1(tx.encode()).hexdigest()
                if h not in s["erledigt"]: offen.append((p, ti, tx, h))
        if not offen:
            time.sleep(300); continue
        log(f"{len(offen)} Abschnitte offen")
        zaehler = {"paare": 0, "seit": 0}
        def eins(a):
            p, ti, tx, h = a
            # Leermeldungen aus Routinen („Nichts zu berichten“, „Keine neuen Kleinanzeigen“) nicht abfragen – kostet nur und ergibt
            # Paare wie „Gab es am 9.11. neue Nachrichten? – Nein“ (Claude 17.11.2026, Gesamtprüfung)
            if re.search(r"(?i)nichts zu (berichten|melden)|nothing to report|keine[nr]? neue[nrs]? (relevante[nrs]? )?(kleinanzeigen|nachricht|mail|meldung)", ti):
                with sperre:
                    s["erledigt"][h] = 0; speichern(s)
                return
            if not ki_frage or nur_lokal(): warten_bis_frei()
            t0 = time.time()
            try: paare = erzeugen(p.stem, tx)
            except Exception as e:
                log(f"Fehler {p.stem}: {e}"); return
            with sperre:
                with open(QA, "a") as f:
                    for x in paare:
                        f.write(json.dumps(dict(x, seite=p.stem, titel=ti, pfad=str(p), hash=h, zeit=time.strftime("%Y-%m-%d %H:%M"),
                                                erzeugt="lokal" if (nur_lokal() or not ki_frage) else "deepseek"), ensure_ascii=False) + "\n")
                s["erledigt"][h] = len(paare); speichern(s)
                zaehler["paare"] += len(paare); zaehler["seit"] += len(paare)
                log(f"{p.stem} › {ti[:40]}: {len(paare)} Paare ({time.time()-t0:.0f} s)")
                if zaehler["seit"] >= 400:
                    zaehler["seit"] = 0; threading.Thread(target=index_auffrischen, daemon=True).start(); log("Index wird aufgefrischt")
        with ThreadPoolExecutor(max_workers=6 if (ki_frage and not nur_lokal()) else 1) as ex:
            list(ex.map(eins, offen))
        index_auffrischen(); log(f"Durchlauf fertig: {zaehler['paare']} neue Paare, Index aufgefrischt")

if __name__ == "__main__":
    main()
