#!/bin/bash
# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# Invoke Cloud Workstations startup scripts (user creation, /home mount, sshd, etc.)
/usr/bin/workstation-startup

log () {
  echo "$(date -u +'%b %d %H:%M:%S') $(hostname) $(basename "$0")[$$]: $1"
}

# Stream systemd journal logs to stdout for Cloud Logging
{
  until journalctl -n0 >/dev/null 2>&1; do
    log "waiting for journalctl"
    sleep 1
  done
  log "following journalctl"
  journalctl -f
} &

# Re-use machine-id saved in /home/.workstation/machine-id across restarts
MACHINE_ID=$(cat /home/.workstation/machine-id 2>/dev/null || true)
if [ -n "${MACHINE_ID}" ]; then
  log "starting systemd with machine id ${MACHINE_ID}"
  exec /sbin/init --system --unit=multi-user.target --machine-id "${MACHINE_ID}"
else
  log "starting systemd"
  exec /sbin/init --system --unit=multi-user.target
fi
