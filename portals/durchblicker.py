"""
KFZPortal-Implementierung fuer durchblicker.at. Alle Selektoren und
Interaktionsmuster sind live mit Playwright verifiziert (siehe
feldkarte.md, Stand 2026-08-24). Rate NIEMALS neue Selektoren hier hinein
-- bei Unklarheit erst mit explore.py live pruefen.
"""

from datetime import date

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from portals.base import KfzPortal

LOGIN_URL = "https://durchblicker.at/konto/auth/anmelden"
START_URL = "https://durchblicker.at/autoversicherung/vergleich/auto/fahrzeugauswahl"
COOKIE_ACCEPT_NAME = "Alle Cookies akzeptieren"
LOGIN_ERROR_SELECTOR = ".alert.error-container .error-message"


def dismiss_cookie_banner(page):
    """Cookie-Banner erscheint zeitlich variabel (0-30s) und blockiert
    alle Klicks -- siehe feldkarte.md."""
    try:
        page.get_by_role("button", name=COOKIE_ACCEPT_NAME).click(timeout=45000)
    except PlaywrightTimeoutError:
        pass


def _fuelle_segmentiertes_datum(page, selector, iso_datum):
    """Datumsfelder sind role=combobox-DIVs (kein <input>) mit Platzhalter
    TT/MM/JJJJ. 8 Ziffern durchtippen, mit Tab abschliessen (NICHT Escape
    -- verwirft die Eingabe, siehe feldkarte.md).

    WICHTIG: den expliziten 'Tag aendern'-Button anklicken, NICHT den
    umschliessenden DIV -- bei einem bereits VORBEFUELLTEN Feld (z.B.
    Erstzulassung des PKW, vom Formular aus dem Baujahr vorbelegt) landet
    der Fokus nach einem Klick auf den DIV auf dem zuletzt aktiven Segment
    (beobachtet: 'Monat' statt 'Tag'), wodurch die 8 getippten Ziffern in
    der falschen Reihenfolge auf die Segmente verteilt werden und ein
    kaputtes Datum entsteht. Live verifiziert und gefixt am 2026-08-24
    (siehe Verifikationstabelle in fill.py, die genau das aufgedeckt hat)."""
    d = date.fromisoformat(iso_datum)
    ziffern = f"{d.day:02d}{d.month:02d}{d.year:04d}"
    page.locator(selector).get_by_role("button", name="Tag ändern").click(timeout=8000)
    page.keyboard.type(ziffern)
    page.keyboard.press("Tab")


def _format_betrag(wert):
    """Euro-Betragsfelder erwarten einen reinen Ziffernstring. '500.0'
    (Python-Float-Repraesentation eines ganzzahligen Euro-Betrags) fuehrt
    zu einer kaputten Eingabe im Feld (beobachtet: wird zu '5' verstuemmelt)
    -- live verifiziert und gefixt am 2026-08-24."""
    f = float(wert)
    return str(int(f)) if f.is_integer() else str(f)


def _lies_segmentiertes_datum(page, selector):
    text = page.query_selector(selector).inner_text()
    teile = [t.strip() for t in text.split("/")]
    if len(teile) != 3 or "TT" in teile[0] or not all(t.isdigit() for t in teile):
        return None
    tag, monat, jahr = teile
    try:
        return date(int(jahr), int(monat), int(tag)).isoformat()
    except ValueError:
        return None


def _checked_index(locator):
    for i in range(locator.count()):
        if locator.nth(i).is_checked():
            return i
    return None


def _lies_ja_nein(locator):
    """Fuer boolesche Radiogruppen, bei denen nth(0)=Ja/nth(1)=Nein
    verifiziert ist (zugelassen, erstbesitzer, zweitwagen -- siehe
    feldkarte.md)."""
    idx = _checked_index(locator)
    return {0: True, 1: False}.get(idx)


def _lies_enum_radio(locator, optionen):
    idx = _checked_index(locator)
    return optionen[idx] if idx is not None else None


