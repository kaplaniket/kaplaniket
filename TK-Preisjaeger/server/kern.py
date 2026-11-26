# TK Preisjäger – Kern: erkennt, ob ein Angebot genau das gesuchte Produkt ist. Claude 26.11.2026
# Keine Netzabrufe hier – nur Text und Zahlen, damit sich alles ohne Internet prüfen lässt (pruefung.py).
import re
import statistics

EINHEITEN = {"gb", "tb", "mb", "ml", "l", "kg", "g", "w", "v", "mah", "ah", "mm", "cm", "m", "zoll", "hz", "mp", "wh", "kw", "ps", "ccm", "k"}
# Wörter, die eine andere Ausführung desselben Namens bezeichnen
AUSFUEHRUNG = {"pro", "max", "plus", "mini", "ultra", "lite", "fe", "air", "se", "xl", "slim", "digital", "oled", "ti", "super",
               "xt", "promax", "neo", "edge", "note", "fold", "flip", "studio", "go", "active", "classic", "elite", "premium", "junior", "kids",
               "portal", "vr", "s", "e", "c", "a", "x"}
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
         "attrappe", "dummy", "anleitung", "poster", "kameraglas", "hardcase", "aufbewahrung", "aufbewahrungsbox", "attachments",
         "zubehör", "controller", "kontroller", "dualsense", "bürste", "bürsten", "kombibürste", "filter", "aufsätze", "ladestation",
         "ersatzrolle", "verpackungskarton", "brosse", "filtro", "düse", "spiel", "spiele", "game", "games"}
ZUBEHOER |= STARK
BEIGABE = {"ovp", "rechnung", "zubehör", "garantie", "originalverpackung", "restgarantie", "karton"}
NACHBAU = {"replica", "replika", "replik", "nachbau", "fake", "fälschung", "kopie", "imitat", "clone", "klon"}
MITGELIEFERT = {"inkl", "inklusive", "mit", "samt", "plus", "und", "incl", "zzgl", "dazu", "sowie", "gratis"}
PASSEND = {"für", "fuer", "for", "passend", "kompatibel", "geeignet", "compatible", "per", "pour", "para", "voor", "gegen"}
# Wörter, die vor dem Produktnamen stehen dürfen, ohne dass es ein anderes Produkt ist
FUELL = {"verkaufe", "verkauf", "verkaufen", "biete", "mein", "meine", "meinen", "ein", "eine", "einen", "neu", "neue", "neuer", "neues",
         "neuwertig", "neuwertige", "neuwertiges", "original", "originale", "originales", "top", "zustand", "gebraucht", "wie", "sehr",
         "gut", "guter", "ovp", "der", "die", "das", "hier", "zum", "zu", "angebot", "super", "fast", "kaum", "unbenutzt", "versiegelt",
         "und", "in", "mit", "nagelneu", "nagelneues", "tolles", "toller", "schönes", "schöner", "gepflegtes", "gepflegter"}
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
            if (w in DEFEKT_WORT or "defekt" in w) and not (set(teile[max(0, i - 3):i]) & VERNEINUNG):
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
    # Zusammengesetzte Wörter: Suchwort „osmose“ steckt in „Umkehrosmose“/„Osmoseanlage“, „wasserspender“ in „Tischwasserspender“
    lang = [g[0] for g in ag if len(g) == 1 and len(g[0]) >= 5 and g[0].isalpha()]
    if lang:
        endung = ("hülle", "kabel", "folie", "glas", "halterung", "tasche", "case", "cover", "filter", "teil", "teile")
        tt = [next((q for q in lang if q in w and w != q and not w.endswith(endung) and w not in ZUBEHOER and not w.startswith("ersatz")), w) for w in tt]
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
    # Die Suchwörter (ohne Größenangaben wie 128gb) müssen beieinander stehen: „Dyson Zubehör für V10, V15, V8, V11“ ist kein Dyson V11
    kern_g = [(n, g) for n, g in enumerate(ag) if not all(re.match(r"\d+[a-zäöü]+$", w) for w in g)]
    if len(kern_g) > 1:
        orte = [[i for i in range(len(tt) - len(g) + 1) if tt[i:i + len(g)] == g] for _, g in kern_g]
        beste = None
        for start in orte[0]:
            nah = [start] + [min(o, key=lambda x: abs(x - start)) for o in orte[1:]]
            weite = max(p + len(g) for p, (_, g) in zip(nah, kern_g)) - min(nah)
            if beste is None or weite < beste[0]:
                beste = (weite, nah)
        if beste[0] > sum(len(g) for _, g in kern_g) + 2:
            return False, "fehlt"
        for p, (n, g) in zip(beste[1], kern_g):
            stellen[n] = (p, p + len(g))
        erste = min(s[0] for s in stellen)
    # Produktname erst weit hinten, davor etwas anderes: „Crucial 2TB SSD für PS5 PlayStation 5“
    erste_kern = next(i for i, w in enumerate(tt) if w in aw)
    davor_fremd = [w for w in tt[:erste_kern] if w not in FUELL and w not in aw and not w.isdigit()]
    if len(davor_fremd) >= 5:
        return False, "fehlt"
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
        if w.startswith("ersatz") and not (set(tt[max(0, i - 4):i]) & MITGELIEFERT):
            return False, "zubehoer"      # Ersatzfilter, Ersatzakku, Ersatzteil … – egal wo im Titel
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
        for nr, (a, b) in enumerate(stellen):
            # unmittelbar dahinter; davor nur zwischen zwei Suchwörtern („MacBook Pro M2“ bei Suche „macbook m2“)
            for j in ([b] if b < len(tt) else []) + ([a - 1] if nr else []):
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


