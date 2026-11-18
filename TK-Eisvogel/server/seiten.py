#!/usr/bin/env python3
"""TK Eisvogel – Seiten und Aussehen (Claude 17.11.2026).
Eine Gestaltung für alles: der Eisvogel-Stil aus ~/bin/vogel-web.py (Farben, Schrift, Kopf, Reiterleiste) gilt auch für
Fragen, Einstellungen und die Rechtstexte. Name, Version und Inhaber stehen in marke.json (eine Stelle für alles).
"""
import html, json, os, re, sys
from datetime import datetime
from pathlib import Path

APP = Path(__file__).resolve().parent
H = Path.home()
WOCHENTAG = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"]
MONAT = ["Januar", "Februar", "März", "April", "Mai", "Juni", "Juli", "August", "September", "Oktober", "November", "Dezember"]


def marke():
    m = {"name": "TK Eisvogel", "kurz": "Eisvogel", "leitsatz": "", "version": "3.0", "stand": "", "jahr": "2026",
         "inhaber": "Tekin Kaplan", "strasse": "", "ort": "", "email": "", "vorgaenger": "TK KI + TK Vogel"}
    try: m.update(json.load(open(APP / "marke.json", encoding="utf-8")))
    except Exception: pass
    return m


def E(s):
    return html.escape(str("" if s is None else s))


# ---------- Grundlage aus TK Vogel übernehmen (Farben, Schrift, Symbole, Vogel-Zeichen) ----------
def _basis():
    merk = APP / "eisvogel-basis.json"
    try:
        from importlib.machinery import SourceFileLoader
        sys.path.insert(0, str(H / "bin"))
        vw = SourceFileLoader("vogelweb_fuer_eisvogel", str(H / "bin/vogel-web.py")).load_module()
        b = {"css": vw.CSS, "ikon": dict(vw.IKON), "vogel": vw.VOGEL}
        try:
            if not merk.exists() or json.load(open(merk)) != b: json.dump(b, open(merk, "w"), ensure_ascii=False)
        except Exception: pass
        return b
    except Exception:
        return json.load(open(merk))   # letzte gemerkte Fassung, falls vogel-web.py gerade nicht ladbar ist


_B = _basis()
IKON = dict(_B["ikon"])
IKON.update({
    "einstellungen": "<path d='M4 7h9M18 7h2M4 17h3M12 17h8'/><circle cx='15.5' cy='7' r='2.4'/><circle cx='9.500' cy='17' r='2.400'/>",
    "kopie": "<rect x='8.500' y='8.500' width='11.500' height='11.500' rx='2.500'/><path d='M15.500 8.500V6.500A2.500 2.500 0 0 0 13 4H6.500A2.500 2.500 0 0 0 4 6.500V13a2.500 2.500 0 0 0 2.500 2.500h2'/>",
    "stopp": "<rect x='7' y='7' width='10' height='10' rx='2' fill='currentColor' stroke='none'/>",
    "plus": "<path d='M12 5v14M5 12h14'/>",
    "info": "<circle cx='12' cy='12' r='8.500'/><path d='M12 11v5.500M12 7.700v.300'/>",
    "schild": "<path d='M12 3.500 5 6v5.500c0 4.300 2.900 7.700 7 9 4.100-1.300 7-4.700 7-9V6z'/><path d='m9 12 2.200 2.200L15.200 10'/>",
    "blatt": "<path d='M7 3.500h7l4 4V20a.500.500 0 0 1-.500.500H7a.500.500 0 0 1-.500-.500V4a.500.500 0 0 1 .500-.500z'/><path d='M14 3.500V8h4M9.500 12.500h5M9.500 16h5'/>",
    "urheber": "<circle cx='12' cy='12' r='8.500'/><path d='M14.800 9.800a3.500 3.500 0 1 0 0 4.400'/>",
    "kartei": "<rect x='4' y='6.500' width='16' height='11' rx='2.500'/><path d='M8 10.500h8M8 13.500h5'/>",
})


def ik(name, extra=""):
    return f"<svg class='ik {extra}' viewBox='0 0 24 24' aria-hidden='true'>{IKON.get(name, '')}</svg>"


