"""
Uebersetzt Freitext-Rohwerte (wie sie aus einem Kundendokument extrahiert
wurden) in die exakten Dropdown-/Radio-Optionstexte, die der durchblicker.at
KFZ-Rechner erwartet (siehe feldkarte.md). Die Synonymtabelle liegt in
synonyme.json und ist ohne Codeaenderung erweiterbar.

Eingabe: ein Rohdaten-Dict in der Struktur von fall.json, bei dem die
enum-/boolean-wertigen Felder noch den ROHEN Dokumenttext in "wert" tragen
(z.B. "VB" oder "Bar" statt "Nein"). Ausgabe: ein Dict in derselben Struktur,
bei dem diese Felder auf den exakten Zielwert normalisiert sind.

Felder ohne festen Optionskatalog (Datum, PLZ, E-Mail, Nationalcode,
Marke/Modell/Variante, Baujahr, Sonderausstattung) werden NICHT hier
verarbeitet -- die sind entweder direkt uebernehmbar oder Aufgabe von
validate.py (Plausibilitaet).

Unbekannter Wert = sicher wird auf false gesetzt, wert auf None. Es wird
NIE der aehnlichste bekannte Wert geraten (siehe WICHTIGSTE REGEL im
Projektauftrag).
"""

import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
SYNONYME_PATH = BASE_DIR / "synonyme.json"

# Vollstaendige, live gegen durchblicker.at verifizierte Optionslisten
# (siehe feldkarte.md). NUR fuer Felder mit bekannter Vollstaendigkeit --
# bestehende_versicherung und nationalitaet fehlen hier bewusst (TODO #1
# in feldkarte.md: Liste noch nicht vollstaendig erfasst).
ERLAUBTE_WERTE = {
    "finanzierung": ["Nein", "Leasing", "Kredit"],
    "anmeldung_als": ["Privatperson", "Einzelunternehmen"],
    "versicherungsschutz_praeferenz": [
        "durchblicker Empfehlung", "Günstiger Preis", "Deckungen selbst festlegen",
    ],
    "bonus_malus_stufe": ["0", "1", "2", "3", "4", "5", "6", "7", "8", "9 - Einsteigerstufe"],
    "kaskovariante": ["Vollkasko", "Teilkasko"],
    "bauart": [
        "Limousine/Sedan", "Kombi - PKW", "SUV", "Coupé", "Cabrio/Cabriolet",
        "MPV", "Kombi Transporter", "Bus",
    ],
}

# Felder mit vollstaendig bekanntem Katalog (ERLAUBTE_WERTE greift als
# zusaetzlicher exakter Fallback zur Synonymtabelle).
ENUM_FELDER = set(ERLAUBTE_WERTE.keys())

# Felder mit NUR TEILWEISE bekanntem Katalog: ausschliesslich ueber
# synonyme.json aufloesbar, kein Fallback-Enum (sonst wuerden unbekannte
# Versicherer/Nationalitaeten faelschlich als "sicher" durchgehen).
FREITEXT_FELDER_MIT_SYNONYMEN = {"bestehende_versicherung", "nationalitaet"}

BOOLEAN_FELDER = {"zugelassen", "erstbesitzer", "zweitwagen", "kasko_zusatzdeckung", "firmenbucheintrag"}

FAHRZEUG_FELDER = {"finanzierung", "zugelassen", "erstbesitzer", "bauart"}
VERSICHERUNGSNEHMER_FELDER = {
    "bonus_malus_stufe", "bestehende_versicherung", "nationalitaet", "zweitwagen",
    "anmeldung_als", "firmenbucheintrag",
}
PRODUKT_FELDER = {"versicherungsschutz_praeferenz", "kasko_zusatzdeckung", "kaskovariante"}


def _normalisieren(text):
    return text.strip().lower() if isinstance(text, str) else text


def lade_synonyme():
    with open(SYNONYME_PATH, encoding="utf-8") as f:
        return json.load(f)


def map_boolean(rohtext, synonyme):
    if not isinstance(rohtext, str) or not rohtext.strip():
        return None, False
    norm = _normalisieren(rohtext)
    ja_nein = synonyme.get("ja_nein", {})
    if norm in ja_nein.get("ja_werte", []):
        return True, True
    if norm in ja_nein.get("nein_werte", []):
        return False, True
    return None, False


