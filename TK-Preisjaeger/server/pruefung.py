#!/usr/bin/env python3
# TK Preisjäger – Prüfung der Produkt-Erkennung ohne Internet. Soll: alle Zeilen „ok“. Claude 26.11.2026
import sys

import kern

# (Suchtext, Titel, erwartet: True = passt / Grund)
FAELLE = [
    ("iphone 13 128gb", "Apple iPhone 13 Midnight – 128 GB – Top Zustand – 100 % Akku", True),
    ("iphone 13 128gb", "iPhone13 128GB blau", True),
    ("iphone 13 128gb", "Apple iPhone 13 Pro 128GB Graphit", "ausfuehrung"),
    ("iphone 13 128gb", "iPhone 13 mini 128GB Grün", "ausfuehrung"),
    ("iphone 13 128gb", "iPhone 13 Pro Max - 128GB - 100% Kapazität", "ausfuehrung"),
    ("iphone 13 128gb", "Apple iPhone 13 256GB", "fehlt"),
    ("iphone 13 128gb", "iPhone 130 128gb", "fehlt"),
    ("iphone 13 128gb", "Hülle für iPhone 13 128GB", "zubehoer"),
    ("iphone 13 128gb", "Panzerglas iPhone 13 128gb 2 Stück", "zubehoer"),
    ("iphone 13 128gb", "Apple iPhone 13 - 128GB - Polarstern - inkl. Silikon & Schutzglas - Sehr Gut", True),
    ("iphone 13 128gb", "iPhone 13 128GB mit Hülle und Ladekabel", True),
    ("iphone 13 128gb", "Suche iPhone 13 128GB", "gesuch"),
    ("iphone 13 128gb", "✅ ANKAUF ✅ Samsung Galaxy S25 iPhone 13 128GB 256GB", "gesuch"),
    ("iphone 13 128gb", "Nur OVP iPhone 13 128GB Leerkarton", "leer"),
    ("iphone 13", "Apple iPhone 13 256GB Rosé", True),
    ("iphone 13 pro", "Apple iPhone 13 Pro 256GB", True),
    ("iphone 13 pro", "iPhone 13 Pro Max 256GB", "ausfuehrung"),
    ("playstation 5", "Sony PlayStation 5 Digital Edition", "ausfuehrung"),
    ("playstation 5", "Sony PlayStation 5 Konsole mit Controller", True),
    ("playstation 5", "Controller für PlayStation 5", "zubehoer"),
    ("sony wh-1000xm5", "Sony WH-1000XM5 Kopfhörer schwarz", True),
    ("sony wh-1000xm5", "Sony WH 1000 XM5 silber", True),
    ("sony wh-1000xm5", "Sony WH-1000XM4 Kopfhörer", "fehlt"),
    ("sony wh-1000xm5", "Ohrpolster für Sony WH-1000XM5", "zubehoer"),
    ("galaxy s24", "Samsung Galaxy S24 Ultra 256GB", "ausfuehrung"),
    ("galaxy s24", "Samsung Galaxy S24 128GB Onyx Black", True),
    ("galaxy s24", "Samsung Galaxy S24 FE", "ausfuehrung"),
    ("macbook air m2", "Apple MacBook Air M2 13 Zoll 256GB", True),
    ("macbook air m2", "MacBook Pro M2 13 Zoll", "fehlt"),
    ("dyson v11", "Dyson V11 Akku Staubsauger", True),
    ("dyson v11", "Akku für Dyson V11", "zubehoer"),
    ("iphone 13 128gb", "*128GB*Apple iPhone 12 kein x xs 11 13 14 15 16 pro max plus", "fehlt"),
    ("iphone 13", "iPhone 13 Hülle Silikon schwarz", "zubehoer"),
    ("dyson v11", "Dyson V11 absolute Zubehör", "zubehoer"),
    ("dyson v11", "Dyson Zubehör für V10 und V15 (evtl. V7, V8, V11)", "fehlt"),
    ("dyson v11", "pezzi di ricambio per dyson V11 originali", "zubehoer"),
    ("dyson v11", "Dyson Staubsauger V11 Absolute", True),
    ("imac m3", "Apple iMac 24 Zoll, Okt.024, M3 Chip, 8-Core CPU, 512 GB SSD !!!", True),
    ("imac m3", "Kult-iMac 24 in edlem Violett – M3 Power & 16 GB RAM für Profis!", True),
    ("imac m3", "Apple iMac 24 Zoll Netzteil 143W A2290 M1 M3 M4 Kabel Netzwerk", "zubehoer"),
    ("imac m3", "Apple iMac 27 Retina 5K (Late 2015) – i7 4 GHz, 40 GB RAM, R9 M3", "fehlt"),
    ("mac mini m4", "APPLE MacMini M4 / 16 GB RAM /256GB SSD", True),
    ("mac mini m4", "Apple Mac mini M6 2026", "fehlt"),
    ("mac mini m4", "Per Apple Mac mini M4 / M5 / M6 Supporto da sotto scrivania", "zubehoer"),
    ("mac mini m4", "Apple Mac mini M4 Pro, 12-Core CPU, 24GB RAM, 512GB", "ausfuehrung"),
    ("mac mini m4", "Apple Mac mini M4 2024 16GB 256GB silber", True),
    ("osmose wasserspender", "AQMOS DrinKing Pro Osmose-Wasserspender – still, sprudelnd, kalt & heiß", True),
    ("osmose wasserspender", "Philips Water 7500 Umkehrosmose-Wasserspender: heißes & gekühltes Wasser", True),
    ("osmose wasserspender", "Ersatzfilter für Osmose Wasserspender", "zubehoer"),
    ("iphone 13", "iPhonehülle 13 schwarz", "fehlt"),
    ("aqmos drinking pro", "Aqmos Ersatzfilter für DrinKing Pro – 4-in-1 Umkehrosmose", "zubehoer"),
    ("aqmos drinking pro", "Aqmos DrinKing Pro / Ihr Premium-Auftisch Wasserspender / TOP!!!", True),
    ("aqmos drinking pro osmose", "AQMOS DrinKing Pro Osmose-Wasserspender – still, sprudelnd, kalt & heiß", True),
    ("playstation 5", "Crucial P310 2TB PCIe Gen4 NVMe M.2 SSD PS5 Playstation 5", "fehlt"),
    ("playstation 5", "Verkaufe meine neuwertige Sony PlayStation 5 mit OVP", True),
    ("lego 42115", "Lego Technic Lamborghini Sian 18+ Sián Lego 42115 Auto mit OVP", True),
    ("sony wh-1000xm5", "wh-1000xm5 Sony Kopfhörer", True),
    ("iphone 13 128gb", "iPhone 13 in Blau, sehr guter Zustand, mit Rechnung, 128GB", True),
    ("playstation 5", "Sony Playstation 5 Portal Remote Player", "ausfuehrung"),
    ("playstation 5", "PlayStation 5 Controller weiß", "zubehoer"),
    ("sony wh-1000xm5", "Sony WH-1000XM5 Hardcase schwarz", "zubehoer"),
    ("sony wh-1000xm5", "Sony WH-1000XM5 replica", "nachbau"),
    ("sony wh-1000xm5", "Sony WH - 1000XM 5 Ohrpolster in Schwarz", "zubehoer"),
    ("iphone 13 128gb", "iPhone 13 128GB, Hülle, Ladekabel, OVP", True),
]
DEFEKT = [
    ("iPhone 13 128GB defekt", "", True),
    ("iPhone 13 128GB", "Display gebrochen, für Bastler", True),
    ("iPhone 13 128GB", "Voll funktionsfähig, kein Defekt, keine Kratzer", False),
    ("iPhone 13 128GB iCloud gesperrt", "", True),
    ("iPhone 13 128GB Top Zustand", "Das Display hat nur leichte Kratzer", False),
    ("iPhone 13, 128 GB, beschädigter Bildschirm", "", True),
    ("DYSON V11 Total Clean, incl. Zubehör, TEILDEFEKT, TOP-Zustand!", "", True),
    ("iPhone 13 128GB , Batteria 100%, Da riparare", "", True),
]

