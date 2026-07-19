#!/usr/bin/env bash
# Start the PIFuHD GPU inference server (photo → 3D mesh → textured .glb).
# Listens on http://127.0.0.1:8090. Requires ./setup_local_gpu.sh to have run.
# Windows: use start_pifuhd_server.bat instead.
set -euo pipefail
cd "$(dirname "$0")"
# shellcheck disable=SC1091
source venv/bin/activate

# Optional: force a fixed reconstruction resolution (else auto-picked from VRAM).
# export PIFUHD_RESOLUTION=512
# export AVATAR_TARGET_FACES=120000

exec python pifuhd_server.py
