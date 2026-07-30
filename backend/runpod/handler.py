"""
RunPod serverless handler for FitCheck AI avatar generation.

Runs the SAME PIFuHD pipeline as the local pifuhd_server.py, but on a cloud
GPU with the memory headroom for high quality: 512³ geometry + 4096px texture
(the 4GB local card is capped at 256 + 2048). The image is deployed with the
PIFuHD code + weights baked in, so cold start only pays for loading the model.

Input  (event["input"]):
  image_base64        : required — the person photo (JPEG/PNG/WebP/HEIC)
  back_image_base64   : optional — real back photo for the avatar's back
  resolution          : optional — marching-cubes grid (default 512)
  texture_res         : optional — colour projection resolution (default 4096)

Output:
  { "glb_base64": <str>, "size_bytes": <int> }   on success
  { "error": <str> }                              on failure
"""
import os
import base64
import tempfile
import traceback
from pathlib import Path

import runpod

# Cloud-quality defaults. A 24GB GPU handles 512³ + 4096 texture comfortably;
# override per-request via the input fields below.
os.environ.setdefault("PIFUHD_RESOLUTION", "512")
os.environ.setdefault("AVATAR_TEXTURE_RES", "4096")
os.environ.setdefault("AVATAR_TARGET_FACES", "300000")

# Import the pipeline from the shared module (baked into the image at /app).
from pifuhd_server import run_pifuhd, prepare_input, convert_to_glb  # noqa: E402


def handler(event):
    try:
        data = event.get("input") or {}
        if "image_base64" not in data:
            return {"error": "image_base64 required"}

        # Per-request quality overrides
        if data.get("resolution"):
            os.environ["PIFUHD_RESOLUTION"] = str(data["resolution"])
        if data.get("texture_res"):
            os.environ["AVATAR_TEXTURE_RES"] = str(data["texture_res"])

        image_bytes = base64.b64decode(data["image_base64"])

        with tempfile.TemporaryDirectory() as tmp:
            img_path = os.path.join(tmp, "input.jpg")
            with open(img_path, "wb") as f:
                f.write(image_bytes)

            back_img_path = None
            if data.get("back_image_base64"):
                back_img_path = os.path.join(tmp, "back.jpg")
                with open(back_img_path, "wb") as f:
                    f.write(base64.b64decode(data["back_image_base64"]))

            # 1) Reconstruct mesh
            obj_path = run_pifuhd(img_path, tmp)

            # 2) High-res texture from the same person-filled crop
            hires = int(os.environ.get("AVATAR_TEXTURE_RES", "4096"))
            texture_source = os.path.join(tmp, "input", "person.jpg")
            rect = None
            try:
                from PIL import Image
                hires_path = os.path.join(tmp, "input", "person_hires.jpg")
                prepare_input(img_path, hires_path, target=hires)
                with Image.open(hires_path) as im:
                    hw, hh = im.size
                texture_source = hires_path
                rect = [0, 0, hw, hh]
            except Exception as e:
                print(f"Hi-res texture prep failed ({e}); using 512 crop", flush=True)

            # 3) Textured GLB
            glb_path = convert_to_glb(
                obj_path, tmp, texture_source, rect, back_image_path=back_img_path
            )
            glb_bytes = Path(glb_path).read_bytes()

        return {
            "glb_base64": base64.b64encode(glb_bytes).decode(),
            "size_bytes": len(glb_bytes),
        }

    except Exception as e:
        tb = traceback.format_exc()
        print(tb, flush=True)
        return {"error": str(e), "traceback": tb}


runpod.serverless.start({"handler": handler})
