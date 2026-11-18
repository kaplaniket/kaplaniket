#!/usr/bin/env python3
"""TK KI – Live-Daten (16.11.2026): Termine, Erinnerungen, Fristen und offene Anliegen.
Liest direkt (nur lesend): Kalender-Stand (~/gedaechtnis/termine_cache.txt), TKMail-Fristen
(postamt.db), Karten (karten.db) und die Wiki-Seite offene-punkte. Antwortet ohne Sprachmodell.
Test: python3 live.py "Welche Termine habe ich diese Woche?"
"""
import json, os, re, sqlite3, sys
from datetime import date, datetime, timedelta

H = os.path.expanduser("~")
CACHE = H + "/gedaechtnis/termine_cache.txt"
TKDB = H + "/postamt/postamt.db"
KARTEN = H + "/gedaechtnis/karten.db"
OFFEN = H + "/Obsidian/06 Wiki/themen/offene-punkte.md"
WT = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]
WTL = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"]
MONATE = {m: i + 1 for i, m in enumerate(["januar", "februar", "märz", "april", "mai", "juni", "juli", "august", "september", "oktober", "november", "dezember"])}
GEHEIM = re.compile(r"passw|kennwort|schlüssel verborgen|token|\bpin\b|\btan\b", re.I)
STOPP = set("wann welche welcher welches meine meinen meiner mein habe hast haben steht stehen noch nächste nächsten diese dieser diesen heute morgen woche monat termin termine frist fristen muss soll kann gibt eine einen einem über oder und der die das ist sind von für mit bei zum zur".split())

ALLGEMEIN = set("""heute morgen übermorgen gestern woche wochen wochenende monat monats jahr jahres tage tagen nächste nächsten nächster nächstes
übernächste übernächsten kommende kommenden anstehende anstehenden ansteht anstehen alle alles aktuell aktuelle gerade jetzt bald demnächst termin termine terminen
kalender verabredung verabredungen feiertag feiertage offen offene offenen offenes offener punkte sachen vorgänge aufgaben aufgabe anliegen themen enden todo todos
erledigen erledigt zeig zeige nenn nenne liste übersicht überblick welche welcher welches welchen meine meinen meiner mein habe hab hast hat steht stehen gibt denn
noch liegt muss soll kann was wann wie wer ist sind mit dem den der die das des beim bei für von zum zur ich mir mich und oder mal bitte sag los vor geplant
wichtig wichtige sonst eigentlich genau stand tun machen tag diese dieser diesen diesem januar februar märz april mai juni juli august september oktober november dezember
montag dienstag mittwoch donnerstag freitag samstag sonntag""".split())

def thema(frage):
    """Worum es geht, wenn die Frage mehr will als „Termine/Offenes allgemein“ – z. B. „Termin beim Finanzamt“ → {finanzamt}.
    Leer = allgemeine Frage (ganze Liste zeigen). Claude 17.11.2026: vorher bekam jede solche Frage die ganze 30-Tage-Liste."""
    return {w for w in re.findall(r"[a-zäöüß0-9]{3,}", frage.lower()) if w not in STOPP and w not in ALLGEMEIN and not w.isdigit()}

def zum_thema(frage, maxn=8):
    """Termine, Fristen und Offenes, die zum Thema der Frage passen – als fertige Zeilen."""
    w = thema(frage)
    if not w: return []
    heute = date.today(); E, _ = sammeln(); tr = []
    for e in E:
        if e["art"] == "Feiertag": continue
        if e["d"] and e["d"] < heute - timedelta(days=45): continue
        et = set(re.findall(r"[a-zäöüß0-9]{3,}", e["text"].lower()))
        if any(a[:5] == b[:5] for a in w for b in et): tr.append(_zeile(e, heute))
    return tr[:maxn]

def _key(d, text):
    return (d, re.sub(r"[^a-zäöüß0-9]", "", text.lower())[:18])

def _datum(tag, monat, heute):
    try:
        d = date(heute.year, monat, tag)
    except ValueError:
        return None
    return d if d >= heute - timedelta(days=90) else date(heute.year + 1, monat, tag)

