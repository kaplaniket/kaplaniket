# TK Preisjäger – Quellen: holt Angebote von den Verkaufsseiten. Claude 26.11.2026
# Jede Quelle liefert eine Liste von dicts: quelle, titel, preis (Euro, float), url, bild, ort, text, zustand, versand, hinweis.
# Es werden nur Seiten abgefragt, die einen gewöhnlichen Abruf beantworten. Seiten, die automatische Abrufe sperren
# (eBay, Geizhals, Back Market …), werden nicht umgangen – für sie gibt es fertige Suchlinks (LINKS).
import gzip
import json
import re
import urllib.parse
import urllib.request
import zlib

from bs4 import BeautifulSoup

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15"
PREIS = re.compile(r"(\d{1,3}(?:\.\d{3})+|\d+)(?:,(\d{1,2}))?\s*€")


def holen(url, timeout=12):
    r = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "de-DE,de;q=0.9",
                                             "Accept": "text/html,application/xhtml+xml", "Accept-Encoding": "gzip, deflate"})
    with urllib.request.urlopen(r, timeout=timeout) as a:
        d = a.read()
        k = (a.headers.get("Content-Encoding") or "").lower()
    if k == "gzip":
        d = gzip.decompress(d)
    elif k == "deflate":
        d = zlib.decompress(d, -zlib.MAX_WBITS) if d[:1] != b"\x78" else zlib.decompress(d)
    return d.decode("utf-8", "replace")


def euro(text):
    m = PREIS.search(text or "")
    if not m:
        return None
    return float(m.group(1).replace(".", "") + "." + (m.group(2) or "0"))


def q(s):
    return urllib.parse.quote_plus(s)


def _klettern(el, stufen=7):
    p = el
    for _ in range(stufen):
        if PREIS.search(p.get_text(" ", strip=True)):
            return p
        if p.parent is None:
            break
        p = p.parent
    return None


def _ldliste(html):
    """Produkte aus schema.org-ItemList (Shpock, MediaMarkt, Saturn)."""
    aus = []
    for s in BeautifulSoup(html, "lxml").select('script[type="application/ld+json"]'):
        try:
            d = json.loads(s.string or "")
        except Exception:
            continue
        if not isinstance(d, dict) or d.get("@type") != "ItemList":
            continue
        for e in d.get("itemListElement", []):
            p = e.get("item") if isinstance(e.get("item"), dict) else e
            o = p.get("offers") or {}
            if isinstance(o, list):
                o = o[0] if o else {}
            try:
                preis = float(o.get("price"))
            except (TypeError, ValueError):
                continue
            bild = p.get("image")
            if isinstance(bild, list):
                bild = bild[0] if bild else ""
            aus.append({"titel": re.sub(r"\s+", " ", p.get("name") or "").strip(), "preis": preis, "url": p.get("url") or "",
                        "bild": bild or "", "text": (p.get("description") or "")[:400]})
    return aus


# ---------- Kleinanzeigen ----------
def _ka_seite(html):
    aus = []
    for a in BeautifulSoup(html, "lxml").select("article[data-adid]"):
        for x in a.select("script,svg"):
            x.decompose()
        stuecke = list(a.stripped_strings)
        ganz = " | ".join(stuecke)
        if "Gesuch" in stuecke:
            continue
        h = a.select_one("h3, h2")
        titel = h.get_text(" ", strip=True) if h else ""
        preis, vb = None, False
        for s in stuecke:
            if re.match(r"^\d[\d.]*\s*€(\s*VB)?$", s):
                preis, vb = euro(s), "VB" in s
                break
        ort = next((s for s in stuecke if re.match(r"^\d{5} \S", s)), "")
        zeit = next((s for s in stuecke if re.match(r"^(Heute|Gestern|\d\d\.\d\d\.\d{4})", s)), "")
        p = a.select_one("p")
        bild = a.select_one("img")
        hinweis = []
        if vb:
            hinweis.append("VB")
        if "Versand möglich" in ganz:
            hinweis.append("Versand möglich")
        elif "Nur Abholung" in ganz:
            hinweis.append("nur Abholung")
        if zeit:
            hinweis.append(zeit)
        aus.append({"quelle": "Kleinanzeigen", "titel": titel, "preis": preis, "url": "https://www.kleinanzeigen.de" + (a.get("data-href") or ""),
                    "bild": bild.get("src", "") if bild else "", "ort": ort, "text": p.get_text(" ", strip=True) if p else "",
                    "zustand": "gebraucht", "hinweis": " · ".join(hinweis)})
    return aus