def _waehle_direkt(page, trigger_selector, text):
    """Fuer Listen, die vollstaendig ohne Tippen im DOM stehen (Bonus/
    Malus-Stufe: nur 10 Werte, alle initial gerendert)."""
    page.click(trigger_selector, timeout=10000)
    page.get_by_role("option", name=text, exact=True).click(timeout=10000)


def _waehle_durchsuchbar(page, trigger_selector, text):
    """Fuer virtualisierte/durchsuchbare Comboboxen (Baujahr, Versicherer):
    Tippen filtert die Liste (live verifiziert), dann exakte Option
    klicken. Playwright normalisiert dabei mehrzeilige Optionstexte
    (z.B. 'Wiener\\nStädtische') automatisch zu einem Leerzeichen beim
    Namensvergleich."""
    page.click(trigger_selector, timeout=10000)
    page.keyboard.type(text)
    page.get_by_role("option", name=text, exact=True).click(timeout=10000)


def _klick_weiter(page):
    page.get_by_role("button", name="Weiter", exact=True).click(timeout=10000)
    page.wait_for_load_state("networkidle")


def _waehle_falls_leer(page, selector, gewuenschter_wert, feldname_lesbar, praefix_ok=False):
    """Fuer die kaskadierenden Comboboxen im 'Marke und Modell'-Zweig
    (Treibstoff/Motorleistung/Bauart/Tueren): manche Felder sind nach den
    vorherigen Auswahlen schon eindeutig automatisch vorbefuellt -- dann
    NICHT anfassen (live beobachtet 2026-08-25, z.B. bei einem E-Auto mit
    nur einer Motorleistung). Ist das Feld leer, muss ausgewaehlt werden;
    ohne passenden fall.json-Wert wird klar abgebrochen statt zu raten.
    praefix_ok=True fuer Felder mit unvorhersehbarem Optionstext-Zusatz
    (z.B. kW-Feld: '85 kW / 115,5 PS')."""
    aktuell = page.input_value(selector)
    if aktuell:
        return aktuell
    if gewuenschter_wert is None:
        raise RuntimeError(
            f"Das Formular verlangt eine Auswahl fuer '{feldname_lesbar}', aber fall.json "
            f"enthaelt keinen Wert dafuer. Bitte ergaenzen (siehe feldkarte.md)."
        )
    gewuenschter_text = str(gewuenschter_wert).replace(".", ",")
    page.click(selector, timeout=10000)
    page.keyboard.type(gewuenschter_text)
    page.wait_for_timeout(500)
    listbox = None
    for lb in page.query_selector_all("[role=listbox]"):
        if lb.is_visible():
            listbox = lb
            break
    treffer = None
    if listbox:
        for opt in listbox.query_selector_all("[role=option]"):
            text = (opt.inner_text() or "").strip()
            norm = text.replace(".", ",")
            if norm == gewuenschter_text or (praefix_ok and norm.startswith(gewuenschter_text)):
                treffer = opt
                break
    if treffer is None:
        page.keyboard.press("Escape")
        raise RuntimeError(
            f"Kein Treffer fuer '{feldname_lesbar}' = '{gewuenschter_wert}' unter den "
            f"verfuegbaren Optionen gefunden."
        )
    treffer.click(timeout=8000)
    page.wait_for_timeout(500)
    return page.input_value(selector)


def _ergebnisliste_zeilen(page):
    """Liefert (radio, Zeilentext) fuer jede sichtbare Zeile der Fahrzeug-
    Ergebnisliste im 'Marke und Modell'-Zweig -- diese Radios haben (anders
    als alle benannten Radiogruppen im Formular) kein name-Attribut."""
    ergebnis = []
    for r in page.query_selector_all("input[type=radio]"):
        try:
            if not r.is_visible() or r.get_attribute("name"):
                continue
        except Exception:
            continue
        text = r.evaluate(
            "e => { let n = e.closest('div'); let i = 0; "
            "while (n && n.innerText.trim().length < 5 && i < 6) { n = n.parentElement; i++; } "
            "return n ? n.innerText.trim() : ''; }"
        )
        ergebnis.append((r, text))
    return ergebnis


