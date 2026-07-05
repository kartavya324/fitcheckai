from fastapi import APIRouter, UploadFile, File, HTTPException
import uuid
import asyncio
from datetime import datetime, UTC

from app.services.avatar_generation_service import AvatarGenerationService
from app.services.storage_service import StorageService
from app.repositories.job_repository import JobRepository
from app.workers.avatar_job_runner import AvatarJobRunner, get_avatar_progress
from app.models.job import Job, JobStatus
from app.config import get_settings

router = APIRouter(prefix="/avatar", tags=["avatar"])


@router.post("/create", status_code=202)
async def create_avatar(person_image: UploadFile = File(...)):
    """
    Accept a person photo and start avatar generation.
    Returns a job_id to poll for status.
    """
    settings = get_settings()

    # Validate file
    allowed = {"image/jpeg", "image/png", "image/webp"}
    if person_image.content_type not in allowed:
        raise HTTPException(400, "Image must be JPEG, PNG, or WebP")

    content = await person_image.read()
    if len(content) > settings.max_upload_bytes:
        raise HTTPException(
            400,
            f"Image too large. Max {settings.max_upload_bytes // 1_048_576}MB",
        )

    # Save uploaded image
    session_id = str(uuid.uuid4())
    avatar_upload_dir = settings.storage_root / "avatars" / "uploads"
    avatar_upload_dir.mkdir(parents=True, exist_ok=True)
    image_path = avatar_upload_dir / f"{session_id}.jpg"
    image_path.write_bytes(content)

    # Create job record
    storage = StorageService(settings)
    job_repo = JobRepository(settings)

    now = datetime.now(UTC)
    job = Job(
        job_id=str(uuid.uuid4()),
        status=JobStatus.QUEUED,
        progress=0,
        person_upload_id=session_id,
        garment_upload_id=None,
        garment_category="avatar",
        job_type="avatar",
        person_path=str(image_path.relative_to(settings.storage_root)),
        stage="Queued",
        created_at=now,
        updated_at=now,
    )
    job_repo.create(job)

    # Launch background task
    gen_service = AvatarGenerationService(settings, storage)
    runner = AvatarJobRunner(gen_service, job_repo)
    asyncio.create_task(
        runner.run(
            job_id=job.job_id,
            session_id=session_id,
            person_image_path=str(image_path),
        )
    )

    return {
        "job_id": job.job_id,
        "session_id": session_id,
        "status": "processing",
        "message": "Avatar generation started",
        "poll_url": f"/api/v1/avatar/status/{job.job_id}",
    }


@router.get("/status/{job_id}")
def get_avatar_status(job_id: str):
    """Poll avatar generation status."""
    settings = get_settings()
    job_repo = JobRepository(settings)
    job = job_repo.get(job_id)

    if not job:
        raise HTTPException(404, "Job not found")

    progress = get_avatar_progress(job_id)
    avatar_url = None

    if job.status == JobStatus.COMPLETED and job.result_path:
        avatar_url = f"{settings.public_base_url}/files/{job.result_path}"

    return {
        "job_id": job_id,
        "status": job.status.value,
        "progress": progress.get("pct", job.progress or 0),
        "stage": progress.get("stage", job.stage or ""),
        "avatar_url": avatar_url,
    }
