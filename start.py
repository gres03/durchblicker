"""
Ein Befehl fuer den kompletten Ablauf: Rohdaten (aus claude.ai, siehe
extraktion_anfrage.txt) -> Uebersetzung in exakte Formularwerte ->
Bestaetigung (fragt NUR nach, wenn etwas unsicher/unplausibel ist) ->
Ausfuellen + Pflicht-Verifikation. Ist der Fall von Anfang an sauber,
laeuft das komplett automatisch durch, ohne dass irgendetwas eingetippt
werden muss.

Verwendung:
    python start.py rohdaten.json

(Unter Windows auch per Drag & Drop einer .json-Datei auf
Fall_starten.bat moeglich, siehe ANLEITUNG.md.)
"""

import json
import sys
from pathlib import Path

from colorama import Fore, Style, init as colorama_init

from confirm import bestaetige_fall
from fill import fuelle_aus
from mapping import map_fall


def main():
    colorama_init()

    if len(sys.argv) != 2:
        print("Verwendung: python start.py <rohdaten.json>", file=sys.stderr)
        sys.exit(2)

    eingabe_pfad = Path(sys.argv[1])
    if not eingabe_pfad.exists():
        print(Fore.RED + f"FEHLER: Datei nicht gefunden: {eingabe_pfad}" + Style.RESET_ALL, file=sys.stderr)
        sys.exit(1)

    try:
        with open(eingabe_pfad, encoding="utf-8") as f:
            rohdaten = json.load(f)
    except json.JSONDecodeError as e:
        print(Fore.RED + f"FEHLER: {eingabe_pfad} ist kein gueltiges JSON ({e}). "
                          "Bitte sicherstellen, dass die Datei NUR den Textblock von "
                          "'{' bis '}' aus der Claude-Antwort enthaelt, sonst nichts." + Style.RESET_ALL,
              file=sys.stderr)
        sys.exit(1)

    fall = map_fall(rohdaten)
    fall_pfad = eingabe_pfad.with_name(eingabe_pfad.stem + "_fall.json")
    with open(fall_pfad, "w", encoding="utf-8") as f:
        json.dump(fall, f, ensure_ascii=False, indent=2)

    print(Fore.CYAN + f"1/3 Rohdaten uebersetzt -> {fall_pfad}" + Style.RESET_ALL)
    print(Fore.CYAN + "2/3 Pruefe Vollstaendigkeit und Plausibilitaet ..." + Style.RESET_ALL)

    if not bestaetige_fall(fall_pfad):
        sys.exit(1)

    print(Fore.CYAN + "3/3 Fuelle den KFZ-Rechner aus ..." + Style.RESET_ALL)
    sys.exit(fuelle_aus(fall_pfad))


if __name__ == "__main__":
    main()
