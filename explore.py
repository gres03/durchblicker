"""
Erkundet den durchblicker.at KFZ-Rechner Schritt fuer Schritt und dumpt fuer
jeden Formularschritt: sichtbare input/select/radio/checkbox-Elemente (Label,
name, id, type), Dropdown-Optionen (wo per Klick erreichbar), Screenshot und
Accessibility-Snapshot. Ergebnis landet in ./exploration/<NN>_<step>.*

Fuellt dabei plausible Testwerte aus, um durch den Wizard vorwaerts zu kommen:
  - Fahrzeug-Auswahl ueber "Nationaler Zulassungscode" (Code "260094" loest
    verifiziert exakt zu "Volkswagen Golf 2,0 TDI Life" auf -- der einzige
    Weg, ein Fahrzeug OHNE Rateschritte bei Marke/Modell eindeutig zu
    identifizieren)
  - Zulassungsdaten: bereits zugelassen=Ja, Erstbesitzer=Nein (Gebrauchtwagen-
    Zweig, zeigt Erstzulassungs-Datumsfelder), keine Finanzierung
  - Bonus/Malus-Stufe: Stufe 9, keine bestehende Versicherung, kein Zweitwagen
  - Produkt: "durchblicker Empfehlung"
  - Person: Default-Werte, NUR bis zum Screen "Versicherungsnehmer" -- der
    "Zum Ergebnis"-Button wird NIEMALS geklickt (siehe WICHTIGSTE REGEL im
    Projektauftrag: das Tool fuellt nur aus, sendet nichts ab).

Deckt damit den kompletten Hauptpfad des Wizards ab (verifiziert am
2026-08-24). Alternative Zweige (z.B. "Nein" bei zugelassen, "Marke und
Modell" statt Zulassungscode, Leasing/Kredit, Einzelunternehmen) sind NICHT
durchlaufen -- siehe TODOs in feldkarte.md.
"""

import json
from pathlib import Path

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

BASE_DIR = Path(__file__).resolve().parent
STATE_FILE = BASE_DIR / "state" / "storage_state.json"
OUT_DIR = BASE_DIR / "exploration"

START_URL = "https://durchblicker.at/autoversicherung/vergleich/auto/fahrzeugauswahl"
COOKIE_ACCEPT_NAME = "Alle Cookies akzeptieren"

TEST_BAUJAHR = "2020"
TEST_ZULASSUNGSCODE = "260094"  # VW Golf 2,0 TDI Life, siehe Docstring

step_counter = 0


def dismiss_cookie_banner(page):
    try:
        page.get_by_role("button", name=COOKIE_ACCEPT_NAME).click(timeout=45000)
    except PlaywrightTimeoutError:
        pass


