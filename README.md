# Cloud Run & Cloud Workstations — Xpra HTML5 Remote Desktop & Browser

Container images for running a **remote Linux desktop** or **seamless Google Chrome browser** on Google Cloud, streamed directly to any modern web browser over HTML5/WebSockets using **[Xpra](https://xpra.org/)** (no VNC client, RDP client, or browser extension required).

---

## Repository Structure

| Directory | Target Platform | Variants | Description |
| :--- | :--- | :--- | :--- |
| **[`cloud_run_xpra/`](./cloud_run_xpra/)** | **Google Cloud Run (Gen2)** | `xpra-chrome`, `xpra-desktop` | Serverless containers listening on `$PORT` (`8080`). Designed for single-instance stateful sessions with IAP authentication and Direct VPC Egress. |
| **[`cloud_workstations_xpra/`](./cloud_workstations_xpra/)** | **Google Cloud Workstations** | `xpra-chrome`, `xpra-gnome` | VM-backed workstation containers running `systemd` as PID 1 and serving Xpra HTML5 on port `80` behind the Cloud Workstations gateway. |

---

## What It Does & Key Features

1. **Two Display Modes:**
   - **Seamless Browser (`xpra-chrome`)**: Runs Google Chrome (`xpra start`) in seamless window-forwarding mode—minimal memory/CPU footprint when you only need a browser inside a target VPC.
   - **Full Linux Desktop (`xpra-desktop` / `xpra-gnome`)**: Runs a complete desktop session (`xfce4-session` on Cloud Run alongside Google Chrome, `xfce4-terminal`, and `google-cloud-cli`; or `ubuntu-desktop-minimal` GNOME on Cloud Workstations).
2. **Tuned for Low-Latency Cloud Run Streaming:**
   - **X11 `MIT-SHM` & `/dev/shm` Shared Memory**: Keeps X11 shared-memory transport enabled between Chrome/GTK, `Xdummy`, and Xpra for zero-copy frame capture.
   - **Fast `libjpeg-turbo` Encoding**: Configured with `--encoding=jpeg --speed=90 --quality=75 --video-encoders=none --csc-modules=none` and `xfwm4` software compositing disabled to avoid CPU-bound software H.264/VP8 encoding stalls on GPU-less vCPUs.
   - **Dynamic Browser Viewport Resizing**: Includes `patch_xpra_desktop_resize.py` so Xpra's RandR 1.6 virtual monitor (`VFB-0`) dynamically resizes to fill the user's browser window.
   - **HTML5 Offscreen Canvas Decoding**: Configured via `default-settings.txt` (`offscreen = true`, `desktop_scaling = off`) to offload frame decoding to a Web Worker in the client browser.
3. **HTML5 Audio Streaming (`PulseAudio` + `GStreamer MP3/WAV`):**
   - Runs an unprivileged PulseAudio server with a dedicated `Xpra-Speaker` null sink (without `module-suspend-on-idle` so the audio clock never stalls).
   - Streams audio over HTML5 MediaSource (`mp3` / `wav`) with `--av-sync=off` so screen frames are never delayed by audio buffering.
   - Includes `patch_xpra_audio.py` to automatically unlock Chrome's Web Autoplay Policy on the user's first click or keypress inside the remote session.

---

## Quickstart: Google Cloud Run (`cloud_run_xpra/`)

### 1. Set Environment Variables
```bash
export PROJECT_ID="your-project-id"
export REGION="us-central1"
export REPO_NAME="cloud-run-images"
```

### 2. Create an Artifact Registry Repository (if needed)
```bash
gcloud artifacts repositories create "${REPO_NAME}" \
  --project="${PROJECT_ID}" \
  --location="${REGION}" \
  --repository-format=docker
```

### 3. Build & Push with Cloud Build

**Option A — Seamless Chrome (`xpra-chrome`):**
```bash
gcloud builds submit ./cloud_run_xpra/xpra-chrome \
  --project="${PROJECT_ID}" \
  --config=./cloud_run_xpra/xpra-chrome/cloudbuild.yaml \
  --substitutions="_IMAGE_NAME=${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO_NAME}/xpra-chrome:latest"
```

**Option B — Full XFCE4 Desktop + Chrome + `gcloud` CLI (`xpra-desktop`):**
```bash
gcloud builds submit ./cloud_run_xpra/xpra-desktop \
  --project="${PROJECT_ID}" \
  --config=./cloud_run_xpra/xpra-desktop/cloudbuild.yaml \
  --substitutions="_IMAGE_NAME=${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO_NAME}/xpra-desktop:latest"
```

### 4. Deploy to Cloud Run (Gen2)
Choose a container (`xpra-chrome` or `xpra-desktop`) and deploy with **Gen2 execution environment**, **CPU always allocated** (`--no-cpu-throttling`), **session affinity**, and **IAP** enabled:

```bash
SERVICE_NAME="xpra-desktop" # or "xpra-chrome"

gcloud beta run deploy "${SERVICE_NAME}" \
  --project="${PROJECT_ID}" \
  --region="${REGION}" \
  --image="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO_NAME}/${SERVICE_NAME}:latest" \
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

> **Private VPC Egress (Optional):** To route traffic from the remote desktop/browser into a private VPC subnet using Cloud Run Direct VPC Egress (recommended over Serverless VPC Access connectors for high-bandwidth streaming), add:
> ```bash
>   --network="your-vpc-name" \
>   --subnet="your-subnet-name" \
>   --vpc-egress=all-traffic
> ```

### 5. Connect to Your Session
- **Via Identity-Aware Proxy (IAP):** Grant your user `roles/run.invoker` (and `roles/iap.httpsResourceAccessor` if using IAP) and open the Cloud Run `https://*.run.app` URL directly in your browser.
- **Via Local Authenticated Proxy (no public access needed):**
  ```bash
  gcloud run services proxy "${SERVICE_NAME}" \
    --project="${PROJECT_ID}" \
    --region="${REGION}" \
    --port=8080
  ```
  Then open [`http://localhost:8080`](http://localhost:8080) in your browser. Click anywhere in the window once connected to automatically unlock HTML5 audio streaming.

---

## Quickstart: Google Cloud Workstations (`cloud_workstations_xpra/`)

See [`cloud_workstations_xpra/README.md`](./cloud_workstations_xpra/README.md) for instructions on building and configuring the `xpra-chrome` and `xpra-gnome` images with a Cloud Workstations cluster and configuration.
