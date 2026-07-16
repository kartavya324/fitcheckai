"""Wardrobe / Outfit builder endpoints."""
from typing import Literal

from fastapi import APIRouter, File, Form, UploadFile
from pydantic import BaseModel, Field

from app.config import get_settings
from app.core.exceptions import AppError
from app.services.wardrobe_service import WardrobeService

router = APIRouter(prefix="/wardrobe", tags=["wardrobe"])

ALLOWED = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}


def _service() -> WardrobeService:
    return WardrobeService(get_settings())


@router.post("/items", status_code=201)
async def add_item(
    image: UploadFile = File(...),
    category: Literal["tops", "bottoms", "footwear", "outerwear", "accessory"] = Form(...),
    name: str | None = Form(None),
    color: str | None = Form(None),
    brand: str | None = Form(None),
) -> dict:
    ext = ALLOWED.get(image.content_type or "")
    if not ext:
        raise AppError("Image must be JPEG, PNG, or WebP", code="VALIDATION_ERROR", status_code=400)
    data = await image.read()
    settings = get_settings()
    if len(data) > settings.max_upload_bytes:
        raise AppError("Image too large", code="PAYLOAD_TOO_LARGE", status_code=413)
    return _service().add_item(
        image_bytes=data, extension=ext, category=category, name=name, color=color, brand=brand
    )


@router.get("/items")
def list_items(category: str | None = None) -> dict:
    return {"items": _service().list_items(category)}


@router.delete("/items/{item_id}", status_code=204)
def delete_item(item_id: str) -> None:
    _service().delete_item(item_id)


class CreateOutfitRequest(BaseModel):
    name: str | None = Field(default=None, max_length=120)
    item_ids: list[str] = Field(..., min_length=1, max_length=12)


@router.post("/outfits", status_code=201)
def create_outfit(body: CreateOutfitRequest) -> dict:
    return _service().create_outfit(name=body.name, item_ids=body.item_ids)


@router.get("/outfits")
def list_outfits() -> dict:
    return {"outfits": _service().list_outfits()}


@router.delete("/outfits/{outfit_id}", status_code=204)
def delete_outfit(outfit_id: str) -> None:
    _service().delete_outfit(outfit_id)
