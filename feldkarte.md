# Feldkarte: durchblicker.at KFZ-Rechner (Autoversicherung)

Erstellt durch `explore.py` am 2026-08-24. Alle Angaben live mit Playwright
gegen `https://durchblicker.at/` verifiziert (Chromium, kein Login noetig --
der Rechner ist oeffentlich erreichbar; Login dient nur zum Speichern von
Vergleichen). Rohdaten (Screenshots, JSON-Dumps, Accessibility-Snapshots) in
`./exploration/`.

**Abgedeckter Pfad:** Auto -> Nationaler Zulassungscode -> Zulassungsdaten
(zugelassen=Ja, Erstbesitzer=Nein) -> Bonus/Malus-Stufe -> Produkt
(durchblicker Empfehlung) -> Person (Versicherungsnehmer). Das ist der
letzte Schritt vor "Zum Ergebnis" -- dieser Button wurde NICHT geklickt.

**Nicht erkundete Nebenzweige** (siehe TODO-Liste am Ende): "Nein" bei
zugelassen (Neuwagen-Anmeldung), Leasing/Kredit-Finanzierung, "Günstiger
Preis"/"Deckungen selbst festlegen" statt Empfehlung. (Erstbesitzer=Ja,
Kasko-Zusatzdeckung, Einzelunternehmen und "Marke und Modell" sind seit
2026-08-25 implementiert, siehe unten.)

**Update 2026-08-25 (Marke und Modell):** Kompletter Fallback-Weg fuer
Dokumente ohne Nationalcode live erkundet und implementiert. Kaskade:
Marke -> Modell -> Treibstoff -> Motorleistung (kW) -> Bauart -> Anzahl
Tueren -> Ergebnisliste mit ggf. mehreren passenden Fahrzeugtypen (bis zu
11 in einem Testlauf gesehen), aus der per Variante-Text eindeutig
ausgewaehlt werden muss. Deutlich aufwaendiger als der Nationalcode-Weg:
- Alle sechs Comboboxen sind durchsuchbar (`get_by_text` + Tippen).
- Manche Felder werden vom Formular selbst schon eindeutig vorbefuellt
  (beobachtet bei einem E-Auto mit nur einer Motorleistung) -- dann NICHT
  anfassen, sonst geht die automatische Vorbelegung verloren.
- Das kW-Feld hat einen unvorhersehbaren PS-Zusatz im Optionstext (z.B.
  "85 kW / 115,5 PS") -- Praefix-Abgleich statt exaktem Textvergleich.
- Die Ergebnisliste-Radios haben (anders als alle anderen Radiogruppen im
  Formular) KEIN `name`-Attribut -- Auswahl ueber Zeilentext + naechster
  Radio-Vorfahre.
- End-to-end getestet: VW Golf, Diesel, 85 kW, Limousine/Sedan, 5 Tueren,
  Variante "1,6 TDI Comfortline" traf unter 11 Ergebniszeilen eindeutig
  "Golf 1,6 TDI Comfortline" -- alle 22 Felder verifiziert.
- Siehe `portals/durchblicker.py` (`_waehle_falls_leer`,
  `_waehle_aus_ergebnisliste`) und `fall.schema.json` (neue Felder
  treibstoff, motorleistung_kw, bauart, tueren, variante jetzt nutzbar).
- **Bug gefunden + gefixt (echter Nutzerfall, 2026-08-25):** Marke-Feld
  "PEUGEOT" aus einem echten Zulassungsschein (Grossbuchstaben-Druck)
  wurde nie gefunden -- Playwrights `exact=True`-Namensvergleich ist
  case-sensitiv, das Formular zeigt aber "Peugeot" (Live-Probe bestaetigt:
  genau 1 Option nach Tippen von "PEUGEOT", Text exakt "Peugeot").
  `Locator.click: Timeout ... waiting for get_by_role("option",
  name="PEUGEOT", exact=True)`. Fix in `_waehle_durchsuchbar`: nach
  fehlgeschlagenem case-sensitivem Treffer wird unter den nach dem Tippen
  tatsaechlich angezeigten Optionen nach genau einem case-insensitiven
  Text-Treffer gesucht (kein Raten -- 0 oder >1 Treffer brechen weiterhin
  klar ab). Betrifft alle durchsuchbaren Freitext-Comboboxen (Marke,
  Modell, Bestehende Versicherung); die zugehoerige Soll/Ist-Verifikation
  (`pruefe(..., ignore_case=True)`) vergleicht dort ebenfalls
  gross-/kleinschreibungs-unabhaengig, damit keine falschen
  Abweichungs-Warnungen entstehen. End-to-end nachgetestet: Peugeot 208,
  Benzin, 55 kW, Bauart/Tueren automatisch aufgeloest, Variante "208 Like
  PureTech 75 S&S" unter 3 Ergebniszeilen eindeutig getroffen -- alle 22
  Felder verifiziert.
