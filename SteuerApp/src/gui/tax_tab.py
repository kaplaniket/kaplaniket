"""
Steuer-Tab: Steuerliche Übersicht, EÜR, Anlage-Helfer
"""

import tkinter as tk
from tkinter import ttk
import sys
from typing import Optional

from ..constants import FARBEN, STEUER_KATEGORIEN
from .. import database as db


class TaxTab:
    def __init__(self, notebook, app):
        self.app = app
        self.frame = ttk.Frame(notebook)
        self.aktuell_jahr: Optional[int] = None
        self._erstelle_gui()

    def _erstelle_gui(self):
        haupt = tk.Frame(self.frame, bg=FARBEN['bg'])
        haupt.pack(fill='both', expand=True, padx=0, pady=0)

        # ── Notebook für Unter-Tabs ──────────────────────────────
        self.sub_nb = ttk.Notebook(haupt)
        self.sub_nb.pack(fill='both', expand=True)

        # Tab 1: Kategorien-Übersicht
        self.kat_frame = tk.Frame(self.sub_nb, bg=FARBEN['bg'])
        self.sub_nb.add(self.kat_frame, text="  📊 Kategorien  ")

        # Tab 2: EÜR
        self.eur_frame = tk.Frame(self.sub_nb, bg=FARBEN['bg'])
        self.sub_nb.add(self.eur_frame, text="  📄 EÜR  ")

        # Tab 3: Anlage N (Arbeitnehmer)
        self.anlage_n_frame = tk.Frame(self.sub_nb, bg=FARBEN['bg'])
        self.sub_nb.add(self.anlage_n_frame, text="  👔 Anlage N  ")

        # Tab 4: Hinweise
        self.tipps_frame = tk.Frame(self.sub_nb, bg=FARBEN['bg'])
        self.sub_nb.add(self.tipps_frame, text="  💡 Hinweise  ")

        self._erstelle_kategorien_tab()
        self._erstelle_eur_tab()
        self._erstelle_anlage_n_tab()
        self._erstelle_tipps_tab()

    def _erstelle_kategorien_tab(self):
        # Toolbar
        toolbar = tk.Frame(self.kat_frame, bg=FARBEN['bg3'], height=44)
        toolbar.pack(fill='x')
        toolbar.pack_propagate(False)

        tk.Label(toolbar, text="Steuerliche Kategorien",
                 bg=FARBEN['bg3'], fg=FARBEN['accent'],
                 font=('SF Pro Display', 13, 'bold') if sys.platform == 'darwin'
                       else ('Segoe UI', 11, 'bold')
                 ).pack(side='left', padx=16, pady=10)

        # Haupt-Bereich mit Scroll
        canvas_frame = tk.Frame(self.kat_frame, bg=FARBEN['bg'])
        canvas_frame.pack(fill='both', expand=True)

        canvas = tk.Canvas(canvas_frame, bg=FARBEN['bg'],
                            highlightthickness=0)
        scrollbar = ttk.Scrollbar(canvas_frame, orient='vertical',
                                   command=canvas.yview)
        self.kat_scroll_frame = tk.Frame(canvas, bg=FARBEN['bg'])

        self.kat_scroll_frame.bind('<Configure>', lambda e: canvas.configure(
            scrollregion=canvas.bbox('all')
        ))
        canvas.create_window((0, 0), window=self.kat_scroll_frame, anchor='nw')
        canvas.configure(yscrollcommand=scrollbar.set)

        scrollbar.pack(side='right', fill='y')
        canvas.pack(side='left', fill='both', expand=True)

        # Mausrad-Scrollen
        def _mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), 'units')
        canvas.bind_all('<MouseWheel>', _mousewheel)

        self.kat_widgets = {}

    def _erstelle_eur_tab(self):
        # EÜR-Tabelle
        tk.Label(
            self.eur_frame,
            text="Einnahmen-Überschuss-Rechnung (EÜR)",
            bg=FARBEN['bg'], fg=FARBEN['accent'],
            font=('SF Pro Display', 14, 'bold') if sys.platform == 'darwin'
                  else ('Segoe UI', 12, 'bold')
        ).pack(anchor='w', padx=20, pady=(16, 8))

        tk.Label(
            self.eur_frame,
            text="Vereinfachte EÜR basierend auf erkannten Dokumenten",
            bg=FARBEN['bg'], fg=FARBEN['fg2'],
            font=('SF Pro Text', 10) if sys.platform == 'darwin'
                  else ('Segoe UI', 9)
        ).pack(anchor='w', padx=20, pady=(0, 12))

        spalten = ('position', 'anzahl', 'betrag')
        self.eur_tabelle = ttk.Treeview(
            self.eur_frame, columns=spalten, show='headings', height=20
        )
        self.eur_tabelle.heading('position', text='Position')
        self.eur_tabelle.heading('anzahl',   text='Belege')
        self.eur_tabelle.heading('betrag',   text='Betrag (€)')
        self.eur_tabelle.column('position', width=400, anchor='w')
        self.eur_tabelle.column('anzahl',   width=80,  anchor='center')
        self.eur_tabelle.column('betrag',   width=140, anchor='e')

        self.eur_tabelle.tag_configure('einnahmen',  background='#1a2e1a', foreground=FARBEN['green'])
        self.eur_tabelle.tag_configure('ausgaben',   background='#2e1a1a', foreground=FARBEN['red'])
        self.eur_tabelle.tag_configure('gesamt',     background='#1a1a3a', foreground=FARBEN['accent'],
                                        font=('SF Pro Text', 11, 'bold') if sys.platform == 'darwin'
                                              else ('Segoe UI', 10, 'bold'))
        self.eur_tabelle.tag_configure('kategorie',  background='#1a1a2e', foreground=FARBEN['fg2'])
        self.eur_tabelle.tag_configure('trennlinie', background=FARBEN['bg3'])

        eur_scroll = ttk.Scrollbar(self.eur_frame, orient='vertical',
                                    command=self.eur_tabelle.yview)
        self.eur_tabelle.configure(yscrollcommand=eur_scroll.set)
        eur_scroll.pack(side='right', fill='y', padx=(0, 12), pady=12)
        self.eur_tabelle.pack(fill='both', expand=True, padx=(20, 0), pady=12)

    def _erstelle_anlage_n_tab(self):
        tk.Label(
            self.anlage_n_frame,
            text="Anlage N – Arbeitnehmer",
            bg=FARBEN['bg'], fg=FARBEN['accent'],
            font=('SF Pro Display', 14, 'bold') if sys.platform == 'darwin'
                  else ('Segoe UI', 12, 'bold')
        ).pack(anchor='w', padx=20, pady=(16, 4))

        tk.Label(
            self.anlage_n_frame,
            text="Zusammenfassung der relevanten Dokumente für die Anlage N",
            bg=FARBEN['bg'], fg=FARBEN['fg2']
        ).pack(anchor='w', padx=20, pady=(0, 16))

        # Canvas mit Scroll
        container = tk.Frame(self.anlage_n_frame, bg=FARBEN['bg'])
        container.pack(fill='both', expand=True, padx=20)

        self.anlage_n_text = tk.Text(
            container,
            bg='#1a1a2e', fg=FARBEN['fg'],
            relief='flat', wrap='word',
            font=('SF Pro Text', 11) if sys.platform == 'darwin'
                  else ('Segoe UI', 10),
            padx=12, pady=10, state='disabled'
        )
        anlage_scroll = ttk.Scrollbar(container, orient='vertical',
                                       command=self.anlage_n_text.yview)
        self.anlage_n_text.configure(yscrollcommand=anlage_scroll.set)
        anlage_scroll.pack(side='right', fill='y')
        self.anlage_n_text.pack(fill='both', expand=True)

        self.anlage_n_text.tag_configure('header',
                                          foreground=FARBEN['accent'],
                                          font=('SF Pro Text', 12, 'bold') if sys.platform == 'darwin'
                                                else ('Segoe UI', 11, 'bold'))
        self.anlage_n_text.tag_configure('subheader',
                                          foreground=FARBEN['fg2'],
                                          font=('SF Pro Text', 10, 'bold') if sys.platform == 'darwin'
                                                else ('Segoe UI', 9, 'bold'))
        self.anlage_n_text.tag_configure('betrag',
                                          foreground=FARBEN['green'],
                                          font=('SF Pro Text', 11, 'bold') if sys.platform == 'darwin'
                                                else ('Segoe UI', 10, 'bold'))
        self.anlage_n_text.tag_configure('hinweis',
                                          foreground=FARBEN['yellow'])
        self.anlage_n_text.tag_configure('normal', foreground=FARBEN['fg'])

    def _erstelle_tipps_tab(self):
        text_widget = tk.Text(
            self.tipps_frame,
            bg='#1a1a2e', fg=FARBEN['fg'],
            relief='flat', wrap='word',
            font=('SF Pro Text', 11) if sys.platform == 'darwin'
                  else ('Segoe UI', 10),
            padx=20, pady=16, state='normal'
        )
        scroll = ttk.Scrollbar(self.tipps_frame, orient='vertical',
                                command=text_widget.yview)
        text_widget.configure(yscrollcommand=scroll.set)
        scroll.pack(side='right', fill='y')
        text_widget.pack(fill='both', expand=True)

        text_widget.tag_configure('h1', foreground=FARBEN['accent'],
                                   font=('SF Pro Display', 14, 'bold') if sys.platform == 'darwin'
                                         else ('Segoe UI', 12, 'bold'))
        text_widget.tag_configure('h2', foreground=FARBEN['teal'],
                                   font=('SF Pro Text', 12, 'bold') if sys.platform == 'darwin'
                                         else ('Segoe UI', 10, 'bold'))
        text_widget.tag_configure('bullet', foreground=FARBEN['fg'])
        text_widget.tag_configure('tipp', foreground=FARBEN['yellow'])
        text_widget.tag_configure('wichtig', foreground=FARBEN['red'])

        hinweise = [
            ("💡 Wichtige Hinweise für Ihre Steuererklärung", 'h1'),
            ("", 'bullet'),
            ("Allgemeines", 'h2'),
            ("• Belege müssen 10 Jahre aufbewahrt werden (Unternehmer), 2 Jahre privat.", 'bullet'),
            ("• Die Abgabefrist für die Steuererklärung ist der 31. Juli des Folgejahres.", 'bullet'),
            ("• Mit Steuerberater verlängert sich die Frist auf den 28./29. Februar des übernächsten Jahres.", 'bullet'),
            ("", 'bullet'),
            ("Arbeitnehmer (Anlage N)", 'h2'),
            ("• Werbungskostenpauschale: 1.230 € (2023) / 1.230 € (2024) – wird automatisch abgezogen.", 'bullet'),
            ("• Fahrtkosten: 0,30 € pro km für die ersten 20 km, 0,38 € ab km 21.", 'bullet'),
            ("• Homeoffice-Pauschale: 6 € pro Tag, max. 1.260 € pro Jahr (210 Tage).", 'bullet'),
            ("• Arbeitsmittel bis 952 € (inkl. MwSt.) können sofort abgesetzt werden.", 'bullet'),
            ("", 'bullet'),
            ("Sonderausgaben", 'h2'),
            ("• Kirchensteuer ist vollständig absetzbar (Anlage Sonderausgaben).", 'bullet'),
            ("• Kranken- und Pflegeversicherung: Basisabsicherung vollständig absetzbar.", 'bullet'),
            ("• Spenden bis 300 € ohne Nachweis (Sammelbestätigung reicht).", 'bullet'),
            ("• Riester-Rente: Beiträge bis 2.100 € pro Jahr absetzbar.", 'bullet'),
            ("", 'bullet'),
            ("Außergewöhnliche Belastungen", 'h2'),
            ("• Krankheitskosten: Nur der Teil über der zumutbaren Eigenbelastung.", 'bullet'),
            ("• Zumutbare Eigenbelastung: 1-7% des Gesamtbetrags der Einkünfte (je nach Einkommen/Familienstand).", 'bullet'),
            ("• Behinderung: Pauschbeträge je nach Grad der Behinderung (384-7.400 €).", 'bullet'),
            ("", 'bullet'),
            ("Haushaltsnahe Ausgaben (§35a EStG)", 'h2'),
            ("• Handwerkerleistungen: 20% der Lohnkosten, max. 1.200 € Steuerersparnis.", 'bullet'),
            ("• Haushaltsnahe Dienstleistungen: 20%, max. 4.000 € Steuerersparnis.", 'bullet'),
            ("⚠️  Wichtig: Barzahlung wird nicht anerkannt! Nur Überweisung.", 'wichtig'),
            ("", 'bullet'),
            ("Selbständige / Freiberufler (Anlage S/G)", 'h2'),
            ("• EÜR (Einnahmen-Überschuss-Rechnung) bei Einnahmen unter 600.000 €/Jahr.", 'bullet'),
            ("• Alle Betriebsausgaben vollständig absetzbar.", 'bullet'),
            ("• Fahrtkosten: 0,30 € pro km mit privatem PKW oder tatsächliche KFZ-Kosten.", 'bullet'),
            ("• Bewirtungskosten: Nur 70% absetzbar, vollständige Dokumentation nötig.", 'bullet'),
            ("", 'bullet'),
            ("🔍 Tipps für diese App", 'h1'),
            ("• Überprüfen Sie alle automatisch erkannten Beträge und Kategorien.", 'tipp'),
            ("• Markieren Sie geprüfte Dokumente mit ✓ (Leertaste oder Rechtsklick).", 'tipp'),
            ("• Nutzen Sie die Notiz-Funktion für besondere Erklärungen.", 'tipp'),
            ("• Erstellen Sie das 'Steuerberater-Paket' für eine übersichtliche Übergabe.", 'tipp'),
        ]

        for text, tag in hinweise:
            text_widget.insert('end', text + '\n', tag)

        text_widget.configure(state='disabled')

    # ─── Aktualisierung ───────────────────────────────────────────

    def aktualisiere(self, steuerjahr=None):
        self.aktuell_jahr = steuerjahr
        statistiken = db.get_statistiken(steuerjahr=steuerjahr)
        dokumente = db.get_dokumente(steuerjahr=steuerjahr)

        self._aktualisiere_kategorien(statistiken)
        self._aktualisiere_eur(dokumente, statistiken)
        self._aktualisiere_anlage_n(dokumente)

    def _aktualisiere_kategorien(self, statistiken: dict):
        # Alle alten Widgets entfernen
        for widget in self.kat_scroll_frame.winfo_children():
            widget.destroy()

        gesamt_einnahmen = sum(
            v.get('summe', 0)
            for v in statistiken.get('nach_steuer', {}).get('EINNAHMEN', {}).values()
        )
        gesamt_ausgaben = sum(
            sum(v.get('summe', 0) for v in subs.values())
            for haupt, subs in statistiken.get('nach_steuer', {}).items()
            if haupt != 'EINNAHMEN'
        )

        # Zusammenfassung oben
        summen_frame = tk.Frame(self.kat_scroll_frame, bg=FARBEN['bg3'],
                                 relief='flat')
        summen_frame.pack(fill='x', padx=16, pady=(16, 8))

        for text, betrag, farbe in [
            ("Einnahmen gesamt", gesamt_einnahmen, FARBEN['green']),
            ("Ausgaben gesamt",  gesamt_ausgaben,  FARBEN['red']),
            ("Differenz (EÜR)", gesamt_einnahmen - gesamt_ausgaben,
             FARBEN['green'] if gesamt_einnahmen >= gesamt_ausgaben else FARBEN['red']),
        ]:
            zeile = tk.Frame(summen_frame, bg=FARBEN['bg3'])
            zeile.pack(fill='x', padx=16, pady=6)
            tk.Label(zeile, text=text, bg=FARBEN['bg3'],
                     fg=FARBEN['fg'],
                     font=('SF Pro Text', 12) if sys.platform == 'darwin'
                           else ('Segoe UI', 10),
                     width=24, anchor='w').pack(side='left')
            tk.Label(zeile, text=f"{betrag:,.2f} €",
                     bg=FARBEN['bg3'], fg=farbe,
                     font=('SF Pro Text', 13, 'bold') if sys.platform == 'darwin'
                           else ('Segoe UI', 11, 'bold')).pack(side='right', padx=16)

        # Kategorien-Karten
        nach_steuer = statistiken.get('nach_steuer', {})

        for haupt_key, haupt_data in STEUER_KATEGORIEN.items():
            haupt_stats = nach_steuer.get(haupt_key, {})
            gesamt_haupt = sum(v.get('summe', 0) for v in haupt_stats.values())
            anzahl_haupt = sum(v.get('anzahl', 0) for v in haupt_stats.values())

            # Kategorie-Karte
            karte = tk.Frame(self.kat_scroll_frame, bg=FARBEN['bg2'],
                              relief='flat')
            karte.pack(fill='x', padx=16, pady=4)

            # Header
            header = tk.Frame(karte, bg=FARBEN['bg3'])
            header.pack(fill='x')

            tk.Label(
                header, text=haupt_data['label'],
                bg=FARBEN['bg3'], fg=FARBEN['accent'],
                font=('SF Pro Text', 12, 'bold') if sys.platform == 'darwin'
                      else ('Segoe UI', 10, 'bold'),
                anchor='w'
            ).pack(side='left', padx=12, pady=8)

            tk.Label(
                header,
                text=f"{anzahl_haupt} Dok. | {gesamt_haupt:,.2f} €",
                bg=FARBEN['bg3'],
                fg=FARBEN['green'] if haupt_key == 'EINNAHMEN' else FARBEN['yellow'],
                font=('SF Pro Text', 11, 'bold') if sys.platform == 'darwin'
                      else ('Segoe UI', 10, 'bold')
            ).pack(side='right', padx=12, pady=8)

            # Subkategorien
            for sub_key, sub_data in haupt_data['subcats'].items():
                sub_stats = haupt_stats.get(sub_key, {})
                if sub_stats.get('anzahl', 0) > 0:
                    zeile = tk.Frame(karte, bg=FARBEN['bg2'])
                    zeile.pack(fill='x', padx=4)

                    tk.Label(
                        zeile, text=f"   {sub_data['label']}",
                        bg=FARBEN['bg2'], fg=FARBEN['fg2'],
                        width=40, anchor='w',
                        font=('SF Pro Text', 10) if sys.platform == 'darwin'
                              else ('Segoe UI', 9)
                    ).pack(side='left', pady=4)

                    tk.Label(
                        zeile, text=f"{sub_stats.get('anzahl', 0)} Dok.",
                        bg=FARBEN['bg2'], fg=FARBEN['fg2'],
                        width=8,
                        font=('SF Pro Text', 10) if sys.platform == 'darwin'
                              else ('Segoe UI', 9)
                    ).pack(side='left')

                    tk.Label(
                        zeile,
                        text=f"{sub_stats.get('summe', 0):,.2f} €",
                        bg=FARBEN['bg2'], fg=FARBEN['fg'],
                        font=('SF Pro Text', 10, 'bold') if sys.platform == 'darwin'
                              else ('Segoe UI', 9, 'bold')
                    ).pack(side='right', padx=12)

                    ttk.Separator(karte, orient='horizontal').pack(fill='x')

    def _aktualisiere_eur(self, dokumente: list, statistiken: dict):
        self.eur_tabelle.delete(*self.eur_tabelle.get_children())

        nach_steuer = statistiken.get('nach_steuer', {})

        einnahmen_gesamt = 0
        ausgaben_gesamt  = 0

        # ── Einnahmen ──
        self.eur_tabelle.insert('', 'end', values=('EINNAHMEN', '', ''),
                                 tags=('gesamt',))

        einnahmen_kat = STEUER_KATEGORIEN.get('EINNAHMEN', {}).get('subcats', {})
        ein_stats = nach_steuer.get('EINNAHMEN', {})

        for sub_key, sub_data in einnahmen_kat.items():
            stats = ein_stats.get(sub_key, {})
            betrag = stats.get('summe', 0)
            anzahl = stats.get('anzahl', 0)
            einnahmen_gesamt += betrag
            self.eur_tabelle.insert('', 'end',
                values=(f"  {sub_data['label']}", anzahl,
                        f"{betrag:,.2f}" if betrag else '—'),
                tags=('einnahmen',)
            )

        self.eur_tabelle.insert('', 'end',
            values=('Einnahmen gesamt', '', f"{einnahmen_gesamt:,.2f}"),
            tags=('gesamt',)
        )
        self.eur_tabelle.insert('', 'end', values=('', '', ''),
                                 tags=('trennlinie',))

        # ── Ausgaben ──
        self.eur_tabelle.insert('', 'end', values=('AUSGABEN / ABZÜGE', '', ''),
                                 tags=('gesamt',))

        ausgaben_gruppen = [
            'WERBUNGSKOSTEN', 'BETRIEBSAUSGABEN', 'SONDERAUSGABEN',
            'AUSSERGEWOEHNLICH', 'HAUSHALTSNAHE'
        ]

        for haupt_key in ausgaben_gruppen:
            haupt_data = STEUER_KATEGORIEN.get(haupt_key, {})
            haupt_stats = nach_steuer.get(haupt_key, {})
            haupt_gesamt = sum(v.get('summe', 0) for v in haupt_stats.values())
            haupt_anzahl = sum(v.get('anzahl', 0) for v in haupt_stats.values())

            if haupt_anzahl == 0:
                continue

            ausgaben_gesamt += haupt_gesamt
            self.eur_tabelle.insert('', 'end',
                values=(f"  {haupt_data.get('label', haupt_key)}",
                        haupt_anzahl, f"{haupt_gesamt:,.2f}"),
                tags=('kategorie',)
            )

            for sub_key, sub_data in haupt_data.get('subcats', {}).items():
                sub_stats = haupt_stats.get(sub_key, {})
                if sub_stats.get('anzahl', 0) > 0:
                    self.eur_tabelle.insert('', 'end',
                        values=(f"    {sub_data['label']}",
                                sub_stats.get('anzahl', 0),
                                f"{sub_stats.get('summe', 0):,.2f}"),
                        tags=('ausgaben',)
                    )

        self.eur_tabelle.insert('', 'end',
            values=('Ausgaben/Abzüge gesamt', '', f"{ausgaben_gesamt:,.2f}"),
            tags=('gesamt',)
        )
        self.eur_tabelle.insert('', 'end', values=('', '', ''),
                                 tags=('trennlinie',))

        # ── Ergebnis ──
        ueberschuss = einnahmen_gesamt - ausgaben_gesamt
        tag = 'einnahmen' if ueberschuss >= 0 else 'ausgaben'
        self.eur_tabelle.insert('', 'end',
            values=(f"ÜBERSCHUSS / GEWINN  ({self.aktuell_jahr or 'alle Jahre'})",
                    '', f"{ueberschuss:,.2f}"),
            tags=('gesamt',)
        )

    def _aktualisiere_anlage_n(self, dokumente: list):
        self.anlage_n_text.configure(state='normal')
        self.anlage_n_text.delete('1.0', 'end')

        def schreibe(text, tag='normal'):
            self.anlage_n_text.insert('end', text + '\n', tag)

        schreibe(f"ANLAGE N – EINKÜNFTE AUS NICHTSELBSTÄNDIGER ARBEIT",
                 'header')
        schreibe(f"Steuerjahr: {self.aktuell_jahr or 'alle'}\n", 'normal')

        # Gehaltsabrechnungen
        gehalt_docs = [d for d in dokumente if d.get('dok_typ') == 'gehaltsabrechnung']
        lohn_docs   = [d for d in dokumente if d.get('dok_typ') == 'lohnsteuerbescheid']

        schreibe("1. EINNAHMEN", 'subheader')
        schreibe("")
        if gehalt_docs:
            gehalt_sum = sum(d.get('betrag', 0) or 0 for d in gehalt_docs)
            schreibe(f"  Gehaltsabrechnungen: {len(gehalt_docs)} Dokument(e)")
            schreibe(f"  Bruttolohn ca.: {gehalt_sum:,.2f} €", 'betrag')
        else:
            schreibe("  ⚠️  Keine Gehaltsabrechnungen gefunden.", 'hinweis')
            schreibe("      Bitte Lohnsteuerbescheinigung manuell ergänzen.", 'hinweis')

        if lohn_docs:
            schreibe(f"\n  Lohnsteuerbescheinigung(en): {len(lohn_docs)} vorhanden")
        else:
            schreibe("\n  ⚠️  Keine Lohnsteuerbescheinigung gefunden!", 'hinweis')

        schreibe("")
        schreibe("2. WERBUNGSKOSTEN", 'subheader')
        schreibe("")

        wk_kategorien = {
            'fahrtkosten':   'Fahrtkosten (Arbeitsstätte)',
            'arbeitsmittel': 'Arbeitsmittel / Bürobedarf',
            'fortbildung':   'Fortbildung / Weiterbildung',
            'homeoffice':    'Homeoffice / Arbeitszimmer',
            'beruf_sons':    'Sonstige Werbungskosten',
        }

        wk_gesamt = 0
        for sub_key, label in wk_kategorien.items():
            docs = [d for d in dokumente
                    if d.get('steuer_haupt') == 'WERBUNGSKOSTEN'
                    and d.get('steuer_sub') == sub_key]
            if docs:
                betrag = sum(d.get('betrag', 0) or 0 for d in docs)
                wk_gesamt += betrag
                schreibe(f"  {label}:")
                schreibe(f"    {len(docs)} Beleg(e) | {betrag:,.2f} €", 'betrag')

        schreibe(f"\n  Werbungskosten gesamt: {wk_gesamt:,.2f} €", 'betrag')
        schreibe(f"  (Werbungskostenpauschale 2024: 1.230,00 €)", 'normal')
        if wk_gesamt > 1230:
            schreibe(f"  ✅ Übersteigt die Pauschale! Nachweis erforderlich.", 'betrag')
        else:
            schreibe(f"  ℹ️  Pauschale günstiger – keine Belege nötig.", 'hinweis')

        schreibe("")
        schreibe("3. HINWEISE FÜR STEUERBERATER", 'subheader')
        schreibe("")
        schreibe("  • Alle Belege im Ordner 'Werbungskosten' prüfen")
        schreibe("  • Fahrtkilometer und -tage dokumentieren")
        schreibe("  • Homeoffice-Tage nachweisen (Kalender/Stundenzettel)")
        schreibe("  • Fortbildungsrechnung auf beruflichen Bezug prüfen")

        self.anlage_n_text.configure(state='disabled')
