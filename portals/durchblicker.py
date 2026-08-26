"""
KFZPortal-Implementierung fuer durchblicker.at. Alle Selektoren und
Interaktionsmuster sind live mit Playwright verifiziert (siehe
feldkarte.md, Stand 2026-08-24). Rate NIEMALS neue Selektoren hier hinein
-- bei Unklarheit erst mit explore.py live pruefen.
"""

from datetime import date

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from portals.base import FeldKlaerungNoetig, KfzPortal

LOGIN_URL = "https://durchblicker.at/konto/auth/anmelden"
START_URL = "https://durchblicker.at/autoversicherung/vergleich/auto/fahrzeugauswahl"
COOKIE_ACCEPT_NAME = "Alle Cookies akzeptieren"
LOGIN_ERROR_SELECTOR = ".alert.error-container .error-message"

# Felder, die NICHT vorab bestaetigt sein muessen, bevor fill() startet --
# sind sie unklar (sicher:false), pausiert fill() an genau dieser Stelle
# und laesst den Menschen DIREKT im Browser eintragen/klicken (siehe
# FeldKlaerungNoetig, _boolean_oder_pausiere & co.). Bewusst NICHT in
# dieser Liste: Felder, die eine Wizard-VERZWEIGUNG steuern, deren
# Alternativ-Zweig nicht (vollstaendig) live erkundet ist (zugelassen,
# finanzierung, identifikationsmethode/nationalcode/marke+modell) -- dort
# wuerde ein Live-Klick in unbekanntes Terrain fuehren, das fill() nicht
# weiter ausfuellen kann. Ebenso nicht enthalten: Felder mit einem
# bereits automatischen Formular-Standard (bonus_malus_stufe,
# nationalitaet, versicherungsschutz_praeferenz, sonderausstattung_wert),
# die praktisch nie unklar sind (siehe mapping.py).
LIVE_KLAERBARE_FELDER = {
    "fahrzeug.erstbesitzer",
    "fahrzeug.erstzulassung_pkw",
    "fahrzeug.erstzulassung_auf_sie",
    "fahrzeug.treibstoff",
    "fahrzeug.motorleistung_kw",
    "fahrzeug.bauart",
    "fahrzeug.tueren",
    "fahrzeug.variante",
    "versicherungsnehmer.bestehende_versicherung",
    "versicherungsnehmer.zweitwagen",
    "versicherungsnehmer.anmeldung_als",
    "versicherungsnehmer.firmenbucheintrag",
    "versicherungsnehmer.geburtsdatum",
    "versicherungsnehmer.plz",
    "versicherungsnehmer.email",
    "produkt.kasko_zusatzdeckung",
    "produkt.kaskovariante",
    # NICHT enthalten: fahrzeug.marke/modell -- koennen strukturell nicht
    # unklar sein, wenn identifikationsmethode bereits 'marke_modell'
    # ergeben hat (bestimme_identifikationsmethode in mapping.py setzt das
    # nur, wenn BEIDE bereits sicher vorliegen). Waeren sie es dennoch,
    # deutet das auf einen tieferen Fehler hin und soll weiterhin vorab
    # blockieren statt live an einer nicht abgesicherten Stelle zu
    # pausieren.
}


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