fehler = 0
for anfrage, titel, soll in FAELLE:
    ok, grund = kern.pruefe(anfrage, titel)
    ist = True if ok else grund.split(":")[0]
    gut = ist == soll
    fehler += not gut
    print("%-6s %-18s | %-70s -> %s%s" % ("ok" if gut else "FEHLER", anfrage, titel[:70], ist, "" if gut else "  (erwartet %s)" % soll))
for titel, text, soll in DEFEKT:
    ist = kern.ist_defekt(titel, text)
    gut = ist == soll
    fehler += not gut
    print("%-6s defekt? %-60s -> %s" % ("ok" if gut else "FEHLER", (titel + " / " + text)[:60], ist))
# Ausreißer
liste = [{"quelle": "T", "titel": "iPhone 13 128GB", "preis": p, "url": str(i)} for i, p in enumerate([250, 260, 270, 280, 300, 20, 310, 120])]
e = kern.bewerten("iphone 13 128gb", liste)
gut = len(e["auffaellig"]) == 2 and e["treffer"][0]["preis"] == 250
fehler += not gut
print("%-6s Ausreißer: bester %s, auffällig %s" % ("ok" if gut else "FEHLER", e["treffer"][0]["preis"], [a["preis"] for a in e["auffaellig"]]))
# fast passend: ein Beschreibungswort fehlt
e = kern.bewerten("aqmos drinking pro osmose", [{"quelle": "T", "titel": "Aqmos DrinKing Pro / Ihr Premium-Auftisch Wasserspender", "preis": 899, "url": "a"},
                                                {"quelle": "T", "titel": "Aqmos Wasserspender DrinKing Schwarz", "preis": 658, "url": "b"}])
