"""
Automatische Dokumentenerkennung ueber die Google Gemini API (kostenloses
Kontingent, kein Zahlungsmittel noetig -- siehe README.md "Setup" fuer die
Einrichtung von GEMINI_API_KEY).

Ersetzt fuer die Web-Oberflaeche (app.py) den manuellen claude.ai-Chat-Weg
aus ANLEITUNG.md/extraktion_anfrage.txt durch einen direkten API-Aufruf.
Der manuelle Weg bleibt als Fallback bestehen (falls kein API-Key
eingerichtet ist, oder als Kontrolle bei einem besonders sensiblen Fall).

Liefert Rohdaten in derselben Struktur wie extraktion_anfrage.txt verlangt
-- direkt kompatibel mit mapping.map_fall().
"""

import json
import mimetypes
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.6-flash")

EXTRAKTIONS_PROMPT = """\
Lies das angehängte Dokument (Zulassungsschein, Versicherungsangebot,
Kundenformular o.ä.) und extrahiere daraus die Daten für eine
KFZ-Versicherung. Gib NUR ein einziges JSON-Objekt zurück, exakt in
dieser Struktur:

{
  "fahrzeug": {
    "baujahr": {"wert": <Jahr als Zahl oder null>, "quelle": "<woertliches Zitat>", "sicher": true/false},
    "nationalcode": {"wert": "<Feld A7 'Nationaler Code' aus dem Zulassungsschein, sonst null>", "quelle": "...", "sicher": true/false},
    "marke": {"wert": "<Automarke oder null, nur falls kein Nationalcode vorhanden>", "quelle": "...", "sicher": true/false},
    "modell": {"wert": "<Modell oder null, nur falls kein Nationalcode vorhanden>", "quelle": "...", "sicher": true/false},
    "variante": {"wert": null, "quelle": "", "sicher": true},
    "sonderausstattung_wert": {"wert": <Euro-Betrag als Zahl oder null>, "quelle": "...", "sicher": true/false},
    "zugelassen": {"wert": "Ja" oder "Nein", "quelle": "...", "sicher": true/false},
    "erstbesitzer": {"wert": "Ja" oder "Nein" (Ja = fabriksneu gekauft), "quelle": "...", "sicher": true/false},
    "erstzulassung_pkw": {"wert": "<Datum als JJJJ-MM-TT oder null>", "quelle": "...", "sicher": true/false},
    "erstzulassung_auf_sie": {"wert": "<Datum als JJJJ-MM-TT, wann auf den Kunden zugelassen, oder null>", "quelle": "...", "sicher": true/false},
    "finanzierung": {"wert": "Nein" / "Leasing" / "Kredit", "quelle": "...", "sicher": true/false}
  },
  "versicherungsnehmer": {
    "bonus_malus_stufe": {"wert": "<Bonus-Malus-Stufe, sonst null>", "quelle": "...", "sicher": true/false},
    "bestehende_versicherung": {"wert": "<Versicherer, 'keine', oder null>", "quelle": "...", "sicher": true/false},
    "nationalitaet": {"wert": "<Staatsangehoerigkeit, meist 'Österreich'>", "quelle": "...", "sicher": true/false},
    "zweitwagen": {"wert": "Ja" oder "Nein", "quelle": "...", "sicher": true/false},
    "anmeldung_als": {"wert": "Privat" oder "Firma", "quelle": "...", "sicher": true/false},
    "geburtsdatum": {"wert": "<Datum als JJJJ-MM-TT oder null>", "quelle": "...", "sicher": true/false},
    "plz": {"wert": "<4-stellige Postleitzahl oder null>", "quelle": "...", "sicher": true/false},
    "email": {"wert": "<E-Mail-Adresse oder null>", "quelle": "...", "sicher": true/false}
  },
  "produkt": {
    "kasko_zusatzdeckung": {"wert": "Ja" oder "Nein", "quelle": "...", "sicher": true/false},
    "kaskovariante": {"wert": "Vollkasko" / "Teilkasko" / null, "quelle": "...", "sicher": true/false},
    "versicherungsschutz_praeferenz": {"wert": "Empfehlung", "quelle": "", "sicher": true}
  }
}

WICHTIGE REGELN:
- "Deckungsumfang" / "gewuenschter Versicherungsschutz" im Dokument richtig
  interpretieren: steht dort "Haftpflicht und Teilkasko" oder "Haftpflicht
  und Vollkasko" (oder nur "Teilkasko"/"Vollkasko"), dann IMMER
  kasko_zusatzdeckung = "Ja" UND kaskovariante = "Teilkasko" bzw.
  "Vollkasko" setzen -- Teilkasko UND Vollkasko sind beides Kasko-Varianten,
  nicht "nur Haftpflicht". Nur wenn ausschliesslich "Haftpflicht" (ohne
  jede Kasko-Erwaehnung) angegeben ist, gilt kasko_zusatzdeckung = "Nein".
- "quelle" ist immer das woertliche Zitat aus dem Dokument. Steht ein Wert
  nicht direkt im Dokument, schreib eine kurze Begruendung hinein.
- "sicher" ist true NUR wenn du dir wirklich sicher bist. Bei unleserlichen,
  mehrdeutigen oder fehlenden Angaben: "sicher": false und "wert": null.
  RATE NIEMALS einen Wert -- ein falscher Wert in einer
  Versicherungsberechnung ist schlimmer als ein leeres Feld, das später
  nachgetragen wird.
- Datumsangaben immer im Format JJJJ-MM-TT. Oesterreichische/deutsche
  Dokumente schreiben Datum als TT.MM.JJJJ (Tag zuerst) -- NICHT als
  US-Format MM/TT/JJJJ verwechseln.
- Nationalcode (Feld A7): besonders sorgfaeltig lesen, da dieser Wert das
  Fahrzeug eindeutig bestimmt und ein einziges falsch gelesenes Zeichen zum
  falschen Auto fuehrt. Bei Verwechslungsgefahr (0/O, 1/I/l, 5/S, 8/B) im
  Zweifel "sicher": false setzen statt zu raten.
- "erstbesitzer" (Ja = fabriksneu/Erstbesitzer): Formulierungen wie "Anzahl
  bisheriger Halter: 1" sind MEHRDEUTIG (koennte "ich bin Halter Nr. 1" ODER
  "es gab 1 Halter vor mir" bedeuten) -- in diesem Fall IMMER
  "sicher": false setzen, nie interpretieren.
- Bevor du antwortest: geh das Dokument noch einmal komplett durch und
  vergleiche jeden extrahierten Wert mit der Originalstelle, bevor du die
  finale Antwort gibst.
"""


