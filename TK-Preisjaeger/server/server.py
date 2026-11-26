#!/usr/bin/env python3
# TK Preisjäger – Webserver. Claude 26.11.2026
# Start: python3 server.py   (Port: PREISJAEGER_PORT, Vorgabe 8815)
import json
import os
import re
import statistics
import threading
import time
import functools
import math
import subprocess
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, wait
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import kern
import quellen
import sprache
import verhandler
import verkauf
import anfragen
import pflege

ORT = os.path.dirname(os.path.abspath(__file__))
DATEN = os.path.join(ORT, "daten")
MERK = os.path.join(DATEN, "merkliste.json")
HANDEL = os.path.join(DATEN, "verhandlungen.json")
NAME = os.environ.get("PREISJAEGER_NAME", "")      # Vorname für den Gruß in Nachrichten
PORT = int(os.environ.get("PREISJAEGER_PORT", "8815"))
FASSUNG = "4.7"
NEUES = "Automatische Antworten berichtigt: nur noch auf Nachrichten, die nach dem Einschalten eingehen – ältere Gespräche bleiben unberührt"      # kurzer Text zum letzten Stand


def _bau():
    """Baunummer zählt bei jeder Änderung an den Programmdateien von selbst hoch (beim Start des Dienstes) –
    so meldet die App jedes Einspielen als „Update verfügbar“, auch wenn die Fassungsnummer gleich blieb."""
    import hashlib
    h = hashlib.sha1()
    for n in sorted(os.listdir(ORT)):
        if n.endswith((".py", ".html")):
            with open(os.path.join(ORT, n), "rb") as f:
                h.update(f.read())
    pfad, jetzt = os.path.join(DATEN, "bau.json"), h.hexdigest()
    try:
        with open(pfad, encoding="utf-8") as f:
            d = json.load(f)
    except Exception:
        d = {"nr": 0, "hash": ""}
    if d.get("hash") != jetzt:
        d = {"nr": d.get("nr", 0) + 1, "hash": jetzt, "zeit": time.strftime("%d.%m.%Y %H:%M")}
        os.makedirs(DATEN, exist_ok=True)
        with open(pfad, "w", encoding="utf-8") as f:
            json.dump(d, f)
    return d


BAU = {"nr": 0, "zeit": ""}
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
            for marke_ende in ("Weitere Stichworte zu dem Produkt", "Kunden interessierten sich auch"):
                j = text.rfind(marke_ende)
                if j > len(text) * 0.4:      # nur wenn der Kasten wirklich im hinteren Teil steht
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


# ---------- Entfernung zwischen Postleitzahlen (Tabelle wird einmal geladen und in daten/ abgelegt) ----------
PLZ_QUELLE = "https://raw.githubusercontent.com/WZBSocialScienceCenter/plz_geocoord/master/plz_geocoord.csv"
_plz = {}


def _plz_laden():
    if _plz:
        return
    pfad = os.path.join(DATEN, "plz.csv")
    try:
        if not os.path.exists(pfad):
            os.makedirs(DATEN, exist_ok=True)
            urllib.request.urlretrieve(PLZ_QUELLE, pfad)
        with open(pfad, encoding="utf-8") as f:
            for z in f:
                t = z.strip().split(",")
                if len(t) == 3 and len(t[0]) == 5 and t[0].isdigit():
                    _plz[t[0]] = (float(t[1]), float(t[2]))
    except Exception:
        _plz["-"] = (0, 0)      # nicht verfügbar: Entfernungen bleiben leer


def entfernung(plz_a, plz_b):
    """Luftlinie in km zwischen zwei Postleitzahlen, None wenn unbekannt."""
    _plz_laden()
    a, b = _plz.get(str(plz_a)[:5]), _plz.get(str(plz_b)[:5])
    if not a or not b:
        return None
    p, q = math.radians(a[0]), math.radians(b[0])
    h = math.sin((q - p) / 2) ** 2 + math.cos(p) * math.cos(q) * math.sin(math.radians(b[1] - a[1]) / 2) ** 2
    return round(12742 * math.asin(math.sqrt(h)))


_ABGEDECKT = ("amazon", "ebay", "mediamarkt", "media markt", "saturn")


def idealo_ausbauen(roh, e):
    """Zu passenden idealo-Produkten die einzelnen Händlerangebote holen (idealo führt nur geprüfte Shops).
    Rückgabe: Namen der dort geführten Shops (für die Vertrauenseinstufung der Websuche)."""
    eltern, gesehen = [], set()
    for a in e["treffer"]:
        if a["quelle"] == "idealo" and not a.get("shop") and a["url"] not in gesehen:
            gesehen.add(a["url"])
            eltern.append(a)
    shops = set()
    if not eltern:
        return shops

    def lesen(a):
        try:
            return a, quellen.idealo_angebote(a["url"])
        except Exception:
            return a, []

    with ThreadPoolExecutor(max_workers=4) as topf:
        for a, angebote in topf.map(lesen, eltern[:4]):
            neu = []
            for o in angebote:
                shops.add(str(o["shop"]).lower())
                if str(o["shop"]).lower().startswith(_ABGEDECKT):
                    continue
                neu.append({"quelle": "idealo", "shop": o["shop"], "titel": o["titel"] or a["titel"], "pruef_titel": a.get("pruef_titel") or a["titel"],
                            "preis": o["preis"], "url": o["url"], "bild": a.get("bild", ""), "ort": "", "text": "", "zustand": "neu",
                            "versand": o["versand"], "hinweis": o["hinweis"], "vertrauen": "idealo"})
            if neu:
                for r in roh:
                    if r.get("quelle") == "idealo" and r.get("url") == a["url"] and not r.get("shop"):
                        r["ersetzt"] = True      # die Sammelzeile „günstigster von N Händlern“ weicht den Einzelangeboten
                roh.extend(neu)
    return shops


