from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.v1.router import api_router
from app.config import Settings, get_settings
from app.core.exceptions import AppError
import asyncio
import httpx
from app.core.logging import get_logger, setup_logging
from app.schemas.common import ErrorBody, ErrorResponse
from app.db import Base, engine

logger = get_logger(__name__)

async def _keepalive_hf_space() -> None:
    import asyncio
    import httpx
    import logging
    logger = logging.getLogger(__name__)
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
    Base.metadata.create_all(bind=engine)
    
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


def create_app(settings: Settings | None = None) -> FastAPI:
    cfg = settings or get_settings()

    app = FastAPI(
        title="FitCheck AI API",
        description="Virtual try-on uploads and generation jobs",
        version=cfg.app_version,
        lifespan=lifespan,
    )
    app.state.settings = cfg

    app.add_middleware(
        CORSMiddleware,
        allow_origins=cfg.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

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
