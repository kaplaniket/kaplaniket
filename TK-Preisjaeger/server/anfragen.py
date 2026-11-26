# TK Preisjäger – Anfragen zu Tekins eigenen Kleinanzeigen automatisch beantworten. Claude 26.11.2026
# Auftrag Tekin 26.11.2026: „übernimm meine in Kleinanzeigen laufenden Anzeigen und antworte auf neue Anfragen ab jetzt automatisch“.
# Arbeitet im eigenen Chrome-Fenster über die sichtbare Seite (Postfach lesen, Antwortfeld ausfüllen, senden).
#
# Leitplanken: beantwortet wird nur, was in der Anzeige steht – sonst „das kläre ich“ und Meldung an Tekin · nie unter den Mindestpreis ·
# nie Adresse, Telefonnummer oder Termin zusagen (das macht Tekin) · bei Betrugszeichen keine Antwort, nur Warnung ·
# höchstens 6 automatische Antworten je Gespräch · je Anzeige und insgesamt abschaltbar · „ab jetzt“: Was beim ersten Lauf schon
# im Postfach lag, wird nicht angefasst.
import json
import os
import re
import threading
import time

import kern
import quellen
import sprache
import verhandler

ORT = os.path.dirname(os.path.abspath(__file__))
DATEI = os.path.join(ORT, "daten", "anfragen.json")
NAME = os.environ.get("PREISJAEGER_NAME", "")
HOECHSTENS = 6
_sperre = threading.Lock()
melden = lambda text: None      # setzt der Server (Telegram)

# typische Maschen von Schein-Käufern (zusätzlich zu kern.betrug)
_KAEUFER_MASCHEN = [
    (r"kurier|abholdienst|spedition|dhl.{0,20}(holt|abhol)|bote\b", "Kurier/Abholdienst soll zahlen oder abholen"),
    (r"sicher(e|er|es)?\s*(bezahl|zahl)\w*.{0,40}(link|karte|bestätig)|zahlung\s*erhalten.{0,40}(link|bestätig)|geld\s*(liegt|wartet|bereit).{0,40}(link|bestätig)", "angebliche Zahlung über einen Link bestätigen"),
    (r"e-?mail\s*adresse|deine\s*(mail|nummer|handynummer|telefonnummer)|nummer\s*(geben|schicken|senden)", "fragt nach Mail-Adresse oder Telefonnummer"),
    (r"(mein|meine)\s*(sohn|tochter|cousin|bruder|schwester|frau|mann).{0,40}(holt|überweis|zahl)|für\s*mein(en)?\s*(sohn|tochter|cousin)", "Dritter soll zahlen oder abholen"),
    (r"mehr\s*(zahlen|bezahlen|geld).{0,40}(versand|reserv)|(zahle|gebe)\s*(dir\s*)?\d+\s*(€|euro)?\s*mehr", "bietet freiwillig mehr Geld"),
]

JS_ANZEIGEN = """
return [...document.querySelectorAll('li[data-testid=ad-card][data-adid]')].map(li => {
  const a = [...li.querySelectorAll('a[href*="/s-anzeige/"]')].map(x => ({t: x.innerText.replace(/^\\s*Anzeige\\s*/, '').replace(/\\s+/g, ' ').trim(), h: x.href})).filter(x => x.t).sort((x, y) => y.t.length - x.t.length)[0] || {};
  const text = li.innerText.replace(/\\s+/g, ' ');
  const p = text.match(/(\\d[\\d.]*)\\s*€(\\s*VB)?/);
  return {adid: li.dataset.adid, titel: a.t || '', url: a.h || '', preis: p ? parseFloat(p[1].replace(/\\./g, '')) : 0, vb: !!(p && p[2]),
          besucher: (text.match(/(\\d+) Besucher/) || [])[1] || '', gemerkt: (text.match(/(\\d+) mal gemerkt/) || [])[1] || '0',
          endet: (text.match(/Endet am ([\\d.]+)/) || [])[1] || '', bild: (li.querySelector('img') || {}).src || '',
          pausiert: /pausiert|deaktiviert|gelöscht|abgelaufen/i.test(text), reserviert: /reserviert/i.test(text)};
}).filter(x => x.titel);"""