def wiki_termine():
    aus, an = [], False
    try:
        zeilen = open(OFFEN, encoding="utf-8").read().splitlines()
    except Exception:
        return aus
    for z in zeilen:
        if z.startswith("## "):
            if an: break
            an = z.startswith("## Nächste Termine"); continue
        if an and z.startswith("|") and not z.startswith("|---") and not z.lower().startswith("| bis"):
            sp = [x.strip() for x in z.strip().strip("|").split("|")]
            if len(sp) < 2: continue
            bis = sp[0].replace("**", ""); was = sp[1].replace("**", "")
            m = re.search(r"(\d{1,2})\.(\d{1,2})\.(\d{4})", bis)
            d = None
            if m:
                try: d = date(int(m[3]), int(m[2]), int(m[1]))
                except ValueError: pass
            aus.append({"d": d, "z": None, "text": was[:170], "art": "Wiki", "bis": bis})
    return aus

def sammeln():
    """Alle Einträge aus allen Quellen, entdoppelt. Rückgabe: (liste, kalender_stand_ts)."""
    heute = date.today(); E, gesehen, stand = [], set(), 0
    def dazu(d, z, text, art, **mehr):
        text = re.sub(r"\s+", " ", text).strip()
        if not text or GEHEIM.search(text): return
        k = _key(d, text)
        if k in gesehen: return
        gesehen.add(k); E.append(dict({"d": d, "z": z, "text": text, "art": art}, **mehr))
    # 1) Kalender + Erinnerungen (Stand vom iMac, auf dem HP zwischengespeichert)
    try:
        for z in open(CACHE, encoding="utf-8").read().splitlines():
            if z.startswith("#stand"):
                stand = int(z.split()[1]); continue
            m = re.match(r"📅 \w+ (\d{1,2})\.(\d{1,2})\.\s*(\d{1,2}:\d{2})?\s*(.*?)(?:\s*\(([^()]*)\))?$", z)
            if m:
                kal = m[5] or ""
                dazu(_datum(int(m[1]), int(m[2]), heute), m[3], re.sub(r"\s+heute$", "", m[4]), "Feiertag" if "Feiertag" in kal else "Kalender")
                continue
            if z.startswith("☑️"):
                t = z[2:].strip(); m = re.search(r"\(fällig (\d{1,2})\.(\d{1,2})\.\)", t)
                d = _datum(int(m[1]), int(m[2]), heute) if m else None
                dazu(d, None, re.sub(r"\s+heute$", "", re.sub(r"\s*\(fällig [^)]*\)", "", t)), "Erinnerung")
    except Exception:
        pass
    # 2) TKMail „Fristen & Termine“ (offen)
    try:
        c = sqlite3.connect(f"file:{TKDB}?mode=ro", uri=True, timeout=3)
        for ts, mz, art, text, von, betreff in c.execute("select ts,mit_zeit,art,text,von,betreff from fristen where status='offen' order by ts"):
            dt = datetime.fromtimestamp(ts); zt = dt.strftime("%H:%M")
            b = re.sub(r"^((AW|WG|RE|FW|Fwd):\s*)+", "", betreff or "", flags=re.I).strip()
            t = (text or "")[:140] if art == "Frist" or not b else b[:110]
            dazu(dt.date(), zt if mz and zt not in ("00:00", "01:01") else None, t, "Frist" if art == "Frist" else "Mail-Termin")
        c.close()
    except Exception:
        pass
    # 3) Karten (Vorschläge/Erinnerungen, die noch offen sind)
    try:
        k = sqlite3.connect(f"file:{KARTEN}?mode=ro", uri=True, timeout=3)
        for titel, daten, typ in k.execute("select titel,daten,typ from karten where status='offen' order by ts"):
            try: j = json.loads(daten or "{}")
            except Exception: j = {}
            d = z = None
            m = re.match(r"(\d{4})-(\d{2})-(\d{2})(?: (\d{2}:\d{2}))?", j.get("faellig") or "")
            if m: d, z = date(int(m[1]), int(m[2]), int(m[3])), m[4]
            dazu(d, z, titel + (" – " + j["notiz"][:90] if j.get("notiz") else ""), "Antwort offen" if typ == "mail" else "Erinnerung")
        k.close()
    except Exception:
        pass
    # 4) Wiki: offene-punkte → „Nächste Termine“
    for w in wiki_termine():
        dazu(w["d"], None, w["text"], "Wiki", bis=w["bis"])
    E.sort(key=lambda e: (e["d"] or date.max, e["z"] or "99"))
    return E, stand