def vertrauen_einstufen(roh, anfrage, idealo_shops):
    """Shops aus der Websuche einstufen: bekannt / bei idealo gelistet / Herstellershop / unbekannt."""
    marke = (kern.flach(kern.zerlegen(anfrage)) or [""])[0]
    idealo_preise = {(str(r.get("shop")).lower(), round(r["preis"])) for r in roh if r.get("quelle") == "idealo" and r.get("shop")}
    for r in roh:
        if r.get("quelle") != "Web":
            continue
        d = str(r.get("shop", "")).lower()
        if r.get("vertrauen") == "unbekannt":
            if any(d and (d in s or s in d) for s in idealo_shops):
                r["vertrauen"] = "idealo"
            elif len(marke) >= 4 and marke in d.split(".")[-2 if d.count(".") else 0]:
                r["vertrauen"] = "hersteller"
        if any(d and (d in s or s in d) and p == round(r["preis"]) for s, p in idealo_preise):
            r["ersetzt"] = True      # derselbe Shop mit demselben Preis steht schon über idealo in der Liste


def unbekannte_trennen(e):
    """Unbekannte Shops kommen nie in die Hauptliste: mit Warnzeichen fliegen sie raus, sonst stehen sie getrennt („nicht geprüft“)."""
    sicher = [a["preis"] for a in e["treffer"] if a.get("art") == "händler" and a.get("vertrauen") != "unbekannt" and a.get("zustand") == "neu"]
    ref = min(sicher) if sicher else None
    unbekannt = []
    for k in ("treffer", "aehnlich"):
        rest = []
        for a in e[k]:
            if a.get("vertrauen") != "unbekannt":
                rest.append(a)
                continue
            m = a.get("merkmale") or {}
            zu_billig = (ref and a["preis"] < ref * 0.7) or (not ref and e.get("ueblich") and a["preis"] < e["ueblich"] * 0.5)
            if not m.get("impressum") or zu_billig:
                n = "unbekannter Shop mit Warnzeichen (kein Impressum oder auffällig billig)"
                e["aussortiert"][n] = e["aussortiert"].get(n, 0) + 1
            elif k == "treffer":
                unbekannt.append(a)
        e[k] = rest
    e["unbekannt"] = sorted(unbekannt, key=lambda a: a["preis"])[:20]


# Wie tief gelesen wird: (Kleinanzeigen-Seiten neueste, Kleinanzeigen-Seiten billigste, Vinted neueste, Vinted billigste)
TIEFE = {1: (4, 12, 2, 3), 2: (8, 40, 4, 8)}


# Schnäppchen-Radar: Produkte mit großem Gebrauchtmarkt, die sich schnell weiterverkaufen lassen
RADAR = ["iphone 13 128gb", "iphone 14 128gb", "iphone 15 128gb", "macbook air m1", "macbook air m2", "ipad 9 64gb", "playstation 5", "nintendo switch oled",
         "steam deck oled", "dyson v11", "dyson v15", "airpods pro 2", "apple watch series 9", "sony wh-1000xm5", "thermomix tm6"]
_radar = {"zeit": 0, "daten": None, "laeuft": False}


EIGENE = os.path.join(DATEN, "radar.json")      # von Tekin ergänzte Radar-Produkte
_sjobs = {}


def eigene_radar(neu=None, weg=None):
    try:
        with open(EIGENE, encoding="utf-8") as f:
            l = json.load(f)
    except Exception:
        l = []
    if neu or weg:
        if neu and neu.lower() not in [x.lower() for x in l + RADAR]:
            l.insert(0, " ".join(neu.split())[:80])
        l = [x for x in l if x != weg][:25]
        os.makedirs(DATEN, exist_ok=True)
        with open(EIGENE, "w", encoding="utf-8") as f:
            json.dump(l, f, ensure_ascii=False)
    return l


