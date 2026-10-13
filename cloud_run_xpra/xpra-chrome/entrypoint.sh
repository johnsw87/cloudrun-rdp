#!/bin/bash
# Copyright 2026 Google LLC
#
# Starts a session D-Bus and runs Xpra seamless window forwarding in the foreground
# bound to Cloud Run's $PORT (default 8080).

set -euo pipefail

export HOME="${HOME:-/home/user}"
export XDG_RUNTIME_DIR="/tmp/runtime-user"

mkdir -p "${XDG_RUNTIME_DIR}"
chmod 0700 "${XDG_RUNTIME_DIR}"

# Restore persistent user & browser state from GCS Fuse mount (if mounted at $GCS_STATE_MOUNT_PATH)
export GCS_STATE_MOUNT_PATH="${GCS_STATE_MOUNT_PATH:-/mnt/state}"
python3 /usr/local/bin/sync_gcs_state.py init || true
if [ -d "${GCS_STATE_MOUNT_PATH}" ] && [ -w "${GCS_STATE_MOUNT_PATH}" ]; then
  python3 /usr/local/bin/sync_gcs_state.py daemon &
  GCS_SYNC_PID=$!
fi

# Start an unprivileged PulseAudio server with a single Xpra-Speaker null sink
# (without module-suspend-on-idle so the monitor stream never stalls).
# Note: PULSE_SERVER must be exported AFTER pulseaudio starts so pulseaudio
# does not treat it as an external remote server.
PULSE_RUNTIME_PATH="${XDG_RUNTIME_DIR}/pulse"
mkdir -p "${PULSE_RUNTIME_PATH}"
chmod 0700 "${PULSE_RUNTIME_PATH}"
export PULSE_RUNTIME_PATH
pulseaudio --start --daemonize=yes --disallow-exit=yes --exit-idle-time=-1 \
  --high-priority=no --realtime=no --log-target=stderr \
  -n \
  -L "module-null-sink sink_name=Xpra-Speaker sink_properties=device.description=Xpra-Speaker" \
  -L "module-native-protocol-unix auth-anonymous=1 socket=${PULSE_RUNTIME_PATH}/native" \
  -L "module-default-device-restore" \
  -L "module-always-sink" \
  -L "module-intended-roles" \
  -L "module-stream-restore"
export PULSE_SERVER="unix:${PULSE_RUNTIME_PATH}/native"
export PULSE_SINK="Xpra-Speaker"
export PULSE_SOURCE="Xpra-Speaker.monitor"
export XPRA_PULSE_SOURCE_DEVICE_NAME="Xpra-Speaker.monitor"
export XPRA_CUTTER_THRESHOLD="0"
pactl set-default-sink Xpra-Speaker || true
pactl set-default-source Xpra-Speaker.monitor || true
pactl set-sink-mute Xpra-Speaker 0 || true
pactl set-sink-volume Xpra-Speaker 100% || true
pactl set-source-mute Xpra-Speaker.monitor 0 || true

# Start a single clean D-Bus daemon after PulseAudio env vars are exported so
# browser/audio subprocesses inherit PULSE_SERVER
DBUS_SOCK="${XDG_RUNTIME_DIR}/bus"
rm -f "${DBUS_SOCK}"
dbus-daemon --session --address="unix:path=${DBUS_SOCK}" --nofork --nopidfile &
ln -sf "${DBUS_SOCK}" /run/dbus/system_bus_socket || true
export DBUS_SESSION_BUS_ADDRESS="unix:path=${DBUS_SOCK}"
export DBUS_SYSTEM_BUS_ADDRESS="unix:path=${DBUS_SOCK}"

LISTEN_PORT="${PORT:-8080}"

cleanup() {
  echo "[entrypoint] Caught shutdown signal, stopping Xpra and flushing state to GCS..."
  if [ -n "${XPRA_PID:-}" ] && kill -0 "${XPRA_PID}" 2>/dev/null; then
    kill -TERM "${XPRA_PID}" 2>/dev/null || true
    for _ in 1 2 3 4 5 6; do
      kill -0 "${XPRA_PID}" 2>/dev/null || break
      sleep 0.5
    done
  fi
  if [ -n "${GCS_SYNC_PID:-}" ] && kill -0 "${GCS_SYNC_PID}" 2>/dev/null; then
    kill -TERM "${GCS_SYNC_PID}" 2>/dev/null || true
  fi
  python3 /usr/local/bin/sync_gcs_state.py sync || true
  exit 0
}
trap cleanup SIGTERM SIGINT

/usr/bin/xpra start :100 \
  --xvfb=Xdummy \
  --bind-tcp="0.0.0.0:${LISTEN_PORT}" \
  --html=on \
  --daemon=no \
  --systemd-run=no \
  --dbus-launch="" \
  --dbus-control=no \
  --exit-with-children=yes \
  --exit-with-client=no \
  --resize-display=1920x1080 \
  --dpi=96 \
  --opengl=no \
  --mmap=yes \
  --sharing=yes \
  --encoding=jpeg \
  --encodings=jpeg,png,rgb \
  --video-encoders=none \
  --csc-modules=none \
  --quality=75 \
  --min-quality=40 \
  --speed=90 \
  --min-speed=75 \
  --compress=1 \
  --bandwidth-limit=0 \
  --pulseaudio=no \
  --speaker=on \
  --speaker-codec=mp3 \
  --speaker-codec=wav \
  --microphone=off \
  --av-sync=off \
  --mdns=no \
  --webcam=no \
  --printing=no \
  --bell=no \
  --notifications=no \
  --start-child="/usr/bin/google-chrome-stable --no-sandbox --test-type --no-first-run --no-default-browser-check --hide-crash-restore-bubble --start-maximized" &
XPRA_PID=$!
wait "${XPRA_PID}" || true
python3 /usr/local/bin/sync_gcs_state.py sync || true

