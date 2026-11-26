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
import sprache

ORT = os.path.dirname(os.path.abspath(__file__))
DATEN = os.path.join(ORT, "daten")
MERK = os.path.join(DATEN, "merkliste.json")
HANDEL = os.path.join(DATEN, "verhandlungen.json")
NAME = os.environ.get("PREISJAEGER_NAME", "")      # Vorname für den Gruß in Nachrichten
PORT = int(os.environ.get("PREISJAEGER_PORT", "8815"))
FASSUNG = "1.4.4"
_speicher, _sperre = {}, threading.Lock()


def _lauf(name, fn, anfrage, ab, seite):
    try:
        return name, fn(anfrage, ab, seite), ""
    except Exception as e:
        return name, [], "%s: %s" % (type(e).__name__, str(e)[:80])


_seiten = {}      # url -> Seitentext (Zwischenspeicher für die Nachprüfung)


def nachpruefen(anfrage, roh, streng):
    """Händlerangebote derselben Marke, deren Titel nicht passt (oft nur eine Modellnummer): Steht der gesuchte Name auf der
    Angebotsseite, gilt das Angebot. Höchstens 8 Seiten je Suche, nur Händlerquellen."""
    gruppen = kern.zerlegen(anfrage)
    if len(gruppen) < 2:
        return
    marke = gruppen[0]
    kand, gesehen = [], set()
    for a in roh:
        if a.get("quelle") not in ("idealo", "MediaMarkt", "Saturn", "Hood") or not a.get("url") or a["url"] in gesehen or a.get("pruef_titel"):
            continue
        tt = kern.flach(kern.zerlegen(a["titel"]))
        if kern._finde(marke, tt) < 0 or kern.pruefe(anfrage, a["titel"], "", streng)[0]:
            continue
        gesehen.add(a["url"])
        kand.append(a)
    kand = sorted(kand, key=lambda a: a["quelle"] != "idealo")[:8]
    if not kand:
        return

    def lesen(a):
        if a["url"] not in _seiten:
            _seiten[a["url"]] = quellen.seitentext(a["url"], 9000)
        return a, _seiten[a["url"]]

    with ThreadPoolExecutor(max_workers=8) as topf:
        for a, text in topf.map(lesen, kand):
            # nur der Teil mit den Angeboten dieser Seite – nicht die Verweise auf andere Produkte darunter
            for marke_ende in ("Ähnliche Produkte", "Weitere Stichworte", "Passende Produkte", "Kunden interessierten sich auch", "Das könnte dich auch interessieren", "Alternative Produkte", "Weitere Produkte"):
                j = text.find(marke_ende)
                if j > 200:
                    text = text[:j]
            zahl, stueck = kern.fenster(anfrage, text)
            if not zahl:      # ein Beschreibungswort darf fehlen, dann muss der Name aber mehrfach auf der Seite stehen
                for kuerzer, _ in kern.kuerzungen(anfrage):
                    zahl, stueck = kern.fenster(kuerzer, text)
                    if zahl >= 2:
                        break
                    zahl = 0
            if zahl:
                for b in roh:
                    if b.get("url") == a["url"]:
                        b["pruef_titel"] = stueck
                        b["hinweis"] = " · ".join(x for x in [b.get("hinweis", ""), "Name laut Angebotsseite bestätigt"] if x)
    if len(_seiten) > 400:
        _seiten.clear()


# Wie tief gelesen wird: (Kleinanzeigen-Seiten neueste, Kleinanzeigen-Seiten billigste, Vinted neueste, Vinted billigste)
TIEFE = {1: (4, 12, 2, 3), 2: (8, 40, 4, 8)}


