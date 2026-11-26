# TK Preisjäger – Steuerung des eigenen Chrome-Fensters (DevTools-Protokoll, nur lokal). Claude 26.11.2026
# Das Chrome läuft mit eigenem Profil als Dienst tk-preisjaeger-browser (Start mit --password-store=basic, sonst wartet es auf den
# Schlüsselbund und lädt keine Seiten) und ist mit Tekins Kleinanzeigen-Konto angemeldet – die Anmeldung macht Tekin selbst im Fenster.
import json
import threading
import time
import urllib.request

import websocket      # Paket websocket-client

PORT = 9335
_sperre = threading.Lock()      # immer nur ein Vorgang gleichzeitig im Browser


class Fehler(Exception):
    pass


class Browser:
    def __init__(self, port=PORT, timeout=40):
        tabs = json.load(urllib.request.urlopen("http://127.0.0.1:%d/json" % port, timeout=5))
        seiten = [t for t in tabs if t.get("type") == "page" and not t.get("url", "").startswith(("chrome://", "devtools://", "chrome-extension://"))]
        if not seiten:
            r = urllib.request.Request("http://127.0.0.1:%d/json/new?about:blank" % port, method="PUT")
            seiten = [json.load(urllib.request.urlopen(r, timeout=8))]
        self.ws = websocket.create_connection(seiten[0]["webSocketDebuggerUrl"], timeout=timeout, suppress_origin=True)
        self.n = 0
        self.ruf("Page.enable")

    def ruf(self, befehl, **parameter):
        self.n += 1
        self.ws.send(json.dumps({"id": self.n, "method": befehl, "params": parameter}))
        while True:
            d = json.loads(self.ws.recv())
            if d.get("id") == self.n:
                if "error" in d:
                    raise Fehler(str(d["error"].get("message"))[:200])
                return d.get("result", {})

    def geh(self, url, warte=2.5):
        self.ruf("Page.navigate", url=url)
        ende = time.time() + 20
        while time.time() < ende:      # bis die Seite geladen ist
            time.sleep(0.4)
            try:
                if self.js("return document.readyState") in ("interactive", "complete"):
                    break
            except Exception:
                pass
        time.sleep(warte)

    def js(self, code, *args):
        """Führt code als Funktionsrumpf aus (mit return …); Promise wird abgewartet. args stehen als arguments[i] bereit."""
        r = self.ruf("Runtime.evaluate", expression="(async function(){ %s }).apply(null, %s)" % (code, json.dumps(list(args))),
                     returnByValue=True, awaitPromise=True)
        if r.get("exceptionDetails"):
            raise Fehler(str(r["exceptionDetails"].get("exception", {}).get("description") or r["exceptionDetails"].get("text"))[:300])
        return r.get("result", {}).get("value")

    def url(self):
        return self.js("return location.href")

    def zu(self):
        try:
            self.ws.close()
        except Exception:
            pass


def mit_browser(fn):
    """Verbindet sich mit dem Fenster, ruft fn(browser) und trennt wieder. Wirft Fehler, wenn der Browser nicht läuft."""
    with _sperre:
        try:
            b = Browser()
        except Fehler:
            raise
        except Exception:
            raise Fehler("Der eigene Browser läuft nicht (Dienst tk-preisjaeger-browser)")
        try:
            return fn(b)
        finally:
            b.zu()
