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
             '"zustand": [] oder Auswahl aus "neu","gebraucht","aufbereitet", "plz": fünfstellige Postleitzahl, falls der Käufer abholen will und eine nennt, '
             'sonst null, "umkreis": Umkreis in km als Zahl, falls genannt, sonst null}')


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
                "min": zahl(d.get("min")), "zustand": [z for z in liste(d.get("zustand")) if z in ("neu", "gebraucht", "aufbereitet")], "weg": "ki",
                "plz": str(d.get("plz"))[:5] if re.fullmatch(r"\d{5}", str(d.get("plz") or "")) else None, "umkreis": zahl(d.get("umkreis"))}
    except Exception:
        return regel


def _eur(n):
    return ("%.2f" % n).replace(".", ",").replace(",00", "") + " €"


VERSAND_SATZ = ("Abholen kann ich wegen der Entfernung nicht – würdest du versenden? Ich zahle per PayPal „Waren und Dienstleistungen“ "
                "(mit Käuferschutz) und übernehme die PayPal-Gebühr zusätzlich.")


def nachricht(titel, preis, mein, quelle="Kleinanzeigen", name="", weg="abholung"):
    """Erste Nachricht an den Verkäufer mit dem eigenen Preis. Erfindet nichts (keine Mängel, keine anderen Angebote).
    weg='versand': kein Abholen, sondern Versand mit PayPal-Käuferschutz, die Gebühr trägt der Käufer – nie „Freunde und Familie“."""
    gruss = "Viele Grüße" + (", " + name if name else "")
    abwicklung = VERSAND_SATZ if weg == "versand" else "Ich kann zeitnah abholen und bar bezahlen."
    if mein >= preis:
        return "Hallo, ist der Artikel „%s“ noch zu haben? Ich würde ihn für %s nehmen. %s %s" % (titel[:70], _eur(preis), abwicklung, gruss)
    regel = ("Der Käufer kann NICHT abholen: Bitte um Versand; Zahlung per PayPal „Waren und Dienstleistungen“ mit Käuferschutz, die PayPal-Gebühr "
             "übernimmt der Käufer zusätzlich zum Preis. Nie „Freunde und Familie“ anbieten." if weg == "versand"
             else "Biete zeitnahe Abholung mit Barzahlung an.")
    t = ki("Du schreibst für einen privaten Käufer eine kurze erste Nachricht an einen privaten Verkäufer auf %s. Ziel: den Artikel für den "
           "genannten Wunschpreis bekommen. Freundlich, direkt, höchstens 65 Wörter, per Du, ein Absatz. Nenne den Wunschpreis genau einmal "
           "als Zahl in Euro. %s Erfinde nichts: keine Mängel, keine anderen Angebote, keine Geschichten. Kein Betreff, keine "
           "Anführungszeichen. Schluss: „%s“." % (quelle, regel, gruss),
           "Artikel: %s\nPreis des Verkäufers: %s\nMein Wunschpreis: %s" % (titel[:120], _eur(preis), _eur(mein)), 220, 0.5)
    if t and _eur(mein).split(" ")[0].split(",")[0] in t and (weg != "versand" or ("paypal" in t.lower() and "freund" not in t.lower())):
        return " ".join(t.split()).strip('"„“')
    return "Hallo, ich habe Interesse an „%s“. Wäre %s für dich in Ordnung? %s %s" % (titel[:70], _eur(mein), abwicklung, gruss)


