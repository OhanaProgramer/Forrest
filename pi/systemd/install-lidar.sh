#!/usr/bin/env bash
# Install and start the forrest-lidar user service (starts at boot; linger is on).
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
mkdir -p ~/.config/systemd/user
ln -sf "$here/forrest-lidar.service" ~/.config/systemd/user/forrest-lidar.service
loginctl enable-linger "$USER"
systemctl --user daemon-reload
systemctl --user enable --now forrest-lidar.service
systemctl --user --no-pager status forrest-lidar.service | head -5
