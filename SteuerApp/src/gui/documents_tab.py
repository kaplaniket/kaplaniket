"""
Dokumente-Tab: Alle gescannten Dokumente anzeigen, filtern, bearbeiten
"""

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import os
import sys
import subprocess
from typing import Optional

from ..constants import FARBEN, DOK_TYPEN, STEUER_KATEGORIEN
from .. import database as db
from ..classifier import DokumentKlassifizierer
from ..extractor import DatenExtraktor


class DocumentsTab:
    def __init__(self, notebook, app):
        self.app = app
        self.frame = ttk.Frame(notebook)
        self.aktuell_jahr: Optional[int] = None
        self.alle_dokumente = []
        self.ausgewaehltes_dok = None

        self._erstelle_gui()
        self.lade_dokumente()

    def _erstelle_gui(self):
        haupt = tk.Frame(self.frame, bg=FARBEN['bg'])
        haupt.pack(fill='both', expand=True)

        # ── Toolbar ──────────────────────────────────────────────
        toolbar = tk.Frame(haupt, bg=FARBEN['bg3'], height=50)
        toolbar.pack(fill='x', padx=0, pady=0)
        toolbar.pack_propagate(False)

        # Suche
        tk.Label(toolbar, text="🔍", bg=FARBEN['bg3'],
                 fg=FARBEN['fg2']).pack(side='left', padx=(12, 4), pady=10)
        self.suche_var = tk.StringVar()
        self.suche_var.trace('w', self._filter_geaendert)
        ttk.Entry(toolbar, textvariable=self.suche_var,
                  width=25).pack(side='left', pady=10, padx=(0, 12))

        # Filter Typ
        tk.Label(toolbar, text="Typ:", bg=FARBEN['bg3'],
                 fg=FARBEN['fg2']).pack(side='left', padx=(0, 4))
        self.filter_typ_var = tk.StringVar(value='Alle')
        typ_optionen = ['Alle'] + list(DOK_TYPEN.values())
        self.filter_typ = ttk.Combobox(
            toolbar, textvariable=self.filter_typ_var,
            values=typ_optionen, width=20, state='readonly'
        )
        self.filter_typ.pack(side='left', pady=10, padx=(0, 12))
        self.filter_typ.bind('<<ComboboxSelected>>', self._filter_geaendert)

        # Filter Steuer-Kategorie
        tk.Label(toolbar, text="Kategorie:", bg=FARBEN['bg3'],
                 fg=FARBEN['fg2']).pack(side='left', padx=(0, 4))
        self.filter_kat_var = tk.StringVar(value='Alle')
        kat_optionen = ['Alle'] + [d['label'] for d in STEUER_KATEGORIEN.values()]
        self.filter_kat = ttk.Combobox(
            toolbar, textvariable=self.filter_kat_var,
            values=kat_optionen, width=28, state='readonly'
        )
        self.filter_kat.pack(side='left', pady=10, padx=(0, 12))
        self.filter_kat.bind('<<ComboboxSelected>>', self._filter_geaendert)

        # Nur ungeprüfte
        self.nur_ungeprueft = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            toolbar, text="Nur ungeprüfte",
            variable=self.nur_ungeprueft,
            command=self._filter_geaendert
        ).pack(side='left', padx=8)

        # Anzahl-Label
        self.anzahl_label = tk.Label(
            toolbar, text="0 Dokumente",
            bg=FARBEN['bg3'], fg=FARBEN['fg2'],
            font=('SF Pro Text', 10) if sys.platform == 'darwin'
                  else ('Segoe UI', 9)
        )
        self.anzahl_label.pack(side='right', padx=12)

        # ── Haupt-Bereich: Tabelle + Details ─────────────────────
        paned = ttk.PanedWindow(haupt, orient='horizontal')
        paned.pack(fill='both', expand=True)

        # ── Linke Seite: Tabelle ──────────────────────────────────
        tabelle_frame = tk.Frame(paned, bg=FARBEN['bg'])
        paned.add(tabelle_frame, weight=3)

        # Tabelle
        spalten = ('nr', 'dateiname', 'typ', 'datum', 'betrag',
                   'lieferant', 'kategorie', 'geprueft')
        self.tabelle = ttk.Treeview(
            tabelle_frame,
            columns=spalten,
            show='headings',
            selectmode='extended'
        )

        # Spalten-Konfiguration
        spalten_config = [
            ('nr',         '#',          50,  'center'),
            ('dateiname',  'Dateiname',  220, 'w'),
            ('typ',        'Typ',        160, 'w'),
            ('datum',      'Datum',       90, 'center'),
            ('betrag',     'Betrag (€)', 100, 'e'),
            ('lieferant',  'Von',        160, 'w'),
            ('kategorie',  'Steuerkategorie', 150, 'w'),
            ('geprueft',   '✓',           40, 'center'),
        ]

        for col, heading, width, anchor in spalten_config:
            self.tabelle.heading(col, text=heading,
                                  command=lambda c=col: self._sortiere(c))
            self.tabelle.column(col, width=width, anchor=anchor, minwidth=40)

        # Scrollbars
        v_scroll = ttk.Scrollbar(tabelle_frame, orient='vertical',
                                   command=self.tabelle.yview)
        h_scroll = ttk.Scrollbar(tabelle_frame, orient='horizontal',
                                   command=self.tabelle.xview)
        self.tabelle.configure(yscrollcommand=v_scroll.set,
                                xscrollcommand=h_scroll.set)

        v_scroll.pack(side='right', fill='y')
        h_scroll.pack(side='bottom', fill='x')
        self.tabelle.pack(fill='both', expand=True)

        # Row-Tags
        self.tabelle.tag_configure('geprueft',    background='#1a2e1a', foreground=FARBEN['green'])
        self.tabelle.tag_configure('ungeprueft',  background='#252535', foreground=FARBEN['fg'])
        self.tabelle.tag_configure('kein_betrag', background='#2e2520', foreground=FARBEN['yellow'])

        # Kontext-Menü
        self.kontext_menu = tk.Menu(self.frame, tearoff=0,
                                     bg=FARBEN['bg3'], fg=FARBEN['fg'])
        self.kontext_menu.add_command(label="🔍 Öffnen",
                                       command=self._datei_oeffnen)
        self.kontext_menu.add_command(label="✅ Als geprüft markieren",
                                       command=lambda: self._geprueft_setzen(True))
        self.kontext_menu.add_command(label="⬜ Geprüft aufheben",
                                       command=lambda: self._geprueft_setzen(False))
        self.kontext_menu.add_separator()
        self.kontext_menu.add_command(label="✏️ Betrag bearbeiten",
                                       command=self._betrag_bearbeiten)
        self.kontext_menu.add_command(label="📅 Datum bearbeiten",
                                       command=self._datum_bearbeiten)
        self.kontext_menu.add_command(label="🏷️ Kategorie ändern",
                                       command=self._kategorie_aendern)
        self.kontext_menu.add_separator()
        self.kontext_menu.add_command(label="📝 Notiz bearbeiten",
                                       command=self._notiz_bearbeiten)
        self.kontext_menu.add_separator()
        self.kontext_menu.add_command(label="🗑️ Aus Datenbank entfernen",
                                       command=self._dokument_loeschen,
                                       foreground=FARBEN['red'])

        self.tabelle.bind('<Button-2>', self._zeige_kontext)   # macOS
        self.tabelle.bind('<Button-3>', self._zeige_kontext)   # Windows/Linux
        self.tabelle.bind('<Double-1>', lambda e: self._datei_oeffnen())
        self.tabelle.bind('<<TreeviewSelect>>', self._auswahl_geaendert)

        # Tastenkürzel
        self.frame.bind_all('<space>', lambda e: self._geprueft_toggle())

        # ── Rechte Seite: Details ─────────────────────────────────
        details_frame = tk.Frame(paned, bg=FARBEN['bg'])
        paned.add(details_frame, weight=1)

        details_label = tk.Label(
            details_frame, text="Dokument-Details",
            bg=FARBEN['bg'], fg=FARBEN['accent'],
            font=('SF Pro Display', 13, 'bold') if sys.platform == 'darwin'
                  else ('Segoe UI', 11, 'bold')
        )
        details_label.pack(anchor='w', padx=12, pady=(12, 6))

        self.details_text = tk.Text(
            details_frame,
            bg='#1a1a2e', fg=FARBEN['fg'],
            relief='flat', font=('SF Pro Text', 10) if sys.platform == 'darwin'
                                  else ('Segoe UI', 9),
            wrap='word', state='disabled', padx=10, pady=8,
            width=35
        )
        self.details_text.pack(fill='both', expand=True, padx=8, pady=(0, 8))

        # Tags für Details
        self.details_text.tag_configure('label',
                                         foreground=FARBEN['fg2'],
                                         font=('SF Pro Text', 9) if sys.platform == 'darwin'
                                               else ('Segoe UI', 8))
        self.details_text.tag_configure('wert',
                                         foreground=FARBEN['fg'],
                                         font=('SF Pro Text', 10) if sys.platform == 'darwin'
                                               else ('Segoe UI', 9))
        self.details_text.tag_configure('highlight',
                                         foreground=FARBEN['accent'],
                                         font=('SF Pro Text', 10, 'bold') if sys.platform == 'darwin'
                                               else ('Segoe UI', 9, 'bold'))
        self.details_text.tag_configure('text_vorschau',
                                         foreground='#888',
                                         font=('SF Mono', 9) if sys.platform == 'darwin'
                                               else ('Consolas', 8))

        # Aktions-Buttons im Details-Bereich
        btn_frame = tk.Frame(details_frame, bg=FARBEN['bg'])
        btn_frame.pack(fill='x', padx=8, pady=(0, 8))

        ttk.Button(btn_frame, text="Öffnen", width=12,
                   command=self._datei_oeffnen).pack(side='left', padx=2)
        ttk.Button(btn_frame, text="✅ Geprüft",
                   command=lambda: self._geprueft_setzen(True),
                   style='Success.TButton').pack(side='left', padx=2)

        # ── Unterhalb der Tabelle: Summen ─────────────────────────
        summen_frame = tk.Frame(haupt, bg=FARBEN['bg3'], height=36)
        summen_frame.pack(fill='x', side='bottom')
        summen_frame.pack_propagate(False)

        self.summen_label = tk.Label(
            summen_frame, text="",
            bg=FARBEN['bg3'], fg=FARBEN['accent'],
            font=('SF Pro Text', 10, 'bold') if sys.platform == 'darwin'
                  else ('Segoe UI', 9, 'bold')
        )
        self.summen_label.pack(side='right', padx=16, pady=8)

        # Gesamt-Aktionen
        aktionen_frame = tk.Frame(summen_frame, bg=FARBEN['bg3'])
        aktionen_frame.pack(side='left', padx=8, pady=4)

        ttk.Button(aktionen_frame, text="Alle als geprüft",
                   command=lambda: self._alle_geprueft(True)).pack(side='left', padx=4)
        ttk.Button(aktionen_frame, text="Geprüft aufheben",
                   command=lambda: self._alle_geprueft(False),
                   style='Warning.TButton').pack(side='left', padx=4)

    def lade_dokumente(self, steuerjahr=None):
        self.aktuell_jahr = steuerjahr
        self._filter_geaendert()

    def _filter_geaendert(self, *args):
        suche = self.suche_var.get().strip() or None
        jahr  = self.aktuell_jahr

        # Typ-Filter
        typ_label = self.filter_typ_var.get()
        dok_typ = None
        if typ_label != 'Alle':
            for k, v in DOK_TYPEN.items():
                if v == typ_label:
                    dok_typ = k
                    break

        # Kategorien-Filter
        kat_label = self.filter_kat_var.get()
        steuer_haupt = None
        if kat_label != 'Alle':
            for k, v in STEUER_KATEGORIEN.items():
                if v['label'] == kat_label:
                    steuer_haupt = k
                    break

        geprueft = None
        if self.nur_ungeprueft.get():
            geprueft = False

        self.alle_dokumente = db.get_dokumente(
            steuerjahr=jahr,
            dok_typ=dok_typ,
            steuer_haupt=steuer_haupt,
            geprueft=geprueft,
            suche=suche
        )
        self._befuelle_tabelle()

    def _befuelle_tabelle(self):
        self.tabelle.delete(*self.tabelle.get_children())

        gesamt_betrag = 0
        for i, d in enumerate(self.alle_dokumente, 1):
            betrag = d.get('betrag') or 0
            gesamt_betrag += betrag

            # Steuer-Kategorie-Label
            haupt = d.get('steuer_haupt', '')
            sub   = d.get('steuer_sub', '')
            kat_label = ''
            if haupt in STEUER_KATEGORIEN:
                kat_data = STEUER_KATEGORIEN[haupt]
                sub_data = kat_data['subcats'].get(sub, {})
                kat_label = sub_data.get('label', haupt)

            tag = 'geprueft' if d.get('geprueft') else (
                'kein_betrag' if not d.get('betrag') else 'ungeprueft'
            )

            self.tabelle.insert('', 'end', iid=str(d['id']),
                values=(
                    i,
                    d.get('dateiname', '')[:50],
                    DOK_TYPEN.get(d.get('dok_typ', ''), d.get('dok_typ', '')),
                    (d.get('datum') or '')[:10],
                    f"{betrag:.2f}" if betrag else '',
                    (d.get('lieferant') or '')[:30],
                    kat_label[:35],
                    '✓' if d.get('geprueft') else ''
                ),
                tags=(tag,)
            )

        self.anzahl_label.configure(
            text=f"{len(self.alle_dokumente)} Dokument(e)"
        )
        self.summen_label.configure(
            text=f"Gesamtbetrag: {gesamt_betrag:,.2f} €"
        )

    def _get_ausgewaehlte_ids(self) -> list:
        return [int(iid) for iid in self.tabelle.selection()]

    def _get_ausgewaehltes_dok(self) -> dict:
        auswahl = self.tabelle.selection()
        if not auswahl:
            return None
        dok_id = int(auswahl[0])
        for d in self.alle_dokumente:
            if d['id'] == dok_id:
                return d
        return None

    def _auswahl_geaendert(self, event=None):
        d = self._get_ausgewaehltes_dok()
        if d:
            self._zeige_details(d)

    def _zeige_details(self, d: dict):
        self.details_text.configure(state='normal')
        self.details_text.delete('1.0', 'end')

        def zeile(label, wert, tag='wert'):
            self.details_text.insert('end', f"{label}\n", 'label')
            self.details_text.insert('end', f"{wert}\n\n", tag)

        zeile("Dateiname", d.get('dateiname', '—'), 'highlight')
        zeile("Typ", DOK_TYPEN.get(d.get('dok_typ', ''), '—'))
        zeile("Datum", (d.get('datum') or '—')[:10])

        betrag = d.get('betrag')
        zeile("Betrag",
              f"{betrag:.2f} €" if betrag else '—',
              'highlight' if betrag else 'wert')

        zeile("Lieferant / Von", d.get('lieferant') or '—')
        zeile("Steuerjahr", str(d.get('steuerjahr') or '—'))

        haupt = d.get('steuer_haupt', '')
        sub   = d.get('steuer_sub', '')
        if haupt in STEUER_KATEGORIEN:
            kat_data = STEUER_KATEGORIEN[haupt]
            haupt_label = kat_data['label']
            sub_label = kat_data['subcats'].get(sub, {}).get('label', sub)
            zeile("Steuer-Kategorie", f"{haupt_label}\n→ {sub_label}")
        else:
            zeile("Steuer-Kategorie", '—')

        zeile("Geprüft", "✅ Ja" if d.get('geprueft') else "⬜ Nein")
        zeile("Dateigröße",
              f"{d.get('dateigroesse', 0) / 1024:.1f} KB")

        if d.get('notiz'):
            zeile("Notiz", d['notiz'])

        # Text-Vorschau
        text = d.get('erkannter_text', '')
        if text and text.strip():
            self.details_text.insert('end', "Erkannter Text (Vorschau)\n", 'label')
            vorschau = text.strip()[:400]
            if len(text) > 400:
                vorschau += "..."
            self.details_text.insert('end', vorschau + "\n", 'text_vorschau')

        self.details_text.configure(state='disabled')

    def _datei_oeffnen(self):
        d = self._get_ausgewaehltes_dok()
        if not d:
            return
        pfad = d.get('dateipfad', '')
        if not os.path.exists(pfad):
            messagebox.showerror("Fehler", f"Datei nicht gefunden:\n{pfad}")
            return
        try:
            if sys.platform == 'darwin':
                subprocess.run(['open', pfad])
            elif sys.platform == 'win32':
                os.startfile(pfad)
            else:
                subprocess.run(['xdg-open', pfad])
        except Exception as e:
            messagebox.showerror("Fehler", f"Kann Datei nicht öffnen: {e}")

    def _geprueft_setzen(self, wert: bool):
        ids = self._get_ausgewaehlte_ids()
        for dok_id in ids:
            db.update_dokument_feld(dok_id, geprueft=1 if wert else 0)
        self._filter_geaendert()

    def _geprueft_toggle(self):
        d = self._get_ausgewaehltes_dok()
        if d:
            db.update_dokument_feld(d['id'],
                                     geprueft=0 if d.get('geprueft') else 1)
            self._filter_geaendert()

    def _alle_geprueft(self, wert: bool):
        ids = self._get_ausgewaehlte_ids()
        if not ids:
            ids = [d['id'] for d in self.alle_dokumente]
        for dok_id in ids:
            db.update_dokument_feld(dok_id, geprueft=1 if wert else 0)
        self._filter_geaendert()

    def _betrag_bearbeiten(self):
        d = self._get_ausgewaehltes_dok()
        if not d:
            return
        alt = str(d.get('betrag') or '')
        neu = simpledialog.askstring(
            "Betrag bearbeiten",
            f"Betrag für:\n{d.get('dateiname')}\n\nNeuen Betrag eingeben (z.B. 123.45):",
            initialvalue=alt,
            parent=self.frame
        )
        if neu is not None:
            try:
                betrag = float(neu.replace(',', '.'))
                db.update_dokument_feld(d['id'], betrag=betrag)
                self._filter_geaendert()
            except ValueError:
                messagebox.showerror("Fehler", "Ungültiger Betrag.")

    def _datum_bearbeiten(self):
        d = self._get_ausgewaehltes_dok()
        if not d:
            return
        alt = (d.get('datum') or '')[:10]
        neu = simpledialog.askstring(
            "Datum bearbeiten",
            f"Datum für:\n{d.get('dateiname')}\n\nFormat: JJJJ-MM-TT",
            initialvalue=alt,
            parent=self.frame
        )
        if neu is not None:
            import re
            if re.match(r'^\d{4}-\d{2}-\d{2}$', neu.strip()):
                db.update_dokument_feld(d['id'], datum=neu.strip())
                self._filter_geaendert()
            else:
                messagebox.showerror("Fehler", "Ungültiges Datum. Format: JJJJ-MM-TT")

    def _kategorie_aendern(self):
        d = self._get_ausgewaehltes_dok()
        if not d:
            return
        KategorieDialog(self.frame, d, callback=self._filter_geaendert)

    def _notiz_bearbeiten(self):
        d = self._get_ausgewaehltes_dok()
        if not d:
            return
        NotizDialog(self.frame, d, callback=self._filter_geaendert)

    def _dokument_loeschen(self):
        ids = self._get_ausgewaehlte_ids()
        if not ids:
            return
        if messagebox.askyesno("Bestätigung",
                                f"{len(ids)} Dokument(e) aus der Datenbank entfernen?\n"
                                "(Original-Dateien bleiben erhalten)"):
            for dok_id in ids:
                db.delete_dokument(dok_id)
            self._filter_geaendert()

    def _zeige_kontext(self, event):
        self.tabelle.identify_row(event.y)
        auswahl = self.tabelle.identify_row(event.y)
        if auswahl:
            if auswahl not in self.tabelle.selection():
                self.tabelle.selection_set(auswahl)
            self.kontext_menu.tk_popup(event.x_root, event.y_root)

    def _sortiere(self, spalte: str):
        """Tabelle nach Spalte sortieren"""
        items = [(self.tabelle.set(iid, spalte), iid)
                  for iid in self.tabelle.get_children()]
        items.sort(key=lambda x: x[0].lower() if x[0] else '')
        for idx, (_, iid) in enumerate(items):
            self.tabelle.move(iid, '', idx)


