# FitCheck AI — API server (FastAPI).
# NOTE: this image runs the web API only. The GPU avatar pipeline (PIFuHD)
# runs separately — locally via pifuhd_server.py, or in the cloud via
# backend/runpod/. In prod set AVATAR_MODE=runpod so the API needs no GPU.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# System libs some wheels need (Pillow/opencv/rembg at runtime)
RUN apt-get update && \
    apt-get install -y --no-install-recommends libgl1 libglib2.0-0 && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
# torch is NOT needed by the API image (GPU work is out-of-process); everything
# else installs from requirements. gunicorn drives uvicorn workers in prod.
RUN pip install -r requirements.txt gunicorn

COPY . .

EXPOSE 8001
ENTRYPOINT ["./docker-entrypoint.sh"]
