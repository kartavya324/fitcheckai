"""Social Fit-Check feed endpoints (device-based identity; no accounts yet)."""
from typing import Literal

from fastapi import APIRouter, File, Form, UploadFile
from pydantic import BaseModel, Field

from app.config import get_settings
from app.core.exceptions import AppError
from app.services.feed_service import FeedService

router = APIRouter(prefix="/feed", tags=["feed"])

ALLOWED = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}


def _service() -> FeedService:
    return FeedService(get_settings())


@router.post("/posts", status_code=201)
async def create_post(
    image: UploadFile = File(...),
    device_id: str = Form(..., min_length=8, max_length=64),
    display_name: str | None = Form(None),
    caption: str | None = Form(None),
) -> dict:
    ext = ALLOWED.get(image.content_type or "")
    if not ext:
        raise AppError("Image must be JPEG, PNG, or WebP", code="VALIDATION_ERROR", status_code=400)
    data = await image.read()
    settings = get_settings()
    if len(data) > settings.max_upload_bytes:
        raise AppError("Image too large", code="PAYLOAD_TOO_LARGE", status_code=413)
    return _service().create_post(
        device_id=device_id, display_name=display_name, image_bytes=data,
        extension=ext, caption=caption,
    )


@router.get("/posts")
def list_posts(device_id: str, limit: int = 20, offset: int = 0) -> dict:
    return _service().list_feed(device_id=device_id, limit=min(limit, 50), offset=offset)


@router.delete("/posts/{post_id}", status_code=204)
def delete_post(post_id: str, device_id: str) -> None:
    _service().delete_post(post_id=post_id, device_id=device_id)


class VoteRequest(BaseModel):
    device_id: str = Field(..., min_length=8, max_length=64)
    value: Literal["fire", "cold"]


@router.post("/posts/{post_id}/vote")
def vote(post_id: str, body: VoteRequest) -> dict:
    return _service().vote(post_id=post_id, device_id=body.device_id, value=body.value)


class CommentRequest(BaseModel):
    device_id: str = Field(..., min_length=8, max_length=64)
    display_name: str | None = None
    text: str = Field(..., min_length=1, max_length=500)


@router.get("/posts/{post_id}/comments")
def list_comments(post_id: str) -> dict:
    return _service().list_comments(post_id)


@router.post("/posts/{post_id}/comments", status_code=201)
def add_comment(post_id: str, body: CommentRequest) -> dict:
    return _service().add_comment(
        post_id=post_id, device_id=body.device_id,
        display_name=body.display_name, text=body.text,
    )