class ExtraktionsFehler(Exception):
    pass


def extrahiere(dateipfad):
    """Schickt ein Dokument (Bild oder PDF) an Gemini und liefert die
    extrahierten Rohdaten als dict (Struktur wie oben). Wirft
    ExtraktionsFehler mit Klartext-Meldung bei fehlendem API-Key oder
    einer Antwort, die kein gueltiges JSON ist -- rate niemals selbst,
    wenn die KI keine brauchbare Antwort liefert."""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ExtraktionsFehler(
            "GEMINI_API_KEY ist nicht in .env gesetzt. Kostenlosen Schluessel "
            "unter https://aistudio.google.com/apikey holen und in .env eintragen, "
            "oder den manuellen Weg ueber claude.ai nutzen (siehe ANLEITUNG.md)."
        )

    from google import genai
    from google.genai import types

    dateipfad = Path(dateipfad)
    mime_type, _ = mimetypes.guess_type(str(dateipfad))
    if not mime_type:
        raise ExtraktionsFehler(f"Dateityp von {dateipfad.name} nicht erkannt (erwartet Bild oder PDF).")

    client = genai.Client(api_key=api_key)
    dokument_bytes = dateipfad.read_bytes()

    try:
        antwort = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=[
                EXTRAKTIONS_PROMPT,
                types.Part.from_bytes(data=dokument_bytes, mime_type=mime_type),
            ],
            config=types.GenerateContentConfig(response_mime_type="application/json"),
        )
    except Exception as e:
        raise ExtraktionsFehler(f"Gemini-Anfrage fehlgeschlagen: {e}") from e

    text = (antwort.text or "").strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        raise ExtraktionsFehler(
            f"Gemini hat kein gueltiges JSON zurueckgegeben ({e}). Antwort: {text[:500]}"
        ) from e
