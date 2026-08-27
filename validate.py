"""
Prueft ein fall.json unabhaengig vom urspruenglichen Dokument-Layout:

  1. Schema-Konformitaet gegen fall.schema.json (inkl. aller Pflichtfelder)
  2. Klaerungsbedarf: jedes Feld mit sicher=false
  3. Plausibilitaet einzelner Werte
  4. Querchecks zwischen mehreren Feldern

Nur Pruefungen fuer Felder, die tatsaechlich in fall.schema.json existieren
(siehe feldkarte.md). Der urspruengliche Projektauftrag nannte zusaetzlich
Fuehrerschein-Datum, kW-Plausibilitaet und Jahreskilometer -- diese Felder
gibt es im tatsaechlich erkundeten Wizard nicht (kW wird vom Nationalcode
automatisch aufgeloest und ist kein Eingabefeld), daher werden sie hier NICHT
geprueft. Siehe README/feldkarte.md fuer die Begruendung.

Verwendung:
    python validate.py fall.json
Exit-Code 0 nur wenn schema-konform, keine offenen Klaerungen und keine
Plausibilitaets-/Quercheck-Fehler. Sonst 1.
"""

import json
import re
import sys
from datetime import date
from pathlib import Path

import jsonschema

from paths import ressourcen_pfad

SCHEMA_PATH = ressourcen_pfad() / "fall.schema.json"

PLZ_PATTERN = re.compile(r"^\d{4}$")
MIN_ALTER = 17
MAX_ALTER = 100
MIN_ERSTZULASSUNGSJAHR = 1950


def lade_schema():
    with open(SCHEMA_PATH, encoding="utf-8") as f:
        return json.load(f)


def alle_felder(fall, pfad=""):
    """Liefert (pfad, feld_dict) fuer jedes Blatt-Feld der Form
    {wert, quelle, sicher} im fall-Dict. pfad z.B. 'fahrzeug.nationalcode'."""
    ergebnisse = []
    if not isinstance(fall, dict):
        return ergebnisse
    if {"wert", "quelle", "sicher"} <= fall.keys():
        ergebnisse.append((pfad, fall))
        return ergebnisse
    for key, value in fall.items():
        neuer_pfad = f"{pfad}.{key}" if pfad else key
        ergebnisse.extend(alle_felder(value, neuer_pfad))
    return ergebnisse


def _feld_wert(fall, pfad):
    for p, feld in alle_felder(fall):
        if p == pfad:
            return feld.get("wert")
    return None


def pruefe_schema(fall, schema):
    validator = jsonschema.Draft202012Validator(schema)
    fehler = []
    for e in validator.iter_errors(fall):
        fehler.append({
            "pfad": ".".join(str(p) for p in e.path) or "(wurzel)",
            "meldung": e.message,
        })
    return fehler


def sammle_klaerungsbedarf(fall):
    return [
        {"pfad": pfad, "grund": "sicher=false (Wert unklar/fehlt im Quelldokument)"}
        for pfad, feld in alle_felder(fall)
        if feld.get("sicher") is False
    ]


def _parse_datum(wert):
    if not wert:
        return None
    try:
        return date.fromisoformat(wert)
    except (TypeError, ValueError):
        return None


