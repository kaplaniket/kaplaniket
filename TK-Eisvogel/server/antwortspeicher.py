#!/usr/bin/env python3
"""TK KI – Antwortspeicher (Claude 16.11.2026, Auftrag Tekin: „Antworten wie aus der Pistole“).
Jede fertige Modell-Antwort wird gemerkt. Kommt dieselbe Frage wieder (Groß/Klein, Satzzeichen,
Füllwörter egal), kommt die Antwort sofort – ohne Sprachmodell.
Gültig nur, solange sich keine der benutzten Wiki-Seiten geändert hat (Änderungsdatum der Datei).
Nicht gemerkt: Fragen mit Gesprächsverlauf, Termine/Live-Daten, Personen-Akten (ändern sich laufend).
Datei: index/antworten.json · Löschen: Datei entfernen oder POST /api/speicher-leeren.
"""
import json, os, re, threading, time

DATEI = "/media/tekin/Disk2/TK-KI/index/antworten.json"
FUELL = set("bitte mal kurz eigentlich denn doch ja nun also sag mir kannst du weißt du hey hallo tk ki".split())
_lock = threading.Lock()
_daten = None

def schluessel(frage):
    w = re.findall(r"[a-zäöüß0-9]+", frage.lower())
    return " ".join(x for x in w if x not in FUELL)

def _laden():
    global _daten
    if _daten is None:
        try: _daten = json.load(open(DATEI))
        except Exception: _daten = {}
    return _daten

def _speichern():
    tmp = DATEI + ".tmp"
    json.dump(_daten, open(tmp, "w"), ensure_ascii=False)
    os.replace(tmp, DATEI)

def _mtime(p):
    try: return round(os.path.getmtime(p), 1)
    except Exception: return None

def holen(frage):
    k = schluessel(frage)
    if len(k) < 3: return None
    with _lock:
        e = _laden().get(k)
    if not e: return None
    for p, m in e.get("seiten", {}).items():
        if _mtime(p) != m:          # Unterlage geändert → Antwort neu bilden
            with _lock:
                _laden().pop(k, None); _speichern()
            return None
    # Fragt Tekin dieselbe Frage binnen 10 Minuten noch einmal, war er wohl unzufrieden → neu bilden
    if time.time() - e.get("gezeigt", 0) < 600:
        with _lock:
            _laden().pop(k, None); _speichern()
        return None
    e["treffer"] = e.get("treffer", 0) + 1; e["gezeigt"] = time.time()
    with _lock: _speichern()
    return e

def ablegen(frage, text, quellen, pfade):
    k = schluessel(frage)
    text = (text or "").strip()
    if len(k) < 3 or len(text) < 2: return
    if re.search(r"[぀-ヿ一-鿿가-힯]", text): return
    e = {"frage": frage, "text": text, "quellen": quellen, "zeit": time.strftime("%Y-%m-%d %H:%M:%S"),
         "seiten": {p: _mtime(p) for p in set(pfade) if _mtime(p) is not None}}
    with _lock:
        _laden()[k] = e
        if len(_daten) > 5000:      # älteste raus
            for alt in sorted(_daten, key=lambda x: _daten[x].get("zeit", ""))[:500]: _daten.pop(alt, None)
        _speichern()

def leeren():
    global _daten
    with _lock:
        _daten = {}; _speichern()