def zeitraum(frage, heute, standard=30):
    f = frage.lower()
    def tag(n): return heute + timedelta(days=n)
    if "übermorgen" in f: return tag(2), tag(2), "übermorgen (" + WTL[tag(2).weekday()] + ")"
    if re.search(r"\bmorgen\b", f): return tag(1), tag(1), "morgen (" + WTL[tag(1).weekday()] + ")"
    if re.search(r"\bheute\b|\bjetzt\b", f): return heute, heute, "heute"
    if "wochenende" in f:
        sa = tag((5 - heute.weekday()) % 7); return sa, sa + timedelta(days=1), "am Wochenende"
    wt = re.search(r"\b(montag|dienstag|mittwoch|donnerstag|freitag|samstag|sonnabend|sonntag)s?\b", f)   # „Was steht am Mittwoch an?“ (Claude 17.11.2026)
    if wt:
        nr = ["montag", "dienstag", "mittwoch", "donnerstag", "freitag", "samstag", "sonntag"].index(wt[1].replace("sonnabend", "samstag"))
        ab = (nr - heute.weekday()) % 7
        if re.search(r"(nächste|kommende|übernächste)[nr]? \w*" + wt[1], f) and ab == 0: ab = 7
        if "übernächste" in f: ab += 7
        d = tag(ab); return d, d, f"am {WTL[nr]} ({d:%d.%m.})"
    if re.search(r"(nächste|kommende)[nr]? woche", f):
        mo = tag(7 - heute.weekday()); return mo, mo + timedelta(days=6), "nächste Woche"
    if "woche" in f: return heute, tag(6 - heute.weekday()), "diese Woche"
    for name, nr in MONATE.items():
        if re.search(r"\b" + name + r"\b", f):
            j = heute.year if nr >= heute.month else heute.year + 1
            a = date(j, nr, 1); e = (date(j + (nr == 12), nr % 12 + 1, 1) - timedelta(days=1))
            return max(a, heute), e, "im " + name.capitalize()
    if re.search(r"(nächste|kommende)[nr]? monat", f):
        a = date(heute.year + (heute.month == 12), heute.month % 12 + 1, 1)
        return a, date(a.year + (a.month == 12), a.month % 12 + 1, 1) - timedelta(days=1), "nächsten Monat"
    if "monat" in f:
        return heute, date(heute.year + (heute.month == 12), heute.month % 12 + 1, 1) - timedelta(days=1), "diesen Monat"
    m = re.search(r"nächsten (\d+) tage", f)
    if m: return heute, tag(int(m[1])), f"in den nächsten {m[1]} Tagen"
    if "jahr" in f: return heute, date(heute.year, 12, 31), "bis Jahresende"
    return heute, tag(standard), f"in den nächsten {standard} Tagen"

def _zeile(e, heute):
    if e["d"]:
        d = e["d"]; wann = f"{WT[d.weekday()]} {d:%d.%m.}" + (f"{d:%Y}" if d.year != heute.year else "")
        if d == heute: wann = "heute"
        elif d == heute + timedelta(days=1): wann = "morgen"
        if e["z"]: wann += f", {e['z']} Uhr"
    else:
        wann = e.get("bis") or "ohne Datum"
    return f"• {wann} – {e['text']}" + (f" ({e['art']})" if e["art"] not in ("Kalender",) else "")

def _stand(stand):
    if not stand: return ""
    alt = (datetime.now() - datetime.fromtimestamp(stand)).total_seconds() / 3600
    return f"\n\nKalender-Stand: {datetime.fromtimestamp(stand):%d.%m. %H:%M} Uhr" + (" (älter – der iMac war länger aus)" if alt > 6 else "")

def absicht(frage):
    f = frage.lower()
    if re.search(r"anliegen|offene[nrs]? (punkte|sachen|vorgänge|aufgaben|enden|themen)|was ist (denn |noch |alles |gerade )*offen|to-?dos?\b|\baufgaben\b|was muss ich|zu erledigen|erledigen muss|was steht (noch )?aus|was liegt an|was ist (\w+ ){0,2}(wichtig|dringend)|was (soll|sollte) ich (heute|morgen|jetzt|als erstes)", f):
        return "anliegen"
    if re.search(r"\b(termine?n?|kalender|verabredung\w*|feiertage?)\b", f) and re.search(r"\b(welche\w*|was|meine\w*|habe ich|hab ich|stehen|steht|gibt es|zeig\w*|nenn\w*|liste|nächste\w*|wann ist mein nächster)\b", f):
        return "termine"
    if re.search(r"was (steht|ist|liegt|habe ich|hab ich|mache ich)\b.*\b(an|geplant|los|vor)\b", f) and re.search(r"heute|morgen|woche|wochenende|monat|tage|montag|dienstag|mittwoch|donnerstag|freitag|samstag|sonnabend|sonntag", f):
        return "termine"
    return None

