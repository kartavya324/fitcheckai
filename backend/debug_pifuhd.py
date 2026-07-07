"""Debug PIFuHD /generate endpoint — captures the full error response."""
import requests
import base64
import json
from pathlib import Path

# Use a tiny real JPEG (create a 1x1 white pixel JPEG for quick test)
import struct, zlib

def make_tiny_jpeg():
    """Create minimal valid JPEG bytes."""
    import io
    try:
        from PIL import Image
        img = Image.new("RGB", (100, 300), color=(200, 180, 160))
        buf = io.BytesIO()
        img.save(buf, format="JPEG")
        return buf.getvalue()
    except Exception:
        # Fallback: read any existing image
        for p in Path(".").rglob("*.jpg"):
            return p.read_bytes()
        for p in Path(".").rglob("*.png"):
            return p.read_bytes()
        raise RuntimeError("No image found and PIL not available")

print("Creating test image...")
img_bytes = make_tiny_jpeg()
img_b64 = base64.b64encode(img_bytes).decode()
print(f"Image size: {len(img_bytes)} bytes")

print("Posting to http://localhost:8090/generate ...")
try:
    r = requests.post(
        "http://localhost:8090/generate",
        json={"image_base64": img_b64},
        timeout=60,
    )
    print(f"Status: {r.status_code}")
    print("Response:")
    print(json.dumps(r.json(), indent=2))
except Exception as e:
    print(f"Request failed: {e}")