def gegenantwort(titel, preis, mein, antwort, name="", weg="abholung"):
    """Vorschlag für die Antwort auf die Rückmeldung des Verkäufers. Bleibt beim eigenen Preis; den Abschluss macht der Käufer selbst."""
    gruss = "Viele Grüße" + (", " + name if name else "")
    t = ki("Du hilfst einem privaten Käufer beim Verhandeln auf einem Kleinanzeigenmarkt. Er will höchstens seinen Wunschpreis zahlen. "
           "Lies die Antwort des Verkäufers und antworte NUR mit JSON: {\"lage\": eines von \"einig\" (Verkäufer nimmt den Wunschpreis oder "
           "weniger an), \"gegenangebot\" (Verkäufer nennt einen höheren Preis), \"abgelehnt\", \"rueckfrage\", \"unklar\", \"betrugsverdacht\" (Verkäufer will Vorkasse, PayPal Freunde, Gutscheine, "
           "schickt Links/Codes, will auf WhatsApp/Mail wechseln, Kurier-Geschichte, ist angeblich im Ausland – dann zusätzlich \"warnung\": ein Satz, "
           "und als Antwort: nur Abholung mit Barzahlung oder „Sicher bezahlen“ in der App), "
           "\"preis_verkaeufer\": genannter Preis als Zahl oder null, \"antwort\": kurze freundliche Antwort per Du, höchstens 50 Wörter. "
           "Bei \"einig\": bedanken und nach Abholung/Bezahlung und Termin fragen, nichts fest zusagen außer dem Preis. Bei \"gegenangebot\": "
           "höflich beim Wunschpreis bleiben und einmal begründen (zeitnahe Abholung, sofortige Bezahlung). Bei \"abgelehnt\": freundlich "
           "bedanken und anbieten, dass das Angebot bestehen bleibt. Erfinde nichts. Schluss: „%s“.}" % gruss,
           "Artikel: %s\nPreis des Verkäufers laut Anzeige: %s\nMein Wunschpreis: %s\nAbwicklung: %s\nAntwort des Verkäufers: %s" % (
               titel[:120], _eur(preis), _eur(mein),
               "Versand; Zahlung nur per PayPal Waren und Dienstleistungen mit Käuferschutz, Gebühr trägt der Käufer; nie Freunde und Familie" if weg == "versand" else "Abholung mit Barzahlung",
               antwort[:800]),
           300, 0.4, 12)
    warn = kern.betrug(antwort)
    if warn:      # Warnzeichen gehen vor: nicht weiterverhandeln, sondern auf sicherem Weg bestehen
        return {"lage": "betrugsverdacht", "preis_verkaeufer": None, "warn": warn,
                "antwort": "Danke für die Rückmeldung. Ich kaufe nur bei persönlicher Abholung mit Barzahlung oder über „Sicher bezahlen“ "
                           "direkt hier in der App – keine Vorkasse, keine Links, kein Wechsel zu anderen Kanälen. Wenn das für dich passt, "
                           "können wir gern einen Termin ausmachen. %s" % gruss}
    try:
        d = json.loads(re.search(r"\{.*\}", t, re.S).group(0))
        if str(d.get("lage")) == "betrugsverdacht":
            return {"lage": "betrugsverdacht", "preis_verkaeufer": None, "warn": [str(d.get("warnung") or "Die Antwort wirkt wie eine bekannte Betrugsmasche")[:200]],
                    "antwort": " ".join(str(d.get("antwort") or "").split())}
        return {"lage": str(d.get("lage") or "unklar"), "preis_verkaeufer": d.get("preis_verkaeufer") if isinstance(d.get("preis_verkaeufer"), (int, float)) else None,
                "antwort": " ".join(str(d.get("antwort") or "").split())}
    except Exception:
        return {"lage": "unklar", "preis_verkaeufer": None,
                "antwort": "Danke für deine Antwort. Mein Angebot von %s steht – ich könnte zeitnah abholen oder sofort bezahlen. %s" % (_eur(mein), gruss)}


