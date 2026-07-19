# FitCheck AI — Local GPU Setup (Real 3D Avatars)

Run the **full** feature on your own machine: upload a photo → get a textured
**3D avatar** → **try clothes on it in 3D**. Reconstruction runs locally with
[PIFuHD](https://github.com/facebookresearch/pifuhd), so you need an NVIDIA GPU.

> No GPU? Two options: set `AVATAR_MODE=stub` for a placeholder avatar that
> exercises the whole UI, or `AVATAR_MODE=runpod` to offload reconstruction to
> a cloud GPU (see [`../runpod-worker/README.md`](../runpod-worker/README.md)).

---

## 1. What runs where

| Service | Port | Purpose |
|---|---|---|
| **PIFuHD server** (`pifuhd_server.py`, Flask) | `8090` | Photo → 3D mesh → textured `.glb`. Uses the GPU. Also re-textures the mesh for try-on (`/recolor`). |
| **Backend API** (`app.main`, FastAPI) | `8001` | Uploads, job queue, serves avatars at `/files`. Calls the PIFuHD server. |
| **Frontend** (Vite/React) | `8080` | UI. Talks to the backend API. |

Flow: **Frontend → Backend API → PIFuHD server (GPU)**.

---

## 2. Hardware & prerequisites

- **NVIDIA GPU** with a current driver. VRAM sets the default avatar quality
  (auto-detected): **≥16 GB → 512³**, **≥8 GB → 384³**, **<8 GB → 256³**.
  4 GB works at 256³. More VRAM = crisper face/body.
- **~6 GB free disk** (PIFuHD weights ~1.5 GB, `rembg`/PyTorch, node modules).
- **Python 3.10–3.11**, **Node 18+**, and **git**.
- First avatar is slower: `rembg` downloads its segmentation model (~176 MB)
  once, and PyTorch warms up.

---

## 3. Install (one time)

**Linux / macOS**
```bash
cd backend
./setup_local_gpu.sh                 # CUDA 12.1 wheels (default)
# TORCH_CUDA=cu118 ./setup_local_gpu.sh   # older driver / broadest compatibility
```

**Windows**
```bat
cd backend
run_windows.bat
:: set CUDA=cu118 & run_windows.bat   :: to use CUDA 11.8 wheels
```

The script creates a `venv`, installs PyTorch (CUDA build) +
[`requirements.txt`](requirements.txt) + [`requirements-gpu.txt`](requirements-gpu.txt),
clones PIFuHD, downloads the weights + face cascade, and verifies the install.

> **Which CUDA build?** `cu121` suits modern GPUs (RTX 30/40, A100, H100).
> Use `cu118` for older drivers. Check yours with `nvidia-smi` (top-right).

---

## 4. Configure

```bash
cd backend
cp .env.example .env
```

In `.env` set:
```env
AVATAR_MODE=local_pifuhd
LOCAL_INFERENCE_URL=http://127.0.0.1:8090
```
Point the frontend at the API (already the default in `frontend/.env`):
```env
VITE_API_BASE_URL=http://127.0.0.1:8001
```

---

## 5. Run (three terminals)

```bash
# 1 — GPU reconstruction server
cd backend && ./start_pifuhd_server.sh      # Windows: start_pifuhd_server.bat

# 2 — API
cd backend && ./start_backend.sh            # Windows: start_backend.bat

# 3 — frontend
cd frontend && npm install && npm run dev
```

The PIFuHD server prints your GPU, VRAM, and the chosen resolution on startup —
confirm it detected the GPU. Check it any time:
```bash
curl http://127.0.0.1:8090/health
# {"status":"ok","gpu":true,"gpu_name":"NVIDIA GeForce RTX 4090"}
```

Then open **http://localhost:8080/avatar**.
(Vite uses the next free port if 8080 is taken — watch its terminal, and add
that origin to `CORS_ORIGINS` in `backend/.env` if it differs.)

---

## 6. Use it

1. **Create Your 3D Avatar** — upload a full-body, front-facing photo
   (optionally add a back photo for a real back instead of a synthesized one).
   *Generate Avatar* → reconstruction runs on the GPU (a few minutes the first
   time) → the textured 3D model appears in the viewer (drag to rotate, scroll
   to zoom).
2. **Try Clothes On This Avatar** — upload a garment photo, pick
   Top / Bottom / Dress, *Try It On*. The garment is applied with 2D try-on
   (IDM-VTON) and re-projected onto your mesh. Toggle **Original / New Outfit**
   under the viewer to compare.

---

## 7. Getting a "perfect" avatar

**The photo matters most** — plain light background, full body head-to-feet,
face forward, arms slightly away from the torso, even lighting, fitted clothes,
one person. (The upload page's *Photo tips* card lists these.)

**Quality knobs** (in `backend/.env`, read by the PIFuHD server):

| Setting | Effect | Try |
|---|---|---|
| `PIFUHD_RESOLUTION` | Marching-cubes grid. Higher → sharper face/body, more VRAM + time. Auto-falls back on OOM. | `512` on a 16 GB+ GPU |
| `AVATAR_TARGET_FACES` | Mesh detail after decimation. Higher → crisper, larger `.glb` (slower load). Default `80000`. | `120000` for close-ups |
| Back photo | Real back texture instead of a synthesized wrap. | Upload one at generation |

Set them before starting the PIFuHD server, e.g.:
```bash
PIFUHD_RESOLUTION=512 AVATAR_TARGET_FACES=120000 ./start_pifuhd_server.sh
```

---

## 8. Troubleshooting

**503 "Local PIFuHD server is not running"** — start `pifuhd_server.py`
(terminal 1) and confirm `curl http://127.0.0.1:8090/health` returns `gpu:true`.

**CUDA out of memory** — expected on smaller GPUs at high resolution. The server
automatically retries at a coarser grid (512 → 384 → 256), so it still finishes.
To skip the failed attempt, set a lower `PIFUHD_RESOLUTION`. Close other
GPU apps. One reconstruction runs at a time (requests queue) by design.

**`onnxruntime-gpu` fails to load / CUDA-cuDNN mismatch** — background removal
falls back to CPU where possible, but for a clean fix swap to the CPU build:
`pip uninstall onnxruntime-gpu && pip install onnxruntime` (a bit slower).

**"No CUDA GPU found" at startup** — driver/toolkit mismatch. Verify with
`nvidia-smi`, then `python check_deps.py` (prints `CUDA available: True/False`).
Reinstall torch with the matching `TORCH_CUDA`/`CUDA` build.

**`ModuleNotFoundError: apps.simple_test`** — PIFuHD didn't clone. Re-run setup,
or `git clone https://github.com/facebookresearch/pifuhd.git` inside `backend/`.

**HEIC/HEIF photo rejected** — ensure `pillow-heif` installed
(it's in `requirements-gpu.txt`); the frontend also converts HEIC→JPEG on-device.

**First run hangs at ~92%** — one-time `rembg` model download (~176 MB) during
photo analysis. It completes; subsequent runs are fast.

**Avatar looks grey / untextured** — the source photo had no clear person on a
plain background. Retry with a cleaner full-body shot (see §7).
