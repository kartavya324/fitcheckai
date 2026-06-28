from datetime import UTC, datetime

from app.models.job import Job, JobStatus
from app.repositories.job_repository import JobRepository
from app.db import Base, engine


def test_job_repository_create_and_get(settings) -> None:
    Base.metadata.create_all(bind=engine)
    repo = JobRepository(settings)
    now = datetime.now(UTC)
    job = Job(
        job_id="880e8400-e29b-41d4-a716-446655440003",
        status=JobStatus.QUEUED,
        progress=0,
        person_upload_id="p1",
        garment_upload_id="g1",
        garment_category="T-Shirt",
        created_at=now,
        updated_at=now,
    )
    repo.create(job)
    loaded = repo.get(job.job_id)
    assert loaded is not None
    assert loaded.status == JobStatus.QUEUED