def vogel(cls="marke"):
    return _B["vogel"].replace("{cls}", cls)


def stil():
    try: zusatz = (APP / "zusatz.css").read_text(encoding="utf-8")
    except Exception: zusatz = ""
    return _B["css"] + "\n" + zusatz


def stand_nr():
    """Ändert sich, sobald Stil oder Skript geändert wurden → Browser lädt neu."""
    n = 0
    for f in ("zusatz.css", "app.js", "seiten.py", "eisvogel-basis.json"):
        try: n = max(n, int((APP / f).stat().st_mtime))
        except OSError: pass
    return n


THEMA = ("<script>(function(){try{var t=localStorage.getItem('eisvogel-thema');if(t==='hell'||t==='dunkel'){document.documentElement.setAttribute('data-thema',t);"
         "var f=t==='hell'?'#07485a':'#0b2a33';document.querySelectorAll('meta[name=theme-color]').forEach(function(m){m.setAttribute('content',f)})}}catch(e){}})()</script>")

REITER = [("/", "fragen", "Fragen"), ("/karten", "karten", "Karten"), ("/imac", "imac", "iMac"), ("/gespraeche", "gespraeche", "Gespräche"),
          ("/mehr", "mehr", "Mehr"), ("/einstellungen", "einstellungen", "Einstellungen")]


def offene_karten():
    try:
        sys.path.insert(0, str(H / "bin"))
        import karten
        return len(karten.liste("offen"))
    except Exception:
        return 0


def kopf_teil(titel=""):
    """Alles, was in <head> gehört (auch für die durchgeleiteten TK-Vogel-Seiten)."""
    m = marke()
    return ("<meta name=apple-mobile-web-app-capable content=yes><meta name=mobile-web-app-capable content=yes>"
            "<meta name=apple-mobile-web-app-status-bar-style content=black-translucent>"
            f"<meta name=apple-mobile-web-app-title content='{E(m['name'])}'><meta name=application-name content='{E(m['name'])}'>"
            f"<meta name=author content='{E(m['inhaber'])}'><meta name=copyright content='© {E(m['jahr'])} {E(m['inhaber'])}'><meta name=robots content='noindex,nofollow'>"
            "<link rel=apple-touch-icon href=/apple-touch-icon.png><link rel=icon type=image/png href=/icon.png><link rel=manifest href=/manifest.json>"
            "<meta name=theme-color content='#07485a' media='(prefers-color-scheme: light)'><meta name=theme-color content='#0b2a33' media='(prefers-color-scheme: dark)'>"
            + THEMA)


def kopf(titel, an, unter="", knoepfe="", unter_id=""):
    m = marke()
    return ("<!doctype html><html lang=de><head><meta charset=utf-8>"
            "<meta name=viewport content='width=device-width,initial-scale=1,viewport-fit=cover'>" + kopf_teil()
            + f"<title>{E(titel)} – {E(m['name'])}</title><link rel=stylesheet href='/stil.css?v={stand_nr()}'></head><body data-seite='{an}'>"
            f"<header class=kopf><div class=kopf-in>{vogel()}<div><h1>{E(titel)}</h1>"
            + (f"<p{' id=' + unter_id if unter_id else ''}>{unter}</p>" if unter or unter_id else "") + f"</div>{knoepfe}</div></header>")


def nav(an, offen=None):
    offen = offene_karten() if offen is None else offen
    t = "".join(f"<a href='{u}' class='{'an' if n == an else ''}'" + (" aria-current=page" if n == an else "") + f"><i>{ik(n)}"
                + (f"<em class=zahl>{offen}</em>" if n == "karten" and offen else "") + f"</i>{name}</a>" for u, n, name in REITER)
    return f"<nav class=tabs aria-label=Bereiche><div class=tabs-in>{t}</div></nav>"


def fuss(an, skript=""):
    return f"<div id=toast role=status aria-live=polite></div>{nav(an)}{skript}</body></html>"


def recht_zeile():
    m = marke()
    return (f"<div class=recht>© {E(m['jahr'])} {E(m['inhaber'])} · <a href='/impressum'>Impressum</a> · <a href='/datenschutz'>Datenschutz</a> · "
            "Antworten können Fehler enthalten</div>")


