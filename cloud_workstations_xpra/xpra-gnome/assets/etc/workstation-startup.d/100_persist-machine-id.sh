#!/bin/bash
# Copyright 2026 Google LLC
#
# Persist machine-id across workstation restarts.

SAVE_PATH=/home/.workstation/machine-id

if [ ! -f "${SAVE_PATH}" ]; then
  MACHINE_ID=$(cat /etc/machine-id)
  echo "saving machine id ${MACHINE_ID} to ${SAVE_PATH}"
  mkdir -p "$(dirname "${SAVE_PATH}")"
  printf '%s\n' "${MACHINE_ID}" > "${SAVE_PATH}"
fi
