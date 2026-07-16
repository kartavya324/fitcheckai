"""Personal color analysis endpoint."""
from fastapi import APIRouter, File, UploadFile

from app.config import get_settings
from app.core.exceptions import AppError
from app.services.color_service import analyze_colors

router = APIRouter(prefix="/color", tags=["color"])

ALLOWED = {"image/jpeg", "image/png", "image/webp"}


@router.post("/analyze")
async def analyze(image: UploadFile = File(...)) -> dict:
    """Analyse a face photo → color season, undertone, and a flattering palette."""
    if image.content_type not in ALLOWED:
        raise AppError("Image must be JPEG, PNG, or WebP", code="VALIDATION_ERROR", status_code=400)
    data = await image.read()
    settings = get_settings()
    if len(data) > settings.max_upload_bytes:
        raise AppError("Image too large", code="PAYLOAD_TOO_LARGE", status_code=413)
    return analyze_colors(data)
