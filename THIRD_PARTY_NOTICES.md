# Third-Party Software & License Notices

The container build definitions (`Dockerfile`, `cloudbuild.yaml`, `entrypoint.sh`, and configuration files) in this repository are licensed under the **[Apache License, Version 2.0](./LICENSE)**.

> **Disclaimer:** This is not an officially supported Google product. It is provided on an "AS IS" basis, without warranties or conditions of any kind.

---

## 1. Build-Time Patches to Xpra (`patch_xpra_*.py`)

During container image builds (`docker build`), the helper scripts `patch_xpra_desktop_resize.py` and `patch_xpra_audio.py` apply targeted compatibility patches to the installed **Xpra** server Python modules (`/usr/lib/python3/dist-packages/xpra/...`) and the **Xpra HTML5 Client** (`/usr/share/xpra/www/js/Client.js`):

- **Xpra Server (`xpra`, `xpra-x11`, `xpra-audio`)**:
  - Upstream project: [https://github.com/Xpra-org/xpra](https://github.com/Xpra-org/xpra)
  - License: **GNU General Public License v2.0 or later (`GPL-2.0-or-later`)**
  - Any modifications applied to Xpra's GPLv2+ files inside a built container image are covered by the **GNU General Public License v2.0 or later** (`https://www.gnu.org/licenses/old-licenses/gpl-2.0.html`). The complete source code of the patches is included in this repository inside `patch_xpra_desktop_resize.py` and `patch_xpra_audio.py`.
- **Xpra HTML5 Client (`xpra-html5`)**:
  - Upstream project: [https://github.com/Xpra-org/xpra-html5](https://github.com/Xpra-org/xpra-html5)
  - License: **Mozilla Public License 2.0 (`MPL-2.0`)** / **GPL-2.0-or-later**
  - Any modifications applied to `/usr/share/xpra/www/js/Client.js` are covered by the **MPL-2.0** (`https://www.mozilla.org/en-US/MPL/2.0/`) and are provided in source form in `patch_xpra_audio.py`.

---

## 2. Third-Party Software Installed During Container Builds

This repository does **not** redistribute compiled binaries in Git. However, when you build a container image using the provided `Dockerfile`s, the build downloads and installs the following third-party software packages into your resulting container image. If you distribute built container images to third parties, you are responsible for complying with the license terms of all included packages:

| Component | Source | License | Notes |
| :--- | :--- | :--- | :--- |
| **Ubuntu Base Image (`ubuntu:24.04`)** | [Canonical / Ubuntu](https://hub.docker.com/_/ubuntu) | Various Open Source ([Ubuntu License Policy](https://ubuntu.com/legal/intellectual-property-policy)) | Base OS userland and APT packages |
| **Xpra (`xpra`, `xpra-x11`, `xpra-audio`)** | [xpra.org](https://xpra.org/) | **GPL-2.0-or-later** | X11 window/desktop server & GStreamer audio forwarding |
| **Xpra HTML5 (`xpra-html5`)** | [xpra.org](https://github.com/Xpra-org/xpra-html5) | **MPL-2.0** | Browser-based HTML5/WebSocket client |
| **XFCE4 Desktop (`xfce4`, `xfce4-goodies`, `xfce4-terminal`)** | [xfce.org](https://www.xfce.org/about/credits) | **GPL-2.0+ / LGPL-2.0+** | Lightweight Linux desktop environment (`xpra-desktop`) |
| **GNOME Desktop (`ubuntu-desktop-minimal`)** | [gnome.org](https://www.gnome.org/) | **GPL-2.0+ / LGPL-2.1+** | Desktop environment (`cloud_workstations_xpra/xpra-gnome`) |
| **PulseAudio (`pulseaudio`, `pulseaudio-utils`)** | [freedesktop.org](https://www.freedesktop.org/wiki/Software/PulseAudio/) | **LGPL-2.1-or-later / GPL-2.0+** | Virtual audio server (`Xpra-Speaker` null sink) |
| **GStreamer (`gstreamer1.0-*`, `libmp3lame0`)** | [gstreamer.freedesktop.org](https://gstreamer.freedesktop.org/) | **LGPL-2.1-or-later** | Audio capture & MP3/WAV/Opus encoding pipeline |
| **X.Org Server & `Xdummy` (`xserver-xorg-core`, `xserver-xorg-video-dummy`)** | [x.org](https://www.x.org/) | **MIT / X11 License** | Virtual framebuffer X11 display server |
| **Google Chrome (`google-chrome-stable`)** | [google.com/chrome](https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb) | **[Google Chrome Terms of Service](https://www.google.com/chrome/terms/)** | Proprietary browser binary downloaded at build time. Note: Google Chrome binaries generally may not be redistributed publicly in pre-built container images; users should build the image in their own environment. |
| **Google Cloud CLI (`google-cloud-cli`)** | [cloud.google.com/sdk](https://cloud.google.com/sdk) | **Apache-2.0** | Installed in `xpra-desktop` for terminal authentication |
