"""
Lesbare deutsche Bezeichnungen fuer die internen Feldpfade (z.B.
"versicherungsnehmer.zweitwagen" -> "Zweitwagen im Haushalt"). Wird von
confirm.py, fill.py und app.py/templates gemeinsam genutzt, damit in
Terminal-Tabellen, Web-Formular und Ergebnis-Ansicht ueberall dieselbe,
verstaendliche Beschriftung erscheint statt des rohen Programm-Pfads.
"""

FELD_LABELS = {
    "fahrzeug.baujahr": "Baujahr",
    "fahrzeug.identifikationsmethode": "Art der Fahrzeug-Identifikation",
    "fahrzeug.nationalcode": "Nationaler Zulassungscode",
    "fahrzeug.marke": "Marke",
    "fahrzeug.modell": "Modell",
    "fahrzeug.variante": "Variante",
    "fahrzeug.sonderausstattung_wert": "Wert der Sonderausstattung",
    "fahrzeug.zugelassen": "Bereits zugelassen",
    "fahrzeug.erstbesitzer": "Erstbesitzer",
    "fahrzeug.erstzulassung_pkw": "Erstzulassung des Fahrzeugs",
    "fahrzeug.erstzulassung_auf_sie": "Zulassung auf den Halter",
    "fahrzeug.finanzierung": "Finanzierung",
    "versicherungsnehmer.bonus_malus_stufe": "Bonus-Malus-Stufe",
    "versicherungsnehmer.bestehende_versicherung": "Bestehende Versicherung",
    "versicherungsnehmer.nationalitaet": "Nationalität",
    "versicherungsnehmer.zweitwagen": "Zweitwagen im Haushalt",
    "versicherungsnehmer.anmeldung_als": "Anmeldung als",
    "versicherungsnehmer.geburtsdatum": "Geburtsdatum",
    "versicherungsnehmer.plz": "Postleitzahl",
    "versicherungsnehmer.email": "E-Mail-Adresse",
    "produkt.kasko_zusatzdeckung": "Kasko-Zusatzdeckung gewünscht",
    "produkt.kaskovariante": "Kaskovariante",
    "produkt.versicherungsschutz_praeferenz": "Gewünschter Versicherungsschutz",
}


def label(pfad):
    """Liefert die lesbare Bezeichnung fuer einen Feldpfad, oder den Pfad
    selbst als Fallback, falls er (noch) nicht in FELD_LABELS eingetragen
    ist -- damit ein neues Feld nie unsichtbar wird, nur unuebersetzt."""
    if pfad in FELD_LABELS:
        return FELD_LABELS[pfad]
    # Synthetische Verifikations-Pfade wie "fahrzeug.nationalcode
    # (Fahrzeug erkannt)" -- Basis-Pfad uebersetzen, Zusatz beibehalten.
    basis, _, zusatz = pfad.partition(" (")
    if basis in FELD_LABELS and zusatz:
        return f"{FELD_LABELS[basis]} ({zusatz}"
    return pfad
