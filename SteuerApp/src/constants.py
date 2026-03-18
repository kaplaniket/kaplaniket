"""
Konstanten und Konfiguration für die Steuer-App
"""

APP_NAME = "SteuerApp – Steuererklärung Assistent"
APP_VERSION = "2.0"

# Unterstützte Dateitypen
SUPPORTED_EXTENSIONS = {
    'pdf': '.pdf',
    'bild': ['.jpg', '.jpeg', '.png', '.tiff', '.tif', '.bmp', '.gif', '.heic', '.heif', '.webp'],
    'word': ['.doc', '.docx', '.odt', '.rtf'],
    'excel': ['.xls', '.xlsx', '.ods', '.csv'],
    'text': ['.txt', '.xml', '.html', '.htm'],
    'sonstige': ['.eml', '.msg', '.zip']
}

ALL_EXTENSIONS = (
    ['.pdf'] +
    ['.jpg', '.jpeg', '.png', '.tiff', '.tif', '.bmp', '.gif', '.heic', '.heif', '.webp'] +
    ['.doc', '.docx', '.odt', '.rtf'] +
    ['.xls', '.xlsx', '.ods', '.csv'] +
    ['.txt', '.xml', '.html', '.htm'] +
    ['.eml', '.msg']
)

# ─── Dokumenttypen ───────────────────────────────────────────────
DOK_TYPEN = {
    'rechnung':             'Rechnung',
    'quittung':             'Quittung/Kassenbon',
    'gehaltsabrechnung':    'Gehaltsabrechnung',
    'lohnsteuerbescheid':   'Lohnsteuerbescheinigung',
    'steuerbescheid':       'Steuerbescheid',
    'versicherung':         'Versicherung',
    'kontoauszug':          'Kontoauszug',
    'spende':               'Spendenquittung',
    'arzt':                 'Arzt/Medizin',
    'fahrtkosten':          'Fahrtkosten',
    'fortbildung':          'Fortbildung/Schulung',
    'buero':                'Büro/Arbeitsmittel',
    'miete':                'Miete/Wohnen',
    'bank':                 'Bank/Finanzinstitut',
    'sonstiges':            'Sonstiges',
}

# ─── Steuer-Kategorien (Anlage-Struktur) ─────────────────────────
STEUER_KATEGORIEN = {
    'EINNAHMEN': {
        'label': '📈 Einnahmen',
        'subcats': {
            'gehalt':       {'label': 'Gehalt / Lohn (Anlage N)',        'anlage': 'N'},
            'selbstaendig': {'label': 'Selbständigkeit (Anlage S)',       'anlage': 'S'},
            'gewerbe':      {'label': 'Gewerbebetrieb (Anlage G)',        'anlage': 'G'},
            'vermietung':   {'label': 'Vermietung & Verpachtung (Anl. V)','anlage': 'V'},
            'kapital':      {'label': 'Kapitalerträge (Anlage KAP)',      'anlage': 'KAP'},
            'rente':        {'label': 'Renten (Anlage R)',                'anlage': 'R'},
            'sonstige_ein': {'label': 'Sonstige Einnahmen (Anlage SO)',   'anlage': 'SO'},
        }
    },
    'WERBUNGSKOSTEN': {
        'label': '💼 Werbungskosten',
        'subcats': {
            'fahrtkosten':   {'label': 'Fahrtkosten (Pendlerpauschale)',  'anlage': 'N'},
            'arbeitsmittel': {'label': 'Arbeitsmittel & Bürobedarf',      'anlage': 'N'},
            'fortbildung':   {'label': 'Fortbildung & Fachliteratur',     'anlage': 'N'},
            'homeoffice':    {'label': 'Homeoffice / Arbeitszimmer',      'anlage': 'N'},
            'beruf_sons':    {'label': 'Sonstige Werbungskosten',         'anlage': 'N'},
        }
    },
    'BETRIEBSAUSGABEN': {
        'label': '🏭 Betriebsausgaben (EÜR)',
        'subcats': {
            'buerokosten':   {'label': 'Büro- & Raumkosten',             'anlage': 'EÜR'},
            'kfz':           {'label': 'KFZ-Kosten',                     'anlage': 'EÜR'},
            'reise':         {'label': 'Reise- & Bewirtungskosten',      'anlage': 'EÜR'},
            'personal':      {'label': 'Personalkosten',                  'anlage': 'EÜR'},
            'afa':           {'label': 'Abschreibungen (AfA)',            'anlage': 'EÜR'},
            'versich_betr':  {'label': 'Betriebliche Versicherungen',     'anlage': 'EÜR'},
            'sonstige_ba':   {'label': 'Sonstige Betriebsausgaben',       'anlage': 'EÜR'},
        }
    },
    'SONDERAUSGABEN': {
        'label': '📋 Sonderausgaben',
        'subcats': {
            'versicherung':  {'label': 'Versicherungsbeiträge',           'anlage': 'SA'},
            'altersvorsorge':{'label': 'Altersvorsorge (Riester/Rürup)',  'anlage': 'AV'},
            'spenden':       {'label': 'Spenden & Mitgliedsbeiträge',     'anlage': 'SA'},
            'kirchensteuer': {'label': 'Kirchensteuer',                   'anlage': 'SA'},
            'sonstige_sa':   {'label': 'Sonstige Sonderausgaben',         'anlage': 'SA'},
        }
    },
    'AUSSERGEWOEHNLICH': {
        'label': '🏥 Außergewöhnliche Belastungen',
        'subcats': {
            'krankheit':     {'label': 'Krankheitskosten',                'anlage': 'AB'},
            'pflege':        {'label': 'Pflegekosten',                    'anlage': 'AB'},
            'behinderung':   {'label': 'Behinderungsbedingte Kosten',     'anlage': 'AB'},
            'sonstige_ab':   {'label': 'Sonstige außergewöhnl. Belast.',  'anlage': 'AB'},
        }
    },
    'HAUSHALTSNAHE': {
        'label': '🏠 Haushaltsnahe Ausgaben',
        'subcats': {
            'handwerker':    {'label': 'Handwerkerleistungen (§35a)',     'anlage': 'HA'},
            'haushaltsnahe': {'label': 'Haushaltsnahe Dienstleistungen',  'anlage': 'HA'},
        }
    },
}