def map_enum(feldname, rohtext, synonyme):
    if not isinstance(rohtext, str) or not rohtext.strip():
        return None, False
    norm = _normalisieren(rohtext)

    # Fuehrende Nullen normalisieren (z.B. "04" -> "4"), aber nur bei rein
    # numerischem Text -- verhindert, dass z.B. "04" mangels Treffer als
    # unsicher durchfaellt, obwohl es eindeutig "4" meint.
    kandidaten = [norm]
    if norm.isdigit() and str(int(norm)) != norm:
        kandidaten.append(str(int(norm)))

    tabelle = synonyme.get(feldname, {})
    for kandidat in kandidaten:
        if kandidat in tabelle:
            return tabelle[kandidat], True

    if feldname in ENUM_FELDER:
        for erlaubt in ERLAUBTE_WERTE[feldname]:
            if _normalisieren(erlaubt) in kandidaten:
                return erlaubt, True

    # kein Treffer -- weder Synonym noch (falls vorhanden) exakter Katalogwert
    return None, False


def map_feld(feldname, rohtext, synonyme):
    if feldname in BOOLEAN_FELDER:
        return map_boolean(rohtext, synonyme)
    if feldname in ENUM_FELDER or feldname in FREITEXT_FELDER_MIT_SYNONYMEN:
        return map_enum(feldname, rohtext, synonyme)
    raise ValueError(f"Feld '{feldname}' hat keinen bekannten Optionskatalog -- "
                      f"gehoert nicht zu mapping.py (siehe validate.py fuer Freitext-/Formatpruefungen).")


def _mappe_abschnitt(abschnitt, feldnamen, synonyme):
    ergebnis = {}
    for feldname, feld in abschnitt.items():
        if feldname not in feldnamen or not isinstance(feld, dict):
            ergebnis[feldname] = feld
            continue

        roh_wert = feld.get("wert")
        # Bereits vorher als unsicher/leer markierte Felder werden nicht
        # neu geraten -- sie bleiben unsicher, bis ein Mensch sie klaert.
        if feld.get("sicher") is False or roh_wert in (None, ""):
            ergebnis[feldname] = {"wert": None, "quelle": feld.get("quelle", ""), "sicher": False}
            continue

        neuer_wert, sicher = map_feld(feldname, roh_wert, synonyme)
        ergebnis[feldname] = {
            "wert": neuer_wert,
            "quelle": feld.get("quelle", roh_wert),
            "sicher": sicher,
        }
    return ergebnis


def bestimme_identifikationsmethode(fahrzeug_rohdaten):
    """Nationalcode ist der bevorzugte, deterministische Weg (siehe
    feldkarte.md) -- wird verwendet sobald ein Nationalcode extrahiert
    wurde. Marke/Modell nur als Fallback, wenn kein Code vorliegt."""
    nationalcode = fahrzeug_rohdaten.get("nationalcode", {})
    if nationalcode.get("sicher") and nationalcode.get("wert"):
        return {"wert": "nationalcode", "quelle": "", "sicher": True}

    marke = fahrzeug_rohdaten.get("marke", {})
    modell = fahrzeug_rohdaten.get("modell", {})
    if marke.get("sicher") and marke.get("wert") and modell.get("sicher") and modell.get("wert"):
        return {"wert": "marke_modell", "quelle": "", "sicher": True}

    return {"wert": None, "quelle": "", "sicher": False}


# Nur eines der beiden Identifikations-Feldsets ist pro Fall jemals
# relevant (siehe bestimme_identifikationsmethode) -- das jeweils andere
# ist bewusst kein Klaerungsbedarf, auch wenn es leer/unsicher ist.
NATIONALCODE_FELDER = {"nationalcode"}
MARKE_MODELL_FELDER = {"marke", "modell", "treibstoff", "motorleistung_kw", "bauart", "tueren", "variante"}


def _bereinige_identifikationsfelder(fahrzeug):
    methode = fahrzeug.get("identifikationsmethode", {}).get("wert")
    if methode == "nationalcode":
        irrelevant, grund = MARKE_MODELL_FELDER, "nicht relevant, da Fahrzeug ueber Nationalcode identifiziert"
    elif methode == "marke_modell":
        irrelevant, grund = NATIONALCODE_FELDER, "nicht relevant, da Fahrzeug ueber Marke/Modell identifiziert"
    else:
        return  # Identifikationsmethode selbst noch unklar -- nichts bereinigen

    for feldname in irrelevant:
        feld = fahrzeug.get(feldname, {})
        if feld.get("sicher") is False and feld.get("wert") in (None, ""):
            fahrzeug[feldname] = {"wert": None, "quelle": grund, "sicher": True}