- **Bug gefunden + gefixt (echter Nutzerfall, 2026-08-26):** Bauart-Feld
  "Schräghecklimousine" (Karosserie-Fachbegriff aus einem echten Dokument)
  fand keinen Treffer -- `Ausfuellen abgebrochen: Kein Treffer fuer
  'Bauart' = 'Schräghecklimousine' unter den verfuegbaren Optionen
  gefunden.` Anders als beim Marke-Bug (siehe oben) ist das KEIN
  Gross-/Kleinschreibungsproblem, sondern ein Vokabular-Problem: das
  Formular kennt nur eine feste, kleine Kategorienliste, live verifiziert
  ueber mehrere Marken/Modelle (VW Golf, Skoda Octavia, Ford Focus/Mustang,
  VW Tiguan, Fiat Ducato, Renault Espace, Dacia Duster): "Limousine/Sedan",
  "Kombi - PKW", "SUV", "Coupé", "Cabrio/Cabriolet", "MPV", "Kombi
  Transporter", "Bus". Fix: `bauart` ist jetzt in `mapping.py` ein
  Enum-Feld (`ERLAUBTE_WERTE`) mit eigener Synonymtabelle in
  `synonyme.json` (z.B. "schräghecklimousine"/"fließheck"/"steilheck"
  -> "Limousine/Sedan", "kombi"/"break"/"avant" -> "Kombi - PKW",
  "geländewagen" -> "SUV", ...) -- unbekannte Begriffe bleiben weiterhin
  `sicher:false` statt geraten zu werden. `extract.py`/
  `extraktion_anfrage.txt` nennen der Dokumentenerkennung jetzt zusaetzlich
  alle acht Kategorien direkt. End-to-end nachgetestet: VW Golf, Diesel,
  85 kW, Bauart-Rohtext "Schräghecklimousine" -> korrekt zu "Limousine/
  Sedan" uebersetzt und ausgewaehlt -- alle 22 Felder verifiziert.
- **Bug gefunden + gefixt (echter Nutzerfall, 2026-08-26):** Variante-Feld
  "L/P/HNPJ-C1T200" (ein Typenschein-/Genehmigungscode aus dem Dokument,
  keine lesbare Ausstattungslinie) passte zu keiner der 5 gefundenen
  Fahrzeugtypen (Peugeot 208, Benzin, 55 kW): `variante='L/P/HNPJ-C1T200'
  passt nicht eindeutig zu genau einem der 5 gefundenen Fahrzeuge: [...]`.
  Zwei Fixes:
  1. `extract.py`/`extraktion_anfrage.txt` weisen die Dokumentenerkennung
     jetzt explizit an, NUR eine in normaler Sprache lesbare
     Ausstattungslinie (z.B. "Active", "Comfortline") als `variante` zu
     nehmen -- technische Codes (Typenschein-Nummer, Genehmigungsnummer,
     interne Schluessel) fuehren zu `sicher:false`/`wert:null` statt
     einer garantiert unpassenden Rateloesung.
  2. **Strukturelle Sackgasse behoben:** bisher landete JEDER Fehlschlag
     der 'Marke und Modell'-Kaskade (Marke/Modell/Treibstoff/kW/Bauart/
     Tueren/Variante ohne eindeutigen Treffer) auf einer Endseite ohne
     Weg zurueck -- das Feld war durch `/bestaetigen` schon als
     `sicher:true` festgeschrieben und tauchte auf `/pruefen` nicht mehr
     als "Klären" auf, selbst nach "Nächsten Fall bearbeiten" (das setzt
     nur die Upload-Seite zurueck, nicht das schon bestaetigte Feld).
     Neue Exception `portals.base.FeldKlaerungNoetig(feldpfad, optionen)`:
     alle betroffenen Stellen (`_waehle_durchsuchbar` fuer Marke/Modell/
     Bestehende Versicherung, `_waehle_falls_leer` fuer Treibstoff/kW/
     Bauart/Tueren, `_waehle_aus_ergebnisliste` fuer Variante) werfen sie
     jetzt statt eines nackten `RuntimeError` und liefern dabei die am
     Formular tatsaechlich angezeigten Optionen mit. `fill.py`
     (`fuelle_fuer_webapp`) und `app.py` (`/bestaetigen`) fangen sie ab,
     setzen GENAU das betroffene Feld in `aktueller_fall.json` wieder auf
     `sicher:false` (mit den echten Optionen als `quelle`-Hinweistext) und
     leiten zurueck zu `/pruefen` -- der Nutzer kann das eine Feld
     korrigieren, ohne neu hochzuladen oder alle anderen Antworten zu
     verlieren. Live end-to-end getestet (echter durchblicker.at-Server,
     `threaded=True`, zwei aufeinanderfolgende Ausfuell-Versuche im
     SELBEN Flask-Prozess): erster Versuch mit erfundenem Variante-Code
     schlaegt fehl und setzt das Feld zurueck, `/pruefen` zeigt "Klären"
     mit den 3 echten Kandidatennamen, zweiter Versuch mit korrekt
     eingetragenem Namen laeuft vollstaendig durch.

