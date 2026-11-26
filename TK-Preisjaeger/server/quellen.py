# TK Preisjäger – Quellen: holt Angebote von den Verkaufsseiten. Claude 26.11.2026
# Jede Quelle liefert eine Liste von dicts: quelle, titel, preis (Euro, float), url, bild, ort, text, zustand, versand, hinweis.
# Es werden nur Seiten abgefragt, die einen gewöhnlichen Abruf beantworten. Seiten, die automatische Abrufe sperren
# (eBay, Geizhals, Back Market …), werden nicht umgangen – für sie gibt es fertige Suchlinks (LINKS).
import gzip
import json
import re
import time
import urllib.parse
import urllib.request
import zlib

from bs4 import BeautifulSoup

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15"
PREIS = re.compile(r"(\d{1,3}(?:\.\d{3})+|\d+)(?:,(\d{1,2}))?\s*€")


def holen(url, timeout=12, kopf=None):
    r = urllib.request.Request(url, headers=dict({"User-Agent": UA, "Accept-Language": "de-DE,de;q=0.9",
                                                  "Accept": "text/html,application/xhtml+xml", "Accept-Encoding": "gzip, deflate"}, **(kopf or {})))
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


GESAMT = {}      # Quelle -> Gesamtzahl der Anzeigen zur letzten Suche (soweit die Seite sie nennt)


_orte = {}


def ka_ort(plz):
    """Ortskennung von Kleinanzeigen zu einer Postleitzahl (für die Umkreissuche); None, wenn unbekannt."""
    plz = re.sub(r"\D", "", str(plz))[:5]
    if len(plz) != 5:
        return None
    if plz not in _orte:
        try:
            d = json.loads(holen("https://www.kleinanzeigen.de/s-ort-empfehlungen.json?query=" + plz, 8,
                                 {"X-Requested-With": "XMLHttpRequest", "Accept": "application/json"}))
            _orte[plz] = next((k.strip("_") for k, v in d.items() if k.strip("_").isdigit() and k != "_0" and str(v).startswith(plz)), None)
        except Exception:
            return None
    return _orte[plz]


def kleinanzeigen(anfrage, ab=None, seite=1, ort=None):
    """ort = (Ortskennung, Umkreis in km) schränkt auf Anzeigen im Umkreis ein."""
    slug = re.sub(r"[^a-z0-9äöüß]+", "-", anfrage.lower()).strip("-")
    teile = ["anzeige:angebote"]
    if ab:
        teile += ["preis:%d:" % ab, "sortierung:preis"]
    if seite > 1:
        teile.append("seite:%d" % seite)
    html = holen("https://www.kleinanzeigen.de/s-%s/%s/k0%s" % ("/".join(teile), urllib.parse.quote(slug), ("l%sr%d" % ort) if ort else ""))
    if not ab and seite == 1:      # „1 - 25 von 8.667“: wie viele Anzeigen es insgesamt gibt
        m = re.search(r"\d+\s*-\s*\d+\s*von\s*([\d.]+)", html)
        if m:
            GESAMT["Kleinanzeigen"] = int(m.group(1).replace(".", ""))
    return _ka_seite(html)


# ---------- Vinted ----------
def vinted(anfrage, ab=None, seite=1):
    u = "https://www.vinted.de/catalog?search_text=" + q(anfrage)
    if ab:
        u += "&order=price_low_to_high&price_from=%d&currency=EUR" % ab
    if seite > 1:
        u += "&page=%d" % seite
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
        aus.append({"quelle": "Vinted", "titel": titel, "preis": mit_schutz or float(preise[0]), "url": "https://www.vinted.de" + a.get("href", "").split("?")[0],
                    "bild": bild.get("src", "") if bild else "", "ort": "", "text": "",
                    "zustand": "neu" if z.startswith("neu") else "gebraucht",
                    "hinweis": " · ".join(x for x in [zu.group(1) if zu else "", "inkl. Käuferschutz" if mit_schutz else "", "zzgl. Versand"] if x)})
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
    for versuch in (1, 2):      # Amazon antwortet nicht jedes Mal: ein zweiter Versuch
        b = BeautifulSoup(holen("https://www.amazon.de/s?k=" + q(anfrage)), "lxml")
        if b.select_one('div[data-component-type="s-search-result"]'):
            break
        if versuch == 2:
            raise RuntimeError("Amazon hat nicht geantwortet")
        time.sleep(1.5)
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
# „Web“ (offene Websuche nach weiteren Händlern) wird am Dateiende angehängt, weil die Funktion erst dort steht.

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


