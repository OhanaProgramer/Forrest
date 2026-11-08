#!/bin/bash
# Copy the Pico drive firmware from the repo to the board, then restart it.
# Usage: firmware/pico/deploy.sh [port]     (default: auto-detect)
# The repo is the source of truth: edit here, deploy, never edit on the board.
set -euo pipefail
cd "$(dirname "$0")/drive"
MP="$(git rev-parse --show-toplevel)/.venv/bin/mpremote"
PORT=${1:-auto}
CONNECT=(connect "$PORT")
[ "$PORT" = auto ] && CONNECT=()

# modules first, main.py last, so the board never boots a main.py whose imports are missing
FILES=(comm.py heartbeat.py protocol.py main.py)
"$MP" "${CONNECT[@]}" cp "${FILES[@]}" : + exec "import os; print('on board:', os.listdir())" + reset
echo "deployed: ${FILES[*]}"
