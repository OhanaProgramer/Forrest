#!/usr/bin/env bash
# Install and start the forrest-dash user service; enable linger so it runs at boot.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
mkdir -p ~/.config/systemd/user
ln -sf "$here/forrest-dash.service" ~/.config/systemd/user/forrest-dash.service
loginctl enable-linger "$USER"
systemctl --user daemon-reload
systemctl --user enable --now forrest-dash.service
systemctl --user --no-pager status forrest-dash.service | head -5
