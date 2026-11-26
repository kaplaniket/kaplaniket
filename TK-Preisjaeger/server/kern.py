# TK Preisjäger – Kern: erkennt, ob ein Angebot genau das gesuchte Produkt ist. Claude 26.11.2026
# Keine Netzabrufe hier – nur Text und Zahlen, damit sich alles ohne Internet prüfen lässt (pruefung.py).
import re
import statistics

EINHEITEN = {"gb", "tb", "mb", "ml", "l", "kg", "g", "w", "v", "mah", "ah", "mm", "cm", "m", "zoll", "hz", "mp", "wh", "kw", "ps", "ccm", "k"}
# Wörter, die eine andere Ausführung desselben Namens bezeichnen
AUSFUEHRUNG = {"pro", "max", "plus", "mini", "ultra", "lite", "fe", "air", "se", "xl", "slim", "digital", "oled", "ti", "super",
               "xt", "promax", "neo", "edge", "note", "fold", "flip", "studio", "go", "active", "classic", "elite", "premium", "junior", "kids", "s", "e", "c", "a", "x"}
ZUBEHOER = {"hülle", "huelle", "hülle", "case", "cover", "schutzhülle", "handyhülle", "panzerglas", "schutzglas", "schutzfolie", "folie",
            "displayschutz", "ladekabel", "kabel", "ladegerät", "netzteil", "adapter", "halterung", "halter", "armband", "tasche",
            "ersatzakku", "ersatzteil", "ersatzteile", "backcover", "rückseite", "akkudeckel", "platine", "mainboard", "logicboard",
            "ersatzdisplay", "lcd", "display", "bildschirm", "skin", "sticker", "aufkleber", "bumper", "etui", "dockingstation", "dock",
            "fernbedienung", "ständer", "standfuß", "tastatur", "pencil", "stift", "ohrpolster", "aufsatz", "attrappe", "dummy",
            "anleitung", "handbuch", "poster", "simkartenhalter", "kameraglas", "linse", "objektivdeckel", "gehäuse", "rahmen", "lüfter"}
# eindeutiges Zubehör: zählt auch direkt hinter dem Produktnamen („iPhone 13 Hülle“)
STARK = {"hülle", "huelle", "case", "cover", "covers", "schutzhülle", "handyhülle", "panzerglas", "schutzglas", "schutzfolie", "folie",
         "displayschutz", "halterung", "armband", "tasche", "ersatzakku", "ersatzteil", "ersatzteile", "backcover", "akkudeckel",
         "ersatzdisplay", "skin", "sticker", "aufkleber", "bumper", "etui", "ohrpolster", "polster", "earpads", "pads", "cups",
         "attrappe", "dummy", "anleitung", "poster", "kameraglas", "hardcase", "aufbewahrung", "aufbewahrungsbox", "attachments"}
ZUBEHOER |= STARK
BEIGABE = {"ovp", "rechnung", "zubehör", "garantie", "originalverpackung", "restgarantie", "karton"}
NACHBAU = {"replica", "replika", "replik", "nachbau", "fake", "fälschung", "kopie", "imitat", "clone", "klon"}
MITGELIEFERT = {"inkl", "inklusive", "mit", "samt", "plus", "und", "incl", "zzgl", "dazu", "sowie", "gratis"}
PASSEND = {"für", "fuer", "for", "passend", "kompatibel", "geeignet", "compatible"}
GESUCH = {"suche", "gesuch", "gesucht", "ankauf", "kaufe", "tausch", "tausche", "miete", "mieten", "verleih", "vermiete",
          "reparatur", "reparieren", "wanted"}
DEFEKT_WORT = {"defekt", "defekter", "defektes", "defekte", "kaputt", "bastler", "bastlergerät", "displaybruch", "displayschaden",
               "wasserschaden", "ersatzteilspender", "teilespender", "gesprungen", "gebrochen", "gesperrt", "icloudsperre",
               "funktionslos", "glasbruch", "sturzschaden", "beschädigt", "beschädigter", "beschädigtes", "displayriss", "broken",
               "rotto", "riparare", "cassé", "casse", "fissure", "fissuré", "hs", "roto", "stuk", "uszkodzony"}
