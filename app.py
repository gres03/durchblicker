"""
Lokale Web-Oberflaeche: Dokument hochladen -> automatische Erkennung
(Gemini API, kostenloses Kontingent) -> Uebersetzung -> Bestaetigung nur
bei echtem Klaerungsbedarf (als Formular statt Terminal-Tabelle) ->
Ausfuellen + Verifikation im Browser.

Laeuft komplett lokal auf diesem PC (kein Deployment, kein externer
Zugriff). Start:
    python app.py
Oeffnet sich automatisch im Standardbrowser unter http://127.0.0.1:5000/
"""

import json
import threading
import webbrowser
from datetime import date

from flask import Flask, redirect, render_template, request, url_for

from confirm import resolve_wert_schema, sammle_gruende
from extract import ExtraktionsFehler, extrahiere, gemini_key_gesetzt, speichere_gemini_key
from feldbezeichnungen import label
from fill import FuellSitzung, bereit_zum_ausfuellen
from mapping import map_fall
from paths import daten_pfad, ressourcen_pfad
from portals.durchblicker import DurchblickerPortal
from validate import alle_felder, lade_schema, validiere

UPLOAD_DIR = daten_pfad() / "web_uploads"
UPLOAD_DIR.mkdir(exist_ok=True)
FALL_PFAD = UPLOAD_DIR / "aktueller_fall.json"

app = Flask(__name__, template_folder=str(ressourcen_pfad() / "templates"))
app.config["MAX_CONTENT_LENGTH"] = 20 * 1024 * 1024  # 20 MB, grosszuegig fuer Fotos/gescannte PDFs

# Genau eine laufende Ausfuell-Sitzung gleichzeitig -- passt zum Rest der
# App (ein gemeinsames aktueller_fall.json, keine Mehrbenutzer-Trennung).
# Der Worker-Thread der Sitzung haelt Playwright am Leben, waehrend
# mehrere Flask-Requests (jeweils eigene Threads) nacheinander mit ihm
# kommunizieren -- siehe FuellSitzung-Docstring in fill.py.
_SITZUNG = None


def lade_fall():
    with open(FALL_PFAD, encoding="utf-8") as f:
        return json.load(f)


def speichere_fall(fall):
    with open(FALL_PFAD, "w", encoding="utf-8") as f:
        json.dump(fall, f, ensure_ascii=False, indent=2)


def _set_feld(fall, pfad, neues_feld):
    teile = pfad.split(".")
    node = fall
    for teil in teile[:-1]:
        node = node[teil]
    node[teile[-1]] = neues_feld


def parse_formular_wert(wert_schema, roh_text, aktueller_wert):
    """Wie confirm.py's frage_neuen_wert, aber fuer einen einzelnen
    Formular-Wert statt eine Terminal-Schleife. Leeres Feld = aktuellen
    Wert behalten. Liefert (wert, fehlermeldung_oder_None)."""
    roh_text = (roh_text or "").strip()
    if roh_text == "":
        return aktueller_wert, None

    enum = [w for w in wert_schema.get("enum", []) if w is not None]
    typen = wert_schema.get("type", [])
    if isinstance(typen, str):
        typen = [typen]
    ist_datum = wert_schema.get("format") == "date"

    if enum:
        treffer = [w for w in enum if w == roh_text]
        if treffer:
            return treffer[0], None
        return None, f"Muss exakt einer von {enum} sein."

    if ist_datum:
        try:
            date.fromisoformat(roh_text)
            return roh_text, None
        except ValueError:
            return None, "Format muss JJJJ-MM-TT sein."

    if "boolean" in typen:
        norm = roh_text.lower()
        if norm in ("ja", "j", "true", "1"):
            return True, None
        if norm in ("nein", "n", "false", "0"):
            return False, None
        return None, "Bitte 'ja' oder 'nein' eingeben."

    if "integer" in typen:
        try:
            return int(roh_text), None
        except ValueError:
            return None, "Bitte eine ganze Zahl eingeben."

    if "number" in typen:
        try:
            return float(roh_text), None
        except ValueError:
            return None, "Bitte eine Zahl eingeben."

    return roh_text, None


@app.route("/")
def start():
    if not gemini_key_gesetzt():
        return redirect(url_for("einstellungen", ersteinrichtung=1))
    return render_template("upload.html")