def _waehle_durchsuchbar(page, trigger_selector, text, feldpfad=None):
    """Fuer virtualisierte/durchsuchbare Comboboxen (Baujahr, Versicherer,
    Marke, Modell): Tippen filtert die Liste (live verifiziert), dann
    exakte Option klicken. Playwright normalisiert dabei mehrzeilige
    Optionstexte (z.B. 'Wiener\\nStädtische') automatisch zu einem
    Leerzeichen beim Namensvergleich.

    Faellt der case-sensitive exakte Treffer aus (z.B. Dokument liefert
    'PEUGEOT' in Grossbuchstaben, Formular zeigt 'Peugeot' -- live
    beobachtet 2026-08-25), wird NICHT geraten, sondern unter den nach
    dem Tippen tatsaechlich angezeigten Optionen nach einem einzigen
    case-insensitiven Text-Treffer gesucht. Gibt es keinen oder mehr als
    einen solchen Treffer, wird klar abgebrochen statt eine falsche
    Option zu waehlen -- als FeldKlaerungNoetig(feldpfad), wenn ein
    fall.json-Feldpfad uebergeben wurde, damit die Web-Oberflaeche das
    Feld gezielt zur erneuten Klaerung zurueckgeben kann."""
    page.click(trigger_selector, timeout=10000)
    page.keyboard.type(text)
    exakt = page.get_by_role("option", name=text, exact=True)
    try:
        exakt.click(timeout=6000)
        return
    except PlaywrightTimeoutError:
        pass

    optionen = page.get_by_role("option").all()
    text_norm = " ".join(text.split()).casefold()
    treffer = [o for o in optionen if " ".join(o.inner_text().split()).casefold() == text_norm]
    if len(treffer) == 1:
        treffer[0].click(timeout=10000)
        return
    if len(treffer) == 0:
        gefunden = [o.inner_text() for o in optionen]
        meldung = (
            f"Keine passende Option fuer '{text}' gefunden (auch nicht "
            f"gross-/kleinschreibungs-unabhaengig). Angezeigte Optionen: {gefunden}"
        )
        if feldpfad:
            raise FeldKlaerungNoetig(meldung, feldpfad, gefunden)
        raise RuntimeError(meldung)
    gefunden = [o.inner_text() for o in treffer]
    meldung = (
        f"Mehrdeutig: '{text}' passt gross-/kleinschreibungs-unabhaengig auf "
        f"mehrere Optionen: {gefunden}"
    )
    if feldpfad:
        raise FeldKlaerungNoetig(meldung, feldpfad, gefunden)
    raise RuntimeError(meldung)


def _versuche_oder_pausiere(aktion):
    """Generator-Helfer fuer fill(): fuehrt aktion() aus. Wirft aktion()
    eine FeldKlaerungNoetig, wird NICHT abgebrochen, sondern pausiert
    (die Exception wird 'ge-yielded') -- der Aufrufer (fill.py) haelt in
    diesem Moment die Playwright-Sitzung an und laesst den Menschen die
    betroffene Auswahl DIREKT im bereits geoeffneten Browserfenster
    treffen. Kehrt fill() (via next()/send()) danach zurueck, wird
    aktion() NICHT erneut versucht -- der Mensch hat sie bereits erledigt.
    Liefert True, wenn pausiert wurde (manuelle Aktion), sonst False."""
    try:
        aktion()
    except FeldKlaerungNoetig as e:
        yield e
        return True
    return False


def _boolean_oder_pausiere(feldpfad, feldname_lesbar, wert, radios):
    """Generator-Helfer fuer ein Ja/Nein-Radiopaar (nth(0)=Ja, nth(1)=Nein):
    ist wert bekannt, wird direkt geklickt. Ist wert None (nicht aus
    dem/den Dokument(en) lesbar -- z.B. Zweitwagen, Erstbesitzer), wird
    pausiert und der Mensch waehlt DIREKT im Browser. Liefert in beiden
    Faellen (ist_wert, manuell)."""
    if wert is not None:
        radios.nth(0 if wert else 1).click(timeout=8000)
        return _lies_ja_nein(radios), False
    yield FeldKlaerungNoetig(
        f"'{feldname_lesbar}' konnte nicht aus dem/den Dokument(en) gelesen werden. "
        "Bitte direkt im Browser auswählen.",
        feldpfad, ["Ja", "Nein"],
    )
    return _lies_ja_nein(radios), True


def _enum_oder_pausiere(feldpfad, feldname_lesbar, wert, radios, optionen):
    """Wie _boolean_oder_pausiere, aber fuer eine Radiogruppe mit mehr als
    zwei benannten Optionen (z.B. Anmeldung als, Kaskovariante)."""
    if wert is not None:
        radios.nth(optionen.index(wert)).click(timeout=8000)
        return _lies_enum_radio(radios, optionen), False
    yield FeldKlaerungNoetig(
        f"'{feldname_lesbar}' konnte nicht aus dem/den Dokument(en) gelesen werden. "
        "Bitte direkt im Browser auswählen.",
        feldpfad, optionen,
    )
    return _lies_enum_radio(radios, optionen), True