**Update 2026-08-26 (Pause/Fortsetzen statt Retype-Schleife):** Nutzer-
Feedback zum obigen "/pruefen erneut oeffnen"-Fix: das erneute Eintippen
des exakten Kandidatennamens in ein Textfeld ist umstaendlich/fehleranfaellig.
Gewuenscht: bei einer nicht automatisch aufloesbaren Auswahl DIREKT im
bereits geoeffneten Browserfenster klicken koennen, danach uebernimmt die
Automatisierung automatisch den Rest. Grundlegend groesserer Umbau:

- `DurchblickerPortal.fill()` ist jetzt ein GENERATOR. An jeder Stelle in
  der 'Marke und Modell'-Kaskade (Marke, Modell, Treibstoff, kW, Bauart,
  Tueren, Variante, Bestehende Versicherung), an der bisher eine
  `FeldKlaerungNoetig` geworfen wurde, wird sie stattdessen 'ge-yielded'
  (`_versuche_oder_pausiere()`-Helfer) -- die Playwright-Seite bleibt an
  genau dieser Stelle offen und unveraendert, der Aufrufer haelt an. Wird
  der Generator spaeter fortgesetzt (`next()`), wird die fehlgeschlagene
  Aktion NICHT wiederholt (der Mensch hat sie im Browser bereits erledigt)
  -- der jeweils aktuelle DOM-Wert wird einfach neu ausgelesen
  (`page.input_value()`). Verifikationszeilen fuer manuell geklaerte
  Felder zeigen `soll: "(manuell gewählt) <Wert>"` statt eines Soll/Ist-
  Vergleichs (`pruefe_manuell()`).
- **Sonderfall Variante:** anders als alle anderen Kaskade-Felder loescht
  ein Klick auf eine Ergebniszeile die komplette Radioliste aus dem DOM
  und ersetzt sie durch eine "Gewähltes Fahrzeug:"-Bestaetigung (live
  beobachtet -- `is_checked()` auf den (nicht mehr vorhandenen) Radios
  schlaegt danach fehl, auch bei frischer Abfrage). Fix: der automatische
  Erfolgsfall kennt den Zeilentext bereits vorher aus dem Rueckgabewert
  von `_waehle_aus_ergebnisliste()`; der manuelle Fall liest ihn per
  `_gewaehltes_fahrzeug_name()` aus der Bestaetigungs-Anzeige.
- **Kritische Erkenntnis beim Bauen der Web-Anbindung (live verifiziert):**
  Playwrights Sync API bindet eine Seite/einen Browser an das Greenlet-
  Dispatching GENAU des Threads, der `sync_playwright().start()`
  aufgerufen hat. Flasks `threaded=True` startet fuer JEDEN Request einen
  NEUEN Thread -- ein zweiter Request, der versucht, dieselbe (bereits
  pausierte) Seite anzufassen, wirft `playwright._impl._errors.Error:
  cannot switch to a different thread (which happens to have exited)`.
  Live mit einem eigenen Test bestaetigt (Thread A startet Browser+Seite,
  beendet sich, Thread B versucht `page.title()`: exakt dieser Fehler).
  Loesung: `fill.py`'s neue Klasse `FuellSitzung` treibt `portal.fill()`
  in einem EIGENEN, langlebigen Worker-Thread an, der ueber mehrere
  Flask-Requests hinweg am Leben bleibt und bei einer Pause auf einem
  `threading.Event` wartet -- Kommunikation mit den (kurzlebigen)
  Request-Threads ausschliesslich ueber eine thread-sichere `queue.Queue`,
  NIE durch direkten Zugriff auf page/browser von einem anderen Thread.
  `app.py` haelt genau eine `FuellSitzung` in einer Modulvariable
  (`_SITZUNG`, passt zum Rest der App: ein gemeinsames aktueller_fall.json,
  keine Mehrbenutzer-Trennung); neue Route `/weiter_automatisieren` sowie
  Template `klaerung_manuell.html` ("Kurz Ihre Hilfe nötig").
- End-to-end getestet mit einer echten Cross-Thread-Simulation: Worker-
  Thread pausiert bei einer mehrdeutigen Peugeot-208-Variante; eine
  VOELLIG unabhaengige zweite Playwright-Verbindung (per
  `connect_over_cdp`, simuliert einen Menschen mit Maus am bereits
  offenen Fenster) klickt die richtige Option; ein dritter, neuer Thread
  (simuliert einen neuen Flask-Request) ruft nur `fortsetzen()` auf --
  alle drei Threads unterschiedliche Thread-IDs, kein direkter
  Seiten-Zugriff ausserhalb des Worker-Threads. Ergebnis: alle 22 Felder
  verifiziert, `ist` fuer die Variante korrekt "Peugeot 208 Like PureTech
  75 S&S". Der vollautomatische Pfad (kein Pausieren noetig) separat
  nachgetestet und weiterhin unveraendert korrekt.

