"""
Genauigkeits-Gate vor fill.py. Zeigt im Terminal eine Tabelle:
Feld | erkannter Wert | Zitat aus dem Dokument | Status.

Alles was unsicher (sicher=false), unplausibel (validate.py) oder schema-
ungueltig ist, wird ROT markiert und muss einzeln bestaetigt oder
korrigiert werden. Korrekturen werden sofort zurueck ins fall.json
geschrieben. Erst wenn JEDE Zeile gruen ist, gilt der Fall als bestaetigt.
Kein Flag zum Ueberspringen -- das ist Absicht (siehe Projektauftrag).

Verwendung:
    python confirm.py fall.json
"""

import json
import sys
from datetime import date
from pathlib import Path

from colorama import Fore, Style, init as colorama_init

from validate import alle_felder, lade_schema, validiere

BASE_DIR = Path(__file__).resolve().parent


def _resolve_ref(node, schema):
    if isinstance(node, dict) and "$ref" in node:
        ref = node["$ref"]
        ziel = schema
        for teil in ref.lstrip("#/").split("/"):
            ziel = ziel[teil]
        return ziel
    return node


def _merge_allof(node, schema):
    if not isinstance(node, dict):
        return node
    node = _resolve_ref(node, schema)
    if "allOf" not in node:
        return node
    merged = {}
    for teilschema in node["allOf"]:
        teilschema = _merge_allof(teilschema, schema)
        for key, value in teilschema.items():
            if key == "properties":
                merged.setdefault("properties", {})
                for pk, pv in value.items():
                    bestehend = merged["properties"].get(pk)
                    if isinstance(bestehend, dict) and isinstance(pv, dict):
                        merged["properties"][pk] = {**bestehend, **pv}
                    else:
                        merged["properties"][pk] = pv
            else:
                merged[key] = value
    return merged


def resolve_wert_schema(schema, pfad):
    """Navigiert fall.schema.json entlang eines Punkt-Pfads (z.B.
    'fahrzeug.baujahr') und liefert das (allOf-aufgeloeste) Schema fuer
    'wert' an dieser Stelle -- inkl. type/enum/format, falls vorhanden."""
    node = schema
    for teil in pfad.split("."):
        node = _merge_allof(node, schema)
        props = node.get("properties", {})
        if teil not in props:
            return {}
        node = props[teil]
    node = _merge_allof(node, schema)
    return node.get("properties", {}).get("wert", {})


def _normalisierte_schema_pfade(schema_fehler):
    pfade = set()
    for e in schema_fehler:
        p = e["pfad"]
        if p.endswith(".wert"):
            p = p[: -len(".wert")]
        pfade.add(p)
    return pfade


def sammle_gruende(bericht):
    """pfad -> Liste von Gruenden, warum die Zeile rot ist."""
    gruende = {}
    for eintrag in bericht["klaerungsbedarf"]:
        gruende.setdefault(eintrag["pfad"], []).append(eintrag["grund"])
    for eintrag in bericht["plausibilitaet_fehler"]:
        gruende.setdefault(eintrag["pfad"], []).append(eintrag["grund"])
    for pfad in _normalisierte_schema_pfade(bericht["schema_fehler"]):
        gruende.setdefault(pfad, []).append("Schema-Fehler (siehe validate.py-Bericht)")
    return gruende


def drucke_tabelle(fall, gruende):
    zeilen = sorted(alle_felder(fall), key=lambda kv: kv[0])
    breite_pfad = max(len(p) for p, _ in zeilen) + 1
    print(f"\n{'Feld'.ljust(breite_pfad)}  {'Wert'.ljust(28)}  {'Zitat'.ljust(40)}  Status")
    print("-" * (breite_pfad + 28 + 40 + 20))
    for pfad, feld in zeilen:
        wert = str(feld.get("wert"))[:28]
        quelle = str(feld.get("quelle") or "")[:40]
        if pfad in gruende:
            status = Fore.RED + "ZU KLAEREN" + Style.RESET_ALL
        else:
            status = Fore.GREEN + "OK" + Style.RESET_ALL
        print(f"{pfad.ljust(breite_pfad)}  {wert.ljust(28)}  {quelle.ljust(40)}  {status}")
    print()


def _parse_bool(text):
    norm = text.strip().lower()
    if norm in ("ja", "j", "true", "1"):
        return True
    if norm in ("nein", "n", "false", "0"):
        return False
    return None