# ───────────────────────── Fragen ─────────────────────────
def seite_fragen():
    m = marke(); d = datetime.now()
    knoepfe = (f"<button class='kopf-knopf rund' id=neu title='Neues Gespräch' aria-label='Neues Gespräch'>{ik('plus')}</button>"
               f"<button class='kopf-knopf rund' id=kbtn title='Karteikarten: alle bisherigen Fragen' aria-label='Karteikarten'>{ik('kartei')}</button>"
               "<button class=kopf-knopf id=xbtn hidden>Beenden</button>")
    schnell = ["Was ist heute wichtig?", "Was ist offen?", "Termine diese Woche", "Was war gestern los?", "Was weiß ich über "]
    start = (f"<div class=start id=leer>{vogel('gross')}<h2>Frag mich alles</h2>"
             "<p>Ich kenne dein Wiki, Mails, WhatsApp, Termine, Dokumente und den Bildschirm am iMac.</p><div class=liste>"
             f"<div class=zeile>{ik('kamera')}<div><b>Foto mitschicken</b><div class=meta>Brief, Rechnung oder Bildschirm – ich sage, was zu tun ist.</div></div></div>"
             f"<div class=zeile>{ik('merk')}<div><b>Merken und erinnern</b><div class=meta>„Merk dir …“ oder „Sag Bescheid, wenn …“.</div></div></div>"
             f"<div class=zeile>{ik('hermes')}<div><b>Auftrag an Hermes</b><div class=meta>Ein „!“ an den Anfang setzen.</div></div></div></div></div>")
    symbole = json.dumps({"laut": ik("laut"), "kopie": ik("kopie"), "senden": ik("senden"), "stopp": ik("stopp")})
    return (kopf(m["name"], "fragen", "<i class=lampe></i>Prüfe …", knoepfe, "zustand")
            + "<main class=mit-dock id=haupt><div id=liste>" + start + "</div>"
            "<div class=dock><div class=schnell>" + "".join(f"<button type=button data-t=\"{E(s)}\">{E(s.strip())}{' …' if s.endswith(' ') else ''}</button>" for s in schnell) + "</div>"
            f"<div class=anhang id=anhang hidden><img id=vbild alt='Gewähltes Foto'><span>Foto wird mitgeschickt</span><button type=button class='rund klar' onclick=fotoweg() aria-label='Foto entfernen'>{ik('x')}</button></div>"
            f"<div class=feld><button type=button class='rund klar' onclick=\"document.getElementById('datei').click()\" aria-label='Foto mitschicken'>{ik('kamera')}</button>"
            "<input type=file id=datei accept='image/*' hidden>"
            "<textarea id=frage rows=1 placeholder='Frage oder Auftrag' aria-label='Frage oder Auftrag'></textarea>"
            f"<button type=button class='rund haupt' id=los aria-label=Senden>{ik('senden')}</button></div>" + recht_zeile() + "</div></main>"
            "<main id=kmain hidden><section class=abschnitt><h2>Karteikarten</h2><p class=hinweis>Jede Frage mit Antwort wird hier aufbewahrt. Antippen zeigt sie wieder im Gespräch.</p>"
            f"<div class=suchfeld><div>{ik('suche')}<input id=kq type=search placeholder='Karteikarten durchsuchen, z. B. Anna, Versicherung, Prüfung' aria-label='Karteikarten durchsuchen'></div></div>"
            "<div class=kraster id=kraster></div></section></main>"
            + fuss("fragen", f"<script>window.IK={symbole}</script><script src='/app.js?v={stand_nr()}'></script>"))


