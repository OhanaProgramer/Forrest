#!/usr/bin/env bash
# Install and start the forrest-sensors user service (starts at boot; linger is on).
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
mkdir -p ~/.config/systemd/user
ln -sf "$here/forrest-sensors.service" ~/.config/systemd/user/forrest-sensors.service
loginctl enable-linger "$USER"
systemctl --user daemon-reload
systemctl --user enable --now forrest-sensors.service
systemctl --user --no-pager status forrest-sensors.service | head -5
