"""
Dokument-Klassifizierer: Bestimmt Typ und Steuer-Kategorie anhand von Text-Keywords
"""

import re
from typing import Tuple, Dict
from .constants import KLASSIFIZIERUNG_KEYWORDS, DOK_ZU_STEUER


class DokumentKlassifizierer:

    def klassifiziere(self, text: str, dateiname: str = '') -> Tuple[str, str, str]:
        """
        Gibt (dok_typ, steuer_haupt, steuer_sub) zurück
        """
        text_lower = (text + ' ' + dateiname).lower()

        # Keyword-Scores berechnen
        scores: Dict[str, int] = {}
        for typ, keywords in KLASSIFIZIERUNG_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw in text_lower)
            if score > 0:
                scores[typ] = score

        # Dateiname-Bonus (stärkere Gewichtung)
        dateiname_lower = dateiname.lower()
        for typ, keywords in KLASSIFIZIERUNG_KEYWORDS.items():
            bonus = sum(2 for kw in keywords if kw in dateiname_lower)
            scores[typ] = scores.get(typ, 0) + bonus

        # Spezielle Muster-Erkennung
        muster_typ = self._muster_erkennung(text_lower, dateiname_lower)
        if muster_typ:
            scores[muster_typ] = scores.get(muster_typ, 0) + 5

        if not scores:
            return 'sonstiges', 'SONDERAUSGABEN', 'sonstige_sa'

        bester_typ = max(scores, key=scores.get)
        haupt, sub = DOK_ZU_STEUER.get(
            bester_typ, ('SONDERAUSGABEN', 'sonstige_sa')
        )
        return bester_typ, haupt, sub

    def _muster_erkennung(self, text: str, dateiname: str) -> str:
        """Regex-basierte Erkennung besonderer Dokumenttypen"""

        # Lohnsteuerbescheinigung
        if re.search(r'lohnsteuer\w*bescheinigung', text):
            return 'lohnsteuerbescheid'

        # Steuerbescheid
        if re.search(r'(einkommensteuer|körperschaftsteuer|gewerbesteuer)\w*bescheid', text):
            return 'steuerbescheid'

        # IBAN → Kontoauszug oder Rechnung
        if re.search(r'\bIBAN\s*:?\s*[A-Z]{2}\d{2}', text, re.IGNORECASE):
            if re.search(r'(kontoauszug|buchung|saldo|habensaldo)', text):
                return 'kontoauszug'

        # Rezept / Apotheke
        if re.search(r'(apotheke|rezept|arzneimittel|pharma)', text):
            return 'arzt'

        # Tankquittung
        if re.search(r'(liter|diesel|benzin|super e10|kraftstoff|tankstelle)', text):
            return 'fahrtkosten'

        # Versicherungspolice
        if re.search(r'(policennummer|versicherungsschein|prämienzahlung)', text):
            return 'versicherung'

        # Spendenquittung
        if re.search(r'(zuwendungsbestätigung|steuerbegünstigte)', text):
            return 'spende'

        return ''

    def schlage_steuer_vor(self, text: str, dok_typ: str,
                           betrag: float = 0) -> Tuple[str, str]:
        """
        Verfeinerte Steuer-Kategorie-Empfehlung basierend auf Kontext
        """
        text_lower = text.lower()

        # Arbeitnehmer vs. Selbständige unterscheiden
        if dok_typ in ('rechnung', 'quittung'):
            if any(kw in text_lower for kw in ['büro', 'arbeitsmittel', 'laptop',
                                                'software', 'telefon']):
                return 'WERBUNGSKOSTEN', 'arbeitsmittel'
            if any(kw in text_lower for kw in ['reise', 'hotel', 'übernachtung',
                                                'flug', 'bahn']):
                return 'WERBUNGSKOSTEN', 'beruf_sons'
            if any(kw in text_lower for kw in ['handwerker', 'renovierung',
                                                'reparatur', 'maler']):
                return 'HAUSHALTSNAHE', 'handwerker'

        # Versicherungen kategorisieren
        if dok_typ == 'versicherung':
            if any(kw in text_lower for kw in ['kranken', 'health', 'gesundheit']):
                return 'SONDERAUSGABEN', 'versicherung'
            if any(kw in text_lower for kw in ['rente', 'riester', 'rürup',
                                                'altersvorsorge']):
                return 'SONDERAUSGABEN', 'altersvorsorge'
            if any(kw in text_lower for kw in ['betriebs', 'haftpflicht firma',
                                                'berufshaft']):
                return 'BETRIEBSAUSGABEN', 'versich_betr'

        return DOK_ZU_STEUER.get(dok_typ, ('SONDERAUSGABEN', 'sonstige_sa'))