def _umkreis_alles(job, plz, km, eins):
    """Ohne Artikel: (A) alle Radar-Produkte im Umkreis, (B) die neuesten Anzeigen aus der Gegend – die KI sucht erkennbare
    Markenprodukte heraus, deren Preis mit dem bundesweiten Marktpreis verglichen wird."""
    liste = []
    namen = list(dict.fromkeys(eigene_radar() + RADAR))
    _sjobs[job]["schritt"] = "Prüfe %d gängige Produkte in deinem Umkreis …" % len(namen)
    with ThreadPoolExecutor(max_workers=3) as topf:
        for l in topf.map(lambda n: _sicher(lambda: eins(n, 1)), namen):
            liste += l[:8]
    kennung = quellen.ka_ort(plz)
    if not kennung:
        return liste
    _sjobs[job]["schritt"] = "Lese die neuesten Anzeigen aus deiner Gegend …"
    ort, roh, gesehen = (kennung, km), [], {a["url"] for a in liste}
    with ThreadPoolExecutor(max_workers=4) as topf:
        for l in topf.map(lambda x: _sicher(lambda: quellen.kleinanzeigen_umkreis(ort, x[0], x[1])), [(1, True), (2, True), (3, True), (4, True), (1, False), (2, False)]):
            roh += l
    kandidaten, da = [], set()
    for a in roh:
        if a.get("preis") and a["preis"] >= 60 and a["url"] not in da and a["url"] not in gesehen and not kern.ist_defekt(a["titel"], a.get("text", "")):
            da.add(a["url"])
            kandidaten.append(a)
    if not kandidaten:
        return liste
    _sjobs[job]["schritt"] = "%d Anzeigen aus deiner Gegend gelesen – suche erkennbare Markenprodukte heraus …" % len(kandidaten)
    wahl = sprache.auswahl(kandidaten[:140])

    def pruefen(x):
        nr, begriff = x
        a = dict(kandidaten[nr])
        s = (suche(begriff).get("schnaeppchen") or {})
        markt = s.get("markt")
        if not markt:
            return None
        gewinn = round(markt * 0.90) - a["preis"]
        if gewinn < 25 or gewinn < a["preis"] * 0.12:
            return None
        warn = kern.betrug(a["titel"] + " " + a.get("text", ""))
        m = re.match(r"(\d{5})", a.get("ort") or "")
        hoch = a["preis"] < markt * 0.5 or bool(warn)
        gruende = (["unter der Hälfte des Marktpreises – oft Lockpreis, Zubehör oder Betrug"] if a["preis"] < markt * 0.5 else []) + \
                  (["Warnzeichen in der Anzeige: " + warn[0]] if warn else []) + \
                  ["Produkt wurde von der KI aus dem Titel erkannt („%s“) – Modell, Ausstattung und Zustand selbst prüfen" % begriff]
        a.pop("text", None)
        return dict(a, quelle="Kleinanzeigen", art="privat", zustand="gebraucht", produkt=begriff, entdeckt=True, km=entfernung(plz, m.group(1)) if m else None,
                    markt=round(markt), wiederverkauf=round(markt * 0.90), ersparnis=round(markt - a["preis"]), ersparnis_pct=round((1 - a["preis"] / markt) * 100),
                    nebenkosten=0, gewinn=gewinn, rendite=round(gewinn / a["preis"] * 100), risiko="hoch" if hoch else "mittel", gruende=gruende)

    _sjobs[job]["schritt"] = "Vergleiche %d Fundstücke aus deiner Gegend mit dem Marktpreis …" % len(wahl)
    with ThreadPoolExecutor(max_workers=3) as topf:
        for r in topf.map(lambda x: _sicher(lambda: pruefen(x), None), wahl):
            if r:
                liste.append(r)
    _sjobs[job]["gelesen"] = len(kandidaten)
    return liste


def _sicher(fn, sonst=None):
    try:
        return fn()
    except Exception:
        return [] if sonst is None and sonst != 0 else sonst


def schnaeppchen_start(d):
    """Eigene Schnäppchen-Suche (läuft im Hintergrund): gründlich suchen, auf Wunsch auf verwandte Produkte ausweiten und auf den Umkreis begrenzen."""
    q = " ".join(str(d.get("q", "")).split())[:120]
    plz = str(d.get("plz") or "") if re.fullmatch(r"\d{5}", str(d.get("plz") or "")) else None
    km = int(float(d.get("km") or 30))
    alles = len(q) < 2      # ohne Artikel: alles im Umkreis durchsuchen
    if alles and not (plz and d.get("umkreis")):
        raise ValueError("Bitte ein Produkt eingeben – oder „nur im Umkreis“ wählen, dann wird alles in deiner Nähe durchsucht")
    job = "%d" % (time.time() * 1000)
    _sjobs[job] = {"laeuft": True, "schritt": "Durchsuche deine Gegend …" if alles else "Suche „%s“ gründlich …" % q, "liste": [], "produkte": []}
    if d.get("merken"):
        eigene_radar(neu=q)

    def lauf():
        try:
            liste, produkte = [], []

            def eins(name, tiefe):
                e = suche(name, True, tiefe, plz, km, False)
                s = e.get("schnaeppchen") or {}
                l = [dict(a, produkt=name) for a in s.get("liste", [])]
                if plz and d.get("umkreis"):      # nur, was sich im Umkreis abholen lässt
                    l = [a for a in l if a.get("km") is not None and a["km"] <= km * 1.25]
                gut = [a for a in l if a["risiko"] != "hoch"]
                produkte.append({"name": name, "markt": s.get("markt"), "angebote": len(e["treffer"]), "schnaeppchen": len(gut), "bester_gewinn": gut[0]["gewinn"] if gut else 0,
                                 "basis": s.get("anzahl_basis", 0)})
                return l

            if alles:
                liste += _umkreis_alles(job, plz, km, eins)
            else:
                liste += eins(q, 2)
            if d.get("ausweiten") and not alles:
                _sjobs[job]["schritt"] = "Weite die Suche auf verwandte Produkte aus …"
                _, namen = sprache.alternativen(q, "Der Käufer sucht günstige Angebote zum Weiterverkauf. Nenne direkt verwandte Produkte: Nachbarmodelle, "
                                                    "Vorgänger/Nachfolger und andere Größen desselben Geräts.", None)
                for n in namen[:3]:
                    _sjobs[job]["schritt"] = "Suche auch „%s“ …" % n
                    try:
                        liste += eins(n, 1)[:12]
                    except Exception:
                        pass
            liste.sort(key=lambda a: ({"niedrig": 0, "mittel": 1, "hoch": 2}[a["risiko"]], -a["gewinn"]))
            _sjobs[job].update(liste=liste[:80], produkte=produkte, zeit=time.strftime("%d.%m.%Y %H:%M"), umkreis={"plz": plz, "km": km} if plz and d.get("umkreis") else None)
        except Exception as x:
            _sjobs[job]["fehler"] = str(x)
        finally:
            _sjobs[job]["laeuft"] = False
            for k in sorted(_sjobs)[:-6]:
                _sjobs.pop(k, None)

    threading.Thread(target=lauf, daemon=True).start()
    return {"job": job}


