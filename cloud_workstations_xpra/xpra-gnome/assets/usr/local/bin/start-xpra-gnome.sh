#!/bin/bash
# Copyright 2026 Google LLC
#
# Starts an Xpra desktop session (xpra start-desktop) on :100 with the built-in
# HTML5 web client bound to port 80 so Cloud Workstations routes HTTPS/WSS
# traffic directly to a full Ubuntu GNOME desktop.

set -euo pipefail

export HOME="${HOME:-/home/user}"
export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/1000}"
export PULSE_RUNTIME_PATH="${XDG_RUNTIME_DIR}/pulse"
export PULSE_STATE_PATH="${XDG_RUNTIME_DIR}/pulse"
export PULSE_COOKIE="${XDG_RUNTIME_DIR}/pulse/cookie"
export XPRA_PRIVATE_PULSEAUDIO=0
export XPRA_PULSEAUDIO_SHM=0
export XPRA_PULSEAUDIO_REALTIME=0
export XPRA_PULSEAUDIO_HIGH_PRIORITY=0
export XPRA_AUDIO_QUERY_SLEEP=2

mkdir -p "${XDG_RUNTIME_DIR}" "${PULSE_RUNTIME_PATH}"
chmod 0700 "${XDG_RUNTIME_DIR}" "${PULSE_RUNTIME_PATH}"

exec /usr/bin/xpra start-desktop :100 \
  --xvfb=Xdummy \
  --bind-tcp=0.0.0.0:80 \
  --html=on \
  --daemon=no \
  --systemd-run=no \
  --dbus-launch="" \
  --dbus-control=no \
  --exit-with-children=yes \
  --exit-with-client=no \
  --resize-display=yes \
  --pulseaudio=yes \
  --pulseaudio-configure-commands=none \
  --speaker=on \
  --microphone=on \
  --av-sync=on \
  --mdns=no \
  --webcam=no \
  --printing=no \
  --bell=no \
  --notifications=no \
  --start-child="/usr/local/bin/gnome-session-wrapper.sh"