DEFEKT_SATZ = ["für bastler", "an bastler", "nicht funktionsfähig", "ohne funktion", "icloud lock", "icloud gesperrt", "icloud sperre",
               "geht nicht mehr an", "lässt sich nicht einschalten", "display kaputt", "display defekt", "display gebrochen",
               "als ersatzteil", "nur ersatzteile", "nicht mehr funktionsfähig", "als defekt", "sprung im display", "riss im display",
               "for parts", "not working", "pour pièces", "per ricambi", "da riparare", "voor onderdelen"]
VERNEINUNG = {"kein", "keine", "keinen", "keinerlei", "nicht", "ohne", "nie", "weder", "frei"}
LEER = ["nur ovp", "nur verpackung", "nur karton", "leerkarton", "leere ovp", "leere verpackung", "ohne gerät", "nur die ovp",
        "leerverpackung", "nur box", "leere box", "nur originalverpackung"]
NEU_SATZ = ["neu & ovp", "neu und ovp", "neu ovp", "neu in ovp", "nagelneu", "versiegelt", "originalverpackt", "ungeöffnet",
            "neu und unbenutzt", "neu, unbenutzt", "brandneu", "neuware", "sealed", "noch verschweißt", "neu!"]
AUFBEREITET = ["generalüberholt", "refurbished", "wiederaufbereitet", "aufbereitet", "renewed", "refurbed"]
GEBRAUCHT = ["gebraucht", "b-ware", "gebrauchsspuren", "sehr gut", "wie neu", "guter zustand", "top zustand", "akzeptabel"]

_wort = re.compile(r"[a-z0-9äöüß]+")
_teil = re.compile(r"[a-zäöüß]+|\d+")


def zerlegen(text):
    """'iPhone13 128 GB' -> [['iphone','13'], ['128gb']] – Gruppen aus zusammengehörigen Teilen."""
    t = (text or "").lower().replace("+", " plus ").replace("&", " und ")
    gruppen = []
    for w in _wort.findall(t):
        teile = _teil.findall(w)
        g, i = [], 0
        while i < len(teile):
            if teile[i].isdigit() and i + 1 < len(teile) and teile[i + 1] in EINHEITEN:
                g.append(teile[i] + teile[i + 1]); i += 2
            else:
                g.append(teile[i]); i += 1
        gruppen.append(g)
    # „128 gb“ (getrennt geschrieben) zusammenziehen
    aus = []
    for g in gruppen:
        if aus and len(g) == 1 and g[0] in EINHEITEN and len(aus[-1]) >= 1 and aus[-1][-1].isdigit():
            aus[-1][-1] = aus[-1][-1] + g[0]
        else:
            aus.append(g)
    return aus


def flach(gruppen):
    return [t for g in gruppen for t in g]


def _finde(folge, teile, ab=0):
    n = len(folge)
    for i in range(ab, len(teile) - n + 1):
        if teile[i:i + n] == folge:
            return i
    return -1


def zustand(titel, text, vorgabe):
    t = (titel + " " + (text or "")).lower()
    if any(s in t for s in AUFBEREITET):
        return "aufbereitet"
    tt = titel.lower()
    if any(s in tt for s in NEU_SATZ) or re.match(r"^\s*(neu|new)\b", tt):
        return "neu" if vorgabe != "aufbereitet" else vorgabe
    if vorgabe == "neu" and any(s in tt for s in GEBRAUCHT):
        return "gebraucht"
    return vorgabe


