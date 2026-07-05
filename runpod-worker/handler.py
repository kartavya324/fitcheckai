import runpod
import base64
import os
import subprocess
import tempfile
import json
from pathlib import Path


def download_models():
    """Download ECON and TeCH model weights if not cached."""
    # ECON weights
    econ_path = Path("/workspace/models/econ")
    if not econ_path.exists():
        econ_path.mkdir(parents=True, exist_ok=True)
        os.system(
            "wget -q -O /workspace/models/econ/econ.pt "
            "https://github.com/YuliangXiu/ECON/releases/download/"
            "v0.1/econ.pt"
        )
    
    # TeCH weights
    tech_path = Path("/workspace/models/tech")
    if not tech_path.exists():
        tech_path.mkdir(parents=True, exist_ok=True)
        # TeCH downloads handled by the TeCH repo itself on first run


def run_econ(image_path: str, output_dir: str) -> str:
    """
    Run ECON reconstruction on input image.
    Returns path to output .obj mesh file.
    """
    cmd = [
        "python", "-m", "apps.infer",
        "--config", "configs/econ.yaml",
        "--in_dir", os.path.dirname(image_path),
        "--out_dir", output_dir,
        "--export_video", "False",
    ]
    result = subprocess.run(
        cmd,
        cwd="/workspace/ECON",
        capture_output=True,
        text=True,
        timeout=180,
    )
    if result.returncode != 0:
        raise RuntimeError(f"ECON failed: {result.stderr}")
    
    # Find output obj file
    output_path = Path(output_dir)
    obj_files = list(output_path.rglob("*.obj"))
    if not obj_files:
        raise RuntimeError(f"ECON produced no .obj file. stdout: {result.stdout}")
    
    return str(obj_files[0])


def run_tech(obj_path: str, image_path: str, output_dir: str) -> str:
    """
    Run TeCH texture baking on the ECON mesh.
    Returns path to output .glb file.
    """
    cmd = [
        "python", "inference.py",
        "--mesh_path", obj_path,
        "--image_path", image_path,
        "--output_dir", output_dir,
        "--export_glb", "True",
    ]
    result = subprocess.run(
        cmd,
        cwd="/workspace/TeCH",
        capture_output=True,
        text=True,
        timeout=300,
    )
    if result.returncode != 0:
        raise RuntimeError(f"TeCH failed: {result.stderr}")
    
    output_path = Path(output_dir)
    glb_files = list(output_path.rglob("*.glb"))
    if not glb_files:
        raise RuntimeError(f"TeCH produced no .glb file. stdout: {result.stdout}")
    
    return str(glb_files[0])


def handler(job):
    """
    RunPod serverless handler.
    
    Input:
      job["input"]["image_base64"] — base64 encoded person photo
      job["input"]["pipeline"] — "econ_tech" (only option for now)
      job["input"]["output_format"] — "glb" (only option for now)
    
    Output:
      {"glb_base64": "<base64 encoded .glb file>"}
    """
    try:
        job_input = job["input"]
        
        # Decode input image
        image_b64 = job_input.get("image_base64")
        if not image_b64:
            return {"error": "image_base64 is required"}
        
        image_bytes = base64.b64decode(image_b64)
        
        # Write to temp file
        with tempfile.TemporaryDirectory() as tmpdir:
            image_path = os.path.join(tmpdir, "input.jpg")
            with open(image_path, "wb") as f:
                f.write(image_bytes)
            
            econ_output_dir = os.path.join(tmpdir, "econ_output")
            os.makedirs(econ_output_dir, exist_ok=True)
            
            tech_output_dir = os.path.join(tmpdir, "tech_output")
            os.makedirs(tech_output_dir, exist_ok=True)
            
            # Download models on first run
            download_models()
            
            # Step 1: ECON reconstruction
            print("Running ECON...")
            obj_path = run_econ(image_path, econ_output_dir)
            print(f"ECON done: {obj_path}")
            
            # Step 2: TeCH texture baking
            print("Running TeCH...")
            glb_path = run_tech(obj_path, image_path, tech_output_dir)
            print(f"TeCH done: {glb_path}")
            
            # Read and encode output
            with open(glb_path, "rb") as f:
                glb_bytes = f.read()
            
            glb_b64 = base64.b64encode(glb_bytes).decode()
            
            return {
                "glb_base64": glb_b64,
                "glb_size_bytes": len(glb_bytes),
            }
    
    except Exception as e:
        import traceback
        return {
            "error": str(e),
            "traceback": traceback.format_exc(),
        }


if __name__ == "__main__":
    runpod.serverless.start({"handler": handler})
