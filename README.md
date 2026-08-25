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
   Zugangsdaten (Passwort maskiert) sowie optional einem kostenlosen
   Gemini-API-Schlüssel (für die automatische Dokumentenerkennung in der
   Web-Oberfläche, siehe unten — kann leer gelassen und später
   nachgetragen werden). Alles landet lokal in `.env`, das nie committed
   wird. Bei einem erneuten Lauf (z.B. nach `git pull`) wird eine
   bestehende `.env` nicht angetastet.

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

**Web-Oberflaeche** (empfohlener Weg, siehe `ANLEITUNG.md`): `python app.py`
(oder `Webapp_starten.bat`/`webapp_starten.sh`) startet einen lokalen Server
und oeffnet automatisch den Browser. Dokument hochladen -> automatische
Erkennung ueber die Gemini-API (kostenloses Kontingent, `GEMINI_API_KEY` in
`.env`) -> nur bei echtem Klaerungsbedarf ein kurzes Formular -> Ausfuellen
+ Verifikation im geoeffneten Browserfenster. `extract.py` kapselt den
Gemini-Aufruf; wirft `ExtraktionsFehler` mit Klartext-Meldung statt zu
raten, wenn kein Key gesetzt ist oder die Antwort kein gueltiges JSON war.

**Kommandozeile** (kein Gemini-Key noetig, Dokumentenerkennung manuell ueber
claude.ai -- siehe `extraktion_anfrage.txt`): Rohdaten (Struktur wie
`fall.json`, aber mit unuebersetztem Freitext in den enum-/boolean-Feldern)
mit einem einzigen Befehl verarbeiten:

```
python start.py rohdaten.json
```

(Windows: alternativ die Datei per Drag & Drop auf `Fall_starten.bat`
ziehen; macOS/Linux: `./fall_starten.sh rohdaten.json`.)

`start.py` fuehrt `mapping.py` -> `confirm.py` -> `fill.py` automatisch
nacheinander aus (dieselben Funktionen, die auch `app.py` fuer die
Web-Oberflaeche wiederverwendet). Ist ein Fall von Anfang an vollstaendig
und plausibel, laeuft das komplett ohne jede Eingabe durch; nur bei
tatsaechlichem Klaerungsbedarf (siehe `confirm.py` unten) wird kurz
nachgefragt.

**Formular-Standards statt Rueckfrage:** `mapping.py` (`_wende_formular_standards_an`)
uebernimmt bei fuenf Feldern automatisch einen unbedenklichen Formular-Default,
wenn das Dokument dazu nichts hergibt, statt nachzufragen: Bonus/Malus-Stufe
(Standard "9 - Einsteigerstufe", entspricht dem Formular-Default selbst),
Sonderausstattung (Slider-Default bleibt unveraendert), Kasko-Zusatzdeckung
und Finanzierung (Standard jeweils "Nein"/keine, damit nichts ungefragt
unterstellt wird) und Nationalitaet (Standard "Österreich"). Das ist bewusst
NICHT geraten, sondern die jeweils sicherste/am wenigsten unterstellende
Annahme -- transparent sichtbar am `quelle`-Text jedes so gesetzten Felds.

**Ableitung statt Rueckfrage:** `mapping.py` (`_leite_erstbesitzer_ab`) bestimmt
"Erstbesitzer" automatisch aus zwei bereits vorhandenen Datumsangaben, wenn
BEIDE sicher vorliegen: sind "Erstzulassung des PKW" und "Zulassung auf den
Halter" identisch, ist der Halter zwangslaeufig Erstbesitzer, sind sie
unterschiedlich, zwangslaeufig nicht. Das ist Logik aus vorhandenen Fakten,
kein Raten -- fehlt eine der beiden Daten, bleibt das Feld weiterhin
klaerungsbeduerftig statt eine falsche Sicherheit vorzutaeuschen.

Alle anderen Felder (Geburtsdatum, PLZ, Nationalcode, ob das Fahrzeug
ueberhaupt schon zugelassen ist, bestehende Versicherung, Zweitwagen,
Kaskovariante bei aktiver Kaskodeckung, ...) bleiben bei Unklarheit
weiterhin zwingend klaerungsbeduerftig: entweder weil es eine
Pflichtfrage des Rechners ohne Formular-Default ist (z.B. "bereits
zugelassen?" -- unser Code unterstuetzt bisher nur den Ja-Zweig), oder
weil es eine reine Kundenauskunft ist, die auf keinem Fahrzeugdokument
steht (bestehende Versicherung, Zweitwagen im Haushalt) und daher so oder
so vom Kunden/Berater kommen muss, egal wie gut die Dokumentenerkennung
ist.

Die einzelnen Schritte lassen sich weiterhin separat aufrufen (z.B. zum
Debuggen):

1. `python mapping.py rohdaten.json -o fall.json` -- uebersetzt Freitext in
   exakte Formularwerte.
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

- `ANLEITUNG.md` — nicht-technische Bedienungsanleitung fuer den Alltagsgebrauch
- `app.py` — lokale Web-Oberflaeche (Upload -> Erkennung -> Pruefen -> Ausfuellen), `templates/`
- `extract.py` — automatische Dokumentenerkennung ueber die Gemini API (kostenloses Kontingent)
- `extraktion_anfrage.txt` — Textvorlage fuer die manuelle Dokumentenerkennung via claude.ai (Fallback ohne API-Key)
- `Webapp_starten.bat` / `webapp_starten.sh` — Start-Wrapper fuer `app.py`
- `start.py` — ein Befehl fuer den kompletten CLI-Ablauf (mapping -> confirm -> fill)
- `Fall_starten.bat` / `fall_starten.sh` — Drag-and-drop-Wrapper um `start.py`
- `web_uploads/` — hochgeladene Dokumente + aktueller Fall der Web-Oberflaeche (gitignored, enthaelt personenbezogene Daten)
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