# ---------- Produktvergleich ----------
ALTERNATIVEN = ('Du bekommst ein Produkt mit Angaben von der Angebotsseite. Bestimme zuerst genau, was für ein Gerät es ist, und nenne dann bis zu '
                'drei direkt vergleichbare Konkurrenzprodukte: gleiche Geräteart mit denselben Kernfunktionen, ähnliche Preisklasse, in Deutschland '
                'erhältlich, anderer Hersteller oder das Nachbarmodell. KEIN Zubehör, keine Filter, keine Ersatzteile, keine anderen Gerätearten. '
                'Antworte NUR mit JSON: {"gattung": Geräteart in wenigen Wörtern mit den Kernfunktionen, "alternativen": ["Marke Modell", …]}. '
                'Nur Produkte, die es sicher gibt; lieber weniger oder keine als erfundene.')
VERGLEICH = ('Du vergleichst Produkte für einen Käufer in Deutschland. Grundlage sind zuerst die mitgelieferten „Angaben von der Angebotsseite“; '
             'dein allgemeines Wissen nur ergänzend. Erfinde keine technischen Daten: Was du nicht sicher weißt, kommt in "unsicher". '
             'Preise nennst du nur so, wie sie mitgeliefert sind. Antworte NUR mit JSON: {"produkte": [{"name": genau der mitgelieferte Name, '
             '"kurz": ein Satz, was es ist, "kann": [bis 6 Stichpunkte: was es kann/hat], "kann_nicht": [bis 5: was es nicht kann/nicht hat], '
             '"plus": [bis 4 Vorteile gegenüber den anderen], "minus": [bis 4 Nachteile gegenüber den anderen], "fuer_wen": ein Satz, '
             '"unsicher": [Punkte, die du nicht sicher weißt, sonst leer], "vergleichbar": true oder false – false, wenn es eine andere Geräteart, '
             'Zubehör, ein Filter oder ein Ersatzteil ist und deshalb nicht mit Produkt 1 verglichen werden kann}], "empfehlung": {"name": einer der Namen, "grund": zwei bis drei Sätze '
             'mit Bezug auf Preis und Wunsch des Käufers, "warum_kaufen": [3 bis 5 konkrete Gründe, warum der Käufer genau dieses kaufen soll – '
             'jeweils mit Zahl oder Vergleich zu den anderen, z. B. Preisunterschied in Euro, Funktion, die nur dieses hat], '
             '"vorteile": [3 bis 5 Vorteile des empfohlenen Produkts], "nachteile": [2 bis 4 ehrliche Nachteile oder Risiken des empfohlenen '
             'Produkts, die der Käufer vor dem Kauf wissen muss], "wann_anders": ein Satz, wann eines der anderen die bessere Wahl ist}}. '
             'Stichpunkte kurz, auf Deutsch, ohne Werbesprache.')


def alternativen(name, angaben="", preis=None):
    """Rückgabe (gattung, [Namen]). Die Angaben von der Angebotsseite sagen der KI, was für ein Gerät es wirklich ist."""
    text = "Produkt: %s\nPreis: %s\nAngaben von der Angebotsseite: %s" % (name[:200], _eur(preis) if preis else "unbekannt", (angaben or "keine")[:3500])
    roh = ki(ALTERNATIVEN, text, 220, 0.2, 20)
    try:
        d = json.loads(re.search(r"\{.*\}", roh, re.S).group(0))
        return str(d.get("gattung") or "")[:160], [" ".join(str(x).split())[:70] for x in d.get("alternativen", []) if str(x).strip()][:3]
    except Exception:
        return "", []


