#!/bin/bash
# Copyright 2026 Google LLC
#
# Initializes Ubuntu X11 GNOME environment variables and launches gnome-session
# with software rendering inside the Xpra virtual desktop display.

export XDG_SESSION_TYPE=x11
export XKL_XMODMAP_DISABLE=1
export DESKTOP_SESSION=ubuntu-xorg
export XDG_SESSION_DESKTOP="${DESKTOP_SESSION}"
export XDG_CONFIG_DIRS=/etc/xdg/xdg-ubuntu-xorg:/etc/xdg
export XDG_CURRENT_DESKTOP=ubuntu:GNOME
export XDG_DATA_DIRS="/usr/share/${DESKTOP_SESSION}:/usr/share/gnome:/usr/local/share/:/usr/share/:/var/lib/snapd/desktop"
export GNOME_SHELL_SESSION_MODE=ubuntu
export LIBGL_ALWAYS_SOFTWARE=1

unset SESSION_MANAGER
unset DBUS_SESSION_BUS_ADDRESS

exec dbus-launch --exit-with-session /usr/bin/gnome-session --disable-acceleration-check
