from functools import lru_cache
from typing import Annotated

from fastapi import Depends

import app.config as config
from app.config import Settings
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


SettingsDep = Annotated[Settings, Depends(get_settings_dep)]
StorageServiceDep = Annotated[StorageService, Depends(get_storage_service)]
UploadServiceDep = Annotated[UploadService, Depends(get_upload_service)]
JobServiceDep = Annotated[JobService, Depends(get_job_service)]
JobRepositoryDep = Annotated[JobRepository, Depends(get_job_repository)]
JobRunnerDep = Annotated[JobRunner, Depends(get_job_runner)]
