# FitCheck AI — Deployment & Go-Live Guide

This is your **do-it-yourself checklist** to take the app from "runs on my
laptop" to "live SaaS". Everything in code is done; the steps below are the
accounts, keys, and commands only you can run. Work top to bottom.

> Architecture in one line: **Frontend** (static/SSR) → **API** (FastAPI) →
> **Postgres** + **object storage** (S3/R2), with the **GPU avatar pipeline**
> running separately (RunPod cloud, or a local GPU box).

---

## 0. What each piece needs to run in prod
| Piece | Runs on | Needs |
|---|---|---|
| Frontend | Vercel / Netlify / Node host | `VITE_API_BASE_URL` → your API URL |
| API | Railway / Fly / Render / VPS (Docker) | Postgres, storage, secrets below |
| Database | Managed Postgres (Neon/Supabase/RDS) | `DATABASE_URL` |
| File storage | S3 or Cloudflare R2 | `S3_*` vars |
| GPU avatars | RunPod serverless | `RUNPOD_*` (see `backend/runpod/README.md`) |

---

## 1. Security setup (Phase 5) — required before any public deploy

Everything here is already enforced in code; you just supply the values.

1. **Set `ENVIRONMENT=production`.** This turns on the safety net: the API
   **refuses to boot** if the JWT secret is still the dev default or if CORS is
   `*`. (It also enables the HSTS header.)
2. **Generate a real `JWT_SECRET`:**
   ```bash
   python -c "import secrets; print(secrets.token_urlsafe(48))"
   ```
   Put it in your host's env vars (never in git).
3. **Lock `CORS_ORIGINS`** to only your real frontend origin(s), e.g.
   `CORS_ORIGINS=https://app.fitcheck.ai`. No `*`.
