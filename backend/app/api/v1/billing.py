from fastapi import APIRouter, Request, Header
from pydantic import BaseModel

from app.config import get_settings
from app.services.billing_service import BillingService
from app.api.deps import CurrentUserDep

router = APIRouter(prefix="/billing", tags=["billing"])


def _service() -> BillingService:
    return BillingService(get_settings())


class CheckoutRequest(BaseModel):
    # "stripe" (international) or "razorpay" (India); defaults per config
    provider: str | None = None


@router.post("/checkout")
def create_checkout(body: CheckoutRequest, current_user: CurrentUserDep) -> dict:
    """Start a Pro-plan checkout. Returns a hosted URL to redirect the user to."""
    url = _service().create_checkout(user=current_user, provider=body.provider or "")
    return {"checkout_url": url}


@router.get("/subscription")
def my_subscription(current_user: CurrentUserDep) -> dict:
    """The caller's current plan. `pro` when an active subscription exists."""
    active = _service().get_active(current_user.id)
    return {"plan": active["plan"] if active else "free", "subscription": active}


# ── Webhooks (called by the providers, not the browser; no auth) ──

@router.post("/webhook/stripe")
async def stripe_webhook(request: Request, stripe_signature: str = Header(None)) -> dict:
    payload = await request.body()
    _service().handle_stripe_webhook(payload, stripe_signature)
    return {"received": True}


@router.post("/webhook/razorpay")
async def razorpay_webhook(
    request: Request, x_razorpay_signature: str = Header(None)
) -> dict:
    payload = await request.body()
    _service().handle_razorpay_webhook(payload, x_razorpay_signature)
    return {"received": True}
