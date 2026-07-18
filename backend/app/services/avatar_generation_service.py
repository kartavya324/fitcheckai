from pathlib import Path
import base64
import httpx
from app.config import Settings
from app.services.storage_service import StorageService
from app.core.exceptions import AppError
from collections.abc import Callable


class AvatarGenerationService:

    def __init__(self, settings: Settings, storage_service: StorageService) -> None:
        self._settings = settings
        self._storage = storage_service

    def generate(
        self,
        *,
        session_id: str,
        person_image_path: str,
        back_image_path: str | None = None,
        on_progress: Callable[[int, str | None], None] | None = None,
    ) -> str:
        """Generate avatar. Returns relative path to .glb file.

        `back_image_path` is optional — when given, the back of the avatar is
        textured from that real photo instead of being synthesized.
        """
        if self._settings.avatar_mode == "runpod":
            return self._generate_runpod(
                session_id=session_id,
                person_image_path=person_image_path,
                on_progress=on_progress,
            )
        if self._settings.avatar_mode == "local_pifuhd":
            return self._generate_local_pifuhd(
                session_id=session_id,
                person_image_path=person_image_path,
                back_image_path=back_image_path,
                on_progress=on_progress,
            )
        return self._generate_stub(
            session_id=session_id,
            person_image_path=person_image_path,
            on_progress=on_progress,
        )

    def _generate_stub(self, *, session_id, person_image_path, on_progress=None):
        """Download a placeholder .glb for development/testing."""
        if on_progress:
            on_progress(10, "Initialising avatar pipeline...")

        glb_urls = [
            "https://threejs.org/examples/models/gltf/Soldier.glb",
            "https://threejs.org/examples/models/gltf/RobotExpressive/RobotExpressive.glb",
        ]

        glb_bytes = None
        last_error = None

        for url in glb_urls:
            try:
                if on_progress:
                    on_progress(30, "Downloading avatar model...")
                response = httpx.get(url, follow_redirects=True, timeout=60.0)
                response.raise_for_status()
                glb_bytes = response.content
                break
            except Exception as e:
                last_error = e
                continue

        if not glb_bytes:
            raise AppError(
                f"Failed to download stub avatar: {last_error}",
                code="AVATAR_ERROR",
                status_code=500,
            )

        if on_progress:
            on_progress(70, "Processing avatar...")

        result_path = self._save_avatar_glb(session_id, glb_bytes)

        if on_progress:
            on_progress(100, "Avatar ready!")

        return result_path

    def _generate_runpod(self, *, session_id, person_image_path, on_progress=None):
        """Call RunPod serverless endpoint running ECON+TeCH pipeline."""
        if not self._settings.runpod_api_key:
            raise AppError(
                "RUNPOD_API_KEY not set",
                code="CONFIG_ERROR",
                status_code=500,
            )
        if not self._settings.runpod_endpoint_id:
            raise AppError(
                "RUNPOD_ENDPOINT_ID not set",
                code="CONFIG_ERROR",
                status_code=500,
            )

        if on_progress:
            on_progress(10, "Uploading photo to GPU server...")

        image_b64 = base64.b64encode(
            open(person_image_path, "rb").read()
        ).decode()

        if on_progress:
            on_progress(25, "Reconstructing 3D body mesh...")

        url = f"https://api.runpod.ai/v2/{self._settings.runpod_endpoint_id}/runsync"
        headers = {"Authorization": f"Bearer {self._settings.runpod_api_key}"}
        payload = {
            "input": {
                "image_base64": image_b64,
                "pipeline": "econ_tech",
                "output_format": "glb",
            }
        }

        try:
            response = httpx.post(
                url, json=payload, headers=headers, timeout=300.0
            )
            response.raise_for_status()
        except Exception as e:
            raise AppError(
                f"RunPod API error: {e}",
                code="RUNPOD_ERROR",
                status_code=500,
            ) from e

        if on_progress:
            on_progress(80, "Baking texture onto mesh...")

        result = response.json()
        try:
            glb_b64 = result["output"]["glb_base64"]
            glb_bytes = base64.b64decode(glb_b64)
        except Exception as e:
            raise AppError(
                f"Invalid RunPod response: {e}",
                code="RUNPOD_ERROR",
                status_code=500,
            ) from e

        if on_progress:
            on_progress(95, "Saving avatar...")

        result_path = self._save_avatar_glb(session_id, glb_bytes)

        if on_progress:
            on_progress(100, "Avatar ready!")

        return result_path

    def _generate_local_pifuhd(
        self, *, session_id, person_image_path, back_image_path=None, on_progress=None
    ):
        """Call local PIFuHD Flask server (pifuhd_server.py) running on this machine."""
        local_url = getattr(self._settings, "local_inference_url", "http://localhost:8090")

        if on_progress:
            on_progress(10, "Uploading photo to local PIFuHD server...")

        with open(person_image_path, "rb") as f:
            image_b64 = base64.b64encode(f.read()).decode()

        payload = {"image_base64": image_b64}
        if back_image_path:
            with open(back_image_path, "rb") as f:
                payload["back_image_base64"] = base64.b64encode(f.read()).decode()

        if on_progress:
            on_progress(25, "Reconstructing 3D body mesh (3-6 min on RTX 3050)...")

        try:
            response = httpx.post(
                f"{local_url}/generate",
                json=payload,
                # Generous: PIFuHD may retry at coarser resolutions after a
                # CUDA OOM (~3.5 min per failed attempt on a 4GB GPU).
                timeout=900.0,
            )
            response.raise_for_status()
        except httpx.ConnectError as e:
            raise AppError(
                "Local PIFuHD server is not running. Start start_pifuhd_server.bat first.",
                code="PIFUHD_UNAVAILABLE",
                status_code=503,
            ) from e
        except Exception as e:
            raise AppError(
                f"Local PIFuHD server error: {e}",
                code="PIFUHD_ERROR",
                status_code=500,
            ) from e

        if on_progress:
            on_progress(80, "Converting mesh to GLB...")

        result = response.json()
        if "error" in result:
            raise AppError(
                f"PIFuHD inference failed: {result['error']}",
                code="PIFUHD_ERROR",
                status_code=500,
            )

        try:
            glb_bytes = base64.b64decode(result["glb_base64"])
        except Exception as e:
            raise AppError(
                f"Invalid PIFuHD server response: {e}",
                code="PIFUHD_ERROR",
                status_code=500,
            ) from e

        if on_progress:
            on_progress(95, "Saving avatar...")

        result_path = self._save_avatar_glb(session_id, glb_bytes)

        if on_progress:
            on_progress(100, "Avatar ready!")

        return result_path

    def recolor_avatar(
        self,
        *,
        glb_path: str,
        image_path: str,
        output_name: str,
        on_progress: Callable[[int, str | None], None] | None = None,
    ) -> str:
        """Re-texture an existing avatar GLB from a new photo (e.g. a 2D
        try-on result) via the local PIFuHD server's /recolor endpoint.
        Returns relative path to the new .glb."""
        local_url = getattr(self._settings, "local_inference_url", "http://localhost:8090")

        if on_progress:
            on_progress(70, "Projecting outfit onto your 3D avatar...")

        payload = {
            "glb_base64": base64.b64encode(open(glb_path, "rb").read()).decode(),
            "image_base64": base64.b64encode(open(image_path, "rb").read()).decode(),
        }

        try:
            response = httpx.post(
                f"{local_url}/recolor", json=payload, timeout=180.0
            )
            response.raise_for_status()
        except httpx.ConnectError as e:
            raise AppError(
                "Local PIFuHD server is not running. Start it first.",
                code="PIFUHD_UNAVAILABLE",
                status_code=503,
            ) from e
        except Exception as e:
            raise AppError(
                f"Avatar recolor failed: {e}",
                code="PIFUHD_ERROR",
                status_code=500,
            ) from e

        result = response.json()
        if "error" in result:
            raise AppError(
                f"Avatar recolor failed: {result['error']}",
                code="PIFUHD_ERROR",
                status_code=500,
            )

        glb_bytes = base64.b64decode(result["glb_base64"])
        avatar_dir = self._settings.storage_root / "avatars"
        avatar_dir.mkdir(parents=True, exist_ok=True)
        out_path = avatar_dir / f"{output_name}.glb"
        out_path.write_bytes(glb_bytes)
        return str(out_path.relative_to(self._settings.storage_root))

    def _save_avatar_glb(self, session_id: str, glb_bytes: bytes) -> str:
        """Save .glb bytes and return relative path."""
        avatar_dir = self._settings.storage_root / "avatars"
        avatar_dir.mkdir(parents=True, exist_ok=True)
        avatar_path = avatar_dir / f"{session_id}.glb"
        avatar_path.write_bytes(glb_bytes)
        return str(avatar_path.relative_to(self._settings.storage_root))