# Angebote unter der Hälfte des üblichen Preises sind fast immer Zubehör, Spiele, Lockpreise oder Betrug
GRENZE = 0.5


def kuerzungen(anfrage):
    """Suchtext mit je einem weggelassenen Beschreibungswort: [(kürzerer Suchtext, weggelassenes Wort)].
    Marke (erstes Wort) und alles mit Ziffern bleiben immer; erst ab drei Wörtern. Letzte Wörter zuerst."""
    worte = anfrage.split()
    if len(worte) < 3:
        return []
    aus = []
    for n in range(len(worte) - 1, 0, -1):
        if any(c.isdigit() for c in worte[n]) or len(worte[n]) < 3:
            continue
        aus.append((" ".join(w for i, w in enumerate(worte) if i != n), worte[n].lower()))
    return aus


def bewerten(anfrage, angebote, streng=True, ueblich=None):
    """Teilt Rohangebote ein. Rückgabe: dict mit treffer, auffaellig, defekt, aussortiert (Zähler) und hinweise."""
    treffer, defekt, zaehler, andere, aehnlich = [], [], {}, {}, []
    kurz = kuerzungen(anfrage)
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
        if not ok and grund == "fehlt":
            # Fast passend: genau ein Beschreibungswort fehlt im Titel („Osmose“), sonst stimmt alles
            for kuerzer, wort in kurz:
                if pruefe(kuerzer, a["titel"], a.get("text", ""), streng)[0]:
                    a["fehlt"] = wort
                    a["zustand"] = "defekt" if ist_defekt(a["titel"], a.get("text", "")) else zustand(a["titel"], a.get("text", ""), a.get("zustand", "gebraucht"))
                    if a["zustand"] != "defekt":
                        aehnlich.append(a)
                    break
            if a.get("fehlt"):
                zaehler["fast passend (ein Wort fehlt)"] = zaehler.get("fast passend (ein Wort fehlt)", 0) + 1
                continue
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
            mitte = statistics.median([a["preis"] for a in treffer if a["preis"] >= mitte * GRENZE] or [mitte])
        grenze = mitte * GRENZE
        auffaellig = [a for a in treffer if a["preis"] < grenze]
        treffer = [a for a in treffer if a["preis"] >= grenze]
    for l in (treffer, auffaellig, defekt, aehnlich):
        l.sort(key=lambda a: (a["preis"] + (a.get("versand") or 0), a["preis"]))
    return {"treffer": treffer, "auffaellig": auffaellig, "defekt": defekt, "aehnlich": aehnlich[:60], "aussortiert": zaehler,
            "andere_ausfuehrungen": dict(sorted(((k, v) for k, v in andere.items() if len(k) > 1 and v >= 3), key=lambda x: -x[1])[:6]), "ueblich": mitte}


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


# ---------- Freitext verstehen: „Ich suche einen Wasserspender mit Sprudel und Heißwasser bis 900 €, gebraucht“ ----------
_AUSLOESER = re.compile(r"\b(ich|suche|sucht|brauche|möchte|will|soll|sollte|mit|ohne|unter|bis|max|maximal|höchstens|euro|gesucht|kaufen|inkl|inklusive|kein|keine|keinen)\b|€")
_FUELLWORT = {"ich", "suche", "suchen", "brauche", "möchte", "will", "hätte", "gerne", "gern", "bitte", "kaufen", "haben", "einen", "eine", "ein",
              "einem", "einer", "eines", "für", "mich", "mir", "uns", "nach", "günstig", "günstige", "günstigen", "günstiges", "günstiger",
              "billig", "billige", "billigen", "preiswert", "gut", "gute", "guten", "gutes", "guter", "am", "besten", "möglichst", "soll",
              "sollte", "sein", "es", "der", "die", "das", "den", "dem", "und", "oder", "zum", "zur", "gesucht", "wird", "wäre", "ist", "auch",
              "so", "wie", "was", "wo", "ausgestattet", "ausstattung", "hat", "kann", "können", "muss", "dabei", "noch", "etwa", "ca", "circa",
              "ungefähr", "preis", "kosten", "kostet", "darf", "von", "als", "zu", "in", "im", "marke", "modell", "sowie", "viel", "integriertem",
              "integrierter", "eingebautem", "eingebauter", "funktion", "zustand", "sehr", "top"}