def antwort_termine(frage):
    heute = date.today(); von, bis, label = zeitraum(frage, heute)
    E, stand = sammeln()
    imr = [e for e in E if e["d"] and von <= e["d"] <= bis and e["art"] != "Wiki"]
    haupt = [e for e in imr if e["art"] != "Feiertag"]; feier = [e for e in imr if e["art"] == "Feiertag"]
    if "feiertag" in frage.lower(): haupt, feier = feier, []
    aus = []
    if haupt:
        aus.append(f"Deine Termine {label}:" if len(haupt) > 1 else f"{label[0].upper() + label[1:]} hast du einen Termin:")
        aus += [_zeile(e, heute) for e in haupt[:25]]
    else:
        aus.append(f"{label[0].upper() + label[1:]} steht nichts im Kalender.")
        nxt = [e for e in E if e["d"] and e["d"] > bis and e["art"] not in ("Feiertag", "Wiki")]
        if nxt: aus.append("Der nächste Termin danach:\n" + _zeile(nxt[0], heute))
    if feier: aus.append("Feiertage: " + ", ".join(f"{WT[e['d'].weekday()]} {e['d']:%d.%m.} {e['text']}" for e in feier[:6]))
    ueber = [e for e in E if e["d"] and e["d"] < heute and e["art"] in ("Erinnerung", "Frist", "Mail-Termin", "Antwort offen")]
    if ueber: aus.append("Noch offen von früher:\n" + "\n".join(_zeile(e, heute) for e in ueber[:5]))
    return "\n".join(aus) + _stand(stand)

def antwort_anliegen(frage):
    heute = date.today(); von, bis, label = zeitraum(frage, heute, standard=14)
    E, stand = sammeln()
    E = [e for e in E if e["art"] != "Feiertag"]
    ueber = [e for e in E if e["d"] and e["d"] < heute and e["d"] >= heute - timedelta(days=45)]
    jetzt = [e for e in E if e["d"] and von <= e["d"] <= bis]
    ohne = [e for e in E if not e["d"] and e["art"] != "Wiki"]
    spaeter = [e for e in E if e["d"] and e["d"] > bis][:6]
    aus = ["Das ist gerade offen:"]
    if ueber: aus += ["", "Überfällig / noch nicht abgehakt:"] + [_zeile(e, heute) for e in ueber[:8]]
    if jetzt: aus += ["", f"Fällig {label}:"] + [_zeile(e, heute) for e in jetzt[:12]]
    if ohne: aus += ["", "Wartet auf dich (ohne Datum):"] + [_zeile(e, heute).replace("• ohne Datum – ", "• ") for e in ohne[:8]]
    if spaeter: aus += ["", "Danach:"] + [_zeile(e, heute) for e in spaeter]
    if len(aus) == 1: aus = ["Im Moment ist nichts offen – weder im Kalender, in TKMail, bei den Karten noch auf der Wiki-Seite offene-punkte."]
    aus += ["", "Einträge mit „(Wiki)“ stammen von der Seite [[offene-punkte]]. Für Einzelheiten frag z. B. „Was ist offen bei der Steuer?“"]
    return "\n".join(aus) + _stand(stand)

def antwort(art, frage):
    return antwort_termine(frage) if art == "termine" else antwort_anliegen(frage)

def kontext(frage, maxn=6):
    """Passende Termine/Fristen als kleiner Zusatz für das Sprachmodell."""
    w = {t for t in re.findall(r"[a-zäöüß0-9]{4,}", frage.lower()) if t not in STOPP}
    if not w: return ""
    heute = date.today(); E, _ = sammeln(); tr = []
    for e in E:
        if e["art"] == "Feiertag" and "feiertag" not in frage.lower(): continue
        if e["d"] and e["d"] < heute - timedelta(days=30): continue
        et = set(re.findall(r"[a-zäöüß0-9]{3,}", e["text"].lower()))
        if any(a.startswith(b[:5]) or b.startswith(a[:5]) for a in w for b in et if len(b) >= 4):
            tr.append(_zeile(e, heute))
    return ("TERMINE UND FRISTEN (aktuell aus Kalender, TKMail, Karten):\n" + "\n".join(tr[:maxn])) if tr else ""

if __name__ == "__main__":
    f = " ".join(sys.argv[1:]) or "Welche Termine habe ich?"
    a = absicht(f); print("Absicht:", a); print(antwort(a, f) if a else kontext(f) or "(kein Live-Treffer)")
