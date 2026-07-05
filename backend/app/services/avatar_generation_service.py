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
        on_progress: Callable[[int, str | None], None] | None = None,
    ) -> str:
        """Generate avatar. Returns relative path to .glb file."""
        if self._settings.avatar_mode == "runpod":
            return self._generate_runpod(
                session_id=session_id,
                person_image_path=person_image_path,
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
        except (KeyError, Exception) as e:
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

    def _save_avatar_glb(self, session_id: str, glb_bytes: bytes) -> str:
        """Save .glb bytes and return relative path."""
        avatar_dir = self._settings.storage_root / "avatars"
        avatar_dir.mkdir(parents=True, exist_ok=True)
        avatar_path = avatar_dir / f"{session_id}.glb"
        avatar_path.write_bytes(glb_bytes)
        return str(avatar_path.relative_to(self._settings.storage_root))
