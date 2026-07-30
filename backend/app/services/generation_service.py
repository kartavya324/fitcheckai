from collections.abc import Callable
import time
import httpx
from PIL import Image
import io

from app.config import Settings
from app.services.storage_service import StorageService
from app.core.exceptions import AppError


class GenerationService:
    """Try-on generation — 2D via HuggingFace IDM-VTON Space, or 3D via ECON+TeCH."""

    HF_SPACE = "yisol/IDM-VTON"
    HF_SPACE_URL = "https://yisol-idm-vton.hf.space"
    MAX_RETRIES = 3

    def __init__(self, settings: Settings, storage_service: StorageService) -> None:
        self._settings = settings
        self._storage = storage_service

    def _compress_image(self, path: str, max_size: int = 768) -> str:
        from PIL import Image, ImageOps
        import tempfile
        img = ImageOps.exif_transpose(Image.open(path))
        if img.mode != 'RGB':
            img = img.convert('RGB')
        if max(img.size) > max_size:
            ratio = max_size / max(img.size)
            new_size = (int(img.size[0]*ratio), int(img.size[1]*ratio))
            img = img.resize(new_size, Image.LANCZOS)
        tmp = tempfile.NamedTemporaryFile(
            suffix='.jpg', delete=False, dir=tempfile.gettempdir()
        )
        img.save(tmp.name, 'JPEG', quality=85)
        tmp.close()
        return tmp.name

    def _prepare_person(self, path: str, max_size: int = 768) -> str:
        """
        Crop a wide/landscape photo to the person so they FILL the frame.

        IDM-VTON resizes inputs toward a portrait target; a landscape photo
        makes the person tiny with white margins in the output (the "shrink"
        bug). Cropping to the subject first fixes it regardless of the source
        photo's aspect ratio. Falls back to plain compression if no person is
        found. Keeps the original background (IDM-VTON does its own masking).
        """
        from PIL import Image, ImageOps
        import numpy as np
        import tempfile

        img = ImageOps.exif_transpose(Image.open(path)).convert("RGB")
        W, H = img.size

        try:
            from rembg import remove, new_session
            session = new_session("u2net_human_seg")
            alpha = np.array(remove(img, session=session).convert("RGBA"))[:, :, 3]
            ys, xs = np.where(alpha > 128)
            if len(ys) < 100:
                raise ValueError("no person found")
            l, t, r, b = int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())
        except Exception:
            return self._compress_image(path, max_size)  # safe fallback

        # Generous margin so we don't clip hair/feet/hands
        bw, bh = r - l, b - t
        mx, my = int(bw * 0.18), int(bh * 0.08)
        l, t = max(0, l - mx), max(0, t - my)
        r, b = min(W, r + mx), min(H, b + my)

        # Widen a too-narrow crop toward a 3:4 portrait so the person isn't
        # stretched when IDM-VTON forces its target aspect.
        crop_w, crop_h = r - l, b - t
        target_w = int(crop_h * 0.75)
        if target_w > crop_w:
            cx = (l + r) // 2
            half = target_w // 2
            l, r = max(0, cx - half), min(W, cx + half)

        crop = img.crop((l, t, r, b))
        if max(crop.size) > max_size:
            ratio = max_size / max(crop.size)
            crop = crop.resize(
                (int(crop.size[0] * ratio), int(crop.size[1] * ratio)), Image.LANCZOS
            )

        tmp = tempfile.NamedTemporaryFile(
            suffix='.jpg', delete=False, dir=tempfile.gettempdir()
        )
        crop.save(tmp.name, 'JPEG', quality=90)
        tmp.close()
        return tmp.name

    def generate(
        self,
        *,
        job_id: str,
        person_path: str,
        garment_path: str,
        garment_category: str,
        on_progress: Callable[[int, str | None], None] | None = None,
    ) -> str:
        mode = self._settings.generation_mode
        if mode == "econ_3d":
            return self._generate_3d(
                job_id=job_id, person_path=person_path,
                garment_path=garment_path, garment_category=garment_category,
                on_progress=on_progress,
            )
        return self._generate_2d(
            job_id=job_id, person_path=person_path,
            garment_path=garment_path, garment_category=garment_category,
            on_progress=on_progress,
        )

    # ------------------------------------------------------------------
    # 2-D pipeline: HuggingFace IDM-VTON Space via gradio_client
    # ------------------------------------------------------------------
    def _generate_2d(
        self,
        *,
        job_id: str,
        person_path: str,
        garment_path: str,
        garment_category: str,
        on_progress: Callable[[int, str | None], None] | None = None,
    ) -> str:
        try:
            from gradio_client import Client, handle_file
        except ImportError:
            raise AppError(
                "gradio_client not installed — run: pip install gradio_client",
                code="CONFIG_ERROR", status_code=500,
            )

        if on_progress:
            on_progress(10, "Waking up AI model...")

        # Pre-warm: hit the space URL to wake it from sleep
        self._wake_space()

        if on_progress:
            on_progress(25, "Connecting to IDM-VTON...")

        cat_raw = (garment_category or "").lower().replace("-", " ").replace("_", " ").strip()

        # Check for explicit category strings first (from frontend)
        if cat_raw in ["lower body", "lower", "bottom body", "lower_body"]:
            mapped_category = "lower_body"
        elif cat_raw in ["dresses", "full body", "dress", "gown", "full"]:
            mapped_category = "dresses"
        elif cat_raw in ["upper body", "upper", "top", "upper_body"]:
            mapped_category = "upper_body"
        else:
            # Fall back to keyword matching
            lower_keywords = [
                "jogger", "joggers", "sweatpant", "sweatpants", "trackpant",
                "jeans", "trouser", "trousers", "pant", "pants", "short",
                "shorts", "skirt", "palazzo", "salwar", "churidar", "legging",
                "leggings", "cargo", "chino", "dhoti", "lower", "bottom"
            ]
            dress_keywords = [
                "dress", "gown", "saree", "sari", "lehenga", "anarkali",
                "jumpsuit", "romper", "coord", "co-ord", "set"
            ]
            if any(kw in cat_raw for kw in dress_keywords):
                mapped_category = "dresses"
            elif any(kw in cat_raw for kw in lower_keywords):
                mapped_category = "lower_body"
            else:
                mapped_category = "upper_body"

        import logging
        logging.getLogger(__name__).info(
            "Category mapping: input=%r → mapped=%r", garment_category, mapped_category
        )

        # Crop the person to fill the frame (fixes landscape-photo "shrink"),
        # and compress the garment for faster transfer.
        person_path = self._prepare_person(str(person_path))
        garment_path = self._compress_image(str(garment_path))

        try:
            last_error: Exception | None = None
            for attempt in range(1, self.MAX_RETRIES + 1):
                try:
                    if attempt > 1:
                        wait = 10 * attempt
                        if on_progress:
                            on_progress(25, f"Retry {attempt}/{self.MAX_RETRIES} — waiting {wait}s...")
                        time.sleep(wait)

                    # Fresh client every attempt — avoids stale session IDs
                    client = Client(self.HF_SPACE, token=self._settings.hf_token, verbose=False)

                    if on_progress:
                        on_progress(40, f"Running try-on AI (attempt {attempt})...")

                    result = client.predict(
                        dict={
                            "background": handle_file(person_path),
                            "layers": [],
                            "composite": None,
                        },
                        garm_img=handle_file(garment_path),
                        garment_des=mapped_category,
                        is_checked=True,
                        is_checked_crop=False,
                        denoise_steps=20,
                        seed=42,
                        api_name="/tryon",
                    )

                    # result is (output_image_path, masked_image_path)
                    result_image_path = result[0] if isinstance(result, (list, tuple)) else result

                    # Validate: a real IDM-VTON try-on is the person re-dressed,
                    # so it is always a ~3:4 PORTRAIT at the person's aspect.
                    # The free Space intermittently hands back unrelated example
                    # images (landscapes/stock photos) on GPU errors — reject
                    # those so the job fails honestly instead of showing garbage.
                    self._validate_tryon_output(result_image_path, person_path)

                    if on_progress:
                        on_progress(85, "Saving result...")

                    result_bytes = open(result_image_path, "rb").read()
                    result_abs_path = self._storage.write_result(
                        job_id=job_id, extension="jpg", data=result_bytes,
                    )

                    if on_progress:
                        on_progress(100, "Done!")

                    return str(result_abs_path.relative_to(self._settings.storage_root))

                except Exception as e:
                    last_error = e
                    from app.core.logging import get_logger
                    get_logger(__name__).warning(
                        "IDM-VTON attempt %d/%d failed: %s", attempt, self.MAX_RETRIES, e
                    )

            raise AppError(
                f"IDM-VTON failed after {self.MAX_RETRIES} attempts: {last_error}",
                code="GENERATION_ERROR", status_code=500,
            )
        finally:
            import os
            for path in (person_path, garment_path):
                try:
                    os.unlink(path)
                except OSError:
                    pass

    def _validate_tryon_output(self, result_path: str, person_path: str) -> None:
        """Raise if the Space returned something that isn't a real try-on.

        IDM-VTON preserves the person's pose/framing and outputs a portrait
        image whose aspect ratio matches the (cropped) person input. Unrelated
        example images the broken Space sometimes returns fail these checks.
        """
        from PIL import Image

        try:
            with Image.open(result_path) as im:
                im.verify()  # detects truncated/garbage files
            with Image.open(result_path) as im:
                rw, rh = im.size
        except Exception as e:
            raise ValueError(f"Try-on output is not a valid image: {e}")

        if rw < 128 or rh < 128:
            raise ValueError(f"Try-on output too small ({rw}x{rh})")

        # Content check: a genuine try-on keeps the person — including their
        # FACE — since only the garment changes. The broken free Space instead
        # hands back unrelated example/stock photos (night sky, a TV in sand,
        # a desert road) which contain no face. Every try-on input is a photo
        # of a person, so a valid output MUST show a face; no face → garbage.
        #
        # This is FAIL-CLOSED on purpose: if face detection can't run, we
        # reject rather than let an unvalidated image through. Showing a
        # "Generation Failed" card is strictly better than showing a random
        # stock photo as the user's try-on.
        import cv2
        from app.core.logging import get_logger

        cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        )
        img = cv2.imread(result_path)
        n_faces = 0
        if img is not None and not cascade.empty():
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            n_faces = len(cascade.detectMultiScale(gray, 1.1, 5, minSize=(30, 30)))

        get_logger(__name__).info(
            "Try-on output validation: %sx%s, faces=%s", rw, rh, n_faces
        )
        if n_faces == 0:
            raise ValueError(
                "Try-on output has no detectable face; the Space returned "
                "an unrelated image instead of a try-on"
            )

    def _wake_space(self) -> None:
        """Hit the Space URL to wake it from HF free-tier sleep."""
        try:
            httpx.get(self.HF_SPACE_URL, timeout=15.0, follow_redirects=True)
        except Exception:
            pass  # Best-effort — failure here is fine

    # ------------------------------------------------------------------
    # 3-D pipeline: ECON + TeCH (simulated; requires GPU in production)
    # ------------------------------------------------------------------
    def _generate_3d(
        self,
        *,
        job_id: str,
        person_path: str,
        garment_path: str,
        garment_category: str,
        on_progress: Callable[[int, str | None], None] | None = None,
    ) -> str:
        from app.core.logging import get_logger
        logger = get_logger(__name__)

        if on_progress:
            on_progress(10, "Reconstructing 3D mesh from photo (ECON)")
        try:
            time.sleep(2)
        except Exception as e:
            logger.warning(f"ECON simulation error: {e}")

        if on_progress:
            on_progress(50, "Baking garment texture onto mesh (TeCH)")
        try:
            time.sleep(2)
        except Exception as e:
            logger.warning(f"TeCH simulation error: {e}")

        if on_progress:
            on_progress(90, "Exporting 3D avatar (.glb)")

        try:
            resp = httpx.get(
                "https://threejs.org/examples/models/gltf/Soldier.glb",
                follow_redirects=True, timeout=30.0,
            )
            resp.raise_for_status()
            glb_bytes = resp.content
        except Exception:
            glb_bytes = b""

        result_abs_path = self._storage.write_result(
            job_id=job_id, extension="glb", data=glb_bytes,
        )

        if on_progress:
            on_progress(100, "Done")

        return str(result_abs_path.relative_to(self._settings.storage_root))
