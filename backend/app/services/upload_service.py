from datetime import UTC, datetime
from uuid import uuid4

from app.config import Settings
from app.core.exceptions import NotFoundError, ValidationError
from app.models.job import UploadKind, UploadRecord
from app.services.media_validation import normalize_content_type, validate_image_upload
from app.services.storage_service import StorageService


class UploadService:
    """Validate and persist person/garment uploads."""

    def __init__(self, storage_service: StorageService, settings: Settings) -> None:
        self._storage = storage_service
        self._settings = settings

    async def save_person_upload(
        self,
        *,
        filename: str,
        content_type: str,
        data: bytes,
    ) -> UploadRecord:
        return await self._save_upload(
            kind=UploadKind.PERSON,
            filename=filename,
            content_type=content_type,
            data=data,
        )

    async def save_garment_upload(
        self,
        *,
        filename: str,
        content_type: str,
        data: bytes,
    ) -> UploadRecord:
        return await self._save_upload(
            kind=UploadKind.GARMENT,
            filename=filename,
            content_type=content_type,
            data=data,
        )

    async def _save_upload(
        self,
        *,
        kind: UploadKind,
        filename: str,
        content_type: str,
        data: bytes,
    ) -> UploadRecord:
        normalized_type = normalize_content_type(content_type)
        extension = validate_image_upload(
            data=data,
            content_type=normalized_type,
            allowed_content_types=self._settings.allowed_content_types,
            max_upload_bytes=self._settings.max_upload_bytes,
        )

        upload_id = str(uuid4())
        created_at = datetime.now(UTC)
        relative_path = self._storage.relative_upload_path(upload_id, kind, extension)

        self._storage.write_upload(
            upload_id=upload_id,
            kind=kind,
            extension=extension,
            data=data,
        )

        record = UploadRecord(
            upload_id=upload_id,
            kind=kind,
            original_filename=filename or f"upload.{extension}",
            content_type=normalized_type,
            size_bytes=len(data),
            relative_path=relative_path,
            created_at=created_at,
        )

        self._storage.write_upload_metadata(
            upload_id,
            {
                "upload_id": record.upload_id,
                "kind": record.kind.value,
                "original_filename": record.original_filename,
                "content_type": record.content_type,
                "size_bytes": record.size_bytes,
                "relative_path": record.relative_path,
                "extension": extension,
                "created_at": record.created_at.isoformat(),
            },
        )

        return record

    def get_upload(self, upload_id: str) -> UploadRecord | None:
        metadata = self._storage.read_upload_metadata(upload_id)
        if metadata is None:
            return None
        return _metadata_to_record(metadata)

    def resolve_for_job(self, upload_id: str, expected_kind: UploadKind) -> UploadRecord:
        record = self.get_upload(upload_id)
        if record is None:
            raise NotFoundError(
                f"Upload not found: {upload_id}",
                details={"upload_id": upload_id},
            )
        if record.kind != expected_kind:
            raise ValidationError(
                f"Upload {upload_id} is not a {expected_kind.value} image",
                details={
                    "upload_id": upload_id,
                    "expected_kind": expected_kind.value,
                    "actual_kind": record.kind.value,
                },
            )
        if self._storage.resolve_upload_path(upload_id, expected_kind) is None:
            raise NotFoundError(
                f"Upload file missing on disk: {upload_id}",
                details={"upload_id": upload_id},
            )
        return record


def _metadata_to_record(metadata: dict[str, object]) -> UploadRecord:
    kind_value = metadata.get("kind")
    if kind_value not in (UploadKind.PERSON.value, UploadKind.GARMENT.value):
        raise ValidationError("Invalid upload metadata: missing or unknown kind")

    created_raw = metadata.get("created_at")
    if isinstance(created_raw, str):
        created_at = datetime.fromisoformat(created_raw.replace("Z", "+00:00"))
    else:
        created_at = datetime.now(UTC)

    return UploadRecord(
        upload_id=str(metadata["upload_id"]),
        kind=UploadKind(str(kind_value)),
        original_filename=str(metadata.get("original_filename", "upload")),
        content_type=str(metadata.get("content_type", "image/jpeg")),
        size_bytes=int(metadata.get("size_bytes", 0)),
        relative_path=str(metadata.get("relative_path", "")),
        created_at=created_at,
    )
