#!/usr/bin/env bash
# Set up (or rebuild) Forrest Jr's software on a Raspberry Pi 5.
# Run from the repo folder on the Pi:   bash pi/setup_pi.sh
# Add --apply to also make the system changes it would otherwise only report.
#
# Safe to run again: each step checks before it changes anything.
set -euo pipefail

APPLY=0
[[ "${1:-}" == "--apply" ]] && APPLY=1
REPO="$(cd "$(dirname "$0")/.." && pwd)"
CONFIG=/boot/firmware/config.txt

say()  { printf '\n== %s\n' "$*"; }
note() { printf '   %s\n' "$*"; }

say "Repo: $REPO"

# 1. Python environment (Trixie requires a venv for pip installs)
say "Python virtual environment"
if [[ ! -d "$REPO/.venv" ]]; then
  python3 -m venv "$REPO/.venv"
  note "created .venv"
fi
"$REPO/.venv/bin/pip" install -q --upgrade pip
"$REPO/.venv/bin/pip" install -q -e "$REPO[viz,dev]"
note "installed forrest + plotting + tests"
note "activate with:  source $REPO/.venv/bin/activate"

# 2. Serial port access (LIDAR over USB shows up as a serial device)
say "Serial port permission"
if id -nG "$USER" | grep -qw dialout; then
  note "$USER is in the dialout group: OK"
elif (( APPLY )); then
  sudo usermod -aG dialout "$USER"
  note "added $USER to dialout. Log out and back in (or reboot) for it to take effect."
else
  note "NEEDED: $USER is not in dialout. Re-run with --apply, or: sudo usermod -aG dialout $USER"
fi

# 3. USB current: the C1 draws ~800 mA at spin-up; the Pi allows 600 mA total
#    unless told the supply can deliver 5 A (our buck converter can't say so itself).
say "USB current limit (config.txt)"
if grep -qE '^\s*usb_max_current_enable=1' "$CONFIG" 2>/dev/null; then
  note "usb_max_current_enable=1 is set: OK"
elif (( APPLY )); then
  sudo cp "$CONFIG" "$CONFIG.bak.$(date +%Y%m%d%H%M)"
  printf '\n# Forrest: buck converter supplies 5V 5A; allow full USB current\nusb_max_current_enable=1\n' \
    | sudo tee -a "$CONFIG" >/dev/null
  note "added usb_max_current_enable=1 (backup saved next to config.txt). Reboot to apply."
else
  note "NEEDED: add usb_max_current_enable=1 to $CONFIG. Re-run with --apply."
fi

# 4. What's plugged in
say "Serial devices now present"
ls -1 /dev/ttyUSB* /dev/ttyACM* 2>/dev/null || note "none (plug in the LIDAR's USB adapter)"

# 5. Power state since boot
say "Pi power check"
"$REPO/.venv/bin/forrest" power || true

say "Done. Next: forrest lidar check"