class KategorieDialog:
    """Dialog zum Ändern der Steuer-Kategorie"""
    def __init__(self, parent, dokument: dict, callback=None):
        self.dokument = dokument
        self.callback = callback

        self.win = tk.Toplevel(parent)
        self.win.title("Kategorie ändern")
        self.win.geometry("500x400")
        self.win.configure(bg=FARBEN['bg'])
        self.win.grab_set()

        tk.Label(
            self.win,
            text=f"Kategorie für:\n{dokument.get('dateiname', '')}",
            bg=FARBEN['bg'], fg=FARBEN['fg'],
            wraplength=450
        ).pack(padx=16, pady=(16, 8))

        # Haupt-Kategorie
        tk.Label(self.win, text="Hauptkategorie:",
                 bg=FARBEN['bg'], fg=FARBEN['fg2']).pack(anchor='w', padx=16)
        self.haupt_var = tk.StringVar(
            value=dokument.get('steuer_haupt', 'SONDERAUSGABEN')
        )
        haupt_combo = ttk.Combobox(
            self.win, textvariable=self.haupt_var,
            values=list(STEUER_KATEGORIEN.keys()),
            state='readonly', width=40
        )
        haupt_combo.pack(anchor='w', padx=16, pady=(0, 12))
        haupt_combo.bind('<<ComboboxSelected>>', self._haupt_geaendert)

        # Unter-Kategorie
        tk.Label(self.win, text="Unterkategorie:",
                 bg=FARBEN['bg'], fg=FARBEN['fg2']).pack(anchor='w', padx=16)
        self.sub_var = tk.StringVar(
            value=dokument.get('steuer_sub', 'sonstige_sa')
        )
        self.sub_combo = ttk.Combobox(
            self.win, textvariable=self.sub_var, state='readonly', width=40
        )
        self.sub_combo.pack(anchor='w', padx=16, pady=(0, 16))
        self._haupt_geaendert()

        # Buttons
        btn_frame = tk.Frame(self.win, bg=FARBEN['bg'])
        btn_frame.pack(fill='x', padx=16, pady=8)
        ttk.Button(btn_frame, text="Speichern",
                   command=self._speichern).pack(side='left', padx=(0, 8))
        ttk.Button(btn_frame, text="Abbrechen",
                   command=self.win.destroy).pack(side='left')

    def _haupt_geaendert(self, event=None):
        haupt = self.haupt_var.get()
        if haupt in STEUER_KATEGORIEN:
            sub_keys = list(STEUER_KATEGORIEN[haupt]['subcats'].keys())
            sub_labels = [STEUER_KATEGORIEN[haupt]['subcats'][k]['label']
                          for k in sub_keys]
            self.sub_combo.configure(values=sub_keys)
            if sub_keys:
                self.sub_var.set(sub_keys[0])

    def _speichern(self):
        db.update_dokument_feld(
            self.dokument['id'],
            steuer_haupt=self.haupt_var.get(),
            steuer_sub=self.sub_var.get()
        )
        if self.callback:
            self.callback()
        self.win.destroy()


