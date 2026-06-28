from fastapi import APIRouter, BackgroundTasks, Query, status

from app.api.deps import JobRunnerDep, JobServiceDep
from app.core.exceptions import NotImplementedServiceError
from app.schemas.job import (
    JobCreateRequest,
    JobCreatedResponse,
    JobListResponse,
    JobResultResponse,
    JobStatusResponse,
    job_to_created_response,
    job_to_status_response,
    JobListItem
)

from app.api.deps import JobRunnerDep, JobServiceDep, StorageServiceDep

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.post(
    "",
    response_model=JobCreatedResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_job(
    body: JobCreateRequest,
    background_tasks: BackgroundTasks,
    service: JobServiceDep,
    runner: JobRunnerDep,
) -> JobCreatedResponse:
    job = service.create_job(
        person_upload_id=body.person_upload_id,
        garment_upload_id=body.garment_upload_id,
        garment_category=body.garment_category,
        metadata=body.metadata,
    )
    background_tasks.add_task(runner.run, job.job_id)
    return job_to_created_response(job)


@router.get(
    "",
    response_model=JobListResponse,
)
async def list_jobs(
    service: JobServiceDep,
    storage: StorageServiceDep,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> JobListResponse:
    jobs, total = service.list_jobs(limit=limit, offset=offset)
    items = []
    for job in jobs:
        result_url = None
        if job.status == "completed" and job.job_id:
            result_url = storage.build_result_url(job.job_id)
        
        items.append(
            JobListItem(
                job_id=job.job_id,
                status=job.status,
                garment_category=job.garment_category,
                result_url=result_url,
                created_at=job.created_at,
                completed_at=job.completed_at,
            )
        )
    return JobListResponse(items=items, total=total, limit=limit, offset=offset)


@router.get(
    "/{job_id}",
    response_model=JobStatusResponse,
)
async def get_job(
    job_id: str,
    service: JobServiceDep,
    storage: StorageServiceDep,
) -> JobStatusResponse:
    job = service.get_job(job_id)
    resp = job_to_status_response(job)
    if job.status == "completed":
        resp.result_url = storage.build_result_url(job.job_id)
    return resp


@router.get(
    "/{job_id}/result",
    response_model=JobResultResponse,
)
async def get_job_result(
    job_id: str,
    _service: JobServiceDep,
) -> JobResultResponse:
    del job_id
    raise NotImplementedServiceError("Get job result not implemented yet")
