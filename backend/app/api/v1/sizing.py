"""Size & Fit advisor endpoint."""
from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.services import sizing_service

router = APIRouter(prefix="/sizing", tags=["sizing"])


class SizingRequest(BaseModel):
    height_cm: float = Field(..., ge=120, le=230)
    weight_kg: float = Field(..., ge=30, le=250)
    sex: Literal["male", "female"]
    fit_preference: Literal["fitted", "regular", "relaxed"] = "regular"
    brand: str | None = None
    categories: list[Literal["tops", "bottoms"]] | None = None


@router.post("/recommend")
def recommend_size(body: SizingRequest) -> dict:
    """Recommend a size per category from body inputs, brand, and fit preference."""
    return sizing_service.recommend(
        height_cm=body.height_cm,
        weight_kg=body.weight_kg,
        sex=body.sex,
        fit_preference=body.fit_preference,
        brand=body.brand,
        categories=body.categories,
    )


@router.get("/brands")
def list_brands() -> dict:
    """Brands with known fit adjustments (for the UI dropdown)."""
    return {"brands": sorted(sizing_service.BRAND_OFFSETS.keys())}