# ─── Klassifizierungs-Schlüsselwörter (Deutsch + Englisch) ───────
KLASSIFIZIERUNG_KEYWORDS = {
    'gehaltsabrechnung': [
        'gehaltsabrechnung', 'lohnabrechnung', 'entgeltabrechnung',
        'bruttolohn', 'nettolohn', 'bruttogehalt', 'nettogehalt',
        'sozialversicherung', 'krankenversicherung beitrag', 'rentenversicherung',
        'lohnsteuer', 'kirchensteuer', 'solidaritätszuschlag',
        'arbeitnehmer', 'arbeitgeber', 'steuerklasse',
    ],
    'lohnsteuerbescheid': [
        'lohnsteuerbescheinigung', 'elektronische lohnsteuerbescheinigung',
        'arbeitslohn', 'einbehaltene lohnsteuer',
    ],
    'steuerbescheid': [
        'steuerbescheid', 'einkommensteuerbescheid', 'körperschaftsteuerbescheid',
        'festsetzung', 'finanzamt', 'steuernummer', 'steuererstattung',
        'nachzahlung', 'vorauszahlung',
    ],
    'versicherung': [
        'versicherung', 'versicherungsprämie', 'versicherungsbeitrag',
        'krankenversicherung', 'haftpflicht', 'hausratversicherung',
        'lebensversicherung', 'berufsunfähigkeit', 'unfallversicherung',
        'kfz-versicherung', 'rechtsschutz', 'zahnzusatz',
        'allianz', 'aok', 'barmer', 'tkk', 'techniker krankenkasse',
        'huk coburg', 'ergo', 'axa', 'generali', 'debeka',
        'beitragsrechnung', 'policennummer', 'versicherungsschein',
    ],
    'rechnung': [
        'rechnung', 'invoice', 'rechnungsnummer', 'rechnungsdatum',
        'zahlbar bis', 'fällig', 'netto', 'mwst', 'mehrwertsteuer',
        'ust', 'umsatzsteuer', 'eur', '€', 'gesamt',
        'lieferant', 'lieferschein', 'pos ', 'artikel',
    ],
    'quittung': [
        'quittung', 'kassenbon', 'kassenbeleg', 'beleg', 'bon',
        'receipt', 'kassiererin', 'kassierer', 'vielen dank',
        'summe', 'bar', 'karte', 'ec-karte',
    ],
    'kontoauszug': [
        'kontoauszug', 'kontoübersicht', 'girokonto', 'sparkonto',
        'iban', 'bic', 'buchung', 'gutschrift', 'lastschrift',
        'überweisungsauftrag', 'saldo', 'habensaldo',
        'sparkasse', 'volksbank', 'commerzbank', 'deutsche bank',
        'ing', 'dkb', 'postbank', 'comdirect',
    ],
    'spende': [
        'spende', 'spendenquittung', 'zuwendungsbestätigung',
        'gemeinnützig', 'wohltätig', 'verein', 'stiftung',
        'rotes kreuz', 'unicef', 'wwf', 'greenpeace', 'caritas',
    ],
    'arzt': [
        'arzt', 'arztrechnung', 'krankenhaus', 'apotheke',
        'rezept', 'medikament', 'behandlung', 'honorar',
        'privatarzt', 'zahnarzt', 'physiotherapie', 'psychotherapie',
        'röntgen', 'labor', 'praxis', 'klinik',
    ],
    'fahrtkosten': [
        'fahrtkosten', 'reisekosten', 'pendler', 'ticket',
        'bahnticket', 'db ', 'deutsche bahn', 'bvg', 'mvv',
        'hvv', 'rnv', 'nahverkehr', 'monatsticket', 'jobticket',
        'tankquittung', 'tankbeleg', 'kraftstoff', 'benzin',
        'diesel', 'parkticket', 'parkschein',
    ],
    'fortbildung': [
        'fortbildung', 'weiterbildung', 'schulung', 'kurs',
        'seminar', 'workshop', 'training', 'zertifikat',
        'fachliteratur', 'fachbuch', 'studium', 'fernstudium',
        'udemy', 'coursera', 'linkedin learning',
    ],
    'buero': [
        'bürobedarf', 'arbeitsmittel', 'computer', 'laptop',
        'monitor', 'tastatur', 'drucker', 'tinte', 'papier',
        'aktenschrank', 'schreibtisch', 'bürostuhl',
        'software', 'lizenz', 'microsoft office', 'adobe',
        'handy', 'telefon', 'internet', 'dsl',
    ],
    'miete': [
        'miete', 'mietzahlung', 'kaltmiete', 'warmmiete', 'nebenkosten',
        'betriebskosten', 'hausgeld', 'vermieter', 'mieter',
        'mietvertrag', 'mietquittung', 'wohnungsmiete',
    ],
}

