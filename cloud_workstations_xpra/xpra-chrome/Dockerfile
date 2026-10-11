# syntax=docker/dockerfile:1

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

FROM us-central1-docker.pkg.dev/cloud-workstations-images/predefined/base

# Install and configure systemd so Xpra runs as a managed service on port 80
RUN apt-get update && apt-get install -y \
    ca-certificates \
    curl \
    dbus-x11 \
    gnupg \
    locales \
    systemd \
    wget && \
  apt-get clean && \
  rm -rf /var/lib/apt/lists/* && \
  ln -sf /dev/null /etc/systemd/system/apache2.service && \
  ln -sf /dev/null /etc/systemd/system/getty@tty1.service && \
  ln -sf /dev/null /etc/systemd/system/ldconfig.service && \
  /sbin/ldconfig -Xv && \
  ln -sf /dev/null /etc/systemd/system/systemd-modules-load.service && \
  ln -sf /dev/null /etc/systemd/system/ssh.socket && \
  ln -sf /dev/null /etc/systemd/system/ssh.service && \
  echo "d /run/sshd 0755 root root" > /usr/lib/tmpfiles.d/sshd.conf && \
  printf "x /run/docker.socket - - - - -\nx /var/run/docker.socket - - - - -\n" > /usr/lib/tmpfiles.d/docker.conf

# Install Xpra + HTML5 client for seamless window forwarding
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
    pulseaudio \
    pulseaudio-utils \
    python3-avahi \
    python3-gst-1.0 \
    python3-paramiko \
    python3-requests \
    python3-zeroconf \
    xpra \
    xpra-audio \
    xpra-html5 \
    xpra-x11 \
    xserver-xorg-core \
    xserver-xorg-video-dummy \
    xvfb && \
  xpra set xvfb Xdummy && \
  apt-get clean && \
  rm -rf /var/lib/apt/lists/*

# Install Google Chrome and configure headless software rendering (SwiftShader)
RUN wget -q -O /tmp/google-chrome-stable_current_amd64.deb \
    https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb && \
  apt-get update && \
  apt-get install -y /tmp/google-chrome-stable_current_amd64.deb && \
  rm /tmp/google-chrome-stable_current_amd64.deb && \
  apt-get clean && \
  rm -rf /var/lib/apt/lists/* && \
  echo "QT_X11_NO_MITSHM=1 _X11_NO_MITSHM=1 _MITSHM=0 $(tail -n -1 /opt/google/chrome/google-chrome) --disable-gpu --disable-dev-shm-usage --use-gl=swiftshader" \
    >> /opt/google/chrome/google-chrome && \
  sed -i 'N;$!P;D' /opt/google/chrome/google-chrome

# Merge configuration and startup scripts into the container
COPY assets/. /

RUN chmod +x \
    /google/scripts/entrypoint.sh \
    /etc/workstation-startup.d/100_persist-machine-id.sh \
    /usr/local/bin/start-xpra-chrome.sh && \
  if [ -d /usr/share/xpra/www ]; then \
    ln -sf /etc/xpra/html5-client/default-settings.txt /usr/share/xpra/www/default-settings.txt; \
  fi && \
  ln -sf /etc/systemd/system/xpra-chrome.service /etc/systemd/system/multi-user.target.wants/xpra-chrome.service

ENTRYPOINT ["/google/scripts/entrypoint.sh"]
