@echo off
REM ─────────────────────────────────────────────────────────────────────
REM  FitCheck AI — one-time local GPU setup (Windows)
REM  Linux/macOS users: run ./setup_local_gpu.sh instead.
REM  Full walkthrough + troubleshooting: LOCAL_GPU_SETUP.md
REM
REM  Torch CUDA build: set CUDA before running (default cu121).
REM    set CUDA=cu118 & run_windows.bat   (older driver / broadest compat)
REM ─────────────────────────────────────────────────────────────────────
echo Setting up FitCheck AI backend...
cd /d %~dp0
if "%CUDA%"=="" set CUDA=cu121

echo [1/6] Creating venv...
python -m venv venv
call venv\Scripts\activate
python -m pip install --upgrade pip

echo [2/6] Installing torch + torchvision (%CUDA%)...
pip install torch torchvision --index-url https://download.pytorch.org/whl/%CUDA%

echo [3/6] Installing backend + GPU-server dependencies...
pip install -r requirements.txt
pip install -r requirements-gpu.txt

echo [4/6] Cloning PIFuHD...
if not exist pifuhd (
    git clone https://github.com/facebookresearch/pifuhd.git
    pip install -r pifuhd\requirements.txt
)

echo [5/6] Downloading PIFuHD weights (~1.5GB) + face cascade...
python download_weights.py

echo [6/6] Verifying install...
python check_deps.py

echo.
echo ==================================================
echo  Setup complete.
echo    Window 1:  start_pifuhd_server.bat   (GPU, port 8090)
echo    Window 2:  start_backend.bat         (API,  port 8001)
echo    Window 3:  cd ..\frontend ^&^& npm install ^&^& npm run dev
echo  Then set AVATAR_MODE=local_pifuhd in backend\.env
echo ==================================================
pause