def frage_neuen_wert(pfad, wert_schema, aktueller_wert, quelle):
    enum = [w for w in wert_schema.get("enum", []) if w is not None]
    typen = wert_schema.get("type", [])
    if isinstance(typen, str):
        typen = [typen]
    ist_datum = wert_schema.get("format") == "date"

    print(f"\n--- {pfad} ---")
    print(f"  aktueller Wert : {aktueller_wert!r}")
    print(f"  Zitat          : {quelle!r}")
    if enum:
        print(f"  erlaubte Werte : {enum}")
    elif ist_datum:
        print("  Format         : JJJJ-MM-TT")
    elif "boolean" in typen:
        print("  Format         : ja / nein")

    while True:
        eingabe = input(
            "  [Enter]=bestaetigen, oder neuen Wert eingeben "
            "(Format s.o.), 'abbrechen' zum Verlassen: "
        ).strip()

        if eingabe == "":
            return aktueller_wert
        if eingabe.lower() == "abbrechen":
            raise KeyboardInterrupt

        if enum:
            treffer = [w for w in enum if w == eingabe]
            if treffer:
                return treffer[0]
            print(f"  Ungueltig -- muss exakt einer von {enum} sein.")
            continue

        if ist_datum:
            try:
                date.fromisoformat(eingabe)
                return eingabe
            except ValueError:
                print("  Ungueltig -- Format muss JJJJ-MM-TT sein.")
                continue

        if "boolean" in typen:
            b = _parse_bool(eingabe)
            if b is None:
                print("  Ungueltig -- bitte 'ja' oder 'nein' eingeben.")
                continue
            return b

        if "integer" in typen:
            try:
                return int(eingabe)
            except ValueError:
                print("  Ungueltig -- bitte eine ganze Zahl eingeben.")
                continue

        if "number" in typen:
            try:
                return float(eingabe)
            except ValueError:
                print("  Ungueltig -- bitte eine Zahl eingeben.")
                continue

        return eingabe


def klaere_interaktiv(fall, schema, gruende):
    for pfad, feld in sorted(alle_felder(fall)):
        if pfad not in gruende:
            continue
        print(Fore.RED + f"\n>>> Klaerung noetig: {pfad}" + Style.RESET_ALL)
        for grund in gruende[pfad]:
            print(f"    - {grund}")

        wert_schema = resolve_wert_schema(schema, pfad)
        neuer_wert = frage_neuen_wert(pfad, wert_schema, feld.get("wert"), feld.get("quelle"))
        feld["wert"] = neuer_wert
        feld["sicher"] = True


def _set_feld(fall, pfad, neues_feld):
    teile = pfad.split(".")
    node = fall
    for teil in teile[:-1]:
        node = node[teil]
    node[teile[-1]] = neues_feld


def main():
    colorama_init()

    if len(sys.argv) != 2:
        print("Verwendung: python confirm.py <fall.json>", file=sys.stderr)
        sys.exit(2)

    fall_pfad = Path(sys.argv[1])
    with open(fall_pfad, encoding="utf-8") as f:
        fall = json.load(f)

    schema = lade_schema()

    while True:
        bericht = validiere(fall)
        gruende = sammle_gruende(bericht)
        drucke_tabelle(fall, gruende)

        if bericht["ok"]:
            print(Fore.GREEN + "Alle Felder bestaetigt und plausibel. Bereit fuer fill.py." + Style.RESET_ALL)
            sys.exit(0)

        if bericht["schema_fehler"]:
            print(Fore.YELLOW + "Hinweis: Schema-Fehler koennen nach einer Korrektur unten bestehen "
                                 "bleiben, wenn sie nicht in den unten aufgelisteten Feldern liegen "
                                 "(z.B. fehlende Pflichtfelder auf Abschnittsebene)." + Style.RESET_ALL)

        try:
            klaere_interaktiv(fall, schema, gruende)
        except KeyboardInterrupt:
            print("\nAbgebrochen. Aenderungen wurden NICHT gespeichert.")
            sys.exit(1)

        with open(fall_pfad, "w", encoding="utf-8") as f:
            json.dump(fall, f, ensure_ascii=False, indent=2)
        print(f"\nZwischenstand nach {fall_pfad} gespeichert. Pruefe erneut ...")


if __name__ == "__main__":
    main()
