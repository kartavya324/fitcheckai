"""
Avatar Analysis Service — extracts clothing colors and face thumbnail
from the original uploaded photo (independent of the 3D mesh pipeline).
"""

import logging
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)

# Print cv2.data.haarcascades to check what it resolves to
try:
    _haarcascades_path = cv2.data.haarcascades
    print(f"cv2.data.haarcascades resolves to: {_haarcascades_path}", flush=True)
    logger.info(f"cv2.data.haarcascades resolves to: {_haarcascades_path}")
    _haarcascades_file = Path(_haarcascades_path) / "haarcascade_frontalface_default.xml"
    if _haarcascades_file.exists():
        print(f"  -> haarcascade file EXISTS at {_haarcascades_file}", flush=True)
    else:
        print(f"  -> haarcascade file MISSING at {_haarcascades_file}", flush=True)
except Exception as e:
    print(f"cv2.data.haarcascades is NOT available: {e}", flush=True)
    logger.warning(f"cv2.data.haarcascades is not available: {e}")



def analyze_person_image(
    image_path: str,
    session_id: str,
    output_dir: str,
    *,
    n_colors: int = 5,
    face_size: int = 128,
) -> dict:
    """
    Run analysis on the original uploaded photo.

    Returns:
        {
            "dominant_colors": [{"hex": "#2C3E50", "percentage": 45.2}, ...],
            "face_thumbnail_path": "avatars/analysis/{session_id}_face.jpg" | None,
        }
    """
    result: dict = {
        "dominant_colors": [],
        "face_thumbnail_path": None,
    }

    try:
        img_pil = Image.open(image_path).convert("RGB")
        img_np = np.array(img_pil)
    except Exception as e:
        logger.error(f"Failed to load image for analysis: {e}")
        return result

    # ── 1. Person segmentation mask ──────────────────────────────
    person_mask = _get_person_mask(image_path)

    # ── 2. Clothing color extraction ─────────────────────────────
    try:
        result["dominant_colors"] = _extract_clothing_colors(
            img_np, person_mask, n_colors=n_colors
        )
    except Exception as e:
        logger.error(f"Color extraction failed: {e}", exc_info=True)

    # ── 3. Face thumbnail ────────────────────────────────────────
    try:
        out_path = Path(output_dir)
        out_path.mkdir(parents=True, exist_ok=True)
        face_path = out_path / f"{session_id}_face.jpg"

        if _extract_face_thumbnail(img_np, person_mask, str(face_path), face_size):
            # Return relative path from storage root
            # output_dir is like <storage_root>/avatars/analysis
            result["face_thumbnail_path"] = f"avatars/analysis/{session_id}_face.jpg"
    except Exception as e:
        logger.error(f"Face thumbnail failed: {e}", exc_info=True)

    return result


def _get_person_mask(image_path: str) -> np.ndarray | None:
    """Use rembg u2net_human_seg to get a binary person mask."""
    try:
        from rembg import remove, new_session
        import io

        session = new_session("u2net_human_seg")

        with open(image_path, "rb") as f:
            input_data = f.read()

        output_data = remove(input_data, session=session)
        img_rgba = Image.open(io.BytesIO(output_data)).convert("RGBA")
        alpha = np.array(img_rgba)[:, :, 3]

        # Binary mask: person pixels > 128
        mask = (alpha > 128).astype(np.uint8) * 255
        logger.info(f"Person mask: {np.count_nonzero(mask)} pixels")
        return mask
    except Exception as e:
        logger.warning(f"Person mask generation failed: {e}")
        return None


def _extract_clothing_colors(
    img_np: np.ndarray,
    person_mask: np.ndarray | None,
    n_colors: int = 5,
) -> list[dict]:
    """
    Extract dominant clothing colors using KMeans on the torso region.
    """
    from sklearn.cluster import MiniBatchKMeans

    h, w = img_np.shape[:2]

    if person_mask is not None:
        # Find the bounding box of the person
        ys, xs = np.where(person_mask > 0)
        if len(ys) == 0:
            return []

        y_min, y_max = ys.min(), ys.max()
        person_height = y_max - y_min

        # Torso region: 20% to 70% of person height (below neck, above knees)
        torso_top = int(y_min + person_height * 0.20)
        torso_bottom = int(y_min + person_height * 0.70)

        # Create torso-only mask
        torso_mask = np.zeros_like(person_mask)
        torso_mask[torso_top:torso_bottom, :] = person_mask[torso_top:torso_bottom, :]

        # Get pixels within the torso mask
        pixels = img_np[torso_mask > 0]
    else:
        # Fallback: use middle 50% of image
        y_start = int(h * 0.2)
        y_end = int(h * 0.7)
        pixels = img_np[y_start:y_end, :, :].reshape(-1, 3)

    if len(pixels) < 10:
        return []

    # Subsample for speed (max 50k pixels)
    if len(pixels) > 50_000:
        indices = np.random.choice(len(pixels), 50_000, replace=False)
        pixels = pixels[indices]

    pixels = pixels.astype(np.float32)

    # Run KMeans
    kmeans = MiniBatchKMeans(n_clusters=n_colors, random_state=42, n_init=3)
    labels = kmeans.fit_predict(pixels)
    centers = kmeans.cluster_centers_.astype(int)

    # Count pixels per cluster
    unique, counts = np.unique(labels, return_counts=True)
    total = counts.sum()

    # Build result sorted by coverage
    colors = []
    for idx in np.argsort(-counts):
        cluster_id = unique[idx]
        r, g, b = centers[cluster_id]
        hex_code = f"#{r:02X}{g:02X}{b:02X}"
        percentage = round(float(counts[idx] / total * 100), 1)

        # Skip very white/near-white colors (likely background bleed)
        if r > 240 and g > 240 and b > 240:
            continue

        colors.append({"hex": hex_code, "percentage": percentage})

    logger.info(f"Extracted {len(colors)} clothing colors")
    return colors[:5]  # Return top 5


