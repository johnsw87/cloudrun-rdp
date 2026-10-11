# syntax=docker/dockerfile:1

# Copyright 2026 Google LLC
#
# Cloud Run container for full Linux Desktop HTML5 forwarding via Xpra.
# Uses XFCE4 (xfce4-session) instead of GNOME Shell because Cloud Run does not
# allow booting systemd/systemd-logind as PID 1, which modern GNOME requires.

FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive

# Install XFCE4 desktop environment, terminal, and D-Bus
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    dbus-x11 \
    fonts-liberation \
    gnupg \
    locales \
    pavucontrol \
    procps \
    tango-icon-theme \
    wget \
    xdg-utils \
    xfce4 \
    xfce4-goodies \
    xfce4-pulseaudio-plugin \
    xfce4-terminal && \
  locale-gen en_US.UTF-8 && \
  apt-get clean && \
  rm -rf /var/lib/apt/lists/*

# Install Xpra + HTML5 client + virtual audio forwarding
RUN mkdir -p /etc/apt/keyrings && \
  curl -fsSL https://xpra.org/gpg.asc -o /etc/apt/keyrings/xpra.asc && \
  . /etc/os-release && \
  echo "deb [signed-by=/etc/apt/keyrings/xpra.asc] https://xpra.org/ ${VERSION_CODENAME} main" \
    > /etc/apt/sources.list.d/xpra.list && \
  apt-get update && apt-get install -y \
    gstreamer1.0-plugins-base \
    gstreamer1.0-plugins-good \
    gstreamer1.0-plugins-ugly \
    gstreamer1.0-pulseaudio \
    gstreamer1.0-tools \
    libmp3lame0 \
    pulseaudio \
    pulseaudio-utils \
    python3-gst-1.0 \
    python3-paramiko \
    python3-requests \
    xpra \
    xpra-audio \
    xpra-html5 \
    xpra-x11 \
    xserver-xorg-core \
    xserver-xorg-video-dummy \
    xvfb && \
  xpra set xvfb Xdummy && \
  mkdir -p /tmp/.X11-unix && chmod 1777 /tmp/.X11-unix && \
  apt-get clean && \
  rm -rf /var/lib/apt/lists/*

# Install Google Chrome and configure flags for Cloud Run Gen2 (keep MIT-SHM & /dev/shm enabled for fast X11 shared-memory rendering)
RUN wget -q -O /tmp/google-chrome-stable_current_amd64.deb \
    https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb && \
  apt-get update && \
  apt-get install -y /tmp/google-chrome-stable_current_amd64.deb && \
  rm /tmp/google-chrome-stable_current_amd64.deb && \
  apt-get clean && \
  rm -rf /var/lib/apt/lists/* && \
  sed -i 's|exec -a "\$0" "\$HERE/chrome" "\$@"|export XDG_RUNTIME_DIR="/tmp/runtime-user" PULSE_SERVER="unix:/tmp/runtime-user/pulse/native" PULSE_SINK="Xpra-Speaker" PULSE_SOURCE="Xpra-Speaker.monitor" DBUS_SESSION_BUS_ADDRESS="unix:path=/tmp/runtime-user/bus" DBUS_SYSTEM_BUS_ADDRESS="unix:path=/tmp/runtime-user/bus"\nexec -a "$0" "$HERE/chrome" --no-sandbox --disable-gpu --disable-gpu-compositing --disable-software-rasterizer --autoplay-policy=no-user-gesture-required --no-first-run --no-default-browser-check --disable-background-networking --disable-sync --disable-translate --disable-dev-tools --hide-crash-restore-bubble "$@"|' /opt/google/chrome/google-chrome && \
  update-alternatives --install /usr/bin/x-www-browser x-www-browser /usr/bin/google-chrome-stable 200 && \
  update-alternatives --set x-www-browser /usr/bin/google-chrome-stable

# Patch XpraDesktopServer so RandR 1.6 Xdummy virtual monitor (VFB-0) resizes
# dynamically with the X11 root screen to fill the entire HTML5 browser viewport,
# and patch Xpra server/HTML5 audio handling for PulseAudio & Chrome autoplay
COPY patch_xpra_desktop_resize.py /usr/local/bin/patch_xpra_desktop_resize.py
COPY patch_xpra_audio.py /usr/local/bin/patch_xpra_audio.py
RUN python3 /usr/local/bin/patch_xpra_desktop_resize.py && \
    python3 /usr/local/bin/patch_xpra_audio.py

# Configure Xpra HTML5 client defaults
COPY default-settings.txt /etc/xpra/html5-client/default-settings.txt
RUN if [ -d /usr/share/xpra/www ]; then \
      ln -sf /etc/xpra/html5-client/default-settings.txt /usr/share/xpra/www/default-settings.txt; \
    fi

# Create unprivileged runtime user, configure system-wide PulseAudio client
# defaults so all desktop/D-Bus/browser subprocesses route audio to Xpra-Speaker,
# and remove XDG autostart pulseaudio launcher so XFCE4 does not interfere
RUN useradd -m -s /bin/bash user && \
    mkdir -p /run/dbus && chown user:user /run/dbus && \
    rm -f /etc/xdg/autostart/pulseaudio.desktop && \
    printf "default-sink = Xpra-Speaker\ndefault-source = Xpra-Speaker.monitor\nautospawn = no\n" > /etc/pulse/client.conf

COPY entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

# Install Google Cloud CLI (gcloud, bq, gsutil) so terminal sessions authenticate
# automatically via the Cloud Run metadata server
RUN curl -fsSL https://packages.cloud.google.com/apt/doc/apt-key.gpg \
    | gpg --dearmor -o /etc/apt/keyrings/cloud.google.gpg && \
  echo "deb [signed-by=/etc/apt/keyrings/cloud.google.gpg] https://packages.cloud.google.com/apt cloud-sdk main" \
    > /etc/apt/sources.list.d/google-cloud-sdk.list && \
  apt-get update && apt-get install -y --no-install-recommends \
    google-cloud-cli && \
  apt-get clean && \
  rm -rf /var/lib/apt/lists/*

USER user
WORKDIR /home/user
ENV HOME=/home/user
ENV LANG=en_US.UTF-8
ENV PORT=8080

EXPOSE 8080

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
