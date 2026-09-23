#!/usr/bin/env python3
"""PiAgent – ein lokaler KI-Agent für den Raspberry Pi.

Läuft komplett offline mit einem lokalen Sprachmodell über Ollama.
Nur Python-Standardbibliothek, keine pip-Pakete nötig.

Modi:
    python3 agent.py            # Chat im Terminal
    python3 agent.py --web      # Web-Oberfläche (Browser / Handy)
    python3 agent.py -p "..."   # Einzelne Frage, Antwort ausgeben, beenden
"""

import argparse
import datetime
import json
import os
import platform
import shutil
import subprocess
import sys
import threading
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434")
MODEL = os.environ.get("PI_AGENT_MODEL", "qwen2.5:3b")
WORKDIR = Path(os.environ.get("PI_AGENT_WORKDIR", Path.home())).expanduser()
MAX_STEPS = int(os.environ.get("PI_AGENT_MAX_STEPS", "8"))
MAX_OUTPUT = 4000  # Zeichen pro Werkzeug-Ergebnis, damit der Kontext klein bleibt

SYSTEM_PROMPT = """Du bist PiAgent, ein hilfreicher lokaler Assistent, der auf einem \
Raspberry Pi läuft. Du antwortest auf Deutsch, kurz und präzise.
Du hast Werkzeuge, um den Pi zu untersuchen und zu steuern. Nutze sie, wenn \
eine Frage den Zustand des Systems, Dateien oder Befehle betrifft, statt zu raten.
Arbeitsverzeichnis: {workdir}. Heute ist {today}."""


# --------------------------------------------------------------------------
# Werkzeuge
# --------------------------------------------------------------------------

def _truncate(text: str) -> str:
    if len(text) <= MAX_OUTPUT:
        return text
    return text[:MAX_OUTPUT] + f"\n… ({len(text) - MAX_OUTPUT} Zeichen abgeschnitten)"


def _resolve(path: str) -> Path:
    p = Path(path).expanduser()
    return p if p.is_absolute() else (WORKDIR / p)


def tool_system_info() -> str:
    info = {
        "hostname": platform.node(),
        "system": f"{platform.system()} {platform.release()} ({platform.machine()})",
        "python": platform.python_version(),
    }
    model_file = Path("/proc/device-tree/model")
    if model_file.exists():
        info["board"] = model_file.read_text(errors="ignore").strip("\x00\n ")
    temp_file = Path("/sys/class/thermal/thermal_zone0/temp")
    if temp_file.exists():
        info["cpu_temp_c"] = round(int(temp_file.read_text().strip()) / 1000, 1)
    try:
        info["load_avg"] = os.getloadavg()
    except OSError:
        pass
    meminfo = Path("/proc/meminfo")
    if meminfo.exists():
        mem = {}
        for line in meminfo.read_text().splitlines():
            key, _, val = line.partition(":")
            mem[key] = int(val.split()[0]) // 1024  # MB
        info["ram_mb"] = {"total": mem.get("MemTotal"), "available": mem.get("MemAvailable")}
    du = shutil.disk_usage("/")
    info["disk_gb"] = {"total": round(du.total / 1e9, 1), "free": round(du.free / 1e9, 1)}
    uptime = Path("/proc/uptime")
    if uptime.exists():
        info["uptime_h"] = round(float(uptime.read_text().split()[0]) / 3600, 1)
    if shutil.which("vcgencmd"):
        try:
            out = subprocess.run(["vcgencmd", "get_throttled"], capture_output=True,
                                 text=True, timeout=5).stdout.strip()
            info["throttled"] = out
        except Exception:
            pass
    return json.dumps(info, ensure_ascii=False, indent=1)


def tool_list_dir(path: str = ".") -> str:
    p = _resolve(path)
    if not p.is_dir():
        return f"Fehler: {p} ist kein Verzeichnis."
    entries = []
    for child in sorted(p.iterdir())[:200]:
        kind = "/" if child.is_dir() else ""
        entries.append(child.name + kind)
    return _truncate("\n".join(entries) or "(leer)")


def tool_read_file(path: str) -> str:
    p = _resolve(path)
    if not p.is_file():
        return f"Fehler: {p} existiert nicht."
    return _truncate(p.read_text(errors="replace"))


def tool_write_file(path: str, content: str) -> str:
    p = _resolve(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content)
    return f"{len(content)} Zeichen nach {p} geschrieben."