def suche(anfrage, streng=True, tiefe=1):
    anfrage = " ".join(anfrage.split())[:120]
    tiefe = 2 if tiefe == 2 else 1
    ka_neu, ka_billig, vi_neu, vi_billig = TIEFE[tiefe]
    schluessel = (anfrage.lower(), streng, tiefe)
    try:      # Suchtexte mitschreiben – nur zur Fehlersuche, bleibt auf dem eigenen Rechner
        os.makedirs(DATEN, exist_ok=True)
        with open(os.path.join(DATEN, "suchen.log"), "a", encoding="utf-8") as f:
            f.write("%s\t%s\t%s\n" % (time.strftime("%d.%m.%Y %H:%M:%S"), tiefe, anfrage))
    except Exception:
        pass
    with _sperre:
        alt = _speicher.get(schluessel)
        if alt and time.time() - alt[0] < 600:
            return dict(alt[1], aus_speicher=True)
    start = time.time()
    voll, v = anfrage, sprache.verstehen(anfrage)      # Freitext: Produkt, Ausstattung, Preisgrenze, Zustand
    anfrage = v["produkt"]
    roh, status = [], {n: {"name": n, "gefunden": 0, "passend": 0, "fehler": ""} for n, _, _, _ in quellen.QUELLEN}

    def sammeln(auftraege):
        with ThreadPoolExecutor(max_workers=10) as p:
            laeufe = [p.submit(_lauf, *a) for a in auftraege]
            wait(laeufe, timeout=30 * tiefe)
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

    # 1. Durchgang: jede Quelle mit dem Suchtext (Kleinanzeigen und Vinted mehrere Seiten)
    quellen.GESAMT.pop("Kleinanzeigen", None)
    sammeln([(n, f, anfrage, None, 1) for n, f, _, _ in quellen.QUELLEN]
            + [("Kleinanzeigen", quellen.kleinanzeigen, anfrage, None, s) for s in range(2, ka_neu + 1)]
            + [("Vinted", quellen.vinted, anfrage, None, s) for s in range(2, vi_neu + 1)])
    e = kern.bewerten(anfrage, [dict(a) for a in roh], streng)
    nachpruefen(anfrage, roh, streng)
    e = kern.bewerten(anfrage, [dict(a) for a in roh], streng)
    # Kaum Treffer: Die Seiten verlangen oft alle Wörter. Dann zusätzlich mit einem Beschreibungswort weniger suchen;
    # bewertet wird weiter gegen den vollen Suchtext (fehlt nur dieses Wort im Titel, steht es unter „fast passend“).
    if len(e["treffer"]) < 3:
        for kuerzer, _ in kern.kuerzungen(anfrage)[:2]:
            sammeln([(n, f, kuerzer, None, 1) for n, f, _, _ in quellen.QUELLEN])
        e = kern.bewerten(anfrage, [dict(a) for a in roh], streng)
    # 2. Durchgang: Der übliche Preis ist jetzt bekannt -> auf den Privatmärkten gezielt die billigsten echten Angebote holen
    # (ab der Hälfte des üblichen Preises, nach Preis sortiert; darunter liegt fast nur Zubehör)
    if e["ueblich"]:
        ab = max(1, int(e["ueblich"] * kern.GRENZE))
        sammeln([("Kleinanzeigen", quellen.kleinanzeigen, anfrage, ab, s) for s in range(1, ka_billig + 1)]
                + [("Vinted", quellen.vinted, anfrage, ab, s) for s in range(1, vi_billig + 1)])
        e = kern.bewerten(anfrage, [dict(a) for a in roh], streng, e["ueblich"])
    arten = {n: art for n, _, art, _ in quellen.QUELLEN}
    for l in (e["treffer"], e["auffaellig"], e["defekt"], e["aehnlich"]):
        for a in l:
            a["art"] = arten.get(a["quelle"], "")
    e = kern.wuensche_anwenden(e, v)
    for a in e["treffer"]:
        status[a["quelle"]]["passend"] += 1
    for l in (e["treffer"], e["auffaellig"], e["defekt"], e["aehnlich"]):
        for a in l:
            a.pop("text", None)
    if "Kleinanzeigen" in quellen.GESAMT:
        status["Kleinanzeigen"]["gesamt"] = quellen.GESAMT["Kleinanzeigen"]
    e["tiefe"], e["gelesen"] = tiefe, len({(a.get("quelle"), a.get("url")) for a in roh})
    e.update(anfrage=voll, produkt=anfrage, verstanden=v if voll.lower() != anfrage.lower() else None, streng=streng, quellen=list(status.values()), links=quellen.links(anfrage),
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
                self._json(suche(a, (p.get("streng") or ["1"])[0] != "0", 2 if (p.get("tief") or ["0"])[0] == "1" else 1))
            except Exception as e:
                self._json({"fehler": "Suche fehlgeschlagen: %s" % e}, 500)
        elif u.path == "/api/merkliste":
            self._json(_merk_lesen())
        elif u.path == "/api/konto":
            import verhandler
            self._json(verhandler.konto())
        elif u.path == "/api/verhandlungen":
            self._json(_lesen(HANDEL))
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
        if u.path == "/api/fehler":
            print("OBERFLÄCHE-FEHLER:", str(d.get("text", ""))[:300], "|", (self.headers.get("User-Agent") or "")[-40:], flush=True)
            return self._json({})
        if u.path == "/api/details":
            try:
                url = str(d.get("url") or "")
                angaben = quellen.seitentext(url, 4500) if url else ""
                e = sprache.details(str(d.get("titel", ""))[:160], angaben, float(d.get("preis") or 0) or None, str(d.get("quelle", ""))[:20])
                if not e:
                    raise ValueError("die KI hat nicht geantwortet – bitte noch einmal versuchen")
                return self._json(dict(e, belegt=bool(angaben), warn=kern.betrug(angaben)))
            except Exception as e:
                return self._json({"fehler": "Details nicht möglich: %s" % e}, 400)
        if u.path == "/api/vergleich":
            try:
                return self._json(vergleichen(d))
            except Exception as e:
                return self._json({"fehler": "Vergleich nicht möglich: %s" % e}, 400)
        if u.path in ("/api/nachricht", "/api/antwort", "/api/verhandlung"):
            try:
                return self._json(self._handel(u.path, d))
            except Exception as e:
                return self._json({"fehler": "Das hat nicht geklappt: %s" % e}, 400)
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


def _eur(n):
    return ("%.2f" % n).replace(".", ",").replace(",00", "") + " €"


def vergleichen(d):
    """Produktvergleich: bis zu 4 Produkte (aus der Trefferliste mit url/preis oder nur als Name). Zu einem einzelnen
    Produkt werden auf Wunsch Alternativen gesucht. Preise und Händlerangaben kommen aus der eigenen Suche, die Einschätzung von der KI."""
    eingang = [p for p in (d.get("produkte") or []) if str(p.get("name", "")).strip()][:4]
    if not eingang:
        raise ValueError("Bitte mindestens ein Produkt angeben")

    def aufbereiten(p):
        name, url = " ".join(str(p["name"]).split())[:140], str(p.get("url") or "")
        preise, bester, link, angaben = [], None, url, ""
        if p.get("preis"):
            bester = float(p["preis"])
            preise.append("%s (%s, %s)" % (_eur(bester), p.get("quelle", "Angebot"), p.get("zustand", "")))
        gesucht = " ".join(str(p.get("gesucht") or "").split())[:120] or (name if not p.get("preis") else "")
        if gesucht:      # eigene Suche: Preise je Zustand und eine Händlerseite mit den technischen Angaben
            try:
                e = suche(gesucht)
                alle = e["treffer"]      # nur genaue Treffer – „fast passend“ kann ein anderes Gerät sein
                if not p.get("preis"):
                    je = {}
                    for a in alle:
                        je.setdefault(a["zustand"], a)
                    for z, a in je.items():
                        preise.append("%s ab %s (%s)" % ({"neu": "neu", "aufbereitet": "geprüft", "gebraucht": "gebraucht"}.get(z, z), _eur(a["preis"]), a["quelle"]))
                    if alle:
                        bester = alle[0]["preis"]
                haendler = sorted([a for a in alle if a.get("art") == "händler" and a["url"] != url], key=lambda a: a["quelle"] != "Amazon")
                if haendler:
                    angaben = quellen.seitentext(haendler[0]["url"], 3000)
                    link = link or haendler[0]["url"]
                elif alle and not link:
                    link = alle[0]["url"]
            except Exception:
                pass
        if link and len(angaben) < 2500:
            angaben = (angaben + " " + quellen.seitentext(link, 2500)).strip()
        return {"name": name, "preise": " · ".join(preise), "bester": bester, "url": link, "vorschlag": bool(p.get("vorschlag")), "angaben": angaben}

    with ThreadPoolExecutor(max_workers=4) as topf:
        produkte = list(topf.map(aufbereiten, eingang))
    gattung, verworfen = "", []
    if len(produkte) == 1 and d.get("alternativen", True):
        # Alternativen erst, wenn bekannt ist, was das Gerät ist (Angaben von der Angebotsseite) – nie nur aus dem Namen raten
        erstes = produkte[0]
        gattung, namen = sprache.alternativen(erstes["name"], erstes["angaben"], erstes["bester"])
        with ThreadPoolExecutor(max_workers=4) as topf:
            vorschlaege = list(topf.map(aufbereiten, [{"name": n, "vorschlag": True} for n in namen]))
        for v in vorschlaege:
            # ganz andere Preisklasse = kein ernsthafter Vergleich (Zubehör, anderes Gerät); dieselbe Angebotsseite = dasselbe Gerät doppelt
            if v["bester"] and erstes["bester"] and not (0.3 <= v["bester"] / erstes["bester"] <= 3.0):
                verworfen.append(v["name"])
            elif v["url"] and v["url"] in [x["url"] for x in produkte]:
                continue
            else:
                produkte.append(v)
        produkte = produkte[:4]
    if len(produkte) < 2:
        raise ValueError("keine vergleichbare Alternative gefunden%s – bitte ein zweites Produkt selbst eintragen"
                         % ((" (verworfen: %s)" % ", ".join(verworfen)) if verworfen else ""))
    v = sprache.vergleich(produkte, str(d.get("wunsch", "")), gattung)
    if not v:
        raise ValueError("die KI hat nicht geantwortet – bitte noch einmal versuchen")
    aus = []
    for i, p in enumerate(v["produkte"]):
        q = produkte[i] if i < len(produkte) else {}
        if q.get("vorschlag") and not p.get("vergleichbar", True):
            verworfen.append(q.get("name", p["name"]))
            continue
        p.update(name=q.get("name", p["name"]), preise=q.get("preise", ""), bester=q.get("bester"), url=q.get("url", ""),
                 vorschlag=q.get("vorschlag", False), belegt=bool(q.get("angaben")))
        aus.append(p)
    if len(aus) < 2:
        raise ValueError("keine vergleichbare Alternative gefunden (verworfen: %s) – bitte ein zweites Produkt selbst eintragen" % ", ".join(verworfen))
    v["produkte"] = aus
    if v["empfehlung"]["name"] not in [p["name"] for p in aus]:      # Empfehlung auf einen der gezeigten Namen abbilden
        nah = [p["name"] for p in aus if p["name"].lower()[:12] in v["empfehlung"]["name"].lower() or v["empfehlung"]["name"].lower()[:12] in p["name"].lower()]
        v["empfehlung"]["name"] = nah[0] if nah else aus[0]["name"]
    v.update(zeit=time.strftime("%d.%m.%Y %H:%M"), gattung=gattung, verworfen=verworfen)
    return v


def _lesen(pfad):
    try:
        with open(pfad, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def _handel(self, pfad, d):
    """Verhandeln: Nachricht entwerfen, Antwort des Verkäufers einordnen, Stand festhalten. Gesendet wird hier nie etwas."""
    titel, url = str(d.get("titel", ""))[:160], str(d.get("url", ""))[:400]
    preis, mein = float(d.get("preis") or 0), float(d.get("mein") or 0)
    if pfad == "/api/nachricht":
        if not (titel and preis > 0 and mein > 0):
            raise ValueError("Titel, Preis und dein Preis werden gebraucht")
        return {"text": sprache.nachricht(titel, preis, mein, str(d.get("quelle", "Kleinanzeigen"))[:20], NAME)}
    if pfad == "/api/antwort":
        return sprache.gegenantwort(titel, preis, mein, str(d.get("antwort", ""))[:1000], NAME)
    with _sperre:      # /api/verhandlung: anlegen, ändern oder (stand = "weg") entfernen
        liste = [x for x in _lesen(HANDEL) if x.get("url") != url]
        if url and d.get("stand") != "weg":
            liste.insert(0, {"url": url, "titel": titel, "quelle": str(d.get("quelle", ""))[:20], "preis": preis, "mein": mein,
                             "stand": str(d.get("stand", "Nachricht kopiert"))[:60], "text": str(d.get("text", ""))[:1500], "zeit": time.strftime("%d.%m.%Y %H:%M")})
        os.makedirs(DATEN, exist_ok=True)
        with open(HANDEL + ".neu", "w", encoding="utf-8") as f:
            json.dump(liste[:200], f, ensure_ascii=False, indent=1)
        os.replace(HANDEL + ".neu", HANDEL)
    return liste


Antwort._handel = _handel


if __name__ == "__main__":
    print("TK Preisjäger %s auf Port %d" % (FASSUNG, PORT), flush=True)
    ThreadingHTTPServer(("0.0.0.0", PORT), Antwort).serve_forever()
