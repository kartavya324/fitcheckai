import asyncio
import logging

from app.services.avatar_generation_service import AvatarGenerationService
from app.services.generation_service import GenerationService
from app.repositories.job_repository import JobRepository
from app.models.job import Job, JobError, JobStatus

logger = logging.getLogger(__name__)

# In-memory progress overlay keyed by job_id — a fast path for the process
# actually running the job. It is NOT the source of truth: every tick is also
# written to the DB (job.progress/stage), which is what status reads. Returns
# None when this process isn't running the job, so status falls back to the DB
# instead of a bogus 0/"Queued" default (the old 'stuck at Queued' bug).
_avatar_progress: dict[str, dict] = {}


def get_avatar_progress(job_id: str) -> dict | None:
    return _avatar_progress.get(job_id)


class AvatarJobRunner:

    def __init__(
        self,
        avatar_generation_service: AvatarGenerationService,
        job_repository: JobRepository,
    ) -> None:
        self._gen = avatar_generation_service
        self._repo = job_repository

    async def run(
        self, *, job_id: str, session_id: str, person_image_path: str,
        back_image_path: str | None = None,
    ) -> None:
        _avatar_progress[job_id] = {"pct": 0, "stage": "Starting..."}

        def on_progress(pct: int, stage: str | None = None) -> None:
            _avatar_progress[job_id] = {"pct": pct, "stage": stage or ""}
            job = self._repo.get(job_id)
            if job:
                from datetime import datetime, UTC
                job.progress = pct
                job.stage = stage
                job.updated_at = datetime.now(UTC)
                self._repo.update(job)

        try:
            # Mark as processing
            job = self._repo.get(job_id)
            if job:
                from datetime import datetime, UTC
                job.status = JobStatus.PROCESSING
                job.progress = 0
                job.started_at = datetime.now(UTC)
                job.updated_at = datetime.now(UTC)
                self._repo.update(job)

            result_path = await asyncio.to_thread(
                self._gen.generate,
                session_id=session_id,
                person_image_path=person_image_path,
                back_image_path=back_image_path,
                on_progress=on_progress,
            )

            # ── Run photo analysis (clothing colors + face thumbnail) ──
            analysis_data = {}
            try:
                if on_progress:
                    on_progress(92, "Analyzing clothing colors...")
                from app.services.avatar_analysis_service import analyze_person_image
                from app.config import get_settings
                settings = get_settings()
                analysis_dir = str(settings.storage_root / "avatars" / "analysis")
                analysis_data = await asyncio.to_thread(
                    analyze_person_image,
                    person_image_path,
                    session_id,
                    analysis_dir,
                )
                logger.info(f"Photo analysis complete: {len(analysis_data.get('dominant_colors', []))} colors")
            except Exception as e:
                logger.warning(f"Photo analysis failed (non-fatal): {e}", exc_info=True)

            # Mark as completed
            job = self._repo.get(job_id)
            if job:
                from datetime import datetime, UTC
                job.status = JobStatus.COMPLETED
                job.progress = 100
                job.result_path = result_path
                job.stage = None
                job.metadata = job.metadata or {}
                job.metadata["analysis"] = analysis_data
                job.completed_at = datetime.now(UTC)
                job.updated_at = datetime.now(UTC)
                self._repo.update(job)

        except Exception as e:
            logger.error(f"Avatar job {job_id} failed: {e}", exc_info=True)
            job = self._repo.get(job_id)
            if job:
                from datetime import datetime, UTC
                job.status = JobStatus.FAILED
                job.error = JobError(code="AVATAR_ERROR", message=str(e))
                job.updated_at = datetime.now(UTC)
                self._repo.update(job)
        finally:
            _avatar_progress.pop(job_id, None)

    async def run_tryon(
        self,
        *,
        job_id: str,
        session_id: str,
        person_image_path: str,
        garment_image_path: str,
        garment_category: str,
        avatar_glb_path: str,
        tryon_service: GenerationService,
    ) -> None:
        """Avatar try-on pipeline:
        1. 2D virtual try-on (IDM-VTON) — dress the person photo in the garment.
        2. Re-project the dressed photo onto the existing 3D avatar mesh.
        """
        _avatar_progress[job_id] = {"pct": 0, "stage": "Starting..."}

        def on_progress(pct: int, stage: str | None = None) -> None:
            _avatar_progress[job_id] = {"pct": pct, "stage": stage or ""}
            job = self._repo.get(job_id)
            if job:
                from datetime import datetime, UTC
                job.progress = pct
                job.stage = stage
                job.updated_at = datetime.now(UTC)
                self._repo.update(job)

        try:
            job = self._repo.get(job_id)
            if job:
                from datetime import datetime, UTC
                job.status = JobStatus.PROCESSING
                job.progress = 0
                job.started_at = datetime.now(UTC)
                job.updated_at = datetime.now(UTC)
                self._repo.update(job)

            # ── Stage 1: 2D try-on (0–65%) ──
            def tryon_progress(pct: int, stage: str | None = None) -> None:
                on_progress(int(pct * 0.65), stage)

            tryon_image_rel = await asyncio.to_thread(
                tryon_service.generate,
                job_id=job_id,
                person_path=person_image_path,
                garment_path=garment_image_path,
                garment_category=garment_category,
                on_progress=tryon_progress,
            )

            from app.config import get_settings
            settings = get_settings()
            tryon_image_abs = str(settings.storage_root / tryon_image_rel)

            # ── Stage 2: project the dressed photo onto the 3D mesh (65–100%) ──
            on_progress(70, "Projecting outfit onto your 3D avatar...")
            tryon_glb_rel = await asyncio.to_thread(
                self._gen.recolor_avatar,
                glb_path=avatar_glb_path,
                image_path=tryon_image_abs,
                output_name=f"{session_id}_tryon_{job_id[:8]}",
                on_progress=on_progress,
            )

            job = self._repo.get(job_id)
            if job:
                from datetime import datetime, UTC
                job.status = JobStatus.COMPLETED
                job.progress = 100
                job.result_path = tryon_glb_rel
                job.stage = None
                job.metadata = job.metadata or {}
                job.metadata["tryon_image_path"] = tryon_image_rel
                job.completed_at = datetime.now(UTC)
                job.updated_at = datetime.now(UTC)
                self._repo.update(job)

        except Exception as e:
            logger.error(f"Avatar try-on job {job_id} failed: {e}", exc_info=True)
            job = self._repo.get(job_id)
            if job:
                from datetime import datetime, UTC
                job.status = JobStatus.FAILED
                job.error = JobError(code="AVATAR_TRYON_ERROR", message=str(e))
                job.updated_at = datetime.now(UTC)
                self._repo.update(job)
        finally:
            _avatar_progress.pop(job_id, None)
