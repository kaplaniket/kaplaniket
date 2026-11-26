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
    ("playstation 5", "Sony Playstation 5 Portal Remote Player", "ausfuehrung"),
    ("playstation 5", "PlayStation 5 Controller weiß", "zubehoer"),
    ("sony wh-1000xm5", "Sony WH-1000XM5 Hardcase schwarz", "zubehoer"),
    ("sony wh-1000xm5", "Cuffie replica delle Sony WH-1000XM5.", "nachbau"),
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
print("\nERGEBNIS: %s" % ("alles in Ordnung" if not fehler else "%d FEHLER" % fehler))
sys.exit(1 if fehler else 0)
