import pytest

from app.core.exceptions import PayloadTooLargeError, ValidationError
from app.services.media_validation import validate_image_upload
from tests.api.test_uploads import JPEG_BYTES, PNG_BYTES


def test_validate_image_upload_accepts_jpeg() -> None:
    ext = validate_image_upload(
        data=JPEG_BYTES,
        content_type="image/jpeg",
        allowed_content_types=["image/jpeg", "image/png", "image/webp"],
        max_upload_bytes=10_485_760,
    )
    assert ext == "jpg"


def test_validate_image_upload_rejects_empty() -> None:
    with pytest.raises(ValidationError):
        validate_image_upload(
            data=b"",
            content_type="image/png",
            allowed_content_types=["image/png"],
            max_upload_bytes=1024,
        )


def test_validate_image_upload_rejects_oversized() -> None:
    with pytest.raises(PayloadTooLargeError):
        validate_image_upload(
            data=PNG_BYTES + (b"\x00" * 2000),
            content_type="image/png",
            allowed_content_types=["image/png"],
            max_upload_bytes=100,
        )