def ist_defekt(titel, text):
    for quelle in (titel, text or ""):
        t = quelle.lower()
        teile = flach(zerlegen(t))
        for i, w in enumerate(teile):
            if w in DEFEKT_WORT and not (set(teile[max(0, i - 3):i]) & VERNEINUNG):
                return True
        for s in DEFEKT_SATZ:
            j = t.find(s)
            if j >= 0 and not (set(_wort.findall(t[max(0, j - 25):j])) & VERNEINUNG):
                return True
    return False


def pruefe(anfrage, titel, text="", streng=True):
    """Gibt (passt, grund) zurück. grund ist '' oder eines von: fehlt, ausfuehrung, zubehoer, gesuch, leer."""
    ag = zerlegen(anfrage)
    tt = flach(zerlegen(titel))
    if not ag or not tt:
        return False, "fehlt"
    aw = set(flach(ag))
    stellen = []
    for n, g in enumerate(ag):
        i = _finde(g, tt)
        if i < 0:
            return False, "fehlt"
        if n and g[0].isdigit() and not re.match(r"\d+[a-zäöü]+$", ag[n - 1][-1]):
            # Modellnummer: muss unmittelbar auf das vorige Suchwort folgen („iphone 13“, nicht „iphone 12 … 13“)
            i = _finde(ag[n - 1] + g, tt)
            if i < 0:
                return False, "fehlt"
            i += len(ag[n - 1])
        stellen.append((i, i + len(g)))
    erste = min(s[0] for s in stellen)
    tl = titel.lower()
    if any(s in tl for s in LEER):
        return False, "leer"
    if set(tt) & (NACHBAU - aw):
        return False, "nachbau"
    letzte = max(s[1] for s in stellen)
    if set(tt[:6]) & (GESUCH - aw) or re.search(r"\b(suche|ankauf|tausche?)\b", tl[:40]) and not (GESUCH & aw):
        return False, "gesuch"
    # Zubehör: „Hülle für iPhone 13“ – Zubehörwort vor dem Produkt oder „für/passend“ davor; „inkl. Hülle“ ist in Ordnung
    for i, w in enumerate(tt):
        if w in aw:
            continue
        if w in PASSEND and i < erste:
            return False, "zubehoer"
        if w in ZUBEHOER or any(w.endswith(z) for z in ("hülle", "kabel", "folie", "glas", "halterung", "tasche", "case", "cover")) and w not in aw:
            davor = set(tt[max(0, i - 4):i])
            if i < erste and not (davor & MITGELIEFERT):
                return False, "zubehoer"
            if i > erste and not (davor & MITGELIEFERT) and (set(tt[max(0, i - 3):i]) & PASSEND):
                return False, "zubehoer"
            if w in STARK and letzte <= i <= letzte + 1 and not (davor & MITGELIEFERT):
                # „iPhone 13 Hülle schwarz“ ist Zubehör; „iPhone 13, Hülle, Ladekabel, OVP“ ist das Gerät mit Beigaben
                if not any(x in ZUBEHOER or x in BEIGABE for x in tt[i + 1:]):
                    return False, "zubehoer"
    if streng:
        # andere Ausführung: direkt hinter (oder vor) dem gesuchten Namen steht z. B. „Pro“, „Mini“, „Max“
        belegt = set()
        for a, b in stellen:
            belegt.update(range(a, b))
        for a, b in stellen:
            for j in list(range(b, min(b + 2, len(tt)))) + [a - 1]:
                if j < 0 or j in belegt:
                    continue
                w = tt[j]
                if w in AUSFUEHRUNG and w not in aw:
                    if len(w) == 1 and not (j == b and tt[b - 1].isdigit()):
                        continue      # einzelne Buchstaben nur direkt hinter einer Zahl werten (z. B. „13 s“)
                    if j == a - 1 and w in ("s", "e", "c", "a", "x", "se", "go", "note", "edge", "active", "air", "studio", "neo"):
                        continue
                    return False, "ausfuehrung:" + w
        # andere Größe/Leistung als gesucht (nur wenn der Suchtext eine nennt)
        for g in ag:
            for w in g:
                m = re.match(r"(\d+)([a-zäöü]+)$", w)
                if m and m.group(2) in ("gb", "tb"):
                    andere = [x for x in tt if re.match(r"\d+(gb|tb)$", x) and x != w]
                    if andere and w not in tt:
                        return False, "ausfuehrung:" + andere[0]
    return True, ""