def vergleich(produkte, wunsch="", gattung=""):
    """produkte: [{name, preise (Text), angaben (Text von der Angebotsseite)}]. Rückgabe dict oder None, wenn die KI nicht antwortet."""
    text = ("Wunsch des Käufers: %s\n\n" % wunsch[:300]) if wunsch else ""
    if gattung:
        text += "Geräteart von Produkt 1: %s\n\n" % gattung
    for i, p in enumerate(produkte, 1):
        text += "Produkt %d: %s\nGefundene Preise: %s\nAngaben von der Angebotsseite: %s\n\n" % (
            i, p["name"], p.get("preise") or "keine gefunden", p.get("angaben") or "keine")
    roh = ki(VERGLEICH, text[:14000], 2800, 0.2, 90)
    try:
        d = json.loads(re.search(r"\{.*\}", roh, re.S).group(0))
        liste = lambda x, n: [" ".join(str(w).split())[:140] for w in (x if isinstance(x, list) else []) if str(w).strip()][:n]
        aus = []
        for p in d.get("produkte", [])[:len(produkte)]:
            aus.append({"name": str(p.get("name", ""))[:120], "kurz": str(p.get("kurz", ""))[:240], "kann": liste(p.get("kann"), 6),
                        "kann_nicht": liste(p.get("kann_nicht"), 5), "plus": liste(p.get("plus"), 4), "minus": liste(p.get("minus"), 4),
                        "fuer_wen": str(p.get("fuer_wen", ""))[:240], "unsicher": liste(p.get("unsicher"), 4), "vergleichbar": p.get("vergleichbar") is not False})
        e = d.get("empfehlung") or {}
        return {"produkte": aus, "empfehlung": {"name": str(e.get("name", ""))[:120], "grund": str(e.get("grund", ""))[:600],
                                                "warum_kaufen": liste(e.get("warum_kaufen"), 5), "vorteile": liste(e.get("vorteile"), 5),
                                                "nachteile": liste(e.get("nachteile"), 4),
                                                "wann_anders": str(e.get("wann_anders", ""))[:300]}} if aus else None
    except Exception:
        return None


# ---------- Produktdetails: Eigenschaften und Ausstattung eines ausgewählten Angebots ----------
DETAILS = ('Du stellst für einen Käufer die Eigenschaften eines Produkts zusammen. Grundlage sind zuerst die „Angaben von der Angebotsseite“; '
           'allgemeines Wissen über das Modell nur ergänzend. Erfinde nichts; Unsicheres kommt in "unsicher". Antworte NUR mit JSON: '
           '{"produkt": sauberer Produktname (Marke Modell), "kurz": ein bis zwei Sätze, was es ist, "eigenschaften": [["Merkmal", "Wert"], … bis 14 '
           'technische Daten wie Maße, Leistung, Speicher, Anschlüsse, Baujahr], "ausstattung": [bis 10 Stichpunkte: Funktionen und Ausstattung], '
           '"lieferumfang": [was laut Angebot dabei ist, sonst leer], "zu_diesem_angebot": [bis 6 Punkte nur aus der Angebotsseite: Zustand, Mängel, '
           'Alter, Garantie, Abholung/Versand], "unsicher": [Punkte, die nicht sicher sind]}. Deutsch, knapp, keine Werbesprache.')


def details(name, angaben="", preis=None, quelle=""):
    text = "Angebot: %s\nPreis: %s\nQuelle: %s\nAngaben von der Angebotsseite: %s" % (name[:160], _eur(preis) if preis else "unbekannt", quelle, angaben or "keine lesbar")
    roh = ki(DETAILS, text[:6000], 1100, 0.1, 45)
    try:
        d = json.loads(re.search(r"\{.*\}", roh, re.S).group(0))
        liste = lambda x, n: [" ".join(str(w).split())[:160] for w in (x if isinstance(x, list) else []) if str(w).strip()][:n]
        paare = [[" ".join(str(p[0]).split())[:50], " ".join(str(p[1]).split())[:120]] for p in (d.get("eigenschaften") or [])
                 if isinstance(p, list) and len(p) == 2 and str(p[1]).strip()][:14]
        return {"produkt": str(d.get("produkt") or name)[:120], "kurz": str(d.get("kurz", ""))[:400], "eigenschaften": paare,
                "ausstattung": liste(d.get("ausstattung"), 10), "lieferumfang": liste(d.get("lieferumfang"), 8),
                "zu_diesem_angebot": liste(d.get("zu_diesem_angebot"), 6), "unsicher": liste(d.get("unsicher"), 5)}
    except Exception:
        return None