def radar(neu=False):
    """Schnäppchen über die Radar-Produkte und die Merkliste. Läuft im Hintergrund (dauert Minuten); geliefert wird der letzte fertige
    Stand, mit laeuft=True, solange ein Durchgang arbeitet. Ergebnis gilt 30 Minuten."""
    alt = _radar["daten"]
    if (neu or not alt or time.time() - _radar["zeit"] > 1800) and not _radar["laeuft"]:
        _radar["laeuft"] = True
        threading.Thread(target=_radar_lauf, daemon=True).start()
    return dict(alt or {"liste": [], "produkte": [], "zeit": ""}, laeuft=_radar["laeuft"], eigene=eigene_radar())


def _radar_lauf(melde=False):
    try:
        namen = list(dict.fromkeys(eigene_radar() + RADAR + [m["anfrage"] for m in _merk_lesen()[:10] if not _AB.search(m["anfrage"])]))

        def eins(n):
            try:
                e = suche(n)
                return n, e.get("schnaeppchen") or {}, len(e["treffer"])
            except Exception:
                return n, {}, 0

        liste, produkte = [], []
        with ThreadPoolExecutor(max_workers=3) as topf:
            for n, s, zahl in topf.map(eins, namen):
                gut = [a for a in s.get("liste", []) if a["risiko"] != "hoch"]
                produkte.append({"name": n, "markt": s.get("markt"), "angebote": zahl, "schnaeppchen": len(gut), "bester_gewinn": gut[0]["gewinn"] if gut else 0})
                liste += [dict(a, produkt=n) for a in s.get("liste", [])[:6]]
        liste.sort(key=lambda a: ({"niedrig": 0, "mittel": 1, "hoch": 2}[a["risiko"]], -a["gewinn"]))
        _radar.update(zeit=time.time(), daten={"liste": liste[:60], "produkte": sorted(produkte, key=lambda p: -p["bester_gewinn"]), "zeit": time.strftime("%d.%m.%Y %H:%M")})
        if melde:      # automatischer Lauf: die besten neuen Funde melden (geringes Risiko, mindestens 120 € und 25 % Gewinn), höchstens drei
            neu_ = [a for a in liste if a["risiko"] == "niedrig" and a["gewinn"] >= 120 and a["rendite"] >= 25 and a["url"] not in _radar.setdefault("gemeldet", set())][:3]
            for a in neu_:
                _radar["gemeldet"].add(a["url"])
                melden("💰 Preisjäger-Radar: %s für %s (üblich %s) – möglicher Gewinn rund %s\n%s\n%s" % (
                    a["produkt"], _eur(a["preis"]), _eur(a["markt"]), _eur(a["gewinn"]), a["titel"][:80], a["url"]))
    except Exception as x:
        print("Radar:", x, flush=True)
    finally:
        _radar["laeuft"] = False


_AB = re.compile(r"\bab\s+([a-zA-Z]{0,3})(\d{1,2})\b(?!\s*(?:€|euro|eur|gb|tb|zoll|km|jahre?)\b)", re.I)