_ZUSTAND_WORT = {"neu": "neu", "neue": "neu", "neuen": "neu", "neues": "neu", "neuer": "neu", "neuware": "neu", "gebraucht": "gebraucht",
                 "gebrauchte": "gebraucht", "gebrauchten": "gebraucht", "gebrauchtes": "gebraucht", "generalüberholt": "aufbereitet",
                 "refurbished": "aufbereitet", "aufbereitet": "aufbereitet", "geprüft": "aufbereitet"}
_ZAHL = r"(\d{1,3}(?:\.\d{3})+|\d+)(?:,\d+)?\s*(?:€|euro\b|eur\b)"


def verstehen(text):
    """Zerlegt einen frei geschriebenen Wunsch. Ohne Auslösewörter bleibt der Text unverändert das Produkt."""
    roh = " ".join((text or "").split())
    v = {"produkt": roh, "wuensche": [], "ohne": [], "max": None, "min": None, "zustand": []}
    t = roh.lower()
    if not _AUSLOESER.search(t):
        return v
    zahl = lambda s: float(s.replace(".", ""))
    m = re.search(r"\b(?:unter|bis zu|bis|max\.?|maximal|höchstens|nicht mehr als|für)\s*" + _ZAHL, t)
    if m:
        v["max"] = zahl(m.group(1)); t = t[:m.start()] + " " + t[m.end():]
    m = re.search(r"\b(?:ab|mindestens|über|mehr als)\s*" + _ZAHL, t)
    if m:
        v["min"] = zahl(m.group(1)); t = t[:m.start()] + " " + t[m.end():]
    m = re.search(_ZAHL, t)
    if m and v["max"] is None:      # „… 800 €“ ohne „bis“: als Obergrenze nehmen
        v["max"] = zahl(m.group(1)); t = t[:m.start()] + " " + t[m.end():]
    for m in list(re.finditer(r"\b(?:ohne|kein|keine|keinen)\s+([a-zäöüß0-9-]{3,})", t)):
        v["ohne"].append(m.group(1))
    t = re.sub(r"\b(?:ohne|kein|keine|keinen)\s+[a-zäöüß0-9-]{3,}", " ", t)
    worte = re.findall(r"[a-zäöüß0-9][a-zäöüß0-9.\-/]*", t)
    zu = [_ZUSTAND_WORT[w] for w in worte if w in _ZUSTAND_WORT]
    worte = [w for w in worte if w not in _ZUSTAND_WORT]
    v["zustand"] = sorted(set(zu)) if len(set(zu)) < 3 else []
    # alles hinter „mit / inkl.“ ist Ausstattung, davor das Produkt
    schnitt = next((i for i, w in enumerate(worte) if w in ("mit", "inkl", "inkl.", "inklusive", "samt")), None)
    kern_w, wunsch_w = (worte, []) if schnitt is None else (worte[:schnitt], worte[schnitt + 1:])
    v["wuensche"] = [w for w in wunsch_w if w not in _FUELLWORT and w not in ("mit", "inkl", "inklusive", "samt") and len(w) >= 3]
    kern_w = [w for w in kern_w if w not in _FUELLWORT]
    if not kern_w and v["wuensche"]:      # „mit …“ ganz vorn: erstes Wunschwort ist das Produkt
        kern_w, v["wuensche"] = v["wuensche"][:1], v["wuensche"][1:]
    v["produkt"] = " ".join(kern_w) or roh
    return v


def _hat(wort, text):
    return wort in text or (len(wort) >= 6 and wort[:-2] in text) or (len(wort) >= 8 and wort[:4] in text)