# Felder, bei denen eine fehlende Angabe im Dokument NICHT zur Klaerung
# vorgelegt werden muss, weil entweder (a) der durchblicker.at-Rechner
# selbst schon einen Standardwert vorbelegt (Bonus/Malus-Stufe,
# Sonderausstattung-Slider) oder (b) die sicherste/am wenigsten
# unterstellende Annahme eindeutig ist (keine ungefragte Zusatzdeckung,
# oesterreichisches Portal). Das ist KEIN Raten von Dokumentinhalt --
# es wird nur davon abgesehen, einen ohnehin vorhandenen Formular-Default
# ohne Not zu ueberschreiben oder eine Ablehnung zu unterstellen.
#
# Bewusst NICHT in dieser Liste: alles, was die Versicherung inhaltlich
# veraendert und keinen harmlosen Formular-Default hat (Geburtsdatum, PLZ,
# E-Mail, Nationalcode, Zulassungsdaten (ausser der Ableitung unten),
# bestehende Versicherung, Zweitwagen, Kaskovariante bei aktiver
# Kaskodeckung, ob das Fahrzeug ueberhaupt schon zugelassen ist) -- dort
# bleibt jede Unklarheit weiterhin klaerungsbeduerftig, weil es entweder
# eine Pflichtfrage ohne Formular-Default ist oder eine reine
# Kundenauskunft, die auf keinem Fahrzeugdokument steht.
def _wende_formular_standards_an(fahrzeug, versicherungsnehmer, produkt):
    def ist_offen(feld):
        return feld.get("sicher") is False and feld.get("wert") in (None, "")

    if ist_offen(versicherungsnehmer.get("bonus_malus_stufe", {})):
        versicherungsnehmer["bonus_malus_stufe"] = {
            "wert": "9 - Einsteigerstufe",
            "quelle": "nicht im Dokument angegeben -- Formular-Standard fuer Neueinsteiger uebernommen",
            "sicher": True,
        }

    if ist_offen(fahrzeug.get("sonderausstattung_wert", {})):
        fahrzeug["sonderausstattung_wert"] = {
            "wert": None,
            "quelle": "nicht im Dokument angegeben -- Slider-Standard des Formulars bleibt unveraendert",
            "sicher": True,
        }

    if ist_offen(produkt.get("kasko_zusatzdeckung", {})):
        produkt["kasko_zusatzdeckung"] = {
            "wert": False,
            "quelle": "nicht im Dokument angegeben -- Standard: nur Haftpflicht, keine ungefragte Zusatzdeckung",
            "sicher": True,
        }

    if ist_offen(versicherungsnehmer.get("nationalitaet", {})):
        versicherungsnehmer["nationalitaet"] = {
            "wert": "Österreich",
            "quelle": "nicht im Dokument angegeben -- Formular-Standard (österreichisches Portal) uebernommen",
            "sicher": True,
        }

    if ist_offen(fahrzeug.get("finanzierung", {})):
        fahrzeug["finanzierung"] = {
            "wert": "Nein",
            "quelle": "nicht im Dokument angegeben -- Standard: keine Leasing-/Kreditfinanzierung unterstellt",
            "sicher": True,
        }


def _leite_erstbesitzer_ab(fahrzeug):
    """'Erstbesitzer' ist keine Vermutung, sondern eine Ableitung aus zwei
    bereits vorhandenen Datumsangaben: sind 'Erstzulassung des PKW' und
    'Zulassung auf den Halter' identisch, ist der Halter zwangslaeufig der
    Erstbesitzer -- sind sie unterschiedlich, zwangslaeufig nicht. Nur
    anwendbar, wenn BEIDE Daten sicher vorliegen; fehlt eines, bleibt das
    Feld unveraendert (weiterhin klaerungsbeduerftig)."""
    erstbesitzer = fahrzeug.get("erstbesitzer", {})
    if not (erstbesitzer.get("sicher") is False and erstbesitzer.get("wert") is None):
        return

    erstzulassung_pkw = fahrzeug.get("erstzulassung_pkw", {})
    erstzulassung_auf_sie = fahrzeug.get("erstzulassung_auf_sie", {})
    if not (erstzulassung_pkw.get("sicher") and erstzulassung_auf_sie.get("sicher")):
        return
    if not (erstzulassung_pkw.get("wert") and erstzulassung_auf_sie.get("wert")):
        return

    ist_erstbesitzer = erstzulassung_pkw["wert"] == erstzulassung_auf_sie["wert"]
    fahrzeug["erstbesitzer"] = {
        "wert": ist_erstbesitzer,
        "quelle": (
            f"abgeleitet: Erstzulassung PKW ({erstzulassung_pkw['wert']}) "
            f"{'=' if ist_erstbesitzer else '!='} Zulassung auf Halter ({erstzulassung_auf_sie['wert']})"
        ),
        "sicher": True,
    }