def _waehle_aus_ergebnisliste(page, variante_wert):
    """Nach Marke/Modell/Treibstoff/kW/Bauart/Tueren zeigt das Formular
    eine Liste passender Fahrzeugtypen (z.B. 'Golf 1,6 TDI Comfortline').
    Bleibt genau eine Zeile uebrig, wird sie direkt gewaehlt. Bei mehreren
    Zeilen muss 'variante' zu GENAU EINER passen (Teilstring-Abgleich,
    Dezimaltrennzeichen , und . gleich behandelt) -- sonst klarer Abbruch
    statt Raten. Live verifiziert 2026-08-25."""
    zeilen = _ergebnisliste_zeilen(page)
    if not zeilen:
        raise RuntimeError(
            "Keine Fahrzeug-Ergebniszeilen gefunden -- die Kombination aus Marke/Modell/"
            "Treibstoff/Motorleistung/Bauart/Tueren ergab keinen Treffer."
        )
    if len(zeilen) == 1:
        zeilen[0][0].click(timeout=8000)
        return zeilen[0][1]
    if not variante_wert:
        namen = [t.splitlines()[0] for _, t in zeilen]
        raise RuntimeError(
            f"{len(zeilen)} passende Fahrzeuge gefunden, aber fall.json enthaelt keine "
            f"'variante' zur eindeutigen Auswahl. Gefundene Typen: {namen}"
        )
    norm_ziel = variante_wert.strip().lower().replace(".", ",")
    treffer = [(r, t) for r, t in zeilen if norm_ziel in t.strip().lower().replace(".", ",")]
    if len(treffer) != 1:
        namen = [t.splitlines()[0] for _, t in zeilen]
        raise RuntimeError(
            f"variante='{variante_wert}' passt nicht eindeutig zu genau einem der "
            f"{len(zeilen)} gefundenen Fahrzeuge: {namen}"
        )
    treffer[0][0].click(timeout=8000)
    return treffer[0][1]