def wuensche_anwenden(e, v):
    """Wendet Höchst-/Mindestpreis, Zustand, „ohne …“ und Ausstattungswünsche auf ein Ergebnis von bewerten() an."""
    z = e["aussortiert"]

    def raus(name):
        z[name] = z.get(name, 0) + 1

    def sieb(liste):
        aus = []
        for a in liste:
            voll = (a["titel"] + " " + (a.get("text") or "") + " " + (a.get("hinweis") or "")).lower()
            if v["max"] and a["preis"] > v["max"]:
                # Privatangebote bis 40 % über dem eigenen Preis bleiben drin: die lassen sich herunterhandeln
                if a.get("art") == "privat" and a["preis"] <= v["max"] * 1.4 and a.get("zustand") != "defekt":
                    a["ueber"] = round(a["preis"] - v["max"], 2)
                else:
                    raus("über deinem Preis"); continue
            if v["min"] and a["preis"] < v["min"]:
                raus("unter deinem Mindestpreis"); continue
            if v["zustand"] and a.get("zustand") not in v["zustand"] and a.get("zustand") != "defekt":
                raus("anderer Zustand als gewünscht"); continue
            if any(_hat(o, voll) for o in v["ohne"]):
                raus("enthält, was du nicht willst"); continue
            a["warn"] = betrug(a["titel"] + " " + (a.get("text") or ""))
            a["wunsch_da"] = [w for w in v["wuensche"] if _hat(w, voll)]
            a["wunsch_offen"] = [w for w in v["wuensche"] if w not in a["wunsch_da"]]
            aus.append(a)
        return aus

    for k in ("treffer", "aehnlich", "auffaellig", "defekt"):
        e[k] = sieb(e[k])
    # Angebote, bei denen ein Ausstattungswunsch nirgends genannt ist, zählen nur als „fast passend“
    offen = [a for a in e["treffer"] if a["wunsch_offen"]]
    e["treffer"] = [a for a in e["treffer"] if not a["wunsch_offen"]]
    e["aehnlich"] = sorted(e["aehnlich"] + offen, key=lambda a: (len(a.get("wunsch_offen", [])), a["preis"]))[:80]
    return e


# ---------- Betrug und Abzocke: typische Warnzeichen in Anzeigen und in Antworten von Verkäufern ----------
_BETRUG = [
    (r"freunde\s*(und|&|\+|u\.)\s*familie|friends\s*(and|&)\s*family|paypal\s*f\s*&\s*f|\b(pp|paypal)\s*freunde", "PayPal „Freunde und Familie“ verlangt – dabei gibt es keinen Käuferschutz"),
    (r"vorkasse|vorab\s*(überweis|bezahl|zahl)|überweisung\s*vorab|anzahlung|vorauszahlung|im\s*voraus\s*(bezahl|überweis|zahl)|erst\s*(das\s*)?geld", "Vorkasse oder Anzahlung verlangt"),
    (r"western\s*union|moneygram|gutschein(karte|code)|paysafe|amazon.?gutschein|steam.?(karte|guthaben)|bitcoin|krypto|crypto|usdt", "ungewöhnlicher Zahlungsweg (Gutschein, Krypto, Bargeldtransfer)"),
    (r"whats\s*app|telegram|\bsignal\b|schreib\w*\s*(sie\s*)?(mir|mich)\s*(bitte\s*)?(per|auf|an|über)\s*(e-?mail|mail|sms)|@(gmail|outlook|hotmail|yahoo|gmx|web)\.|(\+|00)\d[\d\s/-]{9,}|\b01[5-7]\d[\d\s/-]{6,}", "will außerhalb der Plattform schreiben (WhatsApp, Mail, Telefonnummer)"),
    (r"klick\w*\s*(sie\s*)?(bitte\s*)?(auf\s*)?(den|diesen|folgenden)\s*link|link\s*(zum|zur|für)\s*(bezahl|zahlung|empfang|versand)|bestätigungs?code|sms.?code|\btan\b|kreditkartendaten|kartendaten|https?://", "Link oder Code geschickt/verlangt – typische Phishing-Masche"),
    (r"kurier|abholdienst|spedition\s*(holt|kommt)|dhl\s*(kurier|holt)|versandunternehmen\s*(holt|kommt)", "Kurier/Abholdienst soll das Geschäft abwickeln"),
    (r"im\s*ausland|aus\s*dem\s*ausland|nicht\s*in\s*deutschland|versand\s*aus\s*(england|uk|spanien|polen|china|frankreich|italien)|beruflich\s*(im|in)\s*\w+\s*(unterwegs)?", "Verkäufer angeblich im Ausland"),
    (r"sofort\s*(überweis|bezahl)|heute\s*noch\s*(überweis|bezahl)|nur\s*heute|viele\s*(andere\s*)?interessenten.*(sofort|schnell)", "Zeitdruck beim Bezahlen"),
    (r"abholung\s*(ist\s*)?(leider\s*)?nicht\s*möglich|keine\s*abholung|nur\s*(per\s*)?versand", "keine Abholung möglich – nur Versand"),
]


def betrug(text):
    """Liste der Warnzeichen im Text (leer = keines gefunden). Ein Fund ist ein Hinweis, kein Beweis."""
    t = (text or "").lower()
    return [hinweis for muster, hinweis in _BETRUG if re.search(muster, t)]
