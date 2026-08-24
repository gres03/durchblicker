#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if [ ! -d ".venv" ]; then
    python3 -m venv .venv
fi

if [ -f ".venv/bin/activate" ]; then
    source .venv/bin/activate
else
    source .venv/Scripts/activate
fi

pip install --upgrade pip
pip install -r requirements.txt
playwright install chromium

if [ ! -f ".env" ]; then
    echo ""
    echo "Zugangsdaten fuer durchblicker.at (werden nur lokal in .env gespeichert, nie committed):"
    read -r -p "  E-Mail: " BENUTZER
    read -r -s -p "  Passwort: " PASSWORT
    echo ""

    echo ""
    echo "Optional: Gemini-API-Schluessel fuer die automatische Dokumentenerkennung"
    echo "in der Web-Oberflaeche (webapp_starten.sh). Kostenloses Kontingent, kein"
    echo "Zahlungsmittel noetig -- siehe https://aistudio.google.com/apikey"
    echo "Leer lassen und Enter druecken, um das jetzt zu ueberspringen (kann"
    echo "spaeter jederzeit in .env nachgetragen werden -- dann funktioniert nur"
    echo "der manuelle claude.ai-Weg aus ANLEITUNG.md, nicht die Web-Oberflaeche)."
    read -r -p "  Gemini-API-Schluessel (optional): " GEMINI_KEY

    cat > .env <<EOF
DURCHBLICKER_URL=https://durchblicker.at/
DURCHBLICKER_USER=${BENUTZER}
DURCHBLICKER_PASS=${PASSWORT}
GEMINI_API_KEY=${GEMINI_KEY}
EOF

    echo ".env angelegt."
else
    echo ".env existiert bereits, wird nicht ueberschrieben."
fi

echo ""
echo "Setup abgeschlossen. Aktivieren mit: source .venv/bin/activate"
echo "Web-Oberflaeche starten mit: ./webapp_starten.sh"
echo "Login testen mit: python login.py"
