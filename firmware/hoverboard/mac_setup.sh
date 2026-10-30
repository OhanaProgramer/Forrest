#!/usr/bin/env bash
# One-time Mac setup for hoverboard work: flashing tools and a check that the
# ST-Link is seen. Run:  bash firmware/hoverboard/mac_setup.sh
set -euo pipefail

say() { printf '\n== %s\n' "$*"; }

say "Homebrew"
command -v brew >/dev/null || { echo "Install Homebrew first: https://brew.sh"; exit 1; }

say "Tools: stlink (st-info, st-flash), openocd (unlock), platformio (build)"
for pkg in stlink open-ocd platformio; do
  if brew list --formula "$pkg" >/dev/null 2>&1; then echo "   $pkg: installed"
  else brew install "$pkg"; fi
done

say "ST-Link probe (plug the ST-Link into the Mac, nothing connected to its pins yet)"
st-info --probe || echo "   No ST-Link seen: check the USB adapter, re-plug, try again."

say "Serial adapters present (CP2102 shows up as cu.usbserial-* or cu.SLAB_USBtoUART)"
ls /dev/cu.* 2>/dev/null | grep -Ei 'usbserial|SLAB|wchusb' || echo "   none plugged in"

say "Done. Next: bash firmware/hoverboard/prepare.sh"
