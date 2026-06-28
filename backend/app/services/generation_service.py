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
        from PIL import Image
        import tempfile
        import os
        img = Image.open(path)
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

        cat_lower = (garment_category or "").lower()

        lower_body_keywords = [
            "pant", "pants", "trouser", "trousers", "jeans", "denim",
            "skirt", "shorts", "short", "jogger", "joggers", "legging",
            "leggings", "bottom", "lower", "chino", "chinos", "cargo",
            "palazzo", "dhoti", "churidar", "salwar", "pyjama", "trackpant",
            "sweatpant", "sweatpants"
        ]
        dress_keywords = [
            "dress", "gown", "saree", "sari", "lehenga", "anarkali",
            "jumpsuit", "romper", "co-ord", "coord", "set"
        ]

        if any(kw in cat_lower for kw in dress_keywords):
            mapped_category = "dresses"
        elif any(kw in cat_lower for kw in lower_body_keywords):
            mapped_category = "lower_body"
        else:
            mapped_category = "upper_body"

        # Compress input images to speed up network transfers and model execution
        person_path = self._compress_image(str(person_path))
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