def _bereinige_erstzulassung_auf_sie(fahrzeug):
    """Ist der Halter Erstbesitzer, verlangt das Formular gar kein
    eigenes 'Erstzulassung auf Sie'-Feld -- es ist per Definition
    identisch mit 'Erstzulassung des PKW' (live verifiziert 2026-08-25,
    siehe portals/durchblicker.py). Ein noch offenes
    erstzulassung_auf_sie ist in diesem Fall kein Klaerungsbedarf mehr,
    sondern schlicht nicht anwendbar."""
    if fahrzeug.get("erstbesitzer", {}).get("wert") is not True:
        return
    feld = fahrzeug.get("erstzulassung_auf_sie", {})
    if feld.get("sicher") is False and feld.get("wert") in (None, ""):
        fahrzeug["erstzulassung_auf_sie"] = {
            "wert": None,
            "quelle": "nicht relevant, da Erstbesitzer (identisch mit Erstzulassung des PKW)",
            "sicher": True,
        }


def map_fall(rohdaten):
    synonyme = lade_synonyme()

    fahrzeug = _mappe_abschnitt(rohdaten.get("fahrzeug", {}), FAHRZEUG_FELDER, synonyme)
    fahrzeug["identifikationsmethode"] = bestimme_identifikationsmethode(rohdaten.get("fahrzeug", {}))
    _bereinige_identifikationsfelder(fahrzeug)
    _leite_erstbesitzer_ab(fahrzeug)
    _bereinige_erstzulassung_auf_sie(fahrzeug)

    versicherungsnehmer = _mappe_abschnitt(
        rohdaten.get("versicherungsnehmer", {}), VERSICHERUNGSNEHMER_FELDER, synonyme
    )
    if versicherungsnehmer.get("anmeldung_als", {}).get("wert") != "Einzelunternehmen":
        # firmenbucheintrag erscheint am Formular nur, wenn als
        # Einzelunternehmen angemeldet wird -- sonst ist ein offener Wert
        # nicht anwendbar statt klaerungsbeduerftig.
        versicherungsnehmer["firmenbucheintrag"] = {
            "wert": None,
            "quelle": "nicht relevant, da Anmeldung als Privatperson",
            "sicher": True,
        }

    produkt = _mappe_abschnitt(rohdaten.get("produkt", {}), PRODUKT_FELDER, synonyme)

    _wende_formular_standards_an(fahrzeug, versicherungsnehmer, produkt)

    if produkt.get("kasko_zusatzdeckung", {}).get("wert") is False:
        # kaskovariante ist nur relevant, wenn Kasko am Ende aktiv ist (siehe
        # portals/durchblicker.py). Ist Kasko klar abgelehnt, ist ein leerer
        # Wert hier kein Klaerungsbedarf, sondern schlicht nicht anwendbar --
        # sonst wuerde confirm.py unnoetig danach fragen.
        produkt["kaskovariante"] = {
            "wert": None,
            "quelle": "nicht relevant, da keine Kasko-Zusatzdeckung gewuenscht",
            "sicher": True,
        }

    return {
        "fahrzeug": fahrzeug,
        "versicherungsnehmer": versicherungsnehmer,
        "produkt": produkt,
    }


def main():
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="Rohdaten in fall.json-Zielwerte uebersetzen")
    parser.add_argument("eingabe", help="Pfad zu einer Rohdaten-JSON-Datei (Struktur wie fall.json)")
    parser.add_argument("-o", "--ausgabe", help="Zieldatei (Default: stdout)")
    args = parser.parse_args()

    with open(args.eingabe, encoding="utf-8") as f:
        rohdaten = json.load(f)

    ergebnis = map_fall(rohdaten)
    text = json.dumps(ergebnis, ensure_ascii=False, indent=2)

    if args.ausgabe:
        Path(args.ausgabe).write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text + "\n")


if __name__ == "__main__":
    main()