# ---------- Angaben von einer Angebotsseite lesen (für den Produktvergleich) ----------
LESBAR = ("amazon.de", "mediamarkt.de", "saturn.de", "idealo.de", "rebuy.de", "kleinanzeigen.de", "hood.de", "shpock.com", "vinted.de")


def seitentext(url, laenge=2800):
    """Sichtbarer Text einer Angebotsseite (nur von den bekannten Verkaufsseiten), gekürzt. Bei Fehler ''."""
    try:
        host = urllib.parse.urlparse(url).hostname or ""
        if not url.startswith("https://") or not any(host == h or host.endswith("." + h) for h in LESBAR):
            return ""
        b = BeautifulSoup(holen(url, 10), "lxml")
        for x in b.select("script,style,noscript,svg,nav,footer,header,form,iframe"):
            x.decompose()
        kern_el = b.select_one("#feature-bullets, #productOverview_feature_div") if "amazon." in host else None
        teile = []
        if kern_el is not None:
            t = b.select_one("#productTitle")
            teile.append((t.get_text(" ", strip=True) + ". ") if t else "")
            teile += [x.get_text(" ", strip=True) for x in b.select("#productOverview_feature_div, #feature-bullets, #productDescription")]
        else:
            teile.append((b.select_one("main") or b.body or b).get_text(" ", strip=True))
        return re.sub(r"\s+", " ", " ".join(teile).replace("\u00ad", "")).strip()[:laenge]
    except Exception:
        return ""


# ---------- Einzelne Händlerangebote einer idealo-Produktseite (idealo listet nur geprüfte Shops) ----------
def idealo_angebote(url):
    """[{shop, titel, preis, url, hinweis}] – alle Händler, die idealo zu diesem Produkt führt."""
    b = BeautifulSoup(holen(url, 10), "lxml")
    aus = []
    for li in b.select(".productOffers-listItem"):
        try:
            m = json.loads(li.get("data-mtrx-click") or "{}")
            shop, preis = m.get("shop_name"), float(m["products"][0]["price"])
        except Exception:
            continue
        a = li.select_one('a[class*="productOffers-listItemTitle"]')
        text = re.sub(r"\s+", " ", li.get_text(" ", strip=True).replace("­", ""))
        gesamt = re.search(r"([\d.]+,\d\d) € inkl\. Versand", text)
        note = re.search(r"(\d,\d) (\d+) Shop-Details", text)
        hinweis = ["über idealo"]
        if gesamt:
            hinweis.append("inkl. Versand " + gesamt.group(1) + " €")
        if note:
            hinweis.append("Shop-Bewertung %s (%s)" % (note.group(1), note.group(2)))
        aus.append({"shop": shop, "titel": a.get_text(" ", strip=True).replace("­", "")[:160] if a else "", "preis": preis,
                    "url": "https://www.idealo.de" + a.get("href") if a and a.get("href", "").startswith("/") else url,
                    "versand": (euro(gesamt.group(1) + " €") - preis) if gesamt else None, "hinweis": " · ".join(hinweis)})
    return aus


