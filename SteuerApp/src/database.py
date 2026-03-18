"""
SQLite Datenbank für die Steuer-App
Speichert alle gescannten Dokumente und ihre Metadaten
"""

import sqlite3
import json
import os
from datetime import datetime
from pathlib import Path


DB_PATH = os.path.join(os.path.expanduser("~"), ".steuerapp", "steuerapp.db")


def get_connection():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    with get_connection() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS dokumente (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                dateiname       TEXT NOT NULL,
                dateipfad       TEXT NOT NULL UNIQUE,
                dateigroesse    INTEGER,
                dateiendung     TEXT,
                erkannter_text  TEXT,
                dok_typ         TEXT DEFAULT 'sonstiges',
                steuer_haupt    TEXT,
                steuer_sub      TEXT,
                datum           TEXT,
                betrag          REAL,
                waehrung        TEXT DEFAULT 'EUR',
                lieferant       TEXT,
                beschreibung    TEXT,
                steuerjahr      INTEGER,
                geprueft        INTEGER DEFAULT 0,
                notiz           TEXT,
                tags            TEXT,
                scan_datum      TEXT,
                thumbnail       TEXT,
                created_at      TEXT DEFAULT (datetime('now')),
                updated_at      TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS scans (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                pfad        TEXT NOT NULL,
                steuerjahr  INTEGER,
                anzahl      INTEGER DEFAULT 0,
                datum       TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS einstellungen (
                schluessel  TEXT PRIMARY KEY,
                wert        TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_dok_steuerjahr ON dokumente(steuerjahr);
            CREATE INDEX IF NOT EXISTS idx_dok_typ ON dokumente(dok_typ);
            CREATE INDEX IF NOT EXISTS idx_dok_steuer ON dokumente(steuer_haupt, steuer_sub);
        """)


# ─── Dokument CRUD ────────────────────────────────────────────────

def upsert_dokument(daten: dict) -> int:
    with get_connection() as conn:
        existing = conn.execute(
            "SELECT id FROM dokumente WHERE dateipfad = ?", (daten['dateipfad'],)
        ).fetchone()

        daten['updated_at'] = datetime.now().isoformat()
        if 'scan_datum' not in daten:
            daten['scan_datum'] = datetime.now().isoformat()

        felder = [
            'dateiname', 'dateipfad', 'dateigroesse', 'dateiendung',
            'erkannter_text', 'dok_typ', 'steuer_haupt', 'steuer_sub',
            'datum', 'betrag', 'waehrung', 'lieferant', 'beschreibung',
            'steuerjahr', 'geprueft', 'notiz', 'tags', 'scan_datum',
            'thumbnail', 'updated_at'
        ]

        if existing:
            sets = ', '.join(f"{f} = :{f}" for f in felder if f in daten)
            conn.execute(
                f"UPDATE dokumente SET {sets} WHERE id = {existing['id']}", daten
            )
            return existing['id']
        else:
            daten.setdefault('created_at', datetime.now().isoformat())
            cols = [f for f in felder if f in daten] + ['created_at']
            vals = ', '.join(f":{c}" for c in cols)
            cols_str = ', '.join(cols)
            cur = conn.execute(
                f"INSERT INTO dokumente ({cols_str}) VALUES ({vals})", daten
            )
            return cur.lastrowid


def get_dokumente(steuerjahr=None, dok_typ=None, steuer_haupt=None,
                  steuer_sub=None, geprueft=None, suche=None) -> list:
    query = "SELECT * FROM dokumente WHERE 1=1"
    params = []

    if steuerjahr:
        query += " AND steuerjahr = ?"
        params.append(steuerjahr)
    if dok_typ:
        query += " AND dok_typ = ?"
        params.append(dok_typ)
    if steuer_haupt:
        query += " AND steuer_haupt = ?"
        params.append(steuer_haupt)
    if steuer_sub:
        query += " AND steuer_sub = ?"
        params.append(steuer_sub)
    if geprueft is not None:
        query += " AND geprueft = ?"
        params.append(1 if geprueft else 0)
    if suche:
        query += " AND (dateiname LIKE ? OR lieferant LIKE ? OR erkannter_text LIKE ? OR notiz LIKE ?)"
        s = f"%{suche}%"
        params.extend([s, s, s, s])

    query += " ORDER BY datum DESC, created_at DESC"

    with get_connection() as conn:
        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]


def update_dokument_feld(dok_id: int, **kwargs):
    kwargs['updated_at'] = datetime.now().isoformat()
    sets = ', '.join(f"{k} = ?" for k in kwargs)
    vals = list(kwargs.values()) + [dok_id]
    with get_connection() as conn:
        conn.execute(f"UPDATE dokumente SET {sets} WHERE id = ?", vals)


def delete_dokument(dok_id: int):
    with get_connection() as conn:
        conn.execute("DELETE FROM dokumente WHERE id = ?", (dok_id,))


def delete_alle_dokumente():
    with get_connection() as conn:
        conn.execute("DELETE FROM dokumente")


# ─── Statistiken ─────────────────────────────────────────────────

def get_statistiken(steuerjahr=None) -> dict:
    with get_connection() as conn:
        basis = "FROM dokumente WHERE 1=1"
        params = []
        if steuerjahr:
            basis += " AND steuerjahr = ?"
            params.append(steuerjahr)

        total = conn.execute(f"SELECT COUNT(*) {basis}", params).fetchone()[0]
        summe = conn.execute(
            f"SELECT COALESCE(SUM(betrag),0) {basis}", params
        ).fetchone()[0]

        nach_typ = {}
        for row in conn.execute(
            f"SELECT dok_typ, COUNT(*) as n, COALESCE(SUM(betrag),0) as s {basis} GROUP BY dok_typ",
            params
        ).fetchall():
            nach_typ[row['dok_typ']] = {'anzahl': row['n'], 'summe': row['s']}

        nach_haupt = {}
        for row in conn.execute(
            f"SELECT steuer_haupt, steuer_sub, COUNT(*) as n, COALESCE(SUM(betrag),0) as s "
            f"{basis} GROUP BY steuer_haupt, steuer_sub",
            params
        ).fetchall():
            h = row['steuer_haupt'] or 'UNBEKANNT'
            if h not in nach_haupt:
                nach_haupt[h] = {}
            nach_haupt[h][row['steuer_sub'] or 'sonstiges'] = {
                'anzahl': row['n'], 'summe': row['s']
            }

        jahre = [r[0] for r in conn.execute(
            "SELECT DISTINCT steuerjahr FROM dokumente WHERE steuerjahr IS NOT NULL ORDER BY steuerjahr"
        ).fetchall()]

        return {
            'total': total,
            'gesamtsumme': summe,
            'nach_typ': nach_typ,
            'nach_steuer': nach_haupt,
            'jahre': jahre,
        }


# ─── Einstellungen ────────────────────────────────────────────────

def set_einstellung(key: str, value):
    with get_connection() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO einstellungen (schluessel, wert) VALUES (?, ?)",
            (key, json.dumps(value))
        )


def get_einstellung(key: str, default=None):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT wert FROM einstellungen WHERE schluessel = ?", (key,)
        ).fetchone()
        if row:
            return json.loads(row['wert'])
        return default


# Initialisierung beim Import
init_db()