4. **Rate limits** are already active (login/signup 10/min, GPU + scraping
   endpoints 20/hr, 300/min global). If you deploy behind a proxy/load
   balancer, start the server so it trusts forwarded IPs, otherwise every user
   looks like the proxy:
   - gunicorn/uvicorn: set `--forwarded-allow-ips="*"` (or your proxy's IP).
5. **Security headers** (`X-Frame-Options`, `nosniff`, Referrer-Policy,
   Permissions-Policy, HSTS in prod) are added to every response automatically.

✅ Done when: `ENVIRONMENT=production` + real `JWT_SECRET` + locked CORS are set
in your host, and the API boots without the "Refusing to start" error.

---

## 2. Database (Phase 2)

1. Create a managed Postgres (Neon / Supabase / RDS). Copy its connection
   string and set:
   ```
   DATABASE_URL=postgresql+psycopg://USER:PASS@HOST:5432/DBNAME
   ```
2. Apply the schema (the Docker entrypoint does this automatically on boot; to
   run it manually):
   ```bash
   cd backend && alembic upgrade head
   ```
3. Future schema changes: edit models, then
   `alembic revision --autogenerate -m "describe change"` → commit the file →
   it auto-applies on next deploy.

✅ Done when: `alembic upgrade head` succeeds against your Postgres and the API
starts.

---

## 3. Object storage (Phase 2)

Local disk works for dev; for prod use a bucket so files survive redeploys and
scale.

1. Create an S3 bucket **or** a Cloudflare R2 bucket (R2 has no egress fees).
2. Set:
   ```
   STORAGE_BACKEND=s3
   S3_BUCKET=your-bucket
   S3_REGION=us-east-1            # R2: leave region blank
   S3_ENDPOINT_URL=               # R2/MinIO only, e.g. https://<acct>.r2.cloudflarestorage.com
   S3_PUBLIC_BASE_URL=https://cdn.yourdomain.com   # public/CDN base for object URLs
   S3_ACCESS_KEY_ID=...
   S3_SECRET_ACCESS_KEY=...
   ```
3. **Last-mile TODO before flipping to s3** (documented, not yet wired): a few
   write sites still go to local disk — the 2D try-on uploads/results, the
   person-photo writes in `avatar.py`, and the generation pipeline reads inputs
   from disk. Route those through `storage_backend` (avatar GLBs + wardrobe
   already are) before relying on S3 for the full flow. Ask Claude to
   "finish the S3 last-mile" — it's scoped in the code comments.

✅ Done when: avatar GLBs + wardrobe images appear in your bucket and load in
the app.

---

## 4. GPU avatar pipeline (RunPod)

The 3D avatar can't run on a typical web host (no GPU). Two options:
- **RunPod serverless** (recommended): follow `backend/runpod/README.md` to
  build/push the image and create the endpoint, then set `AVATAR_MODE=runpod`,
  `RUNPOD_API_KEY`, `RUNPOD_ENDPOINT_ID`.
- **Local/own GPU box**: run `pifuhd_server.py` on a machine with an NVIDIA GPU
  and point `AVATAR_MODE=local_pifuhd` + `LOCAL_INFERENCE_URL` at it.

✅ Done when: a real photo → 3D avatar completes through your chosen backend.

---

## 5. Run the whole stack locally in prod config (Phase 6)

Validate everything before deploying, using the same config prod uses:

```bash
# 1. Put a strong JWT_SECRET (and any S3/RunPod keys) in a root .env file
echo "JWT_SECRET=$(python -c 'import secrets;print(secrets.token_urlsafe(48))')" > .env
# 2. Bring up Postgres + API (migrations run on boot) + frontend
docker compose up --build
```
- API → http://localhost:8001  ·  Frontend → http://localhost:3000
- This uses `postgresql+psycopg`, runs `alembic upgrade head`, and serves under
  gunicorn (no `--reload`) — a faithful prod rehearsal.
- The GPU pipeline isn't in compose; set `AVATAR_MODE=runpod` (+ keys) to
  exercise avatars, or leave it and test the rest of the app.

---

## 6. Deploy for real (Phase 6)

**Backend** (Docker) — Railway / Fly.io / Render / any Docker host:
1. Point it at `backend/Dockerfile`.
2. Set env vars from §1–4 (`ENVIRONMENT=production`, `JWT_SECRET`,
   `DATABASE_URL`, `CORS_ORIGINS`, `STORAGE_BACKEND=s3` + `S3_*`, `AVATAR_MODE`
   + `RUNPOD_*`, and `ANTHROPIC_API_KEY`/`SERPAPI_KEY` for the Stylist).
3. Deploy. The entrypoint runs migrations then starts gunicorn. Health check:
   `GET /api/v1/health`.

**Frontend** — Vercel/Netlify (easiest) or the provided `frontend/Dockerfile`:
1. Build env: `VITE_API_BASE_URL=https://your-api-domain`.
2. Deploy. Point your domain at it.

**CI** — `.github/workflows/ci.yml` runs on every push/PR: backend syntax +
migration check, frontend typecheck + build. Green CI = safe to deploy.

---

## 7. Enforce login (optional flip)

Auth + per-user data isolation are built and non-breaking (anonymous still
works). When you want to REQUIRE login, ask Claude to "flip OptionalUserDep →
CurrentUserDep on the owned endpoints" — a small, mechanical change.

---

## 8. Still-open items (ask Claude when ready)
- **Payments** — Stripe + Razorpay, being built on the `feature/payments`
  branch; merge when funded.
- **S3 last-mile** wiring (§3).
- **Error tracking** — add Sentry (free tier): `pip install sentry-sdk`, init in
  `main.py` with `SENTRY_DSN`.
- **2D try-on reliability** — the free IDM-VTON Space is flaky; swap for a paid
  or self-hosted endpoint behind the existing provider seam.
- **Amazon product-fetch** bot-wall (Myntra already works).
- **Legal** — privacy policy + ToS (you handle face/body photos = sensitive
  data; get a real review).

---

## Quick reference: production env vars
```
ENVIRONMENT=production
JWT_SECRET=<48+ random chars>
DATABASE_URL=postgresql+psycopg://user:pass@host:5432/fitcheck
CORS_ORIGINS=https://app.yourdomain.com
PUBLIC_BASE_URL=https://api.yourdomain.com
STORAGE_BACKEND=s3
S3_BUCKET=... S3_REGION=... S3_ACCESS_KEY_ID=... S3_SECRET_ACCESS_KEY=... S3_PUBLIC_BASE_URL=...
AVATAR_MODE=runpod
RUNPOD_API_KEY=... RUNPOD_ENDPOINT_ID=...
ANTHROPIC_API_KEY=...   # AI Stylist
SERPAPI_KEY=...         # AI Stylist product search
```
