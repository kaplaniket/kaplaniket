#!/usr/bin/env python3
"""
SteuerApp – Steuererklärung Assistent
Hauptprogramm

Unterstützt: macOS Intel (2020+) und Apple Silicon (M1–M5)
Python 3.8 oder neuer erforderlich.
"""

import sys
import os

# Sicherstellen, dass der App-Ordner im Pfad ist
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def pruefe_python_version():
    if sys.version_info < (3, 8):
        print("FEHLER: Python 3.8 oder neuer ist erforderlich.")
        print(f"Aktuelle Version: {sys.version}")
        sys.exit(1)


def pruefe_tkinter():
    try:
        import tkinter
        return True
    except ImportError:
        print("FEHLER: tkinter ist nicht installiert.")
        print("Auf macOS: brew install python-tk")
        print("Oder: python.org Python installieren (enthält tkinter)")
        return False


def zeige_installations_hinweis():
    """Zeigt einen Hinweis auf fehlende optionale Bibliotheken"""
    optionale = {
        'fitz':        ('PyMuPDF',      'pip3 install PyMuPDF'),
        'PIL':         ('Pillow',       'pip3 install Pillow'),
        'pytesseract': ('pytesseract',  'pip3 install pytesseract'),
        'docx':        ('python-docx',  'pip3 install python-docx'),
        'openpyxl':    ('openpyxl',     'pip3 install openpyxl'),
        'reportlab':   ('reportlab',    'pip3 install reportlab'),
    }

    fehlend = []
    for modul, (name, install) in optionale.items():
        try:
            __import__(modul)
        except ImportError:
            fehlend.append(f"  {name:15} → {install}")

    if fehlend:
        print("\n── Optionale Bibliotheken (empfohlen) ──────────────")
        print("Für volle Funktionalität installieren:")
        for zeile in fehlend:
            print(zeile)
        print("\nOder alle auf einmal:")
        print("  pip3 install -r requirements.txt")
        print("────────────────────────────────────────────────────\n")


def main():
    pruefe_python_version()

    if not pruefe_tkinter():
        sys.exit(1)

    zeige_installations_hinweis()

    # App starten
    try:
        from src.gui.main_app import SteuerApp
        app = SteuerApp()
        app.run()
    except ImportError as e:
        print(f"Import-Fehler: {e}")
        print("Bitte sicherstellen, dass alle Abhängigkeiten installiert sind:")
        print("  pip3 install -r requirements.txt")
        sys.exit(1)
    except Exception as e:
        import traceback
        print(f"Fehler beim Starten der App: {e}")
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