def dump_step(page, name):
    global step_counter
    step_counter += 1
    prefix = f"{step_counter:02d}_{name}"
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    page.screenshot(path=str(OUT_DIR / f"{prefix}.png"), full_page=True)

    fields = []
    for el in page.query_selector_all("input, select, textarea, [role=combobox]"):
        try:
            if not el.is_visible():
                continue
        except Exception:
            continue
        fields.append({
            "tag": el.evaluate("e => e.tagName"),
            "type": el.get_attribute("type"),
            "name": el.get_attribute("name"),
            "id": el.get_attribute("id"),
            "placeholder": el.get_attribute("placeholder"),
            "role": el.get_attribute("role"),
        })

    headings = []
    for el in page.query_selector_all("h1, h2, h3, h4, label"):
        try:
            if not el.is_visible():
                continue
            t = (el.inner_text() or "").strip()
        except Exception:
            t = ""
        if t:
            headings.append(t)

    accessibility_tree = page.locator("body").aria_snapshot()

    dump = {
        "step": name,
        "url": page.url,
        "headings_and_labels": headings,
        "visible_fields": fields,
    }
    (OUT_DIR / f"{prefix}.json").write_text(
        json.dumps(dump, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (OUT_DIR / f"{prefix}_a11y.yaml").write_text(accessibility_tree, encoding="utf-8")
    print(f"[dump] {prefix}  URL={page.url}  sichtbare Felder={len(fields)}")


def dump_dropdown_options(page, trigger_selector, name):
    page.click(trigger_selector, timeout=20000)
    page.wait_for_timeout(600)
    listbox = None
    for lb in page.query_selector_all("[role=listbox]"):
        if lb.is_visible():
            listbox = lb
            break
    options = []
    if listbox:
        for el in listbox.query_selector_all("[role=option]"):
            try:
                t = (el.inner_text() or "").strip()
            except Exception:
                t = ""
            if t:
                options.append(t)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / f"optionen_{name}.json").write_text(
        json.dumps(options, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"[optionen] {name}: {len(options)} initial gerenderte Optionen "
          f"(virtualisierte/durchsuchbare Liste -- ggf. nicht vollstaendig)")
    page.keyboard.press("Escape")
    page.wait_for_timeout(300)
    return options


def fill_segmented_date(page, selector, ddmmyyyy):
    """Fuellt eine der 'TT / MM / JJJJ'-Datumsfelder (role=combobox, kein
    <input>): Element anklicken, dann Ziffern durchtippen wie bei einem
    nativen Date-Input. Nicht mit Escape abschliessen (verwirft den Wert) --
    Tab druecken."""
    page.click(selector)
    page.keyboard.type(ddmmyyyy)
    page.wait_for_timeout(300)
    page.keyboard.press("Tab")
    page.wait_for_timeout(300)


def main():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=False)
        if STATE_FILE.exists():
            context = browser.new_context(storage_state=str(STATE_FILE))
            print(f"Session-State geladen: {STATE_FILE}")
        else:
            context = browser.new_context()
            print("Kein Session-State gefunden, erkunde ohne Login.")
        page = context.new_page()

        # --- Schritt 1: Fahrzeug waehlen ---
        page.goto(START_URL, wait_until="networkidle")
        dismiss_cookie_banner(page)
        page.wait_for_timeout(500)
        dump_step(page, "fahrzeugauswahl_leer")

        dump_dropdown_options(page, "#auto\\.fahrzeug\\.baujahr-combobox", "baujahr")
        page.click("#auto\\.fahrzeug\\.baujahr-combobox", timeout=20000)
        page.wait_for_timeout(500)
        page.get_by_role("option", name=TEST_BAUJAHR, exact=True).click(timeout=20000)
        page.wait_for_timeout(1000)

        page.get_by_text("Nationaler Zulassungscode", exact=False).click(timeout=10000)
        page.wait_for_timeout(500)
        page.fill("#auto\\.fahrzeug\\.etxauswahl", TEST_ZULASSUNGSCODE)
        page.wait_for_timeout(2500)
        dump_step(page, "fahrzeugauswahl_fahrzeug_aufgeloest")

        page.get_by_role("button", name="Weiter", exact=True).click(timeout=10000)
        page.wait_for_timeout(1500)

        # --- Schritt 2: Zulassungsdaten ---
        page.locator('input[name="auto.fahrzeug.zugelassen-radiogroup"]').nth(0).click(timeout=8000)  # Ja
        page.wait_for_timeout(800)
        dump_step(page, "zulassungsdaten_nach_zugelassen_ja")

        page.locator('input[name="auto.fahrzeug.erstbesitzv-radiogroup"]').nth(1).click(timeout=8000)  # Nein
        page.wait_for_timeout(800)
        dump_step(page, "zulassungsdaten_nach_erstbesitzv_nein")

        fill_segmented_date(page, "#auto\\.fahrzeug\\.erstzulassungvnv", "15012020")
        page.locator('input[name="auto.fahrzeug.finanzierung-radiogroup"]').nth(0).click(timeout=8000)  # Nein
        page.wait_for_timeout(500)
        dump_step(page, "zulassungsdaten_vollstaendig")

        page.get_by_role("button", name="Weiter", exact=True).click(timeout=10000)
        page.wait_for_timeout(1500)

        # --- Schritt 3: Bonus/Malus-Stufe ---
        dump_dropdown_options(page, "#auto\\.vn\\.bmstufe-select", "bmstufe")
        page.click("#auto\\.vn\\.bmstufe-select", timeout=10000)
        page.wait_for_timeout(500)
        page.get_by_role("option", name="9 - Einsteigerstufe", exact=True).click(timeout=8000)
        page.wait_for_timeout(500)

        dump_dropdown_options(page, "#auto\\.vn\\.versicherer-combobox", "versicherer")
        page.click("#auto\\.vn\\.versicherer-combobox", timeout=10000)
        page.wait_for_timeout(500)
        page.get_by_role("option", name="Derzeit keine Versicherung", exact=True).click(timeout=8000)
        page.wait_for_timeout(500)

        page.locator('input[name="auto.rabatte.zweitwagen-radiogroup"]').nth(1).click(timeout=8000)  # Nein
        page.wait_for_timeout(500)
        dump_step(page, "bmstufe_vollstaendig")

        page.get_by_role("button", name="Weiter", exact=True).click(timeout=10000)
        page.wait_for_timeout(2000)

        # --- Schritt 4: Produkt / Leistungsumfang ---
        dump_step(page, "leistungsumfang_leer")
        page.locator('input[name="auto.produkt.auswahl-radiogroup"]').nth(0).click(timeout=8000)  # durchblicker Empfehlung
        page.wait_for_timeout(500)
        dump_step(page, "leistungsumfang_ausgewaehlt")

        page.get_by_role("button", name="Weiter", exact=True).click(timeout=10000)
        page.wait_for_timeout(2000)

        # --- Schritt 5: Person / Versicherungsnehmer ---
        dump_step(page, "person_versicherungsnehmer")

        print(
            "\nStop VOR dem 'Zum Ergebnis'-Button (letzter Schritt im Wizard). "
            "Dieser Button wird laut Projektauftrag NIE geklickt -- das Tool "
            "fuellt nur aus, sendet nichts ab.\n"
            "Nicht erkundete Nebenzweige (u.a. 'Nein' bei zugelassen, "
            "'Marke und Modell' statt Zulassungscode, Leasing/Kredit, "
            "Einzelunternehmen, Kasko-Zusatzdeckung) siehe TODOs in "
            "feldkarte.md."
        )

        browser.close()


if __name__ == "__main__":
    main()
