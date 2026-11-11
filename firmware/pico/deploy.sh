#!/bin/bash
# Copy the Pico drive firmware from the repo to the board, then restart it.
# Usage: firmware/pico/deploy.sh [port]     (default: the drive board, by USB serial number)
# The repo is the source of truth: edit here, deploy, never edit on the board.
set -euo pipefail
cd "$(dirname "$0")/drive"
ROOT="$(git rev-parse --show-toplevel)"
MP="$ROOT/.venv/bin/mpremote"
# Never "auto": with two Picos on USB, mpremote would take whichever comes first.
# The serial comes from BOARDS in src/forrest/drivers/pico.py (one source of truth).
SERIAL="$("$ROOT/.venv/bin/python" -c 'from forrest.drivers.pico import BOARDS; print(BOARDS["drive"])')"
PORT=${1:-id:$SERIAL}
CONNECT=(connect "$PORT")

# modules first, main.py last, so the board never boots a main.py whose imports are missing
FILES=(comm.py heartbeat.py protocol.py main.py)
"$MP" "${CONNECT[@]}" cp "${FILES[@]}" : + exec "import os; print('on board:', os.listdir())" + reset
echo "deployed: ${FILES[*]}"
