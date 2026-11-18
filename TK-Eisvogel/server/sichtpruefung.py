#!/usr/bin/env python3
"""TK Eisvogel – Sichtprüfung der Oberfläche (Claude 17.11.2026).
Startet Chromium ohne Fenster, bedient die App wie ein Mensch (Frage eintippen, senden, Reiter wechseln) und
legt Bildschirmfotos ab. Meldet JavaScript-Fehler. Fragen laufen als Prüflauf (test=true): es wird nichts angelegt.
Aufruf: sichtpruefung.py [Zielordner]     (braucht: chromium, python3-websocket)
"""
import base64, json, os, subprocess, sys, tempfile, time, urllib.request
import websocket

URL = os.environ.get("EISVOGEL_URL", "http://127.0.0.1:8811")
ZIEL = sys.argv[1] if len(sys.argv) > 1 else "/tmp/eisvogel-bilder"
os.makedirs(ZIEL, exist_ok=True)
prof = tempfile.mkdtemp(prefix="chrome-prof-")
ch = subprocess.Popen(["chromium", "--headless=new", "--no-sandbox", "--disable-gpu", "--hide-scrollbars", f"--user-data-dir={prof}",
                       "--remote-debugging-port=9333", "--remote-allow-origins=*", "--window-size=390,844", "about:blank"],
                      stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
fehler, nr = [], [0]
try:
    for _ in range(40):
        try:
            tabs = json.load(urllib.request.urlopen("http://127.0.0.1:9333/json", timeout=2)); break
        except Exception: time.sleep(0.25)
    ws = websocket.create_connection([t for t in tabs if t["type"] == "page"][0]["webSocketDebuggerUrl"], timeout=60)

    def ruf(methode, **p):
        nr[0] += 1; ws.send(json.dumps({"id": nr[0], "method": methode, "params": p}))
        while True:
            m = json.loads(ws.recv())
            if m.get("method") == "Runtime.exceptionThrown":
                fehler.append(m["params"]["exceptionDetails"].get("exception", {}).get("description", str(m["params"]))[:300])
            if m.get("method") == "Log.entryAdded" and m["params"]["entry"]["level"] == "error":
                fehler.append("Konsole: " + m["params"]["entry"]["text"][:200] + " " + m["params"]["entry"].get("url", ""))
            if m.get("id") == nr[0]: return m.get("result", {})

    def js(code):
        r = ruf("Runtime.evaluate", expression=code, awaitPromise=True, returnByValue=True)
        return r.get("result", {}).get("value")

    def groesse(b, h, handy=True):
        ruf("Emulation.setDeviceMetricsOverride", width=b, height=h, deviceScaleFactor=2, mobile=handy)

    def dunkel(an):
        ruf("Emulation.setEmulatedMedia", features=[{"name": "prefers-color-scheme", "value": "dark" if an else "light"}])

    def gehe(pfad, warte=1.2):
        ruf("Page.navigate", url=URL + pfad); time.sleep(warte)

    def foto(name):
        d = ruf("Page.captureScreenshot", format="jpeg", quality=72)["data"]
        open(f"{ZIEL}/{name}.jpg", "wb").write(base64.b64decode(d)); print("Foto:", name)

    def fragen(text, hoechstens=40):
        js("""(()=>{const f=window.fetch;window.fetch=(u,o)=>{if(u==='/api/frage'){const b=JSON.parse(o.body);b.test=true;o.body=JSON.stringify(b)}return f(u,o)}})()""") if not js("window._pruef") else None
        js("window._pruef=1")
        vorher = js("document.querySelectorAll('.er .fuss').length")
        js(f"(()=>{{const F=document.getElementById('frage');F.value={json.dumps(text)};F.dispatchEvent(new Event('input'));document.getElementById('los').click()}})()")
        t0 = time.time()
        while time.time() - t0 < hoechstens:
            time.sleep(0.4)
            if js("document.querySelectorAll('.er .fuss').length") > vorher: break
        return round(time.time() - t0, 1)

    for m in ("Runtime.enable", "Page.enable", "Log.enable"): ruf(m)
    # 1) Handy, hell: Startseite
    groesse(390, 844); dunkel(False); gehe("/", 1.5); foto("1-handy-start-hell")
    print("Zustand:", js("document.getElementById('zustand').innerText"))
    # 2) zwei Fragen stellen
    print("Termine:", fragen("Welche Termine habe ich diese Woche?"), "s")
    print("Vogel:", fragen("Wann ist der TÜV für den GLK fällig?"), "s")
    js("window.scrollTo(0,document.documentElement.scrollHeight)"); time.sleep(0.4); foto("2-handy-antworten-hell")
    print("Antworten:", js("document.querySelectorAll('.er').length"), "· Quellen-Pillen:", js("document.querySelectorAll('.er .pille').length"),
          "· Überlauf quer:", js("document.documentElement.scrollWidth>document.documentElement.clientWidth"))
    # 3) Reiterwechsel und zurück: Gespräch muss noch da sein
    gehe("/karten", 1.5); foto("3-handy-karten-hell")
    print("Karten-Seite Titel:", js("document.title"), "· Reiter:", js("document.querySelectorAll('.tabs a').length"), "· aktiv:", js("(document.querySelector('.tabs a.an')||{}).innerText"))
    gehe("/", 1.2); print("Gespräch nach Rückkehr noch da:", js("document.querySelectorAll('.er').length"), "Antworten")
    # 4) dunkel
    dunkel(True); gehe("/", 1.2); js("window.scrollTo(0,document.documentElement.scrollHeight)"); time.sleep(0.3); foto("4-handy-antworten-dunkel")
    js("document.getElementById('kbtn').click()"); time.sleep(1.0); foto("5-handy-karteikarten-dunkel")
    print("Karteikarten sichtbar:", js("document.querySelectorAll('#kraster .karte').length"))
    gehe("/mehr", 1.5); foto("6-handy-mehr-dunkel")
    # 5) Schreibtisch
    groesse(1100, 820, False); dunkel(False); gehe("/einstellungen", 1.8); foto("7-mac-einstellungen-hell")
    print("Stand-Zeilen:", js("document.querySelectorAll('#stand .zeile').length"))
    gehe("/datenschutz", 1.0); foto("8-mac-datenschutz-hell")
    dunkel(True); gehe("/ueber", 1.0); foto("9-mac-ueber-dunkel")
    for p in ("/impressum", "/lizenzen", "/imac", "/gespraeche"):
        gehe(p, 1.0); print(p, "→", js("document.title"), "· quer überlaufend:", js("document.documentElement.scrollWidth>document.documentElement.clientWidth"))
    # fest gewähltes Aussehen
    dunkel(False); gehe("/einstellungen", 1.2); js("document.querySelector('#thema button[data-t=dunkel]').click()"); time.sleep(0.3)
    print("Aussehen fest dunkel:", js("document.documentElement.getAttribute('data-thema')"), "· Hintergrund:", js("getComputedStyle(document.body).backgroundColor"))
    gehe("/karten", 1.2); print("… gilt auch auf Karten-Seite:", js("document.documentElement.getAttribute('data-thema')"), js("getComputedStyle(document.body).backgroundColor"))
    js("localStorage.removeItem('eisvogel-thema')")
    ws.close()
finally:
    ch.terminate()
    try: ch.wait(timeout=5)
    except Exception: ch.kill()
    subprocess.run(["rm", "-rf", prof])
print("JavaScript-Fehler:", len(fehler)); [print("  ", f) for f in fehler[:10]]