class DurchblickerPortal(KfzPortal):
    def login(self, page, email, password):
        page.goto(LOGIN_URL, wait_until="networkidle")
        dismiss_cookie_banner(page)
        page.fill("#login-email", email)
        page.fill("#login-password", password)
        page.click("#login-container-form-cta")
        try:
            page.wait_for_url(lambda url: url != LOGIN_URL, timeout=20000)
        except PlaywrightTimeoutError:
            error_el = page.query_selector(LOGIN_ERROR_SELECTOR)
            if error_el:
                raise RuntimeError(f"Login fehlgeschlagen: {error_el.inner_text().strip()}")
            raise RuntimeError(
                "Login-Ergebnis nach 20s nicht eindeutig (keine Navigation, keine erkannte Fehlermeldung)."
            )

    def navigate(self, page):
        page.goto(START_URL, wait_until="networkidle")
        dismiss_cookie_banner(page)

    def unterstuetzter_pfad(self, fall):
        gruende = []
        fz, vn, pr = fall["fahrzeug"], fall["versicherungsnehmer"], fall["produkt"]

        if fz["identifikationsmethode"]["wert"] not in ("nationalcode", "marke_modell"):
            gruende.append(
                "fahrzeug.identifikationsmethode: kein gueltiger Wert -- weder Nationalcode "
                "noch Marke+Modell konnten aus dem Dokument bestimmt werden."
            )
        if fz["zugelassen"]["wert"] is not True:
            gruende.append(
                "fahrzeug.zugelassen: nur True/Ja implementiert (Neuanmeldung-Zweig nicht "
                "erkundet, siehe feldkarte.md TODO #3)"
            )
        if fz["finanzierung"]["wert"] != "Nein":
            gruende.append(
                "fahrzeug.finanzierung: nur 'Nein' implementiert (Leasing/Kredit-Folgefelder "
                "nicht erkundet, siehe feldkarte.md TODO #5)"
            )
        if vn["nationalitaet"]["wert"] != "Österreich":
            gruende.append(
                "versicherungsnehmer.nationalitaet: nur der Formular-Default 'Österreich' "
                "implementiert (vollstaendige Optionsliste nicht erfasst, siehe TODO #1)"
            )
        if pr["versicherungsschutz_praeferenz"]["wert"] != "durchblicker Empfehlung":
            gruende.append(
                "produkt.versicherungsschutz_praeferenz: nur 'durchblicker Empfehlung' "
                "implementiert ('Deckungen selbst festlegen' oeffnet vermutlich weitere "
                "Felder, siehe TODO #6)"
            )

        return gruende

    def fill(self, page, fall):
        """Fuellt jeden Schritt aus und verifiziert ihn SOFORT (Auslesen aus
        dem DOM), BEVOR zum naechsten Schritt geblattert wird -- die Felder
        eines Schritts existieren nach 'Weiter' nicht mehr im DOM (SPA), ein
        nachtraegliches Zurueck-Auslesen am Ende ist daher nicht moeglich.
        Die gesammelten Verifikationszeilen liegen danach in self._zeilen;
        verify() liefert genau diese Liste."""
        fz, vn, pr = fall["fahrzeug"], fall["versicherungsnehmer"], fall["produkt"]
        zeilen = []

        def pruefe(pfad, soll, ist):
            zeilen.append({"pfad": pfad, "soll": soll, "ist": ist, "ok": soll == ist})

        def pruefe_kaskade(pfad, soll, ist, praefix_ok=False):
            """Wie pruefe(), aber fuer die 'Marke und Modell'-Kaskade: war
            in fall.json kein Wert vorgegeben (Feld hat sich selbst
            eindeutig aufgeloest), gibt es keinen echten Soll/Ist-Vergleich
            -- dann wird der tatsaechliche Wert transparent als
            '(automatisch)' vermerkt statt einen Fehlalarm auszuloesen."""
            if soll is None:
                zeilen.append({"pfad": pfad, "soll": f"(automatisch) {ist}", "ist": ist, "ok": True})
                return
            soll_norm = str(soll).strip().replace(".", ",")
            ist_norm = (ist or "").strip().replace(".", ",")
            ok = ist_norm.startswith(soll_norm) if praefix_ok else ist_norm == soll_norm
            zeilen.append({"pfad": pfad, "soll": soll, "ist": ist, "ok": ok})

        # --- Schritt 1: Fahrzeug waehlen ---
        _waehle_durchsuchbar(page, "#auto\\.fahrzeug\\.baujahr-combobox", str(fz["baujahr"]["wert"]))
        pruefe("fahrzeug.baujahr", str(fz["baujahr"]["wert"]), page.input_value("#auto\\.fahrzeug\\.baujahr-combobox"))

        if fz["identifikationsmethode"]["wert"] == "nationalcode":
            page.get_by_text("Nationaler Zulassungscode", exact=False).click(timeout=10000)
            page.fill("#auto\\.fahrzeug\\.etxauswahl", fz["nationalcode"]["wert"])
            page.get_by_text("Gewähltes Fahrzeug:", exact=False).wait_for(timeout=15000)
            pruefe("fahrzeug.nationalcode (Fahrzeug erkannt)", True,
                   page.get_by_text("Gewähltes Fahrzeug:", exact=False).count() > 0)

            sonderausstattung = fz.get("sonderausstattung_wert", {}).get("wert")
            if sonderausstattung is not None:
                page.get_by_text("Exakt eingeben", exact=True).click(timeout=5000)
                page.fill("#auto\\.fahrzeug\\.sonderausstattungexakt", _format_betrag(sonderausstattung))
                page.keyboard.press("Tab")
                ist_text = page.input_value("#auto\\.fahrzeug\\.sonderausstattungexakt")
                try:
                    ist_wert = float(ist_text)
                except ValueError:
                    ist_wert = None
                pruefe("fahrzeug.sonderausstattung_wert", float(sonderausstattung), ist_wert)
        else:
            # 'Marke und Modell' -- Fallback ohne lesbaren Nationalcode.
            # Kaskadierende Comboboxen, live erkundet und implementiert
            # 2026-08-25: Marke -> Modell -> Treibstoff -> Motorleistung ->
            # Bauart -> Anzahl Tueren -> Ergebnisliste mit ggf. mehreren
            # passenden Fahrzeugtypen.
            page.get_by_text("Marke und Modell", exact=False).click(timeout=10000)

            _waehle_durchsuchbar(page, "#auto\\.fahrzeug\\.marke-combobox", fz["marke"]["wert"])
            pruefe("fahrzeug.marke", fz["marke"]["wert"], page.input_value("#auto\\.fahrzeug\\.marke-combobox"))

            _waehle_durchsuchbar(page, "#auto\\.fahrzeug\\.modell-combobox", fz["modell"]["wert"])
            pruefe("fahrzeug.modell", fz["modell"]["wert"], page.input_value("#auto\\.fahrzeug\\.modell-combobox"))

            treibstoff_soll = fz.get("treibstoff", {}).get("wert")
            treibstoff_ist = _waehle_falls_leer(
                page, "#auto\\.fahrzeug\\.treibstoff-combobox", treibstoff_soll, "Treibstoff"
            )
            pruefe_kaskade("fahrzeug.treibstoff", treibstoff_soll, treibstoff_ist)

            kw_soll = fz.get("motorleistung_kw", {}).get("wert")
            kw_ist = _waehle_falls_leer(
                page, "#auto\\.fahrzeug\\.kw-combobox", kw_soll, "Motorleistung (kW)", praefix_ok=True
            )
            pruefe_kaskade("fahrzeug.motorleistung_kw", kw_soll, kw_ist, praefix_ok=True)

            bauart_soll = fz.get("bauart", {}).get("wert")
            bauart_ist = _waehle_falls_leer(page, "#auto\\.fahrzeug\\.bauart-combobox", bauart_soll, "Bauart")
            pruefe_kaskade("fahrzeug.bauart", bauart_soll, bauart_ist)

            tueren_sel = "#auto\\.fahrzeug\\.tueren-combobox"
            if page.query_selector(tueren_sel):
                tueren_soll = fz.get("tueren", {}).get("wert")
                tueren_ist = _waehle_falls_leer(page, tueren_sel, tueren_soll, "Anzahl Türen")
                pruefe_kaskade("fahrzeug.tueren", tueren_soll, tueren_ist)

            variante_soll = fz.get("variante", {}).get("wert")
            zeile_text = _waehle_aus_ergebnisliste(page, variante_soll)
            erste_zeile = zeile_text.splitlines()[0] if zeile_text else "?"
            zeilen.append({
                "pfad": "fahrzeug.variante (Fahrzeug ausgewählt)",
                "soll": variante_soll or f"(automatisch) {erste_zeile}",
                "ist": erste_zeile,
                "ok": True,
            })

        _klick_weiter(page)

        # --- Schritt 2: Zulassungsdaten ---
        zugelassen_radios = page.locator('input[name="auto.fahrzeug.zugelassen-radiogroup"]')
        zugelassen_radios.nth(0).click(timeout=8000)  # Ja
        pruefe("fahrzeug.zugelassen", fz["zugelassen"]["wert"], _lies_ja_nein(zugelassen_radios))

        erstbesitzer_wert = fz["erstbesitzer"]["wert"]
        erstbesitzer_radios = page.locator('input[name="auto.fahrzeug.erstbesitzv-radiogroup"]')
        erstbesitzer_radios.nth(0 if erstbesitzer_wert else 1).click(timeout=8000)
        pruefe("fahrzeug.erstbesitzer", erstbesitzer_wert, _lies_ja_nein(erstbesitzer_radios))

        # Bei Erstbesitzer=Ja (fabriksneu) zeigt das Formular NUR
        # 'Erstzulassung des PKW' -- das zweite Feld 'Erstzulassung auf
        # Sie' existiert in diesem Zweig gar nicht im DOM, weil beide
        # Daten fuer einen Erstbesitzer per Definition identisch sind.
        # Live verifiziert 2026-08-25.
        page.wait_for_selector("#auto\\.fahrzeug\\.erstzulassung", timeout=10000)
        _fuelle_segmentiertes_datum(page, "#auto\\.fahrzeug\\.erstzulassung", fz["erstzulassung_pkw"]["wert"])
        pruefe("fahrzeug.erstzulassung_pkw", fz["erstzulassung_pkw"]["wert"],
               _lies_segmentiertes_datum(page, "#auto\\.fahrzeug\\.erstzulassung"))

        if not erstbesitzer_wert:
            _fuelle_segmentiertes_datum(page, "#auto\\.fahrzeug\\.erstzulassungvnv", fz["erstzulassung_auf_sie"]["wert"])
            pruefe("fahrzeug.erstzulassung_auf_sie", fz["erstzulassung_auf_sie"]["wert"],
                   _lies_segmentiertes_datum(page, "#auto\\.fahrzeug\\.erstzulassungvnv"))

        finanzierung_radios = page.locator('input[name="auto.fahrzeug.finanzierung-radiogroup"]')
        finanzierung_radios.nth(0).click(timeout=8000)  # Nein
        pruefe("fahrzeug.finanzierung", fz["finanzierung"]["wert"],
               _lies_enum_radio(finanzierung_radios, ["Nein", "Leasing", "Kredit"]))

        _klick_weiter(page)

        # --- Schritt 3: Bonus/Malus-Stufe ---
        _waehle_direkt(page, "#auto\\.vn\\.bmstufe-select", vn["bonus_malus_stufe"]["wert"])
        pruefe("versicherungsnehmer.bonus_malus_stufe", vn["bonus_malus_stufe"]["wert"],
               page.inner_text("#auto\\.vn\\.bmstufe-select").strip())

        _waehle_durchsuchbar(page, "#auto\\.vn\\.versicherer-combobox", vn["bestehende_versicherung"]["wert"])
        pruefe("versicherungsnehmer.bestehende_versicherung", vn["bestehende_versicherung"]["wert"],
               page.input_value("#auto\\.vn\\.versicherer-combobox"))

        zweitwagen_index = 0 if vn["zweitwagen"]["wert"] else 1
        zweitwagen_radios = page.locator('input[name="auto.rabatte.zweitwagen-radiogroup"]')
        zweitwagen_radios.nth(zweitwagen_index).click(timeout=8000)
        pruefe("versicherungsnehmer.zweitwagen", vn["zweitwagen"]["wert"], _lies_ja_nein(zweitwagen_radios))

        _klick_weiter(page)

        # --- Schritt 4: Produkt / Leistungsumfang ---
        produkt_radios = page.locator('input[name="auto.produkt.auswahl-radiogroup"]')
        produkt_radios.nth(0).click(timeout=8000)  # durchblicker Empfehlung
        pruefe(
            "produkt.versicherungsschutz_praeferenz",
            pr["versicherungsschutz_praeferenz"]["wert"],
            _lies_enum_radio(produkt_radios, ["durchblicker Empfehlung", "Günstiger Preis", "Deckungen selbst festlegen"]),
        )

        # "durchblicker Empfehlung" kann Kasko selbststaendig vorschlagen und
        # die Checkbox unabhaengig von fall.json vorbelegen (live entdeckt
        # 2026-08-24) -- daher aktiv auf den Sollwert setzen, in BEIDE
        # Richtungen, nicht nur ergaenzend anhaken.
        kasko_gewuenscht = pr.get("kasko_zusatzdeckung", {}).get("wert") is True
        kasko = page.get_by_role("checkbox", name="Kasko", exact=True)
        if kasko.is_checked() != kasko_gewuenscht:
            kasko.click(timeout=8000)
        pruefe("produkt.kasko_zusatzdeckung", kasko_gewuenscht, kasko.is_checked())

        # Wenn Kasko am Ende aktiv ist, verlangt das Formular zusaetzlich
        # eine Kaskovariante (Vollkasko/Teilkasko) -- dieses Feld erscheint
        # nur reaktiv, abhaengig von der Empfehlung fuer DIESES Fahrzeug,
        # und kann daher nicht vorab in unterstuetzter_pfad() geprueft
        # werden. Live entdeckt 2026-08-24. WICHTIG: die Radiogruppe bleibt
        # auch bei ausgeschaltetem Kasko im DOM (nur nicht mehr blockierend
        # fuer 'Weiter') -- pruefbar ist daher NICHT ihre DOM-Praesenz,
        # sondern der tatsaechliche Kasko-Checkbox-Zustand.
        kaskodeckung_radios = page.locator('input[name="auto.produkt.kaskodeckung-radiogroup"]')
        if kasko.is_checked():
            kaskovariante = pr.get("kaskovariante", {}).get("wert")
            if kaskovariante not in ("Vollkasko", "Teilkasko"):
                raise RuntimeError(
                    "Das Formular verlangt fuer dieses Fahrzeug eine Kaskovariante "
                    "(Vollkasko/Teilkasko), aber fall.json enthaelt keinen gueltigen "
                    "Wert fuer produkt.kaskovariante. Bitte ergaenzen (siehe feldkarte.md)."
                )
            idx = {"Vollkasko": 0, "Teilkasko": 1}[kaskovariante]
            kaskodeckung_radios.nth(idx).click(timeout=8000)
            pruefe("produkt.kaskovariante", kaskovariante,
                   _lies_enum_radio(kaskodeckung_radios, ["Vollkasko", "Teilkasko"]))

        _klick_weiter(page)

        # --- Schritt 5: Person / Versicherungsnehmer ---
        anmeldung_als = vn["anmeldung_als"]["wert"]
        vntyp_radios = page.locator('input[name="auto.vn.vntyp-radiogroup"]')
        vntyp_radios.nth(0 if anmeldung_als == "Privatperson" else 1).click(timeout=8000)
        pruefe("versicherungsnehmer.anmeldung_als", anmeldung_als,
               _lies_enum_radio(vntyp_radios, ["Privatperson", "Einzelunternehmen"]))

        # 'Ist Ihr Einzelunternehmen im Firmenbuch eingetragen?' erscheint
        # nur nach Auswahl von 'Einzelunternehmen' -- live entdeckt
        # 2026-08-25.
        if anmeldung_als == "Einzelunternehmen":
            firmenbucheintrag = vn.get("firmenbucheintrag", {}).get("wert")
            if firmenbucheintrag not in (True, False):
                raise RuntimeError(
                    "Das Formular verlangt fuer 'Einzelunternehmen' eine Angabe, ob das "
                    "Unternehmen im Firmenbuch eingetragen ist, aber fall.json enthaelt "
                    "keinen gueltigen Wert fuer versicherungsnehmer.firmenbucheintrag. "
                    "Bitte ergaenzen (siehe feldkarte.md)."
                )
            firmenbuch_radios = page.locator('input[name="auto.vn.firmenbucheintrag-radiogroup"]')
            firmenbuch_radios.nth(0 if firmenbucheintrag else 1).click(timeout=8000)
            pruefe("versicherungsnehmer.firmenbucheintrag", firmenbucheintrag,
                   _lies_ja_nein(firmenbuch_radios))

        _fuelle_segmentiertes_datum(page, "#auto\\.vn\\.geburtsdatum", vn["geburtsdatum"]["wert"])
        pruefe("versicherungsnehmer.geburtsdatum", vn["geburtsdatum"]["wert"],
               _lies_segmentiertes_datum(page, "#auto\\.vn\\.geburtsdatum"))

        page.fill("#auto\\.vn\\.region\\.plz", vn["plz"]["wert"])
        pruefe("versicherungsnehmer.plz", vn["plz"]["wert"], page.input_value("#auto\\.vn\\.region\\.plz"))

        page.fill("#auto\\.vn\\.mail", vn["email"]["wert"])
        pruefe("versicherungsnehmer.email", vn["email"]["wert"], page.input_value("#auto\\.vn\\.mail"))

        # ABSICHTLICH KEIN Klick auf "Zum Ergebnis" -- siehe Projektauftrag.

        self._zeilen = zeilen

    def verify(self, page, fall):
        """Liefert die Verifikationszeilen, die fill() bereits pro Schritt
        gesammelt hat (siehe Docstring dort)."""
        return getattr(self, "_zeilen", [])
