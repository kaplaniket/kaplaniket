# PiAgent – lokaler KI-Agent für den Raspberry Pi

Ein KI-Assistent, der **komplett lokal** auf deinem Raspberry Pi läuft – ohne Cloud,
ohne API-Schlüssel. Das Sprachmodell läuft über [Ollama](https://ollama.com),
der Agent selbst ist ein einzelnes Python-Skript ohne Abhängigkeiten.

Der Agent kann Werkzeuge benutzen:

| Werkzeug      | Was es tut                                                  | Rückfrage |
|---------------|-------------------------------------------------------------|-----------|
| `system_info` | CPU-Temperatur, RAM, Speicher, Last, Uptime, Throttling     | nein      |
| `list_dir`    | Verzeichnis auflisten                                       | nein      |
| `read_file`   | Datei lesen                                                 | nein      |
| `write_file`  | Datei schreiben                                             | **ja**    |
| `run_shell`   | Shell-Befehl ausführen                                      | **ja**    |

## Voraussetzungen

- Raspberry Pi 4 oder 5 (empfohlen: 8 GB RAM)
- **Raspberry Pi OS 64-bit**
- Internet nur für die Installation (Ollama + Modell herunterladen)

## Installation

Ordner `PiAgent` auf den Pi kopieren (z. B. `git clone` oder `scp`), dann:

```bash
cd PiAgent
bash install_pi.sh
```

Das Skript installiert Ollama, wählt ein Modell passend zum RAM, lädt es herunter
und richtet den Befehl `pi-agent` sowie die Web-Oberfläche als Dienst ein.

| RAM   | Modell          |
|-------|-----------------|
| 8 GB  | `qwen2.5:3b`    |
| 4 GB  | `qwen2.5:1.5b`  |
| 2 GB  | `qwen2.5:0.5b`  |

Anderes Modell: `bash install_pi.sh llama3.2:3b` (das Modell muss Tool-Calling unterstützen).

## Benutzung

**Terminal:**

```bash
pi-agent
Du: Wie warm ist mein Pi und wie viel Speicher ist noch frei?
Du: Zeig mir die letzten Fehler im Systemlog
⚠ run_shell: journalctl -p err -n 20 – ausführen? [j/N] j
```

Einzelne Frage: `pi-agent -p "Wie lange läuft der Pi schon?"`
Befehle: `/neu` = neuer Chat, `/ende` = beenden.

**Browser / Handy:** `http://<IP-des-Pi>:8765`

Im Browser gibt es keine Rückfrage, deshalb sind `run_shell` und `write_file` dort
standardmäßig **gesperrt**. Freischalten in `~/pi-agent/pi-agent.env`:

```
PI_AGENT_ALLOW_SHELL=1
```

danach `sudo systemctl restart pi-agent`. ⚠️ Dann kann jeder im Netzwerk, der die
Seite erreicht, Befehle auf dem Pi ausführen – nur im vertrauenswürdigen Heimnetz nutzen.
Soll die Seite nur lokal erreichbar sein: `PI_AGENT_HOST=127.0.0.1`.

## Einstellungen (`~/pi-agent/pi-agent.env`)

| Variable               | Standard                 | Bedeutung                              |
|------------------------|--------------------------|----------------------------------------|
| `PI_AGENT_MODEL`       | je nach RAM              | Ollama-Modell                          |
| `PI_AGENT_HOST`        | `0.0.0.0`                | Adresse der Web-Oberfläche             |
| `PI_AGENT_PORT`        | `8765`                   | Port der Web-Oberfläche                |
| `PI_AGENT_ALLOW_SHELL` | `0`                      | Shell/Schreiben im Web erlauben        |
| `PI_AGENT_WORKDIR`     | Home-Verzeichnis         | Arbeitsverzeichnis für relative Pfade  |
| `PI_AGENT_MAX_STEPS`   | `8`                      | Max. Werkzeug-Schritte pro Frage       |

## Eigene Werkzeuge hinzufügen

In `agent.py` eine Funktion schreiben und in `TOOLS` eintragen, z. B. für GPIO:

```python
def tool_led(on: bool) -> str:
    subprocess.run(["pinctrl", "set", "17", "op", "dh" if on else "dl"])
    return "LED an" if on else "LED aus"

TOOLS["led"] = (tool_led, "Schaltet die LED an GPIO 17.",
                {"on": {"type": "boolean", "description": "true = an"}})
```

## Probleme

- `Ollama ist nicht erreichbar` → `sudo systemctl start ollama`
- `Modell fehlt` → `ollama pull <modell>`
- Antworten sehr langsam → kleineres Modell wählen, Pi gut kühlen
- Logs der Web-Oberfläche → `journalctl -u pi-agent -f`
