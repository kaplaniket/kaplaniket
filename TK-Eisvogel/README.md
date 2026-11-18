# TK Eisvogel

„Dein Gedächtnis. Deine KI. Eine App.“ – Fassung 3.0 (17.11.2026), die zusammengelegte App aus **TK KI** und **TK Vogel**.

Persönliche KI, die zu Hause auf dem HP (`tk-ki-hp`) läuft und Fragen aus dem eigenen Obsidian-Wiki, der Dokumentenablage und dem Mail-/Chat-Archiv beantwortet. Wahlweise mit DeepSeek („TK Vogel – schnell“) oder ganz ohne fremde KI („Nur lokal – privat“, Ollama mit qwen3:4b).

## Ordner

| Ordner | Inhalt | Auf dem HP |
|---|---|---|
| `server/` | Webserver, Oberfläche, Wissensindex, Training, Prüfungen | `/media/tekin/Disk2/TK-KI/app/` |
| `mac/` | Mac-Programm (WebKit-Fenster), `bauen.sh`, `einbauen.sh` | `~/Agent Arbeit/Apps/TK Eisvogel/Mac/` |
| `server/eisvogel-cli` | Terminal-Befehl `eisvogel "Frage"` | `~/bin/eisvogel` |

## Wichtige Dateien (`server/`)

| Datei | Aufgabe |
|---|---|
| `server.py` | Webserver (Port 8811), Weg einer Frage, Schutz vor fremden Seiten |
| `seiten.py`, `app.js`, `zusatz.css`, `eisvogel-basis.json` | Oberfläche, Einstellungen, Rechtstexte |
| `marke.json` | Name, Leitsatz, Fassung, Inhaber |
| `indexer.py` | Wissensindex |
| `lokal.py` | Antworten ohne fremde KI |
| `verlauf.py` | frühere Fragen mit der damaligen Antwort |
| `live.py`, `person.py`, `dokumente.py`, `antwortspeicher.py` | Termine, Personen-Akte, Dokumente lesen, Antwortspeicher |
| `training.py`, `lernen.sh`, `lernpruefung.py` | Dauertraining, Lernen, nächtliche Lernprüfung |
| `pruefung.py`, `lokaltest.py`, `test.py`, `sichtpruefung.py` | Prüfungen |

## Persönliche Daten

Das Repo ist öffentlich. Deshalb steht hier **nichts Persönliches**. Auf dem HP liegt es in `server/privat/` (per `.gitignore` ausgeschlossen):

- `lokaltest.json`, `pruefung.json`, `pruefung-mehr.json`, `test.json`: Prüffragen mit den echten Antworten
- `synonyme.json`, `dokumente-synonyme.json`: Namen der Familie, Kennzeichen
- `marke.json`: volle Anschrift fürs Impressum

Fehlen diese Dateien, laufen die Prüfungen mit Beispielfragen, und der Server arbeitet ohne Familien-Synonyme. `lernfragen.jsonl` bleibt ebenfalls auf dem HP (Muster: `lernfragen.beispiel.jsonl`).

Netz-Adressen kommen aus der Umgebung statt aus dem Code:

- Server: `EISVOGEL_ADRESSEN` (z. B. Tailnet-IP des HP), `EISVOGEL_HOSTS` (weitere erlaubte Hostnamen), `EISVOGEL_PORT`
- Mac: `defaults write de.tekin.tkki adressen "http://<Tailnet-IP>:8811,http://<Heimnetz-IP>:8811"`

## Starten und prüfen (am HP)

```bash
systemctl --user restart tk-ki
python3 /media/tekin/Disk2/TK-KI/app/pruefung.py      # Soll: 8/8
python3 /media/tekin/Disk2/TK-KI/app/lokaltest.py     # Genauigkeit „Nur lokal“
```

Mac-Programm: im Ordner `mac/` zuerst `bauen.sh` ausführen, dann am iMac `einbauen.sh`.

Ausführliche Beschreibung im Wiki: `~/Obsidian/06 Wiki/themen/tk-eisvogel.md`.
