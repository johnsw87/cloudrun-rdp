# Cloud Workstations — Xpra HTML5 Seamless Browser (`xpra-chrome`)

This custom image extends `us-central1-docker.pkg.dev/cloud-workstations-images/predefined/base` to serve **Google Chrome** directly on **port `80`** using **Xpra HTML5 seamless window forwarding** (`xpra start :100 --bind-tcp=0.0.0.0:80 --html=on`).

When a developer clicks **Launch** in the Cloud Workstations console (or opens `https://<WORKSTATION_HOST>`), the Cloud Workstations IAM/IAP gateway routes traffic directly to the Xpra HTML5 client on port `80`, rendering a full-window Chrome browser inside their local browser tab with no VNC server or Chrome Remote Desktop setup required.

## Build with Cloud Build

```bash
export PROJECT_ID="your-project-id"
export REGION="europe-west2"
export REPO_NAME="workstation-images"

gcloud builds submit . \
  --config=cloudbuild.yaml \
  --substitutions="_IMAGE_NAME=${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO_NAME}/xpra-chrome:latest"
```

## Create a Cloud Workstation Configuration

```bash
gcloud workstations configs create xpra-chrome-config \
  --project="${PROJECT_ID}" \
  --region="${REGION}" \
  --cluster="${CLUSTER_NAME}" \
  --machine-type="e2-standard-4" \
  --container-custom-image="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO_NAME}/xpra-chrome:latest"
```
