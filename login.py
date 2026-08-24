"""
Login fuer durchblicker.at. Fuellt das Anmeldeformular aus, speichert den
Session-State (Cookies + LocalStorage) nach ./state/ zur Wiederverwendung
in fill.py / explore.py.

Verifizierte Selektoren (live auf https://durchblicker.at/konto/auth/anmelden
mit Playwright geprueft am 2026-08-24):
  - E-Mail-Feld:    #login-email
  - Passwort-Feld:  #login-password
  - Submit-Button:  #login-container-form-cta (bindet Google reCAPTCHA v2,
                     unsichtbar/"invisible" -- loest im normalen (nicht
                     headless) Browser automatisch aus, kein Klick auf eine
                     Checkbox noetig)
  - Cookie-Banner:  Button mit Accessible Name "Alle Cookies akzeptieren"
                     (muss weggeklickt werden, sonst blockiert er den
                     Submit-Button)
  - Fehlermeldung:  .alert.error-container .error-message
                     (verifiziert per Testlauf mit falschen Zugangsdaten;
                     Text z.B. "Ihre E-Mail-Adresse oder Ihr Passwort ist
                     falsch")

Der Erfolgsfall (welche Seite/Element nach echtem Login erscheint) konnte
bisher NICHT mit echten Zugangsdaten verifiziert werden. Als Erfolgssignal
wird daher verwendet: die URL wechselt weg von der Login-Seite UND es
erscheint keine Fehlermeldung. Beim ersten echten Lauf bitte pruefen, ob
das zuverlaessig ist -- Screenshot wird in jedem Fall nach ./logs/
geschrieben.
"""

import argparse
import json
import sys
from pathlib import Path

from dotenv import load_dotenv
import os

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

BASE_DIR = Path(__file__).resolve().parent
STATE_DIR = BASE_DIR / "state"
LOGS_DIR = BASE_DIR / "logs"
STATE_FILE = STATE_DIR / "storage_state.json"

LOGIN_URL = "https://durchblicker.at/konto/auth/anmelden"

COOKIE_ACCEPT_NAME = "Alle Cookies akzeptieren"
ERROR_SELECTOR = ".alert.error-container .error-message"


def dismiss_cookie_banner(page):
    try:
        page.get_by_role("button", name=COOKIE_ACCEPT_NAME).click(timeout=8000)
    except PlaywrightTimeoutError:
        pass


def save_state(context):
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    context.storage_state(path=str(STATE_FILE))
    print(f"Session-State gespeichert: {STATE_FILE}")


def fail(page, message):
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    screenshot_path = LOGS_DIR / "login_fehler.png"
    page.screenshot(path=str(screenshot_path), full_page=True)
    print(f"FEHLER: {message}", file=sys.stderr)
    print(f"Screenshot: {screenshot_path}", file=sys.stderr)
    sys.exit(1)


def run_auto_login(playwright, email, password):
    browser = playwright.chromium.launch(headless=False)
    context = browser.new_context()
    page = context.new_page()

    page.goto(LOGIN_URL, wait_until="networkidle")
    dismiss_cookie_banner(page)

    page.fill("#login-email", email)
    page.fill("#login-password", password)
    page.click("#login-container-form-cta")

    try:
        page.wait_for_url(lambda url: url != LOGIN_URL, timeout=20000)
    except PlaywrightTimeoutError:
        error_el = page.query_selector(ERROR_SELECTOR)
        if error_el:
            error_text = error_el.inner_text().strip()
            fail(page, f"Login fehlgeschlagen: {error_text}")
        else:
            fail(page, "Login-Ergebnis nach 20s nicht eindeutig (keine Navigation, keine erkannte Fehlermeldung).")

    print(f"Login erfolgreich, aktuelle URL: {page.url}")
    save_state(context)
    browser.close()


def run_manual_login(playwright):
    browser = playwright.chromium.launch(headless=False)
    context = browser.new_context()
    page = context.new_page()

    page.goto(LOGIN_URL, wait_until="networkidle")
    dismiss_cookie_banner(page)

    print("Bitte manuell im Browser einloggen.")
    input("Enter druecken, sobald der Login abgeschlossen ist...")

    save_state(context)
    browser.close()


def main():
    parser = argparse.ArgumentParser(description="Login fuer durchblicker.at")
    parser.add_argument("--manual", action="store_true", help="Browser oeffnen, manuell einloggen, State speichern")
    args = parser.parse_args()

    load_dotenv(BASE_DIR / ".env")

    email = os.environ.get("DURCHBLICKER_USER")
    password = os.environ.get("DURCHBLICKER_PASS")
    if not args.manual and (not email or not password):
        print(
            "FEHLER: DURCHBLICKER_USER / DURCHBLICKER_PASS fehlen in .env. "
            "Alternativ --manual verwenden.",
            file=sys.stderr,
        )
        sys.exit(1)

    with sync_playwright() as playwright:
        if args.manual:
            run_manual_login(playwright)
        else:
            run_auto_login(playwright, email, password)


if __name__ == "__main__":
    main()
