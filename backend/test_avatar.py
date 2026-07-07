"""
Test avatar generation directly without the frontend.
Usage: python test_avatar.py path\to\person_photo.jpg
"""
import sys
import base64
import requests
from pathlib import Path

def test(image_path: str):
    print(f"Testing with: {image_path}")
    
    with open(image_path, "rb") as f:
        image_b64 = base64.b64encode(f.read()).decode()

    print("Sending to PIFuHD server...")
    print("This takes 3-6 minutes on RTX 3050...")
    
    try:
        r = requests.post(
            "http://localhost:8090/generate",
            json={"image_base64": image_b64},
            timeout=400,
        )
        r.raise_for_status()
        result = r.json()
    except requests.ConnectionError:
        print("ERROR: PIFuHD server not running!")
        print("Run start_pifuhd_server.bat first")
        return

    if "error" in result:
        print(f"ERROR: {result['error']}")
        return

    output_path = "test_avatar_output.glb"
    glb_bytes = base64.b64decode(result["glb_base64"])
    open(output_path, "wb").write(glb_bytes)

    print(f"SUCCESS!")
    print(f"GLB size: {result['size_bytes']} bytes")
    print(f"Saved to: {output_path}")
    print(f"Preview at: https://gltf-viewer.donmccurdy.com")
    print(f"Drag the .glb file into that website to see the 3D avatar")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python test_avatar.py <image_path>")
        sys.exit(1)
    test(sys.argv[1])
