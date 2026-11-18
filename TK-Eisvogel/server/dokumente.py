#!/usr/bin/env python3
"""TK KI – Dokumente selbst finden und lesen (16.11.2026, Auftrag Tekin: „selbstständig alles lesen und erledigen“).
Sucht in der Ablage (PiSpeicher/Ablage, iCloud-Spiegel Disk1) nach Dateinamen und im Volltext (speicher.db + Inhaltsindex),
liest die Treffer: vorhandener Text (Inhaltsindex/pdftotext), sonst Texterkennung (tesseract, deutsch) – Ergebnis wird gemerkt.
Nur lesend. Test: python3 dokumente.py "Wann ist der TÜV für den GLK fällig?"
"""
import hashlib, json, os, re, sqlite3, subprocess, sys, time, unicodedata
from pathlib import Path

H = Path.home()
WURZELN = [Path("/mnt/PiSpeicher/Ablage"), Path("/media/tekin/Disk1/icloud-dokumente")]
INHALT = H / ".cache/fundorte/inhalt"
SDB = H / "gedaechtnis/speicher.db"
OCR = Path("/media/tekin/Disk2/TK-KI/index/ocr"); OCR.mkdir(parents=True, exist_ok=True)
LISTE = Path("/media/tekin/Disk2/TK-KI/index/dateiliste.txt")
ENDUNG = {".pdf", ".jpg", ".jpeg", ".png", ".heic", ".tif", ".tiff", ".txt", ".docx", ".odt"}
GEHEIM = re.compile(r"(?i)passw|kennwort|\bpin\b|\btan\b|puk")
STOPP = set("wann wie wo was wer ist sind mein meine meinen meiner der die das den dem des ein eine einen für mit von zum zur bei auf aus und oder noch schon fällig bis ab im in an es gibt hat habe hast liegt steht sag mir bitte zeig such finde dann diese dieser beiden".split())
DOKWORT = re.compile(r"(?i)schein|zulassung|tüv|tuev|\bhu\b|hauptunters|brief|bescheid|rechnung|vertrag|police|versicherung|kündig|scan|ausweis|pass\b|urkunde|zeugnis|bescheinig|beleg|quittung|kontoauszug|abrechnung|steuer|nachweis|formular|antrag|dokument|datei|unterlage|ordner|pdf|foto|bild|fahrzeug|kennzeichen|fin\b|führerschein|mietvertrag|nebenkosten|grundbesitz|meldebest")
SYN = {"tüv": ["tüv", "hu", "hauptuntersuchung", "prüfbescheinigung", "fahrzeugschein", "zulassung"], "hu": ["hu", "hauptuntersuchung", "fahrzeugschein", "prüfbescheinigung"],
       "anhänger": ["anhaenger", "anhänger"], "motorrad": ["leichtkraftrad"],
       "kfz-schein": ["fahrzeugschein", "zulassung"], "fahrzeugschein": ["fahrzeugschein", "zulassungsbescheinigung"]}

try: SYN.update(json.load(open(Path(__file__).resolve().parent / "privat" / "dokumente-synonyme.json", encoding="utf-8")))   # Kennzeichen nur auf dem HP
except Exception: pass

def relevant(frage):
    return bool(DOKWORT.search(frage))

import threading
_LISTE_LAEUFT = threading.Lock()
_LISTE_MERK = {"zeit": 0, "liste": []}

def _liste_bauen():
    alle = []
    for w in WURZELN:
        if w.is_dir():
            for o, ds, fs in os.walk(w):
                ds[:] = [d for d in ds if not d.startswith(".") and "Archiv_Alt" not in d]
                alle += [os.path.join(o, f) for f in fs if Path(f).suffix.lower() in ENDUNG]
    if alle:   # eine leere Liste (Platte nicht eingehängt) überschreibt die gute nicht
        tmp = LISTE.with_suffix(".tmp"); tmp.write_text("\n".join(alle)); os.replace(tmp, LISTE)
    return alle