def suche(anfrage, streng=True, tiefe=1, plz=None, km=None, nur_abholung=False):
    """„Mac mini ab M4“ heißt: M4 oder neuer. Dann wird je Generation (M4, M5, M6, M7) gesucht und zusammengeführt."""
    anfrage = " ".join(anfrage.split())[:120]
    m = _AB.search(anfrage)
    if not m:
        return _suche_eine(anfrage, streng, tiefe, plz, km, nur_abholung)
    stufen = [m.group(1) + str(int(m.group(2)) + i) for i in range(4)]
    texte = [(anfrage[:m.start()] + st + anfrage[m.end():]).strip() for st in stufen]
    with ThreadPoolExecutor(max_workers=4) as topf:
        teile = list(topf.map(lambda t: _suche_eine(t, streng, tiefe, plz, km, nur_abholung), texte))
    e = dict(teile[0])
    for k in ("treffer", "aehnlich", "auffaellig", "defekt", "unbekannt", "versand"):
        alle = []
        for st, teil in zip(stufen, teile):
            alle += [dict(a, variante=st.upper()) for a in teil.get(k, [])]
        e[k] = sorted(alle, key=lambda a: a["preis"])[:600 if k == "treffer" else 60]
    e["quellen"] = [dict(q, gefunden=sum(x["gefunden"] for t in teile for x in t["quellen"] if x["name"] == q["name"]),
                         passend=sum(x["passend"] for t in teile for x in t["quellen"] if x["name"] == q["name"])) for q in teile[0]["quellen"]]
    e["ueblich"] = statistics.median([a["preis"] for a in e["treffer"]]) if len(e["treffer"]) >= 5 else None
    e["schnaeppchen"] = kern.schnaeppchen(e)
    e.update(anfrage=anfrage, gelesen=sum(t.get("gelesen", 0) for t in teile), dauer=max(t["dauer"] for t in teile), links=quellen.links(texte[0]),
             stufen=[{"name": st.upper(), "treffer": len(t["treffer"]), "ab": t["treffer"][0]["preis"] if t["treffer"] else None, "suche": x}
                     for st, t, x in zip(stufen, teile, texte)],
             groessen={}, andere_ausfuehrungen={}, verstanden=None, produkt=texte[0])
    if not plz:
        _merk_stand(e)
    return e


