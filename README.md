# durchblicker-automation

Playwright-Automatisierung, die KFZ-Versicherungsdaten in den
durchblicker.at KFZ-Rechner einträgt. Füllt nur aus — klickt nie auf
"Berechnen"/"Zum Ergebnis" und sendet nichts ab.

## Setup (neuer PC, 2 Schritte)

1. `git clone https://github.com/gres03/durchblicker.git && cd durchblicker`
2. Setup-Skript ausführen:
   - Windows: `.\setup.ps1`
   - macOS/Linux: `./setup.sh`

   Das Skript legt eine venv an, installiert Abhängigkeiten + Playwright-
   Chromium und fragt beim ersten Lauf interaktiv nach den durchblicker.at-
   Zugangsdaten (Passwort maskiert), die es lokal in `.env` speichert —
   diese Datei wird nie committed. Bei einem erneuten Lauf (z.B. nach
   `git pull`) wird eine bestehende `.env` nicht angetastet.

Danach: Login testen mit `python login.py` (öffnet sichtbaren Browser,
loggt ein, speichert Session-State nach `./state/`). Bei geändertem
Login-Formular: `python login.py --manual`.

Erkundung/Weiterentwicklung: `python explore.py` (dumpt den Rechner-Wizard
Schritt für Schritt nach `./exploration/`, siehe `feldkarte.md`).

## Stand

Alle 4 Phasen sind abgeschlossen und end-to-end gegen die echte Seite
getestet (bis zum letzten Schritt vor "Zum Ergebnis" -- dieser Button wird
nie geklickt, siehe unten).

- Phase 1 (Login + Erkundung): siehe `feldkarte.md`.
- Phase 2 (Datenmodell): siehe `fall.schema.json`/`fall.json`/`mapping.py`.
- Phase 3 (Genauigkeits-Gate): siehe `validate.py`/`confirm.py`.
- Phase 4 (Ausfuellen + Verifikation): siehe `fill.py`/`portals/`.

**Kompletter Ablauf** (Rohdaten -> ausgefuelltes Formular):

1. Rohdaten (aus einem Kundendokument extrahiert, Struktur wie `fall.json`
   aber mit unuebersetztem Freitext in den enum-/boolean-Feldern) durch
   `python mapping.py rohdaten.json -o fall.json` schicken.
2. `python confirm.py fall.json` -- zeigt eine Tabelle, klaert jedes
   unsichere/unplausible Feld interaktiv und schreibt Korrekturen zurueck.
   Erst wenn `confirm.py` mit Exit-Code 0 durchlaeuft (alle Zeilen gruen),
   ist der Fall bestaetigt.
3. `python fill.py fall.json` -- prueft das bestaetigte fall.json ein
   zweites Mal (kein Flag zum Ueberspringen), oeffnet einen sichtbaren
   Browser, fuellt den Wizard Schritt fuer Schritt aus, verifiziert jedes
   Feld direkt nach dem Ausfuellen durch Zuruecklesen aus dem DOM und
   druckt eine Soll/Ist-Tabelle. Bei Abweichungen: laute Warnung,
   Exit-Code 1. Der Browser bleibt in jedem Fall offen, das Skript wartet
   auf Enter -- **es wird nie auf "Zum Ergebnis"/"Berechnen" geklickt.**

`validate.py fall.json` kann auch einzeln als reiner Pruefbericht (JSON,
kein Terminal-UI) aufgerufen werden.

**Aktuell unterstuetzter Wizard-Pfad:** siehe `feldkarte.md`. Fall.json-
Kombinationen ausserhalb des live erkundeten Hauptpfads (z.B. "Marke und
Modell" statt Nationalcode, Neuanmeldung, Leasing/Kredit, Einzelunternehmen)
lehnt `fill.py` mit Klartext-Grund ab, statt zu raten
(`DurchblickerPortal.unterstuetzter_pfad`).

## Struktur

- `login.py` — CLI-Einstiegspunkt fuer den Login (Logik in `portals/durchblicker.py`)
- `explore.py` — Wizard-Erkundung, dumpt Felder/Screenshots nach `./exploration/`
- `feldkarte.md` — Ergebnis der Erkundung: Locators, Feldtypen, Pflichtfelder, Abhängigkeiten
- `fall.schema.json` — Datenmodell fuer einen KFZ-Fall (JSON Schema)
- `fall.json` — Beispiel-Fall (VW Golf, siehe feldkarte.md-Testfall)
- `synonyme.json` — Freitext-zu-Optionswert-Tabelle, ohne Codeaenderung erweiterbar
- `mapping.py` — uebersetzt Rohdaten-Freitext in exakte Dropdown-Optionen
- `validate.py` — Schema-/Plausibilitaets-/Quercheck-Pruefbericht fuer ein fall.json
- `confirm.py` — interaktives Genauigkeits-Gate (Terminal-Tabelle, Korrekturen), Voraussetzung fuer fill.py
- `fill.py` — CLI-Einstiegspunkt fuers Ausfuellen (Logik in `portals/durchblicker.py`)
- `portals/base.py` — abstrakte Portal-Schnittstelle (login/navigate/fill/verify/unterstuetzter_pfad)
- `portals/durchblicker.py` — Implementierung fuer durchblicker.at. Ein zweites Portal ist ein neues Modul hier, ohne Aenderung an `login.py`/`fill.py`
- `state/` — Playwright Storage State (gitignored)
- `logs/` — Fehler-Screenshots/HTML-Dumps (gitignored)
- `exploration/` — Rohdaten aus explore.py (Screenshots, JSON, Accessibility-Snapshots)
