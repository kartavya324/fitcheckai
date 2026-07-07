@echo off
echo Setting up FitCheck AI backend...
cd /d %~dp0

python -m venv venv
call venv\Scripts\activate

pip install torch==2.5.1+cu118 torchvision==0.20.1+cu118 --index-url https://download.pytorch.org/whl/cu118

pip install -r requirements.txt
pip install flask flask-cors trimesh

echo Installing PIFuHD...
if not exist pifuhd (
    git clone https://github.com/facebookresearch/pifuhd.git
)
cd pifuhd
pip install -r requirements.txt
cd ..

echo Downloading PIFuHD weights (1.5GB)...
python -c "
import requests, os
from pathlib import Path
url = 'https://dl.fbaipublicfiles.com/pifuhd/checkpoints/pifuhd.pt'
path = Path('pifuhd/checkpoints/pifuhd.pt')
path.parent.mkdir(parents=True, exist_ok=True)
if not path.exists():
    print('Downloading...')
    r = requests.get(url, stream=True)
    total = int(r.headers.get('content-length', 0))
    downloaded = 0
    with open(path, 'wb') as f:
        for chunk in r.iter_content(8192):
            f.write(chunk)
            downloaded += len(chunk)
            print(f'\r{downloaded*100//total}%%', end='', flush=True)
    print('\nDone!')
else:
    print('Already downloaded.')
"

echo Setup complete!
pause
