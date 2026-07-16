"""AI Stylist chat endpoint — Claude-powered product finder."""
from fastapi import APIRouter
from pydantic import BaseModel, Field
from typing import Literal

from app.config import get_settings
from app.services.stylist_service import StylistService

router = APIRouter(prefix="/stylist", tags=["stylist"])


class StylistMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class StylistChatRequest(BaseModel):
    messages: list[StylistMessage] = Field(..., min_length=1, max_length=40)


class StylistProduct(BaseModel):
    title: str | None = None
    price: float | None = None
    price_str: str | None = None
    source: str | None = None
    link: str | None = None
    thumbnail: str | None = None


class StylistChatResponse(BaseModel):
    reply: str
    products: list[StylistProduct] = []


@router.post("/chat", response_model=StylistChatResponse)
def stylist_chat(body: StylistChatRequest) -> StylistChatResponse:
    """
    Send the conversation so far; get the stylist's reply plus any real products
    it found. Stateless — the client sends the full message history each turn.
    """
    settings = get_settings()
    service = StylistService(settings)
    result = service.chat([m.model_dump() for m in body.messages])
    return StylistChatResponse(
        reply=result["reply"],
        products=[StylistProduct(**p) for p in result["products"]],
    )
