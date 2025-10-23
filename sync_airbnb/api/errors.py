"""Standardized error handling for API responses."""

import logging
from typing import Any

from fastapi import HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


class ErrorResponse:
    """Standard error response format for API errors."""

    @staticmethod
    def format(
        error_code: str,
        message: str,
        details: dict[str, Any] | None = None,
        request_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Format error response with consistent structure.

        Args:
            error_code: Error code (e.g., "ACCOUNT_NOT_FOUND", "VALIDATION_ERROR")
            message: Human-readable error message
            details: Additional error details (optional)
            request_id: Request ID for tracing (optional)

        Returns:
            Standardized error response dictionary
        """
        return {
            "error": {
                "code": error_code,
                "message": message,
                "details": details or {},
                "request_id": request_id,
            }
        }


async def http_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle HTTPException with standardized error format."""
    if not isinstance(exc, HTTPException):
        return await general_exception_handler(request, exc)

    request_id = getattr(request.state, "request_id", None)

    # Log error with request context
    logger.error(
        f"HTTP {exc.status_code}: {exc.detail}",
        extra={
            "status_code": exc.status_code,
            "request_id": request_id,
            "path": request.url.path,
        },
    )

    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse.format(
            error_code=f"HTTP_{exc.status_code}",
            message=str(exc.detail),
            request_id=request_id,
        ),
    )


async def validation_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle Pydantic validation errors with standardized format."""
    if not isinstance(exc, RequestValidationError):
        return await general_exception_handler(request, exc)

    request_id = getattr(request.state, "request_id", None)

    # Extract validation error details
    errors = []
    for error in exc.errors():
        errors.append(
            {
                "field": ".".join(str(loc) for loc in error["loc"]),
                "message": error["msg"],
                "type": error["type"],
            }
        )

    # Log validation error
    logger.warning(
        f"Validation error: {len(errors)} field(s)",
        extra={
            "request_id": request_id,
            "path": request.url.path,
            "errors": errors,
        },
    )

    return JSONResponse(
        status_code=422,
        content=ErrorResponse.format(
            error_code="VALIDATION_ERROR",
            message="Request validation failed",
            details={"validation_errors": errors},
            request_id=request_id,
        ),
    )


async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle unexpected exceptions with standardized format."""
    request_id = getattr(request.state, "request_id", None)

    # Log unexpected error with full traceback
    logger.error(
        f"Unexpected error: {type(exc).__name__}: {str(exc)}",
        extra={
            "request_id": request_id,
            "path": request.url.path,
            "error_type": type(exc).__name__,
        },
        exc_info=True,
    )

    return JSONResponse(
        status_code=500,
        content=ErrorResponse.format(
            error_code="INTERNAL_ERROR",
            message="An unexpected error occurred",
            details={"error_type": type(exc).__name__},
            request_id=request_id,
        ),
    )