**Update 2026-08-26 (mehrere Dokumente gleichzeitig hochladbar):**
Nutzer-Feedback: bei nur einem hochgeladenen Zulassungsschein bleiben
viele Felder rot (Geburtsdatum, PLZ, bestehende Versicherung, ...) --
zurecht, denn diese Kundenangaben stehen auf einem Zulassungsschein
schlicht nicht drauf (kein Erkennungsfehler, sondern eine echte Grenze).
Fix: Upload-Seite erlaubt jetzt mehrere Dateien gleichzeitig (`multiple`
am `<input type=file>`, `request.files.getlist("dokument")` in app.py).
`extract.py`'s `extrahiere()` nimmt jetzt einen einzelnen Pfad ODER eine
Liste von Pfaden entgegen und schickt alle Dokumente in EINEM Gemini-
Aufruf (`contents=[PROMPT, Part1, Part2, ...]`) -- der Prompt weist
Gemini an, Angaben aus allen Dokumenten zu einem Fall zu kombinieren und
bei Widerspruechen zwischen den Dokumenten `sicher:false` zu setzen statt
zu raten, welches Dokument recht hat. Live end-to-end getestet: ein
Text-"Zulassungsschein" (Nationalcode, Erstzulassung, Erstbesitzer) und
ein Text-"Kundenformular" (Geburtsdatum, PLZ, E-Mail, bestehende
Versicherung, Zweitwagen, Bonus-Malus-Stufe) zusammen hochgeladen --
Ergebnis nach `mapping.py`/`validate.py`: `ok: true, klaerungsbedarf: 0`,
alle 28 Felder automatisch bestaetigt, keine einzige Nachfrage noetig.

**Update 2026-08-26 (Live-Klaeren fuer praktisch ALLE Felder, nicht nur
Fahrzeug-Variante):** Nutzer-Wunsch nach dem Variante-Pause-Feature:
dieselbe Direkt-im-Browser-Klaerung auch fuer die anderen, aus keinem
Dokument lesbaren Felder (Geburtsdatum, PLZ, bestehende Versicherung,
Zweitwagen, ...) statt sie auf `/pruefen` abtippen zu muessen. Grosser,
aber durchgaengiger Umbau von `fill()`:

- Vier generische Generator-Helfer ergaenzt: `_boolean_oder_pausiere`
  (Ja/Nein-Radiopaar), `_enum_oder_pausiere` (Radiogruppe mit mehreren
  benannten Optionen), `_datum_oder_pausiere` (segmentiertes Datum),
  `_text_oder_pausiere` (einfaches Textfeld), `_durchsuchbar_oder_pausiere`
  (durchsuchbare Combobox). Alle nach demselben Muster: Wert bekannt ->
  normal ausfuellen; Wert `None` -> `FeldKlaerungNoetig` yielden (pausieren,
  Mensch traegt DIREKT im Browser ein), danach den tatsaechlichen DOM-Wert
  zurueckliefern (nie den fall.json-Sollwert vertrauen, wenn manuell
  geklaert wurde).
- Neu live klaerbar (siehe `LIVE_KLAERBARE_FELDER`-Konstante in
  portals/durchblicker.py): `fahrzeug.erstbesitzer`,
  `fahrzeug.erstzulassung_pkw`/`erstzulassung_auf_sie`,
  `fahrzeug.treibstoff`/`motorleistung_kw`/`bauart`/`tueren`/`variante`
  (Kaskade, war schon vorher pausierbar), `versicherungsnehmer.
  bestehende_versicherung`/`zweitwagen`/`anmeldung_als`/
  `firmenbucheintrag`/`geburtsdatum`/`plz`/`email`, `produkt.
  kasko_zusatzdeckung`/`kaskovariante`.
- **Bewusst NICHT live klaerbar** (bleiben vorab pflichtzuklaeren, siehe
  `unterstuetzter_pfad`): `fahrzeug.zugelassen` (nur Ja live erkundet --
  ein Live-Klick auf 'Nein' wuerde in unerkundetes Terrain fuehren, das
  fill() nicht weiter ausfuellen kann), `fahrzeug.finanzierung` (nur
  'Nein' erkundet), `fahrzeug.identifikationsmethode`/`marke`/`modell`
  (steuern, welcher GESAMTE Schritt-1-Zweig ueberhaupt geladen wird --
  koennen strukturell nicht unklar sein, wenn identifikationsmethode
  schon feststeht, siehe Kommentar an der Konstante).
- **Verzweigung folgt jetzt dem TATSAECHLICH beobachteten Wert, nicht dem
  fall.json-Sollwert:** z.B. ob 'Erstzulassung auf Sie' ueberhaupt
  erscheint haengt von der (evtl. live geklaerten) Erstbesitzer-Antwort
  ab, ob 'Firmenbucheintrag' erscheint von der (evtl. live geklaerten)
  Anmeldung-als-Antwort. Wichtig, weil der Mensch bei einer Pause anders
  entscheiden kann als im Dokument angenommen.
- Neue Funktion `bereit_zum_ausfuellen(bericht, portal)` in fill.py:
  ersetzt den bisherigen strikten `bericht["ok"]`-Gate vor dem Start.
  Schema-/Plausibilitaetsfehler blockieren weiterhin hart (echte
  Datenfehler muessen vorab korrigiert werden); alles andere darf offen
  bleiben, wenn der Feldpfad in `portal.LIVE_KLAERBARE_FELDER` steht.
