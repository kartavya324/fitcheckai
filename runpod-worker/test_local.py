"""
Test the handler locally without RunPod.
Run: python test_local.py path/to/person_photo.jpg
"""
import sys
import base64
import json
from handler import handler

def test(image_path: str):
    with open(image_path, "rb") as f:
        image_b64 = base64.b64encode(f.read()).decode()
    
    job = {
        "id": "test-job-001",
        "input": {
            "image_base64": image_b64,
            "pipeline": "econ_tech",
            "output_format": "glb",
        }
    }
    
    print("Running handler...")
    result = handler(job)
    
    if "error" in result:
        print(f"ERROR: {result['error']}")
        print(result.get("traceback", ""))
        return
    
    glb_bytes = base64.b64decode(result["glb_base64"])
    output_path = "test_output.glb"
    with open(output_path, "wb") as f:
        f.write(glb_bytes)
    
    print(f"SUCCESS: {result['glb_size_bytes']} bytes")
    print(f"Saved to: {output_path}")
    print("Open test_output.glb in https://gltf-viewer.donmccurdy.com to preview")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python test_local.py <image_path>")
        sys.exit(1)
    test(sys.argv[1])
