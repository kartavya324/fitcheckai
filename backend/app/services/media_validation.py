from app.core.exceptions import PayloadTooLargeError, ValidationError

CONTENT_TYPE_TO_EXTENSION: dict[str, str] = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
}


def normalize_content_type(content_type: str | None) -> str:
    if not content_type or not content_type.strip():
        raise ValidationError(
            "Content-Type is required",
            details={"field": "content_type"},
        )
    return content_type.split(";", 1)[0].strip().lower()


def extension_for_content_type(content_type: str) -> str:
    extension = CONTENT_TYPE_TO_EXTENSION.get(content_type)
    if extension is None:
        raise ValidationError(
            f"Unsupported content type: {content_type}",
            details={
                "content_type": content_type,
                "allowed": list(CONTENT_TYPE_TO_EXTENSION.keys()),
            },
        )
    return extension


def validate_image_upload(
    *,
    data: bytes,
    content_type: str,
    allowed_content_types: list[str],
    max_upload_bytes: int,
) -> str:
    if not data:
        raise ValidationError("Uploaded file is empty")

    if len(data) > max_upload_bytes:
        raise PayloadTooLargeError(
            f"File exceeds maximum size of {max_upload_bytes} bytes",
            details={"size_bytes": len(data), "max_bytes": max_upload_bytes},
        )

    normalized = normalize_content_type(content_type)
    if normalized not in allowed_content_types:
        raise ValidationError(
            f"Unsupported content type: {normalized}",
            details={
                "content_type": normalized,
                "allowed": allowed_content_types,
            },
        )

    if not _content_matches_magic(normalized, data):
        raise ValidationError(
            "File content does not match declared image type",
            details={"content_type": normalized},
        )

    return extension_for_content_type(normalized)


def _content_matches_magic(content_type: str, data: bytes) -> bool:
    if content_type == "image/jpeg":
        return len(data) >= 3 and data[:3] == b"\xff\xd8\xff"
    if content_type == "image/png":
        return len(data) >= 8 and data[:8] == b"\x89PNG\r\n\x1a\n"
    if content_type == "image/webp":
        return len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP"
    return False
