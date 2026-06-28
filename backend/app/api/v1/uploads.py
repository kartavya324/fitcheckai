from fastapi import APIRouter, File, Request, UploadFile, status

from app.api.deps import StorageServiceDep, UploadServiceDep
from app.core.exceptions import NotFoundError, ValidationError
from app.models.job import UploadRecord
from app.schemas.upload import (
    UploadCreatedResponse,
    UploadResponse,
    record_to_created_response,
    record_to_response,
)
from app.services.storage_service import StorageService

router = APIRouter(prefix="/uploads", tags=["uploads"])


def _request_base_url(request: Request) -> str:
    return str(request.base_url).rstrip("/")


async def _read_upload_file(file: UploadFile) -> tuple[str, str, bytes]:
    if file.filename is None or not file.filename.strip():
        raise ValidationError(
            "Filename is required",
            details={"field": "file"},
        )

    content_type = file.content_type
    if not content_type:
        raise ValidationError(
            "Content-Type is required",
            details={"field": "content_type"},
        )

    data = await file.read()
    return file.filename, content_type, data


def _extension_for_record(record: UploadRecord) -> str:
    return record.relative_path.rsplit(".", 1)[-1]


def _created_response(
    record: UploadRecord,
    storage: StorageService,
    *,
    base_url: str,
) -> UploadCreatedResponse:
    extension = _extension_for_record(record)
    url = storage.build_upload_url(
        record.upload_id,
        record.kind,
        extension,
        base_url=base_url,
    )
    return record_to_created_response(record, url=url)


@router.post(
    "/person",
    response_model=UploadCreatedResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_person(
    request: Request,
    service: UploadServiceDep,
    storage: StorageServiceDep,
    file: UploadFile = File(...),
) -> UploadCreatedResponse:
    filename, content_type, data = await _read_upload_file(file)
    record = await service.save_person_upload(
        filename=filename,
        content_type=content_type,
        data=data,
    )
    return _created_response(record, storage, base_url=_request_base_url(request))


@router.post(
    "/garment",
    response_model=UploadCreatedResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_garment(
    request: Request,
    service: UploadServiceDep,
    storage: StorageServiceDep,
    file: UploadFile = File(...),
) -> UploadCreatedResponse:
    filename, content_type, data = await _read_upload_file(file)
    record = await service.save_garment_upload(
        filename=filename,
        content_type=content_type,
        data=data,
    )
    return _created_response(record, storage, base_url=_request_base_url(request))


@router.get(
    "/{upload_id}",
    response_model=UploadResponse,
)
async def get_upload(
    request: Request,
    upload_id: str,
    service: UploadServiceDep,
    storage: StorageServiceDep,
) -> UploadResponse:
    record = service.get_upload(upload_id)
    if record is None:
        raise NotFoundError(
            f"Upload not found: {upload_id}",
            details={"upload_id": upload_id},
        )
    extension = _extension_for_record(record)
    url = storage.build_upload_url(
        record.upload_id,
        record.kind,
        extension,
        base_url=_request_base_url(request),
    )
    return record_to_response(record, url=url)