def _datum_oder_pausiere(page, selector, feldpfad, feldname_lesbar, iso_datum):
    """Wie _boolean_oder_pausiere, aber fuer ein segmentiertes Datumsfeld
    (z.B. Geburtsdatum, Erstzulassung) -- reine Kundenauskuenfte wie das
    Geburtsdatum stehen auf keinem Fahrzeugdokument."""
    if iso_datum is not None:
        _fuelle_segmentiertes_datum(page, selector, iso_datum)
        return _lies_segmentiertes_datum(page, selector), False
    yield FeldKlaerungNoetig(
        f"'{feldname_lesbar}' konnte nicht aus dem/den Dokument(en) gelesen werden. "
        "Bitte Datum direkt im Browser eintragen.",
        feldpfad, [],
    )
    return _lies_segmentiertes_datum(page, selector), True


def _text_oder_pausiere(page, selector, feldpfad, feldname_lesbar, wert):
    """Wie _boolean_oder_pausiere, aber fuer ein einfaches Textfeld (PLZ,
    E-Mail) -- reine Kundenauskuenfte, die auf keinem Fahrzeugdokument
    stehen."""
    if wert is not None:
        page.fill(selector, wert)
        return page.input_value(selector), False
    yield FeldKlaerungNoetig(
        f"'{feldname_lesbar}' konnte nicht aus dem/den Dokument(en) gelesen werden. "
        "Bitte direkt im Browser eintragen.",
        feldpfad, [],
    )
    return page.input_value(selector), True


def _durchsuchbar_oder_pausiere(page, selector, feldpfad, feldname_lesbar, wert):
    """Wie _boolean_oder_pausiere, aber fuer eine durchsuchbare Combobox
    (z.B. Bestehende Versicherung) -- kombiniert mit der bestehenden
    Mehrdeutigkeits-Behandlung aus _waehle_durchsuchbar()."""
    if wert is None:
        yield FeldKlaerungNoetig(
            f"'{feldname_lesbar}' konnte nicht aus dem/den Dokument(en) gelesen werden. "
            "Bitte direkt im Browser eintragen.",
            feldpfad, [],
        )
        return page.input_value(selector), True
    manuell = yield from _versuche_oder_pausiere(
        lambda: _waehle_durchsuchbar(page, selector, wert, feldpfad=feldpfad)
    )
    return page.input_value(selector), manuell


def _gewaehltes_fahrzeug_name(page):
    """Liest den Fahrzeugnamen aus der 'Gewähltes Fahrzeug:'-Bestaetigung,
    die nach einem Klick auf eine Ergebniszeile die komplette Radioliste
    ERSETZT (live beobachtet 2026-08-26: die Radios verschwinden komplett
    aus dem DOM, sind daher NICHT mehr per is_checked() abfragbar -- auch
    nicht frisch abgefragt). Wird nur fuer den manuell-pausierten Zweig
    gebraucht; der automatische Zweig kennt den Zeilentext bereits vorher
    aus _waehle_aus_ergebnisliste()'s Rueckgabewert."""
    zeilen = [z.strip() for z in page.locator("body").inner_text().split("\n") if z.strip()]
    if "Gewähltes Fahrzeug:" in zeilen:
        idx = zeilen.index("Gewähltes Fahrzeug:")
        if idx + 1 < len(zeilen):
            return zeilen[idx + 1]
    return None


def _klick_weiter(page):
    page.get_by_role("button", name="Weiter", exact=True).click(timeout=10000)
    page.wait_for_load_state("networkidle")


