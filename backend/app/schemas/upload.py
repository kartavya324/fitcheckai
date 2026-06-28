from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from app.models.job import UploadKind, UploadRecord


class UploadKindSchema(StrEnum):
    PERSON = "person"
    GARMENT = "garment"


class UploadCreatedResponse(BaseModel):
    """Minimal response returned after a successful upload."""

    upload_id: str
    kind: UploadKindSchema
    url: str


class UploadResponse(BaseModel):
    """Full upload metadata (e.g. GET /uploads/{id})."""

    model_config = ConfigDict(from_attributes=True)

    upload_id: str
    kind: UploadKindSchema
    original_filename: str
    content_type: str
    size_bytes: int = Field(ge=0)
    url: str
    created_at: datetime


def upload_kind_to_schema(kind: UploadKind) -> UploadKindSchema:
    return UploadKindSchema(kind.value)


def record_to_created_response(
    record: UploadRecord,
    *,
    url: str,
) -> UploadCreatedResponse:
    return UploadCreatedResponse(
        upload_id=record.upload_id,
        kind=upload_kind_to_schema(record.kind),
        url=url,
    )


def record_to_response(record: UploadRecord, *, url: str) -> UploadResponse:
    return UploadResponse(
        upload_id=record.upload_id,
        kind=upload_kind_to_schema(record.kind),
        original_filename=record.original_filename,
        content_type=record.content_type,
        size_bytes=record.size_bytes,
        url=url,
        created_at=record.created_at,
    )