- `/pruefen` zeigt jetzt drei Zustaende statt zwei: gruen (versteckt, wie
  seit dem letzten Update), rot "Klären" (muss hier korrigiert werden --
  Schema-/Plausibilitaetsfehler oder ein NICHT live klaerbares Feld), und
  neu gelb "Im Browser eintragen" (rein informativ, kein Eingabefeld --
  wird beim Ausfuellen automatisch abgefragt).
- End-to-end getestet mit einer Kaskade aus 10 aufeinanderfolgenden
  Pausen in einem einzigen Lauf (Nationalcode-Pfad, praktisch alle
  Kundenfelder unklar: Erstbesitzer, Erstzulassung auf Sie, Bestehende
  Versicherung, Zweitwagen, Kaskovariante, Anmeldung als, Firmenbuch-
  eintrag, Geburtsdatum, PLZ, E-Mail) -- jede Pause per unabhaengiger
  CDP-Verbindung (simulierter Mensch) beantwortet, jeweils von einem
  NEUEN Thread fortgesetzt (simuliert einen neuen Flask-Request). Alle
  18 Felder verifiziert, inklusive korrekter Verzweigung (Erstbesitzer
  live auf 'Nein' gesetzt -> Erstzulassung-auf-Sie-Pause erscheint wie
  erwartet; Anmeldung live auf 'Einzelunternehmen' gesetzt ->
  Firmenbucheintrag-Pause erscheint wie erwartet). Vollautomatischer Pfad
  (Peugeot-Testfall ohne jede Pause) separat nachgetestet, weiterhin
  unveraendert korrekt. `/pruefen`- und `/bestaetigen`-Routen live gegen
  echten Flask-Testclient verifiziert (Drei-Stufen-Anzeige, Start trotz
  vieler unklarer Felder, Plausibilitaetsfehler blockiert weiterhin).

**Update Phase 4 (fill.py, live end-to-end getestet, siehe portals/durchblicker.py):**
- Tippen-zum-Filtern in durchsuchbaren Comboboxen (Baujahr, Bestehende
  Versicherung) live verifiziert -- funktioniert zuverlaessig, auch fuer
  Werte ausserhalb der initial gerenderten Optionen (getestet: Baujahr 2015,
  Versicherer "Wiener Städtische" -- neu zur Optionsliste hinzugefuegt).
- Kasko-Checkbox: `get_by_role("checkbox", name="Kasko", exact=True")`
  live verifiziert (Haftpflicht ist beim Laden bereits `checked`).
- **Bug gefunden + gefixt:** Bei einem bereits VORBEFUELLTEN Datumsfeld
  (z.B. "Erstzulassung des PKW", vom Formular aus dem Baujahr vorbelegt)
  fokussiert ein Klick auf den umschliessenden DIV nicht zuverlaessig das
  "Tag"-Segment, sondern offenbar das zuletzt aktive Segment -- 8 blind
  getippte Ziffern landen dann auf den falschen Segmenten und ergeben ein
  kaputtes Datum. Fix: explizit den "Tag ändern"-Button anklicken
  (`page.locator(selector).get_by_role("button", name="Tag ändern")`).
- **Bug gefunden + gefixt:** Das Feld "Sonderausstattung exakt" verarbeitet
  `"500.0"` (Python-Float-Stringrepraesentation) falsch -- landet als `"5"`
  im Feld. Fix: ganzzahlige Betraege als reinen Ziffernstring ohne `.0`
  senden (siehe `_format_betrag` in portals/durchblicker.py). Zeigt genau,
  wofuer die Pflicht-Verifikation in fill.py da ist -- beide Bugs wurden
  ausschliesslich durch den Soll/Ist-Vergleich entdeckt, nicht durch
  Betrachtung des Screenshots.

---

## Wichtige Erkenntnisse (site-weit)

- **Cookie-Banner** blockiert alle Klicks, bis er weggeklickt wird. Button:
  `get_by_role("button", name="Alle Cookies akzeptieren")`. Erscheint
  zeitlich variabel (0-30s nach Seitenaufbau) -- mit grosszuegigem Timeout
  (z.B. 45s) warten, nicht mit `time.sleep`.