def pruefe_plausibilitaet(fall):
    probleme = []
    heute = date.today()

    baujahr = _feld_wert(fall, "fahrzeug.baujahr")
    if baujahr is not None:
        if baujahr < MIN_ERSTZULASSUNGSJAHR or baujahr > heute.year:
            probleme.append({
                "pfad": "fahrzeug.baujahr",
                "grund": f"Baujahr {baujahr} liegt ausserhalb {MIN_ERSTZULASSUNGSJAHR}-{heute.year}",
            })

    erstzulassung_pkw = _parse_datum(_feld_wert(fall, "fahrzeug.erstzulassung_pkw"))
    if erstzulassung_pkw is not None:
        if erstzulassung_pkw > heute:
            probleme.append({"pfad": "fahrzeug.erstzulassung_pkw", "grund": "liegt in der Zukunft"})
        elif erstzulassung_pkw.year < MIN_ERSTZULASSUNGSJAHR:
            probleme.append({
                "pfad": "fahrzeug.erstzulassung_pkw",
                "grund": f"liegt vor {MIN_ERSTZULASSUNGSJAHR}",
            })
        if baujahr is not None and erstzulassung_pkw.year not in (baujahr, baujahr + 1):
            probleme.append({
                "pfad": "fahrzeug.erstzulassung_pkw",
                "grund": f"Quercheck: Jahr ({erstzulassung_pkw.year}) passt nicht zum Baujahr ({baujahr}); "
                         f"erwartet {baujahr} oder {baujahr + 1}",
            })

    erstzulassung_auf_sie = _parse_datum(_feld_wert(fall, "fahrzeug.erstzulassung_auf_sie"))
    if erstzulassung_auf_sie is not None:
        if erstzulassung_auf_sie > heute:
            probleme.append({"pfad": "fahrzeug.erstzulassung_auf_sie", "grund": "liegt in der Zukunft"})
        if erstzulassung_pkw is not None and erstzulassung_auf_sie < erstzulassung_pkw:
            probleme.append({
                "pfad": "fahrzeug.erstzulassung_auf_sie",
                "grund": "liegt vor 'Erstzulassung des PKW' -- das Formular selbst weist das zurueck "
                         "(live verifiziert in Phase 1, siehe feldkarte.md)",
            })

    geburtsdatum = _parse_datum(_feld_wert(fall, "versicherungsnehmer.geburtsdatum"))
    if geburtsdatum is not None:
        alter = heute.year - geburtsdatum.year - (
            (heute.month, heute.day) < (geburtsdatum.month, geburtsdatum.day)
        )
        if not (MIN_ALTER <= alter <= MAX_ALTER):
            probleme.append({
                "pfad": "versicherungsnehmer.geburtsdatum",
                "grund": f"errechnetes Alter {alter} liegt ausserhalb {MIN_ALTER}-{MAX_ALTER}",
            })

    plz = _feld_wert(fall, "versicherungsnehmer.plz")
    if plz is not None and not PLZ_PATTERN.match(str(plz)):
        probleme.append({"pfad": "versicherungsnehmer.plz", "grund": "keine 4-stellige oesterreichische PLZ"})

    nationalcode = _feld_wert(fall, "fahrzeug.nationalcode")
    if nationalcode is not None and not re.match(r"^[A-Za-z0-9]{3,10}$", str(nationalcode)):
        probleme.append({
            "pfad": "fahrzeug.nationalcode",
            "grund": "unerwartetes Format (weiches Warn-Kriterium -- bisher nur ein Beispiel "
                     "'260094' live verifiziert, siehe TODO in feldkarte.md, ggf. Falsch-Positiv)",
        })

    return probleme


def validiere(fall):
    schema = lade_schema()
    schema_fehler = pruefe_schema(fall, schema)
    klaerungsbedarf = sammle_klaerungsbedarf(fall)
    plausibilitaet_fehler = pruefe_plausibilitaet(fall)

    ok = not schema_fehler and not klaerungsbedarf and not plausibilitaet_fehler
    return {
        "ok": ok,
        "schema_fehler": schema_fehler,
        "klaerungsbedarf": klaerungsbedarf,
        "plausibilitaet_fehler": plausibilitaet_fehler,
    }


def main():
    if len(sys.argv) != 2:
        print("Verwendung: python validate.py <fall.json>", file=sys.stderr)
        sys.exit(2)

    pfad = Path(sys.argv[1])
    with open(pfad, encoding="utf-8") as f:
        fall = json.load(f)

    bericht = validiere(fall)
    print(json.dumps(bericht, ensure_ascii=False, indent=2))
    sys.exit(0 if bericht["ok"] else 1)


if __name__ == "__main__":
    main()
