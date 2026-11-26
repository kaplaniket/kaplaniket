# TK Preisjäger – selbstständiges Verhandeln über Tekins eigenes Kleinanzeigen-Konto. Claude 26.11.2026
# Freigabe Tekin 26.11.2026 („ja bauen“): Die App darf für diese Verhandlungen selbst an Verkäufer schreiben, bis sein Preis erreicht ist;
# Abholung/Bezahlung macht er selbst. Bedient wird nur die sichtbare Seite im eigenen Chrome-Fenster (Formular ausfüllen, Knopf drücken,
# Verlauf lesen) – keine interne Schnittstelle, kein Zugriff auf Anmeldedaten.
#
# Leitplanken: nie über Tekins Preis gehen · bei Betrugszeichen sofort abbrechen · Rückfragen an Tekin weitergeben statt etwas zu erfinden ·
# höchstens 3 Gegenrunden · höchstens 8 neue Verhandlungen am Tag · nach „einig“ schreibt nur noch Tekin.
import json
import os
import re
import threading
import time

import browser
import kern
import sprache

ORT = os.path.dirname(os.path.abspath(__file__))
DATEI = os.path.join(ORT, "daten", "auftraege.json")
NAME = os.environ.get("PREISJAEGER_NAME", "")
NEU_JE_TAG, GEGENRUNDEN, TAKT = 8, 3, 240
_sperre = threading.Lock()
melden = lambda text: None      # setzt der Server (Telegram)

OFFEN = ("wartet", "gesendet", "verhandelt")
ENDE = {"einig": "✅ Einig – ab hier du (Abholung/Bezahlung)", "abgelehnt": "Abgelehnt", "betrug": "⚠ Betrugsverdacht – abgebrochen",
        "rueckfrage": "Rückfrage – wartet auf deine Antwort", "festgefahren": "Verkäufer bleibt über deinem Preis", "fehler": "Fehler",
        "gestoppt": "Von dir gestoppt", "weg": "Anzeige nicht mehr verfügbar"}

JS_ANZEIGE = """
const namen = [...document.querySelectorAll('#viewad-contact a[href*="s-bestandsliste"], a[href*="s-bestandsliste"]')].map(a => a.innerText.trim()).filter(Boolean);
const knopf = [...document.querySelectorAll('button')].find(x => /Nachricht schreiben/.test(x.innerText || '') && x.offsetParent);
return {titel: ((document.querySelector('#viewad-title') || {}).innerText || document.title || '').trim(),
        preis: ((document.querySelector('#viewad-price') || {}).innerText || '').trim(),
        text: ((document.querySelector('#viewad-description-text') || {}).innerText || '').trim().slice(0, 4000),
        verk: namen.sort((x, y) => y.length - x.length)[0] || '',
        form: !!document.querySelector('#viewad-contact-form textarea[name=message]') || !!knopf,
        url: location.href};"""

# Kleinanzeigen hat zwei Bauarten der Anzeigenseite: altes Formular auf der Seite oder ein Fenster hinter „Nachricht schreiben“.
JS_ERSTE = """
const setze = (t, w) => { Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, 'value').set.call(t, w);
                         t.dispatchEvent(new Event('input', {bubbles: true})); t.dispatchEvent(new Event('change', {bubbles: true})); };
const alt = document.querySelector('#viewad-contact-form');
if (alt && alt.querySelector('textarea[name=message]')) {
  const t = alt.querySelector('textarea[name=message]'); setze(t, arguments[0]);
  const k = alt.querySelector('button.viewad-contact-submit, button[type=submit]');
  if (!k) return {fehler: 'kein Senden-Knopf'};
  if (arguments[1]) k.click();
  return {gefuellt: t.value.length, bauart: 'formular'};
}
const auf = [...document.querySelectorAll('button')].find(x => /Nachricht schreiben/.test(x.innerText || '') && x.offsetParent);
if (!auf) return {fehler: 'kein Kontaktformular'};
auf.click();
await new Promise(r => setTimeout(r, 2500));
const d = [...document.querySelectorAll('[role=dialog],dialog,[aria-modal=true]')].find(x => x.offsetParent || x.open);
const t = d && d.querySelector('textarea');
const k = d && [...d.querySelectorAll('button')].find(x => /Nachricht senden/.test(x.innerText || ''));
if (!t || !k) return {fehler: 'Nachrichtenfenster nicht gefunden'};
setze(t, arguments[0]);
await new Promise(r => setTimeout(r, 600));
if (arguments[1]) { if (k.disabled) return {fehler: 'Senden-Knopf nicht bereit'}; k.click(); return {gefuellt: t.value.length, bauart: 'fenster'}; }
const zu = [...d.querySelectorAll('button')].find(x => !x.innerText.trim() || /schlie|abbrechen/i.test((x.getAttribute('aria-label') || '') + x.innerText));
const r = {gefuellt: t.value.length, bauart: 'fenster', knopf_bereit: !k.disabled};
setze(t, ''); if (zu) zu.click();
return r;"""

