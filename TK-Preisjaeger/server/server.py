#!/usr/bin/env python3
# TK Preisjäger – Webserver. Claude 26.11.2026
# Start: python3 server.py   (Port: PREISJAEGER_PORT, Vorgabe 8815)
import json
import os
import threading
import time
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, wait
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import kern
import quellen

ORT = os.path.dirname(os.path.abspath(__file__))
DATEN = os.path.join(ORT, "daten")
MERK = os.path.join(DATEN, "merkliste.json")
PORT = int(os.environ.get("PREISJAEGER_PORT", "8815"))
FASSUNG = "1.0"
_speicher, _sperre = {}, threading.Lock()


def _lauf(name, fn, anfrage, ab, seite):
    try:
        return name, fn(anfrage, ab, seite), ""
    except Exception as e:
        return name, [], "%s: %s" % (type(e).__name__, str(e)[:80])


def suche(anfrage, streng=True):
    anfrage = " ".join(anfrage.split())[:120]
    schluessel = (anfrage.lower(), streng)
    with _sperre:
        alt = _speicher.get(schluessel)
        if alt and time.time() - alt[0] < 600:
            return dict(alt[1], aus_speicher=True)
    start = time.time()
    roh, status = [], {n: {"name": n, "gefunden": 0, "passend": 0, "fehler": ""} for n, _, _, _ in quellen.QUELLEN}

    def sammeln(auftraege):
        with ThreadPoolExecutor(max_workers=12) as p:
            laeufe = [p.submit(_lauf, *a) for a in auftraege]
            wait(laeufe, timeout=25)
            for l in laeufe:
                if not l.done():
                    continue
                name, liste, fehler = l.result()
                for a in liste:
                    a.setdefault("quelle", name)
                roh.extend(liste)
                status[name]["gefunden"] += len(liste)
                if fehler and not status[name]["fehler"]:
                    status[name]["fehler"] = fehler

    # 1. Durchgang: jede Quelle mit dem Suchtext (Kleinanzeigen zwei Seiten)
    sammeln([(n, f, anfrage, None, 1) for n, f, _, _ in quellen.QUELLEN] + [("Kleinanzeigen", quellen.kleinanzeigen, anfrage, None, 2)])
    e = kern.bewerten(anfrage, [dict(a) for a in roh], streng)
    # 2. Durchgang: Der übliche Preis ist jetzt bekannt -> auf den Privatmärkten gezielt die billigsten echten Angebote holen
    # (ab 40 % des üblichen Preises, nach Preis sortiert; darunter liegt fast nur Zubehör)
    if e["ueblich"]:
        ab = max(1, int(e["ueblich"] * 0.4))
        sammeln([(n, f, anfrage, ab, s) for n, f, _, zwei in quellen.QUELLEN if zwei for s in (1, 2) if not (n == "Vinted" and s == 2)])
        e = kern.bewerten(anfrage, [dict(a) for a in roh], streng, e["ueblich"])
    for a in e["treffer"]:
        status[a["quelle"]]["passend"] += 1
    arten = {n: art for n, _, art, _ in quellen.QUELLEN}
    for l in (e["treffer"], e["auffaellig"], e["defekt"]):
        for a in l:
            a["art"] = arten.get(a["quelle"], "")
            a.pop("text", None)
    e.update(anfrage=anfrage, streng=streng, quellen=list(status.values()), links=quellen.links(anfrage),
             groessen=kern.groessen(anfrage, e["treffer"]), dauer=round(time.time() - start, 1), zeit=time.strftime("%d.%m.%Y %H:%M"))
    e["defekt"], e["auffaellig"] = e["defekt"][:40], e["auffaellig"][:40]
    with _sperre:
        _speicher[schluessel] = (time.time(), e)
        for k in [k for k, v in _speicher.items() if time.time() - v[0] > 3600]:
            _speicher.pop(k, None)
    _merk_stand(e)
    return e


# ---------- Merkliste ----------
def _merk_lesen():
    try:
        with open(MERK, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def _merk_schreiben(liste):
    os.makedirs(DATEN, exist_ok=True)
    with open(MERK + ".neu", "w", encoding="utf-8") as f:
        json.dump(liste, f, ensure_ascii=False, indent=1)
    os.replace(MERK + ".neu", MERK)


def _merk_stand(e):
    """Nach jeder Suche: steht der Suchtext auf der Merkliste, den besten Preis festhalten."""
    with _sperre:
        liste, da = _merk_lesen(), False
        for m in liste:
            if m["anfrage"].lower() == e["anfrage"].lower() and e["treffer"]:
                b = e["treffer"][0]
                m["vorher"] = m.get("preis")
                m.update(preis=b["preis"], quelle=b["quelle"], url=b["url"], zeit=e["zeit"])
                m["tiefst"] = min(b["preis"], m.get("tiefst") or b["preis"])
                da = True
        if da:
            _merk_schreiben(liste)


class Antwort(BaseHTTPRequestHandler):
    server_version = "TKPreisjaeger/" + FASSUNG

    def log_message(self, *a):
        pass

    def _json(self, d, code=200):
        b = json.dumps(d, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(b)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        p = urllib.parse.parse_qs(u.query)
        if u.path == "/":
            with open(os.path.join(ORT, "index.html"), "rb") as f:
                b = f.read().replace(b"{{FASSUNG}}", FASSUNG.encode())
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(b)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(b)
        elif u.path == "/api/suche":
            a = (p.get("q") or [""])[0].strip()
            if len(a) < 2:
                return self._json({"fehler": "Bitte ein Produkt eingeben."}, 400)
            try:
                self._json(suche(a, (p.get("streng") or ["1"])[0] != "0"))
            except Exception as e:
                self._json({"fehler": "Suche fehlgeschlagen: %s" % e}, 500)
        elif u.path == "/api/merkliste":
            self._json(_merk_lesen())
        elif u.path == "/api/stand":
            self._json({"name": "TK Preisjäger", "fassung": FASSUNG, "quellen": [n for n, _, _, _ in quellen.QUELLEN]})
        else:
            self.send_error(404)

    def do_POST(self):
        u = urllib.parse.urlparse(self.path)
        try:
            d = json.loads(self.rfile.read(min(int(self.headers.get("Content-Length") or 0), 4000)) or b"{}")
        except Exception:
            d = {}
        a = " ".join(str(d.get("anfrage", "")).split())[:120]
        if u.path == "/api/merken" and a:
            with _sperre:
                liste = _merk_lesen()
                if not any(m["anfrage"].lower() == a.lower() for m in liste):
                    liste.insert(0, {"anfrage": a, "seit": time.strftime("%d.%m.%Y")})
                    _merk_schreiben(liste)
            with _sperre:
                alt = _speicher.get((a.lower(), True))
            if alt:
                _merk_stand(alt[1])
            self._json(_merk_lesen())
        elif u.path == "/api/vergessen" and a:
            with _sperre:
                _merk_schreiben([m for m in _merk_lesen() if m["anfrage"].lower() != a.lower()])
            self._json(_merk_lesen())
        else:
            self.send_error(404)


if __name__ == "__main__":
    print("TK Preisjäger %s auf Port %d" % (FASSUNG, PORT), flush=True)
    ThreadingHTTPServer(("0.0.0.0", PORT), Antwort).serve_forever()
