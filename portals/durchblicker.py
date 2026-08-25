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

        if fz["identifikationsmethode"]["wert"] != "nationalcode":
            gruende.append(
                "fahrzeug.identifikationsmethode: nur 'nationalcode' ist implementiert "
                "(Zweig 'Marke und Modell' nicht erkundet, siehe feldkarte.md TODO #2)"
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
        if vn["anmeldung_als"]["wert"] != "Privatperson":
            gruende.append("versicherungsnehmer.anmeldung_als: nur 'Privatperson' implementiert")
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

        # --- Schritt 1: Fahrzeug waehlen ---
        _waehle_durchsuchbar(page, "#auto\\.fahrzeug\\.baujahr-combobox", str(fz["baujahr"]["wert"]))
        pruefe("fahrzeug.baujahr", str(fz["baujahr"]["wert"]), page.input_value("#auto\\.fahrzeug\\.baujahr-combobox"))

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
        vntyp_radios = page.locator('input[name="auto.vn.vntyp-radiogroup"]')
        vntyp_radios.nth(0).click(timeout=8000)  # Privatperson
        pruefe("versicherungsnehmer.anmeldung_als", vn["anmeldung_als"]["wert"],
               _lies_enum_radio(vntyp_radios, ["Privatperson", "Einzelunternehmen"]))

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
