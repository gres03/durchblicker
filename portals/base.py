"""
Abstrakte Schnittstelle fuer ein KFZ-Vergleichsportal. Ein zweites Portal
ist spaeter nur ein neues Modul in portals/, das diese Klasse implementiert
-- fill.py und login.py aendern sich dabei nicht.
"""

from abc import ABC, abstractmethod


class FeldKlaerungNoetig(RuntimeError):
    """Ausloesbar aus fill(), wenn ein einzelnes Feld nicht automatisch
    aufgeloest werden konnte (z.B. mehrdeutige/kein Treffer bei einer
    durchsuchbaren Combobox), aber der Rest des bereits Ausgefuellten
    gueltig bleibt. Traegt zusaetzlich zur Meldung den betroffenen
    fall.json-Feldpfad (z.B. 'fahrzeug.variante') und, falls bekannt, die
    tatsaechlich am Formular angezeigten Optionen -- damit die Web-
    Oberflaeche das Feld gezielt zur erneuten Klaerung auf /pruefen
    zurueckgeben kann, statt in einer Sackgasse zu enden (echter
    Nutzerfall 2026-08-26: ein Fahrzeug mit 5 mehrdeutigen Varianten)."""

    def __init__(self, message, feldpfad, optionen=None):
        super().__init__(message)
        self.feldpfad = feldpfad
        self.optionen = optionen or []


class KfzPortal(ABC):
    @abstractmethod
    def login(self, page, email, password):
        """Loggt automatisch ein. Wirft bei Fehlschlag eine Exception mit
        Klartext-Grund (kein Retry-Loop, siehe Projektauftrag)."""

    @abstractmethod
    def navigate(self, page):
        """Navigiert zum ersten Schritt des KFZ-Vergleichs-Wizards."""

    @abstractmethod
    def unterstuetzter_pfad(self, fall):
        """Prueft, ob fall.json ausschliesslich live verifizierte
        Wizard-Zweige verwendet (siehe feldkarte.md TODOs). Liefert eine
        Liste von Klartext-Gruenden fuer JEDEN nicht unterstuetzten Zweig;
        leere Liste = unterstuetzt. fill.py MUSS abbrechen, wenn diese
        Liste nicht leer ist -- kein Raten bei unbekannten Selektoren."""

    @abstractmethod
    def fill(self, page, fall):
        """Generator: fuellt den Wizard Schritt fuer Schritt anhand von
        fall.json aus. Nutzt Playwright-Auto-Waiting, kein time.sleep().
        Klickt NIE auf den Abschluss-/'Zum Ergebnis'-Button.

        Da es sich um eine Single-Page-App handelt, existieren die
        DOM-Elemente eines Schritts nach 'Weiter' nicht mehr -- Implementierungen
        MUESSEN daher jeden Schritt SOFORT nach dem Ausfuellen (vor dem
        Klick auf 'Weiter') verifizieren und das Ergebnis intern sammeln,
        damit verify() es danach zurueckgeben kann.

        Kann eine einzelne Auswahl nicht automatisch getroffen werden,
        'yielded' die Implementierung eine FeldKlaerungNoetig statt
        abzubrechen -- der Aufrufer haelt die Playwright-Sitzung an
        genau dieser Stelle an, ein Mensch trifft die Auswahl DIREKT im
        bereits geoeffneten Browserfenster, und der Aufrufer ruft
        next()/send() erneut auf, um fortzusetzen (aktion() wird dabei
        NICHT erneut versucht). Laeuft der Generator vollstaendig durch
        (StopIteration), ist das Ausfuellen fertig."""

    @abstractmethod
    def verify(self, page, fall):
        """Liefert die waehrend fill() pro Schritt gesammelten
        Verifikationszeilen: Liste von Dicts {pfad, soll, ist, ok}."""