def _ensure_cascade_file() -> Path:
    backend_dir = Path(__file__).resolve().parent.parent.parent
    assets_dir = backend_dir / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    cascade_path = assets_dir / "haarcascade_frontalface_default.xml"
    
    if not cascade_path.exists():
        logger.info(f"Downloading haarcascade_frontalface_default.xml to {cascade_path}...")
        url = "https://raw.githubusercontent.com/opencv/opencv/master/data/haarcascades/haarcascade_frontalface_default.xml"
        try:
            import requests
            r = requests.get(url, timeout=30)
            r.raise_for_status()
            cascade_path.write_bytes(r.content)
            logger.info("Successfully downloaded haarcascade_frontalface_default.xml")
        except Exception as e:
            logger.error(f"Failed to download Haar cascade file: {e}")
            raise
    return cascade_path


def _extract_face_thumbnail(
    img_np: np.ndarray,
    person_mask: np.ndarray | None,
    output_path: str,
    size: int = 128,
) -> bool:
    """
    Detect face using OpenCV Haar cascade and save a cropped thumbnail.
    Returns True if successful.
    """
    try:
        gray = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY)

        # Ensure cascade file is downloaded and get path
        try:
            cascade_path = _ensure_cascade_file()
            face_cascade = cv2.CascadeClassifier(str(cascade_path))
            if face_cascade.empty():
                raise RuntimeError(f"Loaded CascadeClassifier from {cascade_path} is empty")
        except Exception as e:
            logger.error(f"Failed to load local Haar cascade classifier: {e}")
            # Try to fall back to cv2.data.haarcascades just in case
            try:
                fallback_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
                logger.info(f"Attempting fallback to cv2.data.haarcascades: {fallback_path}")
                face_cascade = cv2.CascadeClassifier(fallback_path)
            except Exception as e2:
                logger.error(f"cv2.data.haarcascades fallback also failed: {e2}")
                logger.warning("Face detection unavailable — continuing without face thumbnail")
                return False

        faces = face_cascade.detectMultiScale(
            gray,
            scaleFactor=1.1,
            minNeighbors=5,
            minSize=(30, 30),
        )

        if len(faces) > 0:
            # Pick the largest detected face
            x, y, fw, fh = max(faces, key=lambda f: f[2] * f[3])

            # Add 30% padding
            pad_x = int(fw * 0.3)
            pad_y = int(fh * 0.3)
            h, w = img_np.shape[:2]

            x1 = max(0, x - pad_x)
            y1 = max(0, y - pad_y)
            x2 = min(w, x + fw + pad_x)
            y2 = min(h, y + fh + pad_y)

            face_crop = img_np[y1:y2, x1:x2]
            logger.info(f"Face detected at ({x},{y}) size {fw}x{fh}")
        elif person_mask is not None:
            # Fallback: crop top 25% of person area
            ys, xs = np.where(person_mask > 0)
            if len(ys) == 0:
                return False

            y_min, y_max = ys.min(), ys.max()
            x_min, x_max = xs.min(), xs.max()
            person_height = y_max - y_min

            head_bottom = int(y_min + person_height * 0.25)
            face_crop = img_np[y_min:head_bottom, x_min:x_max]
            logger.info("Face not detected, using top-of-person fallback")
        else:
            # Last resort: top-center crop
            h, w = img_np.shape[:2]
            crop_h = int(h * 0.25)
            crop_w = int(w * 0.4)
            x_start = (w - crop_w) // 2
            face_crop = img_np[0:crop_h, x_start : x_start + crop_w]
            logger.info("No mask or face, using top-center fallback")

        if face_crop.size == 0:
            return False

        # Resize to square thumbnail
        face_pil = Image.fromarray(face_crop)
        face_pil = face_pil.resize((size, size), Image.LANCZOS)
        face_pil.save(output_path, "JPEG", quality=90)
        logger.info(f"Face thumbnail saved: {output_path}")
        return True

    except Exception as e:
        logger.error(f"Error during face detection / thumbnail extraction: {e}", exc_info=True)
        return False

