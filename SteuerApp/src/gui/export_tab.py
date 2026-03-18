"""
Export-Tab: PDF, Excel, Steuerberater-Paket erstellen
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import os
import sys
import threading
import subprocess
from datetime import datetime

from ..constants import FARBEN
from ..exporter import Exporter
from .. import database as db


class ExportTab:
    def __init__(self, notebook, app):
        self.app = app
        self.frame = ttk.Frame(notebook)
        self.exporter = Exporter()
        self._erstelle_gui()

    def _erstelle_gui(self):
        haupt = tk.Frame(self.frame, bg=FARBEN['bg'])
        haupt.pack(fill='both', expand=True, padx=30, pady=30)

        # Titel
        tk.Label(
            haupt,
            text="📤 Export & Berichte",
            bg=FARBEN['bg'], fg=FARBEN['accent'],
            font=('SF Pro Display', 16, 'bold') if sys.platform == 'darwin'
                  else ('Segoe UI', 14, 'bold')
        ).pack(anchor='w', pady=(0, 4))

        tk.Label(
            haupt,
            text="Erstellen Sie Berichte für Ihren Steuerberater",
            bg=FARBEN['bg'], fg=FARBEN['fg2'],
            font=('SF Pro Text', 11) if sys.platform == 'darwin'
                  else ('Segoe UI', 10)
        ).pack(anchor='w', pady=(0, 20))

        # ── Export-Optionen ───────────────────────────────────────
        optionen_frame = tk.Frame(haupt, bg=FARBEN['bg'])
        optionen_frame.pack(fill='x', pady=(0, 20))

        # Jahr-Auswahl
        jahr_frame = ttk.LabelFrame(optionen_frame, text="  Steuerjahr  ", padding=12)
        jahr_frame.pack(fill='x', pady=(0, 12))

        tk.Label(jahr_frame, text="Exportieren Sie für ein oder mehrere Jahre:",
                 bg=FARBEN['bg2'], fg=FARBEN['fg2']).pack(anchor='w', pady=(0, 6))

        jahr_row = tk.Frame(jahr_frame, bg=FARBEN['bg2'])
        jahr_row.pack(fill='x')

        self.export_alle_jahre = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            jahr_row, text="Alle Jahre exportieren",
            variable=self.export_alle_jahre,
            command=self._toggle_jahresauswahl
        ).pack(side='left', padx=(0, 16))

        tk.Label(jahr_row, text="oder Jahr:",
                 bg=FARBEN['bg2'], fg=FARBEN['fg2']).pack(side='left', padx=(0, 8))

        stats = db.get_statistiken()
        jahre = stats.get('jahre', [])
        self.export_jahr_var = tk.StringVar(
            value=str(self.app.aktuelles_jahr.get())
        )
        self.export_jahr_combo = ttk.Combobox(
            jahr_row, textvariable=self.export_jahr_var,
            values=[str(j) for j in sorted(jahre, reverse=True)],
            width=8, state='readonly'
        )
        self.export_jahr_combo.pack(side='left')

        # ── Export-Karten ─────────────────────────────────────────
        karten_frame = tk.Frame(haupt, bg=FARBEN['bg'])
        karten_frame.pack(fill='both', expand=True)

        # Karte 1: PDF-Bericht
        self._erstelle_export_karte(
            karten_frame,
            symbol="📄",
            titel="PDF-Bericht",
            beschreibung=(
                "Vollständiger Steuerbericht als PDF.\n"
                "Enthält: Übersicht, Kategoriensummary,\n"
                "alle Dokumente, EÜR"
            ),
            btn_text="PDF erstellen",
            btn_cmd=self._export_pdf,
            btn_style='Success.TButton'
        )

        # Karte 2: Excel
        self._erstelle_export_karte(
            karten_frame,
            symbol="📊",
            titel="Excel-Tabelle",
            beschreibung=(
                "Detaillierte Excel-Tabelle.\n"
                "Enthält: Alle Dokumente, Kategorien,\n"
                "EÜR, Steuerberater-Übergabe"
            ),
            btn_text="Excel erstellen",
            btn_cmd=self._export_excel,
            btn_style='TButton'
        )

        # Karte 3: Steuerberater-Paket
        self._erstelle_export_karte(
            karten_frame,
            symbol="📁",
            titel="Steuerberater-Paket",
            beschreibung=(
                "Komplettes Übergabepaket:\n"
                "• Sortierte Belege in Unterordnern\n"
                "• PDF-Bericht + Excel-Tabelle\n"
                "• README mit Checkliste"
            ),
            btn_text="Paket erstellen",
            btn_cmd=self._export_paket,
            btn_style='Warning.TButton'
        )

        # ── Fortschritt ───────────────────────────────────────────
        fort_frame = ttk.LabelFrame(haupt, text="  Status  ", padding=10)
        fort_frame.pack(fill='x', pady=(16, 0))

        self.export_status = tk.Label(
            fort_frame, text="Bereit.",
            bg=FARBEN['bg2'], fg=FARBEN['fg2'],
            font=('SF Pro Text', 11) if sys.platform == 'darwin'
                  else ('Segoe UI', 10)
        )
        self.export_status.pack(anchor='w', pady=(0, 6))

        self.export_progress = ttk.Progressbar(
            fort_frame, length=600, mode='indeterminate'
        )
        self.export_progress.pack(fill='x')

        # ── Log ───────────────────────────────────────────────────
        log_frame = ttk.LabelFrame(haupt, text="  Protokoll  ", padding=8)
        log_frame.pack(fill='both', expand=True, pady=(12, 0))

        self.log_text = tk.Text(
            log_frame, height=8,
            bg='#1a1a2e', fg=FARBEN['fg2'],
            relief='flat',
            font=('SF Mono', 10) if sys.platform == 'darwin'
                  else ('Consolas', 9),
            state='disabled'
        )
        log_scroll = ttk.Scrollbar(log_frame, orient='vertical',
                                    command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=log_scroll.set)
        log_scroll.pack(side='right', fill='y')
        self.log_text.pack(fill='both', expand=True)

        self.log_text.tag_configure('success', foreground=FARBEN['green'])
        self.log_text.tag_configure('error',   foreground=FARBEN['red'])
        self.log_text.tag_configure('info',    foreground=FARBEN['fg2'])

    def _erstelle_export_karte(self, parent, symbol, titel, beschreibung,
                                btn_text, btn_cmd, btn_style):
        karte = tk.Frame(parent, bg=FARBEN['bg2'],
                          relief='flat', bd=1)
        karte.pack(side='left', fill='both', expand=True, padx=8, pady=8)

        tk.Label(
            karte, text=symbol,
            bg=FARBEN['bg2'], fg=FARBEN['accent'],
            font=('SF Pro Display', 36) if sys.platform == 'darwin'
                  else ('Segoe UI', 28)
        ).pack(pady=(16, 4))

        tk.Label(
            karte, text=titel,
            bg=FARBEN['bg2'], fg=FARBEN['fg'],
            font=('SF Pro Text', 13, 'bold') if sys.platform == 'darwin'
                  else ('Segoe UI', 11, 'bold')
        ).pack()

        tk.Label(
            karte, text=beschreibung,
            bg=FARBEN['bg2'], fg=FARBEN['fg2'],
            font=('SF Pro Text', 10) if sys.platform == 'darwin'
                  else ('Segoe UI', 9),
            justify='center', wraplength=200
        ).pack(pady=8, padx=16)

        ttk.Button(
            karte, text=btn_text,
            command=btn_cmd, style=btn_style
        ).pack(pady=(4, 16), padx=20, fill='x')

    def _toggle_jahresauswahl(self):
        state = 'disabled' if self.export_alle_jahre.get() else 'readonly'
        self.export_jahr_combo.configure(state=state)

    def _get_jahr(self):
        if self.export_alle_jahre.get():
            return None
        try:
            return int(self.export_jahr_var.get())
        except (ValueError, tk.TclError):
            return self.app.aktuelles_jahr.get()

    def _export_pdf(self):
        jahr = self._get_jahr()
        ziel = filedialog.asksaveasfilename(
            title="PDF speichern",
            defaultextension=".pdf",
            filetypes=[("PDF", "*.pdf")],
            initialfile=f"Steuerbericht_{jahr or 'alle'}.pdf"
        )
        if ziel:
            self._starte_export(self._pdf_worker, ziel, jahr)

    def _export_excel(self):
        jahr = self._get_jahr()
        ziel = filedialog.asksaveasfilename(
            title="Excel speichern",
            defaultextension=".xlsx",
            filetypes=[("Excel", "*.xlsx"), ("CSV", "*.csv")],
            initialfile=f"Steuerübersicht_{jahr or 'alle'}.xlsx"
        )
        if ziel:
            self._starte_export(self._excel_worker, ziel, jahr)

    def _export_paket(self):
        jahr = self._get_jahr()
        ziel_ordner = filedialog.askdirectory(
            title="Ordner für das Steuerberater-Paket auswählen"
        )
        if ziel_ordner:
            self._starte_export(self._paket_worker, ziel_ordner, jahr)

    def _starte_export(self, worker_func, ziel, jahr):
        self.export_progress.start()
        self.export_status.configure(
            text="Export läuft...", fg=FARBEN['yellow']
        )
        threading.Thread(
            target=worker_func, args=(ziel, jahr), daemon=True
        ).start()

    def _pdf_worker(self, ziel, jahr):
        try:
            dokumente = db.get_dokumente(steuerjahr=jahr)
            statistiken = db.get_statistiken(steuerjahr=jahr)
            ok = self.exporter.export_pdf(dokumente, ziel, jahr or 0, statistiken)
            self.frame.after(0, self._export_fertig, ok, ziel, 'PDF')
        except Exception as e:
            self.frame.after(0, self._export_fehler, str(e))

    def _excel_worker(self, ziel, jahr):
        try:
            dokumente = db.get_dokumente(steuerjahr=jahr)
            statistiken = db.get_statistiken(steuerjahr=jahr)
            ok = self.exporter.export_excel(dokumente, ziel, jahr or 0, statistiken)
            self.frame.after(0, self._export_fertig, ok, ziel, 'Excel')
        except Exception as e:
            self.frame.after(0, self._export_fehler, str(e))

    def _paket_worker(self, ziel_ordner, jahr):
        try:
            dokumente = db.get_dokumente(steuerjahr=jahr)
            statistiken = db.get_statistiken(steuerjahr=jahr)
            paket_pfad = self.exporter.erstelle_steuerberater_paket(
                dokumente, ziel_ordner, jahr or datetime.now().year - 1,
                statistiken
            )
            self.frame.after(0, self._export_fertig, True, paket_pfad, 'Paket')
        except Exception as e:
            self.frame.after(0, self._export_fehler, str(e))

    def _export_fertig(self, ok: bool, ziel: str, typ: str):
        self.export_progress.stop()
        if ok:
            self.export_status.configure(
                text=f"✅ {typ} erfolgreich erstellt!", fg=FARBEN['green']
            )
            self._log(f"✅ {typ} erstellt: {ziel}", 'success')
            self.app.set_status(f"{typ} erfolgreich exportiert.", FARBEN['green'])

            if messagebox.askyesno("Export erfolgreich",
                                    f"{typ} wurde erstellt:\n{ziel}\n\nJetzt öffnen?"):
                self._oeffne_datei(ziel)
        else:
            self.export_status.configure(
                text=f"⚠️ Export abgeschlossen (Fallback verwendet)",
                fg=FARBEN['yellow']
            )
            self._log(f"⚠️ Export mit Einschränkungen: {ziel}", 'info')

    def _export_fehler(self, fehler: str):
        self.export_progress.stop()
        self.export_status.configure(
            text=f"❌ Fehler beim Export", fg=FARBEN['red']
        )
        self._log(f"❌ Fehler: {fehler}", 'error')
        messagebox.showerror("Export-Fehler",
                              f"Fehler beim Exportieren:\n{fehler}")

    def _oeffne_datei(self, pfad: str):
        try:
            if sys.platform == 'darwin':
                subprocess.run(['open', pfad])
            elif sys.platform == 'win32':
                os.startfile(pfad)
            else:
                subprocess.run(['xdg-open', pfad])
        except Exception:
            pass

    def _log(self, nachricht: str, tag: str = 'info'):
        self.log_text.configure(state='normal')
        zeitstempel = datetime.now().strftime('%H:%M:%S')
        self.log_text.insert('end', f"[{zeitstempel}] {nachricht}\n", tag)
        self.log_text.see('end')
        self.log_text.configure(state='disabled')
