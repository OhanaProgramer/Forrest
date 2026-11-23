#!/bin/bash
# Copy a Pico's firmware from the repo to the board, then restart it.
# Usage: firmware/pico/deploy.sh [drive|sensors] [port]
#   board defaults to drive; port defaults to that board, by USB serial number
# The repo is the source of truth: edit here, deploy, never edit on the board.
set -euo pipefail
BOARD=drive
if [[ "${1:-}" == drive || "${1:-}" == sensors ]]; then BOARD=$1; shift; fi
cd "$(dirname "$0")/$BOARD"
ROOT="$(git rev-parse --show-toplevel)"
MP="$ROOT/.venv/bin/mpremote"
# Never "auto": with two Picos on USB, mpremote would take whichever comes first.
# The serial comes from BOARDS in src/forrest/drivers/pico.py (one source of truth).
SERIAL="$("$ROOT/.venv/bin/python" -c 'from forrest.drivers.pico import BOARDS; import sys; print(BOARDS[sys.argv[1]])' "$BOARD")"
PORT=${1:-id:$SERIAL}
CONNECT=(connect "$PORT")

# modules first, main.py last, so the board never boots a main.py whose imports are missing
if [[ $BOARD == drive ]]; then FILES=(comm.py heartbeat.py protocol.py main.py)
else FILES=(main.py); fi
"$MP" "${CONNECT[@]}" cp "${FILES[@]}" : + exec "import os; print('on board:', os.listdir())" + reset
echo "deployed to $BOARD: ${FILES[*]}"
