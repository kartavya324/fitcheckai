from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.models.job import Job, JobStatus


class JobErrorSchema(BaseModel):
    code: str
    message: str


class JobCreateRequest(BaseModel):
    person_upload_id: str
    garment_upload_id: str
    garment_category: str = "T-Shirt"
    metadata: dict[str, Any] = Field(default_factory=dict)


class JobCreatedResponse(BaseModel):
    job_id: str
    status: JobStatus


class JobStatusResponse(BaseModel):
    job_id: str
    status: JobStatus
    progress: int = Field(ge=0, le=100)
    stage: str | None = None
    result_url: str | None = None


class JobResponse(BaseModel):
    job_id: str
    status: JobStatus
    progress: int = Field(ge=0, le=100)
    stage: str | None = None
    person_upload_id: str
    garment_upload_id: str
    garment_category: str
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error: JobErrorSchema | None = None
    result_url: str | None = None
    status_url: str | None = None


class JobResultResponse(BaseModel):
    job_id: str
    result_url: str
    content_type: str
    size_bytes: int | None = None
    width: int | None = None
    height: int | None = None
    completed_at: datetime


class JobListItem(BaseModel):
    job_id: str
    status: JobStatus
    garment_category: str
    result_url: str | None = None
    created_at: datetime
    completed_at: datetime | None = None


class JobListResponse(BaseModel):
    items: list[JobListItem]
    total: int
    limit: int
    offset: int


def job_to_created_response(job: Job) -> JobCreatedResponse:
    return JobCreatedResponse(job_id=job.job_id, status=job.status)


def job_to_status_response(job: Job) -> JobStatusResponse:
    return JobStatusResponse(
        job_id=job.job_id,
        status=job.status,
        progress=job.progress,
        stage=job.stage,
    )
