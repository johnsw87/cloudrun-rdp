# syntax=docker/dockerfile:1

# Copyright 2026 Google LLC
#
# Cloud Run container for seamless Google Chrome HTML5 window forwarding via Xpra.
# Unlike Cloud Workstations, Cloud Run does not boot systemd as PID 1; this image
# launches D-Bus and Xpra directly in the foreground on $PORT (default 8080).

FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive

# 1. Bootstrap HTTPS APT transport and register Xpra + Google Chrome APT repositories,
#    then install all OS, Xpra, audio, and Chrome packages in a single APT pass
#    with --no-install-recommends to avoid ~600MB of unused cups/pipewire/mesa bloat.
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates \
      curl && \
    mkdir -p /etc/apt/keyrings && \
    curl -fsSL https://xpra.org/gpg.asc -o /etc/apt/keyrings/xpra.asc && \
    curl -fsSL https://dl.google.com/linux/linux_signing_key.pub -o /etc/apt/keyrings/google-chrome.asc && \
    . /etc/os-release && \
    echo "deb [signed-by=/etc/apt/keyrings/xpra.asc] https://xpra.org/ ${VERSION_CODENAME} main" \
      > /etc/apt/sources.list.d/xpra.list && \
    echo "deb [arch=amd64 signed-by=/etc/apt/keyrings/google-chrome.asc] https://dl.google.com/linux/chrome/deb/ stable main" \
      > /etc/apt/sources.list.d/google-chrome.list && \
    apt-get update && apt-get install -y --no-install-recommends \
      dbus-x11 \
      fonts-liberation \
      gir1.2-glib-2.0 \
      gir1.2-gst-plugins-base-1.0 \
      gir1.2-gstreamer-1.0 \
      gir1.2-gtk-3.0 \
      google-chrome-stable \
      gstreamer1.0-plugins-base \
      gstreamer1.0-plugins-good \
      gstreamer1.0-plugins-ugly \
      gstreamer1.0-pulseaudio \
      gstreamer1.0-tools \
      libmp3lame0 \
      locales \
      procps \
      pulseaudio \
      pulseaudio-utils \
      python3-cairo \
      python3-dbus \
      python3-gi \
      python3-gi-cairo \
      python3-gst-1.0 \
      python3-netifaces \
      python3-paramiko \
      python3-pil \
      python3-requests \
      python3-setproctitle \
      python3-watchdog \
      python3-xdg \
      x11-xkb-utils \
      x11-xserver-utils \
      xauth \
      xdg-utils \
      xfonts-base \
      xkb-data \
      xpra \
      xpra-audio \
      xpra-audio-server \
      xpra-codecs \
      xpra-common \
      xpra-html5 \
      xpra-server \
      xpra-x11 \
      xserver-xorg-core \
      xserver-xorg-video-dummy \
      xvfb && \
    locale-gen en_US.UTF-8 && \
    xpra set xvfb Xdummy && \
    mkdir -p /tmp/.X11-unix && chmod 1777 /tmp/.X11-unix && \
    cp /opt/google/chrome/google-chrome /opt/google/chrome/google-chrome.orig && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# 2. Fast configuration & script layers placed at the end so edits rebuild in seconds
RUN useradd -m -s /bin/bash user && \
    mkdir -p /run/dbus && chown user:user /run/dbus && \
    rm -f /etc/xdg/autostart/pulseaudio.desktop && \
    printf "default-sink = Xpra-Speaker\ndefault-source = Xpra-Speaker.monitor\nautospawn = no\n" > /etc/pulse/client.conf && \
    cp /opt/google/chrome/google-chrome.orig /opt/google/chrome/google-chrome && \
    sed -i 's|exec -a "\$0" "\$HERE/chrome" "\$@"|export XDG_RUNTIME_DIR="/tmp/runtime-user" PULSE_SERVER="unix:/tmp/runtime-user/pulse/native" PULSE_SINK="Xpra-Speaker" PULSE_SOURCE="Xpra-Speaker.monitor" DBUS_SESSION_BUS_ADDRESS="unix:path=/tmp/runtime-user/bus" DBUS_SYSTEM_BUS_ADDRESS="unix:path=/tmp/runtime-user/bus"\nexec -a "$0" "$HERE/chrome" --no-sandbox --test-type --disable-gpu --disable-gpu-compositing --disable-software-rasterizer --autoplay-policy=no-user-gesture-required --no-first-run --no-default-browser-check --disable-background-networking --disable-sync --disable-translate --disable-dev-tools --hide-crash-restore-bubble "$@"|' /opt/google/chrome/google-chrome

COPY patch_xpra_audio.py /usr/local/bin/patch_xpra_audio.py
RUN python3 /usr/local/bin/patch_xpra_audio.py

COPY default-settings.txt /etc/xpra/html5-client/default-settings.txt
RUN if [ -d /usr/share/xpra/www ]; then \
      ln -sf /etc/xpra/html5-client/default-settings.txt /usr/share/xpra/www/default-settings.txt; \
    fi

COPY sync_gcs_state.py /usr/local/bin/sync_gcs_state.py
COPY entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/sync_gcs_state.py /usr/local/bin/entrypoint.sh && \
    python3 /usr/local/bin/sync_gcs_state.py --self-test

USER user
WORKDIR /home/user
ENV HOME=/home/user
ENV LANG=en_US.UTF-8
ENV PORT=8080

EXPOSE 8080

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
