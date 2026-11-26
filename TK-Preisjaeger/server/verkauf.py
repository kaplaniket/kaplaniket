# TK Preisjäger – Verkaufen: Fotos → Artikel erkennen → Anzeigentext und Preisvorschlag → bei Kleinanzeigen einstellen. Claude 26.11.2026
# Fotos und Artikel liegen in daten/verkauf/. Erkennung und Text über den KI-Helfer (~/bin/ki.py, versteht Bilder);
# der Preisvorschlag kommt aus der eigenen Marktsuche (was verlangen andere gerade für denselben Artikel).
# Eingestellt wird über das eigene Chrome-Fenster: Formular „Anzeige aufgeben“ ausfüllen, Fotos anhängen, dann
# „Entwurf speichern“ (Tekin prüft und veröffentlicht) oder – nur auf seinen ausdrücklichen Klick – „Anzeige aufgeben“.
import base64
import json
import os
import re
import statistics
import threading
import time

import browser
import sprache

ORT = os.path.dirname(os.path.abspath(__file__))
ORDNER = os.path.join(ORT, "daten", "verkauf")
DATEI = os.path.join(ORDNER, "artikel.json")
_sperre = threading.Lock()
PORTALE = [("eBay", "https://www.ebay.de/sl/sell"), ("Vinted", "https://www.vinted.de/items/new"), ("Shpock", "https://www.shpock.com/de-de/sell"),
           ("Hood", "https://www.hood.de/verkaufen.htm")]

ERKENNEN = ('Du siehst Fotos eines Artikels, den eine Privatperson verkaufen will. Erkenne, was es ist, und schreibe eine ehrliche Anzeige für '
            'Kleinanzeigen. Beschreibe nur, was auf den Fotos zu sehen oder vom Verkäufer angegeben ist – erfinde keine Daten (kein Kaufdatum, '
            'keinen Akkuzustand, kein Zubehör, das nicht zu sehen ist). Sichtbare Mängel nennst du offen. Antworte NUR mit JSON: '
            '{"produkt": Marke und Modell so genau wie erkennbar, "sicher": true/false ob Marke und Modell sicher erkannt sind, '
            '"suchbegriff": kurzer Suchbegriff, mit dem man denselben Artikel auf Kleinanzeigen findet (Marke Modell Größe), '
            '"titel": Anzeigentitel, höchstens 65 Zeichen, ohne Ausrufezeichen und ohne Großschreib-Geschrei, '
            '"zustand": eines von "neu", "sehr gut", "gut", "in Ordnung", "defekt", '
            '"beschreibung": Anzeigentext mit 4 bis 9 Zeilen: ein einleitender Satz, dann Stichpunkte mit „- “ (Modell, Ausstattung, Zustand, '
            'Lieferumfang laut Fotos), am Ende die Zeile „Privatverkauf, keine Garantie, keine Rücknahme.“, '
            '"maengel": [sichtbare Mängel, sonst leer], "fragen": [bis 5 Angaben, die der Verkäufer ergänzen sollte, weil man sie auf Fotos '
            'nicht sieht, z. B. Kaufjahr, Akkuzustand, Rechnung vorhanden, Nichtraucherhaushalt]}. Deutsch.')


