# Cloud Workstations — Xpra HTML5 Browser & GNOME Desktop Images

Two custom Cloud Workstations container configurations using **Xpra HTML5 forwarding** on **port `80`** (instead of VNC or Chrome Remote Desktop), so clicking **Launch** in Cloud Workstations immediately opens the graphical environment in the browser.

## Configurations

| Folder | Mode | Xpra Command | What Opens on Port 80 |
| :--- | :--- | :--- | :--- |
| [`xpra-chrome/`](./xpra-chrome/) | Seamless Browser Window Forwarding | `xpra start :100 --bind-tcp=0.0.0.0:80 --html=on` | Full-window **Google Chrome** directly inside the HTML5 canvas (no desktop shell overhead). |
| [`xpra-gnome/`](./xpra-gnome/) | Full Desktop Forwarding | `xpra start-desktop :100 --bind-tcp=0.0.0.0:80 --html=on` | Full **Ubuntu GNOME Desktop** (`ubuntu-desktop-minimal`) with Chrome and GNOME Terminal pre-pinned. |

## Key Design Choices
1. **Base Image (`predefined/base`)**: Extends `us-central1-docker.pkg.dev/cloud-workstations-images/predefined/base` rather than `code-oss` so port `80` is available for Xpra's built-in HTML5 server.
2. **Managed by `systemd` (`CAP_NET_BIND_SERVICE`)**: Both images run `systemd` as PID 1 via `/google/scripts/entrypoint.sh` (after executing `/usr/bin/workstation-startup`) and launch Xpra as unprivileged `user` (UID `1000`) with `AmbientCapabilities=CAP_NET_BIND_SERVICE` so it can bind port `80` safely and auto-restart if the window/session exits.
3. **Headless GPU Compatibility**: Google Chrome is configured with `--disable-gpu --disable-dev-shm-usage --use-gl=swiftshader` (and `LIBGL_ALWAYS_SOFTWARE=1` + `--disable-acceleration-check` for GNOME) to prevent black/blank windows on GPU-less Cloud Workstation VMs.
4. **Virtual Audio Driver (`Xpra-Speaker` / `Xpra-Mic-Source`)**: Both images start an unprivileged PulseAudio server with Xpra's virtual `module-null-sink` (`Xpra-Speaker`) and `module-remap-source` (`Xpra-Mic-Source`), encoding container audio via GStreamer (`opus+mka` / `vorbis+mka` / `mp3`) directly to the user's local browser audio output.
5. **VPC Security Note**: Because Xpra listens on port `80` inside the container and relies on the Cloud Workstations HTTPS/IAP gateway for authentication, ensure VPC firewall rules only permit ingress to workstation port `80` from the Cloud Workstations gateway IP range.