def tool_run_shell(command: str) -> str:
    try:
        res = subprocess.run(command, shell=True, capture_output=True, text=True,
                             timeout=60, cwd=WORKDIR)
    except subprocess.TimeoutExpired:
        return "Fehler: Zeitlimit (60 s) überschritten."
    out = res.stdout + (("\n[stderr]\n" + res.stderr) if res.stderr else "")
    return _truncate(f"[exit {res.returncode}]\n{out}".strip())


TOOLS = {
    "system_info": (tool_system_info, "Zeigt Board, CPU-Temperatur, RAM, Speicherplatz, Last und Uptime des Pi.", {}),
    "list_dir": (tool_list_dir, "Listet den Inhalt eines Verzeichnisses.",
                 {"path": {"type": "string", "description": "Pfad, relativ zum Arbeitsverzeichnis oder absolut"}}),
    "read_file": (tool_read_file, "Liest eine Textdatei.",
                  {"path": {"type": "string", "description": "Dateipfad"}}),
    "write_file": (tool_write_file, "Schreibt (überschreibt) eine Textdatei.",
                   {"path": {"type": "string", "description": "Dateipfad"},
                    "content": {"type": "string", "description": "Neuer Dateiinhalt"}}),
    "run_shell": (tool_run_shell, "Führt einen Shell-Befehl auf dem Pi aus und gibt die Ausgabe zurück.",
                  {"command": {"type": "string", "description": "Der Bash-Befehl"}}),
}

# Werkzeuge, die etwas verändern und deshalb bestätigt werden müssen
DANGEROUS = {"write_file", "run_shell"}


def tool_schemas():
    return [{
        "type": "function",
        "function": {
            "name": name,
            "description": desc,
            "parameters": {"type": "object", "properties": params, "required": list(params)},
        },
    } for name, (_, desc, params) in TOOLS.items()]


# --------------------------------------------------------------------------
# Ollama
# --------------------------------------------------------------------------

def ollama_chat(messages):
    body = json.dumps({
        "model": MODEL,
        "messages": messages,
        "tools": tool_schemas(),
        "stream": False,
        "options": {"temperature": 0.3},
    }).encode()
    req = urllib.request.Request(f"{OLLAMA_URL}/api/chat", data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=600) as resp:
        return json.loads(resp.read())["message"]


def check_ollama():
    try:
        with urllib.request.urlopen(f"{OLLAMA_URL}/api/tags", timeout=5) as resp:
            models = [m["name"] for m in json.loads(resp.read()).get("models", [])]
    except (urllib.error.URLError, OSError):
        sys.exit(f"Ollama ist unter {OLLAMA_URL} nicht erreichbar. "
                 "Starte es mit: sudo systemctl start ollama")
    if not any(m == MODEL or m.split(":")[0] == MODEL for m in models):
        sys.exit(f"Modell '{MODEL}' fehlt. Lade es mit: ollama pull {MODEL}")


# --------------------------------------------------------------------------
# Agenten-Schleife
# --------------------------------------------------------------------------

class Agent:
    def __init__(self, confirm):
        """confirm(name, args) -> bool entscheidet über gefährliche Werkzeuge."""
        self.confirm = confirm
        self.lock = threading.Lock()
        self.reset()

    def reset(self):
        self.messages = [{"role": "system", "content": SYSTEM_PROMPT.format(
            workdir=WORKDIR, today=datetime.date.today().isoformat())}]

    def ask(self, text, on_tool=None):
        with self.lock:
            self.messages.append({"role": "user", "content": text})
            for _ in range(MAX_STEPS):
                msg = ollama_chat(self.messages)
                self.messages.append(msg)
                calls = msg.get("tool_calls") or []
                if not calls:
                    return msg.get("content", "").strip()
                for call in calls:
                    name = call["function"]["name"]
                    args = call["function"].get("arguments") or {}
                    if isinstance(args, str):
                        args = json.loads(args or "{}")
                    result = self._run_tool(name, args)
                    if on_tool:
                        on_tool(name, args, result)
                    self.messages.append({"role": "tool", "tool_name": name, "content": result})
            return "(Abgebrochen: zu viele Werkzeug-Schritte.)"

    def _run_tool(self, name, args):
        if name not in TOOLS:
            return f"Fehler: unbekanntes Werkzeug '{name}'."
        if name in DANGEROUS and not self.confirm(name, args):
            return "Vom Benutzer abgelehnt."
        try:
            return TOOLS[name][0](**args)
        except Exception as exc:  # Fehler an das Modell zurückgeben statt abstürzen
            return f"Fehler: {exc}"


