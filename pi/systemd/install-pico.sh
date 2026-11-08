#!/usr/bin/env bash
# Install and start the forrest-pico user service (starts at boot; linger is on).
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
mkdir -p ~/.config/systemd/user
ln -sf "$here/forrest-pico.service" ~/.config/systemd/user/forrest-pico.service
loginctl enable-linger "$USER"
systemctl --user daemon-reload
systemctl --user enable --now forrest-pico.service
systemctl --user --no-pager status forrest-pico.service | head -5
