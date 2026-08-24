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
zugelassen (Neuwagen-Anmeldung), "Marke und Modell" statt Zulassungscode,
Erstbesitzer=Ja, Leasing/Kredit-Finanzierung, "Günstiger Preis"/"Deckungen
selbst festlegen" statt Empfehlung, Kasko-Zusatzdeckung, Einzelunternehmen.

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
| Erstzulassung des PKW | `#auto.fahrzeug.erstzulassung` (segmentiertes Datum, DIV role=combobox) | Datum | ja | TT/MM/JJJJ, war in unserem Testlauf mit Default vorbefüllt (02/01/2020, abgeleitet vom Baujahr) | erscheint nach "Erstbesitzer" = Nein |
| Erstzulassung auf Sie (Feld-ID: `erstzulassungvnv`) | `#auto.fahrzeug.erstzulassungvnv` (segmentiertes Datum) | Datum | ja | TT/MM/JJJJ. **Muss >= "Erstzulassung des PKW" sein**, sonst Validierungsfehler "Bitte treffen Sie eine Auswahl" | erscheint nur wenn Erstbesitzer = Nein |
| Läuft für das Fahrzeug ein Leasingvertrag oder Kredit? | `input[name="auto.fahrzeug.finanzierung-radiogroup"]` (nth 0 = Nein, nth 1 = Leasing, nth 2 = Kredit) | Radio | ja | Nein / Leasing / Kredit | steht gleichzeitig mit den Erstbesitzer-Folgefeldern |
| **TODO — nicht erkundet:** Zweig "Erstbesitzer = Ja" (vermutlich andere/weniger Folgefelder), Zweig "zugelassen = Nein" (Neuanmeldung, laut Tooltip "unterscheidet sich der weitere Ablauf"), Leasing/Kredit-Folgefelder | — | — | — | — |

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
| **TODO — nicht erkundet:** was "Deckungen selbst festlegen" für Folgefelder öffnet (vermutlich Selbstbehalt, Zusatzbausteine — genau die Felder aus dem ursprünglichen Datenmodell-Entwurf) | — | — | — | — |

---

## Schritt 5: "Person" -> "Versicherungsnehmer"

URL: `/autoversicherung/vergleich/person/versicherungsnehmer`

**Das ist der letzte Schritt vor dem Ergebnis** (Button heißt hier "Zum
Ergebnis" statt "Weiter" — wurde NICHT geklickt).

| Feld | Locator | Typ | Pflicht | Werte / Format | Abhängigkeiten |
|---|---|---|---|---|---|
| Anmeldung als | `input[name="auto.vn.vntyp-radiogroup"]` (nth 0 = Privatperson, nth 1 = Einzelunternehmen) | Radio | ja | Privatperson (Default aktiv) / Einzelunternehmen | — |
| Geburtsdatum | `#auto.vn.geburtsdatum` (segmentiertes Datum, gleiche Mechanik wie Erstzulassung) | Datum | ja | TT/MM/JJJJ | — |
| Nationalität | `#auto.vn.nation-combobox` | Combobox (durchsuchbar) | ja | Default "Österreich". Weitere Optionen nicht gedumpt (TODO) | — |
| Postleitzahl | `#auto.vn.region.plz` (name-Attribut identisch: `auto.vn.region.plz`) | Text | ja | Placeholder "Postleitzahl" — vermutlich 4-stellig AT, Format nicht am Feld selbst erzwungen gesehen (TODO: Grenzfall testen, z.B. 3-stellig) | — |
| E-Mail | `#auto.vn.mail` (name: `auto.vn.mail`) | Email (`type=email`) | ja | Standard-E-Mail-Format | — |
| **NICHT vorhanden:** "Führerschein seit" | — | — | — | Im ursprünglichen Datenmodell-Entwurf angenommen, kommt in diesem Wizard-Pfad **nicht vor**. Nicht raten/erfinden — ggf. taucht es im "Einzelunternehmen"-Zweig oder in einem späteren, hier nicht erreichten Schritt auf. | — |

---

## Offene TODOs für Phase 2/3 (vor `fall.schema.json` klären)

1. Vollständige Options-Listen für Versicherer und Nationalität einsammeln
   (Tippen zum Filtern, iterativ dumpen).
2. Zweig "Marke und Modell" statt Zulassungscode erkunden (Fallback für
   Dokumente ohne lesbaren Nationalcode).
3. Zweig "zugelassen = Nein" (Neuanmeldung) erkunden — laut Tooltip
   eigener Ablauf.
4. Zweig "Erstbesitzer = Ja" erkunden.
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
