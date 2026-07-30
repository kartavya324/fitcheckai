# FitCheck AI — Payments (Stripe + Razorpay)

Subscription billing for the **Pro** plan, with **Stripe** (international) and
**Razorpay** (India) behind one API. This lives on the `feature/payments`
branch — merge into `main` when you're ready to charge.

Everything in code is done and verified (endpoints, webhook signature checks,
DB model, migration). The steps below are the accounts + keys only you can set;
both providers have **free test modes**, so you can wire and test the full flow
without real money.

## What's built
| Piece | File |
|---|---|
| Config (both providers) | `backend/app/config.py` (STRIPE_* / RAZORPAY_*) |
| DB model + migration | `subscriptions` table, `alembic/versions/*add_subscriptions*` |
| Billing service | `backend/app/services/billing_service.py` |
| Endpoints | `backend/app/api/v1/billing.py` |

Endpoints (all under `/api/v1/billing`):
- `POST /checkout` (auth) → `{checkout_url}` — redirect the user there.
- `GET /subscription` (auth) → `{plan: "free"|"pro", subscription}`.
- `POST /webhook/stripe` · `POST /webhook/razorpay` — called by the providers;
  both verify signatures before touching the DB.

## Setup — Stripe (test mode)
1. Create a Stripe account → **Test mode**.
2. Products → create a **Pro** product with a **recurring price**; copy the
   price id (`price_...`) → `STRIPE_PRICE_ID`.
3. Developers → API keys → copy the **secret key** (`sk_test_...`) →
   `STRIPE_SECRET_KEY`.
4. Developers → Webhooks → add endpoint
   `https://your-api/api/v1/billing/webhook/stripe`, subscribe to
   `checkout.session.completed`, `customer.subscription.updated`,
   `customer.subscription.deleted`; copy the signing secret (`whsec_...`) →
   `STRIPE_WEBHOOK_SECRET`.
5. Local testing: `stripe listen --forward-to localhost:8001/api/v1/billing/webhook/stripe`.

## Setup — Razorpay (test mode)
1. Create a Razorpay account → **Test mode**.
2. Subscriptions → create a **Plan** (monthly Pro); copy the plan id
   (`plan_...`) → `RAZORPAY_PLAN_ID`.
3. Settings → API Keys → generate → `RAZORPAY_KEY_ID` + `RAZORPAY_KEY_SECRET`.
4. Settings → Webhooks → add `https://your-api/api/v1/billing/webhook/razorpay`,
   subscribe to `subscription.activated`, `subscription.charged`,
   `subscription.cancelled`, `subscription.completed`; set a secret →
   `RAZORPAY_WEBHOOK_SECRET`.

## Env vars
```
DEFAULT_PAYMENT_PROVIDER=stripe        # or razorpay
BILLING_SUCCESS_URL=https://app.yourdomain.com/billing/success
BILLING_CANCEL_URL=https://app.yourdomain.com/billing/cancel
STRIPE_SECRET_KEY=sk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...
STRIPE_PRICE_ID=price_...
RAZORPAY_KEY_ID=rzp_test_...
RAZORPAY_KEY_SECRET=...
RAZORPAY_WEBHOOK_SECRET=...
RAZORPAY_PLAN_ID=plan_...
```

## Flow
1. Frontend calls `POST /billing/checkout {provider}` → gets `checkout_url` →
   redirects the user.
2. User pays on the provider's hosted page → provider fires a webhook →
   we verify the signature and mark the `subscriptions` row **active**.
3. `GET /billing/subscription` now returns `plan: "pro"`.

## Remaining to wire up (when merging)
- **Gate features by plan**: add a dependency that reads
  `BillingService.get_active(user.id)` and enforces free-tier quotas
  (e.g. N avatars/month) — the data is ready, the enforcement is a small add.
- **Frontend**: a pricing page + "Upgrade" button calling `/checkout`, and a
  `/billing/success` route. (Backend is provider-agnostic; the UI just needs
  the two buttons.)
- Run `alembic upgrade head` after merge so the `subscriptions` table is created
  in prod.

## Test-mode cards
- Stripe: `4242 4242 4242 4242`, any future expiry/CVC.
- Razorpay: use their test card list in the checkout modal.
