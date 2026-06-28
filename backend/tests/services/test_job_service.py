from app.models.job import JobStatus


def test_job_status_enum_values() -> None:
    assert JobStatus.QUEUED == "queued"
    assert JobStatus.PROCESSING == "processing"
    assert JobStatus.COMPLETED == "completed"
    assert JobStatus.FAILED == "failed"
    assert JobStatus.CANCELLED == "cancelled"