# ───────────────────────── Einstellungen ─────────────────────────
JS_EINST = """<script>
const $=s=>document.querySelector(s);const esc=t=>String(t).replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));
function sag(t,f){const e=$('#toast');e.textContent=t;e.className='da'+(f?' fehler':'');clearTimeout(sag.t);sag.t=setTimeout(()=>e.className='',f?6000:2600)}
async function laden(){try{const j=await(await fetch('/api/einstellungen',{cache:'no-store'})).json();
 document.querySelectorAll('#quelle button').forEach(b=>b.classList.toggle('an',b.dataset.q===j.quelle));
 const z=(a,b)=>'<div class=zeile><div>'+a+'</div><div class=wert>'+esc(b)+'</div></div>';const w=j.wissen||{};
 $('#stand').innerHTML=z('Rechner',j.rechner)+z('Wissen',(w.seiten||'?')+' Seiten, '+(w.abschnitte||'?')+' Abschnitte · Stand '+(w.stand||'?'))
 +z('Speicher von TK Vogel',j.speicher_dateien?j.speicher_dateien.toLocaleString('de-DE')+' Dateien (Wiki, Dokumente, Mail- und Chat-Archiv)':'–')
 +z('Selbst gelernt',(w.gelernt||0).toLocaleString('de-DE')+' Antworten, davon '+(w.gelernt_woertlich||0).toLocaleString('de-DE')+' geprüft aus dem Wiki')
 +z('Aus deinem Verlauf',(w.verlauf||0).toLocaleString('de-DE')+' früher gestellte Fragen mit der damaligen Antwort')
 +z('Karteikarten',j.karteikarten)+z('Lokales Modell',j.modell_lokal+(j.geladen&&j.geladen.length?' · im Speicher: '+j.geladen.join(', '):''))+z('Fassung',j.version)}
 catch(e){$('#stand').innerHTML='<div class=zeile><div>Der Stand lässt sich gerade nicht laden.</div></div>'}}
document.querySelectorAll('#quelle button').forEach(b=>b.onclick=async()=>{try{await fetch('/api/einstellungen',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({quelle:b.dataset.q})});sag('Gespeichert');laden()}catch(e){sag('Speichern nicht möglich',1)}});
function thema(){let t='auto';try{t=localStorage.getItem('eisvogel-thema')||'auto'}catch(e){}document.querySelectorAll('#thema button').forEach(b=>b.classList.toggle('an',b.dataset.t===t))}
document.querySelectorAll('#thema button').forEach(b=>b.onclick=()=>{try{b.dataset.t==='auto'?localStorage.removeItem('eisvogel-thema'):localStorage.setItem('eisvogel-thema',b.dataset.t)}catch(e){}
 if(b.dataset.t==='auto')document.documentElement.removeAttribute('data-thema');else document.documentElement.setAttribute('data-thema',b.dataset.t);thema()});
thema();laden();
</script>"""


def seite_einstellungen():
    m = marke()
    return (kopf("Einstellungen", "einstellungen", "Antworten, Aussehen, Stand, Rechtliches")
            + "<main><section class=abschnitt><h2>Wer beantwortet freie Fragen?</h2>"
            "<p class=hinweis>Termine, Offenes, Personen-Akten und Gelerntes kommen immer sofort vom eigenen Rechner.</p>"
            "<div class=wahl id=quelle><button data-q=vogel>TK Vogel – schnell<small>Fertige Antwort nach 3–5 Sekunden, auch bei Zusammenhängen, Zeiträumen und Bildern. "
            "Ganzes Gedächtnis einschließlich Bildschirm. Die Frage und passende Auszüge gehen dafür an DeepSeek (Internet).</small></button>"
            "<button data-q=lokal>Nur lokal – privat<small>Keine fremde KI, nichts verlässt den Rechner. Wörtliche Belege aus Wiki, Dokumenten, Mails und Nachrichten nach etwa einer Sekunde, "
            "der zusammenfassende Satz nach 10–20 Sekunden. Einfacheres Modell: gut für Fakten, schwächer bei Zusammenhängen.</small></button></div></section>"
            "<section class=abschnitt><h2>Aussehen</h2><div class=dreier id=thema><button data-t=auto>Automatisch</button><button data-t=hell>Hell</button><button data-t=dunkel>Dunkel</button></div></section>"
            "<section class=abschnitt><h2>Stand</h2><div class=liste id=stand><div><div class=skelett style='width:70%'></div><div class=skelett style='width:45%'></div></div></div></section>"
            "<section class=abschnitt><h2>Über und Rechtliches</h2><div class=liste>"
            + "".join(f"<a class=zeile href='{u}'>{ik(s)}<div>{E(t)}</div>{ik('pfeil')}</a>" for u, s, t in
                      [("/ueber", "info", "Über " + m["name"]), ("/impressum", "blatt", "Impressum"), ("/datenschutz", "schild", "Datenschutz"), ("/lizenzen", "urheber", "Urheberrecht und Lizenzen")])
            + f"</div><p class=stand-hinweis>{E(m['name'])} {E(m['version'])} · © {E(m['jahr'])} {E(m['inhaber'])}</p></section></main>"
            + fuss("einstellungen", JS_EINST))