# --------------------------------------------------------------------------
# Terminal
# --------------------------------------------------------------------------

def run_cli(auto_yes, prompt=None):
    def confirm(name, args):
        if auto_yes:
            return True
        detail = args.get("command") or args.get("path")
        answer = input(f"\033[33m⚠ {name}: {detail} – ausführen? [j/N] \033[0m")
        return answer.strip().lower() in ("j", "ja", "y", "yes")

    def show_tool(name, args, result):
        first = result.splitlines()[0] if result else ""
        print(f"\033[2m  ↳ {name}({json.dumps(args, ensure_ascii=False)[:80]}) → {first[:80]}\033[0m")

    agent = Agent(confirm)
    if prompt:
        print(agent.ask(prompt, show_tool))
        return

    print(f"PiAgent · Modell {MODEL} · /neu = neuer Chat, /ende = beenden")
    while True:
        try:
            text = input("\n\033[36mDu:\033[0m ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not text:
            continue
        if text in ("/ende", "/exit", "/quit"):
            break
        if text in ("/neu", "/new"):
            agent.reset()
            print("Neuer Chat.")
            continue
        try:
            print(f"\033[32mPiAgent:\033[0m {agent.ask(text, show_tool)}")
        except urllib.error.URLError as exc:
            print(f"Ollama-Fehler: {exc}")


# --------------------------------------------------------------------------
# Web-Oberfläche
# --------------------------------------------------------------------------

WEB_PAGE = (Path(__file__).parent / "web.html")


def run_web(host, port, allow_shell):
    # Im Browser gibt es keine Rückfrage – gefährliche Werkzeuge nur mit expliziter Freigabe
    agent = Agent(lambda name, args: allow_shell)

    class Handler(BaseHTTPRequestHandler):
        def _send(self, code, body, ctype="application/json"):
            data = body.encode() if isinstance(body, str) else body
            self.send_response(code)
            self.send_header("Content-Type", ctype + "; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            if self.path == "/":
                self._send(200, WEB_PAGE.read_bytes(), "text/html")
            else:
                self._send(404, '{"error":"not found"}')

        def do_POST(self):
            length = int(self.headers.get("Content-Length", 0))
            payload = json.loads(self.rfile.read(length) or b"{}")
            if self.path == "/api/reset":
                agent.reset()
                self._send(200, '{"ok":true}')
            elif self.path == "/api/chat":
                tools = []
                try:
                    reply = agent.ask(payload.get("message", ""),
                                      lambda n, a, r: tools.append({"name": n, "args": a, "result": r[:300]}))
                    self._send(200, json.dumps({"reply": reply, "tools": tools}, ensure_ascii=False))
                except Exception as exc:
                    self._send(500, json.dumps({"error": str(exc)}))
            else:
                self._send(404, '{"error":"not found"}')

        def log_message(self, *args):
            pass

    print(f"PiAgent Web läuft auf http://{host}:{port}  (Modell {MODEL}, "
          f"Shell/Schreiben {'ERLAUBT' if allow_shell else 'gesperrt'})")
    ThreadingHTTPServer((host, port), Handler).serve_forever()


def main():
    global MODEL
    ap = argparse.ArgumentParser(description="Lokaler KI-Agent für den Raspberry Pi")
    ap.add_argument("-p", "--prompt", help="Einzelne Frage stellen und beenden")
    ap.add_argument("-m", "--model", help=f"Ollama-Modell (Standard: {MODEL})")
    ap.add_argument("-y", "--yes", action="store_true", help="Befehle ohne Rückfrage ausführen")
    ap.add_argument("--web", action="store_true", help="Web-Oberfläche starten")
    ap.add_argument("--host", default=os.environ.get("PI_AGENT_HOST", "127.0.0.1"))
    ap.add_argument("--port", type=int, default=int(os.environ.get("PI_AGENT_PORT", "8765")))
    ap.add_argument("--allow-shell", action="store_true",
                    default=os.environ.get("PI_AGENT_ALLOW_SHELL") == "1",
                    help="Im Web-Modus Shell-Befehle und Schreiben erlauben")
    args = ap.parse_args()
    if args.model:
        MODEL = args.model

    check_ollama()
    if args.web:
        run_web(args.host, args.port, args.allow_shell)
    else:
        run_cli(args.yes, args.prompt)


if __name__ == "__main__":
    main()
