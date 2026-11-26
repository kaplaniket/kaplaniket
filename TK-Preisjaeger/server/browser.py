# TK Preisjäger – Steuerung des eigenen Firefox (Marionette, nur lokal). Claude 26.11.2026
# Der Firefox läuft mit eigenem Profil als Dienst tk-preisjaeger-browser und ist mit Tekins Kleinanzeigen-Konto angemeldet
# (die Anmeldung macht Tekin selbst im Fenster). Hier wird nichts getarnt: Firefox meldet sich als ferngesteuert.
import json
import socket
import threading
import time

PORT = 2828
_sperre = threading.Lock()      # immer nur ein Vorgang gleichzeitig im Browser


class Fehler(Exception):
    pass


class Browser:
    def __init__(self, port=PORT, timeout=40):
        self.s = socket.create_connection(("127.0.0.1", port), timeout=timeout)
        self.n = 0
        self._lesen()      # Begrüßung
        self.ruf("WebDriver:NewSession", {"capabilities": {"alwaysMatch": {"pageLoadStrategy": "eager", "unhandledPromptBehavior": "dismiss"}}})

    def _lesen(self):
        kopf = b""
        while not kopf.endswith(b":"):
            c = self.s.recv(1)
            if not c:
                raise Fehler("Browser hat die Verbindung beendet")
            kopf += c
        rest, daten = int(kopf[:-1]), b""
        while len(daten) < rest:
            daten += self.s.recv(rest - len(daten))
        return json.loads(daten)

    def ruf(self, befehl, parameter=None):
        self.n += 1
        d = json.dumps([0, self.n, befehl, parameter or {}])
        self.s.sendall(("%d:%s" % (len(d.encode()), d)).encode())
        while True:
            a = self._lesen()
            if isinstance(a, list) and len(a) == 4 and a[1] == self.n:
                if a[2]:
                    raise Fehler("%s: %s" % (a[2].get("error"), str(a[2].get("message"))[:200]))
                return a[3]

    def geh(self, url, warte=2.5):
        self.ruf("WebDriver:Navigate", {"url": url})
        time.sleep(warte)

    def js(self, code, *args):
        """Führt code als Funktionsrumpf aus (mit return …); Promise wird abgewartet."""
        r = self.ruf("WebDriver:ExecuteAsyncScript", {
            "script": "const fertig = arguments[arguments.length - 1]; (async () => { %s })().then(fertig, e => fertig({__fehler: String(e)}));" % code,
            "args": list(args), "scriptTimeout": 30000})
        w = r.get("value") if isinstance(r, dict) else r
        if isinstance(w, dict) and "__fehler" in w:
            raise Fehler(w["__fehler"])
        return w

    def url(self):
        return self.ruf("WebDriver:GetCurrentURL").get("value")

    def zu(self):
        try:
            self.ruf("WebDriver:DeleteSession")
        except Exception:
            pass
        try:
            self.s.close()
        except Exception:
            pass


def mit_browser(fn):
    """Öffnet eine Sitzung, ruft fn(browser) und schließt sie wieder. Wirft Fehler, wenn der Browser nicht läuft."""
    with _sperre:
        try:
            b = Browser()
        except OSError:
            raise Fehler("Der eigene Browser läuft nicht (Dienst tk-preisjaeger-browser)")
        try:
            return fn(b)
        finally:
            b.zu()