# ---------- Offene Websuche: weitere Händler finden und den Preis direkt von der Shop-Seite lesen ----------
# Bekannte, seit Jahren etablierte Händler in Deutschland (Auswahl). Alles andere gilt als „unbekannt“ und wird getrennt behandelt.
VERTRAUT = {
    "otto.de", "alternate.de", "notebooksbilliger.de", "cyberport.de", "galaxus.de", "conrad.de", "proshop.de", "computeruniverse.net",
    "mindfactory.de", "coolblue.de", "expert.de", "euronics.de", "lidl.de", "kaufland.de", "aldi-onlineshop.de", "obi.de", "hornbach.de",
    "bauhaus.info", "toom.de", "hagebau.de", "globus-baumarkt.de", "thomann.de", "musicstore.de", "ikea.com", "tchibo.de", "zalando.de",
    "aboutyou.de", "douglas.de", "dm.de", "rossmann.de", "baur.de", "quelle.de", "neckermann.de", "apple.com", "samsung.com", "dyson.de",
    "bosch-home.com", "philips.de", "sony.de", "lg.com", "medion.com", "reichelt.de", "voelkner.de", "pollin.de", "caseking.de", "jacob.de",
    "office-partner.de", "pearl.de", "elv.com", "boettcher.de", "bueroshop24.de", "decathlon.de", "sportscheck.com", "bergfreunde.de",
    "fahrrad-xxl.de", "bike-discount.de", "rosebikes.de", "fahrrad.de", "bike24.de", "tink.de", "smyths-toys.com", "mytoys.de", "babymarkt.de",
    "thalia.de", "hugendubel.de", "buecher.de", "weltbild.de", "medimops.de", "momox-shop.de", "backmarket.de", "refurbed.de", "asgoodasnew.de",
    "clevertronic.de", "swappie.com", "afbshop.de", "gravis.de", "o2online.de", "telekom.de", "vodafone.de", "1und1.de", "mediamarkt.de",
    "saturn.de", "amazon.de", "ebay.de", "kleinanzeigen.de", "idealo.de", "xxxlutz.de", "hoeffner.de", "moebel.de", "home24.de", "wayfair.de",
    "westwing.de", "manufactum.de", "globetrotter.de", "karstadt.de", "galeria.de", "breuninger.com", "christ.de", "fielmann.de",
    "shop-apotheke.com", "docmorris.de", "zooplus.de", "fressnapf.de", "atu.de", "kfzteile24.de", "reifendirekt.de", "tedi.com", "action.com",
    "norma24.de", "netto-online.de", "penny.de", "rewe.de", "edeka.de", "real.de", "ao.de", "tecedo.de", "technikdirekt.de", "elektroshopwagner.de",
    "berlet.de", "electronic4you.de", "euronics.de", "ep.de", "medimax.de", "hifiklubben.de", "teufel.de", "nubert.de", "foto-erhardt.de",
    "calumetphoto.de", "fotokoch.de", "contorion.de", "svh24.de", "toolineo.de", "wuerth.de", "hilti.de", "makita.de", "kaercher.com", "gardena.com",
}
# schon über eigene Quellen abgedeckt oder keine Shops
_KEIN_SHOP = ("amazon.", "idealo.", "kleinanzeigen.", "ebay.", "vinted.", "shpock.", "hood.", "rebuy.", "mediamarkt.", "saturn.", "youtube.",
              "wikipedia.", "mydealz.", "dealsieger.", "pinterest.", "facebook.", "instagram.", "tiktok.", "reddit.", "chip.de", "computerbild.",
              "testberichte.", "geizhals.", "billiger.de", "guenstiger.de", "check24.", "preisvergleich.", "google.", "bing.", "duckduckgo.",
              "trustpilot.", "x.com", "twitter.", "heise.de", "gutefrage.", "stiftung-warentest", "test.de", "ciao.", "ladenzeile.", "shopping.com")


def domain(url):
    h = (urllib.parse.urlparse(url).hostname or "").lower()
    return h[4:] if h.startswith("www.") else h


def _kern_domain(d):
    t = d.split(".")
    return ".".join(t[-2:]) if len(t) >= 2 else d


def _ld_produkt(html):
    """Erstes Produkt mit Preis aus schema.org-Daten der Seite: (name, preis, bild, verfügbar) oder None."""
    b = BeautifulSoup(html, "lxml")
    funde = []

    def lauf(d):
        if isinstance(d, list):
            for x in d:
                lauf(x)
        elif isinstance(d, dict):
            t = d.get("@type")
            if "Product" in (t if isinstance(t, list) else [t]):
                funde.append(d)
            for k in ("@graph", "mainEntity", "mainEntityOfPage"):
                if k in d:
                    lauf(d[k])

    for s in b.select('script[type="application/ld+json"]'):
        try:
            lauf(json.loads(s.string or ""))
        except Exception:
            pass

    def zahl(x):
        try:
            x = str(x).replace("\xa0", "").replace("€", "").strip()
            if "," in x:
                x = x.replace(".", "").replace(",", ".")
            return float(x)
        except Exception:
            return None

    for p in funde:
        o = p.get("offers") or {}
        if isinstance(o, list):
            o = o[0] if o else {}
        if (o.get("priceCurrency") or "EUR") != "EUR":
            continue
        preis = zahl(o.get("price") if o.get("price") is not None else o.get("lowPrice"))
        if preis and preis > 0:
            bild = p.get("image")
            bild = bild[0] if isinstance(bild, list) and bild else bild
            bild = bild.get("url") if isinstance(bild, dict) else bild
            return re.sub(r"\s+", " ", str(p.get("name") or "")).strip()[:160], preis, bild or "", "OutOfStock" not in str(o.get("availability"))
    m = b.select_one('meta[property="product:price:amount"], meta[property="og:price:amount"]')
    t = b.select_one('meta[property="og:title"]')
    if m and t and zahl(m.get("content")):
        return t.get("content", "")[:160], zahl(m.get("content")), "", True
    return None