def _liste():
    """Dateiliste der Ablage. Claude 17.11.2026: Eine Frage wartet nie mehr auf das Durchlaufen der Platten –
    die vorhandene Liste gilt sofort, ist sie älter als 30 Min., wird sie im Hintergrund erneuert."""
    alt = time.time() - LISTE.stat().st_mtime if LISTE.exists() else None
    if alt is None:
        return _liste_bauen()
    if alt > 1800 and _LISTE_LAEUFT.acquire(blocking=False):
        def lauf():
            try: _liste_bauen()
            finally: _LISTE_LAEUFT.release()
        threading.Thread(target=lauf, daemon=True).start()
    mt = LISTE.stat().st_mtime
    if _LISTE_MERK["zeit"] != mt:
        _LISTE_MERK.update(zeit=mt, liste=LISTE.read_text(errors="ignore").splitlines())
    return _LISTE_MERK["liste"]

def begriffe(frage):
    f = frage.lower()
    w = [x for x in re.findall(r"[a-zäöüß0-9][a-zäöüß0-9\-]{1,}", f) if x not in STOPP]
    aus = set(w)
    for x in list(w):
        for k, v in SYN.items():
            if x.startswith(k[:4]) and (x == k or len(x) > 3): aus.update(v)
    return [x for x in aus if len(x) >= 2]

def suchen(frage, n=5):
    b = begriffe(frage)
    if not b: return []
    punkte = {}
    seen_name = {}
    for p in _liste():
        pn = unicodedata.normalize("NFC", p)       # zerlegte Umlaute (Mac/iCloud) wie normale behandeln, sonst findet „Ölwechsel“ nichts
        name = pn.lower().replace("_", " ").replace("ä", "ae").replace("ö", "oe").replace("ü", "ue")
        roh = pn.lower().replace("_", " ")
        bn, bn2 = os.path.basename(roh), os.path.basename(name)
        def drin(t, s):
            return re.search(r"(?<![a-z0-9])" + re.escape(t) + r"(?![a-z0-9])", s) if len(t) < 4 else t in s
        s = sum(2 if drin(t, bn) or drin(t.replace("ä", "ae").replace("ö", "oe").replace("ü", "ue"), bn2) else (1 if drin(t, roh) else 0) for t in b)
        if s >= 2:
            k = os.path.basename(p)   # gleiche Datei in mehreren Spiegeln nur einmal
            if k in seen_name and punkte.get(seen_name[k], 0) >= s: continue
            seen_name[k] = p; punkte[p] = s
    # Volltext (Inhaltsindex über speicher.db)
    try:
        c = sqlite3.connect(f"file:{SDB}?mode=ro", uri=True, timeout=3)
        q = " OR ".join('"' + x.replace('"', '') + '"' for x in b if len(x) >= 3)
        for (pfad,) in c.execute("select pfad from dokumente where dokumente match ? and pfad not like '%Obsidian%' order by rank limit 15", (q,)):
            if Path(pfad).suffix.lower() in ENDUNG: punkte[pfad] = punkte.get(pfad, 0) + 1.5
        c.close()
    except Exception:
        pass
    # neuere Dateien leicht bevorzugen
    def wert(p):
        try: alter = (time.time() - os.path.getmtime(p)) / (365 * 86400)
        except Exception: alter = 9
        return punkte[p] + max(0, 1 - alter / 5)
    aus, namen = [], set()      # dieselbe Datei aus zwei Spiegeln oder als Kopie („…_1.pdf“) nur einmal lesen (Claude 17.11.2026)
    for p in sorted(punkte, key=wert, reverse=True):
        k = re.sub(r"(_\d{1,2}| \(\d+\)| kopie)?(\.[a-z0-9]+)$", r"\2", unicodedata.normalize("NFC", os.path.basename(p)).lower())   # NFC: Mac schreibt Umlaute zerlegt
        if k in namen: continue
        namen.add(k); aus.append(p)
        if len(aus) >= n: break
    return aus

