from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse

from app.api.deps import JobRepositoryDep, StorageServiceDep, get_settings_dep
from app.config import Settings
from app.schemas.common import ErrorResponse

router = APIRouter(tags=["health"])


@router.get("/health")
def health(settings: Settings = Depends(get_settings_dep)) -> dict[str, str]:
    return {
        "status": "ok",
        "service": settings.app_name,
        "version": settings.app_version,
    }


@router.get(
    "/ready",
    responses={503: {"model": ErrorResponse}},
)
def ready(
    storage: StorageServiceDep,
    job_repo: JobRepositoryDep,
) -> JSONResponse:
    checks = {
        "storage": "ok" if storage.is_writable() else "fail",
        "job_store": "ok" if job_repo.is_reachable() else "fail",
    }
    body = {"status": "ready", "checks": checks}
    if all(value == "ok" for value in checks.values()):
        return JSONResponse(content=body, status_code=status.HTTP_200_OK)
    return JSONResponse(
        content={**body, "status": "not_ready"},
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
    )
