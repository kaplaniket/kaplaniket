# TK Preisjäger – Sprache: freien Text verstehen und Verhandlungsnachrichten schreiben. Claude 26.11.2026
# Nutzt, wenn vorhanden, den KI-Helfer ~/bin/ki.py (frage(system, text) -> str). Fehlt er oder antwortet er nicht
# rechtzeitig, greifen feste Regeln (kern.verstehen) bzw. Textbausteine – die App läuft also auch ohne KI.
import json
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor

import kern

_topf = ThreadPoolExecutor(max_workers=4)
_frage = None
try:
    sys.path.insert(0, os.path.expanduser("~/bin"))
    from ki import frage as _frage      # noqa: E402
except Exception:
    _frage = None

VERSTEHEN = ('Du zerlegst einen Kaufwunsch für eine Preissuche. Antworte NUR mit JSON: {"produkt": kurzer Suchbegriff, wie man ihn bei '
             'Kleinanzeigen eintippt (Marke, Modell, Gattung, Größe; keine Füllwörter, keine Ausstattung; Produktnamen unverändert lassen), '
             '"wuensche": [Ausstattungsmerkmale, je ein einzelnes Stichwort in Grundform], "ohne": [was nicht gewünscht ist, Stichwörter], '
             '"max": Preis in Euro, den der Käufer höchstens zahlen will, als Zahl oder null, "min": Mindestpreis oder null, '
             '"zustand": [] oder Auswahl aus "neu","gebraucht","aufbereitet"}')


def ki(system, text, max_tokens=300, temperatur=0.2, warten=9):
    if not _frage:
        return None
    try:
        return _topf.submit(_frage, system, text, max_tokens, temperatur, "preisjaeger").result(timeout=warten)
    except Exception:
        return None


def verstehen(text):
    """Kurze Produktnamen: feste Regeln. Längere/freie Texte: KI, mit Regeln als Rückfall. Ergebnis wie kern.verstehen, plus 'weg'."""
    regel = kern.verstehen(text)
    regel["weg"] = "regeln"
    frei = len(text.split()) >= 5 or regel["produkt"].lower() != " ".join(text.split()).lower()
    if not frei:
        return regel
    roh = ki(VERSTEHEN, text[:400], 220, 0)
    try:
        d = json.loads(re.search(r"\{.*\}", roh, re.S).group(0))
        produkt = " ".join(str(d.get("produkt") or "").split())[:80]
        if len(produkt) < 2:
            return regel
        liste = lambda x: [str(w).lower().strip()[:30] for w in (x if isinstance(x, list) else []) if str(w).strip()][:6]
        zahl = lambda x: float(x) if isinstance(x, (int, float)) and x > 0 else None
        return {"produkt": produkt, "wuensche": liste(d.get("wuensche")), "ohne": liste(d.get("ohne")), "max": zahl(d.get("max")),
                "min": zahl(d.get("min")), "zustand": [z for z in liste(d.get("zustand")) if z in ("neu", "gebraucht", "aufbereitet")], "weg": "ki"}
    except Exception:
        return regel


def _eur(n):
    return ("%.2f" % n).replace(".", ",").replace(",00", "") + " €"


def nachricht(titel, preis, mein, quelle="Kleinanzeigen", name=""):
    """Erste Nachricht an den Verkäufer mit dem eigenen Preis. Erfindet nichts (keine Mängel, keine anderen Angebote)."""
    gruss = "Viele Grüße" + (", " + name if name else "")
    if mein >= preis:
        return "Hallo, ist der Artikel „%s“ noch zu haben? Ich würde ihn für %s nehmen und kann zeitnah abholen oder direkt bezahlen. %s" % (titel[:70], _eur(preis), gruss)
    t = ki("Du schreibst für einen privaten Käufer eine kurze erste Nachricht an einen privaten Verkäufer auf %s. Ziel: den Artikel für den "
           "genannten Wunschpreis bekommen. Freundlich, direkt, höchstens 55 Wörter, per Du, ein Absatz. Nenne den Wunschpreis genau einmal "
           "als Zahl in Euro. Biete zeitnahe Abholung oder sofortige Bezahlung an. Erfinde nichts: keine Mängel, keine anderen Angebote, "
           "keine Geschichten. Kein Betreff, keine Anführungszeichen. Schluss: „%s“." % (quelle, gruss),
           "Artikel: %s\nPreis des Verkäufers: %s\nMein Wunschpreis: %s" % (titel[:120], _eur(preis), _eur(mein)), 200, 0.5)
    if t and _eur(mein).split(" ")[0].split(",")[0] in t:
        return " ".join(t.split()).strip('"„“')
    return ("Hallo, ich habe Interesse an „%s“. Wäre %s für dich in Ordnung? Ich kann zeitnah abholen oder sofort bezahlen. %s"
            % (titel[:70], _eur(mein), gruss))


def gegenantwort(titel, preis, mein, antwort, name=""):
    """Vorschlag für die Antwort auf die Rückmeldung des Verkäufers. Bleibt beim eigenen Preis; den Abschluss macht der Käufer selbst."""
    gruss = "Viele Grüße" + (", " + name if name else "")
    t = ki("Du hilfst einem privaten Käufer beim Verhandeln auf einem Kleinanzeigenmarkt. Er will höchstens seinen Wunschpreis zahlen. "
           "Lies die Antwort des Verkäufers und antworte NUR mit JSON: {\"lage\": eines von \"einig\" (Verkäufer nimmt den Wunschpreis oder "
           "weniger an), \"gegenangebot\" (Verkäufer nennt einen höheren Preis), \"abgelehnt\", \"rueckfrage\", \"unklar\", "
           "\"preis_verkaeufer\": genannter Preis als Zahl oder null, \"antwort\": kurze freundliche Antwort per Du, höchstens 50 Wörter. "
           "Bei \"einig\": bedanken und nach Abholung/Bezahlung und Termin fragen, nichts fest zusagen außer dem Preis. Bei \"gegenangebot\": "
           "höflich beim Wunschpreis bleiben und einmal begründen (zeitnahe Abholung, sofortige Bezahlung). Bei \"abgelehnt\": freundlich "
           "bedanken und anbieten, dass das Angebot bestehen bleibt. Erfinde nichts. Schluss: „%s“.}" % gruss,
           "Artikel: %s\nPreis des Verkäufers laut Anzeige: %s\nMein Wunschpreis: %s\nAntwort des Verkäufers: %s" % (titel[:120], _eur(preis), _eur(mein), antwort[:800]),
           300, 0.4, 12)
    try:
        d = json.loads(re.search(r"\{.*\}", t, re.S).group(0))
        return {"lage": str(d.get("lage") or "unklar"), "preis_verkaeufer": d.get("preis_verkaeufer") if isinstance(d.get("preis_verkaeufer"), (int, float)) else None,
                "antwort": " ".join(str(d.get("antwort") or "").split())}
    except Exception:
        return {"lage": "unklar", "preis_verkaeufer": None,
                "antwort": "Danke für deine Antwort. Mein Angebot von %s steht – ich könnte zeitnah abholen oder sofort bezahlen. %s" % (_eur(mein), gruss)}
