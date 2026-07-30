# FitCheck AI — PIFuHD avatar generation on RunPod serverless.
# Build context = the backend/ directory (so pifuhd/, pifuhd_server.py, etc.
# are available). See README.md for build/deploy commands.
FROM runpod/pytorch:2.2.0-py3.10-cuda12.1.1-devel-ubuntu22.04

WORKDIR /app

# System libs for opencv / rembg
RUN apt-get update && \
    apt-get install -y --no-install-recommends libgl1 libglib2.0-0 wget && \
    rm -rf /var/lib/apt/lists/*

# Python deps (torch/torchvision come from the base image — do NOT reinstall)
COPY runpod/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Pipeline code + PIFuHD network
COPY pifuhd/ ./pifuhd/
COPY pifuhd_server.py texture_projection.py ./
COPY runpod/handler.py ./

# PIFuHD trained weights (~1.5GB) into the path pifuhd_server expects
RUN mkdir -p pifuhd/checkpoints && \
    wget -q -O pifuhd/checkpoints/pifuhd.pt \
    "https://dl.fbaipublicfiles.com/pifuhd/checkpoints/pifuhd.pt"

# Pre-cache the rembg human-seg model so the first request isn't slow
RUN python -c "from rembg import new_session; new_session('u2net_human_seg')" || true

CMD ["python", "-u", "handler.py"]
