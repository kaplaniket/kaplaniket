# TK Preisjäger – Anzeigenpflege: Tekins laufende Kleinanzeigen durchgehen, Titel/Text verbessern, Preis prüfen. Claude 26.11.2026
# Auftrag Tekin 26.11.2026: „Preise von meinen angebotenen Artikeln durchgehen, Texte und Überschriften nach Produkt verbessern, Preise
# anpassen, sodass es auch verkauft“. Die App macht je Anzeige einen Vorschlag (alt/neu nebeneinander). Bei Kleinanzeigen geändert wird
# erst, wenn Tekin den Vorschlag je Anzeige freigibst – es geht um seine Preise.
#
# Titel/Text: KI aus dem bisherigen Text und dem ersten Foto – erfindet nichts, fehlende Angaben stehen als Fragen dabei.
# Preis: wenn das Produkt sicher erkannt ist, aus der eigenen Marktsuche; sonst vorsichtig aus dem Interesse (Besucher, Merker, Laufzeit).
import datetime
import json
import os
import re
import threading
import time
import urllib.request

import browser
import quellen
import sprache
import verkauf

ORT = os.path.dirname(os.path.abspath(__file__))
DATEI = os.path.join(ORT, "daten", "pflege.json")
BILDER = os.path.join(ORT, "daten", "pflege-bilder")
_sperre = threading.Lock()
_lauf = {"laeuft": False, "schritt": "", "fertig": 0, "gesamt": 0}

VERBESSERN = ('Du überarbeitest die Kleinanzeige eines Privatverkäufers, damit sie gefunden wird und sich verkauft. Du bekommst Titel, Text, Preis '
              'und ein Foto. Regeln: Erfinde nichts – nimm nur, was im bisherigen Text steht oder auf dem Foto eindeutig zu sehen ist (Marke, Farbe, '
              'Art, Zustand). Titel: höchstens 65 Zeichen, die Suchwörter nach vorn (Marke, Produktart, Modell, Größe, Farbe, Zustand), keine '
              'Ausrufezeichen, kein Großbuchstaben-Geschrei, Rechtschreibung richtig. Beschreibung: ein Einleitungssatz, dann Stichpunkte mit „- “ '
              '(Marke/Modell, Größe/Maße, Farbe/Material, Zustand, Lieferumfang, Abholung/Versand soweit bekannt), am Ende „Privatverkauf, keine '
              'Garantie, keine Rücknahme.“. Antworte NUR mit JSON: {"produkt": was es ist (Marke Modell/Art), "sicher": true wenn Marke UND genaues '
              'Modell feststehen (bei Kleidung/Schuhen ohne Modellnamen false), "suchbegriff": Marke Modell für die Preissuche oder "", '
              '"zustand": "neu"/"sehr gut"/"gut"/"in Ordnung"/"defekt", "titel": neuer Titel, "beschreibung": neue Beschreibung, '
              '"schwaechen": [bis 4 konkrete Schwächen der bisherigen Anzeige, z. B. Tippfehler im Titel, Größe fehlt, zu wenig Text], '
              '"fragen": [bis 4 Angaben, die der Verkäufer ergänzen sollte, weil sie Käufer wissen wollen und nirgends stehen]}. Deutsch.')


