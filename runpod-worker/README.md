# FitCheck AI — RunPod Avatar Worker

## What this does
Takes a person photo → runs ECON (3D body reconstruction) + 
TeCH (texture baking) → returns a textured .glb avatar

## How to deploy to RunPod

1. Create a RunPod account at runpod.io

2. Build and push the Docker image:
   docker build -t your-dockerhub-username/fitcheckai-avatar:latest .
   docker push your-dockerhub-username/fitcheckai-avatar:latest

3. In RunPod dashboard:
   - Go to Serverless > New Endpoint
   - Select GPU: A40 (48GB) or RTX 4090 (24GB)
   - Container image: your-dockerhub-username/fitcheckai-avatar:latest
   - Container disk: 50GB (ECON+TeCH models are large)
   - Set max workers: 3
   - Set idle timeout: 60 seconds

4. Copy the Endpoint ID from RunPod dashboard

5. Add to backend/.env:
   AVATAR_MODE=runpod
   RUNPOD_API_KEY=your_runpod_api_key
   RUNPOD_ENDPOINT_ID=your_endpoint_id

6. Restart the backend. Real avatar generation is now active.

## Test locally (requires NVIDIA GPU + Docker)
docker run --gpus all -it \
  your-dockerhub-username/fitcheckai-avatar:latest \
  python handler.py

## Estimated costs
- A40 GPU: ~$0.50/hr
- Average job time: 3-5 minutes
- Cost per avatar: ~$0.04-0.08
- First job cold start: +2-3 minutes (model download)
- Subsequent jobs: models cached in container