JS_NACH_SENDEN = """
const t = document.body.innerText;
const offen = [...document.querySelectorAll('[role=dialog],dialog,[aria-modal=true]')].find(x => (x.offsetParent || x.open) && x.querySelector('textarea'));
return {ok: /Nachricht (wurde )?(erfolgreich )?(gesendet|verschickt|versendet)|Deine Nachricht wurde|Zu meinen Nachrichten/i.test(t) && !offen,
        fehler: (t.match(/[^.\\n]*(konnte nicht gesendet|Fehler beim Senden|zu viele Nachrichten|Bitte bestätige|verifizier)[^.\\n]*/i) || [''])[0].slice(0, 160)};"""

JS_OEFFNE = """
const name = arguments[0].toLowerCase(), nr = arguments[1];
const arts = [...document.querySelectorAll('.ConversationByDateList article')].slice(0, 20)
  .filter(a => { const s = a.querySelector('span'); return s && s.innerText.trim().toLowerCase() === name; });
if (!arts[nr]) return false;
(arts[nr].querySelector('a,[role=button]') || arts[nr]).click();
return true;"""

JS_VERLAUF = """
const W = document.querySelector('[data-testid=conversation-wrapper]');
if (!W) return null;
const ls = [...W.querySelectorAll('a[href*="zur-anzeige"], a[href*="s-anzeige"]')];
const a = ls[0];
return {anzeige: a ? a.getAttribute('href') : '', titel: ls.map(x => x.innerText.trim()).sort((x, y) => y.length - x.length)[0] || '',
        nachrichten: [...W.querySelectorAll('[data-testid=INBOUND],[data-testid=OUTBOUND]')]
          .map(x => ({von: x.dataset.testid === 'INBOUND' ? 'verk' : 'ich', text: x.innerText.trim()})).filter(m => m.text)};"""

JS_ANTWORT = """
const t = document.querySelector('textarea#nachricht');
if (!t) return {fehler: 'kein Antwortfeld'};
Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, 'value').set.call(t, arguments[0]);
t.dispatchEvent(new Event('input', {bubbles: true})); t.dispatchEvent(new Event('change', {bubbles: true}));
const k = document.querySelector('[data-testid=submit-button]');
if (!k || k.disabled) return {fehler: 'Senden-Knopf nicht bereit'};
if (arguments[1]) k.click();
return {gefuellt: t.value.length};"""


