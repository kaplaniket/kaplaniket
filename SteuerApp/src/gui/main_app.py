"""
Haupt-Fenster der SteuerApp
"""

import tkinter as tk
from tkinter import ttk, messagebox
import os
import sys
import threading
from datetime import datetime

from ..constants import APP_NAME, APP_VERSION, FARBEN
from .. import database as db
from .scan_tab import ScanTab
from .documents_tab import DocumentsTab
from .tax_tab import TaxTab
from .export_tab import ExportTab


class SteuerApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title(f"{APP_NAME} v{APP_VERSION}")
        self.root.geometry("1200x800")
        self.root.minsize(900, 600)

        # App-Icon setzen (wenn vorhanden)
        icon_pfad = os.path.join(os.path.dirname(__file__), '..', '..', 'assets', 'icon.png')
        if os.path.exists(icon_pfad):
            try:
                icon = tk.PhotoImage(file=icon_pfad)
                self.root.iconphoto(True, icon)
            except Exception:
                pass

        # Aktuelles Steuerjahr
        self.aktuelles_jahr = tk.IntVar(value=datetime.now().year - 1)

        self._setup_styles()
        self._erstelle_gui()
        self._setup_callbacks()

    def _setup_styles(self):
        style = ttk.Style()
        style.theme_use('clam')

        bg  = FARBEN['bg2']
        fg  = FARBEN['fg']
        acc = FARBEN['accent']
        bg3 = FARBEN['bg3']

        style.configure('.',
                         background=bg, foreground=fg,
                         font=('SF Pro Text', 11) if sys.platform == 'darwin'
                              else ('Segoe UI', 10))
        style.configure('TFrame', background=bg)
        style.configure('TLabel', background=bg, foreground=fg)
        style.configure('TButton',
                         background=acc, foreground='#000',
                         relief='flat', padding=(12, 6),
                         font=('SF Pro Text', 11, 'bold') if sys.platform == 'darwin'
                              else ('Segoe UI', 10, 'bold'))
        style.map('TButton',
                  background=[('active', '#60a5fa'), ('pressed', '#3b82f6')])

        style.configure('Danger.TButton', background=FARBEN['red'], foreground='#000')
        style.configure('Success.TButton', background=FARBEN['green'], foreground='#000')
        style.configure('Warning.TButton', background=FARBEN['yellow'], foreground='#000')

        style.configure('TNotebook', background=FARBEN['bg'], tabmargins=[2, 5, 0, 0])
        style.configure('TNotebook.Tab',
                         background=bg3, foreground=fg,
                         padding=[16, 8], font=('SF Pro Text', 11) if sys.platform == 'darwin'
                                           else ('Segoe UI', 10))
        style.map('TNotebook.Tab',
                  background=[('selected', acc)],
                  foreground=[('selected', '#000')])

        style.configure('Treeview',
                         background='#252535', foreground=fg,
                         fieldbackground='#252535',
                         rowheight=26, font=('SF Pro Text', 10) if sys.platform == 'darwin'
                                             else ('Segoe UI', 9))
        style.configure('Treeview.Heading',
                         background=FARBEN['bg3'], foreground=fg,
                         relief='flat', font=('SF Pro Text', 10, 'bold') if sys.platform == 'darwin'
                                              else ('Segoe UI', 9, 'bold'))
        style.map('Treeview',
                  background=[('selected', acc)],
                  foreground=[('selected', '#000')])

        style.configure('TEntry',
                         background='#252535', foreground=fg,
                         fieldbackground='#252535',
                         insertcolor=fg, relief='flat')
        style.configure('TCombobox',
                         background='#252535', foreground=fg,
                         fieldbackground='#252535')
        style.configure('TScrollbar', background=bg3, troughcolor=bg, relief='flat')
        style.configure('TProgressbar',
                         background=acc, troughcolor=bg, relief='flat')
        style.configure('TLabelframe', background=bg, foreground=acc)
        style.configure('TLabelframe.Label', background=bg, foreground=acc,
                         font=('SF Pro Text', 11, 'bold') if sys.platform == 'darwin'
                              else ('Segoe UI', 10, 'bold'))
        style.configure('TSeparator', background=bg3)

        self.root.configure(bg=FARBEN['bg'])

    def _erstelle_gui(self):
        # ── Header ──────────────────────────────────────────────
        header = tk.Frame(self.root, bg=FARBEN['bg'], height=60)
        header.pack(fill='x', padx=0, pady=0)
        header.pack_propagate(False)

        logo_label = tk.Label(
            header,
            text="📊 SteuerApp",
            bg=FARBEN['bg'],
            fg=FARBEN['accent'],
            font=('SF Pro Display', 18, 'bold') if sys.platform == 'darwin'
                  else ('Segoe UI', 16, 'bold')
        )
        logo_label.pack(side='left', padx=20, pady=10)

        # Jahr-Auswahl
        jahr_frame = tk.Frame(header, bg=FARBEN['bg'])
        jahr_frame.pack(side='right', padx=20, pady=10)

        tk.Label(
            jahr_frame, text="Steuerjahr:", bg=FARBEN['bg'], fg=FARBEN['fg2'],
            font=('SF Pro Text', 11) if sys.platform == 'darwin' else ('Segoe UI', 10)
        ).pack(side='left', padx=(0, 8))

        jahre = list(range(2000, datetime.now().year + 1))
        self.jahr_combo = ttk.Combobox(
            jahr_frame,
            textvariable=self.aktuelles_jahr,
            values=[str(j) for j in sorted(jahre, reverse=True)],
            width=6, state='readonly'
        )
        self.jahr_combo.pack(side='left')

        # Trennlinie
        sep = tk.Frame(self.root, bg=FARBEN['bg3'], height=1)
        sep.pack(fill='x')

        # ── Tabs ─────────────────────────────────────────────────
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill='both', expand=True, padx=0, pady=0)

        self.scan_tab     = ScanTab(self.notebook, self)
        self.docs_tab     = DocumentsTab(self.notebook, self)
        self.tax_tab      = TaxTab(self.notebook, self)
        self.export_tab   = ExportTab(self.notebook, self)

        self.notebook.add(self.scan_tab.frame,   text="  📂 Scanner  ")
        self.notebook.add(self.docs_tab.frame,   text="  📋 Dokumente  ")
        self.notebook.add(self.tax_tab.frame,    text="  🧾 Steuer  ")
        self.notebook.add(self.export_tab.frame, text="  📤 Export  ")

        # ── Statusleiste ─────────────────────────────────────────
        status_bar = tk.Frame(self.root, bg=FARBEN['bg3'], height=28)
        status_bar.pack(fill='x', side='bottom')
        status_bar.pack_propagate(False)

        self.status_var = tk.StringVar(value="Bereit. Wählen Sie Ordner zum Scannen.")
        self.status_label = tk.Label(
            status_bar, textvariable=self.status_var,
            bg=FARBEN['bg3'], fg=FARBEN['fg2'],
            font=('SF Pro Text', 10) if sys.platform == 'darwin' else ('Segoe UI', 9),
            anchor='w'
        )
        self.status_label.pack(side='left', padx=12, pady=4)

        stats = db.get_statistiken()
        self.stats_label = tk.Label(
            status_bar,
            text=f"v{APP_VERSION}",
            bg=FARBEN['bg3'], fg=FARBEN['fg2'],
            font=('SF Pro Text', 10) if sys.platform == 'darwin' else ('Segoe UI', 9)
        )
        self.stats_label.pack(side='right', padx=12, pady=4)

    def _setup_callbacks(self):
        self.aktuelles_jahr.trace('w', self._jahr_geaendert)

    def _jahr_geaendert(self, *args):
        try:
            jahr = int(self.aktuelles_jahr.get())
            self.docs_tab.lade_dokumente(steuerjahr=jahr)
            self.tax_tab.aktualisiere(steuerjahr=jahr)
        except (ValueError, tk.TclError):
            pass

    def set_status(self, text: str, farbe: str = None):
        """Statusleiste aktualisieren"""
        self.status_var.set(text)
        if farbe:
            self.status_label.configure(fg=farbe)
        else:
            self.status_label.configure(fg=FARBEN['fg2'])
        self.root.update_idletasks()

    def nach_scan(self):
        """Wird nach erfolgreichem Scan aufgerufen"""
        jahr = self.aktuelles_jahr.get()
        self.docs_tab.lade_dokumente(steuerjahr=jahr)
        self.tax_tab.aktualisiere(steuerjahr=jahr)
        self.notebook.select(1)  # Dokumente-Tab

    def run(self):
        self.root.mainloop()
