"""Download PIFuHD model weights (pifuhd.pt, ~1.5GB)."""
import requests
from pathlib import Path
import sys

url = "https://dl.fbaipublicfiles.com/pifuhd/checkpoints/pifuhd.pt"
path = Path("pifuhd/checkpoints/pifuhd.pt")
path.parent.mkdir(parents=True, exist_ok=True)

if path.exists():
    print(f"Already downloaded: {path} ({path.stat().st_size // 1024 // 1024} MB)")
else:
    print("Downloading PIFuHD weights (1.5GB)...")
    print("URL:", url)

    try:
        r = requests.get(url, stream=True, timeout=30)
        r.raise_for_status()
        total = int(r.headers.get("content-length", 0))
        downloaded = 0

        with open(path, "wb") as f:
            for chunk in r.iter_content(chunk_size=65536):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total:
                        pct = downloaded * 100 // total
                        mb = downloaded // 1024 // 1024
                        total_mb = total // 1024 // 1024
                        print(f"\r  {pct}% — {mb}/{total_mb} MB", end="", flush=True)

        print(f"\nDone! Saved to {path}")
    except Exception as e:
        print(f"\nERROR: {e}")
        if path.exists():
            path.unlink()
        sys.exit(1)

# Download Haar cascade file for face detection
cascade_url = "https://raw.githubusercontent.com/opencv/opencv/master/data/haarcascades/haarcascade_frontalface_default.xml"
cascade_path = Path("assets/haarcascade_frontalface_default.xml")
cascade_path.parent.mkdir(parents=True, exist_ok=True)

if cascade_path.exists():
    print(f"Already downloaded: {cascade_path}")
else:
    print("Downloading Haar cascade frontal face xml...")
    try:
        r = requests.get(cascade_url, timeout=30)
        r.raise_for_status()
        cascade_path.write_bytes(r.content)
        print(f"Done! Saved to {cascade_path}")
    except Exception as e:
        print(f"ERROR downloading cascade xml: {e}")

