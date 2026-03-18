"""
Daten-Extraktor: Extrahiert Beträge, Datums- und Firmenangaben aus Dokumenttexten
"""

import re
from datetime import datetime
from typing import Optional, Tuple, List


class DatenExtraktor:

    # ─── Betragsextraktion ────────────────────────────────────────

    def extrahiere_betrag(self, text: str) -> Optional[float]:
        """
        Findet den wichtigsten Geldbetrag im Text.
        Bevorzugt 'Gesamt', 'Total', 'Endbetrag', 'Brutto'-Zeilen.
        """
        # Prioritäts-Muster (Summen-Zeilen)
        prioritaets_muster = [
            r'(?:gesamt|total|endbetrag|rechnungsbetrag|gesamtbetrag|'
            r'zu zahlen|zahlbar|summe|brutto)\s*:?\s*'
            r'([1-9]\d{0,6}[.,]\d{2})\s*(?:€|EUR)?',

            r'(?:nettobetrag|netto)\s*:?\s*'
            r'([1-9]\d{0,6}[.,]\d{2})\s*(?:€|EUR)?',

            # Betrag nach EUR/€
            r'([1-9]\d{0,6}[.,]\d{2})\s*(?:€|EUR)\b',
            r'(?:€|EUR)\s*([1-9]\d{0,6}[.,]\d{2})',
        ]

        for muster in prioritaets_muster:
            treffer = re.findall(muster, text, re.IGNORECASE)
            if treffer:
                # Größten Betrag wählen (wahrscheinlich der Gesamtbetrag)
                betraege = [self._parse_betrag(t) for t in treffer]
                betraege = [b for b in betraege if b and 0.01 <= b <= 9_999_999]
                if betraege:
                    return max(betraege)

        # Allgemeines Muster
        alle = re.findall(
            r'\b([1-9]\d{0,6}(?:[.,]\d{3})*[.,]\d{2})\b', text
        )
        betraege = [self._parse_betrag(t) for t in alle]
        betraege = [b for b in betraege if b and 0.50 <= b <= 999_999]
        if betraege:
            return sorted(betraege)[-1]

        return None

    def extrahiere_alle_betraege(self, text: str) -> List[float]:
        """Alle Beträge im Text"""
        treffer = re.findall(
            r'\b([1-9]\d{0,6}(?:[.,]\d{3})*[.,]\d{2})\b', text
        )
        ergebnis = []
        for t in treffer:
            b = self._parse_betrag(t)
            if b and 0.01 <= b <= 9_999_999:
                ergebnis.append(b)
        return sorted(set(ergebnis))

    def _parse_betrag(self, text: str) -> Optional[float]:
        """'1.234,56' oder '1,234.56' → float"""
        if not text:
            return None
        t = text.strip()
        # Deutsches Format: 1.234,56
        if re.match(r'^\d{1,3}(\.\d{3})*(,\d{2})$', t):
            t = t.replace('.', '').replace(',', '.')
        # Englisches Format: 1,234.56
        elif re.match(r'^\d{1,3}(,\d{3})*(\.\d{2})$', t):
            t = t.replace(',', '')
        # Einfach: 1234,56 oder 1234.56
        else:
            t = t.replace(',', '.')
        try:
            return float(t)
        except ValueError:
            return None

    # ─── Datumsextraktion ─────────────────────────────────────────

    def extrahiere_datum(self, text: str) -> Tuple[Optional[str], Optional[int]]:
        """
        Gibt (datum_iso, steuerjahr) zurück.
        datum_iso: 'YYYY-MM-DD' oder None
        """
        muster_liste = [
            # TT.MM.JJJJ
            (r'\b(\d{1,2})\.(\d{1,2})\.(20\d{2})\b', '%d.%m.%Y'),
            # TT/MM/JJJJ
            (r'\b(\d{1,2})/(\d{1,2})/(20\d{2})\b', None),
            # JJJJ-MM-TT (ISO)
            (r'\b(20\d{2})-(\d{2})-(\d{2})\b', 'iso'),
            # TT. Monatsname JJJJ
            (r'\b(\d{1,2})\.\s*(Januar|Februar|März|April|Mai|Juni|'
             r'Juli|August|September|Oktober|November|Dezember)\s*(20\d{2})\b', 'de_lang'),
            # Monatsname JJJJ
            (r'\b(Januar|Februar|März|April|Mai|Juni|'
             r'Juli|August|September|Oktober|November|Dezember)\s+(20\d{2})\b', 'de_monat'),
        ]

        monate_de = {
            'januar': 1, 'februar': 2, 'märz': 3, 'april': 4,
            'mai': 5, 'juni': 6, 'juli': 7, 'august': 8,
            'september': 9, 'oktober': 10, 'november': 11, 'dezember': 12
        }

        kandidaten = []

        for muster, fmt in muster_liste:
            for m in re.finditer(muster, text, re.IGNORECASE):
                try:
                    if fmt == 'iso':
                        dt = datetime(int(m.group(1)), int(m.group(2)),
                                      int(m.group(3)))
                        kandidaten.append(dt)
                    elif fmt == 'de_lang':
                        monat = monate_de.get(m.group(2).lower(), 0)
                        if monat:
                            dt = datetime(int(m.group(3)), monat, int(m.group(1)))
                            kandidaten.append(dt)
                    elif fmt == 'de_monat':
                        monat = monate_de.get(m.group(1).lower(), 0)
                        if monat:
                            dt = datetime(int(m.group(2)), monat, 1)
                            kandidaten.append(dt)
                    else:
                        g = m.groups()
                        dt = datetime(int(g[2]), int(g[1]), int(g[0]))
                        kandidaten.append(dt)
                except (ValueError, IndexError):
                    continue

        # Plausibilitätsprüfung: nur Daten 2000-heute
        heute = datetime.now()
        plausibel = [d for d in kandidaten
                     if datetime(2000, 1, 1) <= d <= heute]

        if not plausibel:
            return None, None

        # Datum wählen: Rechnungsdatum bevorzugen (frühestes Datum im Dokument)
        datum = min(plausibel)
        return datum.strftime('%Y-%m-%d'), datum.year

    # ─── Lieferant / Absender ─────────────────────────────────────

    def extrahiere_lieferant(self, text: str) -> Optional[str]:
        """
        Versucht Firmenname / Absender zu extrahieren.
        """
        zeilen = [z.strip() for z in text.split('\n') if z.strip()]

        # Bekannte Firmen
        bekannte_firmen = [
            'Amazon', 'IKEA', 'MediaMarkt', 'Saturn', 'Aldi', 'Lidl',
            'Rewe', 'Edeka', 'Kaufland', 'dm ', 'Rossmann', 'Müller',
            'Telekom', 'Vodafone', 'O2', '1&1', 'Unitymedia',
            'Sparkasse', 'Volksbank', 'DKB', 'ING', 'Commerzbank',
            'Deutsche Bank', 'Postbank', 'Comdirect',
            'Allianz', 'AXA', 'ERGO', 'Generali', 'HUK', 'Debeka',
            'AOK', 'Barmer', 'TK ', 'Techniker Krankenkasse',
            'Deutsche Bahn', 'DB ', 'Lufthansa', 'Ryanair',
            'Apple', 'Microsoft', 'Adobe', 'Google',
            'Finanzamt', 'Bundeszentralamt',
        ]

        text_zeile1 = ' '.join(zeilen[:5])
        for firma in bekannte_firmen:
            if firma.lower() in text_zeile1.lower():
                return firma.strip()

        # Muster: "Von:" oder "Absender:" oder erste nicht-leere Zeile
        for muster in [r'(?:von|absender|firma|gesellschaft)\s*:?\s*(.+)',
                       r'(?:an|to|rechnungsempfänger)\s*:?\s*(.+)']:
            m = re.search(muster, text[:500], re.IGNORECASE)
            if m:
                name = m.group(1).strip()
                if 5 <= len(name) <= 60:
                    return name

        # Erste Zeile als Fallback (oft Firmenname)
        for zeile in zeilen[:3]:
            if (5 <= len(zeile) <= 60 and
                    not re.match(r'^[\d\s./:]+$', zeile) and
                    not re.search(r'(rechnung|quittung|beleg|datum)', zeile, re.I)):
                return zeile

        return None

    # ─── Steuerjahr aus Text ───────────────────────────────────────

    def extrahiere_steuerjahr(self, text: str, dateipfad: str = '',
                               dateidatum_jahr: int = None) -> int:
        """Bestimmt das wahrscheinlichste Steuerjahr"""
        datum_str, jahr = self.extrahiere_datum(text)
        if jahr and 2000 <= jahr <= datetime.now().year:
            return jahr

        # Jahr aus Dateipfad/Name
        if dateipfad:
            jahre_im_pfad = re.findall(r'20\d{2}', dateipfad)
            if jahre_im_pfad:
                return int(jahre_im_pfad[-1])

        # Fallback: Änderungsdatum der Datei
        if dateidatum_jahr and 2000 <= dateidatum_jahr <= datetime.now().year:
            return dateidatum_jahr

        return datetime.now().year
