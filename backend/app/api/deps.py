from functools import lru_cache
from typing import Annotated

from fastapi import Depends, HTTPException, Header
from sqlalchemy.orm import Session

import app.config as config
from app.config import Settings
from app.core.security import decode_access_token
from app.db import get_db, UserModel
from app.repositories.job_repository import JobRepository
from app.services.generation_service import GenerationService
from app.services.job_service import JobService
from app.services.storage_service import StorageService
from app.services.upload_service import UploadService
from app.workers.job_runner import JobRunner


@lru_cache
def get_storage_service() -> StorageService:
    return StorageService(config.get_settings())


@lru_cache
def get_job_repository() -> JobRepository:
    return JobRepository(config.get_settings())


@lru_cache
def get_upload_service() -> UploadService:
    return UploadService(get_storage_service(), config.get_settings())


@lru_cache
def get_generation_service() -> GenerationService:
    return GenerationService(config.get_settings(), get_storage_service())


@lru_cache
def get_job_service() -> JobService:
    return JobService(
        get_job_repository(),
        get_upload_service(),
        get_generation_service(),
    )


@lru_cache
def get_job_runner() -> JobRunner:
    return JobRunner(get_job_service())


def get_settings_dep() -> Settings:
    return config.get_settings()


def _extract_bearer(authorization: str | None) -> str | None:
    if not authorization:
        return None
    parts = authorization.split(" ", 1)
    if len(parts) == 2 and parts[0].lower() == "bearer":
        return parts[1].strip()
    return None


def get_current_user(
    authorization: Annotated[str | None, Header()] = None,
    db: Session = Depends(get_db),
) -> UserModel:
    """Require a valid Bearer token; 401 otherwise."""
    token = _extract_bearer(authorization)
    payload = decode_access_token(token) if token else None
    if not payload or not payload.get("sub"):
        raise HTTPException(401, "Not authenticated")
    user = db.query(UserModel).filter(UserModel.id == payload["sub"]).first()
    if not user:
        raise HTTPException(401, "User no longer exists")
    return user


def get_current_user_optional(
    authorization: Annotated[str | None, Header()] = None,
    db: Session = Depends(get_db),
) -> UserModel | None:
    """Return the user if a valid token is present, else None (no error).
    Used during the accounts migration for endpoints that still allow
    anonymous access."""
    token = _extract_bearer(authorization)
    payload = decode_access_token(token) if token else None
    if not payload or not payload.get("sub"):
        return None
    return db.query(UserModel).filter(UserModel.id == payload["sub"]).first()


SettingsDep = Annotated[Settings, Depends(get_settings_dep)]
CurrentUserDep = Annotated[UserModel, Depends(get_current_user)]
OptionalUserDep = Annotated[UserModel | None, Depends(get_current_user_optional)]
StorageServiceDep = Annotated[StorageService, Depends(get_storage_service)]
UploadServiceDep = Annotated[UploadService, Depends(get_upload_service)]
JobServiceDep = Annotated[JobService, Depends(get_job_service)]
JobRepositoryDep = Annotated[JobRepository, Depends(get_job_repository)]
JobRunnerDep = Annotated[JobRunner, Depends(get_job_runner)]