JS_LISTE = """
return [...document.querySelectorAll('.ConversationByDateList article')].slice(0, 20).map(a => {
  const s = [...a.querySelectorAll('*')].filter(x => x.children.length === 0 && x.innerText && x.innerText.trim()).map(x => x.innerText.trim());
  const datum = s.find(t => /^(Heute|Gestern)\\b|^\\d\\d\\.\\d\\d\\.\\d{4}/.test(t)) || '';
  return {name: s[0] || '', datum, sig: s.join(' | ').slice(0, 200)};
});"""

JS_KLICK = """
const a = [...document.querySelectorAll('.ConversationByDateList article')][arguments[0]];
if (!a) return false;
(a.querySelector('a,[role=button]') || a).click();
return true;"""


def _lesen():
    try:
        with open(DATEI, encoding="utf-8") as f:
            d = json.load(f)
    except Exception:
        d = {}
    d.setdefault("aktiv", True)
    d.setdefault("anzeigen", {})
    d.setdefault("gespraeche", {})
    d.setdefault("liste", [])
    d.setdefault("aktiv_seit", 0)      # Zeitpunkt des Einschaltens: nur was danach hereinkommt, wird angefasst
    d.setdefault("tag", {"datum": "", "antworten": 0})
    d.setdefault("anzeigen_zeit", 0)
    return d


