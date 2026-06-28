from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from app.core.exceptions import ConflictError, NotFoundError
from app.models.job import Job, JobError, JobStatus, UploadKind
from app.repositories.job_repository import JobRepository
from app.services.generation_service import GenerationService
from app.services.upload_service import UploadService


class JobService:
    """Job lifecycle: create, poll, list, progress updates."""

    def __init__(
        self,
        job_repository: JobRepository,
        upload_service: UploadService,
        generation_service: GenerationService,
    ) -> None:
        self._jobs = job_repository
        self._uploads = upload_service
        self._generation = generation_service

    def create_job(
        self,
        *,
        person_upload_id: str,
        garment_upload_id: str,
        garment_category: str = "T-Shirt",
        metadata: dict[str, Any] | None = None,
    ) -> Job:
        person = self._uploads.resolve_for_job(person_upload_id, UploadKind.PERSON)
        garment = self._uploads.resolve_for_job(garment_upload_id, UploadKind.GARMENT)

        now = datetime.now(UTC)
        job = Job(
            job_id=str(uuid4()),
            status=JobStatus.QUEUED,
            progress=0,
            person_upload_id=person.upload_id,
            garment_upload_id=garment.upload_id,
            garment_category=garment_category,
            person_path=person.relative_path,
            garment_path=garment.relative_path,
            stage=None,
            metadata=metadata or {},
            created_at=now,
            updated_at=now,
        )
        return self._jobs.create(job)

    def get_job(self, job_id: str) -> Job:
        job = self._jobs.get(job_id)
        if job is None:
            raise NotFoundError(
                f"Job not found: {job_id}",
                details={"job_id": job_id},
            )
        return job

    def get_job_result(self, job_id: str) -> Job:
        job = self.get_job(job_id)
        if job.status != JobStatus.COMPLETED:
            raise ConflictError(
                f"Job {job_id} is not completed yet",
                details={"job_id": job_id, "status": job.status.value},
            )
        return job

    def list_jobs(self, *, limit: int = 20, offset: int = 0) -> tuple[list[Job], int]:
        return self._jobs.list(limit=limit, offset=offset)

    def update_progress(self, job_id: str, *, progress: int, stage: str | None) -> Job:
        job = self.get_job(job_id)
        job.progress = max(0, min(100, progress))
        job.stage = stage
        job.updated_at = datetime.now(UTC)
        return self._jobs.update(job)

    def mark_processing(self, job_id: str) -> Job:
        job = self.get_job(job_id)
        if job.status not in (JobStatus.QUEUED,):
            raise ConflictError(
                f"Job {job_id} cannot start processing from status {job.status.value}",
                details={"job_id": job_id, "status": job.status.value},
            )
        now = datetime.now(UTC)
        job.status = JobStatus.PROCESSING
        job.progress = 0
        job.stage = "processing"
        job.started_at = now
        job.updated_at = now
        job.error = None
        return self._jobs.update(job)

    def mark_completed(self, job_id: str, *, result_path: str | None = None) -> Job:
        job = self.get_job(job_id)
        now = datetime.now(UTC)
        job.status = JobStatus.COMPLETED
        job.progress = 100
        job.stage = None
        job.result_path = result_path
        job.completed_at = now
        job.updated_at = now
        job.error = None
        return self._jobs.update(job)

    def mark_failed(self, job_id: str, *, code: str, message: str) -> Job:
        job = self.get_job(job_id)
        now = datetime.now(UTC)
        job.status = JobStatus.FAILED
        job.stage = None
        job.error = JobError(code=code, message=message)
        job.updated_at = now
        return self._jobs.update(job)
