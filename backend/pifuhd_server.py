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
from texture_projection import project_texture_onto_mesh

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


def remove_background(image_path: str, output_path: str) -> str:
    try:
        from rembg import remove, new_session
        from PIL import Image
        import io
        import numpy as np

        print("Removing background...")
        
        # u2net_human_seg is specifically trained for people
        # Much better than the default u2net model
        try:
            session = new_session('u2net_human_seg')
        except Exception:
            session = new_session('u2net')

        with open(image_path, "rb") as f:
            input_data = f.read()

        output_data = remove(input_data, session=session)
        img = Image.open(io.BytesIO(output_data)).convert("RGBA")
        
        # Remove small floating islands using connected components
        alpha_array = np.array(img)[:, :, 3]
        from scipy import ndimage
        
        # Fill small holes first
        filled = ndimage.binary_fill_holes(alpha_array > 128)
        
        # Label connected components
        labeled, num = ndimage.label(filled)
        if num > 1:
            sizes = ndimage.sum(
                filled, labeled, range(1, num + 1)
            )
            largest_label = np.argmax(sizes) + 1
            clean_mask = (labeled == largest_label).astype(np.uint8) * 255
            
            # Apply clean mask to alpha
            img_array = np.array(img)
            img_array[:, :, 3] = clean_mask
            img = Image.fromarray(img_array)
            print(f"Removed {num - 1} disconnected regions")

        # Slightly expand the mask to avoid cutting off edges
        from scipy.ndimage import binary_dilation
        alpha_array = np.array(img)[:, :, 3]
        dilated = binary_dilation(
            alpha_array > 128, 
            iterations=3
        ).astype(np.uint8) * 255
        img_array = np.array(img)
        img_array[:, :, 3] = np.minimum(dilated, 
            img_array[:, :, 3] + 50)
        img = Image.fromarray(img_array)

        # White background composite
        background = Image.new("RGB", img.size, (255, 255, 255))
        background.paste(img, mask=img.split()[3])
        background.save(output_path, "JPEG", quality=95)
        
        print(f"Background removed: {output_path}")
        return output_path

    except Exception as e:
        print(f"Background removal error: {e}")
        import traceback
        traceback.print_exc()
        # Return original on failure
        return image_path


def preprocess_image(image_path: str, output_path: str) -> str:
    """
    Resize and center the person for better PIFuHD results.
    """
    from PIL import Image, ImageOps

    img = Image.open(image_path).convert("RGB")

    # Resize to square 512x512 with padding
    target_size = 512
    img.thumbnail((target_size, target_size), Image.LANCZOS)

    # Pad to square with white background
    padded = Image.new("RGB", (target_size, target_size), (255, 255, 255))
    offset = (
        (target_size - img.width) // 2,
        (target_size - img.height) // 2,
    )
    padded.paste(img, offset)
    padded.save(output_path, "JPEG", quality=95)

    print(f"Preprocessed image: {img.size} -> {target_size}x{target_size}")
    return output_path


def run_pifuhd(image_path: str, output_dir: str) -> str:
    input_dir = Path(output_dir) / "input"
    input_dir.mkdir(parents=True, exist_ok=True)

    # Preprocess first
    preprocessed_path = str(input_dir / "preprocessed.jpg")
    preprocess_image(image_path, preprocessed_path)
    print("[OK] Step 1/4: Image preprocessed", flush=True)

    # Then remove background
    dest = input_dir / "person.jpg"
    cleaned_path = remove_background(preprocessed_path, str(dest))
    print("[OK] Step 2/4: Background removed", flush=True)
    if cleaned_path != str(dest):
        shutil.copy2(cleaned_path, str(dest))

    # Write bounding rect file for --use_rect mode
    from PIL import Image
    with Image.open(str(dest)) as img:
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
        "--loadSize", "1024",
        "--resolution", "512",
        "--use_rect",
    ]

    # Try 512 resolution first, fall back to 384 if OOM
    env = os.environ.copy()
    env["CUDA_VISIBLE_DEVICES"] = "0"
    env["PYTORCH_CUDA_ALLOC_CONF"] = "max_split_size_mb:256"

    # Try 512 resolution first, fall back to 384 if OOM or Timeout
    should_retry = False
    try:
        result = subprocess.run(
            cmd, cwd=str(PIFUHD_DIR),
            capture_output=True, text=True,
            timeout=600, env=env,
        )
        if result.returncode != 0 and (
            "out of memory" in result.stderr.lower() or
            "cuda" in result.stderr.lower()
        ):
            print("VRAM limit hit, retrying at resolution 384...")
            should_retry = True
    except subprocess.TimeoutExpired:
        print("VRAM execution timed out at resolution 512, retrying at resolution 384...")
        should_retry = True

    if should_retry:
        cmd_low = [
            sys.executable, "-m", "apps.simple_test",
            "--input_path", str(input_dir),
            "--out_path", str(out_dir),
            "--loadSize", "512",
            "--resolution", "384",
            "--use_rect",
        ]
        try:
            result = subprocess.run(
                cmd_low, cwd=str(PIFUHD_DIR),
                capture_output=True, text=True,
                timeout=600, env=env,
            )
        except subprocess.TimeoutExpired as e:
            raise RuntimeError(f"PIFuHD timed out at resolution 384: {e}")

    if result.returncode != 0:
        raise RuntimeError(
            f"PIFuHD failed.\n"
            f"STDOUT: {result.stdout[-2000:]}\n"
            f"STDERR: {result.stderr[-2000:]}"
        )

    # Check for OBJ output (the real success indicator)
    obj_files = list(out_dir.rglob("*.obj"))
    if not obj_files:
        raise RuntimeError("PIFuHD exited 0 but produced no .obj file")
    
    return str(obj_files[0])


