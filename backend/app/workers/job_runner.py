from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from app.core.exceptions import AppError
import app.config as config
from app.core.logging import get_logger

if TYPE_CHECKING:
    from app.services.job_service import JobService

logger = get_logger(__name__)

PROGRESS_STEPS: list[tuple[int, str]] = [
    (25, "Analyzing photo"),
    (50, "Matching garment"),
    (75, "Rendering try-on"),
]


class JobRunner:
    """Background execution of queued generation jobs."""

    def __init__(self, job_service: JobService) -> None:
        self._jobs = job_service

    async def enqueue(self, job_id: str) -> None:
        """Schedule a job for background processing."""
        asyncio.create_task(self.run(job_id))

    async def run(self, job_id: str) -> None:
        """Run generation job (stub/simulation or real)."""
        settings = config.get_settings()
        
        try:
            self._jobs.mark_processing(job_id)
            
            if settings.generation_stub:
                simulation_seconds = settings.job_simulation_seconds
                step_delay = simulation_seconds / 4
                for progress, stage in PROGRESS_STEPS:
                    await asyncio.sleep(step_delay)
                    self._jobs.update_progress(job_id, progress=progress, stage=stage)
                await asyncio.sleep(step_delay)
                
                import httpx
                if settings.generation_mode == "econ_3d":
                    try:
                        resp = httpx.get("https://threejs.org/examples/models/gltf/Soldier.glb", follow_redirects=True, timeout=10.0)
                        data = resp.content
                    except Exception:
                        data = b""
                    self._jobs._generation._storage.write_result(job_id=job_id, extension="glb", data=data)
                    result_path = f"results/{job_id}.glb"
                else:
                    try:
                        resp = httpx.get("https://picsum.photos/400/600", follow_redirects=True, timeout=10.0)
                        data = resp.content
                    except Exception:
                        data = b""
                    self._jobs._generation._storage.write_result(job_id=job_id, extension="jpg", data=data)
                    result_path = f"results/{job_id}.jpg"

                self._jobs.mark_completed(job_id, result_path=result_path)
                logger.info("Job %s completed (simulated)", job_id)
            else:
                job = self._jobs.get_job(job_id)
                person_abs_path = str(settings.storage_root / str(job.person_path))
                garment_abs_path = str(settings.storage_root / str(job.garment_path))
                
                def on_progress(prog: int, stage: str | None) -> None:
                    self._jobs.update_progress(job_id, progress=prog, stage=stage)

                # run in an executor if the service is synchronous, or if it is sync just call it (which might block the event loop, but for now we call it directly or run_in_executor)
                # Since we are using replicate which is network IO, we should probably run it in an executor.
                result_path = await asyncio.to_thread(
                    self._jobs._generation.generate,
                    job_id=job_id,
                    person_path=person_abs_path,
                    garment_path=garment_abs_path,
                    garment_category=job.garment_category,
                    on_progress=on_progress,
                )
                
                self._jobs.mark_completed(job_id, result_path=result_path)
                logger.info("Job %s completed successfully", job_id)

        except AppError as e:
            logger.exception("Job %s failed with domain exception", job_id)
            try:
                self._jobs.mark_failed(job_id, code=e.code, message=e.message)
            except Exception:
                logger.exception("Could not mark job %s as failed", job_id)
        except Exception as e:
            logger.exception("Job %s failed with unexpected error", job_id)
            try:
                self._jobs.mark_failed(
                    job_id,
                    code="GENERATION_FAILED",
                    message=str(e),
                )
            except Exception:
                logger.exception("Could not mark job %s as failed", job_id)