def _lesen():
    try:
        with open(DATEI, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def _schreiben(liste):
    os.makedirs(ORDNER, exist_ok=True)
    with open(DATEI + ".neu", "w", encoding="utf-8") as f:
        json.dump(liste[:200], f, ensure_ascii=False, indent=1)
    os.replace(DATEI + ".neu", DATEI)


def _eins(kennung):
    for a in _lesen():
        if a["id"] == kennung:
            return a
    raise ValueError("Artikel nicht gefunden")


def _merk(kennung, **neu):
    with _sperre:
        alle = _lesen()
        for a in alle:
            if a["id"] == kennung:
                a.update(neu, geaendert=time.strftime("%d.%m.%Y %H:%M"))
                _schreiben(alle)
                return a
    raise ValueError("Artikel nicht gefunden")


def liste():
    return _lesen()


def bildpfad(kennung, nr):
    if not re.fullmatch(r"\d{10,16}", kennung) or not str(nr).isdigit():
        return None
    p = os.path.join(ORDNER, kennung, "bild_%d.jpg" % int(nr))
    return p if os.path.exists(p) else None


def neu(d):
    """Legt einen Artikel aus hochgeladenen Fotos an (als data:image/jpeg;base64,… – die Oberfläche verkleinert sie vorher)."""
    bilder = [b for b in (d.get("bilder") or []) if isinstance(b, str) and b.startswith("data:image/")][:10]
    if not bilder:
        raise ValueError("Bitte mindestens ein Foto auswählen")
    kennung = "%d" % (time.time() * 1000)
    os.makedirs(os.path.join(ORDNER, kennung), exist_ok=True)
    n = 0
    for b in bilder:
        try:
            roh = base64.b64decode(b.split(",", 1)[1])
        except Exception:
            continue
        if not roh[:3] == b"\xff\xd8\xff" or len(roh) > 3_000_000:      # nur JPEG, höchstens 3 MB je Bild
            continue
        with open(os.path.join(ORDNER, kennung, "bild_%d.jpg" % n), "wb") as f:
            f.write(roh)
        n += 1
    if not n:
        raise ValueError("Die Fotos konnten nicht gelesen werden")
    a = {"id": kennung, "bilder": n, "hinweis": " ".join(str(d.get("hinweis", "")).split())[:400], "titel": "", "beschreibung": "", "preis": 0, "vb": True,
         "zustand": "", "produkt": "", "suchbegriff": "", "maengel": [], "fragen": [], "markt": None, "stand": "neu", "portale": {},
         "erstellt": time.strftime("%d.%m.%Y %H:%M"), "geaendert": time.strftime("%d.%m.%Y %H:%M")}
    with _sperre:
        alle = _lesen()
        alle.insert(0, a)
        _schreiben(alle)
    return a


def erkennen(kennung, suche):
    """Fotos ansehen lassen, Anzeige entwerfen, Marktpreis über die eigene Suche bestimmen. suche = Funktion der Preissuche."""
    a = _eins(kennung)
    pfade = [os.path.join(ORDNER, kennung, "bild_%d.jpg" % i) for i in range(min(a["bilder"], 5))]
    roh = sprache.ki(ERKENNEN, "Angaben des Verkäufers: %s" % (a.get("hinweis") or "keine"), 900, 0.2, 80, pfade)
    try:
        d = json.loads(re.search(r"\{.*\}", roh, re.S).group(0))
    except Exception:
        raise ValueError("die KI hat die Fotos nicht ausgewertet – bitte noch einmal versuchen")
    liste_ = lambda x: [" ".join(str(w).split())[:160] for w in (x if isinstance(x, list) else []) if str(w).strip()][:6]
    neu_ = {"produkt": str(d.get("produkt", ""))[:120], "sicher": bool(d.get("sicher")), "suchbegriff": " ".join(str(d.get("suchbegriff", "")).split())[:80],
            "titel": str(d.get("titel", ""))[:65], "zustand": str(d.get("zustand", ""))[:20], "beschreibung": str(d.get("beschreibung", ""))[:3000],
            "maengel": liste_(d.get("maengel")), "fragen": liste_(d.get("fragen")), "stand": "entwurf"}
    markt = None
    if neu_["suchbegriff"]:
        try:      # was verlangen andere gerade? nur Privatangebote in gebrauchtem Zustand zählen für den Preisvorschlag
            e = suche(neu_["suchbegriff"])
            privat = sorted(x["preis"] for x in e["treffer"] if x.get("art") == "privat" and x.get("zustand") == "gebraucht")
            neuware = sorted(x["preis"] for x in e["treffer"] if x.get("zustand") == "neu" and x.get("art") == "händler")
            if len(privat) >= 3:
                mitte = statistics.median(privat)
                faktor = {"neu": 1.15, "sehr gut": 1.05, "gut": 0.95, "in Ordnung": 0.8, "defekt": 0.35}.get(neu_["zustand"], 0.95)
                markt = {"angebote": len(privat), "guenstigstes": privat[0], "ueblich": round(mitte), "teuerstes": privat[-1],
                         "neu_ab": neuware[0] if neuware else None, "schnell": round(mitte * faktor * 0.88), "empfohlen": round(mitte * faktor),
                         "hoch": round(mitte * faktor * 1.1), "suche": neu_["suchbegriff"]}
            elif neuware:
                markt = {"angebote": len(privat), "neu_ab": neuware[0], "empfohlen": round(neuware[0] * 0.6), "schnell": round(neuware[0] * 0.5),
                         "hoch": round(neuware[0] * 0.7), "suche": neu_["suchbegriff"], "grob": True}
        except Exception:
            pass
    neu_["markt"] = markt
    if markt and not a.get("preis"):
        neu_["preis"] = markt["empfohlen"]
    return _merk(kennung, **neu_)


def speichern(kennung, d):
    felder = {}
    if "titel" in d:
        felder["titel"] = " ".join(str(d["titel"]).split())[:65]
    if "beschreibung" in d:
        felder["beschreibung"] = str(d["beschreibung"])[:4000]
    if "preis" in d:
        try:
            felder["preis"] = max(0, int(float(d["preis"])))
        except Exception:
            pass
    if "vb" in d:
        felder["vb"] = bool(d["vb"])
    return _merk(kennung, **felder)


def loeschen(kennung):
    """Nimmt den Artikel aus der Liste; die Fotos bleiben im Ordner liegen (nichts wird endgültig gelöscht)."""
    with _sperre:
        _schreiben([a for a in _lesen() if a["id"] != kennung])
    return _lesen()


JS_FUELLEN = """
const setze = (el, w) => { const p = el.tagName === 'TEXTAREA' ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
  Object.getOwnPropertyDescriptor(p, 'value').set.call(el, w); el.dispatchEvent(new Event('input', {bubbles: true}));
  el.dispatchEvent(new Event('change', {bubbles: true})); el.dispatchEvent(new Event('blur', {bubbles: true})); };
const warte = ms => new Promise(r => setTimeout(r, ms));
const t = document.querySelector('#ad-title'), b = document.querySelector('#ad-description'), p = document.querySelector('#ad-price-amount');
if (!t || !b || !p) return {fehler: 'Formular „Anzeige aufgeben“ nicht gefunden'};
const biete = document.querySelector('#ad-type-OFFER'); if (biete && !biete.checked) biete.click();
setze(t, arguments[0]);
await warte(5000);
const kat = document.querySelector('input[name="category-suggestions"]');      // erster Kategorie-Vorschlag von Kleinanzeigen
let kategorie = '';
if (kat) { if (!kat.checked) kat.click(); const l = document.querySelector('label[for="' + kat.id + '"]'); kategorie = l ? l.innerText.trim() : ''; }
setze(b, arguments[1]);
setze(p, String(arguments[2]));
if (arguments[3]) {      // Verhandlungsbasis
  const pt = document.querySelector('#ad-price-type');
  if (pt) { pt.click(); await warte(600);
    const o = [...document.querySelectorAll('[role=option], li, button')].find(x => /^(VB|Verhandlungsbasis)$/.test((x.innerText || '').trim()) && x.offsetParent);
    if (o) o.click(); else pt.click(); }
}
await warte(800);
return {kategorie, titel: t.value.length, text: b.value.length, preis: p.value, preistyp: (document.querySelector('#ad-price-type') || {}).innerText || ''};"""

JS_FOTOS = "return document.querySelectorAll('img[src^=\"blob:\"], img[src*=\"img.kleinanzeigen\"], [class*=\"thumbnail\"] img, [class*=\"Thumbnail\"] img').length;"

JS_KLICK = """
const k = [...document.querySelectorAll('button')].find(x => (x.innerText || '').trim() === arguments[0] && x.offsetParent);
if (!k) return {fehler: 'Knopf „' + arguments[0] + '“ nicht gefunden'};
k.click();
await new Promise(r => setTimeout(r, 6000));
const meld = [...document.querySelectorAll('[class*=error], [class*=Error], [role=alert], [aria-invalid=true]')].filter(x => x.offsetParent)
  .map(x => (x.innerText || x.getAttribute('aria-label') || x.id || '').replace(/\\s+/g, ' ').trim()).filter(Boolean).slice(0, 6);
return {url: location.href, meldungen: meld, text: document.body.innerText.replace(/\\s+/g, ' ').slice(0, 400)};"""


def einstellen(kennung, modus="entwurf"):
    """Kleinanzeigen: Formular ausfüllen, Fotos anhängen, dann Entwurf speichern (Vorgabe) oder veröffentlichen."""
    a = _eins(kennung)
    if len(a.get("titel", "")) < 5 or len(a.get("beschreibung", "")) < 10 or not a.get("preis"):
        raise ValueError("Titel, Beschreibung und Preis werden gebraucht")
    pfade = [os.path.join(ORDNER, kennung, "bild_%d.jpg" % i) for i in range(a["bilder"])]

    def arbeit(b):
        b.geh("https://www.kleinanzeigen.de/p-anzeige-aufgeben-schritt2.html", 5)
        if "login" in b.url() or "einloggen" in b.url():
            raise ValueError("Kleinanzeigen ist im Preisjäger-Chrome nicht angemeldet")
        f = b.js(JS_FUELLEN, a["titel"], a["beschreibung"], a["preis"], bool(a.get("vb")))
        if f.get("fehler"):
            raise ValueError(f["fehler"])
        b.dateien('input[type=file]', pfade)
        fotos = 0
        for _ in range(20):      # warten, bis die Fotos hochgeladen sind
            time.sleep(1.5)
            fotos = b.js(JS_FOTOS) or 0
            if fotos >= len(pfade):
                break
        time.sleep(2)
        r = b.js(JS_KLICK, "Entwurf speichern" if modus != "veroeffentlichen" else "Anzeige aufgeben")
        return f, fotos, r

    f, fotos, r = browser.mit_browser(arbeit)
    if r.get("fehler"):
        raise ValueError(r["fehler"])
    text = r.get("text", "")
    if modus == "veroeffentlichen":
        ok = "p-anzeige-aufgeben-bestaetigung" in r.get("url", "") or re.search(r"Anzeige (ist|wurde) (jetzt )?(online|aufgegeben|veröffentlicht)|wird geprüft", text, re.I)
        stand = "veröffentlicht" if ok else "nicht veröffentlicht – Kleinanzeigen verlangt noch Angaben"
    else:
        ok = not r.get("meldungen") or re.search(r"Entwurf (wurde )?gespeichert", text, re.I)
        stand = "als Entwurf gespeichert" if ok else "Entwurf nicht eindeutig gespeichert"
    portale = dict(a.get("portale") or {}, kleinanzeigen={"stand": stand, "zeit": time.strftime("%d.%m.%Y %H:%M"), "kategorie": f.get("kategorie", ""),
                                                             "fotos": fotos, "meldungen": r.get("meldungen", [])[:4]})
    return _merk(kennung, portale=portale, stand=stand if ok else a.get("stand", "entwurf"))
