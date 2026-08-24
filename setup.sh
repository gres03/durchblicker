#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

python3 -m venv .venv

if [ -f ".venv/bin/activate" ]; then
    source .venv/bin/activate
else
    source .venv/Scripts/activate
fi

pip install --upgrade pip
pip install -r requirements.txt
playwright install chromium

if [ ! -f ".env" ]; then
    cp .env.example .env
    echo "Bitte .env mit deinen Zugangsdaten ausfuellen."
fi

echo "Setup abgeschlossen. Aktivieren mit: source .venv/bin/activate"