# ───────────────────────── Über und Rechtstexte ─────────────────────────
def _recht_seite(titel, unter, inhalt):
    m = marke()
    return (kopf(titel, "einstellungen", unter) + "<main><div class='karte recht-text'>" + inhalt + "</div>"
            f"<p class=stand-hinweis>Stand {E(m['stand'])} · <a href='/einstellungen'>Zurück zu den Einstellungen</a></p></main>" + fuss("einstellungen"))


def seite_ueber():
    m = marke()
    return (kopf("Über " + m["name"], "einstellungen", "Fassung " + m["version"])
            + f"<main><div class='karte ueber'>{vogel('gross')}<h2>{E(m['name'])}</h2><p>{E(m['leitsatz'])}</p>"
            f"<p class=meta style='margin-top:10px'>Fassung {E(m['version'])} · Stand {E(m['stand'])}<br>© {E(m['jahr'])} {E(m['inhaber'])}. Alle Rechte vorbehalten.</p></div>"
            "<div class='karte recht-text'>"
            f"<h2>Was das ist</h2><p>{E(m['name'])} ist die persönliche Gedächtnis- und Assistenz-App von {E(m['inhaber'])}. Sie ist aus den beiden Programmen "
            "<b>TK KI</b> (eigene KI auf dem eigenen Rechner) und <b>TK Vogel</b> (Gedächtnis über Wiki, Mails, Nachrichten, Bildschirm und Gespräche) entstanden – jetzt eine App mit einem Gesicht.</p>"
            "<h2>Warum Eisvogel</h2><p>Der Eisvogel wartet ruhig, sieht genau hin und trifft beim ersten Stoß. So soll die App antworten: schnell, genau und nur mit dem, was wirklich in den Unterlagen steht.</p>"
            "<h2>Wie eine Antwort entsteht</h2><ul>"
            "<li><b>Sofort, ohne KI:</b> Termine und Offenes (Kalender, TKMail-Fristen, Karten), Personen-Akten, geprüfte gelernte Antworten, wiederholte Fragen.</li>"
            "<li><b>Dokumente:</b> Passende Dateien aus der Ablage werden selbst gesucht und gelesen, Scans mit Texterkennung.</li>"
            "<li><b>Freie Fragen:</b> je nach Einstellung über TK Vogel (schnell, ganzes Gedächtnis) oder nur lokal auf dem eigenen Rechner.</li></ul>"
            "<h2>Wo es läuft</h2><p>Auf dem eigenen Rechner zu Hause (HP EliteDesk, „tk-ki-hp“). Erreichbar nur im eigenen Tailscale-Netz und am Rechner selbst, nicht aus dem öffentlichen Internet.</p>"
            "<h2>Grenzen</h2><p>Antworten werden automatisch erzeugt und können Fehler enthalten. Maßgeblich sind immer die Originalunterlagen. "
            "Keine Rechts-, Steuer-, Finanz- oder medizinische Beratung.</p></div>"
            "<p class=stand-hinweis><a href='/einstellungen'>Zurück zu den Einstellungen</a></p></main>" + fuss("einstellungen"))


