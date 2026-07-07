import os
import sys
import base64
import tempfile
import subprocess
import traceback
import shutil
from pathlib import Path
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

BASE_DIR = Path(__file__).parent
PIFUHD_DIR = BASE_DIR / "pifuhd"
CHECKPOINT_PATH = PIFUHD_DIR / "checkpoints" / "pifuhd.pt"


def check_setup():
    if not PIFUHD_DIR.exists():
        raise RuntimeError("PIFuHD not found. Run run_windows.bat first.")
    if not CHECKPOINT_PATH.exists():
        raise RuntimeError("Model weights not found. Run run_windows.bat first.")


def run_pifuhd(image_path: str, output_dir: str) -> str:
    input_dir = Path(output_dir) / "input"
    input_dir.mkdir(parents=True, exist_ok=True)
    dest = input_dir / "person.jpg"
    shutil.copy2(image_path, str(dest))

    # Write bounding rect file for --use_rect mode
    from PIL import Image
    with Image.open(image_path) as img:
        width, height = img.size
    
    rect_path = input_dir / "person_rect.txt"
    with open(rect_path, "w") as f:
        f.write(f"0 0 {width} {height}\n")

    out_dir = Path(output_dir) / "result"
    out_dir.mkdir(parents=True, exist_ok=True)

    cmd = [
        sys.executable, "-m", "apps.simple_test",
        "--input_path", str(input_dir),
        "--out_path", str(out_dir),
        "--resolution", "256",
        "--use_rect",
    ]

    env = os.environ.copy()
    env["CUDA_VISIBLE_DEVICES"] = "0"

    result = subprocess.run(
        cmd,
        cwd=str(PIFUHD_DIR),
        capture_output=True,
        text=True,
        timeout=600,
        env=env,
    )

    if result.returncode != 0:
        raise RuntimeError(
            f"PIFuHD failed.\nSTDOUT: {result.stdout}\nSTDERR: {result.stderr}"
        )

    obj_files = list(out_dir.rglob("*.obj"))
    if not obj_files:
        raise RuntimeError(
            f"PIFuHD produced no .obj file.\n"
            f"STDOUT: {result.stdout}\nSTDERR: {result.stderr}"
        )

    return str(obj_files[0])


def convert_to_glb(obj_path: str, output_dir: str) -> str:
    import trimesh
    glb_path = str(Path(output_dir) / "avatar.glb")
    mesh = trimesh.load(obj_path, force="mesh")
    mesh.export(glb_path)
    return glb_path


@app.route("/health", methods=["GET"])
def health():
    try:
        check_setup()
        import torch
        gpu = torch.cuda.is_available()
        name = torch.cuda.get_device_name(0) if gpu else "none"
        return jsonify({
            "status": "ok",
            "gpu": gpu,
            "gpu_name": name,
        })
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500


@app.route("/generate", methods=["POST"])
def generate():
    try:
        data = request.get_json()
        if not data or "image_base64" not in data:
            return jsonify({"error": "image_base64 required"}), 400

        image_bytes = base64.b64decode(data["image_base64"])

        with tempfile.TemporaryDirectory() as tmp:
            img_path = os.path.join(tmp, "input.jpg")
            open(img_path, "wb").write(image_bytes)

            print(f"Running PIFuHD on {len(image_bytes)} byte image...", flush=True)
            obj_path = run_pifuhd(img_path, tmp)
            print(f"PIFuHD done: {obj_path}", flush=True)

            glb_path = convert_to_glb(obj_path, tmp)
            print(f"GLB ready: {glb_path}", flush=True)

            glb_bytes = open(glb_path, "rb").read()
            glb_b64 = base64.b64encode(glb_bytes).decode()

            return jsonify({
                "glb_base64": glb_b64,
                "size_bytes": len(glb_bytes),
            })

    except Exception as e:
        tb = traceback.format_exc()
        print(tb, flush=True)
        with open("last_error.log", "w") as f:
            f.write(tb)
        return jsonify({"error": str(e), "traceback": tb}), 500


if __name__ == "__main__":
    print("=" * 50, flush=True)
    print("FitCheck AI — PIFuHD Server", flush=True)
    print("=" * 50, flush=True)
    check_setup()
    import torch
    if torch.cuda.is_available():
        print(f"GPU: {torch.cuda.get_device_name(0)}", flush=True)
    else:
        print("WARNING: No GPU found", flush=True)
    print("Server: http://localhost:8090", flush=True)
    print("=" * 50, flush=True)
    app.run(host="0.0.0.0", port=8090, debug=False)
