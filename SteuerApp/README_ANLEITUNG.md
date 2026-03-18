# SteuerApp – Steuererklärung Assistent

**Version 2.0** | macOS Intel (2020+) & Apple Silicon (M1–M5)

---

## Was kann diese App?

SteuerApp hilft Ihnen, Ihre Steuererklärung vorzubereiten:

- **Alle Dateitypen scannen**: PDF, JPEG, PNG, TIFF, HEIC, DOCX, XLSX und viele mehr
- **OCR-Texterkennung**: Erkennt Text in gescannten Dokumenten und Fotos
- **Automatische Klassifizierung**: Erkennt Rechnungen, Versicherungen, Gehaltsabrechnungen usw.
- **Steuerliche Kategorisierung**: Ordnet Dokumente den richtigen Anlagen zu (Anlage N, EÜR usw.)
- **Beträge & Daten extrahieren**: Findet automatisch Geldbeträge und Rechnungsdaten
- **Mehrere Jahre**: Kein festes Jahres-Limit
- **Export**: PDF-Bericht, Excel-Tabelle, vollständiges Steuerberater-Paket

---

## Installation (macOS)

### Schritt 1: Installationsskript ausführen

Öffnen Sie das Terminal (Spotlight: "Terminal") und geben Sie ein:

```bash
cd ~/Downloads/SteuerApp
chmod +x install_mac.sh
./install_mac.sh
```

Das Skript installiert automatisch:
- Python 3.12 (falls nicht vorhanden)
- Alle benötigten Bibliotheken (PyMuPDF, Pillow, usw.)
- Tesseract OCR mit deutschen Sprachdaten

### Schritt 2: App starten

**Option A: Terminal**
```bash
cd ~/Downloads/SteuerApp
python3 main.py
```

**Option B: Doppelklick**
- Rechtsklick auf `SteuerApp.command`
- → "Öffnen" wählen
- Beim ersten Start "Öffnen" bestätigen

---

## Erste Schritte

### 1. Ordner auswählen (Scanner-Tab)

1. Klicken Sie auf **"+ Ordner hinzufügen"**
2. Wählen Sie den Ordner mit Ihren Steuer-Unterlagen
3. Geben Sie das Steuerjahr ein (z.B. `2024`)
4. Klicken Sie **"Scan starten"**

**Unterstützte Dateitypen:**
- PDF, JPG/JPEG, PNG, TIFF, HEIC, WebP, BMP
- DOCX (Word), XLSX (Excel)
- TXT, CSV, HTML

### 2. Dokumente prüfen (Dokumente-Tab)

Alle gescannten Dokumente werden in einer Tabelle angezeigt:
- **Beträge** werden automatisch erkannt
- **Kategorie** kann manuell geändert werden
- Dokumente mit **✓** markieren (geprüft)
- **Rechtsklick** für weitere Optionen

### 3. Steuerliche Übersicht (Steuer-Tab)

Hier sehen Sie:
- **Kategorien-Übersicht**: Alle Ausgaben und Einnahmen sortiert
- **EÜR**: Einnahmen-Überschuss-Rechnung (für Selbständige)
- **Anlage N**: Zusammenfassung für Arbeitnehmer
- **Hinweise**: Steuerliche Tipps und Pauschalen

### 4. Export (Export-Tab)

Erstellen Sie für Ihren Steuerberater:

| Export | Inhalt |
|--------|--------|
| **PDF-Bericht** | Vollständiger Steuerbericht, alle Dokumente, EÜR |
| **Excel-Tabelle** | Detaillierte Tabelle, Kategorien, EÜR |
| **Steuerberater-Paket** | Sortierte Belege + Berichte in einem Ordner |

---

## Steuerliche Kategorien

| Kategorie | Anlage | Beispiele |
|-----------|--------|-----------|
| Gehalt/Lohn | Anlage N | Gehaltsabrechnung, Lohnbescheinigung |
| Werbungskosten | Anlage N | Fahrtkosten, Arbeitsmittel, Fortbildung |
| Betriebsausgaben | EÜR | Bürokosten, Reisen (Selbständige) |
| Versicherungen | Anlage SA | Kranken-, Haftpflicht-, Lebensversicherung |
| Spenden | Anlage SA | Zuwendungsbestätigungen |
| Arzt/Medizin | Außerg. Belastungen | Arztkosten, Medikamente, Hilfsmittel |
| Haushaltsnahe | §35a | Handwerker, Haushaltshilfe |

---

## Tipps & Hinweise

### Dokumente vorbereiten
- Gut belichtete Fotos oder Scans liefern bessere OCR-Ergebnisse
- Ordner mit aussagekräftigen Namen helfen bei der Klassifizierung
- Unterordner nach Jahren sind empfehlenswert

### Qualität verbessern
- **Beträge prüfen**: Manchmal werden falsche Beträge erkannt
- **Kategorie korrigieren**: Rechtsklick → "Kategorie ändern"
- **Notizen**: Für schwer erkennbare Dokumente eine Notiz hinzufügen

### Für den Steuerberater
- Nutzen Sie das **Steuerberater-Paket** für eine übersichtliche Übergabe
- Alle Belege werden automatisch nach Kategorien sortiert
- Eine Checkliste und ein Protokoll werden mitgeneriert

---

## Technische Details

- **Datenbank**: SQLite in `~/.steuerapp/steuerapp.db`
- **Thumbnails**: `~/.steuerapp/thumbnails/`
- **Plattform**: macOS 11+ (Intel und Apple Silicon)
- **Python**: 3.8 oder neuer

### Bibliotheken
| Bibliothek | Funktion |
|------------|----------|
| PyMuPDF | PDF-Text-Extraktion |
| Pillow | Bildverarbeitung |
| pytesseract | OCR (Texterkennung) |
| python-docx | Word-Dokumente |
| openpyxl | Excel-Dateien |
| reportlab | PDF-Berichte erstellen |

---

## Häufige Fragen

**Q: OCR funktioniert nicht?**
A: Tesseract muss installiert sein: `brew install tesseract tesseract-lang`

**Q: PDF wird nicht gelesen?**
A: PyMuPDF installieren: `pip3 install PyMuPDF`

**Q: Die App startet nicht?**
A: `install_mac.sh` ausführen oder manuell: `pip3 install -r requirements.txt`

**Q: Wo werden die Daten gespeichert?**
A: In `~/.steuerapp/steuerapp.db` — nur lokal auf Ihrem Mac, keine Cloud.

---

## Datenschutz

Alle Daten bleiben **ausschließlich auf Ihrem Mac**. Es werden keine Daten an Server gesendet. Die App funktioniert vollständig offline.

---

*SteuerApp v2.0 – Für macOS Intel & Apple Silicon*
