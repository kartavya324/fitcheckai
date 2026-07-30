"""
Subscriptions via Stripe (international) and Razorpay (India), behind one
service. Both do the same job: start a hosted checkout for the "Pro" plan and
process webhooks that flip our local SubscriptionModel to active/canceled.

Keys live in Settings and are only touched when that provider is used, so you
can enable just one to start. Nothing here charges anyone without your real
keys + a webhook pointed at this API.
"""
from __future__ import annotations

import hashlib
import hmac
import uuid
from datetime import datetime, UTC

from app.config import Settings
from app.core.exceptions import AppError
from app.core.logging import get_logger
from app.db import SessionLocal, SubscriptionModel, UserModel

logger = get_logger(__name__)

PLAN_PRO = "pro"


def _now() -> datetime:
    return datetime.now(UTC)


class BillingService:
    def __init__(self, settings: Settings) -> None:
        self._s = settings

    # ── Checkout ────────────────────────────────────────────
    def create_checkout(self, *, user: UserModel, provider: str) -> str:
        """Return a hosted checkout URL for the Pro plan."""
        provider = (provider or self._s.default_payment_provider).lower()
        if provider == "stripe":
            return self._stripe_checkout(user)
        if provider == "razorpay":
            return self._razorpay_checkout(user)
        raise AppError(f"Unknown payment provider: {provider}", code="VALIDATION_ERROR", status_code=400)

    def _stripe_checkout(self, user: UserModel) -> str:
        if not (self._s.stripe_secret_key and self._s.stripe_price_id):
            raise AppError("Stripe is not configured", code="CONFIG_ERROR", status_code=500)
        import stripe
        stripe.api_key = self._s.stripe_secret_key
        session = stripe.checkout.Session.create(
            mode="subscription",
            line_items=[{"price": self._s.stripe_price_id, "quantity": 1}],
            customer_email=user.email,
            client_reference_id=user.id,  # ties the webhook back to our user
            success_url=self._s.billing_success_url,
            cancel_url=self._s.billing_cancel_url,
            metadata={"user_id": user.id},
        )
        return session.url

    def _razorpay_checkout(self, user: UserModel) -> str:
        if not (self._s.razorpay_key_id and self._s.razorpay_key_secret and self._s.razorpay_plan_id):
            raise AppError("Razorpay is not configured", code="CONFIG_ERROR", status_code=500)
        import razorpay
        client = razorpay.Client(auth=(self._s.razorpay_key_id, self._s.razorpay_key_secret))
        sub = client.subscription.create({
            "plan_id": self._s.razorpay_plan_id,
            "total_count": 12,  # bill for up to 12 cycles
            "customer_notify": 1,
            "notes": {"user_id": user.id, "email": user.email},
        })
        # Record a pending row now; the webhook activates it.
        self._upsert(
            user_id=user.id, provider="razorpay",
            provider_subscription_id=sub["id"], status="incomplete",
        )
        return sub.get("short_url") or ""

    # ── Webhooks ────────────────────────────────────────────
    def handle_stripe_webhook(self, payload: bytes, sig_header: str | None) -> None:
        if not self._s.stripe_webhook_secret:
            raise AppError("Stripe webhook secret not set", code="CONFIG_ERROR", status_code=500)
        import stripe
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, self._s.stripe_webhook_secret
            )
        except Exception as e:  # invalid signature / payload
            raise AppError(f"Invalid Stripe webhook: {e}", code="INVALID_WEBHOOK", status_code=400) from e

        etype = event["type"]
        obj = event["data"]["object"]
        if etype == "checkout.session.completed":
            user_id = obj.get("client_reference_id") or (obj.get("metadata") or {}).get("user_id")
            if user_id:
                self._upsert(
                    user_id=user_id, provider="stripe",
                    provider_customer_id=obj.get("customer"),
                    provider_subscription_id=obj.get("subscription"),
                    status="active",
                )
        elif etype in ("customer.subscription.updated", "customer.subscription.deleted"):
            self._update_by_provider_sub(
                obj.get("id"),
                status="canceled" if etype.endswith("deleted") else obj.get("status", "active"),
                current_period_end=_ts(obj.get("current_period_end")),
            )

    def handle_razorpay_webhook(self, payload: bytes, sig_header: str | None) -> None:
        secret = self._s.razorpay_webhook_secret
        if not secret:
            raise AppError("Razorpay webhook secret not set", code="CONFIG_ERROR", status_code=500)
        expected = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
        if not sig_header or not hmac.compare_digest(expected, sig_header):
            raise AppError("Invalid Razorpay webhook signature", code="INVALID_WEBHOOK", status_code=400)

        import json
        event = json.loads(payload)
        etype = event.get("event", "")
        sub = (event.get("payload", {}).get("subscription", {}) or {}).get("entity", {})
        sub_id = sub.get("id")
        if not sub_id:
            return
        if etype in ("subscription.activated", "subscription.charged", "subscription.resumed"):
            self._update_by_provider_sub(sub_id, status="active", current_period_end=_ts(sub.get("current_end")))
        elif etype in ("subscription.cancelled", "subscription.completed", "subscription.halted"):
            self._update_by_provider_sub(sub_id, status="canceled")

    # ── Query ───────────────────────────────────────────────
    def get_active(self, user_id: str) -> dict | None:
        with SessionLocal() as db:
            row = (
                db.query(SubscriptionModel)
                .filter(SubscriptionModel.user_id == user_id, SubscriptionModel.status == "active")
                .order_by(SubscriptionModel.updated_at.desc())
                .first()
            )
            if not row:
                return None
            return {
                "plan": row.plan,
                "status": row.status,
                "provider": row.provider,
                "current_period_end": row.current_period_end.isoformat() if row.current_period_end else None,
            }

    # ── Internal persistence ────────────────────────────────
    def _upsert(self, *, user_id, provider, status, provider_customer_id=None, provider_subscription_id=None):
        with SessionLocal() as db:
            row = None
            if provider_subscription_id:
                row = db.query(SubscriptionModel).filter(
                    SubscriptionModel.provider_subscription_id == provider_subscription_id
                ).first()
            if row is None:
                row = SubscriptionModel(id=str(uuid.uuid4()), user_id=user_id, provider=provider, created_at=_now())
                db.add(row)
            row.user_id = user_id
            row.provider = provider
            row.plan = PLAN_PRO
            row.status = status
            if provider_customer_id:
                row.provider_customer_id = provider_customer_id
            if provider_subscription_id:
                row.provider_subscription_id = provider_subscription_id
            row.updated_at = _now()
            db.commit()

    def _update_by_provider_sub(self, provider_subscription_id, *, status, current_period_end=None):
        if not provider_subscription_id:
            return
        with SessionLocal() as db:
            row = db.query(SubscriptionModel).filter(
                SubscriptionModel.provider_subscription_id == provider_subscription_id
            ).first()
            if row is None:
                return
            row.status = status
            if current_period_end:
                row.current_period_end = current_period_end
            row.updated_at = _now()
            db.commit()


def _ts(epoch) -> datetime | None:
    if not epoch:
        return None
    try:
        return datetime.fromtimestamp(int(epoch), UTC)
    except (ValueError, TypeError):
        return None