def websuche(anfrage, ab=None, seite=1):
    """Sucht im offenen Netz nach Shops, die das Produkt führen, und liest Name und Preis von der Shop-Seite.
    Vertrauen: 'bekannt' (Liste VERTRAUT) oder 'unbekannt' – die Einstufung 'idealo'/'hersteller' und das Aussieben macht der Server."""
    if ab or seite > 1:
        return []
    from concurrent.futures import ThreadPoolExecutor
    b = BeautifulSoup(holen("https://html.duckduckgo.com/html/?q=" + q(anfrage + " kaufen") + "&kl=de-de", 10), "lxml")
    ziele, gesehen = [], set()
    for a in b.select("a.result__a"):
        u = a.get("href", "")
        d = domain(u)
        if not u.startswith("https://") or not d or d in gesehen or any(k in d for k in _KEIN_SHOP) or u.lower().endswith(".pdf"):
            continue
        gesehen.add(d)
        ziele.append(u)

    def lesen(u):
        try:
            html = holen(u, 8)
        except Exception:
            return None
        p = _ld_produkt(html)
        if not p or not p[3]:
            return None
        d = domain(u)
        return {"quelle": "Web", "shop": d, "titel": p[0], "preis": p[1], "url": u, "bild": p[2] if str(p[2]).startswith("http") else "", "ort": "", "text": "",
                "zustand": "neu", "vertrauen": "bekannt" if (d in VERTRAUT or _kern_domain(d) in VERTRAUT) else "unbekannt",
                "merkmale": {"impressum": bool(re.search(r"(?i)impressum", html)), "siegel": bool(re.search(r"(?i)trusted\s*shops|ehi\s*gepr|t[üu]v\s*s[üu]d\s*safer", html))},
                "hinweis": "Shop: " + d}

    with ThreadPoolExecutor(max_workers=8) as topf:
        return [x for x in topf.map(lesen, ziele[:10]) if x]


QUELLEN.append(("Web", websuche, "händler", False))


# ---------- Originaltext des Anbieters von der Angebotsseite (für das Details-Fenster) ----------
def anbietertext(url):
    """(Beschreibungstext des Anbieters, Angaben zum Verkäufer) – beides '' wenn nicht lesbar."""
    try:
        host = urllib.parse.urlparse(url).hostname or ""
        if not url.startswith("https://") or not any(host == h or host.endswith("." + h) for h in LESBAR):
            return "", ""
        b = BeautifulSoup(holen(url, 10), "lxml")
        text, verk = "", ""
        el = b.select_one("#viewad-description-text") or b.select_one('[itemprop="description"]') or b.select_one("#feature-bullets") or b.select_one("#productDescription")
        if el is not None:
            for br in el.select("br"):
                br.replace_with("\n")
            text = el.get_text("\n" if el.name in ("ul", "div") and el.get("id") == "feature-bullets" else "", strip=False)
        if not text.strip():      # schema.org-Beschreibung oder Kurzbeschreibung der Seite
            for s in b.select('script[type="application/ld+json"]'):
                try:
                    d = json.loads(s.string or "")
                except Exception:
                    continue
                for x in (d if isinstance(d, list) else [d]):
                    if isinstance(x, dict) and x.get("description") and len(str(x["description"])) > len(text):
                        text = str(x["description"])
            if not text.strip():
                m = b.select_one('meta[property="og:description"], meta[name="description"]')
                text = m.get("content", "") if m else ""
        v = b.select_one("#viewad-contact")
        if v is not None:
            verk = re.sub(r"\s+", " ", v.get_text(" ", strip=True))
            verk = re.split(r"Nachricht schreiben|Anbieter folgen|Folgen", verk)[0].strip()[:220]
        text = re.sub(r"[ \t]+", " ", text.replace("­", "")).strip()
        return re.sub(r"\n\s*\n\s*\n+", "\n\n", text)[:4000], verk
    except Exception:
        return "", ""


# ---------- Neueste Anzeigen im Umkreis ohne Suchwort (für „alles im Umkreis nach Schnäppchen durchsuchen“) ----------
def kleinanzeigen_umkreis(ort, seite=1, elektronik=False, ab=60):
    """ort = (Ortskennung, km). Neueste Angebote ab einem Mindestpreis – quer durch alle Kategorien oder nur Elektronik."""
    teile = ["anzeige:angebote", "preis:%d:" % ab] + (["seite:%d" % seite] if seite > 1 else [])
    if elektronik:
        url = "https://www.kleinanzeigen.de/s-elektronik/%s/c161l%sr%d" % ("/".join(teile), ort[0], ort[1])
    else:
        url = "https://www.kleinanzeigen.de/s-%s/k0l%sr%d" % ("/".join(teile), ort[0], ort[1])
    return _ka_seite(holen(url))
