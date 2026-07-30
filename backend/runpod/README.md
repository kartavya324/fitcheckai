# FitCheck AI — Cloud Avatar Generation (RunPod Serverless)

Runs the PIFuHD avatar pipeline on a cloud GPU so quality isn't capped by the
local 4GB card. Cloud defaults: **512³ geometry + 4096px texture** (vs local
256 + 2048). This also makes the flagship 3D feature cloud-runnable — the main
SaaS launch blocker.

## What's here
| File | Purpose |
|------|---------|
| `handler.py` | RunPod serverless entrypoint; reuses `pifuhd_server.py` pipeline |
| `Dockerfile` | CUDA + torch base, bakes in PIFuHD code + downloads weights |
| `requirements.txt` | Pipeline deps (torch comes from the base image) |

## Deploy (one-time, ~20–30 min)

Everything below is **your** step — it needs a RunPod account + billing.

### 1. Create a RunPod account
Sign up at https://runpod.io, add credit, and create an **API key**
(Settings → API Keys). Serverless GPU time is ~$0.0002–0.0005/sec; a 512³
avatar (~1–2 min on a 24GB card) costs roughly **$0.02–0.05 per avatar**.

### 2. Build & push the image
From the **`backend/`** directory (the build context must include `pifuhd/`):

```bash
docker build -f runpod/Dockerfile -t YOUR_DOCKERHUB_USER/fitcheck-pifuhd:latest .
docker push YOUR_DOCKERHUB_USER/fitcheck-pifuhd:latest
```

No local Docker? Use RunPod's GitHub-build integration instead: point a new
serverless endpoint at this repo with Dockerfile path `backend/runpod/Dockerfile`.

### 3. Create the serverless endpoint
RunPod console → Serverless → New Endpoint:
- **Container image**: the image you pushed (or the GitHub build)
- **GPU**: 24GB (A5000 / L4 / 3090) — needed for 512³
- **Container disk**: ≥ 15 GB (weights + CUDA)
- **Max workers**: 1 to start; **Idle timeout**: ~30s; **Execution timeout**: 600s
- Copy the **Endpoint ID**.

### 4. Point the app at it
In `backend/.env`:

```
AVATAR_MODE=runpod
RUNPOD_API_KEY=<your key>
RUNPOD_ENDPOINT_ID=<your endpoint id>
```

Restart the backend. `AvatarGenerationService._generate_runpod` already speaks
this handler's protocol (submits to `/run`, polls `/status`, reads
`glb_base64`). No local PIFuHD server needed in this mode.

### 5. Smoke-test the endpoint directly
```bash
curl -X POST https://api.runpod.ai/v2/<ENDPOINT_ID>/run \
  -H "Authorization: Bearer <API_KEY>" -H "Content-Type: application/json" \
  -d '{"input":{"image_base64":"<base64 of a full-body photo>"}}'
# then poll:
curl https://api.runpod.ai/v2/<ENDPOINT_ID>/status/<JOB_ID> \
  -H "Authorization: Bearer <API_KEY>"
```
A `COMPLETED` status with `output.glb_base64` means it works.

## Per-request quality knobs (optional)
The handler accepts overrides in `input`: `resolution` (default 512),
`texture_res` (default 4096). Lower them to trade quality for speed/cost.

## Notes
- First request after a cold start is slower (loads the 1.5GB model).
- Keep the local `AVATAR_MODE=local_pifuhd` path for dev; flip to `runpod`
  for hosted/production. Both use the identical pipeline code.