def seite_impressum():
    m = marke()
    return _recht_seite("Impressum", "Wer hinter dieser App steht",
        f"<h2>Anbieter und verantwortlich für den Inhalt</h2><address>{E(m['inhaber'])}<br>{E(m['strasse'])}<br>{E(m['ort'])}<br>Deutschland</address>"
        f"<p>E-Mail: <a href='mailto:{E(m['email'])}'>{E(m['email'])}</a></p>"
        f"<h2>Art des Angebots</h2><p>{E(m['name'])} ist eine private, nicht geschäftsmäßige Anwendung für den eigenen Gebrauch. Sie ist nicht öffentlich zugänglich, "
        "sondern nur im eigenen, geschlossenen Netz erreichbar. Die Angaben auf dieser Seite erfolgen freiwillig; eine Pflicht nach § 5 DDG besteht für rein private Angebote nicht.</p>"
        "<h2>Haftung für Inhalte</h2><p>Die Antworten der App werden automatisch aus den eigenen Unterlagen und mit Hilfe von Sprachmodellen erzeugt. Sie können unvollständig, "
        "veraltet oder falsch sein. Maßgeblich sind die Originalunterlagen (Bescheide, Verträge, Mails). Die App ersetzt keine Rechts-, Steuer-, Finanz- oder medizinische Beratung.</p>"
        "<h2>Verweise</h2><p>Verweise auf fremde Seiten oder Dienste dienen nur der Information. Für deren Inhalte sind die jeweiligen Betreiber verantwortlich.</p>"
        f"<h2>Urheberrecht</h2><p>© {E(m['jahr'])} {E(m['inhaber'])}. Einzelheiten unter <a href='/lizenzen'>Urheberrecht und Lizenzen</a>.</p>")


def seite_datenschutz():
    m = marke()
    return _recht_seite("Datenschutz", "Welche Daten die App verarbeitet und wohin sie gehen",
        f"<h2>Verantwortlich</h2><address>{E(m['inhaber'])}, {E(m['strasse'])}, {E(m['ort'])}<br>E-Mail: <a href='mailto:{E(m['email'])}'>{E(m['email'])}</a></address>"
        f"<h2>Zweck</h2><p>{E(m['name'])} ist das persönliche Gedächtnis und der persönliche Assistent von {E(m['inhaber'])}: Fragen zu eigenen Vorgängen, Terminen, Personen und Dokumenten beantworten.</p>"
        "<h2>Welche Daten verarbeitet werden</h2><ul>"
        "<li>das eigene Obsidian-Wiki einschließlich Chat-Mitschriften und Meeting-Protokollen,</li>"
        "<li>E-Mails und Fristen aus TKMail, WhatsApp- und iMessage-Nachrichten, Kontakte,</li>"
        "<li>Kalender und Erinnerungen, Aktionskarten, Routinen, Merkliste,</li>"
        "<li>Texte und Bildschirmfotos des iMac-Bildschirms sowie der Browser-Verlauf (aufgezeichnet von TK Vogel am iMac),</li>"
        "<li>Dokumente aus der eigenen Ablage (auch per Texterkennung gelesene Scans),</li>"
        "<li>gestellte Fragen, Antworten (Karteikarten) und mitgeschickte Fotos.</li></ul>"
        "<p>Zeilen, die wie Passwörter, PINs, TANs oder Kontonummern aussehen, werden herausgefiltert, soweit sie erkannt werden.</p>"
        "<h2>Wo die Daten liegen</h2><p>Auf den eigenen Geräten: dem Rechner zu Hause (HP EliteDesk „tk-ki-hp“ mit den angeschlossenen Festplatten) und dem iMac. "
        "Die App selbst speichert nichts in einer Cloud.</p>"
        "<h2>Wer zugreifen kann</h2><p>Die App ist nur im eigenen Tailscale-Netz (verschlüsselte Verbindung zwischen den eigenen Geräten) und am Rechner selbst erreichbar, "
        "nicht aus dem öffentlichen Internet. Wer ein Gerät in diesem Netz bedienen kann, kann alles lesen – die Geräte daher mit Code oder Kennwort sperren.</p>"
        "<h2>Weitergabe an Dritte: DeepSeek</h2><p>In der Einstellung <b>„TK Vogel – schnell“</b> werden zur Beantwortung einer freien Frage die Frage selbst und die dazu gefundenen Auszüge "
        "(Wiki, Mails, Nachrichten, Termine, gelesene Dokumente, gegebenenfalls ein Bildschirmfoto oder mitgeschicktes Foto) über das Internet an den KI-Dienst <b>DeepSeek</b> "
        "(api.deepseek.com) gesendet. Der Anbieter sitzt in der Volksrepublik China, also außerhalb der EU; für dieses Land gibt es keinen Angemessenheitsbeschluss der EU-Kommission. "
        "Was DeepSeek mit den Daten tut, richtet sich nach dessen eigenen Bedingungen. Dasselbe gilt für Aufträge an Hermes (ein „!“ am Anfang) und für das Dauertraining, soweit es über DeepSeek läuft.</p>"
        "<p>In der Einstellung <b>„Nur lokal – privat“</b> verlassen Fragen in dieser App den eigenen Rechner nicht: Suche, Belege, Texterkennung von Fotos und das Sprachmodell laufen dort, "
        "und auch das Dauertraining lernt dann ohne DeepSeek. Termine, Offenes, Personen-Akten und gelernte Antworten laufen in beiden Einstellungen lokal. "
        "Unabhängig von dieser Einstellung arbeiten die übrigen Helfer weiter über DeepSeek: Hermes, Routinen und Wächter, Mitschriften, Morgen- und Tagesberichte sowie das Fragefenster von TK Vogel am iMac.</p>"
        "<h2>Daten anderer Personen</h2><p>Die Unterlagen enthalten zwangsläufig auch Daten anderer Menschen (Familie, Mail- und Chat-Partner, Mieter, Behörden, Dienstleister). "
        "Rein persönliche und familiäre Verarbeitung ist von der DSGVO ausgenommen (Art. 2 Abs. 2 Buchst. c). Für alles, was darüber hinausgeht – insbesondere die Vermietung –, "
        "gelten die Regeln der DSGVO, auch für die Weitergabe an einen Dienst außerhalb der EU. Für solche Vorgänge ist die Einstellung „Nur lokal – privat“ die sichere Wahl. "
        "Diese Seite ist keine Rechtsberatung.</p>"
        "<h2>Speicherdauer und Löschen</h2><p>Die Daten bleiben gespeichert, bis sie gelöscht werden. Karteikarten liegen in der Datei <code>index/karteikarten.jsonl</code>, "
        "Protokolle der Fragen in <code>logs/fragen.jsonl</code> und unter <code>~/gedaechtnis/vogel/</code>. Nichts wird automatisch gelöscht.</p>"
        "<h2>Cookies und Auswertung</h2><p>Keine Werbung, keine Auswertung des Nutzungsverhaltens, keine Dienste Dritter in der Oberfläche. Im Browser wird nur die Wahl des Aussehens "
        "und das laufende Gespräch der Sitzung gemerkt (lokaler Speicher des Browsers).</p>"
        "<h2>Rechte</h2><p>Auskunft, Berichtigung und Löschung: an die oben genannte Adresse. Beschwerden nimmt die Landesbeauftragte für Datenschutz und Informationsfreiheit "
        "Nordrhein-Westfalen entgegen.</p>")