def _suche_eine(anfrage, streng=True, tiefe=1, plz=None, km=None, nur_abholung=False):
    anfrage = " ".join(anfrage.split())[:120]
    tiefe = 2 if tiefe == 2 else 1
    ka_neu, ka_billig, vi_neu, vi_billig = TIEFE[tiefe]
    plz = plz if plz and len(str(plz)) == 5 and str(plz).isdigit() else None
    km = int(km) if km and plz else None
    schluessel = (anfrage.lower(), streng, tiefe, plz, km, bool(nur_abholung))
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
    if not plz and v.get("plz"):      # „… zum Abholen in 44137, 20 km“ im Freitext
        plz, km, nur_abholung = v["plz"], int(v.get("umkreis") or 30), True
    ort = None
    if plz:
        kennung = quellen.ka_ort(plz)
        ort = (kennung, km or 30) if kennung else None
    ka = functools.partial(quellen.kleinanzeigen, ort=ort) if ort else quellen.kleinanzeigen
    aktiv = lambda: [dict(a) for a in roh if not a.get("ersetzt")]
    roh, status = [], {n: {"name": n, "gefunden": 0, "passend": 0, "fehler": ""} for n, _, _, _ in quellen.QUELLEN}

    def sammeln(auftraege, stichprobe=False):
        # stichprobe=True: unsortierte Treffer (Reihenfolge der Seite) – nur sie zählen für den Marktpreis der Schnäppchen-Rechnung
        with ThreadPoolExecutor(max_workers=10) as p:
            laeufe = [p.submit(_lauf, *a) for a in auftraege]
            wait(laeufe, timeout=30 * tiefe)
            for l in laeufe:
                if not l.done():
                    continue
                name, liste, fehler = l.result()
                for a in liste:
                    a.setdefault("quelle", name)
                    if stichprobe:
                        a["stichprobe"] = True
                roh.extend(liste)
                status[name]["gefunden"] += len(liste)
                if fehler and not status[name]["fehler"]:
                    status[name]["fehler"] = fehler

    # 1. Durchgang: jede Quelle mit dem Suchtext (Kleinanzeigen und Vinted mehrere Seiten)
    quellen.GESAMT.pop("Kleinanzeigen", None)
    sammeln([(n, ka if n == "Kleinanzeigen" else f, anfrage, None, 1) for n, f, _, _ in quellen.QUELLEN]
            + [("Kleinanzeigen", ka, anfrage, None, s) for s in range(2, ka_neu + 1)]
            + [("Vinted", quellen.vinted, anfrage, None, s) for s in range(2, vi_neu + 1)], stichprobe=True)
    e = kern.bewerten(anfrage, aktiv(), streng)
    nachpruefen(anfrage, roh, streng)
    e = kern.bewerten(anfrage, aktiv(), streng)
    # Händler hinter idealo einzeln holen und die Shops aus der Websuche einstufen
    idealo_shops = idealo_ausbauen(roh, e)
    vertrauen_einstufen(roh, anfrage, idealo_shops)
    e = kern.bewerten(anfrage, aktiv(), streng)
    # Kaum Treffer: Die Seiten verlangen oft alle Wörter. Dann zusätzlich mit einem Beschreibungswort weniger suchen;
    # bewertet wird weiter gegen den vollen Suchtext (fehlt nur dieses Wort im Titel, steht es unter „fast passend“).
    if len(e["treffer"]) < 3:
        for kuerzer, _ in kern.kuerzungen(anfrage)[:2]:
            sammeln([(n, ka if n == "Kleinanzeigen" else f, kuerzer, None, 1) for n, f, _, _ in quellen.QUELLEN if n != "Web"])
        vertrauen_einstufen(roh, anfrage, idealo_shops)
        e = kern.bewerten(anfrage, aktiv(), streng)
    # 2. Durchgang: Der übliche Preis ist jetzt bekannt -> auf den Privatmärkten gezielt die billigsten echten Angebote holen
    # (ab der Hälfte des üblichen Preises, nach Preis sortiert; darunter liegt fast nur Zubehör)
    if e["ueblich"]:
        ab = max(1, int(e["ueblich"] * kern.GRENZE))
        tief_ab = max(1, int(e["ueblich"] * 0.2))      # auch die extremen Ausreißer lesen (20–50 % des Üblichen): dort liegen die echten Schnäppchen – und viel Zubehör
        sammeln([("Kleinanzeigen", ka, anfrage, ab, s) for s in range(1, ka_billig + 1)]
                + [("Kleinanzeigen", ka, anfrage, tief_ab, s) for s in range(1, 5)]
                + [("Vinted", quellen.vinted, anfrage, tief_ab, 1)]
                + ([("Kleinanzeigen", quellen.kleinanzeigen, anfrage, ab, s) for s in range(1, 7)] if ort else [])
                + [("Vinted", quellen.vinted, anfrage, ab, s) for s in range(1, vi_billig + 1)])
        e = kern.bewerten(anfrage, aktiv(), streng, e["ueblich"])
    arten = {n: art for n, _, art, _ in quellen.QUELLEN}
    for l in (e["treffer"], e["auffaellig"], e["defekt"], e["aehnlich"]):
        for a in l:
            a["art"] = arten.get(a["quelle"], "")
    e = kern.wuensche_anwenden(e, v)
    unbekannte_trennen(e)
    # Abholung: Entfernung je Angebot (Luftlinie zwischen den Postleitzahlen); bei „nur Abholung“ bleibt nur, was im Umkreis liegt
    if plz:
        for k in ("treffer", "aehnlich", "auffaellig", "defekt"):
            for a in e[k]:
                m = kern.re.match(r"(\d{5})", a.get("ort") or "")
                if m:
                    a["km"] = entfernung(plz, m.group(1))
            if nur_abholung:
                nah = lambda a: a["quelle"] == "Kleinanzeigen" and a.get("ort") and a.get("km") is not None and a["km"] <= (km or 30) * 1.25
                bleibt = [a for a in e[k] if nah(a)]
                if k == "treffer":
                    # weiter weg, aber mit Versand: getrennt anbieten (Zahlung mit PayPal-Käuferschutz statt Abholung)
                    e["versand"] = [a for a in e[k] if a["quelle"] == "Kleinanzeigen" and not nah(a) and "Versand möglich" in (a.get("hinweis") or "")][:40]
                    weg = len(e[k]) - len(bleibt) - len(e["versand"])
                    if weg > 0:
                        e["aussortiert"]["nicht im Umkreis und kein Versand angeboten / andere Seiten"] = weg
                e[k] = bleibt
        e["unbekannt"] = [] if nur_abholung else e["unbekannt"]
    e.setdefault("versand", [])
    for a in e["versand"]:
        a.pop("text", None)
    e["abholung"] = {"plz": plz, "km": km or 30, "nur": bool(nur_abholung), "ort_bekannt": bool(ort)} if plz else None
    for a in e["treffer"]:
        status[a["quelle"]]["passend"] += 1
    for l in (e["treffer"], e["auffaellig"], e["defekt"], e["aehnlich"], e["unbekannt"]):
        for a in l:
            a.pop("text", None)
            a.pop("merkmale", None)
    if "Kleinanzeigen" in quellen.GESAMT:
        status["Kleinanzeigen"]["gesamt"] = quellen.GESAMT["Kleinanzeigen"]
    e["tiefe"], e["gelesen"] = tiefe, len({(a.get("quelle"), a.get("url")) for a in roh})
    e.update(anfrage=voll, produkt=anfrage, verstanden=v if voll.lower() != anfrage.lower() else None, streng=streng, quellen=list(status.values()), links=quellen.links(anfrage),
             groessen=kern.groessen(anfrage, e["treffer"]), dauer=round(time.time() - start, 1), zeit=time.strftime("%d.%m.%Y %H:%M"))
    e["schnaeppchen"] = kern.schnaeppchen(e)
    e["defekt"], e["auffaellig"] = e["defekt"][:40], sorted(e["auffaellig"], key=lambda a: -a["preis"])[:60]
    with _sperre:
        _speicher[schluessel] = (time.time(), e)
        for k in [k for k, v in _speicher.items() if time.time() - v[0] > 3600]:
            _speicher.pop(k, None)
    if not plz:
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


MELDEN = os.path.expanduser(os.environ.get("PREISJAEGER_MELDEN", "~/.hermes/scripts/notify.sh"))      # Skript: melden "Text" (Telegram)


def melden(text):
    try:
        if os.path.exists(MELDEN):
            subprocess.run([MELDEN, text[:900]], timeout=25)
            return True
    except Exception:
        pass
    return False


