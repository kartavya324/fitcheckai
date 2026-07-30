from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Anchor paths to the backend directory (parent of app/) so the server
# behaves the same regardless of the process working directory.
# Loading ".env" relative to cwd silently falls back to defaults
# (e.g. AVATAR_MODE=stub) when launched from the repo root.
BACKEND_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(BACKEND_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    app_name: str = Field(default="fitcheck-api", alias="APP_NAME")
    app_version: str = Field(default="0.1.0", alias="APP_VERSION")
    # "development" | "production" — gates prod-only safety (secret enforcement,
    # HSTS). Set ENVIRONMENT=production on real deploys.
    environment: str = Field(default="development", alias="ENVIRONMENT")
    storage_root: Path = Field(default=Path("./storage"), alias="STORAGE_ROOT")

    # Database. When unset, we derive a local SQLite file under storage_root
    # (dev default). In production set DATABASE_URL to a Postgres DSN, e.g.
    # postgresql+psycopg://user:pass@host:5432/fitcheck
    database_url: str | None = Field(default=None, alias="DATABASE_URL")

    # Object storage. "local" = disk under storage_root served via /files
    # (dev default). "s3" = S3/R2/any S3-compatible bucket (prod). When s3,
    # set the bucket + credentials; s3_endpoint_url is for R2/MinIO, and
    # s3_public_base_url is the public/CDN base for building object URLs.
    storage_backend: str = Field(default="local", alias="STORAGE_BACKEND")
    s3_bucket: str | None = Field(default=None, alias="S3_BUCKET")
    s3_region: str | None = Field(default=None, alias="S3_REGION")
    s3_endpoint_url: str | None = Field(default=None, alias="S3_ENDPOINT_URL")
    s3_public_base_url: str | None = Field(default=None, alias="S3_PUBLIC_BASE_URL")
    s3_access_key_id: str | None = Field(default=None, alias="S3_ACCESS_KEY_ID")
    s3_secret_access_key: str | None = Field(default=None, alias="S3_SECRET_ACCESS_KEY")

    @field_validator("storage_root", mode="after")
    @classmethod
    def anchor_storage_root(cls, value: Path) -> Path:
        # Resolve relative storage paths against the backend dir, not cwd
        if not value.is_absolute():
            return (BACKEND_DIR / value).resolve()
        return value
    public_base_url: str = Field(
        default="http://127.0.0.1:8001",
        alias="PUBLIC_BASE_URL",
    )
    max_upload_bytes: int = Field(default=10_485_760, alias="MAX_UPLOAD_BYTES")
    cors_origins: list[str] = Field(
        default=[
            "http://localhost:5173",
            "http://localhost:3000",
            "http://localhost:8080",
            "http://127.0.0.1:8080",
        ],
        alias="CORS_ORIGINS",
    )
    generation_stub: bool = Field(default=False, alias="GENERATION_STUB")
    job_simulation_seconds: float = Field(default=5.0, alias="JOB_SIMULATION_SECONDS")
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field(
        default="INFO",
        alias="LOG_LEVEL",
    )
    allowed_content_types: list[str] = Field(
        default=[
            "image/jpeg",
            "image/png",
            "image/webp",
            "image/heic",
            "image/heif",
        ],
    )
    replicate_api_token: str | None = Field(default=None, alias="REPLICATE_API_TOKEN")
    hf_token: str | None = Field(default=None, alias="HF_TOKEN")
    generation_mode: Literal["replicate_2d", "econ_3d"] = Field(
        default="replicate_2d",
        alias="GENERATION_MODE",
    )
    avatar_mode: str = Field(default="local_pifuhd", alias="AVATAR_MODE")
    runpod_api_key: str | None = Field(default=None, alias="RUNPOD_API_KEY")
    runpod_endpoint_id: str | None = Field(default=None, alias="RUNPOD_ENDPOINT_ID")
    local_inference_url: str = Field(
        default="http://127.0.0.1:8090",
        alias="LOCAL_INFERENCE_URL",
    )
    # Auth / JWT. In production set JWT_SECRET to a long random string; the
    # dev default is fine locally but MUST be overridden before launch.
    jwt_secret: str = Field(
        default="dev-insecure-change-me-in-production",
        alias="JWT_SECRET",
    )
    jwt_algorithm: str = Field(default="HS256", alias="JWT_ALGORITHM")
    access_token_expire_minutes: int = Field(
        default=60 * 24 * 30,  # 30 days
        alias="ACCESS_TOKEN_EXPIRE_MINUTES",
    )

    # AI stylist (chat + product search)
    anthropic_api_key: str | None = Field(default=None, alias="ANTHROPIC_API_KEY")
    serpapi_key: str | None = Field(default=None, alias="SERPAPI_KEY")
    shopping_locale: str = Field(default="in", alias="SHOPPING_LOCALE")
    shopping_currency: str = Field(default="₹", alias="SHOPPING_CURRENCY")

    @property
    def is_production(self) -> bool:
        return self.environment.lower() in ("production", "prod")

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: object) -> list[str]:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        if isinstance(value, list):
            return value
        return []

    @property
    def uploads_persons_dir(self) -> Path:
        return self.storage_root / "uploads" / "persons"

    @property
    def uploads_garments_dir(self) -> Path:
        return self.storage_root / "uploads" / "garments"

    @property
    def results_dir(self) -> Path:
        return self.storage_root / "results"

    @property
    def jobs_meta_dir(self) -> Path:
        return self.storage_root / "meta" / "jobs"

    @property
    def uploads_meta_dir(self) -> Path:
        return self.storage_root / "meta" / "uploads"

    def ensure_storage_dirs(self) -> None:
        for path in (
            self.uploads_persons_dir,
            self.uploads_garments_dir,
            self.results_dir,
            self.jobs_meta_dir,
            self.uploads_meta_dir,
        ):
            path.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    return Settings()