def seite_lizenzen():
    m = marke()
    teile = [("Ollama", "Laufzeit für die lokalen Sprachmodelle", "MIT"),
             ("Qwen3 4B (Alibaba Cloud)", "lokales Antwortmodell", "Apache 2.0"),
             ("BGE-M3 (BAAI)", "Suche nach Bedeutung", "MIT"),
             ("Python, NumPy, SQLite", "Programmiersprache, Rechnen, Datenbank", "PSF · BSD-3 · gemeinfrei"),
             ("Tesseract OCR", "Texterkennung für Scans", "Apache 2.0"),
             ("Poppler (pdftotext, pdftoppm)", "PDF lesen; als eigenständige Programme aufgerufen", "GPL"),
             ("ImageMagick", "Bilder verkleinern", "ImageMagick-Lizenz"),
             ("Bricolage Grotesque", "Schrift der Überschriften", "SIL Open Font License 1.1"),
             ("Tailscale", "verschlüsseltes eigenes Netz", "Dienst; Client BSD-3"),
             ("DeepSeek", "KI-Dienst für die Einstellung „TK Vogel – schnell“", "Dienst; Bedingungen des Anbieters"),
             ("WebKit (Apple)", "Anzeige im Mac-Programm", "Teil von macOS")]
    return _recht_seite("Urheberrecht und Lizenzen", "Wem was gehört",
        f"<h2>Urheberrecht</h2><p>© {E(m['jahr'])} {E(m['inhaber'])}. Alle Rechte vorbehalten.</p>"
        f"<p>Name „{E(m['name'])}“, Eisvogel-Zeichen, Gestaltung, Texte und Programmcode dieser App gehören {E(m['inhaber'])}, soweit Rechte daran bestehen. "
        "Die App wurde in seinem Auftrag und nach seinen Vorgaben mit Unterstützung von KI-Werkzeugen (Claude von Anthropic) erstellt. "
        "Sie ist für den eigenen Gebrauch bestimmt; Weitergabe, Vervielfältigung oder Veröffentlichung nur mit seiner Zustimmung.</p>"
        "<h2>Eigene Inhalte</h2><p>Wiki, Dokumente, Mails und Nachrichten bleiben Eigentum ihrer jeweiligen Verfasser. Die App macht sie nur durchsuchbar.</p>"
        "<h2>Verwendete fremde Bausteine</h2><table><tr><th>Baustein</th><th>Wofür</th><th>Lizenz</th></tr>"
        + "".join(f"<tr><td>{E(a)}</td><td>{E(b)}</td><td>{E(c)}</td></tr>" for a, b, c in teile) + "</table>"
        "<p style='margin-top:10px'>Die Lizenztexte liegen den jeweiligen Programmen bei. Die Symbole der Oberfläche und das Eisvogel-Zeichen sind eigene Zeichnungen.</p>"
        "<h2>Marken</h2><p>Apple, iMac, iPhone, iMessage, WhatsApp, Telegram, Obsidian, Tailscale, DeepSeek und andere genannte Namen sind Marken ihrer jeweiligen Inhaber. "
        "Es besteht keine Verbindung zu diesen Unternehmen.</p>"
        f"<h2>Hinweis zum Namen</h2><p>„{E(m['name'])}“ ist ein Arbeitsname für die private Nutzung. Vor einer Veröffentlichung oder Weitergabe wäre eine Markenrecherche (DPMAregister) nötig.</p>")