def _merk_stand(e, alarm=False):
    """Nach jeder Suche: steht der Suchtext auf der Merkliste, besten Preis und Verlauf festhalten.
    alarm=True (Preiswächter): melden, wenn der Zielpreis erreicht ist oder der Preis um mindestens 5 % gefallen ist."""
    meldungen = []
    with _sperre:
        liste, da = _merk_lesen(), False
        for m in liste:
            if m["anfrage"].lower() == e["anfrage"].lower() and e["treffer"]:
                b = e["treffer"][0]
                alt = m.get("preis")
                m["vorher"] = alt
                m.update(preis=b["preis"], quelle=b.get("shop") or b["quelle"], url=b["url"], zeit=e["zeit"])
                m["tiefst"] = min(b["preis"], m.get("tiefst") or b["preis"])
                v = m.setdefault("verlauf", [])
                if not v or v[-1][1] != b["preis"] or v[-1][0][:10] != e["zeit"][:10]:
                    v.append([e["zeit"], b["preis"]])
                    del v[:-120]
                if alarm:
                    ziel = m.get("ziel")
                    if ziel and b["preis"] <= ziel and m.get("gemeldet") != b["preis"]:
                        meldungen.append("🎯 Preisjäger: „%s“ für %s (dein Ziel: %s) bei %s\n%s\n%s" % (m["anfrage"], _eur(b["preis"]), _eur(ziel), m["quelle"], b["titel"][:80], b["url"]))
                        m["gemeldet"] = b["preis"]
                    elif alt and b["preis"] <= alt * 0.95 and m.get("gemeldet") != b["preis"]:
                        meldungen.append("📉 Preisjäger: „%s“ jetzt %s (vorher %s) bei %s\n%s\n%s" % (m["anfrage"], _eur(b["preis"]), _eur(alt), m["quelle"], b["titel"][:80], b["url"]))
                        m["gemeldet"] = b["preis"]
                da = True
        if da:
            _merk_schreiben(liste)
    for t in meldungen:
        melden(t)


