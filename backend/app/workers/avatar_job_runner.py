import asyncio
import logging

from app.services.avatar_generation_service import AvatarGenerationService
from app.repositories.job_repository import JobRepository
from app.models.job import Job, JobError, JobStatus

logger = logging.getLogger(__name__)

# In-memory progress store keyed by job_id
_avatar_progress: dict[str, dict] = {}


def get_avatar_progress(job_id: str) -> dict:
    return _avatar_progress.get(job_id, {"pct": 0, "stage": "Queued"})


class AvatarJobRunner:

    def __init__(
        self,
        avatar_generation_service: AvatarGenerationService,
        job_repository: JobRepository,
    ) -> None:
        self._gen = avatar_generation_service
        self._repo = job_repository

    async def run(self, *, job_id: str, session_id: str, person_image_path: str) -> None:
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
                on_progress=on_progress,
            )

            # Mark as completed
            job = self._repo.get(job_id)
            if job:
                from datetime import datetime, UTC
                job.status = JobStatus.COMPLETED
                job.progress = 100
                job.result_path = result_path
                job.stage = None
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
