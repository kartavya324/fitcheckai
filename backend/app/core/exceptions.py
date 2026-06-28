from typing import Any


class AppError(Exception):
    """Base application error mapped to HTTP responses."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "APP_ERROR",
        status_code: int = 500,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details or {}


class ValidationError(AppError):
    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(
            message,
            code="VALIDATION_ERROR",
            status_code=400,
            details=details,
        )


class NotFoundError(AppError):
    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(
            message,
            code="NOT_FOUND",
            status_code=404,
            details=details,
        )


class ConflictError(AppError):
    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(
            message,
            code="CONFLICT",
            status_code=409,
            details=details,
        )


class PayloadTooLargeError(AppError):
    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(
            message,
            code="PAYLOAD_TOO_LARGE",
            status_code=413,
            details=details,
        )


class NotImplementedServiceError(AppError):
    def __init__(self, message: str = "Not implemented") -> None:
        super().__init__(message, code="NOT_IMPLEMENTED", status_code=501)