def lesen(pfad, max_zeichen=2500):
    """Text einer Datei: Inhaltsindex → pdftotext → Texterkennung (gemerkt)."""
    t = ""
    ix = INHALT / (pfad.lstrip("/") + ".txt")
    if ix.exists(): t = ix.read_text(errors="ignore")
    elif pfad.lower().endswith(".txt"): t = Path(pfad).read_text(errors="ignore")
    elif pfad.lower().endswith(".pdf"):
        t = subprocess.run(["pdftotext", "-layout", "-l", "4", pfad, "-"], capture_output=True, text=True, timeout=30).stdout
    if len(re.sub(r"\s", "", t)) < 80 and Path(pfad).suffix.lower() in {".pdf", ".jpg", ".jpeg", ".png", ".tif", ".tiff", ".heic"}:
        h = hashlib.sha1((pfad + str(os.path.getmtime(pfad))).encode()).hexdigest()
        cache = OCR / (h + ".txt")
        if cache.exists():
            t = cache.read_text(errors="ignore")
        else:
            tmp = Path(f"/tmp/tkki-ocr-{h[:8]}-{os.getpid()}-{threading.get_ident()}"); tmp.mkdir(exist_ok=True)
            try:
                bilder = []
                if pfad.lower().endswith(".pdf"):
                    subprocess.run(["nice", "-n", "19", "pdftoppm", "-r", "170", "-l", "2", "-gray", "-png", pfad, str(tmp / "s")], timeout=90)
                    bilder = sorted(tmp.glob("s*.png"))
                else:
                    bilder = [Path(pfad)]
                # Texterkennung mit niedrigster Priorität und einem Kern: sie läuft oft noch, während das lokale Modell antwortet,
                # und nahm ihm vorher alle Kerne weg (gemessen 17.11.2026: Antwort 93 s statt 15 s)
                t = "\n".join(subprocess.run(["nice", "-n", "19", "tesseract", str(b), "-", "-l", "deu", "--psm", "3"], capture_output=True, text=True, timeout=240,
                                             env=dict(os.environ, OMP_THREAD_LIMIT="1")).stdout for b in bilder)
                cache.write_text(t)
            finally:
                subprocess.run(["rm", "-rf", str(tmp)])
    t = "\n".join(z for z in t.splitlines() if z.strip() and not GEHEIM.search(z))
    return re.sub(r"[ \t]{3,}", "  ", t)[:max_zeichen]

def kontext(frage, n=4, frist=12):
    """Die besten Dateien lesen – gleichzeitig und höchstens `frist` Sekunden (Claude 17.11.2026).
    Vorher nacheinander ohne Grenze: vier ungelesene Scans konnten eine Frage über eine Minute aufhalten.
    Was in der Zeit nicht fertig wird, liest die Texterkennung im Hintergrund zu Ende und ist beim nächsten Mal sofort da."""
    from concurrent.futures import ThreadPoolExecutor, wait
    pfade = suchen(frage, n)
    if not pfade: return ""
    ex = ThreadPoolExecutor(max_workers=len(pfade))
    auftraege = {p: ex.submit(lesen, p) for p in pfade}
    wait(list(auftraege.values()), timeout=frist)
    ex.shutdown(wait=False)
    teile = []
    for p in pfade:
        a = auftraege[p]
        if not a.done(): tx = "(Texterkennung läuft noch – diese Datei ist in etwa einer Minute lesbar)"
        else:
            try: tx = a.result() or "(kein lesbarer Text)"
            except Exception as e: tx = f"(nicht lesbar: {e})"
        teile.append(f"### Datei: {p}\n{tx}")
    return "\n\n".join(teile)

if __name__ == "__main__":
    f = " ".join(sys.argv[1:]); t0 = time.time()
    print("relevant:", relevant(f), "| Begriffe:", begriffe(f))
    for p in suchen(f): print(" -", p)
    print(kontext(f)[:3000]); print(f"({time.time()-t0:.1f} s)")
