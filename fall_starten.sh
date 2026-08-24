#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ -z "$1" ]; then
    echo "Verwendung: ./fall_starten.sh <rohdaten.json>"
    exit 1
fi

if [ -f "$SCRIPT_DIR/.venv/bin/activate" ]; then
    source "$SCRIPT_DIR/.venv/bin/activate"
else
    source "$SCRIPT_DIR/.venv/Scripts/activate"
fi

python "$SCRIPT_DIR/start.py" "$1"
