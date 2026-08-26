"""
Liest ein bestaetigtes fall.json und fuellt den durchblicker.at KFZ-Rechner
Schritt fuer Schritt aus. Klickt NIE auf "Berechnen"/"Zum Ergebnis" und
sendet nichts ab. Der Browser bleibt am Ende offen, damit das Ergebnis
selbst geprueft werden kann -- das Skript beendet sich nicht von selbst,
sondern wartet auf Enter.

Kann eine einzelne Auswahl in der 'Marke und Modell'-Kaskade nicht
automatisch getroffen werden (FeldKlaerungNoetig, siehe portals/base.py),
pausiert das Ausfuellen an genau dieser Stelle -- der Mensch trifft die
Auswahl DIREKT im bereits geoeffneten Browserfenster, danach macht die
Automatisierung automatisch mit dem Rest weiter (CLI: Enter druecken;
Web-Oberflaeche: siehe FuellSitzung/app.py).

Voraussetzungen (werden hart erzwungen, kein Flag zum Ueberspringen):
  1. fall.json muss validate.py OHNE Beanstandung durchlaufen (Schema,
     Klaerungsbedarf, Plausibilitaet) -- d.h. confirm.py muss vorher
     erfolgreich gelaufen sein.
  2. fall.json darf nur Wizard-Zweige verwenden, die live erkundet und in
     portals/durchblicker.py implementiert sind (siehe
     DurchblickerPortal.unterstuetzter_pfad und feldkarte.md-TODOs).

Verwendung:
    python fill.py fall.json
"""

import json
import queue
import sys
import threading
from pathlib import Path

from colorama import Fore, Style, init as colorama_init
from playwright.sync_api import sync_playwright

from feldbezeichnungen import label
from portals.base import FeldKlaerungNoetig
from portals.durchblicker import DurchblickerPortal
from validate import validiere

BASE_DIR = Path(__file__).resolve().parent
STATE_FILE = BASE_DIR / "state" / "storage_state.json"
LOGS_DIR = BASE_DIR / "logs"


def drucke_verifikationstabelle(zeilen):
    breite_pfad = max(len(label(z["pfad"])) for z in zeilen) + 1
    print(f"\n{'Feld'.ljust(breite_pfad)}  {'Soll'.ljust(28)}  {'Ist'.ljust(28)}  Status")
    print("-" * (breite_pfad + 28 + 28 + 20))
    for z in zeilen:
        soll = str(z["soll"])[:28]
        ist = str(z["ist"])[:28]
        status = (Fore.GREEN + "OK" + Style.RESET_ALL) if z["ok"] else (Fore.RED + "FEHLER" + Style.RESET_ALL)
        print(f"{label(z['pfad']).ljust(breite_pfad)}  {soll.ljust(28)}  {ist.ljust(28)}  {status}")
    print()


def dump_fehler(page, name, meldung):
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    screenshot_pfad = LOGS_DIR / f"{name}.png"
    html_pfad = LOGS_DIR / f"{name}.html"
    page.screenshot(path=str(screenshot_pfad), full_page=True)
    html_pfad.write_text(page.content(), encoding="utf-8")
    print(Fore.RED + f"FEHLER: {meldung}" + Style.RESET_ALL, file=sys.stderr)
    print(f"Screenshot: {screenshot_pfad}", file=sys.stderr)
    print(f"HTML-Dump: {html_pfad}", file=sys.stderr)


def _lade_und_pruefe_fall(fall_pfad):
    """Laedt fall_pfad, prueft Bestaetigung + unterstuetzten Pfad. Liefert
    (fall, portal) oder wirft ValueError mit einer bereits fertig
    formatierten (aber noch nicht gedruckten) Fehlermeldung."""
    fall_pfad = Path(fall_pfad)
    with open(fall_pfad, encoding="utf-8") as f:
        fall = json.load(f)

    bericht = validiere(fall)
    if not bericht["ok"]:
        raise ValueError(
            "fall.json ist nicht bestaetigt. Bitte zuerst 'python confirm.py <fall.json>' "
            "erfolgreich durchlaufen lassen.\n" + json.dumps(bericht, ensure_ascii=False, indent=2)
        )

    portal = DurchblickerPortal()
    unterstuetzt_nicht = portal.unterstuetzter_pfad(fall)
    if unterstuetzt_nicht:
        raise ValueError(
            "fall.json verwendet Wizard-Zweige, die noch nicht live erkundet/implementiert sind:\n"
            + "\n".join(f"  - {g}" for g in unterstuetzt_nicht)
        )

    return fall, portal


