# Cloud Workstations — Xpra HTML5 GNOME Desktop (`xpra-gnome`)

This custom image extends `us-central1-docker.pkg.dev/cloud-workstations-images/predefined/base` to serve a full **Ubuntu GNOME Desktop** directly on **port `80`** using **Xpra HTML5 desktop forwarding** (`xpra start-desktop :100 --bind-tcp=0.0.0.0:80 --html=on`).

When a developer clicks **Launch** in the Cloud Workstations console (or opens `https://<WORKSTATION_HOST>`), the Cloud Workstations IAM/IAP gateway routes traffic directly to the Xpra HTML5 client on port `80`, rendering the GNOME desktop inside their browser tab with Google Chrome and GNOME Terminal pre-pinned to the Dock.

## Build with Cloud Build

```bash
export PROJECT_ID="your-project-id"
export REGION="europe-west2"
export REPO_NAME="workstation-images"

gcloud builds submit . \
  --config=cloudbuild.yaml \
  --substitutions="_IMAGE_NAME=${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO_NAME}/xpra-gnome:latest"
```

## Create a Cloud Workstation Configuration

```bash
gcloud workstations configs create xpra-gnome-config \
  --project="${PROJECT_ID}" \
  --region="${REGION}" \
  --cluster="${CLUSTER_NAME}" \
  --machine-type="e2-standard-4" \
  --container-custom-image="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO_NAME}/xpra-gnome:latest"
```
