"""Footwear try-on endpoint — pose-guided 2D compositing (no GPU)."""
import tempfile
import uuid
from pathlib import Path

from fastapi import APIRouter, File, UploadFile

from app.api.deps import StorageServiceDep
from app.config import get_settings
from app.core.exceptions import AppError
from app.services.footwear_service import composite_footwear

router = APIRouter(prefix="/footwear", tags=["footwear"])

ALLOWED = {"image/jpeg", "image/png", "image/webp"}


@router.post("/try", status_code=201)
async def try_footwear(
    storage: StorageServiceDep,
    person_image: UploadFile = File(...),
    shoe_image: UploadFile = File(...),
):
    """
    Composite a shoe/slipper onto the feet of a person image.

    `person_image` is typically the body try-on RESULT (top+bottom already
    applied), so the final image is the complete outfit. `shoe_image` is the
    footwear product photo (a transparent PNG works best; JPEGs are
    background-removed automatically).
    """
    settings = get_settings()

    for f in (person_image, shoe_image):
        if f.content_type not in ALLOWED:
            raise AppError(
                f"{f.filename}: must be JPEG, PNG, or WebP",
                code="VALIDATION_ERROR",
                status_code=400,
            )

    person_bytes = await person_image.read()
    shoe_bytes = await shoe_image.read()
    if len(person_bytes) > settings.max_upload_bytes or len(shoe_bytes) > settings.max_upload_bytes:
        raise AppError("Image too large", code="PAYLOAD_TOO_LARGE", status_code=413)

    result_id = str(uuid.uuid4())
    with tempfile.TemporaryDirectory() as tmp:
        person_path = Path(tmp) / "person.jpg"
        shoe_path = Path(tmp) / f"shoe{Path(shoe_image.filename or 'shoe.png').suffix or '.png'}"
        person_path.write_bytes(person_bytes)
        shoe_path.write_bytes(shoe_bytes)

        out_path = Path(tmp) / "result.jpg"
        try:
            composite_footwear(str(person_path), str(shoe_path), str(out_path))
        except ValueError as e:
            # e.g. no feet detected — actionable 400, not a 500
            raise AppError(str(e), code="NO_FEET_DETECTED", status_code=400) from e
        except Exception as e:
            raise AppError(
                f"Footwear compositing failed: {e}",
                code="FOOTWEAR_ERROR",
                status_code=500,
            ) from e

        storage.write_result(job_id=result_id, extension="jpg", data=out_path.read_bytes())

    return {
        "result_id": result_id,
        "result_url": storage.build_result_url(result_id),
    }
