# Cloud Run — Xpra HTML5 Browser & Desktop Containers

Serverless adaptations of the Xpra HTML5 containers designed for **Google Cloud Run** (`--execution-environment=gen2`).

## Key Differences from Cloud Workstations

| Requirement | Cloud Workstations (`cloud_workstations_xpra/`) | Cloud Run (`cloud_run_xpra/`) |
| :--- | :--- | :--- |
| **Init / PID 1** | Runs full `systemd` (`/sbin/init`) inside a dedicated GCE VM | Cloud Run controls PID 1 (`systemd` cannot boot); uses a single session/system `dbus-daemon` + foreground `xpra --daemon=no` |
| **Desktop Environment** | Ubuntu GNOME (`gnome-shell` via `systemd-logind`) | **XFCE4 (`xfce4-session`)** with `xfwm4` compositing disabled + X11 `MIT-SHM` enabled |
| **Port** | Port `80` | `$PORT` (default `8080`) |
| **Chrome Sandbox** | Standard userns sandbox | Requires `--no-sandbox --test-type` inside Cloud Run's container sandbox |
| **Virtual Audio Driver** | PulseAudio virtual sink (`Xpra-Speaker`) + GStreamer (`opus+mka`) streamed via HTML5 MediaSource | Unprivileged PulseAudio (`Xpra-Speaker` null sink without suspend-on-idle) + GStreamer (`mp3` / `wav`, `--av-sync=off`) with automatic HTML5 autoplay unlock on first click/keypress |
| **Session State** | 1 dedicated VM + Persistent Disk per user | Cloud Storage **GCS Fuse** volume mounted at `/mnt/state` (direct symlinks for `~/Downloads`, `~/Documents`, `~/Desktop`, `~/Workspace` + automatic restore & SHA-256 incremental/SIGTERM sync for Chrome profile, `gcloud` auth, XFCE4 settings, and `~/.ssh`) |

## Build & Deploy to Cloud Run (with Persistent GCS Fuse State)

```bash
export PROJECT_ID="your-project-id"
export REGION="europe-west2"
export REPO_NAME="cloud-run-images"
export STATE_BUCKET="${PROJECT_ID}-rdp-state"

# 1. Create a Cloud Storage bucket for persistent user & browser state (once per project)
gcloud storage buckets create "gs://${STATE_BUCKET}" \
  --project="${PROJECT_ID}" \
  --location="${REGION}" \
  --uniform-bucket-level-access

# 2. Build using cloudbuild.yaml (8-vCPU builder + BuildKit inline layer cache)
gcloud builds submit ./xpra-chrome \
  --project="${PROJECT_ID}" \
  --config=./xpra-chrome/cloudbuild.yaml \
  --substitutions="_IMAGE_NAME=${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO_NAME}/xpra-chrome:latest"

# 3. Deploy to Cloud Run Gen2 with GCS Fuse volume mounted at /mnt/state
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
  --add-volume=name=gcs-state,type=cloud-storage,bucket="${STATE_BUCKET}",mount-options="implicit-dirs;uid=1001;gid=1001;file-mode=0666;dir-mode=0777" \
  --add-volume-mount=volume=gcs-state,mount-path=/mnt/state \
  --set-env-vars="GCS_STATE_MOUNT_PATH=/mnt/state" \
  --iap \
  --no-allow-unauthenticated
```

## How GCS Fuse State Persistence Works (`sync_gcs_state.py`)
When a Cloud Storage volume is mounted at `/mnt/state` (or `$GCS_STATE_MOUNT_PATH`), `entrypoint.sh` automatically activates `sync_gcs_state.py`:
1. **Direct GCS Fuse Symlinks (Zero RAM overhead, immediate persistence):**
   - `~/Downloads` -> `/mnt/state/Downloads`
   - `~/Documents` -> `/mnt/state/Documents`
   - `~/Desktop`   -> `/mnt/state/Desktop`
   - `~/Workspace` -> `/mnt/state/Workspace`
2. **Application & Profile Sync (Fast local memory + SHA-256 deduplicated GCS sync):**
   - Because Chrome (`~/.config/google-chrome`) and `gcloud` (`~/.config/gcloud`) rely on SQLite locks and UNIX sockets that are incompatible with direct FUSE mounts, they run in fast container memory and are **restored on container startup**, **incrementally synced every 15 seconds** (only writing to GCS when a file's SHA-256 digest changes, while skipping browser caches/locks), and **flushed on `SIGTERM`** when Cloud Run scales down or replaces an instance.
   - Persisted paths include:
     - `~/.config/google-chrome` -> `/mnt/state/profiles/<K_SERVICE>/google-chrome` (bookmarks, cookies, preferences, local storage)
     - `~/.config/gcloud` -> `/mnt/state/shared/gcloud` (`gcloud auth` credentials & config)
     - `~/.ssh` -> `/mnt/state/shared/ssh` (SSH keys with `0700`/`0600` permissions automatically restored)
     - `~/.config/xfce4` -> `/mnt/state/shared/xfce4` (XFCE4 desktop preferences)
     - `~/.bash_history` -> `/mnt/state/shared/bash_history`

## Accessing Securely
Because the service is deployed with `--no-allow-unauthenticated`, protect it behind **Identity-Aware Proxy (IAP)** on an external Application Load Balancer, or test locally via Cloud Run's authenticated proxy:

```bash
gcloud run services proxy xpra-chrome --project="${PROJECT_ID}" --region="${REGION}" --port=8080
```

## License & Third-Party Software
- Repository build definitions, scripts, and configurations are licensed under the **[Apache License 2.0](../LICENSE)**.
- See **[`THIRD_PARTY_NOTICES.md`](../THIRD_PARTY_NOTICES.md)** for license details on components installed during `docker build` (including Xpra `GPL-2.0-or-later`, Xpra HTML5 `MPL-2.0`, XFCE4/PulseAudio/GStreamer `GPL/LGPL`, and the [Google Chrome Terms of Service](https://www.google.com/chrome/terms/)).
