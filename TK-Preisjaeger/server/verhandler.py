# TK Preisjäger – selbstständiges Verhandeln über Tekins eigenes Kleinanzeigen-Konto. Claude 26.11.2026
# Freigabe Tekin 26.11.2026 („ja bauen“): Die App darf für diese Verhandlungen selbst an Verkäufer schreiben, bis sein Preis erreicht ist;
# Abholung/Bezahlung macht er selbst. Stand: Das eigene Chrome-Fenster läuft und wird gesteuert; Senden und Lesen der Nachrichten werden
# eingebaut, sobald das Konto im Chrome-Fenster angemeldet ist (die Seiten dafür sind nur angemeldet sichtbar).
import browser


def konto():
    """Läuft der eigene Browser, und ist dort ein Kleinanzeigen-Konto angemeldet?"""
    def pruefe(b):
        b.geh("https://www.kleinanzeigen.de/m-meine-anzeigen.html", 3)
        return b.js("return {url: location.href, einloggen: [...document.querySelectorAll('header a, a')].some(a => /^Einloggen$/.test((a.innerText || '').trim()))}")
    try:
        r = browser.mit_browser(pruefe)
        angemeldet = "login." not in r["url"] and "einloggen" not in r["url"] and not r["einloggen"]
        return {"browser": True, "angemeldet": angemeldet, "bereit": False,
                "hinweis": "Konto ist angemeldet – Senden und Lesen werden jetzt eingerichtet." if angemeldet else
                           "Noch nicht angemeldet: am HP im Chrome-Fenster des Preisjägers („Kleinanzeigen – Anmelden“) mit deinem Konto einloggen."}
    except Exception as e:
        return {"browser": False, "angemeldet": False, "bereit": False, "hinweis": "Der eigene Browser auf dem HP ist nicht erreichbar (%s)." % str(e)[:80]}