def _lesen():
    try:
        with open(DATEI, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def _schreiben(liste):
    os.makedirs(os.path.dirname(DATEI), exist_ok=True)
    with open(DATEI + ".neu", "w", encoding="utf-8") as f:
        json.dump(liste[:300], f, ensure_ascii=False, indent=1)
    os.replace(DATEI + ".neu", DATEI)


def _jetzt():
    return time.strftime("%d.%m.%Y %H:%M")


def _adid(url):
    m = re.search(r"/(\d{8,12})-\d+-\d+", url or "") or re.search(r"(\d{8,12})", url or "")
    return m.group(1) if m else ""


def _eur(n):
    return ("%.2f" % n).replace(".", ",").replace(",00", "") + " €"


def konto():
    """Läuft das eigene Chrome-Fenster, und ist dort ein Kleinanzeigen-Konto angemeldet?"""
    def pruefe(b):
        b.geh("https://www.kleinanzeigen.de/m-nachrichten.html", 3)
        return b.js("return {url: location.href, liste: !!document.querySelector('[data-testid=conversation-list]')}")
    try:
        r = browser.mit_browser(pruefe)
        ok = "login." not in r["url"] and "einloggen" not in r["url"] and r["liste"]
        return {"browser": True, "angemeldet": ok, "bereit": ok,
                "hinweis": "Konto ist angemeldet – selbstständiges Verhandeln ist möglich." if ok else
                           "Noch nicht angemeldet: am HP im Chrome-Fenster des Preisjägers („Kleinanzeigen – Anmelden“) mit deinem Konto einloggen."}
    except Exception as e:
        return {"browser": False, "angemeldet": False, "bereit": False, "hinweis": "Das eigene Chrome-Fenster auf dem HP ist nicht erreichbar (%s)." % str(e)[:80]}


def liste():
    with _sperre:
        return [dict(a, standtext=ENDE.get(a["stand"], {"wartet": "Wird gleich gesendet", "gesendet": "Gesendet – warte auf Antwort",
                                                          "verhandelt": "Verhandlung läuft"}.get(a["stand"], a["stand"]))) for a in _lesen()]


def starten(d):
    """Neue selbstständige Verhandlung anlegen. Gesendet wird die Nachricht, die Tekin im Fenster gesehen (und ggf. geändert) hat."""
    url, text = str(d.get("url", "")), " ".join(str(d.get("text", "")).split())
    preis, mein = float(d.get("preis") or 0), float(d.get("mein") or 0)
    if "kleinanzeigen.de/s-anzeige/" not in url:
        raise ValueError("Selbstständig verhandeln geht nur bei Kleinanzeigen-Angeboten")
    if not (mein > 0 and preis > 0 and len(text) >= 20):
        raise ValueError("Dein Preis und die Nachricht werden gebraucht")
    if _eur(mein).split(" ")[0].split(",")[0] not in text:
        raise ValueError("In der Nachricht steht dein Preis (%s) nicht" % _eur(mein))
    with _sperre:
        alle = _lesen()
        if any(a["adid"] == _adid(url) and a["stand"] in OFFEN + ("einig", "rueckfrage") for a in alle):
            raise ValueError("Für diese Anzeige läuft schon eine Verhandlung")
        heute = time.strftime("%d.%m.%Y")
        if sum(1 for a in alle if a.get("erstellt", "").startswith(heute)) >= NEU_JE_TAG:
            raise ValueError("Heute wurden schon %d Verhandlungen begonnen – das ist die Tagesgrenze" % NEU_JE_TAG)
        a = {"id": "%d" % (time.time() * 1000), "url": url, "adid": _adid(url), "titel": str(d.get("titel", ""))[:160], "preis": preis, "mein": mein,
             "weg": "versand" if d.get("weg") == "versand" else "abholung", "erste": text[:1200], "verkaeufer": "", "stand": "wartet", "runden": 0,
             "gesehen": 0, "verlauf": [], "erstellt": _jetzt(), "geaendert": _jetzt(), "hinweis": ""}
        alle.insert(0, a)
        _schreiben(alle)
    threading.Thread(target=lauf, daemon=True).start()
    return a


def stoppen(kennung):
    with _sperre:
        alle = _lesen()
        for a in alle:
            if a["id"] == kennung and a["stand"] in OFFEN + ("rueckfrage",):
                a.update(stand="gestoppt", geaendert=_jetzt())
        _schreiben(alle)
    return liste()


def eigene_antwort(kennung, text):
    """Tekin beantwortet eine Rückfrage selbst; die App sendet seinen Text und verhandelt weiter."""
    text = " ".join(str(text).split())[:1200]
    if len(text) < 2:
        raise ValueError("Bitte einen Text eingeben")
    with _sperre:
        alle = _lesen()
        for a in alle:
            if a["id"] == kennung and a["stand"] in ("rueckfrage", "einig", "verhandelt", "gesendet"):
                a["zu_senden"] = text
                if a["stand"] == "rueckfrage":
                    a["stand"] = "verhandelt"
        _schreiben(alle)
    threading.Thread(target=lauf, daemon=True).start()
    return liste()


def _merk(a, **neu):
    """Änderungen an einem Auftrag festhalten."""
    with _sperre:
        alle = _lesen()
        for x in alle:
            if x["id"] == a["id"]:
                x.update(neu, geaendert=_jetzt())
                a.update(x)
        _schreiben(alle)


def _erste_senden(b, a):
    b.geh(a["url"], 4)
    s = b.js(JS_ANZEIGE)
    if not s or not s.get("form"):
        return _merk(a, stand="weg", hinweis="Kein Kontaktformular auf der Anzeige (gelöscht, reserviert oder gewerblich ohne Nachrichtenfunktion).")
    warn = kern.betrug(s.get("text", "") + " " + s.get("titel", ""))
    if warn:
        _merk(a, stand="betrug", hinweis="Warnzeichen in der Anzeige: " + " · ".join(warn), verkaeufer=s.get("verk", ""))
        return melden("⚠ Preisjäger: Verhandlung zu „%s“ NICHT begonnen – Warnzeichen in der Anzeige: %s\n%s" % (a["titel"][:60], "; ".join(warn), a["url"]))
    r = b.js(JS_ERSTE, a["erste"], True)
    if r.get("fehler"):
        return _merk(a, stand="fehler", hinweis=r["fehler"])
    time.sleep(5)
    n = b.js(JS_NACH_SENDEN) or {}
    if n.get("fehler") and not n.get("ok"):
        return _merk(a, stand="fehler", hinweis="Kleinanzeigen meldet: " + n["fehler"])
    _merk(a, stand="gesendet", verkaeufer=s.get("verk", ""), verlauf=[{"von": "ich", "text": a["erste"], "zeit": _jetzt()}],
          hinweis="" if n.get("ok") else "Senden nicht eindeutig bestätigt – wird beim nächsten Lesen des Postfachs geprüft.")


def _gespraech(b, a):
    """Öffnet im Postfach das Gespräch zu dieser Anzeige (nur Gespräche mit genau diesem Verkäufernamen werden angeklickt)."""
    if not a.get("verkaeufer"):
        return None
    b.geh("https://www.kleinanzeigen.de/m-nachrichten.html", 4)
    for nr in range(4):
        if not b.js(JS_OEFFNE, a["verkaeufer"], nr):
            return None
        time.sleep(3)
        v = b.js(JS_VERLAUF)
        if v and (a["adid"] and a["adid"] in (v.get("anzeige") or "") or v.get("titel", "")[:14].lower() == a["titel"][:14].lower()):
            return v
    return None


def _sicher(text, a):
    """Nie mehr als Tekins Preis zusagen: steht in der Antwort ein höherer Euro-Betrag, wird der Baustein genommen."""
    for z in re.findall(r"(\d{1,3}(?:\.\d{3})+|\d+)(?:,\d+)?\s*(?:€|euro)", text.lower()):
        if float(z.replace(".", "")) > a["mein"] + 0.5:
            return "Danke für deine Antwort. Mein Angebot von %s steht. %s Viele Grüße%s" % (
                _eur(a["mein"]), sprache.VERSAND_SATZ if a["weg"] == "versand" else "Ich kann zeitnah abholen und bar bezahlen.", (", " + NAME) if NAME else "")
    return text


def _antworten(b, a, text):
    vor = len(b.js(JS_VERLAUF)["nachrichten"])
    r = b.js(JS_ANTWORT, text, True)
    if r.get("fehler"):
        return False
    time.sleep(4)
    return len(b.js(JS_VERLAUF)["nachrichten"]) > vor


def _weiter(b, a):
    v = _gespraech(b, a)
    if not v:
        return
    n = v["nachrichten"]
    if a.get("zu_senden"):      # Tekins eigene Antwort
        text = a["zu_senden"]
        if _antworten(b, a, text):
            _merk(a, zu_senden="", verlauf=a["verlauf"] + [{"von": "ich", "text": text, "zeit": _jetzt()}], gesehen=sum(1 for m in n if m["von"] == "verk"))
        return
    vom_verk = [m["text"] for m in n if m["von"] == "verk"]
    if len(vom_verk) <= a.get("gesehen", 0):
        if a["stand"] == "gesendet" and a.get("hinweis") and any(m["von"] == "ich" for m in n):
            _merk(a, hinweis="")      # Erstnachricht steht im Postfach: Senden bestätigt
        return
    neu = " ".join(vom_verk[a.get("gesehen", 0):])[:1500]
    verlauf = a["verlauf"] + [{"von": "verk", "text": neu, "zeit": _jetzt()}]
    if a["stand"] == "einig":      # nach der Einigung schreibt nur noch Tekin
        _merk(a, verlauf=verlauf, gesehen=len(vom_verk))
        return melden("💬 Preisjäger: Neue Nachricht von %s zu „%s“ (ihr seid euch bei %s einig):\n%s\n%s" % (a["verkaeufer"], a["titel"][:50], _eur(a["mein"]), neu[:400], a["url"]))
    g = sprache.gegenantwort(a["titel"], a["preis"], a["mein"], neu, NAME, a["weg"])
    lage = g.get("lage", "unklar")
    if lage == "betrugsverdacht":
        _merk(a, stand="betrug", verlauf=verlauf, gesehen=len(vom_verk), hinweis=" · ".join(g.get("warn") or []))
        return melden("⚠ Preisjäger: BETRUGSVERDACHT bei „%s“ (%s) – abgebrochen, nichts bezahlen, nichts anklicken.\n%s\nVerkäufer schrieb: %s" % (
            a["titel"][:50], a["verkaeufer"], "; ".join(g.get("warn") or []), neu[:300]))
    if lage in ("rueckfrage", "unklar"):
        _merk(a, stand="rueckfrage", verlauf=verlauf, gesehen=len(vom_verk), hinweis="Vorschlag: " + (g.get("antwort") or ""))
        return melden("❓ Preisjäger: %s fragt zu „%s“ etwas, das nur du beantworten kannst:\n%s\nAntworte in der App unter „Meine Verhandlungen“." % (a["verkaeufer"], a["titel"][:50], neu[:400]))
    if lage == "gegenangebot" and a["runden"] >= GEGENRUNDEN:
        _merk(a, stand="festgefahren", verlauf=verlauf, gesehen=len(vom_verk), hinweis="Letztes Angebot des Verkäufers: " + (_eur(g["preis_verkaeufer"]) if g.get("preis_verkaeufer") else "nicht genannt"))
        return melden("↔ Preisjäger: %s bleibt bei „%s“ über deinem Preis (%s)%s. Verhandlung angehalten – du entscheidest.\n%s" % (
            a["verkaeufer"], a["titel"][:50], _eur(a["mein"]), (", zuletzt " + _eur(g["preis_verkaeufer"])) if g.get("preis_verkaeufer") else "", a["url"]))
    antwort = _sicher(g.get("antwort") or "", a)
    if not antwort or not _antworten(b, a, antwort):
        return _merk(a, verlauf=verlauf, hinweis="Antwort konnte nicht gesendet werden – nächster Versuch beim nächsten Lauf.")
    verlauf.append({"von": "ich", "text": antwort, "zeit": _jetzt()})
    if lage == "einig":
        _merk(a, stand="einig", verlauf=verlauf, gesehen=len(vom_verk), hinweis="")
        return melden("✅ Preisjäger: EINIG bei %s für „%s“ mit %s. Ich habe nach %s gefragt – ab hier übernimmst du.\n%s" % (
            _eur(a["mein"]), a["titel"][:50], a["verkaeufer"], "Versand und PayPal-Daten" if a["weg"] == "versand" else "dem Abholtermin", a["url"]))
    if lage == "abgelehnt":
        _merk(a, stand="abgelehnt", verlauf=verlauf, gesehen=len(vom_verk))
        return melden("✖ Preisjäger: %s hat dein Angebot von %s für „%s“ abgelehnt." % (a["verkaeufer"], _eur(a["mein"]), a["titel"][:50]))
    _merk(a, stand="verhandelt", verlauf=verlauf, gesehen=len(vom_verk), runden=a["runden"] + 1, hinweis="")


_laeuft = threading.Lock()


def lauf():
    """Ein Durchgang über alle offenen Verhandlungen (immer nur einer gleichzeitig)."""
    if not _laeuft.acquire(blocking=False):
        return
    try:
        offen = [a for a in _lesen() if a["stand"] in OFFEN or a["stand"] == "einig" or a.get("zu_senden")]
        if not offen:
            return

        def arbeit(b):
            for a in offen[:12]:
                try:
                    if a["stand"] == "wartet":
                        _erste_senden(b, a)
                    else:
                        _weiter(b, a)
                except Exception as e:
                    _merk(a, hinweis="Fehler beim letzten Lauf: %s" % str(e)[:120])
                time.sleep(6)

        browser.mit_browser(arbeit)
    except Exception as e:
        print("Verhandler:", e, flush=True)
    finally:
        _laeuft.release()


def waechter():
    time.sleep(90)
    while True:
        lauf()
        time.sleep(TAKT)
