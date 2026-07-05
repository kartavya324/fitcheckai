from datetime import datetime, timezone
from sqlalchemy import text
from typing import Any

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
        job_type=model.job_type or "tryon",
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
        job_type=job.job_type,
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

    def create(self, job: Any) -> Job:
        if not isinstance(job, Job):
            job_dict = {}
            if hasattr(job, "__dict__"):
                job_dict = job.__dict__
            elif isinstance(job, dict):
                job_dict = job
            
            import inspect
            from uuid import uuid4
            from datetime import datetime, timezone
            
            job_fields = inspect.signature(Job).parameters.keys()
            kwargs = {}
            for field_name in job_fields:
                if field_name in job_dict:
                    kwargs[field_name] = job_dict[field_name]
            
            if "job_id" not in kwargs:
                kwargs["job_id"] = str(uuid4())
            if "status" not in kwargs:
                kwargs["status"] = JobStatus.QUEUED
            if "progress" not in kwargs:
                kwargs["progress"] = 0
            if "person_upload_id" not in kwargs:
                kwargs["person_upload_id"] = job_dict.get("person_upload_id") or ""
            if "garment_upload_id" not in kwargs:
                kwargs["garment_upload_id"] = job_dict.get("garment_upload_id")
            if "garment_category" not in kwargs:
                kwargs["garment_category"] = job_dict.get("garment_category") or "T-Shirt"
            if "job_type" not in kwargs:
                kwargs["job_type"] = job_dict.get("job_type") or "tryon"
            if "created_at" not in kwargs:
                kwargs["created_at"] = datetime.now(timezone.utc)
            if "updated_at" not in kwargs:
                kwargs["updated_at"] = datetime.now(timezone.utc)
                
            job = Job(**kwargs)
            
        return self.update(job)

    def get(self, job_id: str) -> Job | None:
        with SessionLocal() as db:
            model = db.query(JobModel).filter(JobModel.job_id == job_id).first()
            if model is None:
                return None
            return _model_to_job(model)

    def update(self, job: Job | None = None, job_id: str | None = None, **kwargs) -> Job:
        with SessionLocal() as db:
            target_job_id = job.job_id if job is not None else job_id
            if not target_job_id:
                raise ValueError("Must provide job or job_id to update")
                
            model = db.query(JobModel).filter(JobModel.job_id == target_job_id).first()
            if model is None:
                if job is not None:
                    model = _job_to_model(job)
                    db.add(model)
                else:
                    from app.models.job import JobStatus
                    model = JobModel(
                        job_id=target_job_id,
                        status=JobStatus.QUEUED,
                        progress=0,
                        person_upload_id="",
                        garment_category="T-Shirt",
                        job_type="tryon",
                    )
                    db.add(model)
            
            if job is not None:
                new_model = _job_to_model(job)
                for key, value in new_model.__dict__.items():
                    if not key.startswith("_"):
                        setattr(model, key, value)
            
            from app.models.job import JobStatus, JobError
            for key, value in kwargs.items():
                if key == "metadata":
                    model.metadata_json = value
                elif key == "error" and value is not None:
                    if isinstance(value, JobError):
                        model.error_json = {"code": value.code, "message": value.message}
                    else:
                        model.error_json = value
                elif hasattr(model, key):
                    setattr(model, key, value)
                elif key == "status" and isinstance(value, JobStatus):
                    model.status = value.value
            
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
