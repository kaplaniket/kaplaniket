# PiAgent – Claude Code als Agent auf dem Raspberry Pi

Macht deinen Raspberry Pi zu einem Claude-Code-Agenten: Claude läuft direkt auf dem Pi,
kann dort Befehle ausführen, Dateien bearbeiten, Dienste prüfen und Projekte programmieren –
im Terminal oder ferngesteuert über die Claude-App auf dem Handy (Remote Control).

Das Sprachmodell läuft in der Cloud von Anthropic, alle Befehle und Dateien bleiben auf dem Pi.

## Voraussetzungen

- Raspberry Pi 4 oder 5 (auch Pi 3/Zero 2 W mit 64-bit-OS möglich)
- **Raspberry Pi OS 64-bit**, Internetverbindung
- Claude-Konto (Pro/Max) oder ein Anthropic-API-Schlüssel

## Installation

Ordner `PiAgent` auf den Pi kopieren (z. B. `git clone` oder `scp`), dann:

```bash
cd PiAgent
bash install_pi.sh
```

Das Skript installiert Claude Code mit dem offiziellen Installer, legt das
Arbeitsverzeichnis `~/pi-agent` an und richtet die Befehle `pi-agent` und
`pi-agent-remote` ein.

Danach einmal anmelden:

```bash
pi-agent
```

Beim ersten Start erscheint ein Login-Link. Alternativ mit API-Schlüssel:
`export ANTHROPIC_API_KEY=sk-ant-...` in `~/.bashrc` eintragen.

## Benutzung

**Im Terminal (z. B. per SSH):**

```bash
pi-agent
> Wie warm ist mein Pi und wird er gedrosselt?
> Zeig mir die Fehler im Systemlog seit heute früh
> Schreib mir ein Python-Skript, das die LED an GPIO 17 blinken lässt
```

Einzelne Frage ohne Chat: `pi-agent -p "Wie viel Speicher ist noch frei?"`

**Vom Handy / Browser (Remote Control):**

```bash
pi-agent-remote
```

Startet `claude remote-control` im Hintergrund (in `tmux`). Die Sitzung erscheint
in der Claude-App bzw. unter claude.ai/code – so steuerst du den Pi von überall.
Ansehen: `tmux attach -t pi-agent`, verlassen mit `Strg+B`, dann `D`.

## Was ist dabei

| Datei                                 | Zweck                                                      |
|---------------------------------------|------------------------------------------------------------|
| `~/pi-agent/CLAUDE.md`                | Kontext: Claude weiß, dass es auf einem Pi läuft, kennt `vcgencmd`, `pinctrl`, Regeln |
| `~/pi-agent/.claude/settings.json`    | Berechtigungen: harmlose Statusbefehle ohne Rückfrage, gefährliche (`dd`, `mkfs` …) gesperrt |
| `~/pi-agent/projekte/`                | Ablage für deine Skripte und Projekte                      |

Alles andere (z. B. `sudo`, `apt install`, Dateien schreiben) fragt Claude Code
vorher nach – du bestätigst jeden Schritt.

`CLAUDE.md` und `settings.json` darfst du frei anpassen, z. B. eigene Sensoren,
Pins oder Projekte beschreiben. Ein erneutes `install_pi.sh` überschreibt sie nicht.

## Probleme

- `claude: command not found` → neues Terminal öffnen oder `source ~/.bashrc`
- Login klappt ohne Bildschirm nicht → Link aus dem Terminal am Handy/PC öffnen
- Remote-Sitzung beenden → `tmux kill-session -t pi-agent`