def kleinanzeigen(anfrage, ab=None, seite=1):
    slug = re.sub(r"[^a-z0-9äöüß]+", "-", anfrage.lower()).strip("-")
    teile = ["anzeige:angebote"]
    if ab:
        teile += ["preis:%d:" % ab, "sortierung:preis"]
    if seite > 1:
        teile.append("seite:%d" % seite)
    return _ka_seite(holen("https://www.kleinanzeigen.de/s-%s/%s/k0" % ("/".join(teile), urllib.parse.quote(slug))))


# ---------- Vinted ----------
def vinted(anfrage, ab=None, seite=1):
    u = "https://www.vinted.de/catalog?search_text=" + q(anfrage)
    if ab:
        u += "&order=price_low_to_high&price_from=%d&currency=EUR" % ab
    b = BeautifulSoup(holen(u), "lxml")
    aus = []
    for a in b.select('a[data-testid$="--overlay-link"]'):
        t = a.get("title") or ""
        preise = re.findall(r"(\d+(?:\.\d\d)?) €", t)
        if not preise:
            continue
        titel = re.split(r", (?:Marke|Zustand|Größe): ", t)[0]
        zu = re.search(r"Zustand: ([^,]+)", t)
        kennung = a.get("data-testid", "").replace("--overlay-link", "")
        bild = b.select_one('[data-testid="%s--image--img"]' % kennung)
        mit_schutz = float(preise[1]) if len(preise) > 1 else None
        z = (zu.group(1) if zu else "").lower()
        aus.append({"quelle": "Vinted", "titel": titel, "preis": float(preise[0]), "url": "https://www.vinted.de" + a.get("href", "").split("?")[0],
                    "bild": bild.get("src", "") if bild else "", "ort": "", "text": "",
                    "zustand": "neu" if z.startswith("neu") else "gebraucht",
                    "hinweis": " · ".join(x for x in [zu.group(1) if zu else "", ("%.2f € mit Käuferschutz" % mit_schutz).replace(".", ",") if mit_schutz else "", "zzgl. Versand"] if x)})
    return aus


# ---------- Shpock ----------
def shpock(anfrage, ab=None, seite=1):
    return [dict(p, quelle="Shpock", zustand="gebraucht", ort="", hinweis="") for p in _ldliste(holen("https://www.shpock.com/de-de/results?q=" + q(anfrage)))]


# ---------- Hood ----------
def hood(anfrage, ab=None, seite=1):
    b = BeautifulSoup(holen("https://www.hood.de/suchergebnisse.htm?q=" + q(anfrage)), "lxml")
    aus, gesehen = [], set()
    for a in b.select('a[href*="hood.de/i/"]'):
        u = a.get("href")
        titel = a.get_text(" ", strip=True)
        if u in gesehen or len(titel) < 5:
            continue
        k = _klettern(a)
        if k is None:
            continue
        gesehen.add(u)
        text = k.get_text(" | ", strip=True)
        bild = k.select_one("img")
        aus.append({"quelle": "Hood", "titel": titel, "preis": euro(text), "url": u, "bild": (bild.get("src") or bild.get("data-src") or "") if bild else "",
                    "ort": "", "text": "", "zustand": "gebraucht" if re.search(r"gebraucht|sehr gut|wie neu", text, re.I) else "neu",
                    "versand": 0 if "Kostenloser Versand" in text else None,
                    "hinweis": "Versand kostenlos" if "Kostenloser Versand" in text else "zzgl. Versand"})
    return aus


# ---------- Amazon ----------
def amazon(anfrage, ab=None, seite=1):
    b = BeautifulSoup(holen("https://www.amazon.de/s?k=" + q(anfrage)), "lxml")
    aus = []
    for a in b.select('div[data-component-type="s-search-result"]'):
        text = a.get_text(" | ", strip=True)
        if "Gesponsert" in text or not a.get("data-asin"):
            continue
        h, p = a.select_one("h2"), a.select_one(".a-price .a-offscreen")
        if not h or not p:
            continue
        bild = a.select_one("img.s-image")
        m = re.search(r"Andere Angebote \| ([\d.,]+ €)", text)
        aus.append({"quelle": "Amazon", "titel": h.get_text(" ", strip=True), "preis": euro(p.get_text()),
                    "url": "https://www.amazon.de/dp/" + a["data-asin"], "bild": bild.get("src", "") if bild else "", "ort": "", "text": "",
                    "zustand": "neu", "hinweis": ("weitere Anbieter ab " + m.group(1)) if m else ""})
    return aus


