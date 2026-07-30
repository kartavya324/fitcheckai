from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.core.rate_limit import limiter

from app.api.v1.router import api_router
from app.config import Settings, get_settings
from app.core.exceptions import AppError
import asyncio
import httpx
from app.core.logging import get_logger, setup_logging
from app.schemas.common import ErrorBody, ErrorResponse
from app.db import Base, engine, ensure_schema

logger = get_logger(__name__)

async def _keepalive_hf_space() -> None:
    while True:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                await client.get("https://yisol-idm-vton.hf.space/")
            logger.debug("HF Space keepalive ping sent")
        except Exception:
            pass
        await asyncio.sleep(240)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings: Settings = app.state.settings
    setup_logging(settings)
    settings.ensure_storage_dirs()
    # Dev (SQLite): auto-create tables + patch columns for zero-setup runs.
    # Prod (Postgres): schema is owned by Alembic — run `alembic upgrade head`
    # as a deploy step; don't create_all so migrations stay the source of truth.
    if engine.dialect.name == "sqlite":
        Base.metadata.create_all(bind=engine)
        ensure_schema()
    else:
        logger.info("Non-SQLite DB detected; skipping create_all (use Alembic migrations)")

    # iPhone HEIC support: teaches Pillow to open .heic/.heif everywhere
    try:
        from pillow_heif import register_heif_opener
        register_heif_opener()
    except ImportError:
        logger.warning("pillow-heif not installed; HEIC uploads will fail")

    # Reliability: fail jobs orphaned by a prior crash/restart so they don't
    # sit at 'processing' forever.
    try:
        from app.repositories.job_repository import JobRepository
        JobRepository(settings).reap_stale()
    except Exception:
        logger.exception("Orphan-job reaping failed (non-fatal)")

    asyncio.create_task(_keepalive_hf_space())
    yield


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def app_error_handler(_request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=ErrorResponse(
                error=ErrorBody(
                    code=exc.code,
                    message=exc.message,
                    details=exc.details,
                )
            ).model_dump(),
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(
        _request: Request,
        exc: StarletteHTTPException,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=ErrorResponse(
                error=ErrorBody(
                    code="HTTP_ERROR",
                    message=str(exc.detail),
                )
            ).model_dump(),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        _request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content=ErrorResponse(
                error=ErrorBody(
                    code="VALIDATION_ERROR",
                    message="Request validation failed",
                    details={"errors": exc.errors()},
                )
            ).model_dump(),
        )


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Baseline hardening headers on every response."""

    def __init__(self, app, *, is_production: bool) -> None:
        super().__init__(app)
        self._prod = is_production

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault(
            "Permissions-Policy", "camera=(), microphone=(), geolocation=()"
        )
        # HSTS only in prod (over HTTPS); sending it on local http is harmless
        # but pointless and can wedge dev browsers onto https.
        if self._prod:
            response.headers.setdefault(
                "Strict-Transport-Security", "max-age=31536000; includeSubDomains"
            )
        return response


def _assert_prod_secrets(cfg: Settings) -> None:
    """Refuse to boot a production deploy that still uses dev secrets."""
    if not cfg.is_production:
        return
    problems = []
    if "change-me" in cfg.jwt_secret or cfg.jwt_secret.startswith("dev-"):
        problems.append("JWT_SECRET is still the insecure dev default")
    if any("*" == o for o in cfg.cors_origins):
        problems.append("CORS is wide open (*)")
    if problems:
        raise RuntimeError(
            "Refusing to start in production: " + "; ".join(problems)
        )


def create_app(settings: Settings | None = None) -> FastAPI:
    cfg = settings or get_settings()
    _assert_prod_secrets(cfg)

    app = FastAPI(
        title="FitCheck AI API",
        description="Virtual try-on uploads and generation jobs",
        version=cfg.app_version,
        lifespan=lifespan,
    )
    app.state.settings = cfg

    # Rate limiting (slowapi)
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.add_middleware(SlowAPIMiddleware)

    app.add_middleware(SecurityHeadersMiddleware, is_production=cfg.is_production)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=cfg.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Compress large responses (GLB avatars via /files shrink ~25-35%)
    app.add_middleware(GZipMiddleware, minimum_size=8192)

    register_exception_handlers(app)

    app.include_router(api_router, prefix="/api/v1")

    cfg.ensure_storage_dirs()
    storage_root = cfg.storage_root.resolve()
    app.mount("/files", StaticFiles(directory=str(storage_root), html=False), name="files")

    @app.get("/", include_in_schema=False)
    def root() -> dict[str, str]:
        return {"service": cfg.app_name, "docs": "/docs"}

    return app


app = create_app()