def _waehle_falls_leer(page, selector, gewuenschter_wert, feldname_lesbar, feldpfad, praefix_ok=False):
    """Fuer die kaskadierenden Comboboxen im 'Marke und Modell'-Zweig
    (Treibstoff/Motorleistung/Bauart/Tueren): manche Felder sind nach den
    vorherigen Auswahlen schon eindeutig automatisch vorbefuellt -- dann
    NICHT anfassen (live beobachtet 2026-08-25, z.B. bei einem E-Auto mit
    nur einer Motorleistung). Ist das Feld leer, muss ausgewaehlt werden;
    ohne passenden fall.json-Wert wird klar abgebrochen statt zu raten --
    als FeldKlaerungNoetig(feldpfad, optionen), damit die Web-Oberflaeche
    das Feld gezielt zur erneuten Klaerung auf /pruefen zurueckgeben kann,
    statt in einer Sackgasse zu enden. praefix_ok=True fuer Felder mit
    unvorhersehbarem Optionstext-Zusatz (z.B. kW-Feld: '85 kW / 115,5 PS')."""
    aktuell = page.input_value(selector)
    if aktuell:
        return aktuell
    if gewuenschter_wert is None:
        page.click(selector, timeout=10000)
        page.wait_for_timeout(300)
        optionen = [o.inner_text().strip() for o in page.get_by_role("option").all()]
        page.keyboard.press("Escape")
        raise FeldKlaerungNoetig(
            f"Das Formular verlangt eine Auswahl fuer '{feldname_lesbar}', aber fall.json "
            f"enthaelt keinen Wert dafuer.",
            feldpfad, optionen,
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
    optionen_angezeigt = []
    if listbox:
        for opt in listbox.query_selector_all("[role=option]"):
            text = (opt.inner_text() or "").strip()
            optionen_angezeigt.append(text)
            norm = text.replace(".", ",")
            if norm == gewuenschter_text or (praefix_ok and norm.startswith(gewuenschter_text)):
                treffer = opt
                break
    if treffer is None:
        page.keyboard.press("Escape")
        raise FeldKlaerungNoetig(
            f"Kein Treffer fuer '{feldname_lesbar}' = '{gewuenschter_wert}' unter den "
            f"verfuegbaren Optionen gefunden.",
            feldpfad, optionen_angezeigt,
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
        raise FeldKlaerungNoetig(
            f"{len(zeilen)} passende Fahrzeuge gefunden, aber fall.json enthaelt keine "
            f"'variante' zur eindeutigen Auswahl.",
            "fahrzeug.variante", namen,
        )
    norm_ziel = variante_wert.strip().lower().replace(".", ",")
    treffer = [(r, t) for r, t in zeilen if norm_ziel in t.strip().lower().replace(".", ",")]
    if len(treffer) != 1:
        namen = [t.splitlines()[0] for _, t in zeilen]
        raise FeldKlaerungNoetig(
            f"variante='{variante_wert}' passt nicht eindeutig zu genau einem der "
            f"{len(zeilen)} gefundenen Fahrzeuge.",
            "fahrzeug.variante", namen,
        )
    treffer[0][0].click(timeout=8000)
    return treffer[0][1]


class DurchblickerPortal(KfzPortal):
    LIVE_KLAERBARE_FELDER = LIVE_KLAERBARE_FELDER

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
        """Generator: fuellt jeden Schritt aus und verifiziert ihn SOFORT
        (Auslesen aus dem DOM), BEVOR zum naechsten Schritt geblattert wird
        -- die Felder eines Schritts existieren nach 'Weiter' nicht mehr im
        DOM (SPA), ein nachtraegliches Zurueck-Auslesen am Ende ist daher
        nicht moeglich. Die gesammelten Verifikationszeilen liegen danach
        in self._zeilen; verify() liefert genau diese Liste.

        Ist fill() als Generator implementiert (statt eine normale
        Methode): an mehreren Stellen in der 'Marke und Modell'-Kaskade
        kann eine einzelne Auswahl nicht automatisch getroffen werden
        (FeldKlaerungNoetig, siehe _versuche_oder_pausiere). In diesem
        Fall 'yielded' fill() die Exception statt abzubrechen -- der
        Aufrufer (fill.py) haelt die Playwright-Sitzung an derselben
        Stelle an, laesst den Menschen die Auswahl DIREKT im bereits
        geoeffneten Browserfenster treffen, und ruft danach next()/send()
        erneut auf, um fortzusetzen. Live entwickelt 2026-08-26 als
        Antwort auf wiederholte Sackgassen bei mehrdeutigen
        Fahrzeug-Varianten (siehe feldkarte.md)."""
        fz, vn, pr = fall["fahrzeug"], fall["versicherungsnehmer"], fall["produkt"]
        zeilen = []

        def pruefe(pfad, soll, ist, ignore_case=False):
            """ignore_case=True fuer Freitext-Comboboxen (Marke, Modell,
            Versicherer), deren Formular-Optionen eine feste eigene
            Schreibweise haben (z.B. 'Peugeot' statt 'PEUGEOT' aus dem
            Dokument) -- die Auswahl selbst ist bereits durch
            _waehle_durchsuchbar() eindeutig verifiziert, nur die
            Gross-/Kleinschreibung darf hier noch abweichen."""
            ok = soll.casefold() == ist.casefold() if ignore_case and isinstance(soll, str) and isinstance(ist, str) else soll == ist
            zeilen.append({"pfad": pfad, "soll": soll, "ist": ist, "ok": ok})

        def pruefe_manuell(pfad, ist):
            """Wie pruefe(), aber nachdem der Mensch die Auswahl direkt im
            Browser getroffen hat (siehe _versuche_oder_pausiere) -- es
            gibt keinen fall.json-Sollwert zum Vergleichen mehr, die
            manuelle Auswahl gilt als richtig (der Mensch sieht dieselbe
            Seite, ist also die verlaesslichste verfuegbare Quelle)."""
            zeilen.append({"pfad": pfad, "soll": f"(manuell gewählt) {ist}", "ist": ist, "ok": True})

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

            marke_sel = "#auto\\.fahrzeug\\.marke-combobox"
            manuell = yield from _versuche_oder_pausiere(
                lambda: _waehle_durchsuchbar(page, marke_sel, fz["marke"]["wert"], feldpfad="fahrzeug.marke")
            )
            marke_ist = page.input_value(marke_sel)
            if manuell:
                pruefe_manuell("fahrzeug.marke", marke_ist)
            else:
                pruefe("fahrzeug.marke", fz["marke"]["wert"], marke_ist, ignore_case=True)

            modell_sel = "#auto\\.fahrzeug\\.modell-combobox"
            manuell = yield from _versuche_oder_pausiere(
                lambda: _waehle_durchsuchbar(page, modell_sel, fz["modell"]["wert"], feldpfad="fahrzeug.modell")
            )
            modell_ist = page.input_value(modell_sel)
            if manuell:
                pruefe_manuell("fahrzeug.modell", modell_ist)
            else:
                pruefe("fahrzeug.modell", fz["modell"]["wert"], modell_ist, ignore_case=True)

            treibstoff_sel = "#auto\\.fahrzeug\\.treibstoff-combobox"
            treibstoff_soll = fz.get("treibstoff", {}).get("wert")
            manuell = yield from _versuche_oder_pausiere(
                lambda: _waehle_falls_leer(page, treibstoff_sel, treibstoff_soll, "Treibstoff", "fahrzeug.treibstoff")
            )
            treibstoff_ist = page.input_value(treibstoff_sel)
            if manuell:
                pruefe_manuell("fahrzeug.treibstoff", treibstoff_ist)
            else:
                pruefe_kaskade("fahrzeug.treibstoff", treibstoff_soll, treibstoff_ist)

            kw_sel = "#auto\\.fahrzeug\\.kw-combobox"
            kw_soll = fz.get("motorleistung_kw", {}).get("wert")
            manuell = yield from _versuche_oder_pausiere(
                lambda: _waehle_falls_leer(
                    page, kw_sel, kw_soll, "Motorleistung (kW)", "fahrzeug.motorleistung_kw", praefix_ok=True
                )
            )
            kw_ist = page.input_value(kw_sel)
            if manuell:
                pruefe_manuell("fahrzeug.motorleistung_kw", kw_ist)
            else:
                pruefe_kaskade("fahrzeug.motorleistung_kw", kw_soll, kw_ist, praefix_ok=True)

            bauart_sel = "#auto\\.fahrzeug\\.bauart-combobox"
            bauart_soll = fz.get("bauart", {}).get("wert")
            manuell = yield from _versuche_oder_pausiere(
                lambda: _waehle_falls_leer(page, bauart_sel, bauart_soll, "Bauart", "fahrzeug.bauart")
            )
            bauart_ist = page.input_value(bauart_sel)
            if manuell:
                pruefe_manuell("fahrzeug.bauart", bauart_ist)
            else:
                pruefe_kaskade("fahrzeug.bauart", bauart_soll, bauart_ist)

            tueren_sel = "#auto\\.fahrzeug\\.tueren-combobox"
            if page.query_selector(tueren_sel):
                tueren_soll = fz.get("tueren", {}).get("wert")
                manuell = yield from _versuche_oder_pausiere(
                    lambda: _waehle_falls_leer(page, tueren_sel, tueren_soll, "Anzahl Türen", "fahrzeug.tueren")
                )
                tueren_ist = page.input_value(tueren_sel)
                if manuell:
                    pruefe_manuell("fahrzeug.tueren", tueren_ist)
                else:
                    pruefe_kaskade("fahrzeug.tueren", tueren_soll, tueren_ist)

            # Sonderfall gegenueber den anderen Kaskade-Feldern: ein Klick
            # auf eine Ergebniszeile ERSETZT die komplette Radioliste durch
            # eine 'Gewähltes Fahrzeug:'-Bestaetigung (live beobachtet
            # 2026-08-26) -- der Zeilentext ist danach nicht mehr ueber die
            # (verschwundenen) Radios abfragbar. Der Erfolgsfall kennt den
            # Text daher vorab aus dem Rueckgabewert; der manuelle Fall
            # liest ihn aus der Bestaetigung (_gewaehltes_fahrzeug_name).
            variante_soll = fz.get("variante", {}).get("wert")
            try:
                ergebnis_text = _waehle_aus_ergebnisliste(page, variante_soll)
                manuell = False
            except FeldKlaerungNoetig as e:
                yield e
                ergebnis_text = None
                manuell = True

            if manuell:
                erste_zeile = _gewaehltes_fahrzeug_name(page) or "?"
            else:
                erste_zeile = ergebnis_text.splitlines()[0] if ergebnis_text else "?"

            zeilen.append({
                "pfad": "fahrzeug.variante (Fahrzeug ausgewählt)",
                "soll": "(manuell gewählt)" if manuell else (variante_soll or f"(automatisch) {erste_zeile}"),
                "ist": erste_zeile,
                "ok": True,
            })

        _klick_weiter(page)

        # --- Schritt 2: Zulassungsdaten ---
        zugelassen_radios = page.locator('input[name="auto.fahrzeug.zugelassen-radiogroup"]')
        zugelassen_radios.nth(0).click(timeout=8000)  # Ja
        pruefe("fahrzeug.zugelassen", fz["zugelassen"]["wert"], _lies_ja_nein(zugelassen_radios))

        # erstbesitzer entscheidet, ob 'Erstzulassung auf Sie' ueberhaupt im
        # DOM erscheint (siehe unten) -- beide Zweige sind implementiert,
        # daher live klaerbar. Massgeblich fuer die weitere Verzweigung ist
        # der TATSAECHLICH ausgewaehlte Wert (erstbesitzer_ist), nicht der
        # urspruengliche fall.json-Wert -- der kann bei manueller Klaerung
        # vom Menschen anders entschieden werden.
        erstbesitzer_radios = page.locator('input[name="auto.fahrzeug.erstbesitzv-radiogroup"]')
        erstbesitzer_ist, manuell = yield from _boolean_oder_pausiere(
            "fahrzeug.erstbesitzer", "Fabriksneu gekauft (Erstbesitzer)", fz["erstbesitzer"]["wert"], erstbesitzer_radios
        )
        if manuell:
            pruefe_manuell("fahrzeug.erstbesitzer", erstbesitzer_ist)
        else:
            pruefe("fahrzeug.erstbesitzer", fz["erstbesitzer"]["wert"], erstbesitzer_ist)

        # Bei Erstbesitzer=Ja (fabriksneu) zeigt das Formular NUR
        # 'Erstzulassung des PKW' -- das zweite Feld 'Erstzulassung auf
        # Sie' existiert in diesem Zweig gar nicht im DOM, weil beide
        # Daten fuer einen Erstbesitzer per Definition identisch sind.
        # Live verifiziert 2026-08-25.
        page.wait_for_selector("#auto\\.fahrzeug\\.erstzulassung", timeout=10000)
        erstzulassung_pkw_ist, manuell = yield from _datum_oder_pausiere(
            page, "#auto\\.fahrzeug\\.erstzulassung", "fahrzeug.erstzulassung_pkw",
            "Erstzulassung des Fahrzeugs", fz["erstzulassung_pkw"]["wert"],
        )
        if manuell:
            pruefe_manuell("fahrzeug.erstzulassung_pkw", erstzulassung_pkw_ist)
        else:
            pruefe("fahrzeug.erstzulassung_pkw", fz["erstzulassung_pkw"]["wert"], erstzulassung_pkw_ist)

        if not erstbesitzer_ist:
            erstzulassung_auf_sie_ist, manuell = yield from _datum_oder_pausiere(
                page, "#auto\\.fahrzeug\\.erstzulassungvnv", "fahrzeug.erstzulassung_auf_sie",
                "Zulassung auf den Halter", fz["erstzulassung_auf_sie"]["wert"],
            )
            if manuell:
                pruefe_manuell("fahrzeug.erstzulassung_auf_sie", erstzulassung_auf_sie_ist)
            else:
                pruefe("fahrzeug.erstzulassung_auf_sie", fz["erstzulassung_auf_sie"]["wert"], erstzulassung_auf_sie_ist)

        finanzierung_radios = page.locator('input[name="auto.fahrzeug.finanzierung-radiogroup"]')
        finanzierung_radios.nth(0).click(timeout=8000)  # Nein
        pruefe("fahrzeug.finanzierung", fz["finanzierung"]["wert"],
               _lies_enum_radio(finanzierung_radios, ["Nein", "Leasing", "Kredit"]))

        _klick_weiter(page)

        # --- Schritt 3: Bonus/Malus-Stufe ---
        _waehle_direkt(page, "#auto\\.vn\\.bmstufe-select", vn["bonus_malus_stufe"]["wert"])
        pruefe("versicherungsnehmer.bonus_malus_stufe", vn["bonus_malus_stufe"]["wert"],
               page.inner_text("#auto\\.vn\\.bmstufe-select").strip())

        versicherer_sel = "#auto\\.vn\\.versicherer-combobox"
        versicherer_ist, manuell = yield from _durchsuchbar_oder_pausiere(
            page, versicherer_sel, "versicherungsnehmer.bestehende_versicherung",
            "Bestehende Versicherung", vn["bestehende_versicherung"]["wert"],
        )
        if manuell:
            pruefe_manuell("versicherungsnehmer.bestehende_versicherung", versicherer_ist)
        else:
            pruefe("versicherungsnehmer.bestehende_versicherung", vn["bestehende_versicherung"]["wert"],
                   versicherer_ist, ignore_case=True)

        zweitwagen_radios = page.locator('input[name="auto.rabatte.zweitwagen-radiogroup"]')
        zweitwagen_ist, manuell = yield from _boolean_oder_pausiere(
            "versicherungsnehmer.zweitwagen", "Zweitwagen im Haushalt", vn["zweitwagen"]["wert"], zweitwagen_radios
        )
        if manuell:
            pruefe_manuell("versicherungsnehmer.zweitwagen", zweitwagen_ist)
        else:
            pruefe("versicherungsnehmer.zweitwagen", vn["zweitwagen"]["wert"], zweitwagen_ist)

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
        # Richtungen, nicht nur ergaenzend anhaken. kasko_wert=None (echt
        # unklar, kommt praktisch kaum vor -- siehe Formular-Standard in
        # mapping.py) wird live geklaert statt stillschweigend als 'Nein'
        # behandelt.
        kasko_wert = pr.get("kasko_zusatzdeckung", {}).get("wert")
        kasko = page.get_by_role("checkbox", name="Kasko", exact=True)
        if kasko_wert is not None:
            if kasko.is_checked() != kasko_wert:
                kasko.click(timeout=8000)
            manuell = False
        else:
            yield FeldKlaerungNoetig(
                "'Kasko-Zusatzdeckung' konnte nicht aus dem/den Dokument(en) gelesen werden. "
                "Bitte direkt im Browser ankreuzen oder leer lassen.",
                "produkt.kasko_zusatzdeckung", ["Ja", "Nein"],
            )
            manuell = True
        kasko_ist = kasko.is_checked()
        if manuell:
            pruefe_manuell("produkt.kasko_zusatzdeckung", kasko_ist)
        else:
            pruefe("produkt.kasko_zusatzdeckung", kasko_wert, kasko_ist)

        # Wenn Kasko am Ende aktiv ist, verlangt das Formular zusaetzlich
        # eine Kaskovariante (Vollkasko/Teilkasko) -- dieses Feld erscheint
        # nur reaktiv, abhaengig von der Empfehlung fuer DIESES Fahrzeug,
        # und kann daher nicht vorab in unterstuetzter_pfad() geprueft
        # werden. Live entdeckt 2026-08-24. WICHTIG: die Radiogruppe bleibt
        # auch bei ausgeschaltetem Kasko im DOM (nur nicht mehr blockierend
        # fuer 'Weiter') -- pruefbar ist daher NICHT ihre DOM-Praesenz,
        # sondern der tatsaechliche Kasko-Checkbox-Zustand.
        kaskodeckung_radios = page.locator('input[name="auto.produkt.kaskodeckung-radiogroup"]')
        if kasko_ist:
            kaskovariante_wert = pr.get("kaskovariante", {}).get("wert")
            kaskovariante_ist, manuell = yield from _enum_oder_pausiere(
                "produkt.kaskovariante", "Kaskovariante", kaskovariante_wert,
                kaskodeckung_radios, ["Vollkasko", "Teilkasko"],
            )
            if manuell:
                pruefe_manuell("produkt.kaskovariante", kaskovariante_ist)
            else:
                pruefe("produkt.kaskovariante", kaskovariante_wert, kaskovariante_ist)

        _klick_weiter(page)

        # --- Schritt 5: Person / Versicherungsnehmer ---
        # anmeldung_als entscheidet, ob 'Firmenbucheintrag' ueberhaupt
        # erscheint (siehe unten) -- massgeblich ist wieder der TATSAECHLICH
        # ausgewaehlte Wert (anmeldung_als_ist), nicht der urspruengliche
        # fall.json-Wert.
        vntyp_radios = page.locator('input[name="auto.vn.vntyp-radiogroup"]')
        anmeldung_als_wert = vn["anmeldung_als"]["wert"]
        anmeldung_als_ist, manuell = yield from _enum_oder_pausiere(
            "versicherungsnehmer.anmeldung_als", "Anmeldung als", anmeldung_als_wert,
            vntyp_radios, ["Privatperson", "Einzelunternehmen"],
        )
        if manuell:
            pruefe_manuell("versicherungsnehmer.anmeldung_als", anmeldung_als_ist)
        else:
            pruefe("versicherungsnehmer.anmeldung_als", anmeldung_als_wert, anmeldung_als_ist)

        # 'Ist Ihr Einzelunternehmen im Firmenbuch eingetragen?' erscheint
        # nur nach Auswahl von 'Einzelunternehmen' -- live entdeckt
        # 2026-08-25.
        if anmeldung_als_ist == "Einzelunternehmen":
            firmenbuch_radios = page.locator('input[name="auto.vn.firmenbucheintrag-radiogroup"]')
            firmenbucheintrag_wert = vn.get("firmenbucheintrag", {}).get("wert")
            firmenbucheintrag_ist, manuell = yield from _boolean_oder_pausiere(
                "versicherungsnehmer.firmenbucheintrag", "Einzelunternehmen im Firmenbuch eingetragen",
                firmenbucheintrag_wert, firmenbuch_radios,
            )
            if manuell:
                pruefe_manuell("versicherungsnehmer.firmenbucheintrag", firmenbucheintrag_ist)
            else:
                pruefe("versicherungsnehmer.firmenbucheintrag", firmenbucheintrag_wert, firmenbucheintrag_ist)

        geburtsdatum_ist, manuell = yield from _datum_oder_pausiere(
            page, "#auto\\.vn\\.geburtsdatum", "versicherungsnehmer.geburtsdatum",
            "Geburtsdatum", vn["geburtsdatum"]["wert"],
        )
        if manuell:
            pruefe_manuell("versicherungsnehmer.geburtsdatum", geburtsdatum_ist)
        else:
            pruefe("versicherungsnehmer.geburtsdatum", vn["geburtsdatum"]["wert"], geburtsdatum_ist)

        plz_ist, manuell = yield from _text_oder_pausiere(
            page, "#auto\\.vn\\.region\\.plz", "versicherungsnehmer.plz", "Postleitzahl", vn["plz"]["wert"]
        )
        if manuell:
            pruefe_manuell("versicherungsnehmer.plz", plz_ist)
        else:
            pruefe("versicherungsnehmer.plz", vn["plz"]["wert"], plz_ist)

        email_ist, manuell = yield from _text_oder_pausiere(
            page, "#auto\\.vn\\.mail", "versicherungsnehmer.email", "E-Mail-Adresse", vn["email"]["wert"]
        )
        if manuell:
            pruefe_manuell("versicherungsnehmer.email", email_ist)
        else:
            pruefe("versicherungsnehmer.email", vn["email"]["wert"], email_ist)

        # ABSICHTLICH KEIN Klick auf "Zum Ergebnis" -- siehe Projektauftrag.

        self._zeilen = zeilen

    def verify(self, page, fall):
        """Liefert die Verifikationszeilen, die fill() bereits pro Schritt
        gesammelt hat (siehe Docstring dort)."""
        return getattr(self, "_zeilen", [])
