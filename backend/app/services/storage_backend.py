"""
Pluggable object storage: local disk (dev) or S3/R2 (prod), chosen by
STORAGE_BACKEND. Everything is addressed by a storage-root-relative *key*
(e.g. "avatars/abc.glb", "uploads/persons/x.jpg") so switching backends never
changes the keys — only where bytes live and how URLs are built.

LocalBackend intentionally reproduces the pre-existing behaviour exactly:
bytes under storage_root/<key>, URLs as {public_base_url}/files/<key>. So
adopting it at write sites is a no-op locally; setting STORAGE_BACKEND=s3
flips those same sites to the bucket with zero call-site changes.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Protocol, runtime_checkable

from app.config import Settings, get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)


@runtime_checkable
class StorageBackend(Protocol):
    def save(self, key: str, data: bytes, content_type: str | None = None) -> str: ...
    def read(self, key: str) -> bytes: ...
    def delete(self, key: str) -> None: ...
    def exists(self, key: str) -> bool: ...
    def url(self, key: str) -> str: ...
    def local_path(self, key: str) -> Path | None:
        """Absolute filesystem path if the bytes live on local disk, else None.
        Pipeline code that must hand a real file to a subprocess uses this;
        for remote backends it returns None and the caller must read()+stage."""
        ...


class LocalBackend:
    def __init__(self, settings: Settings) -> None:
        self._s = settings

    def _abs(self, key: str) -> Path:
        return self._s.storage_root / key

    def save(self, key: str, data: bytes, content_type: str | None = None) -> str:
        p = self._abs(key)
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_name(f".{p.name}.tmp")
        tmp.write_bytes(data)
        tmp.replace(p)  # atomic within the same dir
        return self.url(key)

    def read(self, key: str) -> bytes:
        return self._abs(key).read_bytes()

    def delete(self, key: str) -> None:
        self._abs(key).unlink(missing_ok=True)

    def exists(self, key: str) -> bool:
        return self._abs(key).is_file()

    def url(self, key: str) -> str:
        return f"{self._s.public_base_url.rstrip('/')}/files/{key.lstrip('/')}"

    def local_path(self, key: str) -> Path | None:
        return self._abs(key)


class S3Backend:
    """S3 / Cloudflare R2 / any S3-compatible store (boto3)."""

    def __init__(self, settings: Settings) -> None:
        import boto3  # imported lazily so local dev needs no boto3

        self._s = settings
        self._bucket = settings.s3_bucket
        if not self._bucket:
            raise RuntimeError("STORAGE_BACKEND=s3 but S3_BUCKET is not set")
        self._client = boto3.client(
            "s3",
            region_name=settings.s3_region,
            endpoint_url=settings.s3_endpoint_url,  # None for AWS, set for R2/MinIO
            aws_access_key_id=settings.s3_access_key_id,
            aws_secret_access_key=settings.s3_secret_access_key,
        )

    def save(self, key: str, data: bytes, content_type: str | None = None) -> str:
        extra = {"ContentType": content_type} if content_type else {}
        self._client.put_object(Bucket=self._bucket, Key=key, Body=data, **extra)
        return self.url(key)

    def read(self, key: str) -> bytes:
        return self._client.get_object(Bucket=self._bucket, Key=key)["Body"].read()

    def delete(self, key: str) -> None:
        self._client.delete_object(Bucket=self._bucket, Key=key)

    def exists(self, key: str) -> bool:
        from botocore.exceptions import ClientError
        try:
            self._client.head_object(Bucket=self._bucket, Key=key)
            return True
        except ClientError:
            return False

    def url(self, key: str) -> str:
        key = key.lstrip("/")
        base = self._s.s3_public_base_url
        if base:
            return f"{base.rstrip('/')}/{key}"
        # Default AWS virtual-hosted-style URL
        return f"https://{self._bucket}.s3.{self._s.s3_region}.amazonaws.com/{key}"

    def local_path(self, key: str) -> Path | None:
        return None


@lru_cache
def get_storage_backend() -> StorageBackend:
    settings = get_settings()
    if settings.storage_backend == "s3":
        logger.info("Storage backend: S3 (bucket=%s)", settings.s3_bucket)
        return S3Backend(settings)
    return LocalBackend(settings)


# ── Content-type helper (so remote objects serve with the right MIME) ──
_CONTENT_TYPES = {
    "glb": "model/gltf-binary",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "png": "image/png",
    "webp": "image/webp",
    "json": "application/json",
}


def content_type_for(key: str) -> str | None:
    ext = key.rsplit(".", 1)[-1].lower() if "." in key else ""
    return _CONTENT_TYPES.get(ext)
