"""
Abstrakte Schnittstelle fuer ein KFZ-Vergleichsportal. Ein zweites Portal
ist spaeter nur ein neues Modul in portals/, das diese Klasse implementiert
-- fill.py und login.py aendern sich dabei nicht.
"""

from abc import ABC, abstractmethod


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
        """Fuellt den Wizard Schritt fuer Schritt anhand von fall.json aus.
        Nutzt Playwright-Auto-Waiting, kein time.sleep(). Klickt NIE auf
        den Abschluss-/'Zum Ergebnis'-Button.

        Da es sich um eine Single-Page-App handelt, existieren die
        DOM-Elemente eines Schritts nach 'Weiter' nicht mehr -- Implementierungen
        MUESSEN daher jeden Schritt SOFORT nach dem Ausfuellen (vor dem
        Klick auf 'Weiter') verifizieren und das Ergebnis intern sammeln,
        damit verify() es danach zurueckgeben kann."""

    @abstractmethod
    def verify(self, page, fall):
        """Liefert die waehrend fill() pro Schritt gesammelten
        Verifikationszeilen: Liste von Dicts {pfad, soll, ist, ok}."""
