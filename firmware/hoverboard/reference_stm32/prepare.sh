#!/usr/bin/env bash
# Fetch the EFeru FOC hoverboard firmware at a pinned version and apply
# Forrest's settings. Run on the Mac:   bash firmware/hoverboard/prepare.sh
# Result: firmware/hoverboard/build/efoc/ ready for `pio run -e VARIANT_USART`.
# Safe to re-run: it starts from a fresh copy each time.
set -euo pipefail

EFOC_REPO=https://github.com/EFeru/hoverboard-firmware-hack-FOC
EFOC_COMMIT=4f141cbc97b297e194fd58e56444bd0322f902ac   # pinned 2026-10-30 (upstream main, 2026-07-04)

HERE="$(cd "$(dirname "$0")" && pwd)"
WORK="$HERE/build/efoc"
rm -rf "$WORK"
mkdir -p "$HERE/build"
git clone -q "$EFOC_REPO" "$WORK"
git -C "$WORK" checkout -q "$EFOC_COMMIT"

python3 "$HERE/forrest_config.py" "$WORK"

echo
echo "== Forrest changes (git diff):"
git -C "$WORK" --no-pager diff --stat
git -C "$WORK" --no-pager diff
echo
echo "Next:  cd $WORK && pio run -e VARIANT_USART"
