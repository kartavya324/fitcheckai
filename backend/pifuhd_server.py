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

# iPhone HEIC support — lets PIL open .heic/.heif inputs
try:
    from pillow_heif import register_heif_opener
    register_heif_opener()
except ImportError:
    print("WARNING: pillow-heif not installed; HEIC inputs will fail")

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


def _clean_alpha(rgba):
    """Keep only the largest connected person region; fill holes; soften edge."""
    import numpy as np
    from scipy import ndimage
    from PIL import Image

    arr = np.array(rgba)
    alpha = arr[:, :, 3]
    mask = alpha > 128
    filled = ndimage.binary_fill_holes(mask)

    labeled, num = ndimage.label(filled)
    if num > 1:
        sizes = ndimage.sum(filled, labeled, range(1, num + 1))
        largest = int(np.argmax(sizes)) + 1
        filled = labeled == largest
        print(f"Removed {num - 1} disconnected regions")

    # Slight dilation so we don't clip the silhouette edge
    dil = ndimage.binary_dilation(filled, iterations=2)
    arr[:, :, 3] = np.where(dil, np.maximum(alpha, 200), 0).astype(np.uint8)
    return Image.fromarray(arr)


from functools import lru_cache


@lru_cache(maxsize=2)
def _rembg_session(model: str = "u2net_human_seg"):
    """Cache the rembg ONNX session — loading it costs ~1-2s per call otherwise."""
    from rembg import new_session
    try:
        return new_session(model)
    except Exception:
        return new_session("u2net")


def remove_background_rgba(image_path: str):
    """Return a cleaned RGBA PIL image (person opaque, background transparent)."""
    from rembg import remove
    from PIL import Image
    import io

    print("Removing background...")
    with open(image_path, "rb") as f:
        out = remove(f.read(), session=_rembg_session("u2net_human_seg"))
    rgba = Image.open(io.BytesIO(out)).convert("RGBA")
    return _clean_alpha(rgba)


