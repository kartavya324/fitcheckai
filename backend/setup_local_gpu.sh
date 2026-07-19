#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────
# FitCheck AI — one-time local GPU setup (Linux / macOS)
#
# Installs everything the real photo→3D-avatar pipeline needs:
#   • Python venv + FastAPI backend deps         (requirements.txt)
#   • PIFuHD GPU inference-server deps            (requirements-gpu.txt)
#   • PyTorch + torchvision (CUDA build)
#   • PIFuHD source (facebookresearch/pifuhd) + its deps
#   • PIFuHD model weights (~1.5GB) + Haar face-cascade
#
# Windows users: run run_windows.bat instead.
# Full walkthrough + troubleshooting: LOCAL_GPU_SETUP.md
#
# Usage:
#   cd backend
#   ./setup_local_gpu.sh                 # CUDA 12.1 wheels (default)
#   TORCH_CUDA=cu118 ./setup_local_gpu.sh   # older driver / broadest compat
#   TORCH_CUDA=cpu   ./setup_local_gpu.sh   # no GPU (setup dry-run only)
# ─────────────────────────────────────────────────────────────────────────
set -euo pipefail

cd "$(dirname "$0")"                    # always run from backend/
TORCH_CUDA="${TORCH_CUDA:-cu121}"      # cu121 | cu118 | cpu
PY="${PYTHON:-python3}"

echo "=================================================="
echo " FitCheck AI — local GPU setup"
echo " torch build: ${TORCH_CUDA}   python: $($PY --version 2>&1)"
echo "=================================================="

# 1. Virtual environment ---------------------------------------------------
if [ ! -d venv ]; then
  echo "[1/6] Creating venv..."
  "$PY" -m venv venv
else
  echo "[1/6] Reusing existing venv"
fi
# shellcheck disable=SC1091
source venv/bin/activate
python -m pip install --upgrade pip

# 2. PyTorch (CUDA-matched wheels) -----------------------------------------
echo "[2/6] Installing torch + torchvision (${TORCH_CUDA})..."
if [ "$TORCH_CUDA" = "cpu" ]; then
  pip install torch torchvision
else
  pip install torch torchvision \
    --index-url "https://download.pytorch.org/whl/${TORCH_CUDA}"
fi

# 3. Python dependencies ---------------------------------------------------
echo "[3/6] Installing backend + GPU-server dependencies..."
pip install -r requirements.txt        # FastAPI API server
pip install -r requirements-gpu.txt    # Flask PIFuHD server + projection stack

# 4. PIFuHD source ---------------------------------------------------------
if [ ! -d pifuhd ]; then
  echo "[4/6] Cloning PIFuHD..."
  git clone https://github.com/facebookresearch/pifuhd.git
  pip install -r pifuhd/requirements.txt   # scikit-image, tqdm, ...
else
  echo "[4/6] PIFuHD already cloned"
fi

# 5. Model weights + Haar cascade (idempotent; skips if present) -----------
echo "[5/6] Downloading PIFuHD weights (~1.5GB) + face cascade..."
python download_weights.py

# 6. Sanity check ----------------------------------------------------------
echo "[6/6] Verifying install..."
python check_deps.py

echo ""
echo "=================================================="
echo " Setup complete."
echo "   Terminal 1:  ./start_pifuhd_server.sh   (GPU, port 8090)"
echo "   Terminal 2:  ./start_backend.sh         (API,  port 8001)"
echo "   Terminal 3:  cd ../frontend && npm install && npm run dev"
echo " Then set AVATAR_MODE=local_pifuhd in backend/.env"
echo "=================================================="