def _schreiben(d):
    os.makedirs(os.path.dirname(DATEI), exist_ok=True)
    with open(DATEI + ".neu", "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=1)
    os.replace(DATEI + ".neu", DATEI)


def _eur(n):
    return ("%.2f" % n).replace(".", ",").replace(",00", "") + " €"


def _jetzt():
    return time.strftime("%d.%m.%Y %H:%M")


def stand():
    d = _lesen()
    return {"aktiv": d["aktiv"], "anzeigen": sorted(d["anzeigen"].values(), key=lambda a: a.get("titel", "")),
            "gespraeche": sorted(d["gespraeche"].values(), key=lambda g: g.get("geaendert_s", 0), reverse=True)[:60], "anzeigen_stand": d.get("anzeigen_stand", "")}


def einstellen(e):
    """aktiv an/aus, oder je Anzeige: auto an/aus und Mindestpreis."""
    with _sperre:
        d = _lesen()
        if "aktiv" in e:
            if bool(e["aktiv"]) and not d["aktiv"]:
                d["aktiv_seit"] = time.time()      # „ab jetzt“ zählt ab dem Einschalten
            d["aktiv"] = bool(e["aktiv"])
        a = d["anzeigen"].get(str(e.get("adid", "")))
        if a:
            if "auto" in e:
                a["auto"] = bool(e["auto"])
            if "mindest" in e:
                try:
                    a["mindest"] = max(0, int(float(e["mindest"])))
                    a["mindest_gesetzt"] = True
                except Exception:
                    pass
        _schreiben(d)
    return stand()


def eigene_antwort(schluessel, text):
    text = " ".join(str(text).split())[:1200]
    if len(text) < 2:
        raise ValueError("Bitte einen Text eingeben")
    with _sperre:
        d = _lesen()
        g = d["gespraeche"].get(schluessel)
        if not g:
            raise ValueError("Gespräch nicht gefunden")
        g["zu_senden"] = text
        _schreiben(d)
    threading.Thread(target=verhandler.lauf, daemon=True).start()
    return stand()


def anzeigen_holen(b, d):
    """Tekins laufende Anzeigen aus „Meine Anzeigen“ lesen; neue bekommen Mindestpreis 90 % (VB) bzw. 100 % (Festpreis)."""
    b.geh("https://www.kleinanzeigen.de/m-meine-anzeigen.html", 5)
    funde = b.js(JS_ANZEIGEN) or []
    if not funde:
        return
    da = {}
    for f in funde:
        alt = d["anzeigen"].get(f["adid"], {})
        a = dict(alt, **f)
        a.setdefault("auto", True)
        if not alt.get("mindest_gesetzt"):
            a["mindest"] = int(round(f["preis"] * (0.9 if f["vb"] else 1.0)))
        if not a.get("text") and f["url"]:
            a["text"] = quellen.anbietertext(f["url"])[0][:3000]
        da[f["adid"]] = a
    d["anzeigen"], d["anzeigen_zeit"], d["anzeigen_stand"] = da, time.time(), _jetzt()


def _antwort_sicher(text, a):
    """Nie unter den Mindestpreis, nie Adresse/Telefon: sonst ein neutraler Satz."""
    t = text.lower()
    for z in re.findall(r"(\d{1,3}(?:\.\d{3})+|\d+)(?:,\d+)?\s*(?:€|euro)", t):
        w = float(z.replace(".", ""))
        if 5 < w < a.get("mindest", 0) - 0.5:
            return "Danke für dein Angebot. Mein letzter Preis wäre %s. Viele Grüße%s" % (_eur(a["mindest"]), (", " + NAME) if NAME else "")
    if re.search(r"\b\d{5}\s+[a-zäöü]|straße|str\.\s*\d|\b01[5-7]\d[\d /-]{6,}|\+49", t):
        return "Danke für deine Nachricht – die Einzelheiten zur Übergabe schreibe ich dir gleich persönlich. Viele Grüße%s" % ((", " + NAME) if NAME else "")
    return text


TAGESGRENZE = 25      # Sicherung: mehr automatische Antworten gibt es an einem Tag nicht


def _behandeln(b, d, a, v, partner, probe=False):
    schluessel = a["adid"] + "|" + partner
    g = d["gespraeche"].setdefault(schluessel, {"schluessel": schluessel, "adid": a["adid"], "titel": a["titel"], "partner": partner, "gesehen": 0,
                                                 "antworten": 0, "stand": "neu", "verlauf": [], "hinweis": ""})
    n = v["nachrichten"]
    vom_kaeufer = [m["text"] for m in n if m["von"] == "verk"]      # „verk“ heißt hier: die Gegenseite (eingehend)
    if g.get("zu_senden"):
        if verhandler._antworten(b, {}, g["zu_senden"]):
            g["verlauf"].append({"von": "ich", "text": g["zu_senden"], "zeit": _jetzt()})
            g.update(zu_senden="", geaendert=_jetzt(), geaendert_s=time.time())
        return
    # Neu ist nur, was NACH meiner letzten Nachricht hereingekommen ist. Habe ich (oder Tekin) zuletzt geschrieben, ist nichts offen.
    schwanz = []
    for m in reversed(n):
        if m["von"] != "verk":
            break
        schwanz.insert(0, m["text"])
    neu = " ".join(schwanz)[:1500]
    if not neu or neu == g.get("letzte_neu"):
        return
    if probe:
        return "würde antworten auf: " + neu[:80]
    g["letzte_neu"] = neu
    erstkontakt = not any(m["von"] != "verk" for m in n)
    g["verlauf"].append({"von": "kaeufer", "text": neu, "zeit": _jetzt()})
    g.update(geaendert=_jetzt(), geaendert_s=time.time())
    warn = kern.betrug(neu) + [h for m, h in _KAEUFER_MASCHEN if re.search(m, neu.lower())]
    if warn:
        g.update(stand="betrug", hinweis=" · ".join(warn))
        return melden("⚠ Preisjäger: BETRUGSVERDACHT bei Anfrage von %s zu „%s“ – nicht geantwortet.\n%s\nNachricht: %s" % (partner, a["titel"][:50], "; ".join(warn), neu[:300]))
    if not a.get("auto", True) or a.get("pausiert"):
        g.update(stand="wartet auf dich", hinweis="Automatik für diese Anzeige ist aus.")
        return melden("💬 Preisjäger: Anfrage von %s zu „%s“ (Automatik aus):\n%s" % (partner, a["titel"][:50], neu[:400]))
    heute = time.strftime("%d.%m.%Y")
    if d["tag"].get("datum") != heute:
        d["tag"] = {"datum": heute, "antworten": 0}
    if d["tag"]["antworten"] >= TAGESGRENZE:
        g.update(stand="wartet auf dich", hinweis="Tagesgrenze von %d automatischen Antworten erreicht." % TAGESGRENZE)
        return melden("💬 Preisjäger: Tagesgrenze erreicht – Anfrage von %s zu „%s“ bitte selbst beantworten:\n%s" % (partner, a["titel"][:50], neu[:400]))
    if g["antworten"] >= HOECHSTENS:
        g.update(stand="wartet auf dich", hinweis="Schon %d automatische Antworten – ab hier du." % HOECHSTENS)
        return melden("💬 Preisjäger: %s schreibt weiter zu „%s“ – bitte selbst antworten:\n%s" % (partner, a["titel"][:50], neu[:400]))
    r = sprache.verkaufsantwort(a, g["verlauf"][-8:], neu, NAME)
    lage = r.get("lage", "unklar")
    if lage == "betrugsverdacht":
        g.update(stand="betrug", hinweis=r.get("warnung", "wirkt wie eine bekannte Masche"))
        return melden("⚠ Preisjäger: BETRUGSVERDACHT bei Anfrage von %s zu „%s“ – nicht geantwortet.\n%s" % (partner, a["titel"][:50], neu[:300]))
    antwort = _antwort_sicher(r.get("antwort") or "", a)
    if not antwort or not verhandler._antworten(b, {}, antwort):
        g.update(stand="wartet auf dich", hinweis="Antwort konnte nicht gesendet werden.")
        return melden("💬 Preisjäger: Anfrage von %s zu „%s“ – Antwort konnte nicht gesendet werden:\n%s" % (partner, a["titel"][:50], neu[:400]))
    g["verlauf"].append({"von": "ich", "text": antwort, "zeit": _jetzt()})
    g["antworten"] += 1
    d["tag"]["antworten"] += 1
    if lage in ("einig", "termin"):
        g.update(stand="einig – ab hier du", hinweis="Preis: " + (_eur(r["gebot"]) if r.get("gebot") else _eur(a["preis"])))
        return melden("✅ Preisjäger: %s will „%s“ für %s nehmen. Ich habe zugesagt und geschrieben, dass du dich wegen Termin und Übergabe meldest.\nLetzte Nachricht: %s" % (
            partner, a["titel"][:50], _eur(r["gebot"]) if r.get("gebot") else _eur(a["preis"]), neu[:300]))
    if lage == "unklar":
        g.update(stand="wartet auf dich", hinweis="Frage lässt sich aus der Anzeige nicht beantworten.")
        return melden("❓ Preisjäger: %s fragt zu „%s“ etwas, das nicht in der Anzeige steht:\n%s\nIch habe geantwortet, dass du dich meldest. Antworte in der App unter „Verkaufen“." % (partner, a["titel"][:50], neu[:400]))
    g.update(stand="läuft", hinweis="")
    if erstkontakt:
        melden("💬 Preisjäger: Neue Anfrage von %s zu „%s“:\n%s\nGeantwortet: %s" % (partner, a["titel"][:50], neu[:250], antwort[:250]))


def _nach_einschalten(datum, seit):
    """Ist die letzte Nachricht des Gesprächs (laut Postfach-Liste „Heute HH:MM“) nach dem Einschalten der Automatik gekommen?"""
    m = re.match(r"Heute\s+(\d{1,2}):(\d\d)", datum or "")
    if not m or not seit:
        return False
    jetzt = time.localtime()
    t = time.mktime((jetzt.tm_year, jetzt.tm_mon, jetzt.tm_mday, int(m.group(1)), int(m.group(2)), 59, 0, 0, -1))
    return t >= seit


def lauf(b, probe=False):
    """Ein Durchgang. Angefasst werden nur Gespräche, deren letzte Nachricht HEUTE und NACH dem Einschalten der Automatik gekommen ist –
    und darin nur Nachrichten, die nach der letzten eigenen Antwort stehen. Alles Ältere bleibt unberührt.
    probe=True: nichts anklicken und nichts senden, nur melden, was in Frage käme."""
    with _sperre:
        d = _lesen()
    if not d["aktiv"] and not probe:
        return
    if not probe and (time.time() - d["anzeigen_zeit"] > 3600 or not d["anzeigen"]):
        anzeigen_holen(b, d)
    b.geh("https://www.kleinanzeigen.de/m-nachrichten.html", 6)
    liste = b.js(JS_LISTE) or []
    erledigt = set(d["liste"] or [])
    kaufen = {x["adid"] for x in verhandler._lesen() if x["stand"] not in ("gestoppt", "weg", "fehler")}
    warten = [g for g in d["gespraeche"].values() if g.get("zu_senden")]
    seit = d["aktiv_seit"] if not probe else (d["aktiv_seit"] or time.time())
    neu = [i for i, z in enumerate(liste) if z["sig"] not in erledigt and _nach_einschalten(z["datum"], seit)]
    if probe:
        return {"eintraege": len(liste), "kaemen_in_frage": [(liste[i]["name"], liste[i]["datum"]) for i in neu], "aktiv_seit": time.strftime("%d.%m. %H:%M", time.localtime(seit))}
    for i in neu[:6]:
        if not b.js(JS_KLICK, i):
            continue
        time.sleep(3)
        v = b.js(verhandler.JS_VERLAUF)
        if not v or not v["nachrichten"]:
            continue
        adid, partner = verhandler._adid(v.get("anzeige")), (liste[i]["name"] or v.get("partner") or "Interessent")[:60]
        if adid in kaufen:
            continue      # eigene Kauf-Verhandlung: macht der Verhandler
        if v["nachrichten"][-1]["von"] != "verk":
            continue      # die letzte Nachricht ist von mir/Tekin: nichts offen
        a = d["anzeigen"].get(adid)
        if a:
            try:
                _behandeln(b, d, a, v, partner)
            except Exception as x:
                print("Anfragen:", x, flush=True)
        else:      # weder eigene Anzeige noch Kauf-Verhandlung: nur weitermelden
            melden("💬 Kleinanzeigen: Neue Nachricht von %s zu „%s“:\n%s" % (partner, (v.get("titel") or "")[:50], v["nachrichten"][-1]["text"][:400]))
        time.sleep(4)
    for g in warten:      # Tekins eigene Antworten aus der App
        a = d["anzeigen"].get(g["adid"])
        v = verhandler._gespraech(b, {"verkaeufer": g["partner"], "adid": g["adid"], "titel": g["titel"], "id": ""})
        if a and v:
            _behandeln(b, d, a, v, g["partner"])
    b.geh("https://www.kleinanzeigen.de/m-nachrichten.html", 4)
    d["liste"] = [z["sig"] for z in (b.js(JS_LISTE) or liste)]
    with _sperre:
        frisch = _lesen()      # Einstellungen, die Tekin inzwischen geändert hat, behalten
        d["aktiv"], d["aktiv_seit"] = frisch["aktiv"], frisch["aktiv_seit"]
        for k, a in frisch["anzeigen"].items():
            if k in d["anzeigen"]:
                d["anzeigen"][k].update({x: a[x] for x in ("auto", "mindest", "mindest_gesetzt") if x in a})
        _schreiben(d)
