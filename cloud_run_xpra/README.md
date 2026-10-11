# Cloud Run — Xpra HTML5 Browser & Desktop Containers

Serverless adaptations of the Xpra HTML5 containers designed for **Google Cloud Run** (`--execution-environment=gen2`).

## Key Differences from Cloud Workstations

| Requirement | Cloud Workstations (`cloud_workstations_xpra/`) | Cloud Run (`cloud_run_xpra/`) |
| :--- | :--- | :--- |
| **Init / PID 1** | Runs full `systemd` (`/sbin/init`) inside a dedicated GCE VM | Cloud Run controls PID 1 (`systemd` cannot boot); uses a single session/system `dbus-daemon` + foreground `xpra --daemon=no` |
| **Desktop Environment** | Ubuntu GNOME (`gnome-shell` via `systemd-logind`) | **XFCE4 (`xfce4-session`)** with `xfwm4` compositing disabled + X11 `MIT-SHM` enabled |
| **Port** | Port `80` | `$PORT` (default `8080`) |
| **Chrome Sandbox** | Standard userns sandbox | Requires `--no-sandbox` inside Cloud Run's container sandbox |
| **Virtual Audio Driver** | PulseAudio virtual sink (`Xpra-Speaker`) + GStreamer (`opus+mka`) streamed via HTML5 MediaSource | Unprivileged PulseAudio (`Xpra-Speaker` null sink without suspend-on-idle) + GStreamer (`mp3` / `wav`, `--av-sync=off`) with automatic HTML5 autoplay unlock on first click/keypress |
| **Session State** | 1 dedicated VM + Persistent Disk per user | Requires `--max-instances=1`, `--concurrency=80` (so parallel HTML5 JS/CSS asset loads + WebSocket stream don't hit HTTP 429), `--session-affinity`, `--no-cpu-throttling`, and `--timeout=3600` |

## Build & Deploy to Cloud Run

```bash
export PROJECT_ID="your-project-id"
export REGION="europe-west2"
export REPO_NAME="cloud-run-images"

# 1. Build (choose xpra-chrome or xpra-desktop)
gcloud builds submit ./xpra-chrome \
  --config=./xpra-chrome/cloudbuild.yaml \
  --substitutions="_IMAGE_NAME=${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO_NAME}/xpra-chrome:latest"

# 2. Deploy to Cloud Run (Gen2, CPU always allocated, 60m WebSocket timeout, single stateful instance)
gcloud beta run deploy xpra-chrome \
  --project="${PROJECT_ID}" \
  --region="${REGION}" \
  --image="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO_NAME}/xpra-chrome:latest" \
  --execution-environment=gen2 \
  --cpu=4 \
  --memory=8Gi \
  --no-cpu-throttling \
  --session-affinity \
  --concurrency=80 \
  --max-instances=1 \
  --timeout=3600 \
  --iap \
  --no-allow-unauthenticated
```

## Accessing Securely
Because the service is deployed with `--no-allow-unauthenticated`, protect it behind **Identity-Aware Proxy (IAP)** on an external Application Load Balancer, or test locally via Cloud Run's authenticated proxy:

```bash
gcloud run services proxy xpra-chrome --project="${PROJECT_ID}" --region="${REGION}" --port=8080
```
