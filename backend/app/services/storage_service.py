import json
from pathlib import Path

from app.config import Settings
from app.core.logging import get_logger
from app.models.job import UploadKind

logger = get_logger(__name__)


class StorageService:
    """Local filesystem I/O under storage/."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def _upload_directory(self, kind: UploadKind) -> Path:
        if kind == UploadKind.PERSON:
            return self._settings.uploads_persons_dir
        return self._settings.uploads_garments_dir

    def write_upload(
        self,
        *,
        upload_id: str,
        kind: UploadKind,
        extension: str,
        data: bytes,
    ) -> Path:
        directory = self._upload_directory(kind)
        directory.mkdir(parents=True, exist_ok=True)
        final_path = directory / f"{upload_id}.{extension}"
        temp_path = directory / f".{upload_id}.{extension}.tmp"
        temp_path.write_bytes(data)
        temp_path.replace(final_path)
        return final_path

    def write_upload_metadata(self, upload_id: str, metadata: dict[str, object]) -> Path:
        self._settings.uploads_meta_dir.mkdir(parents=True, exist_ok=True)
        path = self._settings.uploads_meta_dir / f"{upload_id}.json"
        temp_path = self._settings.uploads_meta_dir / f".{upload_id}.json.tmp"
        temp_path.write_text(json.dumps(metadata, default=str), encoding="utf-8")
        temp_path.replace(path)
        return path

    def read_upload_metadata(self, upload_id: str) -> dict[str, object] | None:
        path = self._settings.uploads_meta_dir / f"{upload_id}.json"
        if not path.is_file():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def write_result(self, *, job_id: str, extension: str, data: bytes) -> Path:
        self._settings.results_dir.mkdir(parents=True, exist_ok=True)
        final_path = self._settings.results_dir / f"{job_id}.{extension}"
        temp_path = self._settings.results_dir / f".{job_id}.{extension}.tmp"
        temp_path.write_bytes(data)
        temp_path.replace(final_path)
        return final_path

    def read_bytes(self, relative_path: str) -> bytes:
        path = self._settings.storage_root / Path(relative_path)
        return path.read_bytes()

    def resolve_upload_path(self, upload_id: str, kind: UploadKind) -> Path | None:
        metadata = self.read_upload_metadata(upload_id)
        if metadata is not None:
            relative_path = metadata.get("relative_path")
            if isinstance(relative_path, str):
                path = self._settings.storage_root / Path(relative_path)
                if path.is_file():
                    return path

        directory = self._upload_directory(kind)
        matches = list(directory.glob(f"{upload_id}.*"))
        if not matches:
            return None
        return matches[0]

    def resolve_result_path(self, job_id: str) -> Path | None:
        path_jpg = self._settings.results_dir / f"{job_id}.jpg"
        if path_jpg.is_file():
            return path_jpg
        path_glb = self._settings.results_dir / f"{job_id}.glb"
        if path_glb.is_file():
            return path_glb
        return None

    def exists_upload(self, upload_id: str, kind: UploadKind) -> bool:
        return self.resolve_upload_path(upload_id, kind) is not None

    def exists_result(self, job_id: str) -> bool:
        return self.resolve_result_path(job_id) is not None

    def relative_upload_path(self, upload_id: str, kind: UploadKind, extension: str) -> str:
        folder = "persons" if kind == UploadKind.PERSON else "garments"
        return f"uploads/{folder}/{upload_id}.{extension}"

    def build_upload_url(
        self,
        upload_id: str,
        kind: UploadKind,
        extension: str,
        *,
        base_url: str,
    ) -> str:
        folder = "persons" if kind == UploadKind.PERSON else "garments"
        return f"{base_url.rstrip('/')}/files/uploads/{folder}/{upload_id}.{extension}"

    def build_result_url(self, job_id: str, extension: str = "jpg") -> str:
        path = self.resolve_result_path(job_id)
        if path:
            return f"{self._settings.public_base_url.rstrip('/')}/files/results/{path.name}"
        return f"{self._settings.public_base_url.rstrip('/')}/files/results/{job_id}.{extension}"

    def is_writable(self) -> bool:
        """Readiness check: storage root is writable."""
        try:
            self._settings.ensure_storage_dirs()
            probe = self._settings.storage_root / ".write_probe"
            probe.write_text("", encoding="utf-8")
            probe.unlink(missing_ok=True)
            return True
        except OSError:
            logger.exception("Storage not writable")
            return False
