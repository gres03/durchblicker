# durchblicker-automation

Playwright-Automatisierung, die KFZ-Versicherungsdaten in den
durchblicker.at KFZ-Rechner einträgt. Füllt nur aus — klickt nie auf
"Berechnen"/"Zum Ergebnis" und sendet nichts ab.

## Setup

1. `git clone` bzw. Ordner kopieren, dann ins Verzeichnis wechseln.
2. Setup-Skript ausführen:
   - Windows: `.\setup.ps1`
   - macOS/Linux: `./setup.sh`
   (legt venv an, installiert Abhängigkeiten + Playwright-Chromium, kopiert
   `.env.example` nach `.env`)
3. `.env` mit den eigenen Zugangsdaten ausfüllen (`DURCHBLICKER_USER`,
   `DURCHBLICKER_PASS`).
4. Login testen: `python login.py` (öffnet sichtbaren Browser, loggt ein,
   speichert Session-State nach `./state/`). Bei geändertem Login-Formular:
   `python login.py --manual`.
5. Erkundung/Weiterentwicklung: `python explore.py` (dumpt den Rechner-Wizard
   Schritt für Schritt nach `./exploration/`, siehe `feldkarte.md`).

## Stand

Phase 1 (Login + Erkundung) ist abgeschlossen, siehe `feldkarte.md` für die
vollständige Feldkarte und offene TODOs. `fall.json`/`fill.py`/`confirm.py`
(Phasen 2–4) folgen im nächsten Schritt.

## Struktur

- `login.py` — Login, Session-State-Speicherung
- `explore.py` — Wizard-Erkundung, dumpt Felder/Screenshots nach `./exploration/`
- `feldkarte.md` — Ergebnis der Erkundung: Locators, Feldtypen, Pflichtfelder, Abhängigkeiten
- `state/` — Playwright Storage State (gitignored)
- `logs/` — Fehler-Screenshots/Dumps (gitignored)
- `exploration/` — Rohdaten aus explore.py (Screenshots, JSON, Accessibility-Snapshots)