class FuellSitzung:
    """Treibt portal.fill() (ein Generator, siehe portals/base.py) fuer
    die Web-Oberflaeche in einem EIGENEN, langlebigen Worker-Thread an --
    NICHT im jeweiligen Flask-Request-Thread. Grund (live verifiziert
    2026-08-26): Playwrights Sync API bindet eine Seite/einen Browser an
    das Greenlet-Dispatching des Threads, der sync_playwright().start()
    aufgerufen hat. Flasks threaded=True startet fuer JEDEN Request einen
    NEUEN Thread -- versucht ein spaeterer Request, dieselbe Seite
    anzufassen, wirft Playwright 'cannot switch to a different thread
    (which happens to have exited)'. Die Loesung: der Worker-Thread lebt
    ueber mehrere Requests hinweg weiter und wartet bei einer Pause auf
    einem threading.Event, statt dass ein neuer Thread die Seite anfasst.
    Kommunikation ausschliesslich ueber thread-sichere Queue/Event, nie
    ueber direkten Zugriff auf page/browser von aussen."""

    def __init__(self):
        self._status_queue = queue.Queue()
        self._fortsetzen_event = threading.Event()
        self._thread = None

    def starte(self, fall_pfad):
        self._thread = threading.Thread(target=self._laufen, args=(fall_pfad,), daemon=True)
        self._thread.start()
        return self._status_queue.get()

    def fortsetzen(self):
        """Vom Mensch direkt im Browser erledigt -- Worker-Thread fortsetzen."""
        self._fortsetzen_event.set()
        return self._status_queue.get()

    def _laufen(self, fall_pfad):
        try:
            fall, portal = _lade_und_pruefe_fall(fall_pfad)
        except ValueError as e:
            self._status_queue.put(("fehler", str(e)))
            return

        playwright = sync_playwright().start()
        browser = playwright.chromium.launch(headless=False)
        if STATE_FILE.exists():
            context = browser.new_context(storage_state=str(STATE_FILE))
        else:
            context = browser.new_context()
        page = context.new_page()

        try:
            portal.navigate(page)
            gen = portal.fill(page, fall)
            while True:
                try:
                    klaerung = next(gen)
                except StopIteration:
                    break
                self._status_queue.put((
                    "klaerung",
                    {"feldpfad": klaerung.feldpfad, "optionen": klaerung.optionen, "meldung": str(klaerung)},
                ))
                self._fortsetzen_event.wait()
                self._fortsetzen_event.clear()
        except Exception as e:
            dump_fehler(page, "fill_fehler", f"Ausfuellen abgebrochen: {e}")
            self._status_queue.put(
                ("fehler", f"Ausfuellen abgebrochen: {e} (Browser bleibt zur Fehlersuche offen)")
            )
            return

        zeilen = portal.verify(page, fall)
        self._status_queue.put(("fertig", zeilen))


def fuelle_aus(fall_pfad):
    """Fuellt den KFZ-Rechner anhand einer bestaetigten fall.json aus,
    verifiziert jedes Feld und haelt den Browser danach offen (wartet auf
    Enter). Liefert den gewuenschten Exit-Code (0 = alles verifiziert,
    1 = Abweichung/Fehler/nicht bestaetigt)."""
    try:
        fall, portal = _lade_und_pruefe_fall(fall_pfad)
    except ValueError as e:
        print(Fore.RED + f"FEHLER: {e}" + Style.RESET_ALL, file=sys.stderr)
        return 1

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=False)
        if STATE_FILE.exists():
            context = browser.new_context(storage_state=str(STATE_FILE))
            print(f"Session-State geladen: {STATE_FILE}")
        else:
            context = browser.new_context()
            print("Kein Session-State gefunden, fuelle ohne Login (Rechner ist oeffentlich nutzbar).")
        page = context.new_page()

        try:
            portal.navigate(page)
            gen = portal.fill(page, fall)
            while True:
                try:
                    klaerung = next(gen)
                except StopIteration:
                    break
                print(Fore.YELLOW + f"\nBitte im geoeffneten Browserfenster '{label(klaerung.feldpfad)}' "
                                     "selbst auswaehlen." + Style.RESET_ALL)
                if klaerung.optionen:
                    print(f"Zur Auswahl stehen: {', '.join(klaerung.optionen)}")
                input("Enter druecken, sobald im Browser erledigt...")
        except Exception as e:
            dump_fehler(page, "fill_fehler", f"Ausfuellen abgebrochen: {e}")
            input("\nBrowser bleibt offen zur Fehlersuche. Enter druecken zum Beenden...")
            browser.close()
            return 1

        zeilen = portal.verify(page, fall)
        drucke_verifikationstabelle(zeilen)
        alle_ok = all(z["ok"] for z in zeilen)

        if alle_ok:
            print(Fore.GREEN + "Alle Felder verifiziert -- Formular korrekt ausgefuellt. "
                                "Bitte selbst im Browser pruefen." + Style.RESET_ALL)
        else:
            print(Fore.RED + "WARNUNG: Abweichungen zwischen Soll und Ist gefunden -- "
                              "siehe Tabelle oben. Bitte manuell pruefen/korrigieren." + Style.RESET_ALL)

        input("\nBrowser bleibt offen. Enter druecken zum Beenden...")
        browser.close()
        return 0 if alle_ok else 1


def main():
    colorama_init()

    if len(sys.argv) != 2:
        print("Verwendung: python fill.py <fall.json>", file=sys.stderr)
        sys.exit(2)

    sys.exit(fuelle_aus(sys.argv[1]))


if __name__ == "__main__":
    main()
