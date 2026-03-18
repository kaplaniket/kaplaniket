"""
Scanner-Tab: Ordner auswählen, Scan konfigurieren, Dokumente scannen
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
import os
import sys
from datetime import datetime
from pathlib import Path

from ..constants import FARBEN, DOK_TYPEN
from ..file_scanner import DateiScanner
from ..document_processor import DokumentProzessor, verfuegbare_methoden
from ..classifier import DokumentKlassifizierer
from ..extractor import DatenExtraktor
from .. import database as db


class ScanTab:
    def __init__(self, notebook, app):
        self.app = app
        self.frame = ttk.Frame(notebook)
        self.ausgewaehlte_pfade: list = []
        self._scan_thread = None
        self._abbrechen = False

        self.prozessor   = DokumentProzessor()
        self.klassifizierer = DokumentKlassifizierer()
        self.extraktor   = DatenExtraktor()

        self._erstelle_gui()
        self._zeige_bibliotheken()

    def _erstelle_gui(self):
        haupt = tk.Frame(self.frame, bg=FARBEN['bg'])
        haupt.pack(fill='both', expand=True, padx=20, pady=20)

        # ── Linke Spalte: Einstellungen ──────────────────────────
        links = tk.Frame(haupt, bg=FARBEN['bg'], width=380)
        links.pack(side='left', fill='y', padx=(0, 15))
        links.pack_propagate(False)

        # Ordner-Auswahl
        ordner_frame = ttk.LabelFrame(links, text="  Ordner & Dateien auswählen  ",
                                       padding=12)
        ordner_frame.pack(fill='x', pady=(0, 12))

        btn_frame = tk.Frame(ordner_frame, bg=FARBEN['bg2'])
        btn_frame.pack(fill='x', pady=(0, 8))

        ttk.Button(btn_frame, text="+ Ordner hinzufügen",
                   command=self._ordner_hinzufuegen).pack(side='left', padx=(0, 8))
        ttk.Button(btn_frame, text="+ Datei(en) hinzufügen",
                   command=self._dateien_hinzufuegen).pack(side='left', padx=(0, 8))
        ttk.Button(btn_frame, text="Leeren",
                   command=self._pfade_leeren,
                   style='Danger.TButton').pack(side='right')

        # Pfad-Liste
        pfad_container = tk.Frame(ordner_frame, bg=FARBEN['bg3'])
        pfad_container.pack(fill='both', expand=True)

        self.pfad_listbox = tk.Listbox(
            pfad_container,
            bg=FARBEN['bg3'], fg=FARBEN['fg'],
            selectbackground=FARBEN['accent'],
            relief='flat', borderwidth=0,
            font=('SF Pro Text', 10) if sys.platform == 'darwin'
                  else ('Segoe UI', 9),
            height=6
        )
        sb = ttk.Scrollbar(pfad_container, orient='vertical',
                            command=self.pfad_listbox.yview)
        self.pfad_listbox.configure(yscrollcommand=sb.set)
        sb.pack(side='right', fill='y')
        self.pfad_listbox.pack(fill='both', expand=True, padx=2, pady=2)

        # Ausgewählten Pfad entfernen
        ttk.Button(ordner_frame, text="Ausgewählten Pfad entfernen",
                   command=self._pfad_entfernen).pack(anchor='w', pady=(4, 0))

        # ── Scan-Optionen ──────────────────────────────────────
        optionen_frame = ttk.LabelFrame(links, text="  Scan-Optionen  ", padding=12)
        optionen_frame.pack(fill='x', pady=(0, 12))

        # Jahr-Bereich
        jahr_row = tk.Frame(optionen_frame, bg=FARBEN['bg2'])
        jahr_row.pack(fill='x', pady=(0, 8))

        tk.Label(jahr_row, text="Jahre (z.B. 2022,2023,2024):",
                 bg=FARBEN['bg2'], fg=FARBEN['fg']).pack(anchor='w', pady=(0, 4))

        self.jahre_var = tk.StringVar(
            value=str(self.app.aktuelles_jahr.get())
        )
        ttk.Entry(jahr_row, textvariable=self.jahre_var,
                  width=30).pack(fill='x')

        tk.Label(jahr_row,
                 text="Leer lassen = alle Jahre scannen",
                 bg=FARBEN['bg2'], fg=FARBEN['fg2'],
                 font=('SF Pro Text', 9) if sys.platform == 'darwin'
                       else ('Segoe UI', 8)).pack(anchor='w', pady=(2, 0))

        # Optionen
        self.opt_alle_endungen = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            optionen_frame,
            text="Alle Dateitypen scannen (auch unbekannte)",
            variable=self.opt_alle_endungen
        ).pack(anchor='w', pady=2)

        self.opt_ocr = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            optionen_frame,
            text="OCR für Bilder & gescannte PDFs",
            variable=self.opt_ocr
        ).pack(anchor='w', pady=2)

        self.opt_thumbnail = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            optionen_frame,
            text="Vorschaubilder erstellen",
            variable=self.opt_thumbnail
        ).pack(anchor='w', pady=2)

        self.opt_ueberschreiben = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            optionen_frame,
            text="Bereits gescannte Dokumente überschreiben",
            variable=self.opt_ueberschreiben
        ).pack(anchor='w', pady=2)

        # ── Bibliotheken-Status ────────────────────────────────
        self.bibl_frame = ttk.LabelFrame(links, text="  Verfügbare Funktionen  ",
                                          padding=10)
        self.bibl_frame.pack(fill='x', pady=(0, 12))

        # ── Datenbank-Verwaltung ───────────────────────────────
        db_frame = ttk.LabelFrame(links, text="  Datenbank  ", padding=10)
        db_frame.pack(fill='x')

        ttk.Button(db_frame, text="Alle Dokumente löschen",
                   command=self._alle_loeschen,
                   style='Danger.TButton').pack(fill='x', pady=2)

        # ── Rechte Spalte: Fortschritt & Log ─────────────────────
        rechts = tk.Frame(haupt, bg=FARBEN['bg'])
        rechts.pack(side='right', fill='both', expand=True)

        # Scan-Steuerung
        steuerung = tk.Frame(rechts, bg=FARBEN['bg'])
        steuerung.pack(fill='x', pady=(0, 12))

        self.scan_btn = ttk.Button(
            steuerung, text="▶  Scan starten",
            command=self._scan_starten,
            style='Success.TButton'
        )
        self.scan_btn.pack(side='left', padx=(0, 10))

        self.stop_btn = ttk.Button(
            steuerung, text="⏹  Abbrechen",
            command=self._scan_abbrechen,
            style='Danger.TButton',
            state='disabled'
        )
        self.stop_btn.pack(side='left')

        # Fortschrittsanzeige
        fort_frame = ttk.LabelFrame(rechts, text="  Fortschritt  ", padding=10)
        fort_frame.pack(fill='x', pady=(0, 12))

        self.fortschritt_var = tk.DoubleVar(value=0)
        self.fortschritt_bar = ttk.Progressbar(
            fort_frame, variable=self.fortschritt_var,
            maximum=100, length=400
        )
        self.fortschritt_bar.pack(fill='x', pady=(0, 6))

        self.fortschritt_label = tk.Label(
            fort_frame, text="Warte auf Start...",
            bg=FARBEN['bg2'], fg=FARBEN['fg2'],
            font=('SF Pro Text', 10) if sys.platform == 'darwin'
                  else ('Segoe UI', 9)
        )
        self.fortschritt_label.pack(anchor='w')

        # Statistiken
        stats_frame = ttk.LabelFrame(rechts, text="  Scan-Ergebnis  ", padding=10)
        stats_frame.pack(fill='x', pady=(0, 12))

        self.stats_grid = tk.Frame(stats_frame, bg=FARBEN['bg2'])
        self.stats_grid.pack(fill='x')

        self.stats_labels = {}
        kennzahlen = [
            ('gefunden', 'Gefundene Dateien:', '0'),
            ('verarbeitet', 'Verarbeitet:', '0'),
            ('erkannt', 'Erkannte Dokumente:', '0'),
            ('fehler', 'Fehler:', '0'),
        ]
        for i, (key, label, wert) in enumerate(kennzahlen):
            tk.Label(self.stats_grid, text=label,
                     bg=FARBEN['bg2'], fg=FARBEN['fg2'],
                     width=24, anchor='w').grid(row=i, column=0, sticky='w', pady=2)
            lbl = tk.Label(self.stats_grid, text=wert,
                           bg=FARBEN['bg2'], fg=FARBEN['accent'],
                           font=('SF Pro Text', 11, 'bold') if sys.platform == 'darwin'
                                 else ('Segoe UI', 10, 'bold'))
            lbl.grid(row=i, column=1, sticky='w', padx=10)
            self.stats_labels[key] = lbl

        # Log
        log_frame = ttk.LabelFrame(rechts, text="  Protokoll  ", padding=8)
        log_frame.pack(fill='both', expand=True)

        self.log_text = tk.Text(
            log_frame, height=12,
            bg='#1a1a2e', fg=FARBEN['fg2'],
            insertbackground=FARBEN['fg'],
            relief='flat', font=('SF Mono', 10) if sys.platform == 'darwin'
                                  else ('Consolas', 9),
            wrap='word', state='disabled'
        )
        log_scroll = ttk.Scrollbar(log_frame, orient='vertical',
                                    command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=log_scroll.set)
        log_scroll.pack(side='right', fill='y')
        self.log_text.pack(fill='both', expand=True)

        # Log-Tags
        self.log_text.tag_configure('info',    foreground=FARBEN['fg2'])
        self.log_text.tag_configure('success', foreground=FARBEN['green'])
        self.log_text.tag_configure('warning', foreground=FARBEN['yellow'])
        self.log_text.tag_configure('error',   foreground=FARBEN['red'])
        self.log_text.tag_configure('header',  foreground=FARBEN['accent'],
                                     font=('SF Mono', 10, 'bold') if sys.platform == 'darwin'
                                           else ('Consolas', 9, 'bold'))

    def _zeige_bibliotheken(self):
        for widget in self.bibl_frame.winfo_children():
            widget.destroy()

        methoden = verfuegbare_methoden()
        beschreibungen = {
            'PyMuPDF':     'PDF-Verarbeitung',
            'Pillow':      'Bildverarbeitung',
            'Tesseract':   'OCR (Texterkennung)',
            'python-docx': 'Word-Dokumente',
            'openpyxl':    'Excel-Dateien',
        }

        for name, verfuegbar in methoden.items():
            zeile = tk.Frame(self.bibl_frame, bg=FARBEN['bg2'])
            zeile.pack(fill='x', pady=1)

            symbol = '✅' if verfuegbar else '⚠️'
            farbe  = FARBEN['green'] if verfuegbar else FARBEN['yellow']

            tk.Label(zeile, text=symbol, bg=FARBEN['bg2'], width=2).pack(side='left')
            tk.Label(zeile, text=name,
                     bg=FARBEN['bg2'], fg=farbe,
                     font=('SF Pro Text', 10, 'bold') if sys.platform == 'darwin'
                           else ('Segoe UI', 9, 'bold'),
                     width=14, anchor='w').pack(side='left')
            tk.Label(zeile, text=beschreibungen.get(name, ''),
                     bg=FARBEN['bg2'], fg=FARBEN['fg2'],
                     font=('SF Pro Text', 9) if sys.platform == 'darwin'
                           else ('Segoe UI', 8)).pack(side='left')

        if not all(methoden.values()):
            hinweis = tk.Label(
                self.bibl_frame,
                text="Fehlende Bibliotheken: pip3 install -r requirements.txt",
                bg=FARBEN['bg2'], fg=FARBEN['yellow'],
                font=('SF Pro Text', 9) if sys.platform == 'darwin'
                      else ('Segoe UI', 8),
                wraplength=340
            )
            hinweis.pack(anchor='w', pady=(6, 0))

    def _ordner_hinzufuegen(self):
        pfad = filedialog.askdirectory(title="Ordner auswählen")
        if pfad:
            if pfad not in self.ausgewaehlte_pfade:
                self.ausgewaehlte_pfade.append(pfad)
                self.pfad_listbox.insert('end', f"📁 {pfad}")
            self._log(f"Ordner hinzugefügt: {pfad}", 'info')

    def _dateien_hinzufuegen(self):
        pfade = filedialog.askopenfilenames(
            title="Dateien auswählen",
            filetypes=[
                ("Alle Dateien", "*.*"),
                ("PDF", "*.pdf"),
                ("Bilder", "*.jpg *.jpeg *.png *.tiff *.tif *.bmp *.heic"),
                ("Office", "*.docx *.xlsx *.doc *.xls"),
            ]
        )
        for pfad in pfade:
            if pfad not in self.ausgewaehlte_pfade:
                self.ausgewaehlte_pfade.append(pfad)
                self.pfad_listbox.insert('end', f"📄 {os.path.basename(pfad)}")
        if pfade:
            self._log(f"{len(pfade)} Datei(en) hinzugefügt", 'info')

    def _pfad_entfernen(self):
        auswahl = self.pfad_listbox.curselection()
        if auswahl:
            idx = auswahl[0]
            self.pfad_listbox.delete(idx)
            self.ausgewaehlte_pfade.pop(idx)

    def _pfade_leeren(self):
        self.ausgewaehlte_pfade.clear()
        self.pfad_listbox.delete(0, 'end')

    def _alle_loeschen(self):
        if messagebox.askyesno("Bestätigung",
                                "Alle Dokumente aus der Datenbank löschen?\n"
                                "Die Original-Dateien bleiben erhalten."):
            db.delete_alle_dokumente()
            self.app.set_status("Alle Dokumente gelöscht.", FARBEN['yellow'])
            self._log("Alle Dokumente aus der Datenbank gelöscht.", 'warning')

    def _parse_jahre(self) -> list:
        """Parst die Jahr-Eingabe"""
        text = self.jahre_var.get().strip()
        if not text:
            return []
        jahre = []
        for teil in text.replace(';', ',').split(','):
            teil = teil.strip()
            if '-' in teil:
                try:
                    von, bis = teil.split('-')
                    jahre.extend(range(int(von), int(bis)+1))
                except ValueError:
                    pass
            else:
                try:
                    jahre.append(int(teil))
                except ValueError:
                    pass
        return jahre

    def _scan_starten(self):
        if not self.ausgewaehlte_pfade:
            messagebox.showwarning("Kein Ordner",
                                    "Bitte zuerst Ordner oder Dateien auswählen.")
            return

        self._abbrechen = False
        self.scan_btn.configure(state='disabled')
        self.stop_btn.configure(state='normal')
        self.fortschritt_var.set(0)

        jahre = self._parse_jahre()
        self._log("=" * 50, 'header')
        self._log(f"SCAN GESTARTET  –  {datetime.now().strftime('%d.%m.%Y %H:%M')}", 'header')
        if jahre:
            self._log(f"Filter: Jahre {', '.join(str(j) for j in jahre)}", 'info')
        else:
            self._log("Alle Jahre werden gescannt.", 'info')
        self._log(f"Pfade: {len(self.ausgewaehlte_pfade)}", 'info')

        self._scan_thread = threading.Thread(
            target=self._scan_worker,
            args=(liste := list(self.ausgewaehlte_pfade), jahre),
            daemon=True
        )
        self._scan_thread.start()

    def _scan_worker(self, pfade: list, jahre: list):
        """Läuft im Hintergrund-Thread"""
        scanner = DateiScanner(fortschritt_callback=self._fortschritt_callback)
        gefunden = scanner.scan_ordner(pfade, jahre, self.opt_alle_endungen.get())

        self._aktualisiere_stats('gefunden', len(gefunden))
        self._log(f"{len(gefunden)} Dateien gefunden.", 'success')

        if scanner.fehler:
            self._log(f"{len(scanner.fehler)} Fehler beim Scannen.", 'warning')

        verarbeitet = 0
        fehler = 0

        for i, datei_info in enumerate(gefunden):
            if self._abbrechen:
                self._log("Scan abgebrochen.", 'warning')
                break

            pfad = datei_info['dateipfad']
            name = datei_info['dateiname']

            # Fortschritt Phase 2
            self._fortschritt_callback(
                int(50 + (i / max(len(gefunden), 1)) * 50),
                i, len(gefunden),
                f"Verarbeite: {name}"
            )

            try:
                # Text extrahieren
                text, methode = self.prozessor.extrahiere_text(pfad)

                # Klassifizieren
                dok_typ, steuer_haupt, steuer_sub = \
                    self.klassifizierer.klassifiziere(text, name)

                # Daten extrahieren
                betrag    = self.extraktor.extrahiere_betrag(text)
                datum, _  = self.extraktor.extrahiere_datum(text)
                lieferant = self.extraktor.extrahiere_lieferant(text)
                steuerjahr = self.extraktor.extrahiere_steuerjahr(
                    text, pfad,
                    int(datei_info.get('steuerjahr', datetime.now().year))
                )

                # Thumbnail
                thumbnail_pfad = None
                if self.opt_thumbnail.get():
                    thumb_dir = os.path.join(
                        os.path.expanduser("~"), ".steuerapp", "thumbnails"
                    )
                    thumb_name = f"{abs(hash(pfad))}.png"
                    thumbnail_pfad = os.path.join(thumb_dir, thumb_name)
                    self.prozessor.erstelle_thumbnail(pfad, thumbnail_pfad)

                # In DB speichern
                daten = {
                    'dateiname':      name,
                    'dateipfad':      pfad,
                    'dateigroesse':   datei_info.get('dateigroesse', 0),
                    'dateiendung':    datei_info.get('dateiendung', ''),
                    'erkannter_text': text[:5000] if text else '',
                    'dok_typ':        dok_typ,
                    'steuer_haupt':   steuer_haupt,
                    'steuer_sub':     steuer_sub,
                    'datum':          datum,
                    'betrag':         betrag,
                    'lieferant':      lieferant,
                    'steuerjahr':     steuerjahr,
                    'thumbnail':      thumbnail_pfad,
                }
                db.upsert_dokument(daten)

                verarbeitet += 1
                self._aktualisiere_stats('verarbeitet', verarbeitet)

                typ_label = DOK_TYPEN.get(dok_typ, dok_typ)
                betrag_str = f" | {betrag:.2f} €" if betrag else ""
                self._log(
                    f"  ✓ {name[:40]} → {typ_label}{betrag_str}",
                    'success'
                )

            except Exception as e:
                fehler += 1
                self._aktualisiere_stats('fehler', fehler)
                self._log(f"  ✗ {name}: {e}", 'error')

        self._aktualisiere_stats('erkannt', verarbeitet)

        # Fertig
        self.frame.after(0, self._scan_fertig, verarbeitet, fehler)

    def _scan_fertig(self, verarbeitet: int, fehler: int):
        self.scan_btn.configure(state='normal')
        self.stop_btn.configure(state='disabled')
        self.fortschritt_var.set(100)

        self._log("=" * 50, 'header')
        self._log(
            f"SCAN ABGESCHLOSSEN: {verarbeitet} Dokumente verarbeitet, "
            f"{fehler} Fehler.",
            'header'
        )

        self.app.set_status(
            f"Scan fertig: {verarbeitet} Dokumente verarbeitet.",
            FARBEN['green']
        )
        self.app.nach_scan()

    def _scan_abbrechen(self):
        self._abbrechen = True
        self.stop_btn.configure(state='disabled')

    def _fortschritt_callback(self, prozent, aktuell, gesamt, nachricht):
        self.frame.after(0, self._update_fortschritt, prozent, nachricht)

    def _update_fortschritt(self, prozent, nachricht):
        self.fortschritt_var.set(prozent)
        self.fortschritt_label.configure(text=nachricht)

    def _aktualisiere_stats(self, key, wert):
        self.frame.after(0, lambda: self.stats_labels[key].configure(text=str(wert)))

    def _log(self, nachricht: str, tag: str = 'info'):
        def _do():
            self.log_text.configure(state='normal')
            self.log_text.insert('end', nachricht + '\n', tag)
            self.log_text.see('end')
            self.log_text.configure(state='disabled')
        self.frame.after(0, _do)