- Datumsfelder sind **keine normalen `<input>`**, sondern
  `role="combobox"`-DIVs mit drei internen Buttons ("Tag ändern", "Monat
  ändern", "Jahr ändern") und Platzhaltertext `TT / MM / JJJJ`. Ausfuellen:
  Element klicken, dann 8 Ziffern durchtippen (`TTMMJJJJ`), mit `Tab`
  abschliessen (NICHT `Escape` -- das verwirft die Eingabe wieder).
- Viele Dropdowns (Baujahr, Bonus/Malus-Stufe, Versicherer, Marke, Modell)
  sind **virtualisierte, durchsuchbare SearchableSelect-Popups**
  (`role="listbox"` / `role="option"`). Nur ein Ausschnitt der Optionen ist
  initial im DOM; fuer den Rest muss getippt (Filterung) oder gescrollt
  werden. Bei kurzen Listen (Baujahr, BM-Stufe: 0-9) sind das alle Werte.
- Radiogruppen mit doppelt vorkommendem Optionstext (mehrere "Ja"/"Nein"
  gleichzeitig auf der Seite) NIE per `get_by_role(..., name="Ja")` klicken
  -- das ist mehrdeutig. Stattdessen ueber
  `page.locator('input[name="<gruppenname>-radiogroup"]').nth(<index>)`
  ansteuern (Reihenfolge = visuelle Reihenfolge, verifiziert).
- Formularvalidierung ist streng und plausibilitaetspruefend: z.B. wird ein
  "Erstzulassung auf Sie"-Datum VOR dem Baujahr/der Erstzulassung des
  Fahrzeugs abgelehnt (roter Rahmen + "Bitte treffen Sie eine Auswahl").

---

## Schritt 1: "Ihr Auto" -> "Fahrzeug wählen"

URL: `/autoversicherung/vergleich/auto/fahrzeugauswahl`

| Feld | Locator | Typ | Pflicht | Werte / Format | Abhängigkeiten |
|---|---|---|---|---|---|
| Baujahr | `#auto.fahrzeug.baujahr-combobox` (SearchableSelect) | Combobox | ja | Jahre absteigend, aktuell erkundet 2020-2026 (mehr durch Scrollen/Tippen) | muss zuerst gesetzt werden, sonst erscheinen keine weiteren Felder |
| Auswahl über | Radiogroup `auto.fahrzeug.etxtype-radiogroup` (kein "name"-Attribut sichtbar, 2 Radios) | Radio | ja | "Marke und Modell" \| "Nationaler Zulassungscode (im Zulassungsschein)" — sichtbar als 2 Buttons | erscheint erst nach Baujahr |
| Zulassungscode | `#auto.fahrzeug.etxauswahl` | Text | ja (im Code-Zweig) | Alphanumerisch, Label "(Feld A7 im Zulassungsschein)". **Löst automatisch das komplette Fahrzeug auf** (Marke, Modell, Motorleistung) — verifiziert: Code `260094` + Baujahr 2020 → "Volkswagen Golf 2,0 TDI Life", 85 kW/115 PS | nur im "Nationaler Zulassungscode"-Zweig |
| Sonderausstattung | Slider (`input[type=range]`, kein stabiles id) + optional `#auto.fahrzeug.sonderausstattungexakt` (Text, € ) über Link "Exakt eingeben" | Range / Text | ja (irgendeine Angabe) | Slider hat Default-Wert (kein Pflichtfeld-Fehler); im "Exakt"-Modus ist der Text-Wert Pflicht — TODO: Skript-seitiges Befüllen von `sonderausstattungexakt` mit "0" hat in einem Testlauf noch einen Validierungsfehler ausgelöst, nicht abschließend verifiziert. Für Automatisierung empfohlen: Slider-Default unverändert lassen. | — |
| **TODO — nicht erkundet:** "Marke und Modell"-Zweig (vermutlich kaskadierende Comboboxen Marke → Modell → Variante) | — | — | — | — |

**Marke/Modell vs. Nationaler Zulassungscode:** Für die Automatisierung ist
der Zulassungscode klar vorzuziehen — ein einzelner, eindeutiger Wert aus
dem Zulassungsschein (Feld A7) statt Fuzzy-Matching von Markennamen. Das
sollte in `mapping.py`/`fall.schema.json` als bevorzugter Pfad hinterlegt
werden, mit Fallback auf Marke/Modell nur wenn der Code im Dokument fehlt.

---

## Schritt 2: "Ihr Auto" -> "Zulassungsdaten"

URL: `/autoversicherung/vergleich/auto/zulassungsdaten`

| Feld | Locator | Typ | Pflicht | Werte / Format | Abhängigkeiten |
|---|---|---|---|---|---|
| Ist das Fahrzeug bereits auf Sie zugelassen? | `input[name="auto.fahrzeug.zugelassen-radiogroup"]` (nth 0 = Ja, nth 1 = Nein) | Radio | ja | Ja / Nein. Hinweistext: "Die Zulassung muss in Österreich erfolgt sein." | erster sichtbarer Schritt |
| Haben Sie das Fahrzeug fabriksneu gekauft? | `input[name="auto.fahrzeug.erstbesitzv-radiogroup"]` (nth 0 = Ja, nth 1 = Nein) | Radio | ja | Ja / Nein | erscheint erst nach "zugelassen" |
| Erstzulassung des PKW | `#auto.fahrzeug.erstzulassung` (segmentiertes Datum, DIV role=combobox) | Datum | ja | TT/MM/JJJJ, war in unserem Testlauf mit Default vorbefüllt (02/01/2020, abgeleitet vom Baujahr) | erscheint bei Erstbesitzer = Ja UND Nein (immer) |
| Erstzulassung auf Sie (Feld-ID: `erstzulassungvnv`) | `#auto.fahrzeug.erstzulassungvnv` (segmentiertes Datum) | Datum | ja, **nur wenn Erstbesitzer = Nein** | TT/MM/JJJJ. **Muss >= "Erstzulassung des PKW" sein**, sonst Validierungsfehler "Bitte treffen Sie eine Auswahl" | erscheint NICHT wenn Erstbesitzer = Ja -- logisch, da fuer einen Erstbesitzer beide Daten identisch sind. Live verifiziert 2026-08-25. |
| Läuft für das Fahrzeug ein Leasingvertrag oder Kredit? | `input[name="auto.fahrzeug.finanzierung-radiogroup"]` (nth 0 = Nein, nth 1 = Leasing, nth 2 = Kredit) | Radio | ja | Nein / Leasing / Kredit | steht gleichzeitig mit den Erstbesitzer-Folgefeldern |
| **TODO — nicht erkundet:** Zweig "zugelassen = Nein" (Neuanmeldung, laut Tooltip "unterscheidet sich der weitere Ablauf"), Leasing/Kredit-Folgefelder | — | — | — | — |

**Update 2026-08-25:** Zweig "Erstbesitzer = Ja" (fabriksneu) jetzt live
erkundet und implementiert (`portals/durchblicker.py`). Ausgeloest durch
einen echten Nutzerfall, der auf den TODO-Block traf. `erstbesitzv-radiogroup`
nth 0 = Ja, nth 1 = Nein (wie zugelassen). End-to-end getestet: alle Felder
verifiziert, `erstzulassungvnv` wird in diesem Zweig korrekt gar nicht erst
angefasst.

---

## Schritt 3: "Ihr Auto" -> "Bonus/Malus-Stufe"

URL: `/autoversicherung/vergleich/auto/bmstufe`

| Feld | Locator | Typ | Pflicht | Werte / Format | Abhängigkeiten |
|---|---|---|---|---|---|
| Ihre aktuelle Bonus-Stufe | `#auto.vn.bmstufe-select` (Button, öffnet SearchableSelect) | Combobox | ja | Verifizierte Optionen: `0, 1, 2, 3, 4, 5, 6, 7, 8, "9 - Einsteigerstufe"` (vollständige Liste, nur 10 Werte, alle im DOM) | Default bereits "9 - Einsteigerstufe" |
| Bestehende Autoversicherung | `#auto.vn.versicherer-combobox` | Combobox (durchsuchbar) | ja | Placeholder "Bitte wählen...". Initial gerenderte Optionen: "Derzeit keine Versicherung", "Allianz / Allianz24", "Call Direct", "Donau", "ERGO", "EUROHERC Versicherung", "Garanta" — **virtualisierte Liste, weitere österreichische Versicherer nur durch Tippen/Scrollen erreichbar, NICHT vollständig erfasst** | — |
| Gibt es im Haushalt bereits ein anderes versichertes Auto? | `input[name="auto.rabatte.zweitwagen-radiogroup"]` (nth 0 = Ja, nth 1 = Nein) | Radio | ja | Ja / Nein. Hinweis: "Das Auto muss auf Sie oder Ihren Partner versichert sein." Default bereits "Nein" | — |

**TODO:** vollständige Versicherer-Liste für `synonyme.json` (Phase 2)
erfassen — Mechanismus (Tippen zum Filtern) ist verifiziert, die
Ergebnisliste selbst noch nicht vollständig gedumpt.

---

## Schritt 4: "Produkt" -> "Leistungsumfang"

URL: `/autoversicherung/vergleich/produkt/leistungsumfang`

| Feld | Locator | Typ | Pflicht | Werte / Format | Abhängigkeiten |
|---|---|---|---|---|---|
| Deckungsumfang | 2 Checkboxen (kein stabiles Attribut außer Position) | Checkbox | — | "Haftpflicht" (per Default aktiv/angehakt, wirkt Pflicht) + "Kasko" (optional zuschaltbar) | **Wichtig:** anders als vom Projektauftrag angenommen ist "Haftpflicht/Teilkasko/Vollkasko" HIER keine 3er-Auswahl, sondern Haftpflicht (Pflicht) + optionale Kasko-Zusatzdeckung |
| Gewünschter Versicherungsschutz | `input[name="auto.produkt.auswahl-radiogroup"]` (nth 0 = durchblicker Empfehlung, nth 1 = Günstiger Preis, nth 2 = Deckungen selbst festlegen) | Radio | ja | 3 Optionen, s. links. Kein Default vorausgewählt — Weiter-Klick ohne Auswahl bleibt auf der Seite | — |
| Kaskovariante | `input[name="auto.produkt.kaskodeckung-radiogroup"]` (nth 0 = Vollkasko, nth 1 = Teilkasko) | Radio | **bedingt** | Erscheint/blockiert nur, wenn die Kasko-Checkbox am Ende AKTIV ist. **Wichtig, live entdeckt am 2026-08-24:** "durchblicker Empfehlung" kann Kasko fuer ein Fahrzeug selbststaendig vorschlagen und die Checkbox VORBELEGEN, unabhaengig davon, was `fall.json` will (beobachtet bei einem 2021er-Fahrzeug mit Sonderausstattung; beim 2020er-Testfall ohne Sonderausstattung geschah das nicht). fill.py MUSS die Checkbox daher aktiv auf den Sollwert setzen (an UND aus), nicht nur ergaenzend anhaken. Die Radiogruppe bleibt auch bei ausgeschaltetem Kasko im DOM (nur nicht mehr blockierend) — pruefbar ist NICHT ihre DOM-Praesenz, sondern der tatsaechliche Checkbox-Zustand. | nur relevant wenn Kasko aktiv |
| **TODO — nicht erkundet:** was "Deckungen selbst festlegen" für Folgefelder öffnet (vermutlich Selbstbehalt, Zusatzbausteine — genau die Felder aus dem ursprünglichen Datenmodell-Entwurf) | — | — | — | — |

---

## Schritt 5: "Person" -> "Versicherungsnehmer"

URL: `/autoversicherung/vergleich/person/versicherungsnehmer`

**Das ist der letzte Schritt vor dem Ergebnis** (Button heißt hier "Zum
Ergebnis" statt "Weiter" — wurde NICHT geklickt).

| Feld | Locator | Typ | Pflicht | Werte / Format | Abhängigkeiten |
|---|---|---|---|---|---|
| Anmeldung als | `input[name="auto.vn.vntyp-radiogroup"]` (nth 0 = Privatperson, nth 1 = Einzelunternehmen) | Radio | ja | Privatperson (Default aktiv) / Einzelunternehmen | — |
| Ist Ihr Einzelunternehmen im Firmenbuch eingetragen? | `input[name="auto.vn.firmenbucheintrag-radiogroup"]` (nth 0 = Ja, nth 1 = Nein) | Radio | ja, **nur wenn Anmeldung als = Einzelunternehmen** | Ja / Nein | erscheint erst nach Auswahl "Einzelunternehmen". Laut Info-Tooltip: nur Fahrzeuge "ohne besondere Verwendung" abwickelbar, sonstige Unternehmensformen (nicht Einzelunternehmen) aktuell gar nicht vergleichbar. Live erkundet und implementiert 2026-08-25. |
| Geburtsdatum | `#auto.vn.geburtsdatum` (segmentiertes Datum, gleiche Mechanik wie Erstzulassung) | Datum | ja | TT/MM/JJJJ | — |
| Nationalität | `#auto.vn.nation-combobox` | Combobox (durchsuchbar) | ja | Default "Österreich". Weitere Optionen nicht gedumpt (TODO) | — |
| Postleitzahl | `#auto.vn.region.plz` (name-Attribut identisch: `auto.vn.region.plz`) | Text | ja | Placeholder "Postleitzahl" — vermutlich 4-stellig AT, Format nicht am Feld selbst erzwungen gesehen (TODO: Grenzfall testen, z.B. 3-stellig) | — |
| E-Mail | `#auto.vn.mail` (name: `auto.vn.mail`) | Email (`type=email`) | ja | Standard-E-Mail-Format | — |
| Telefonnummer | nicht erfasst (live am 2026-08-24 im Screenshot gesehen, Placeholder "0660123456") | Text | **nein** | Feld bleibt leer, blockiert "Zum Ergebnis" nicht — daher (noch) nicht Teil von fall.schema.json/fill.py. TODO: Locator verifizieren, falls spaeter gewuenscht. | — |
| **NICHT vorhanden:** "Führerschein seit" | — | — | — | Im ursprünglichen Datenmodell-Entwurf angenommen, kommt in diesem Wizard-Pfad **nicht vor**. Nicht raten/erfinden — ggf. taucht es im "Einzelunternehmen"-Zweig oder in einem späteren, hier nicht erreichten Schritt auf. | — |

---

## Offene TODOs für Phase 2/3 (vor `fall.schema.json` klären)

1. Vollständige Options-Listen für Versicherer und Nationalität einsammeln
   (Tippen zum Filtern, iterativ dumpen).
2. Zweig "Marke und Modell" statt Zulassungscode erkunden (Fallback für
   Dokumente ohne lesbaren Nationalcode).
3. Zweig "zugelassen = Nein" (Neuanmeldung) erkunden — laut Tooltip
   eigener Ablauf.
4. ~~Zweig "Erstbesitzer = Ja" erkunden.~~ Erledigt 2026-08-25.
5. Leasing/Kredit-Folgefelder erkunden.
6. "Deckungen selbst festlegen" erkunden — hier liegen vermutlich
   Selbstbehalt und weitere Versicherungsparameter aus dem Datenmodell.
7. Verifizieren, ob/wo ein "Führerschein seit"-Feld tatsächlich vorkommt,
   oder ob dieses Feld aus dem Datenmodell gestrichen werden muss.
8. Sonderausstattung-"Exakt eingeben"-Pflichtfeld-Verhalten klären (Testlauf
   mit Wert "0" ergab einen nicht abschließend geklärten Validierungsfehler).
9. Login-Erfolgsfall (nach echtem Login: welche URL/welches Element zeigt
   Erfolg) mit echten Zugangsdaten einmal verifizieren — aktuell nutzt
   `login.py` "URL wechselt weg von der Login-Seite" als Signal, siehe
   Kommentar dort.

Diese TODOs sind bewusst offen gelassen statt geraten — laut Projektregel
"Rate NIEMALS Selektoren, Feldnamen oder Dropdown-Werte."
