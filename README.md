# durchblicker-automation

Playwright-Automatisierung, die KFZ-Versicherungsdaten in den
durchblicker.at KFZ-Rechner einträgt. Füllt nur aus — klickt nie auf
"Berechnen"/"Zum Ergebnis" und sendet nichts ab.

## Setup (neuer PC, 2 Schritte)

1. `git clone https://github.com/gres03/durchblicker.git && cd durchblicker`
2. Setup-Skript ausführen:
   - Windows: `.\setup.ps1` im Terminal, oder einfach `Setup_starten.bat` doppelklicken
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

## Auf einem weiteren PC einrichten (z.B. für einen Kollegen/Angehörigen)

Am einfachsten **ohne Git/GitHub auf dem anderen PC**, wenn dieses Projekt
bereits in einem OneDrive-Ordner liegt (wie hier):

1. Diesen Projektordner (bzw. den übergeordneten OneDrive-Ordner) mit dem
   OneDrive-Konto der anderen Person teilen (OneDrive-Web: Ordner
   auswählen -> "Freigeben"). Sie muss die Freigabe annehmen und den
   Ordner zu ihrem eigenen OneDrive hinzufügen.
2. Auf ihrem PC: OneDrive synct den Ordner automatisch herunter. Rechtsklick
   auf den Projektordner -> "Immer auf diesem Gerät behalten" (nicht nur
   "Bei Bedarf verfügbar"), damit Python auf echte Dateien zugreifen kann.
3. Python 3.11+ auf ihrem PC installieren, falls noch nicht vorhanden
   (python.org, beim Installer "Add python.exe to PATH" anhaken).
4. Einmalig `Setup_starten.bat` doppelklicken (Windows) bzw. `./setup.sh`
   ausführen (Mac/Linux). Falls eine `.env` schon mitsynct ist (z.B. weil
   du sie schon eingerichtet hast), werden dabei automatisch dieselben
   Zugangsdaten übernommen — es wird dann NICHT erneut nachgefragt.
   Möchte die andere Person einen eigenen, unabhängigen Gemini-API-Key
   (kostenlos, https://aistudio.google.com/apikey), einfach vorher den
   `GEMINI_API_KEY`-Wert in `.env` von Hand ändern.
5. Danach reicht im Alltag ein Doppelklick auf `Webapp_starten.bat`.

**Updates:** Ein `git pull` auf deinem PC synct die geänderten Dateien
über OneDrive automatisch zum anderen PC — ohne dass dort irgendwer Git
anfassen muss.

**Wichtig:** Nicht gleichzeitig auf beiden PCs an derselben Web-Oberfläche
arbeiten (dieselbe `aktueller_fall.json` in `web_uploads/`) — das kann zu
OneDrive-Konfliktkopien führen. Immer nacheinander verwenden.

Braucht die andere Person stattdessen eine eigene, unabhängige Kopie ohne
geteiltes OneDrive (z.B. per USB-Stick): denselben Projektordner
kopieren (der `.venv/`-Unterordner kann weggelassen werden, `Setup_starten.bat`
legt ihn neu an), dann ab Schritt 3 oben weitermachen.

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
und oeffnet automatisch den Browser. Ein oder mehrere Dokumente hochladen
(z.B. Zulassungsschein UND Kundenformular gleichzeitig -- Gemini kombiniert
die Angaben aus allen zu einem Fall) -> automatische Erkennung ueber die
Gemini-API (kostenloses Kontingent, `GEMINI_API_KEY` in `.env`) -> nur bei
echtem Klaerungsbedarf ein kurzes Formular -> Ausfuellen + Verifikation im
geoeffneten Browserfenster. `extract.py` kapselt den Gemini-Aufruf; wirft
`ExtraktionsFehler` mit Klartext-Meldung statt zu raten, wenn kein Key
gesetzt ist oder die Antwort kein gueltiges JSON war. Ein Zulassungsschein
allein enthaelt keine Kundenangaben (Geburtsdatum, PLZ, bestehende
Versicherung, ...) -- diese Felder bleiben dann unvermeidbar klaerungs-
beduerftig, nicht weil die Erkennung schlecht ist, sondern weil die Daten
schlicht nicht im Dokument stehen.

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

**Live im Browser klaeren statt vorab abtippen:** Reine Kundenauskuenfte,
die auf keinem Fahrzeugdokument stehen (Geburtsdatum, PLZ, E-Mail,
bestehende Versicherung, Zweitwagen, Erstbesitzer, Anmeldung als,
Firmenbucheintrag, Kaskovariante, ...) muessen NICHT vorab auf `/pruefen`
eingetippt werden -- `fill.py` haelt beim Ausfuellen genau an dieser
Stelle an und laesst den Menschen den Wert DIREKT im bereits geoeffneten
Browserfenster eintragen (siehe `FeldKlaerungNoetig`,
`LIVE_KLAERBARE_FELDER` in `portals/durchblicker.py`), bevor automatisch
mit dem Rest weitergemacht wird. `/pruefen` zeigt diese Felder nur noch
informativ ("Im Browser eintragen"), nicht als Eingabefeld.

Nur Felder, bei denen ein Live-Klick in einen NICHT erkundeten Wizard-
Zweig fuehren wuerde (z.B. "bereits zugelassen? Nein" oeffnet einen
unerkundeten Neuanmeldungs-Zweig), bleiben zwingend vorab
klaerungsbeduerftig -- sonst wuesste `fill()` beim Fortsetzen nicht,
welche Felder als naechstes kommen. Siehe `bereit_zum_ausfuellen()` in
fill.py und die Kommentare an `LIVE_KLAERBARE_FELDER`.

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

**Aktuell unterstuetzter Wizard-Pfad:** siehe `feldkarte.md`. Fahrzeug-
Identifikation ueber Nationalcode ODER ueber "Marke und Modell" (inkl.
Treibstoff/Motorleistung/Bauart/Tueren-Kaskade und Ergebnislisten-
Auswahl bei mehrdeutigen Varianten) sind beide implementiert. Fall.json-
Kombinationen ausserhalb des live erkundeten Pfads (z.B. Neuanmeldung
eines Neuwagens, Leasing/Kredit) lehnt `fill.py` mit Klartext-Grund ab,
statt zu raten (`DurchblickerPortal.unterstuetzter_pfad`).

## Struktur

- `ANLEITUNG.md` — nicht-technische Bedienungsanleitung fuer den Alltagsgebrauch
- `app.py` — lokale Web-Oberflaeche (Upload -> Erkennung -> Pruefen -> Ausfuellen), `templates/`
- `extract.py` — automatische Dokumentenerkennung ueber die Gemini API (kostenloses Kontingent)
- `extraktion_anfrage.txt` — Textvorlage fuer die manuelle Dokumentenerkennung via claude.ai (Fallback ohne API-Key)
- `Setup_starten.bat` — Doppelklick-Wrapper fuer `setup.ps1` (Windows, umgeht die PowerShell-Ausfuehrungsrichtlinie)
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
