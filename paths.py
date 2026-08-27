"""
Pfad-Aufloesung, die sowohl im normalen 'python app.py'-Lauf als auch in
einer per PyInstaller gebauten .exe funktioniert (siehe build_exe.spec).

PyInstaller entpackt mitgelieferte Dateien (Templates, fall.schema.json,
synonyme.json, ...) bei jedem Start in ein TEMPORAERES Verzeichnis
(sys._MEIPASS), das nach Programmende wieder verschwindet -- dort duerfen
also nur schreibgeschuetzte, mitgelieferte Ressourcen liegen. Beschreibbare
Laufzeitdaten (Gemini-API-Schluessel, hochgeladene Dokumente, Logs) muessen
dagegen dauerhaft NEBEN der .exe liegen, sonst waeren sie nach jedem
Neustart weg.
"""

import os
import sys
from pathlib import Path


def ressourcen_pfad():
    """Basisverzeichnis fuer mitgelieferte, schreibgeschuetzte Dateien
    (templates/, fall.schema.json, synonyme.json, extraktion_anfrage.txt)."""
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent


def daten_pfad():
    """Basisverzeichnis fuer beschreibbare Laufzeitdaten (Einstellungen,
    web_uploads/, state/, logs/) -- bleibt bei einer .exe dauerhaft neben
    dieser liegen, nicht im temporaeren Extraktionsverzeichnis."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def _stelle_playwright_browser_pfad_sicher():
    """Playwright legt heruntergeladene Browser standardmaessig relativ
    zum Ort des Treiber-Pakets ab. In einer PyInstaller-onefile-.exe
    aendert sich dieser Ort bei JEDEM Start (neues temporaeres
    Extraktionsverzeichnis, sys._MEIPASS) -- ohne diese Umgebungsvariable
    wuerde Chromium beim naechsten Start also nicht wiedergefunden und
    (live beobachtet 2026-08-27) 'Executable doesn't exist at
    ...\\_MEIxxxxx\\playwright\\driver\\...\\chrome.exe' werfen. Fix: fester,
    dauerhafter Ort neben der .exe -- dieselbe Umgebungsvariable wird
    sowohl beim Installieren (_stelle_chromium_sicher in app.py) als auch
    beim spaeteren Browser-Start gelesen, muss also nur einmal hier beim
    Modul-Import gesetzt werden, bevor irgendein Playwright-Code laeuft."""
    os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", str(daten_pfad() / "playwright-browsers"))


_stelle_playwright_browser_pfad_sicher()
