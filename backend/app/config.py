from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    app_name: str = Field(default="fitcheck-api", alias="APP_NAME")
    app_version: str = Field(default="0.1.0", alias="APP_VERSION")
    storage_root: Path = Field(default=Path("./storage"), alias="STORAGE_ROOT")
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
    generation_stub: bool = Field(default=True, alias="GENERATION_STUB")
    job_simulation_seconds: float = Field(default=5.0, alias="JOB_SIMULATION_SECONDS")
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field(
        default="INFO",
        alias="LOG_LEVEL",
    )
    allowed_content_types: list[str] = Field(
        default=["image/jpeg", "image/png", "image/webp"],
    )
    replicate_api_token: str | None = Field(default=None, alias="REPLICATE_API_TOKEN")
    hf_token: str | None = Field(default=None, alias="HF_TOKEN")
    generation_mode: Literal["replicate_2d", "econ_3d"] = Field(
        default="replicate_2d",
        alias="GENERATION_MODE",
    )

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