# ---------- idealo (Preisvergleich Neuware/Händler) ----------
def idealo(anfrage, ab=None, seite=1):
    b = BeautifulSoup(holen("https://www.idealo.de/preisvergleich/MainSearchProductCategory.html?q=" + q(anfrage)), "lxml")
    aus = []
    for u in b.select('[data-testid="unit-product-summary"]'):
        k = _klettern(u)
        t, l = u.select_one('[data-testid="product-summary-title"]'), u.select_one("a[href]")
        if k is None or not t or not l:
            continue
        text = k.get_text(" | ", strip=True)
        m = re.search(r"(\d+) Angebote", text)
        bild = k.select_one("img")
        aus.append({"quelle": "idealo", "titel": t.get_text(" ", strip=True), "preis": euro(text[text.find("ab |"):] if "ab |" in text else text),
                    "url": l["href"], "bild": (bild.get("src") or "") if bild else "", "ort": "", "text": "",
                    "zustand": "gebraucht" if "gebraucht:" in text else "neu",
                    "hinweis": "günstigster von %s Händlern" % m.group(1) if m else "Händlerpreis"})
    return aus


# ---------- rebuy (geprüfte Gebrauchtware mit Garantie) ----------
STUFE = {"A1": "wie neu", "A2": "sehr gut", "A3": "gut", "A4": "stark genutzt"}


def rebuy(anfrage, ab=None, seite=1):
    html = holen("https://www.rebuy.de/kaufen/suchen?q=" + q(anfrage))
    aus, gesehen = [], set()
    for m in re.finditer(r'\{"id":(\d+),"category_id"', html):
        nr = m.group(1)
        if nr in gesehen:
            continue
        stueck = html[m.start():m.start() + 6000]
        name = re.search(r'"name":"((?:[^"\\]|\\.)*)"', stueck)
        slug = re.search(r'"product_sanitized_name":"([^"]+)"', stueck)
        kat = re.search(r'"category_sanitized_name":"([^"]+)"', stueck)
        bild = re.search(r'"clean_cover_path":"([^"]+)"', stueck)
        var = re.search(r'"variants":(\[.*?\])', stueck)
        if not (name and slug and var):
            continue
        try:
            varianten = [v for v in json.loads(var.group(1)) if v.get("quantity", 0) > 0 and v.get("price")]
            titel = json.loads('"' + name.group(1) + '"')
        except Exception:
            continue
        if not varianten:
            continue
        gesehen.add(nr)
        v = min(varianten, key=lambda x: x["price"])
        aus.append({"quelle": "rebuy", "titel": titel, "preis": v["price"] / 100.0,
                    "url": "https://www.rebuy.de/i,%s/%s/%s" % (nr, kat.group(1) if kat else "p", slug.group(1)),
                    "bild": ("https:/" + bild.group(1)) if bild else "", "ort": "", "text": "", "zustand": "aufbereitet",
                    "hinweis": "geprüft, Zustand „%s“, mit Garantie" % STUFE.get(v.get("label"), v.get("label", ""))})
    return aus


# ---------- MediaMarkt / Saturn ----------
def mediamarkt(anfrage, ab=None, seite=1):
    return [dict(p, quelle="MediaMarkt", zustand="neu", ort="", hinweis="") for p in _ldliste(holen("https://www.mediamarkt.de/de/search.html?query=" + q(anfrage)))]


def saturn(anfrage, ab=None, seite=1):
    return [dict(p, quelle="Saturn", zustand="neu", ort="", hinweis="") for p in _ldliste(holen("https://www.saturn.de/de/search.html?query=" + q(anfrage)))]


# name, funktion, art, zweiter Durchgang „ab Mindestpreis nach Preis sortiert“ möglich
QUELLEN = [
    ("Kleinanzeigen", kleinanzeigen, "privat", True),
    ("Vinted", vinted, "privat", True),
    ("Shpock", shpock, "privat", False),
    ("Hood", hood, "händler", False),
    ("rebuy", rebuy, "händler", False),
    ("Amazon", amazon, "händler", False),
    ("idealo", idealo, "händler", False),
    ("MediaMarkt", mediamarkt, "händler", False),
    ("Saturn", saturn, "händler", False),
]

# Seiten, die automatische Abrufe sperren: nur fertige Suchlinks zum Selbst-Öffnen
LINKS = [
    ("eBay (Sofort-Kaufen, günstigste zuerst)", "https://www.ebay.de/sch/i.html?_nkw={q}&LH_BIN=1&_sop=15"),
    ("eBay (Auktionen, bald endend)", "https://www.ebay.de/sch/i.html?_nkw={q}&LH_Auction=1&_sop=1"),
    ("Geizhals", "https://geizhals.de/?fs={q}"),
    ("Back Market", "https://www.backmarket.de/de-de/search?q={q}"),
    ("refurbed", "https://www.refurbed.de/?q={q}"),
    ("Google Shopping", "https://www.google.de/search?tbm=shop&q={q}"),
]


def links(anfrage):
    return [{"name": n, "url": u.format(q=q(anfrage))} for n, u in LINKS]