def ausfuehrung_name(grund):
    return grund.split(":", 1)[1] if ":" in grund else ""


def bewerten(anfrage, angebote, streng=True, ueblich=None):
    """Teilt Rohangebote ein. Rückgabe: dict mit treffer, auffaellig, defekt, aussortiert (Zähler) und hinweise."""
    treffer, defekt, zaehler, andere = [], [], {}, {}
    gesehen = set()
    for a in angebote:
        if not a.get("preis") or a["preis"] <= 0:
            zaehler["ohne Preis"] = zaehler.get("ohne Preis", 0) + 1
            continue
        schluessel = (a["quelle"], a.get("url") or a["titel"])
        if schluessel in gesehen:
            continue
        gesehen.add(schluessel)
        ok, grund = pruefe(anfrage, a["titel"], a.get("text", ""), streng)
        if not ok:
            if grund.startswith("ausfuehrung"):
                n = ausfuehrung_name(grund)
                andere[n] = andere.get(n, 0) + 1
                name = "andere Ausführung"
            else:
                name = {"fehlt": "anderes Produkt", "zubehoer": "Zubehör/Ersatzteil", "gesuch": "Gesuch/Ankauf/Tausch", "leer": "nur Verpackung", "nachbau": "Nachbau/Fälschung"}[grund]
            zaehler[name] = zaehler.get(name, 0) + 1
            continue
        a["zustand"] = zustand(a["titel"], a.get("text", ""), a.get("zustand", "gebraucht"))
        if ist_defekt(a["titel"], a.get("text", "")):
            a["zustand"] = "defekt"
            defekt.append(a)
        else:
            treffer.append(a)
    # Ausreißer: weit unter dem üblichen Preis = meist Zubehör, Lockangebot oder Betrug -> getrennt zeigen
    auffaellig, mitte = [], None
    if ueblich or len(treffer) >= 5:
        mitte = ueblich or statistics.median(a["preis"] for a in treffer)
        if not ueblich:      # Zubehör zieht die Mitte nach unten: einmal ohne die Ausreißer neu bestimmen
            mitte = statistics.median([a["preis"] for a in treffer if a["preis"] >= mitte * 0.38] or [mitte])
        grenze = mitte * 0.38
        auffaellig = [a for a in treffer if a["preis"] < grenze]
        treffer = [a for a in treffer if a["preis"] >= grenze]
    for l in (treffer, auffaellig, defekt):
        l.sort(key=lambda a: (a["preis"] + (a.get("versand") or 0), a["preis"]))
    return {"treffer": treffer, "auffaellig": auffaellig, "defekt": defekt, "aussortiert": zaehler,
            "andere_ausfuehrungen": dict(sorted(andere.items(), key=lambda x: -x[1])[:8]), "ueblich": mitte}


def groessen(anfrage, treffer):
    """Wenn im Suchtext keine Speichergröße steht: welche kommen bei den Treffern vor? (zum Verfeinern)"""
    if any(re.match(r"\d+(gb|tb)$", w) for w in flach(zerlegen(anfrage))):
        return {}
    z = {}
    for a in treffer:
        for w in set(flach(zerlegen(a["titel"]))):
            if re.match(r"\d+(gb|tb)$", w) and (w.endswith("tb") or int(w[:-2]) >= 16):
                z[w] = z.get(w, 0) + 1
    return {k.upper().replace("GB", " GB").replace("TB", " TB"): v for k, v in sorted(z.items(), key=lambda x: -x[1])[:6] if v >= 2}