def waechter():
    """Preiswächter: alle 3 Stunden jede gemerkte Suche neu laufen lassen (höchstens 20) und bei Zielpreis/Preissturz melden."""
    time.sleep(120)
    while True:
        for m in _merk_lesen()[:20]:
            try:
                with _sperre:
                    for k in [k for k in _speicher if k[0] == m["anfrage"].lower()]:
                        _speicher.pop(k, None)
                _merk_stand(suche(m["anfrage"]), alarm=True)
            except Exception as x:
                print("Preiswächter:", m.get("anfrage"), x, flush=True)
            time.sleep(20)
        if not _radar["laeuft"]:      # alle 3 Stunden auch den Schnäppchen-Radar laufen lassen und sehr gute Funde melden
            _radar["laeuft"] = True
            _radar_lauf(melde=True)
        time.sleep(3 * 3600)


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
                b = f.read().replace(b"{{FASSUNG}}", FASSUNG.encode()).replace(b"{{BAU}}", str(BAU["nr"]).encode())
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
                self._json(suche(a, (p.get("streng") or ["1"])[0] != "0", 2 if (p.get("tief") or ["0"])[0] == "1" else 1,
                                 (p.get("plz") or [""])[0].strip() or None, (p.get("km") or ["30"])[0], (p.get("abholung") or ["0"])[0] == "1"))
            except Exception as e:
                self._json({"fehler": "Suche fehlgeschlagen: %s" % e}, 500)
        elif u.path in ("/symbol-180.png", "/symbol-512.png", "/apple-touch-icon.png", "/apple-touch-icon-precomposed.png"):
            with open(os.path.join(ORT, "symbol-512.png" if "512" in u.path else "symbol-180.png"), "rb") as f:
                b = f.read()
            self.send_response(200)
            self.send_header("Content-Type", "image/png")
            self.send_header("Content-Length", str(len(b)))
            self.send_header("Cache-Control", "max-age=86400")
            self.end_headers()
            self.wfile.write(b)
        elif u.path == "/manifest.json":
            self._json({"name": "TK Preisjäger", "short_name": "Preisjäger", "start_url": "/", "display": "standalone", "background_color": "#0d1216",
                        "theme_color": "#0a7d55", "lang": "de", "icons": [{"src": "/symbol-180.png", "sizes": "180x180", "type": "image/png"},
                                                                          {"src": "/symbol-512.png", "sizes": "512x512", "type": "image/png"}]})
        elif u.path == "/api/merkliste":
            self._json(_merk_lesen())
        elif u.path == "/api/konto":
            self._json(verhandler.konto())
        elif u.path == "/api/schnaeppchen":
            self._json(_sjobs.get((p.get("job") or [""])[0]) or {"fehler": "Suche nicht gefunden"})
        elif u.path == "/api/pflege":
            self._json(pflege.stand())
        elif u.path == "/api/anfragen":
            self._json(anfragen.stand())
        elif u.path == "/api/radar":
            try:
                self._json(radar((p.get("neu") or ["0"])[0] == "1"))
            except Exception as e:
                self._json({"fehler": "Radar fehlgeschlagen: %s" % e}, 500)
        elif u.path == "/api/verkauf":
            self._json({"artikel": verkauf.liste(), "portale": [{"name": n, "url": x} for n, x in verkauf.PORTALE]})
        elif u.path.startswith("/verkauf/bild/"):
            t = u.path.split("/")
            pfad = verkauf.bildpfad(t[3], t[4]) if len(t) == 5 else None
            if not pfad:
                return self.send_error(404)
            with open(pfad, "rb") as f:
                b = f.read()
            self.send_response(200)
            self.send_header("Content-Type", "image/jpeg")
            self.send_header("Content-Length", str(len(b)))
            self.end_headers()
            self.wfile.write(b)
        elif u.path == "/api/auto":
            self._json(verhandler.liste())
        elif u.path == "/api/verhandlungen":
            self._json(_lesen(HANDEL))
        elif u.path == "/api/stand":
            self._json({"name": "TK Preisjäger", "fassung": FASSUNG, "bau": BAU["nr"], "bau_zeit": BAU.get("zeit", ""), "neues": NEUES, "quellen": [n for n, _, _, _ in quellen.QUELLEN]})
        else:
            self.send_error(404)

    def do_POST(self):
        u = urllib.parse.urlparse(self.path)
        try:
            grenze = 16_000_000 if u.path == "/api/verkauf/neu" else 60_000
            d = json.loads(self.rfile.read(min(int(self.headers.get("Content-Length") or 0), grenze)) or b"{}")
        except Exception:
            d = {}
        a = " ".join(str(d.get("anfrage", "")).split())[:120]
        if u.path == "/api/schnaeppchen/start":
            try:
                return self._json(schnaeppchen_start(d))
            except Exception as e:
                return self._json({"fehler": str(e)}, 400)
        if u.path == "/api/radar/eigene":
            return self._json({"eigene": eigene_radar(neu=str(d.get("neu") or "") or None, weg=str(d.get("weg") or "") or None)})
        if u.path.startswith("/api/pflege/"):
            try:
                if u.path == "/api/pflege/start":
                    return self._json(pflege.start(anfragen.stand()["anzeigen"], suche, bool(d.get("nur_fehlende"))))
                if u.path == "/api/pflege/uebernehmen":
                    return self._json(pflege.uebernehmen(str(d.get("adid", "")), d))
                return self.send_error(404)
            except Exception as e:
                return self._json({"fehler": str(e)}, 400)
        if u.path.startswith("/api/anfragen/"):
            try:
                if u.path == "/api/anfragen/einstellen":
                    return self._json(anfragen.einstellen(d))
                if u.path == "/api/anfragen/antwort":
                    return self._json(anfragen.eigene_antwort(str(d.get("schluessel", "")), d.get("text", "")))
                if u.path == "/api/anfragen/jetzt":
                    threading.Thread(target=verhandler.lauf, daemon=True).start()
                    return self._json(anfragen.stand())
                return self.send_error(404)
            except Exception as e:
                return self._json({"fehler": str(e)}, 400)
        if u.path.startswith("/api/verkauf/"):
            try:
                k = str(d.get("id", ""))
                if u.path == "/api/verkauf/neu":
                    return self._json(verkauf.neu(d))
                if u.path == "/api/verkauf/erkennen":
                    return self._json(verkauf.erkennen(k, suche))
                if u.path == "/api/verkauf/preis":
                    return self._json(verkauf.preis_neu(k, d.get("suchbegriff", ""), suche))
                if u.path == "/api/verkauf/speichern":
                    return self._json(verkauf.speichern(k, d))
                if u.path == "/api/verkauf/einstellen":
                    verkauf.speichern(k, d)
                    return self._json(verkauf.einstellen(k, "veroeffentlichen" if d.get("modus") == "veroeffentlichen" else "entwurf"))
                if u.path == "/api/verkauf/weg":
                    return self._json(verkauf.loeschen(k))
                return self.send_error(404)
            except Exception as e:
                return self._json({"fehler": str(e)}, 400)
        if u.path.startswith("/api/auto/"):
            try:
                if u.path == "/api/auto/start":
                    verhandler.starten(d)
                elif u.path == "/api/auto/stop":
                    verhandler.stoppen(str(d.get("id", "")))
                elif u.path == "/api/auto/antwort":
                    verhandler.eigene_antwort(str(d.get("id", "")), d.get("text", ""))
                return self._json(verhandler.liste())
            except Exception as e:
                return self._json({"fehler": str(e)}, 400)
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
                original, verkaeufer = quellen.anbietertext(url) if url else ("", "")
                return self._json(dict(e, belegt=bool(angaben), warn=kern.betrug(angaben + " " + original), anbietertext=original, verkaeufer=verkaeufer))
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
                try:
                    ziel = float(d.get("ziel") or 0)
                except Exception:
                    ziel = 0
                for m in liste:
                    if m["anfrage"].lower() == a.lower() and ziel > 0:
                        m["ziel"] = ziel
                        m.pop("gemeldet", None)
                _merk_schreiben(liste)
            with _sperre:
                alt = next((w for k, w in _speicher.items() if k[0] == a.lower() and not k[3]), None)
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
        return {"text": sprache.nachricht(titel, preis, mein, str(d.get("quelle", "Kleinanzeigen"))[:20], NAME, "versand" if d.get("weg") == "versand" else "abholung")}
    if pfad == "/api/antwort":
        return sprache.gegenantwort(titel, preis, mein, str(d.get("antwort", ""))[:1000], NAME, "versand" if d.get("weg") == "versand" else "abholung")
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
    BAU.update(_bau())
    print("Bau", BAU["nr"], flush=True)
    threading.Thread(target=waechter, daemon=True).start()
    verhandler.melden = melden
    anfragen.melden = melden
    verhandler.zusatz.append(anfragen.lauf)
    threading.Thread(target=verhandler.waechter, daemon=True).start()
    ThreadingHTTPServer(("0.0.0.0", PORT), Antwort).serve_forever()
