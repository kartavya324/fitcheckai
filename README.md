# FitCheck AI — Virtual Try-On & 3D Avatars

Upload a photo, get a personal **3D avatar**, and **try clothes on it** — in 2D
(photo) or in 3D (on your avatar).

- **2D try-on** — dress a photo in a garment (hosted IDM-VTON, no GPU needed).
- **3D avatar** — reconstruct a textured 3D body from one photo
  ([PIFuHD](https://github.com/facebookresearch/pifuhd)).
- **3D try-on** — apply a garment and re-project it onto your avatar mesh.

---

## Repository layout

```
fitcheckai/
├── frontend/         React + Vite + TanStack Start UI (Three.js 3D viewer)
├── backend/          FastAPI API + PIFuHD GPU server + projection pipeline
│   ├── app/                FastAPI app (uploads, jobs, /files, avatar routes)
│   ├── pifuhd_server.py    Flask GPU server: photo → 3D mesh → textured .glb
│   ├── texture_projection.py   Photo-to-mesh colour projection
│   ├── setup_local_gpu.sh / run_windows.bat   One-time GPU setup
│   └── LOCAL_GPU_SETUP.md  Full local-GPU walkthrough + troubleshooting
└── runpod-worker/    Optional cloud-GPU worker (avatars without a local GPU)
```

**Ports:** frontend `8080` · backend API `8001` · PIFuHD GPU server `8090`.

---

## Choose how avatars are generated

Set `AVATAR_MODE` in `backend/.env`:

| Mode | GPU? | Use when |
|---|---|---|
| `local_pifuhd` | NVIDIA GPU (8 GB+) | You want the real feature on your machine. **→ [LOCAL_GPU_SETUP.md](backend/LOCAL_GPU_SETUP.md)** |
| `runpod` | Cloud GPU | No local GPU; offload to RunPod. **→ [runpod-worker/README.md](runpod-worker/README.md)** |
| `stub` | None | Development/demo — placeholder `.glb` drives the whole UI, no ML. |

The 2D try-on path (`GENERATION_MODE=replicate_2d`) is hosted and needs no GPU,
so 2D try-on and the stub avatar flow run on any machine.

---

## Quickstart

### A) Real 3D avatars on a local GPU
Full instructions (hardware, CUDA, quality tuning): **[backend/LOCAL_GPU_SETUP.md](backend/LOCAL_GPU_SETUP.md)**.
```bash
cd backend
./setup_local_gpu.sh          # Windows: run_windows.bat  (one time)
cp .env.example .env          # then set AVATAR_MODE=local_pifuhd
./start_pifuhd_server.sh      # terminal 1 — GPU server  (Windows: .bat)
./start_backend.sh            # terminal 2 — API         (Windows: .bat)
cd ../frontend && npm install && npm run dev   # terminal 3
```
Open http://localhost:8080/avatar.

### B) No GPU (UI / 2D try-on / stub avatar)
```bash
# backend
cd backend
python -m venv venv && source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env          # set AVATAR_MODE=stub
python -m uvicorn app.main:app --reload --port 8001

# frontend (second terminal)
cd frontend && npm install && npm run dev
```
Open http://localhost:8080. The avatar page serves a placeholder 3D model so
you can exercise upload → job → 3D viewer without a GPU.

---

## Tech stack

- **Frontend:** React, TypeScript, Vite, TanStack Start/Router, Tailwind,
  Three.js (`AvatarViewer3D`), Framer Motion.
- **Backend:** FastAPI, Pydantic, SQLite job store, static `/files` serving.
- **3D:** PIFuHD (PyTorch) for reconstruction, `trimesh` for mesh cleanup /
  decimation / GLB export, `rembg` for segmentation, calibrated photo-to-mesh
  colour projection.
- **2D try-on:** IDM-VTON (HuggingFace Space) via `gradio_client`.

See [backend/BACKEND_ARCHITECTURE.md](backend/BACKEND_ARCHITECTURE.md) for the
API design and [backend/README.md](backend/README.md) for backend specifics.