RECHT = {"/ueber": seite_ueber, "/impressum": seite_impressum, "/datenschutz": seite_datenschutz, "/lizenzen": seite_lizenzen}


def manifest():
    m = marke()
    return json.dumps({"name": m["name"], "short_name": m["kurz"], "description": m["leitsatz"], "lang": "de", "start_url": "/", "scope": "/", "display": "standalone",
                       "background_color": "#edf2f3", "theme_color": "#07485a", "icons": [{"src": "/icon.png", "sizes": "512x512", "type": "image/png", "purpose": "any"}]}, ensure_ascii=False)


# ───────────────────────── TK-Vogel-Seiten einpassen ─────────────────────────
def vogel_umbauen(s, pfad):
    """Durchgeleitete TK-Vogel-Seite (Karten, iMac, Gespräche, Mehr): gleicher Name, gleiche Reiterleiste, gleiches Aussehen."""
    m = marke()
    an = {"/karten": "karten", "/imac": "imac", "/gespraeche": "gespraeche", "/mitschriften": "gespraeche", "/mehr": "mehr"}.get(pfad, "")
    z = re.search(r"<em class=zahl>(\d+)</em>", s)
    s = re.sub(r"<nav class=tabs.*?</nav>", lambda _: nav(an, int(z.group(1)) if z else 0), s, count=1, flags=re.S)
    s = s.replace(" – TK Vogel</title>", f" – {E(m['name'])}</title>", 1)
    s = re.sub(r"<meta name=apple-mobile-web-app-title content='[^']*'>", "", s, count=1)
    s = s.replace("</head>", kopf_teil() + f"<link rel=stylesheet href='/zusatz.css?v={stand_nr()}'></head>", 1)
    s = s.replace("TK Vogel denkt nach", f"{E(m['name'])} denkt nach")
    s = s.replace("api('/api/frage'", "api('/vogel/api/frage'").replace('api("/api/frage"', 'api("/vogel/api/frage"')   # Fragen auf Vogel-Seiten (z. B. iMac) gehen an TK Vogel
    return s