# Keyword → Steuer-Kategorie Mapping
DOK_ZU_STEUER = {
    'gehaltsabrechnung':  ('EINNAHMEN', 'gehalt'),
    'lohnsteuerbescheid': ('EINNAHMEN', 'gehalt'),
    'steuerbescheid':     ('SONDERAUSGABEN', 'sonstige_sa'),
    'versicherung':       ('SONDERAUSGABEN', 'versicherung'),
    'rechnung':           ('BETRIEBSAUSGABEN', 'sonstige_ba'),
    'quittung':           ('BETRIEBSAUSGABEN', 'sonstige_ba'),
    'kontoauszug':        ('EINNAHMEN', 'sonstige_ein'),
    'spende':             ('SONDERAUSGABEN', 'spenden'),
    'arzt':               ('AUSSERGEWOEHNLICH', 'krankheit'),
    'fahrtkosten':        ('WERBUNGSKOSTEN', 'fahrtkosten'),
    'fortbildung':        ('WERBUNGSKOSTEN', 'fortbildung'),
    'buero':              ('WERBUNGSKOSTEN', 'arbeitsmittel'),
    'miete':              ('HAUSHALTSNAHE', 'haushaltsnahe'),
    'sonstiges':          ('SONDERAUSGABEN', 'sonstige_sa'),
}

FARBEN = {
    'bg':          '#1e1e2e',
    'bg2':         '#313244',
    'bg3':         '#45475a',
    'fg':          '#cdd6f4',
    'fg2':         '#a6adc8',
    'accent':      '#89b4fa',
    'green':       '#a6e3a1',
    'red':         '#f38ba8',
    'yellow':      '#f9e2af',
    'orange':      '#fab387',
    'purple':      '#cba6f7',
    'teal':        '#94e2d5',
    'white':       '#ffffff',
    'success':     '#40a02b',
    'warning':     '#df8e1d',
    'error':       '#d20f39',
}
