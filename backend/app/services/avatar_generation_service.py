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
                back_image_path=back_image_path,
                on_progress=on_progress,
            )
        # Everything else routes to the real local PIFuHD pipeline. There is
        # deliberately NO stub fallback: serving a generic robot/soldier GLB
        # when generation isn't configured produced a fake avatar that looked
        # like a bug and confused every test. A misconfiguration must fail
        # loudly, never silently ship a placeholder body.
        return self._generate_local_pifuhd(
            session_id=session_id,
            person_image_path=person_image_path,
            back_image_path=back_image_path,
            on_progress=on_progress,
        )

    def _generate_stub_removed(self, *, session_id, person_image_path, on_progress=None):
        """Deprecated. The placeholder-GLB path was removed on purpose — see
        generate(). Kept only as a tombstone so nothing calls it by accident."""
        raise AppError(
            "Stub avatar generation has been removed. Set AVATAR_MODE=local_pifuhd "
            "and run the local PIFuHD server.",
            code="AVATAR_ERROR",
            status_code=500,
        )

        return result_path

    def _generate_runpod(
        self, *, session_id, person_image_path, back_image_path=None, on_progress=None
    ):
        """Call a RunPod serverless endpoint running our PIFuHD handler
        (backend/runpod/handler.py) on a cloud GPU. Uses async /run + polling
        so multi-minute 512³ jobs don't hit the /runsync time limit.

        The handler I/O matches _generate_local_pifuhd: it takes
        {image_base64, back_image_base64?} and returns {glb_base64}.
        """
        import time

        if not self._settings.runpod_api_key:
            raise AppError("RUNPOD_API_KEY not set", code="CONFIG_ERROR", status_code=500)
        if not self._settings.runpod_endpoint_id:
            raise AppError("RUNPOD_ENDPOINT_ID not set", code="CONFIG_ERROR", status_code=500)

        if on_progress:
            on_progress(10, "Uploading photo to cloud GPU...")

        payload_input = {
            "image_base64": base64.b64encode(
                open(person_image_path, "rb").read()
            ).decode()
        }
        if back_image_path:
            payload_input["back_image_base64"] = base64.b64encode(
                open(back_image_path, "rb").read()
            ).decode()

        base = f"https://api.runpod.ai/v2/{self._settings.runpod_endpoint_id}"
        headers = {"Authorization": f"Bearer {self._settings.runpod_api_key}"}

        # Submit the job (async — returns an id immediately)
        try:
            run = httpx.post(
                f"{base}/run", json={"input": payload_input},
                headers=headers, timeout=60.0,
            )
            run.raise_for_status()
            job_id = run.json()["id"]
        except Exception as e:
            raise AppError(f"RunPod submit failed: {e}", code="RUNPOD_ERROR", status_code=500) from e

        if on_progress:
            on_progress(25, "Reconstructing 3D body mesh on cloud GPU...")

        # Poll status until COMPLETED/FAILED (cap ~10 min)
        deadline = time.time() + 600
        result = None
        while time.time() < deadline:
            try:
                st = httpx.get(f"{base}/status/{job_id}", headers=headers, timeout=30.0)
                st.raise_for_status()
                body = st.json()
            except Exception as e:
                raise AppError(f"RunPod status failed: {e}", code="RUNPOD_ERROR", status_code=500) from e

            status = body.get("status")
            if status == "COMPLETED":
                result = body.get("output") or {}
                break
            if status in ("FAILED", "CANCELLED", "TIMED_OUT"):
                raise AppError(
                    f"RunPod job {status}: {body.get('error', '')}",
                    code="RUNPOD_ERROR", status_code=500,
                )
            time.sleep(3)

        if result is None:
            raise AppError("RunPod job timed out", code="RUNPOD_ERROR", status_code=500)
        if "error" in result:
            raise AppError(
                f"Cloud PIFuHD failed: {result['error']}",
                code="RUNPOD_ERROR", status_code=500,
            )

        if on_progress:
            on_progress(90, "Saving avatar...")

        try:
            glb_bytes = base64.b64decode(result["glb_base64"])
        except Exception as e:
            raise AppError(f"Invalid RunPod response: {e}", code="RUNPOD_ERROR", status_code=500) from e

        result_path = self._save_avatar_glb(session_id, glb_bytes)
        if on_progress:
            on_progress(100, "Avatar ready!")
        return result_path

    def _generate_local_pifuhd(
        self, *, session_id, person_image_path, back_image_path=None, on_progress=None
    ):
        """Call local PIFuHD Flask server (pifuhd_server.py) running on this machine."""
        local_url = getattr(self._settings, "local_inference_url", "http://127.0.0.1:8090")

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
        return self._save_avatar_glb(output_name, glb_bytes)

    def _save_avatar_glb(self, name: str, glb_bytes: bytes) -> str:
        """Persist .glb via the storage backend; return its storage key.
        Key doubles as the value stored on the job (job.result_path) and is
        turned into a URL later via the same backend."""
        from app.services.storage_backend import get_storage_backend, content_type_for
        key = f"avatars/{name}.glb"
        get_storage_backend().save(key, glb_bytes, content_type_for(key))
        return key