gut = len(e["aehnlich"]) == 1 and e["aehnlich"][0]["fehlt"] == "osmose" and not e["treffer"]
fehler += not gut
print("%-6s fast passend: %s" % ("ok" if gut else "FEHLER", [(a["preis"], a.get("fehlt")) for a in e["aehnlich"]]))
gut = kern.kuerzungen("iphone 13 128gb") == [] and kern.kuerzungen("sony wh-1000xm5") == []
fehler += not gut
print("%-6s keine Kürzung bei Modellnummern" % ("ok" if gut else "FEHLER"))
# Freitext
v = kern.verstehen("Ich suche einen Osmose Wasserspender mit Sprudel und Heißwasser bis 900 €, gebraucht, ohne Festanschluss")
gut = v["produkt"] == "osmose wasserspender" and v["wuensche"] == ["sprudel", "heißwasser"] and v["max"] == 900 and v["zustand"] == ["gebraucht"] and v["ohne"] == ["festanschluss"]
fehler += not gut
print("%-6s Freitext: %s" % ("ok" if gut else "FEHLER", v))
v = kern.verstehen("iPhone 13 128GB")
gut = v["produkt"] == "iPhone 13 128GB" and not v["wuensche"] and v["max"] is None
fehler += not gut
print("%-6s Produktname bleibt unverändert: %s" % ("ok" if gut else "FEHLER", v["produkt"]))
v = kern.verstehen("Dyson V11 unter 200 euro")
gut = v["produkt"] == "dyson v11" and v["max"] == 200
fehler += not gut
print("%-6s Preisgrenze: %s" % ("ok" if gut else "FEHLER", v))
e = kern.wuensche_anwenden(kern.bewerten("wasserspender", [
    {"quelle": "T", "titel": "Wasserspender still, sprudelnd, kalt & heiß", "preis": 700, "url": "a"},
    {"quelle": "T", "titel": "Wasserspender Edelstahl", "preis": 300, "url": "b"},
    {"quelle": "T", "titel": "Wasserspender mit Sprudel und Heißwasser", "preis": 950, "url": "c"}]),
    {"produkt": "wasserspender", "wuensche": ["sprudel", "heißwasser"], "ohne": [], "max": 900, "min": None, "zustand": []})
gut = [a["url"] for a in e["treffer"]] == ["a"] and [a["url"] for a in e["aehnlich"]] == ["b"]
fehler += not gut
print("%-6s Wünsche anwenden: Treffer %s, fast %s" % ("ok" if gut else "FEHLER", [a["url"] for a in e["treffer"]], [(a["url"], a["wunsch_offen"]) for a in e["aehnlich"]]))
# Betrug
for text, soll in [("Bitte per PayPal Freunde und Familie zahlen", True), ("Schreib mir auf WhatsApp 0176 12345678", True), ("Ich bin im Ausland, ein Kurier holt das Geld", True),
                   ("Klicken Sie auf den Link zur Zahlung", True), ("Ok 250 passt, wann kannst du kommen? Barzahlung bei Abholung", False), ("iPhone 13 128GB top Zustand, Abholung in Dortmund", False)]:
    gut = bool(kern.betrug(text)) == soll
    fehler += not gut
    print("%-6s Betrug? %-58s -> %s" % ("ok" if gut else "FEHLER", text[:58], kern.betrug(text)[:1]))
# Nachprüfung auf der Angebotsseite (Händler führt nur die Modellnummer im Titel)
seite = "Aqmos WSDK-BLACK-PRO Günstigster Preis 789,00 € Zum Shop AQMOS DrinKing Pro Osmose-Wasserspender - still, sprudelnd, kalt & heiß 879,12 €"
z, st = kern.fenster("aqmos drinking pro osmose", seite)
e = kern.bewerten("aqmos drinking pro osmose", [{"quelle": "idealo", "titel": "Aqmos WSDK-BLACK-PRO", "pruef_titel": st, "preis": 789, "url": "x"}])
gut = z == 1 and len(e["treffer"]) == 1 and kern.fenster("aqmos drinking pro osmose", "Aqmos Wasserspender DrinKing Schwarz 658 €")[0] == 0
fehler += not gut
print("%-6s Nachprüfung Angebotsseite: %s Stelle(n), „%s“" % ("ok" if gut else "FEHLER", z, st[:50]))
gut = kern.fenster("osmofresh fusion pro", "Osmofresh Quella Pro Black 379,00 € Zum Shop … Osmofresh Fusion Pro ab 1.181,50 € 5 Angebote Jimmy Wasserfilter ab 99 €")[0] == 0
fehler += not gut
print("%-6s Verweis „Name ab … €“ zählt nicht als Bestätigung" % ("ok" if gut else "FEHLER"))
print("\nERGEBNIS: %s" % ("alles in Ordnung" if not fehler else "%d FEHLER" % fehler))
sys.exit(1 if fehler else 0)
