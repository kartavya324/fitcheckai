import sys
import base64
import requests
import argparse
from pathlib import Path

def test(image_path: str, recolor: bool):
    print(f"Testing with: {image_path} (recolor: {recolor})")
    
    with open(image_path, "rb") as f:
        image_b64 = base64.b64encode(f.read()).decode()

    print("Sending to PIFuHD server...")
    print("This takes 3-6 minutes on RTX 3050...")
    
    url = "http://localhost:8090/generate"
    if recolor:
        url += "?recolor_debug=true"
    
    try:
        r = requests.post(
            url,
            json={"image_base64": image_b64},
            timeout=600,
        )
        r.raise_for_status()
        result = r.json()
    except requests.ConnectionError:
        print("ERROR: PIFuHD server not running!")
        print("Run start_pifuhd_server.bat first")
        return
    except Exception as e:
        print(f"ERROR: request failed: {e}")
        return

    if "error" in result:
        print(f"ERROR: {result['error']}")
        return

    output_path = "test_avatar_output.glb"
    glb_bytes = base64.b64decode(result["glb_base64"])
    open(output_path, "wb").write(glb_bytes)
    print(f"Saved default avatar to: {output_path}")

    if "recolored_glb_base64" in result:
        recolored_path = "test_avatar_recolored.glb"
        recolored_bytes = base64.b64decode(result["recolored_glb_base64"])
        open(recolored_path, "wb").write(recolored_bytes)
        print(f"Saved recolored avatar to: {recolored_path}")

    print(f"SUCCESS!")
    print(f"GLB size: {result['size_bytes']} bytes")
    if "recolored_size_bytes" in result:
        print(f"Recolored GLB size: {result['recolored_size_bytes']} bytes")
    print(f"Preview at: https://gltf-viewer.donmccurdy.com")
    print(f"Drag the .glb file into that website to see the 3D avatar")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test avatar generation directly without the frontend.")
    parser.add_argument("image_path", type=str, help="Path to the input image file.")
    parser.add_argument("--recolor", action="store_true", help="Enable recoloring debug mode.")
    args = parser.parse_args()
    
    test(args.image_path, args.recolor)
