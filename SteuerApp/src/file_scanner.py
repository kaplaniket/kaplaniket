"""
Datei-Scanner: Durchsucht Ordner rekursiv nach allen Dokumenten
"""

import os
import hashlib
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Callable, Optional

from .constants import ALL_EXTENSIONS


class DateiScanner:
    def __init__(self, fortschritt_callback: Optional[Callable] = None):
        self.fortschritt_callback = fortschritt_callback
        self.gefundene_dateien: List[Dict] = []
        self.fehler: List[str] = []
        self._abbrechen = False

    def abbrechen(self):
        self._abbrechen = True

    def scan_ordner(self, pfade: List[str],
                    jahre: Optional[List[int]] = None,
                    alle_endungen: bool = False) -> List[Dict]:
        """
        Scannt die angegebenen Pfade rekursiv.
        - jahre: Falls angegeben, nur Dateien mit passendem Jahr
        - alle_endungen: Falls True, alle Dateitypen einschließen
        """
        self._abbrechen = False
        self.gefundene_dateien = []
        self.fehler = []

        erlaubte_endungen = set(ALL_EXTENSIONS) if not alle_endungen else None

        alle_pfade = []
        for pfad in pfade:
            p = Path(pfad)
            if p.is_file():
                alle_pfade.append(p)
            elif p.is_dir():
                for datei in p.rglob('*'):
                    if datei.is_file():
                        alle_pfade.append(datei)

        gesamt = len(alle_pfade)
        self._melde_fortschritt(0, gesamt, "Starte Scan...")

        for i, datei_pfad in enumerate(alle_pfade):
            if self._abbrechen:
                break

            self._melde_fortschritt(i, gesamt, f"Scanne: {datei_pfad.name}")

            try:
                # Endung prüfen
                endung = datei_pfad.suffix.lower()
                if erlaubte_endungen and endung not in erlaubte_endungen:
                    continue

                # Versteckte Dateien überspringen
                if datei_pfad.name.startswith('.'):
                    continue

                # System-Ordner überspringen
                teile = datei_pfad.parts
                skip_ordner = {'__pycache__', '.git', 'node_modules', '.DS_Store',
                               'Library', 'System', 'Applications'}
                if any(t in skip_ordner for t in teile):
                    continue

                stat = datei_pfad.stat()
                mtime = datetime.fromtimestamp(stat.st_mtime)

                # Jahr-Filter
                if jahre:
                    if mtime.year not in jahre:
                        # Auch nach Jahr im Pfad suchen
                        pfad_str = str(datei_pfad)
                        jahr_im_pfad = any(str(j) in pfad_str for j in jahre)
                        if not jahr_im_pfad:
                            continue

                datei_info = {
                    'dateiname':    datei_pfad.name,
                    'dateipfad':    str(datei_pfad),
                    'dateigroesse': stat.st_size,
                    'dateiendung':  endung,
                    'aenderungsdatum': mtime.isoformat(),
                    'steuerjahr':   mtime.year,
                }

                self.gefundene_dateien.append(datei_info)

            except (PermissionError, OSError) as e:
                self.fehler.append(f"{datei_pfad}: {e}")
                continue

        self._melde_fortschritt(gesamt, gesamt, f"Fertig. {len(self.gefundene_dateien)} Dateien gefunden.")
        return self.gefundene_dateien

    def _melde_fortschritt(self, aktuell: int, gesamt: int, nachricht: str):
        if self.fortschritt_callback:
            prozent = int((aktuell / max(gesamt, 1)) * 100)
            self.fortschritt_callback(prozent, aktuell, gesamt, nachricht)


def datei_hash(pfad: str) -> str:
    """MD5-Hash einer Datei für Duplikat-Erkennung"""
    try:
        h = hashlib.md5()
        with open(pfad, 'rb') as f:
            for block in iter(lambda: f.read(65536), b''):
                h.update(block)
        return h.hexdigest()
    except Exception:
        return ''


def formatiere_groesse(bytes_groesse: int) -> str:
    """Lesbare Dateigröße"""
    for einheit in ['B', 'KB', 'MB', 'GB']:
        if bytes_groesse < 1024:
            return f"{bytes_groesse:.1f} {einheit}"
        bytes_groesse /= 1024
    return f"{bytes_groesse:.1f} TB"
