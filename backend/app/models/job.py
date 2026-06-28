from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any


class JobStatus(StrEnum):
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class UploadKind(StrEnum):
    PERSON = "person"
    GARMENT = "garment"


@dataclass
class JobError:
    code: str
    message: str


@dataclass
class UploadRecord:
    upload_id: str
    kind: UploadKind
    original_filename: str
    content_type: str
    size_bytes: int
    relative_path: str
    created_at: datetime


@dataclass
class Job:
    job_id: str
    status: JobStatus
    progress: int
    person_upload_id: str
    garment_upload_id: str
    garment_category: str
    person_path: str | None = None
    garment_path: str | None = None
    result_path: str | None = None
    stage: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    error: JobError | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