@app.route("/einstellungen", methods=["GET", "POST"])
def einstellungen():
    """Ersetzt fuer eine als .exe gepackte Version die bisherige
    setup.ps1-Terminalabfrage: der Gemini-API-Schluessel wird hier
    eingetippt und direkt neben der .exe in .env gespeichert (siehe
    extract.speichere_gemini_key), sofort wirksam ohne Neustart."""
    gespeichert = False
    if request.method == "POST":
        neuer_key = request.form.get("gemini_key", "").strip()
        if neuer_key:
            speichere_gemini_key(neuer_key)
            gespeichert = True

    return render_template(
        "einstellungen.html",
        key_gesetzt=gemini_key_gesetzt(),
        gespeichert=gespeichert,
        ersteinrichtung=request.args.get("ersteinrichtung") == "1" and not gemini_key_gesetzt(),
    )


@app.route("/hochladen", methods=["POST"])
def hochladen():
    dateien = [d for d in request.files.getlist("dokument") if d and d.filename]
    if not dateien:
        return render_template("upload.html", fehler="Bitte mindestens eine Datei auswaehlen.")

    ziele = []
    for i, datei in enumerate(dateien):
        ziel = UPLOAD_DIR / f"{i}_{datei.filename}"
        datei.save(ziel)
        ziele.append(ziel)

    try:
        rohdaten = extrahiere(ziele)
    except ExtraktionsFehler as e:
        return render_template("upload.html", fehler=str(e))
    except Exception as e:
        return render_template(
            "upload.html",
            fehler=f"Unerwarteter Fehler beim Auslesen: {e}. Bitte nochmal versuchen "
                   "oder ein anderes Foto/PDF probieren.",
        )

    try:
        fall = map_fall(rohdaten)
    except Exception as e:
        return render_template(
            "upload.html",
            fehler=f"Die Erkennung hat eine unerwartete Antwort geliefert und konnte "
                   f"nicht verarbeitet werden ({e}). Bitte nochmal versuchen.",
        )

    speichere_fall(fall)
    return redirect(url_for("pruefen"))


@app.errorhandler(413)
def datei_zu_gross(_e):
    return render_template("upload.html", fehler="Datei ist zu gross (maximal 20 MB). Bitte verkleinern oder ein Foto statt Scan verwenden."), 413


@app.errorhandler(500)
def interner_fehler(_e):
    return render_template("upload.html", fehler="Unerwarteter Fehler. Bitte nochmal versuchen; falls es wiederholt auftritt, das schwarze Fenster im Hintergrund pruefen."), 500


def _baue_pruefen_zeilen(fall, schema, bericht, formular_fehler=None):
    formular_fehler = formular_fehler or {}
    gruende = sammle_gruende(bericht)
    live_klaerbare_felder = DurchblickerPortal.LIVE_KLAERBARE_FELDER
    zeilen = []
    for pfad, feld in sorted(alle_felder(fall)):
        unklar = pfad in gruende
        eintrag = {
            "pfad": pfad,
            "label": label(pfad),
            "wert": feld.get("wert"),
            "quelle": feld.get("quelle") or "",
            "unklar": unklar,
            # live_klaerbar: Feld muss NICHT hier korrigiert werden, sondern
            # wird beim Ausfuellen direkt im Browser abgefragt (siehe
            # portals/durchblicker.py LIVE_KLAERBARE_FELDER). Nur relevant,
            # wenn die Zeile ueberhaupt unklar ist -- ein Schema-/
            # Plausibilitaetsfehler zaehlt NICHT als live klaerbar, auch
            # wenn der Pfad zufaellig in der Liste steht.
            "live_klaerbar": unklar and pfad in live_klaerbare_felder and pfad not in [
                p["pfad"] for p in bericht["plausibilitaet_fehler"]
            ],
            "gruende": gruende.get(pfad, []),
            "formularfehler": formular_fehler.get(pfad),
        }
        if eintrag["unklar"] and not eintrag["live_klaerbar"]:
            wert_schema = resolve_wert_schema(schema, pfad)
            eintrag["enum"] = [w for w in wert_schema.get("enum", []) if w is not None]
            eintrag["ist_datum"] = wert_schema.get("format") == "date"
            eintrag["ist_boolean"] = "boolean" in (
                wert_schema.get("type") if isinstance(wert_schema.get("type"), list) else [wert_schema.get("type")]
            )
        zeilen.append(eintrag)
    return zeilen


