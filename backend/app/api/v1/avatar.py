from fastapi import APIRouter, UploadFile, File, Form, HTTPException
import uuid
import asyncio
from datetime import datetime, UTC

from app.services.avatar_generation_service import AvatarGenerationService
from app.services.generation_service import GenerationService
from app.services.storage_service import StorageService
from app.repositories.job_repository import JobRepository
from app.workers.avatar_job_runner import AvatarJobRunner, get_avatar_progress
from app.models.job import Job, JobStatus
from app.config import get_settings

router = APIRouter(prefix="/avatar", tags=["avatar"])


@router.post("/create", status_code=202)
async def create_avatar(
    person_image: UploadFile = File(...),
    back_image: UploadFile = File(None),
):
    """
    Accept a person photo (and an OPTIONAL back photo) and start avatar
    generation. Returns a job_id to poll for status. When a back photo is
    provided, the back of the avatar is textured from it instead of synthesized.
    """
    settings = get_settings()

    # Validate file (HEIC accepted — pillow-heif decodes it server-side)
    allowed = {"image/jpeg", "image/png", "image/webp", "image/heic", "image/heif"}
    if person_image.content_type not in allowed:
        raise HTTPException(400, "Image must be JPEG, PNG, WebP, or HEIC")

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

    # Optional back photo
    back_image_path = None
    if back_image is not None and back_image.filename:
        if back_image.content_type not in allowed:
            raise HTTPException(400, "Back image must be JPEG, PNG, or WebP")
        back_content = await back_image.read()
        if len(back_content) > settings.max_upload_bytes:
            raise HTTPException(400, "Back image too large")
        back_path = avatar_upload_dir / f"{session_id}_back.jpg"
        back_path.write_bytes(back_content)
        back_image_path = str(back_path)

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
            back_image_path=back_image_path,
        )
    )

    return {
        "job_id": job.job_id,
        "session_id": session_id,
        "status": "processing",
        "message": "Avatar generation started",
        "poll_url": f"/api/v1/avatar/status/{job.job_id}",
    }


@router.post("/tryon", status_code=202)
async def avatar_tryon(
    session_id: str = Form(...),
    garment_image: UploadFile = File(...),
    garment_category: str = Form("upper_body"),
):
    """
    Try a garment on an existing 3D avatar.

    Pipeline: 2D virtual try-on (IDM-VTON) dresses the avatar's source photo
    in the garment, then the dressed photo is re-projected onto the avatar's
    mesh — so the outfit appears on the 3D model. Poll /avatar/status/{job_id}.
    """
    settings = get_settings()

    # The avatar and its source photo must exist for this session
    avatar_glb = settings.storage_root / "avatars" / f"{session_id}.glb"
    person_photo = settings.storage_root / "avatars" / "uploads" / f"{session_id}.jpg"
    if not avatar_glb.exists() or not person_photo.exists():
        raise HTTPException(
            404, "Avatar not found for this session. Generate an avatar first."
        )

    allowed = {"image/jpeg", "image/png", "image/webp", "image/heic", "image/heif"}
    if garment_image.content_type not in allowed:
        raise HTTPException(400, "Garment image must be JPEG, PNG, WebP, or HEIC")
    content = await garment_image.read()
    if len(content) > settings.max_upload_bytes:
        raise HTTPException(
            400,
            f"Image too large. Max {settings.max_upload_bytes // 1_048_576}MB",
        )

    job_id = str(uuid.uuid4())
    garment_dir = settings.storage_root / "avatars" / "uploads"
    garment_dir.mkdir(parents=True, exist_ok=True)
    garment_path = garment_dir / f"{session_id}_garment_{job_id[:8]}.jpg"
    garment_path.write_bytes(content)

    storage = StorageService(settings)
    job_repo = JobRepository(settings)

    now = datetime.now(UTC)
    job = Job(
        job_id=job_id,
        status=JobStatus.QUEUED,
        progress=0,
        person_upload_id=session_id,
        garment_upload_id=None,
        garment_category=garment_category,
        job_type="avatar_tryon",
        person_path=str(person_photo.relative_to(settings.storage_root)),
        garment_path=str(garment_path.relative_to(settings.storage_root)),
        stage="Queued",
        created_at=now,
        updated_at=now,
    )
    job_repo.create(job)

    gen_service = AvatarGenerationService(settings, storage)
    tryon_service = GenerationService(settings, storage)
    runner = AvatarJobRunner(gen_service, job_repo)
    asyncio.create_task(
        runner.run_tryon(
            job_id=job_id,
            session_id=session_id,
            person_image_path=str(person_photo),
            garment_image_path=str(garment_path),
            garment_category=garment_category,
            avatar_glb_path=str(avatar_glb),
            tryon_service=tryon_service,
        )
    )

    return {
        "job_id": job_id,
        "session_id": session_id,
        "status": "processing",
        "message": "Avatar try-on started",
        "poll_url": f"/api/v1/avatar/status/{job_id}",
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
    analysis = None

    if job.status == JobStatus.COMPLETED and job.result_path:
        avatar_url = f"{settings.public_base_url}/files/{job.result_path}"

    error = None
    if job.status == JobStatus.FAILED and job.error:
        error = {"code": job.error.code, "message": job.error.message}

    # Include photo analysis data when available
    if job.metadata and "analysis" in job.metadata:
        raw_analysis = job.metadata["analysis"]
        face_url = None
        if raw_analysis.get("face_thumbnail_path"):
            face_url = f"{settings.public_base_url}/files/{raw_analysis['face_thumbnail_path']}"
        analysis = {
            "dominant_colors": raw_analysis.get("dominant_colors", []),
            "face_thumbnail_url": face_url,
        }

    # Avatar try-on jobs also carry the intermediate 2D dressed photo
    tryon_image_url = None
    if job.metadata and job.metadata.get("tryon_image_path"):
        tryon_image_url = (
            f"{settings.public_base_url}/files/{job.metadata['tryon_image_path']}"
        )

    return {
        "job_id": job_id,
        "status": job.status.value,
        "progress": progress.get("pct", job.progress or 0),
        "stage": progress.get("stage", job.stage or ""),
        "avatar_url": avatar_url,
        "analysis": analysis,
        "tryon_image_url": tryon_image_url,
        "error": error,
    }