def recolor_mesh_from_image(mesh, image_path: str, rect: list):
    """
    Re-derive vertex colors by projecting each vertex back onto the source
    image using PIFuHD's orthographic NDC coordinate system.

    This lets us later swap `image_path` for a virtual try-on result and
    transfer its colors onto the 3D mesh.

    Coordinate pipeline (from EvalDataset.py → recon.py → convert_to_glb):
      1. PIFuHD outputs vertices in NDC space [-1,1]³ with Y flipped
         (calib = diag(1,-1,1,1)), relative to the *cropped* image.
      2. convert_to_glb applies a 180° Y-axis rotation (x→-x, z→-z).
      3. To project back: undo the rotation, then map NDC → pixel.

    Args:
        mesh:       trimesh.Trimesh — the post-cleanup mesh (already rotated
                    by π around Y in convert_to_glb)
        image_path: path to the original input photo (the one before preprocessing)
        rect:       [x, y, w, h] from person_rect.txt

    Returns:
        The same mesh object, with vertex colors overwritten where the
        projection is valid.
    """
    import trimesh
    import numpy as np
    from PIL import Image
    from scipy.ndimage import map_coordinates
    from numpy.linalg import inv

    print(f"Recoloring mesh from image: {image_path}", flush=True)
    print(f"  rect: {rect}", flush=True)

    # Load source image
    img_pil = Image.open(image_path).convert("RGB")
    img = np.array(img_pil)  # (H, W, 3)
    img_h, img_w = img.shape[:2]
    print(f"  Source image size: {img_w}×{img_h}", flush=True)

    verts = mesh.vertices.copy()  # (N, 3) — in post-rotation space
    n_verts = len(verts)

    # ── Step 1: Undo the π rotation around Y that convert_to_glb applied ──
    # rotation_matrix(π, [0,1,0]) = diag(-1, 1, -1), so invert: x→-x, z→-z
    verts_ndc = verts.copy()
    verts_ndc[:, 0] *= -1  # undo X flip
    verts_ndc[:, 2] *= -1  # undo Z flip
    # Now verts_ndc are back in PIFuHD's output NDC space

    # ── Step 2: NDC → pixel coordinates ──
    # We mirror the normalization math from EvalDataset.py, just inverted.
    # From EvalDataset.py:
    #   scale_im2ndc = 1.0 / float(w // 2)
    #   scale = w / rect[2]
    #   trans_mat = np.identity(4)
    #   trans_mat *= scale
    #   trans_mat[3, 3] = 1.0
    #   trans_mat[0, 3] = -scale * (rect[0] + rect[2] // 2 - w // 2) * scale_im2ndc
    #   trans_mat[1, 3] = scale * (rect[1] + rect[3] // 2 - h // 2) * scale_im2ndc
    # where w, h are original image dimensions.
    scale_im2ndc = 1.0 / float(img_w // 2)
    scale = img_w / rect[2]
    
    trans_mat = np.identity(4)
    trans_mat *= scale
    trans_mat[3, 3] = 1.0
    trans_mat[0, 3] = -scale * (rect[0] + rect[2] // 2 - img_w // 2) * scale_im2ndc
    trans_mat[1, 3] = scale * (rect[1] + rect[3] // 2 - img_h // 2) * scale_im2ndc
    
    trans_mat_inv = inv(trans_mat)
    
    # Vertices in homogeneous coordinates
    verts_homo = np.concatenate([verts_ndc, np.ones((n_verts, 1))], axis=1)
    
    # Map back to original image normalized space (where horizontal extent is [-1, 1])
    verts_orig_norm = np.matmul(verts_homo, trans_mat_inv.T)[:, :3]
    
    # Convert original image normalized space to pixel coordinates
    px = (verts_orig_norm[:, 0] + 1.0) / 2.0 * img_w
    py = img_h / 2.0 - verts_orig_norm[:, 1] * (img_w / 2.0)

    # ── Step 3: Compute vertex normals for front-face test ──
    # In NDC space, the camera looks along -Z, so front-facing = normal · (0,0,1) > 0
    # (PIFuHD's coordinate system has camera at +Z looking at -Z)
    try:
        # Recompute normals in NDC space
        ndc_mesh = trimesh.Trimesh(
            vertices=verts_ndc, faces=mesh.faces, process=False
        )
        normals = ndc_mesh.vertex_normals  # (N, 3)
        front_facing = normals[:, 2] > 0  # normal Z > 0 = facing camera
    except Exception as e:
        print(f"  Normal computation failed: {e}, treating all as front-facing")
        front_facing = np.ones(n_verts, dtype=bool)

    # ── Step 4: Determine which vertices project within image bounds ──
    in_bounds = (
        (px >= 0) & (px < img_w) &
        (py >= 0) & (py < img_h)
    )
    valid = front_facing & in_bounds
    n_valid = valid.sum()
    n_front = front_facing.sum()
    n_inbounds = in_bounds.sum()
    print(f"  Vertices: {n_verts} total, {n_front} front-facing, "
          f"{n_inbounds} in-bounds, {n_valid} valid for recoloring", flush=True)

    # ── Step 5: Sample colors from the image ──
    # Use scipy.ndimage.map_coordinates for bilinear interpolation
    # It expects (row, col) = (py, px)
    # Start from existing vertex colors as fallback
    if hasattr(mesh.visual, 'vertex_colors') and mesh.visual.vertex_colors is not None:
        colors = mesh.visual.vertex_colors[:, :3].copy().astype(np.float64)
        print(f"  Using existing vertex colors as fallback for back-facing vertices")
    else:
        colors = np.full((n_verts, 3), 128, dtype=np.float64)  # grey fallback
        print(f"  No existing vertex colors — using grey fallback")

    if n_valid > 0:
        valid_px = px[valid]
        valid_py = py[valid]

        # Sample each channel with bilinear interpolation
        for c in range(3):
            channel = img[:, :, c].astype(np.float64)  # (H, W)
            sampled = map_coordinates(
                channel,
                [valid_py, valid_px],  # (row, col)
                order=1,               # bilinear
                mode='nearest',
            )
            colors[valid, c] = sampled

    # ── Step 6: Apply colors back to the mesh ──
    colors_uint8 = np.clip(colors, 0, 255).astype(np.uint8)
    # Add alpha channel (fully opaque)
    rgba = np.column_stack([colors_uint8, np.full(n_verts, 255, dtype=np.uint8)])
    mesh.visual = trimesh.visual.ColorVisuals(mesh=mesh, vertex_colors=rgba)

    print(f"  Recoloring complete: {n_valid}/{n_verts} vertices recolored",
          flush=True)
    return mesh


def convert_to_glb(
    obj_path: str, 
    output_dir: str,
    original_image_path: str = None,
) -> str:
    """
    Convert PIFuHD .obj to textured .glb.
    If original_image_path provided, projects photo colors 
    onto mesh as vertex colors.
    """
    glb_path = str(Path(output_dir) / "avatar.glb")
    
    if original_image_path and Path(original_image_path).exists():
        print("Using photo texture projection...")
        try:
            project_texture_onto_mesh(
                obj_path=obj_path,
                image_path=original_image_path,
                output_glb_path=glb_path,
            )
            return glb_path
        except Exception as e:
            print(f"Texture projection failed: {e}")
            print("Falling back to vertex color extraction...")
    
    # Fallback: extract existing vertex colors from obj
    import trimesh
    import numpy as np
    
    mesh = trimesh.load(obj_path, process=False)
    if isinstance(mesh, trimesh.Scene):
        geometries = list(mesh.geometry.values())
        mesh = max(geometries, key=lambda g: len(g.faces))
    
    # Remove fragments
    try:
        components = mesh.split(only_watertight=False)
        if len(components) > 1:
            mesh = max(components, key=lambda c: len(c.faces))
    except Exception:
        pass
    
    # Rotate to face forward
    rotation = trimesh.transformations.rotation_matrix(np.pi, [0, 1, 0])
    mesh.apply_transform(rotation)
    
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
        print(f"\n{'='*50}", flush=True)
        print(f"New avatar request: {len(image_bytes)} bytes", flush=True)
        print(f"{'='*50}", flush=True)
        
        # Read from environment variable or query parameters
        recolor_debug = (
            os.environ.get("RECOLOR_DEBUG", "").lower() == "true" or
            request.args.get("recolor_debug", "").lower() == "true" or
            request.args.get("RECOLOR_DEBUG", "").lower() == "true"
        )

        with tempfile.TemporaryDirectory() as tmp:
            import time
            start_time = time.time()
            img_path = os.path.join(tmp, "input.jpg")
            open(img_path, "wb").write(image_bytes)
            original_img_path = img_path  # Save before preprocessing

            print(f"Running PIFuHD on {len(image_bytes)} byte image...", flush=True)
            obj_path = run_pifuhd(img_path, tmp)
            print("[OK] Step 3/4: 3D mesh reconstructed", flush=True)
            print(f"PIFuHD done: {obj_path}", flush=True)

            # Use the preprocessed (bg removed) image for projection
            # It has clean white background which helps color sampling
            preprocessed_for_texture = os.path.join(tmp, "input", "person.jpg")
            texture_source = (
                preprocessed_for_texture 
                if Path(preprocessed_for_texture).exists() 
                else original_img_path
            )
            glb_path = convert_to_glb(obj_path, tmp, texture_source)
            print("[OK] Step 4/4: Texture applied and GLB exported", flush=True)
            glb_size_mb = Path(glb_path).stat().st_size / (1024*1024)
            print(f"Final GLB size: {glb_size_mb:.2f} MB", flush=True)
            print(f"GLB ready: {glb_path}", flush=True)

            glb_bytes = open(glb_path, "rb").read()
            glb_b64 = base64.b64encode(glb_bytes).decode()

            response_data = {
                "glb_base64": glb_b64,
                "size_bytes": len(glb_bytes),
            }

            # ── Optional recolor debug: re-derive colors from original photo ──
            if recolor_debug:
                try:
                    import trimesh
                    print("RECOLOR_DEBUG=true — producing recolored GLB...",
                          flush=True)

                    # Parse rect from the person_rect.txt generated by PIFuHD script
                    input_dir = Path(tmp) / "input"
                    rect_file = input_dir / "person_rect.txt"

                    rect = [0, 0, 512, 512]  # fallback
                    if rect_file.exists():
                        parts = rect_file.read_text().strip().split()
                        rect = [int(x) for x in parts[:4]]

                    # Load the post-cleanup mesh from the normal GLB
                    recolor_mesh = trimesh.load(glb_path, process=False)
                    if isinstance(recolor_mesh, trimesh.Scene):
                        geoms = list(recolor_mesh.geometry.values())
                        recolor_mesh = max(geoms, key=lambda g: len(g.vertices))

                    # Recolor from the original input photo (img_path) instead of person.jpg
                    recolor_mesh = recolor_mesh_from_image(
                        recolor_mesh, img_path, rect
                    )

                    # Export recolored GLB
                    recolored_glb_path = str(Path(tmp) / "avatar_recolored.glb")
                    recolor_mesh.export(recolored_glb_path)
                    recolored_size = Path(recolored_glb_path).stat().st_size
                    print(f"Recolored GLB: {recolored_size} bytes", flush=True)

                    recolored_bytes = open(recolored_glb_path, "rb").read()
                    response_data["recolored_glb_base64"] = base64.b64encode(
                        recolored_bytes
                    ).decode()
                    response_data["recolored_size_bytes"] = len(recolored_bytes)

                    # Copy to persistent workspace folder for manual verification
                    workspace_dir = Path("c:/Users/karta/Desktop/Projects/fitcheckai/backend")
                    if workspace_dir.exists():
                        shutil.copy2(glb_path, str(workspace_dir / "test_avatar_output.glb"))
                        shutil.copy2(recolored_glb_path, str(workspace_dir / "test_avatar_recolored.glb"))
                        print(f"Copied GLB files to workspace directory {workspace_dir} for visual verification.", flush=True)

                except Exception as e:
                    print(f"RECOLOR_DEBUG failed: {e}", flush=True)
                    import traceback as _tb
                    _tb.print_exc()
                    response_data["recolor_error"] = str(e)

            elapsed = time.time() - start_time
            print(f"Total time: {elapsed:.1f}s", flush=True)
            return jsonify(response_data)

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