@app.route("/pruefen")
def pruefen():
    if not FALL_PFAD.exists():
        return redirect(url_for("start"))

    fall = lade_fall()
    schema = lade_schema()
    bericht = validiere(fall)
    zeilen = _baue_pruefen_zeilen(fall, schema, bericht)

    return render_template("pruefen.html", zeilen=zeilen)


@app.route("/bestaetigen", methods=["POST"])
def bestaetigen():
    fall = lade_fall()
    schema = lade_schema()

    fehler = {}
    for pfad, feld in alle_felder(fall):
        if pfad not in request.form:
            continue
        wert_schema = resolve_wert_schema(schema, pfad)
        neuer_wert, meldung = parse_formular_wert(wert_schema, request.form.get(pfad), feld.get("wert"))
        if meldung:
            fehler[pfad] = meldung
            continue
        _set_feld(fall, pfad, {"wert": neuer_wert, "quelle": feld.get("quelle", ""), "sicher": True})

    speichere_fall(fall)

    if fehler:
        bericht = validiere(fall)
        zeilen = _baue_pruefen_zeilen(fall, schema, bericht, formular_fehler=fehler)
        return render_template("pruefen.html", zeilen=zeilen)

    bericht = validiere(fall)
    if not bereit_zum_ausfuellen(bericht, DurchblickerPortal()):
        return redirect(url_for("pruefen"))

    global _SITZUNG
    _SITZUNG = FuellSitzung()
    status, daten = _SITZUNG.starte(FALL_PFAD)
    return _verarbeite_sitzungsstatus(status, daten)


@app.route("/weiter_automatisieren", methods=["POST"])
def weiter_automatisieren():
    """Wird geklickt, NACHDEM der Nutzer die zuvor angezeigte Auswahl
    (siehe klaerung_manuell.html) direkt im geoeffneten Browserfenster
    von Hand getroffen hat -- setzt genau denselben Ausfuell-Lauf fort,
    OHNE das bereits Ausgefuellte zu wiederholen."""
    if _SITZUNG is None:
        return redirect(url_for("pruefen"))
    status, daten = _SITZUNG.fortsetzen()
    return _verarbeite_sitzungsstatus(status, daten)


def _verarbeite_sitzungsstatus(status, daten):
    if status == "fertig":
        for z in daten:
            z["label"] = label(z["pfad"])
        return render_template("ergebnis.html", zeilen=daten, fehlermeldung=None)

    if status == "klaerung":
        return render_template(
            "klaerung_manuell.html",
            feld_label=label(daten["feldpfad"]),
            optionen=daten["optionen"],
        )

    # status == "fehler"
    return render_template("ergebnis.html", zeilen=[], fehlermeldung=daten)


def _oeffne_browser():
    webbrowser.open("http://127.0.0.1:5000/")


def _stelle_chromium_sicher():
    """Playwright braucht einen heruntergeladenen Chromium-Browser, um
    ueberhaupt etwas ausfuellen zu koennen -- 'playwright install chromium'
    laedt ihn (einmalig, ~150 MB, braucht Internet) in einen
    Nutzer-Cache-Ordner (nicht in dieses Programmverzeichnis). Idempotent:
    ist Chromium schon vorhanden, kehrt der Aufruf sofort zurueck --
    daher bei JEDEM Start unbesorgt aufrufbar, nicht nur beim ersten Mal."""
    import subprocess

    from playwright._impl._driver import compute_driver_executable, get_driver_env

    print("Bereite Playwright vor (beim allerersten Start wird Chromium "
          "heruntergeladen, ~150 MB, braucht Internet -- kann etwas dauern)...")
    driver_executable, driver_cli = compute_driver_executable()
    subprocess.run(
        [driver_executable, driver_cli, "install", "chromium", "--no-shell"],
        env=get_driver_env(), check=True,
    )
    print("Playwright bereit.")


if __name__ == "__main__":
    _stelle_chromium_sicher()
    threading.Timer(1.0, _oeffne_browser).start()
    app.run(debug=False, threaded=True)