class NotizDialog:
    """Dialog zum Bearbeiten der Notiz"""
    def __init__(self, parent, dokument: dict, callback=None):
        self.dokument = dokument
        self.callback = callback

        self.win = tk.Toplevel(parent)
        self.win.title("Notiz bearbeiten")
        self.win.geometry("450x250")
        self.win.configure(bg=FARBEN['bg'])
        self.win.grab_set()

        tk.Label(
            self.win,
            text=f"Notiz für:\n{dokument.get('dateiname', '')}",
            bg=FARBEN['bg'], fg=FARBEN['fg'],
            wraplength=420
        ).pack(padx=16, pady=(16, 8))

        self.text_widget = tk.Text(
            self.win,
            bg='#252535', fg=FARBEN['fg'],
            relief='flat', height=6,
            font=('SF Pro Text', 11) if sys.platform == 'darwin'
                  else ('Segoe UI', 10)
        )
        self.text_widget.pack(fill='both', expand=True, padx=16, pady=(0, 8))
        self.text_widget.insert('1.0', dokument.get('notiz') or '')

        btn_frame = tk.Frame(self.win, bg=FARBEN['bg'])
        btn_frame.pack(fill='x', padx=16, pady=8)
        ttk.Button(btn_frame, text="Speichern",
                   command=self._speichern).pack(side='left', padx=(0, 8))
        ttk.Button(btn_frame, text="Abbrechen",
                   command=self.win.destroy).pack(side='left')

    def _speichern(self):
        notiz = self.text_widget.get('1.0', 'end').strip()
        db.update_dokument_feld(self.dokument['id'], notiz=notiz)
        if self.callback:
            self.callback()
        self.win.destroy()
