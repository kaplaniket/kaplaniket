# TK Preisjäger

Produkt eingeben – gesucht wird **genau dieses Produkt**, neu und gebraucht, der günstigste Preis steht oben. Fassung 1.0 (26.11.2026).

## So findet er das richtige Produkt

1. **Alle Suchwörter müssen im Titel stehen**, Schreibweisen werden angeglichen (`128 GB` = `128gb`, `WH-1000XM5` = `WH 1000 XM5`). Eine Modellnummer muss direkt hinter dem Namen stehen – „iPhone 12 … 11 13 14“ (Stichwort-Spam) zählt nicht als iPhone 13.
2. **Andere Ausführung raus:** Steht hinter dem Namen „Pro“, „Mini“, „Max“, „Ultra“, „Slim“, „Digital“ … und das Wort fehlt im Suchtext, ist es ein anderes Gerät. Ebenso eine andere Speichergröße als die gesuchte. (Abschaltbar: „Nur genau diese Ausführung“.)
3. **Zubehör raus:** „Hülle für …“, „… Panzerglas“, Ersatzteile, Leerkartons, Nachbauten. „iPhone 13 mit Hülle und Ladekabel“ bleibt drin.
4. **Gesuche, Ankauf, Tausch raus.**
5. **Defekte getrennt:** defekt, Bastler, Displaybruch, iCloud-Sperre … stehen in einer eigenen Liste, nicht beim besten Preis.
6. **Üblicher Preis:** Aus dem ersten Durchgang wird der mittlere Preis bestimmt. Alles **unter der Hälfte** davon ist fast immer Zubehör, Lockpreis oder Betrug und steht getrennt unter „genau prüfen“.
7. **Zweiter Durchgang:** Auf Kleinanzeigen und Vinted werden dann gezielt die billigsten Angebote *ab* dieser Grenze geholt (nach Preis sortiert) – so stehen die günstigsten echten Angebote oben, ohne dass man sich durch Zubehör blättern muss.

## Quellen

Abgefragt: Kleinanzeigen, Vinted, Shpock, Hood, rebuy, Amazon, idealo, MediaMarkt, Saturn.

Nur als fertiger Suchlink (diese Seiten sperren automatische Abfragen; das wird nicht umgangen): eBay, Geizhals, Back Market, refurbed, Google Shopping.

## Ordner

| Ordner | Inhalt |
|---|---|
| `server/` | `server.py` (Webserver, Port 8815), `quellen.py` (Abruf der Seiten), `kern.py` (Produkt-Erkennung), `index.html` (Oberfläche), `pruefung.py` (Prüfung ohne Internet) |
| `mac/` | Mac-Programm (WebKit-Fenster, Intel + Apple-Chips, ab macOS 11): `main.swift`, `bauen.sh`, `einbauen.sh`, `symbol.png` |

## Starten und prüfen

```bash
python3 server/pruefung.py        # Soll: „alles in Ordnung“
python3 server/server.py          # http://localhost:8815
```

Braucht Python 3 mit `beautifulsoup4` und `lxml`. Die Merkliste liegt in `server/daten/` (nicht im Repo).

Mac-Programm: im Ordner `mac/` `bauen.sh`, dann `einbauen.sh "http://<Adresse des Servers>:8815"`.

© 2026 Tekin Kaplan