def prepare_input(image_path: str, out_person_path: str,
                  target: int = 512, fill: float = 0.88) -> list:
    """
    Produce the exact 512x512 image PIFuHD is fed AND textured from, and return
    the person's bounding box [x, y, w, h] within that canvas.

    Why this matters: PIFuHD is trained on humans that FILL the frame. The old
    pipeline padded a small person into a big white square and set the rect to
    the whole frame, so the network hallucinated a melted blob. Here we
    background-remove, tight-crop to the person, and scale so the silhouette
    fills ~`fill` of the frame. Because the mesh and this image then share one
    coordinate system, colour projection later becomes pixel-accurate.
    """
    from PIL import Image
    import numpy as np

    try:
        rgba = remove_background_rgba(image_path)
    except Exception as e:
        print(f"BG removal failed ({e}); using original image")
        from PIL import ImageOps
        # rembg applies EXIF orientation internally; this fallback must too,
        # or sideways phone photos produce sideways avatars.
        rgba = ImageOps.exif_transpose(Image.open(image_path)).convert("RGBA")

    arr = np.array(rgba)
    ys, xs = np.where(arr[:, :, 3] > 128)

    if len(ys) == 0:
        # No person detected — letterbox the original onto a square canvas
        rgb = rgba.convert("RGB")
        rgb.thumbnail((target, target), Image.LANCZOS)
        canvas = Image.new("RGB", (target, target), (255, 255, 255))
        off = ((target - rgb.width) // 2, (target - rgb.height) // 2)
        canvas.paste(rgb, off)
        canvas.save(out_person_path, "JPEG", quality=95)
        return [off[0], off[1], rgb.width, rgb.height]

    r0, r1, c0, c1 = int(ys.min()), int(ys.max()), int(xs.min()), int(xs.max())
    crop = rgba.crop((c0, r0, c1 + 1, r1 + 1))

    cw, ch = crop.size
    scale = (target * fill) / max(cw, ch)
    nw, nh = max(1, round(cw * scale)), max(1, round(ch * scale))
    crop_r = crop.resize((nw, nh), Image.LANCZOS)

    canvas = Image.new("RGB", (target, target), (255, 255, 255))
    off = ((target - nw) // 2, (target - nh) // 2)
    canvas.paste(crop_r, off, crop_r.split()[3])
    canvas.save(out_person_path, "JPEG", quality=95)

    print(f"Prepared input: person {cw}x{ch} -> {nw}x{nh} "
          f"filling {fill:.0%} of {target}px frame")
    return [off[0], off[1], nw, nh]


# The 4GB GPU fits exactly one reconstruction at a time. Concurrent requests
# (multiple browser tabs, retries) must queue, or both OOM and both fail.
import threading
_gpu_lock = threading.Lock()


def run_pifuhd(image_path: str, output_dir: str) -> str:
    input_dir = Path(output_dir) / "input"
    input_dir.mkdir(parents=True, exist_ok=True)

    # Background-remove + person-fill crop onto a SQUARE canvas.
    dest = input_dir / "person.jpg"
    prepare_input(image_path, str(dest))
    print("[OK] Step 1/4: Image prepared (person-filled crop)", flush=True)
    print("[OK] Step 2/4: Background removed", flush=True)

    # Rect MUST be the full square canvas. A non-square rect makes PIFuHD
    # stretch the crop to a square and squash the person into a blob. The
    # person already fills the frame vertically, so the full frame is correct,
    # and it keeps colour projection an exact identity mapping.
    from PIL import Image
    with Image.open(str(dest)) as im:
        cw, ch = im.size
    rect_path = input_dir / "person_rect.txt"
    with open(rect_path, "w") as f:
        f.write(f"0 0 {cw} {ch}\n")

    out_dir = Path(output_dir) / "result"
    out_dir.mkdir(parents=True, exist_ok=True)

    # Marching-cubes grid resolution dominates runtime (~O(res^3)) and VRAM.
    # 512 needs more than the 4GB RTX 3050 has (CUDA OOM); 384 fits and gives
    # a ~2.3x denser mesh than 256 — visibly better face structure. PIFuHD's
    # recon.py swallows exceptions (prints and exits 0), so a too-high
    # resolution silently yields no .obj — we therefore try the requested
    # resolution and fall back to coarser grids automatically.
    # Override the starting point with PIFUHD_RESOLUTION.
    requested = os.environ.get("PIFUHD_RESOLUTION", "384")
    fallbacks = ["512", "384", "256"]
    resolutions = [requested] + [r for r in fallbacks if int(r) < int(requested)]

    env = os.environ.copy()
    env["CUDA_VISIBLE_DEVICES"] = "0"
    env["PYTORCH_CUDA_ALLOC_CONF"] = "max_split_size_mb:256"

    last_output = ""
    for resolution in resolutions:
        print(f"Running PIFuHD at resolution {resolution}...", flush=True)
        cmd = [
            sys.executable, "-m", "apps.simple_test",
            "--input_path", str(input_dir),
            "--out_path", str(out_dir),
            "--resolution", resolution,
            "--use_rect",
        ]

        if not _gpu_lock.acquire(timeout=900):
            raise RuntimeError("GPU busy for over 15 minutes; try again later")
        try:
            result = subprocess.run(
                cmd, cwd=str(PIFUHD_DIR),
                capture_output=True, text=True,
                timeout=600, env=env,
            )
        except subprocess.TimeoutExpired:
            print(f"PIFuHD timed out at resolution {resolution}; "
                  f"trying coarser grid...", flush=True)
            last_output = f"timeout at resolution {resolution}"
            continue
        finally:
            _gpu_lock.release()

        last_output = (
            f"STDOUT: {result.stdout[-2000:]}\nSTDERR: {result.stderr[-2000:]}"
        )

        if result.returncode != 0:
            raise RuntimeError(f"PIFuHD failed.\n{last_output}")

        # OBJ output is the real success indicator (recon.py hides errors)
        obj_files = list(out_dir.rglob("*.obj"))
        if obj_files:
            print(f"PIFuHD succeeded at resolution {resolution}", flush=True)
            return str(obj_files[0])

        print(f"No mesh at resolution {resolution} "
              f"(likely GPU memory); trying coarser grid...", flush=True)
        print(last_output, flush=True)

    raise RuntimeError(
        f"PIFuHD produced no .obj at any resolution "
        f"({', '.join(resolutions)}).\n{last_output}"
    )


def _srgb_to_linear_u8(colors_u8):
    """
    Convert sRGB-encoded uint8 colors to linear-encoded uint8.

    glTF stores COLOR_0 as LINEAR values, but our vertex colors are sampled
    straight from photo pixels (sRGB). Without this conversion a spec-correct
    viewer (three.js with sRGB output) renders the avatar noticeably darker
    than the photo.
    """
    import numpy as np
    c = colors_u8.astype(np.float64) / 255.0
    lin = np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
    return np.clip(lin * 255.0 + 0.5, 0, 255).astype(np.uint8)


def _dominant_hair_color(img):
    """
    Median colour of the top band of the person (their hair), from a
    white-background image. Used to paint the back of the head so it doesn't
    show a mirrored face. Falls back to a dark brown.
    """
    import numpy as np
    nonwhite = np.any(img < 217, axis=2)  # ~0.85 * 255
    ys, xs = np.where(nonwhite)
    if len(ys) == 0:
        return np.array([55.0, 45.0, 40.0])
    top = int(ys.min())
    band = ys <= top + 0.08 * (int(ys.max()) - top)
    if int(band.sum()) < 20:
        return np.array([55.0, 45.0, 40.0])
    return np.median(img[ys[band], xs[band]].astype(np.float64), axis=0)


def recolor_mesh_from_image(mesh, image_path: str, rect: list, back_image_path: str = None):
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
    n_front = int(front_facing.sum())
    n_inbounds = int(in_bounds.sum())
    print(f"  Vertices: {n_verts} total, {n_front} front-facing, "
          f"{n_inbounds} in-bounds", flush=True)

    # ── Step 5: Wrap the front photo around the WHOLE body ──
    # We colour every in-bounds vertex by its (x,y) projection — front and back
    # alike. A back vertex projects to the same silhouette location as the front
    # vertex above it, so the back of the blazer becomes navy, the back of the
    # trousers beige, etc. This removes the grey back entirely. Back-facing
    # vertices are then darkened slightly as a shading cue (we have no true back
    # photo, so a plausible darker wrap beats a grey patch).
    colors = np.full((n_verts, 3), 190.0, dtype=np.float64)  # neutral fallback

    if in_bounds.any():
        for c in range(3):
            channel = img[:, :, c].astype(np.float64)  # (H, W)
            colors[in_bounds, c] = map_coordinates(
                channel,
                [py[in_bounds], px[in_bounds]],  # (row, col)
                order=1, mode='nearest',
            )

        # ── The BACK: use a real back photo if the user gave one, else synthesize ──
        back = (~front_facing) & in_bounds
        if back.any():
            real_back = None
            if back_image_path and Path(back_image_path).exists():
                try:
                    import tempfile
                    tb = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False).name
                    prepare_input(back_image_path, tb)  # person fills 512, white bg
                    bimg = np.array(Image.open(tb).convert("RGB"))
                    # Mirror horizontally so the back photo lines up with the
                    # front coordinate frame (left/right swap when seen from behind).
                    real_back = bimg[:, ::-1, :]
                    print("  Using REAL back photo for back-facing vertices", flush=True)
                except Exception as exc:
                    print(f"  Back-photo prep failed ({exc}); synthesizing back")

            if real_back is not None:
                rb_h, rb_w = real_back.shape[:2]
                sx = px * (rb_w / img_w)
                sy = py * (rb_h / img_h)
                for c in range(3):
                    colors[back, c] = map_coordinates(
                        real_back[:, :, c].astype(np.float64),
                        [sy[back], sx[back]], order=1, mode="nearest",
                    )
                colors[back] *= 0.92  # real data — only a touch of depth shading
            else:
                # Synthesize a plausible back from the person's own clothing
                # colours. Blurring the raw photo bleeds the white background
                # into the wrap (grey streaks), so first replace every
                # background pixel with its nearest person pixel — the blur
                # then produces clean garment-colour bands.
                from scipy.ndimage import gaussian_filter, distance_transform_edt
                person_px = np.any(img < 240, axis=2)  # non-white = person
                if person_px.any():
                    _, (iy, ix) = distance_transform_edt(
                        ~person_px, return_indices=True
                    )
                    img_fill = img[iy, ix].astype(np.float64)
                else:
                    img_fill = img.astype(np.float64)
                sigma = max(img_h, img_w) * 0.02
                img_blur = np.stack(
                    [gaussian_filter(img_fill[:, :, c], sigma) for c in range(3)],
                    axis=2,
                )
                for c in range(3):
                    colors[back, c] = map_coordinates(
                        img_blur[:, :, c], [py[back], px[back]], order=1, mode="nearest"
                    )
                colors[back] *= 0.82  # gentler depth shading (was 0.72)

                # Back of the head → hair colour (never a wrapped face)
                yv = verts_ndc[:, 1]
                y_lo, y_hi = float(yv.min()), float(yv.max())
                head_back = back & (yv > y_hi - 0.12 * (y_hi - y_lo))
                if head_back.any():
                    colors[head_back] = _dominant_hair_color(img) * 0.85

        # Rare out-of-bounds verts inherit the nearest in-bounds colour
        oob = ~in_bounds
        if oob.any():
            from scipy.spatial import cKDTree
            tree = cKDTree(verts_ndc[in_bounds])
            _, nn = tree.query(verts_ndc[oob], k=1)
            colors[oob] = colors[in_bounds][nn] * 0.72

        # ── Blend seams (front↔back, head↔torso) without softening the face ──
        try:
            from scipy import sparse
            e = mesh.edges
            A = sparse.coo_matrix(
                (np.ones(len(e) * 2),
                 (np.r_[e[:, 0], e[:, 1]], np.r_[e[:, 1], e[:, 0]])),
                shape=(n_verts, n_verts),
            ).tocsr()
            deg = np.asarray(A.sum(1)).ravel()
            invd = np.zeros(n_verts)
            invd[deg > 0] = 1.0 / deg[deg > 0]
            op = sparse.diags(invd).dot(A)
            smoothed = colors.copy()
            for _ in range(3):
                smoothed = smoothed * 0.5 + op.dot(smoothed) * 0.5
            # Smooth the back strongly, the front barely (preserves the face).
            w = np.where(front_facing, 0.12, 0.75)[:, None]
            colors = colors * (1 - w) + smoothed * w
        except Exception as exc:
            print(f"  Colour seam-blend skipped: {exc}")

    # ── Step 6: Apply colors back to the mesh ──
    colors_uint8 = np.clip(colors, 0, 255).astype(np.uint8)
    # sRGB photo samples → linear, as the glTF COLOR_0 spec requires
    colors_uint8 = _srgb_to_linear_u8(colors_uint8)
    # Add alpha channel (fully opaque)
    rgba = np.column_stack([colors_uint8, np.full(n_verts, 255, dtype=np.uint8)])
    mesh.visual = trimesh.visual.ColorVisuals(mesh=mesh, vertex_colors=rgba)

    print(f"  Recoloring complete: {n_inbounds}/{n_verts} vertices coloured "
          f"({n_front} front-lit, {n_verts - n_front} back-shaded)", flush=True)
    return mesh


def convert_to_glb(
    obj_path: str,
    output_dir: str,
    original_image_path: str = None,
    rect: list = None,
    back_image_path: str = None,
) -> str:
    """
    Convert PIFuHD .obj to a cleaned, textured .glb.

    Texture path (in order of preference):
      1. Calibrated projection — samples the photo using PIFuHD's own
         orthographic camera, so colour lines up with geometry exactly.
      2. Bounding-box projection — cruder stretch, used only if (1) fails.
      3. Warm neutral colour — last resort. We NEVER silently fall back to
         trimesh's default grey (that was the old "grey blob" bug).
    """
    import trimesh
    import numpy as np

    glb_path = str(Path(output_dir) / "avatar.glb")

    mesh = trimesh.load(obj_path, process=False)
    if isinstance(mesh, trimesh.Scene):
        mesh = max(mesh.geometry.values(), key=lambda g: len(g.faces))

    # Keep only the main body component (drop floating fragments)
    try:
        components = mesh.split(only_watertight=False)
        if len(components) > 1:
            mesh = max(components, key=lambda c: len(c.faces))
            print(f"Kept main component: {len(mesh.faces)} faces")
    except Exception as e:
        print(f"Component split skipped: {e}")

    # Taubin smoothing reduces the lumpy surface WITHOUT shrinking the mesh
    # (plain Laplacian shrinks it and rounds off hands/feet).
    try:
        import trimesh.smoothing as smoothing
        smoothing.filter_taubin(mesh, iterations=10)
        print("Mesh smoothed (Taubin)")
    except Exception as e:
        print(f"Smoothing skipped: {e}")

    # Quadric decimation: adaptive, so flat regions collapse while curved
    # detail (face, hands) keeps its density. Halves GLB size → faster loads.
    try:
        target_faces = int(os.environ.get("AVATAR_TARGET_FACES", "80000"))
        if len(mesh.faces) > target_faces:
            before = len(mesh.faces)
            decimated = mesh.simplify_quadric_decimation(face_count=target_faces)
            if len(decimated.faces) > 0:
                mesh = decimated
                print(f"Decimated mesh: {before} -> {len(mesh.faces)} faces")
    except Exception as e:
        print(f"Decimation skipped: {e}")

    # Rotate 180° about Y so the mesh faces the camera
    mesh.apply_transform(trimesh.transformations.rotation_matrix(np.pi, [0, 1, 0]))

    colored = False
    if original_image_path and Path(original_image_path).exists():
        # 1. Calibrated projection (preferred)
        try:
            from PIL import Image
            if rect is None:
                with Image.open(original_image_path) as im:
                    W, H = im.size
                rect = [0, 0, W, H]
            mesh = recolor_mesh_from_image(
                mesh, original_image_path, rect, back_image_path=back_image_path
            )
            colored = True
            print("Texture: calibrated projection OK")
        except Exception as e:
            print(f"Calibrated projection failed: {e}")
            import traceback
            traceback.print_exc()

        # 2. Bounding-box projection (fallback — writes its own glb)
        if not colored:
            try:
                project_texture_onto_mesh(
                    obj_path=obj_path,
                    image_path=original_image_path,
                    output_glb_path=glb_path,
                )
                print("Texture: bbox projection fallback OK")
                return glb_path
            except Exception as e:
                print(f"Bbox projection failed: {e}")

    # 3. Warm neutral colour — last resort, never grey
    if not colored:
        n = len(mesh.vertices)
        skin = np.append(_srgb_to_linear_u8(np.array([[200, 180, 165]], np.uint8))[0], 255)
        rgba = np.tile(skin.astype(np.uint8), (n, 1))
        mesh.visual = trimesh.visual.ColorVisuals(mesh=mesh, vertex_colors=rgba)
        print("Texture: applied neutral fallback colour")

    mesh.export(glb_path)
    return glb_path


@app.route("/recolor", methods=["POST"])
def recolor():
    """
    Re-texture an existing avatar GLB from a new photo of the same person
    (e.g. a 2D virtual try-on result). The pose must match the photo the
    avatar was generated from — IDM-VTON preserves pose, so its output
    projects cleanly onto the same mesh.

    Body: { "glb_base64": ..., "image_base64": ... }
    Returns: { "glb_base64": ..., "size_bytes": ... }
    """
    try:
        import trimesh

        data = request.get_json()
        if not data or "glb_base64" not in data or "image_base64" not in data:
            return jsonify({"error": "glb_base64 and image_base64 required"}), 400

        glb_bytes = base64.b64decode(data["glb_base64"])
        image_bytes = base64.b64decode(data["image_base64"])
        print(f"\nRecolor request: {len(glb_bytes)} byte GLB, "
              f"{len(image_bytes)} byte image", flush=True)

        with tempfile.TemporaryDirectory() as tmp:
            glb_in = os.path.join(tmp, "avatar.glb")
            open(glb_in, "wb").write(glb_bytes)
            img_raw = os.path.join(tmp, "input.jpg")
            open(img_raw, "wb").write(image_bytes)

            # Same 512 person-filled canvas the original texture used, so the
            # projection lands on the same coordinates.
            img_prepared = os.path.join(tmp, "person.jpg")
            prepare_input(img_raw, img_prepared)

            mesh = trimesh.load(glb_in, process=False)
            if isinstance(mesh, trimesh.Scene):
                mesh = max(mesh.geometry.values(), key=lambda g: len(g.vertices))

            mesh = recolor_mesh_from_image(mesh, img_prepared, [0, 0, 512, 512])

            glb_out = os.path.join(tmp, "avatar_recolored.glb")
            mesh.export(glb_out)
            out_bytes = open(glb_out, "rb").read()
            print(f"Recolor done: {len(out_bytes)} bytes", flush=True)

            return jsonify({
                "glb_base64": base64.b64encode(out_bytes).decode(),
                "size_bytes": len(out_bytes),
            })

    except Exception as e:
        tb = traceback.format_exc()
        print(tb, flush=True)
        return jsonify({"error": str(e), "traceback": tb}), 500


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

            # Optional back photo → textures the back with real data
            back_img_path = None
            if data.get("back_image_base64"):
                try:
                    back_img_path = os.path.join(tmp, "back.jpg")
                    with open(back_img_path, "wb") as f:
                        f.write(base64.b64decode(data["back_image_base64"]))
                    print("Received optional back photo", flush=True)
                except Exception as e:
                    print(f"Could not decode back photo: {e}", flush=True)
                    back_img_path = None

            print(f"Running PIFuHD on {len(image_bytes)} byte image...", flush=True)
            obj_path = run_pifuhd(img_path, tmp)
            print("[OK] Step 3/4: 3D mesh reconstructed", flush=True)
            print(f"PIFuHD done: {obj_path}", flush=True)

            # Texture from the SAME 512 image PIFuHD was fed (person.jpg) so the
            # calibrated projection lines up exactly. Read the person rect that
            # prepare_input wrote for that alignment.
            preprocessed_for_texture = os.path.join(tmp, "input", "person.jpg")
            texture_source = (
                preprocessed_for_texture
                if Path(preprocessed_for_texture).exists()
                else original_img_path
            )
            rect = None
            rect_file = Path(tmp) / "input" / "person_rect.txt"
            if rect_file.exists():
                parts = rect_file.read_text().split()
                if len(parts) >= 4:
                    rect = [int(float(p)) for p in parts[:4]]
            glb_path = convert_to_glb(
                obj_path, tmp, texture_source, rect, back_image_path=back_img_path
            )
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