def _lesen():
    try:
        with open(DATEI, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _schreiben(d):
    os.makedirs(os.path.dirname(DATEI), exist_ok=True)
    with open(DATEI + ".neu", "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=1)
    os.replace(DATEI + ".neu", DATEI)


def stand():
    d = _lesen()
    return dict(_lauf, vorschlaege=sorted(d.values(), key=lambda v: (v.get("stand") == "übernommen", v["alt"]["titel"].lower())))


def _eur(n):
    return ("%.2f" % n).replace(".", ",").replace(",00", "") + " €"


def _bild(a):
    """Erstes Foto der Anzeige für die KI holen (größer als das Vorschaubild)."""
    u = (a.get("bild") or "").replace("$_2.", "$_59.").replace("$_35.", "$_59.")
    if not u.startswith("https://img.kleinanzeigen.de/"):
        return None
    try:
        os.makedirs(BILDER, exist_ok=True)
        p = os.path.join(BILDER, a["adid"] + ".jpg")
        if not os.path.exists(p):
            roh = urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": quellen.UA}), timeout=15).read()
            if roh[:3] != b"\xff\xd8\xff":
                return None
            with open(p, "wb") as f:
                f.write(roh)
        return p
    except Exception:
        return None


def _preis(a, k, suche):
    """Preisempfehlung mit Begründung. Rückgabe (neuer Preis, Begründung, Marktdaten oder None)."""
    preis = a["preis"]
    tage = None
    m = re.match(r"(\d\d)\.(\d\d)\.(\d{4})", a.get("endet") or "")
    if m:      # Anzeigen laufen 60 Tage: aus dem Enddatum folgt, wie lange sie schon online ist
        ende = datetime.date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
        tage = max(0, 60 - (ende - datetime.date.today()).days)
    bes, gem = int(a.get("besucher") or 0), int(a.get("gemerkt") or 0)
    interesse = "%s Besucher, %s-mal gemerkt%s" % (bes, gem, (", seit rund %d Tagen online" % tage) if tage is not None else "")
    markt = verkauf.marktpreis(k["suchbegriff"], k.get("zustand", ""), suche) if k.get("sicher") and k.get("suchbegriff") else None
    if markt and not markt.get("grob"):
        ziel = markt["empfohlen"]
        if preis > ziel * 1.12:
            return ziel, "Andere verlangen für „%s“ gebraucht meist %s (Spanne %s–%s, %d Angebote). Dein Preis liegt deutlich darüber – %s." % (
                markt["suche"], _eur(markt["ueblich"]), _eur(markt["guenstigstes"]), _eur(markt["teuerstes"]), markt["angebote"], interesse), markt
        if preis < ziel * 0.8:
            return ziel, "Andere verlangen für „%s“ gebraucht meist %s (%d Angebote). Du bist deutlich billiger – da ist mehr drin. %s." % (
                markt["suche"], _eur(markt["ueblich"]), markt["angebote"], interesse), markt
        return preis, "Dein Preis passt zum Markt: Andere verlangen für „%s“ meist %s (%d Angebote). %s." % (markt["suche"], _eur(markt["ueblich"]), markt["angebote"], interesse), markt
    # kein belastbarer Marktvergleich (z. B. Kleidung ohne Modell): nur aus dem Interesse schließen
    hinweis = "Kein belastbarer Marktvergleich (kein eindeutiges Modell oder zu wenige vergleichbare Angebote) – Einschätzung nur aus dem Interesse: %s. " % interesse
    if tage is not None and tage >= 14 and gem == 0 and bes < 25 and preis >= 10:
        return max(5, int(round(preis * 0.8 / 5.0)) * 5 if preis >= 25 else int(round(preis * 0.8))), hinweis + "Wenig Aufrufe und niemand hat sie sich gemerkt: besserer Titel und rund 20 % weniger.", None
    if tage is not None and tage >= 21 and gem >= 2 and preis >= 10:
        return max(5, int(round(preis * 0.9))), hinweis + "Es gibt Interessenten, aber noch keinen Käufer: rund 10 % weniger kann den Ausschlag geben.", None
    return preis, hinweis + "Preis vorerst lassen; der neue Titel und Text sollen erst einmal mehr Aufrufe bringen.", None


def _eine(a, suche):
    bild = _bild(a)
    text = "Bisheriger Titel: %s\nBisheriger Text: %s\nPreis: %s%s\nAufrufe: %s Besucher, %s-mal gemerkt" % (
        a["titel"], (a.get("text") or "(kein Text lesbar)")[:2500], _eur(a["preis"]), " VB" if a.get("vb") else "", a.get("besucher") or "?", a.get("gemerkt") or "0")
    roh = sprache.ki(VERBESSERN, text, 900, 0.3, 60, [bild] if bild else None)
    try:
        k = json.loads(re.search(r"\{.*\}", roh, re.S).group(0))
    except Exception:
        return None
    liste = lambda x: [" ".join(str(w).split())[:160] for w in (x if isinstance(x, list) else []) if str(w).strip()][:4]
    k = {"produkt": str(k.get("produkt", ""))[:120], "sicher": bool(k.get("sicher")), "suchbegriff": " ".join(str(k.get("suchbegriff") or "").split())[:80],
         "zustand": str(k.get("zustand", ""))[:20], "titel": " ".join(str(k.get("titel", "")).split())[:65], "beschreibung": str(k.get("beschreibung", ""))[:3500],
         "schwaechen": liste(k.get("schwaechen")), "fragen": liste(k.get("fragen"))}
    if len(k["titel"]) < 5 or len(k["beschreibung"]) < 20:
        return None
    preis, grund, markt = _preis(a, k, suche)
    return {"adid": a["adid"], "url": a["url"], "bild": a.get("bild", ""), "stand": "vorschlag", "zeit": time.strftime("%d.%m.%Y %H:%M"),
            "alt": {"titel": a["titel"], "beschreibung": a.get("text") or "", "preis": a["preis"], "vb": bool(a.get("vb")), "besucher": a.get("besucher"), "gemerkt": a.get("gemerkt")},
            "neu": {"titel": k["titel"], "beschreibung": k["beschreibung"], "preis": preis},
            "produkt": k["produkt"], "sicher": k["sicher"], "preis_grund": grund, "markt": markt, "schwaechen": k["schwaechen"], "fragen": k["fragen"]}


def start(anzeigen, suche, nur_fehlende=False):
    """Alle laufenden Anzeigen im Hintergrund durchgehen (nur_fehlende: nur die, für die es noch keinen Vorschlag gibt)."""
    if _lauf["laeuft"]:
        return stand()
    da = _lesen()
    anzeigen = [a for a in anzeigen if a.get("titel") and not a.get("pausiert") and not (nur_fehlende and a["adid"] in da)]
    _lauf.update(laeuft=True, fertig=0, gesamt=len(anzeigen), schritt="Gehe %d Anzeigen durch …" % len(anzeigen))

    def lauf():
        try:
            for a in anzeigen:
                _lauf["schritt"] = "Prüfe „%s“ …" % a["titel"][:50]
                v = None
                for versuch in (1, 2):      # die KI antwortet nicht immer verwertbar: ein zweiter Versuch
                    try:
                        v = _eine(a, suche)
                    except Exception as e:
                        print("Pflege:", a.get("titel"), e, flush=True)
                    if v:
                        break
                if v:
                    with _sperre:
                        d = _lesen()
                        if d.get(a["adid"], {}).get("stand") != "übernommen" or d[a["adid"]]["neu"]["titel"] != a["titel"]:
                            d[a["adid"]] = v
                        _schreiben(d)
                _lauf["fertig"] += 1
        finally:
            _lauf.update(laeuft=False, schritt="")

    threading.Thread(target=lauf, daemon=True).start()
    return stand()


JS_AENDERN = """
const setze = (el, w) => { const p = el.tagName === 'TEXTAREA' ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
  Object.getOwnPropertyDescriptor(p, 'value').set.call(el, w); el.dispatchEvent(new Event('input', {bubbles: true}));
  el.dispatchEvent(new Event('change', {bubbles: true})); el.dispatchEvent(new Event('blur', {bubbles: true})); };
const t = document.querySelector('#ad-title'), b = document.querySelector('#ad-description'), p = document.querySelector('#ad-price-amount');
if (!t || !b || !p) return {fehler: 'Bearbeiten-Formular nicht gefunden'};
const vorher = {titel: t.value, text: b.value.length, preis: p.value};
setze(t, arguments[0]); setze(b, arguments[1]); setze(p, String(arguments[2]));
await new Promise(r => setTimeout(r, 1500));
const k = [...document.querySelectorAll('button')].find(x => /^Anzeige speichern$/.test((x.innerText || '').trim()) && x.offsetParent);
if (!k) return {fehler: 'Knopf „Anzeige speichern“ nicht gefunden'};
if (!arguments[3]) { setze(t, vorher.titel); return {probe: true, vorher, knopf: true}; }
k.click();
await new Promise(r => setTimeout(r, 7000));
const meld = [...document.querySelectorAll('[class*=error], [class*=Error], [role=alert], [aria-invalid=true]')].filter(x => x.offsetParent)
  .map(x => (x.innerText || x.id || '').replace(/\\s+/g, ' ').trim()).filter(Boolean).slice(0, 5);
return {vorher, url: location.href, meldungen: meld, text: document.body.innerText.replace(/\\s+/g, ' ').slice(0, 300)};"""


def uebernehmen(adid, felder, probe=False):
    """Vorschlag (ggf. von Tekin geändert) bei Kleinanzeigen eintragen und speichern."""
    d = _lesen()
    v = d.get(str(adid))
    if not v:
        raise ValueError("Vorschlag nicht gefunden")
    titel = " ".join(str(felder.get("titel") or v["neu"]["titel"]).split())[:65]
    text = str(felder.get("beschreibung") or v["neu"]["beschreibung"])[:4000]
    preis = int(float(felder.get("preis") or v["neu"]["preis"]))
    if len(titel) < 5 or len(text) < 10 or preis < 1:
        raise ValueError("Titel, Beschreibung und Preis werden gebraucht")

    def arbeit(b):
        b.geh("https://www.kleinanzeigen.de/p-anzeige-bearbeiten.html?adId=" + str(adid), 6)
        if "login" in b.url():
            raise ValueError("Kleinanzeigen ist im Preisjäger-Chrome nicht angemeldet")
        return b.js(JS_AENDERN, titel, text, preis, not probe)

    r = browser.mit_browser(arbeit)
    if r.get("fehler"):
        raise ValueError(r["fehler"])
    if probe:
        return r
    ok = "bearbeiten" not in r.get("url", "") or re.search(r"gespeichert|aktualisiert|wird geprüft|ist online", r.get("text", ""), re.I)
    if not ok:
        raise ValueError("Kleinanzeigen hat die Änderung nicht bestätigt" + ((": " + " · ".join(r.get("meldungen") or [])) if r.get("meldungen") else ""))
    with _sperre:
        d = _lesen()
        d[str(adid)].update(stand="übernommen", zeit=time.strftime("%d.%m.%Y %H:%M"), neu={"titel": titel, "beschreibung": text, "preis": preis})
        _schreiben(d)
    return stand()
