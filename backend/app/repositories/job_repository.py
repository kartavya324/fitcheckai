from datetime import datetime, timezone
from sqlalchemy import text

from app.config import Settings
from app.core.logging import get_logger
from app.models.job import Job, JobError, JobStatus
from app.db import SessionLocal, JobModel

logger = get_logger(__name__)

def _ensure_utc(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt

def _model_to_job(model: JobModel) -> Job:
    error = None
    if model.error_json:
        error = JobError(
            code=model.error_json.get("code", "UNKNOWN"),
            message=model.error_json.get("message", "Unknown error"),
        )
        
    return Job(
        job_id=model.job_id,
        status=JobStatus(model.status) if isinstance(model.status, str) else model.status,
        progress=model.progress,
        person_upload_id=model.person_upload_id,
        garment_upload_id=model.garment_upload_id,
        garment_category=model.garment_category,
        person_path=model.person_path,
        garment_path=model.garment_path,
        result_path=model.result_path,
        stage=model.stage,
        metadata=model.metadata_json or {},
        error=error,
        created_at=_ensure_utc(model.created_at),
        updated_at=_ensure_utc(model.updated_at),
        started_at=_ensure_utc(model.started_at),
        completed_at=_ensure_utc(model.completed_at),
    )

def _job_to_model(job: Job) -> JobModel:
    error_json = None
    if job.error:
        error_json = {"code": job.error.code, "message": job.error.message}
        
    return JobModel(
        job_id=job.job_id,
        status=job.status.value if isinstance(job.status, JobStatus) else job.status,
        progress=job.progress,
        person_upload_id=job.person_upload_id,
        garment_upload_id=job.garment_upload_id,
        garment_category=job.garment_category,
        person_path=job.person_path,
        garment_path=job.garment_path,
        result_path=job.result_path,
        stage=job.stage,
        metadata_json=job.metadata,
        error_json=error_json,
        created_at=job.created_at,
        updated_at=job.updated_at,
        started_at=job.started_at,
        completed_at=job.completed_at,
    )

class JobRepository:
    """Persist job records using SQLite."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def create(self, job: Job) -> Job:
        return self.update(job)

    def get(self, job_id: str) -> Job | None:
        with SessionLocal() as db:
            model = db.query(JobModel).filter(JobModel.job_id == job_id).first()
            if model is None:
                return None
            return _model_to_job(model)

    def update(self, job: Job) -> Job:
        with SessionLocal() as db:
            model = db.query(JobModel).filter(JobModel.job_id == job.job_id).first()
            if model is None:
                model = _job_to_model(job)
                db.add(model)
            else:
                new_model = _job_to_model(job)
                for key, value in new_model.__dict__.items():
                    if not key.startswith("_"):
                        setattr(model, key, value)
            db.commit()
            db.refresh(model)
            return _model_to_job(model)

    def list(self, *, limit: int = 20, offset: int = 0) -> tuple[list[Job], int]:
        with SessionLocal() as db:
            total = db.query(JobModel).count()
            models = db.query(JobModel).order_by(JobModel.created_at.desc()).offset(offset).limit(limit).all()
            return [_model_to_job(m) for m in models], total

    def is_reachable(self) -> bool:
        """Readiness check: DB is usable."""
        try:
            with SessionLocal() as db:
                db.execute(text("SELECT 1"))
            return True
        except Exception:
            logger.exception("DB not reachable")
            return False
