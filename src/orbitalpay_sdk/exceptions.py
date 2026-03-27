"""Exception hierarchy for OrbitalPay SDK."""

from __future__ import annotations

from typing import Any

import httpx


class OrbitalPayError(Exception):
    """Base exception for all OrbitalPay SDK errors."""

    def __init__(
        self,
        message: str,
        status_code: int | None = None,
        detail: Any = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.detail = detail


class AuthenticationError(OrbitalPayError):
    """Raised on 401 Unauthorized."""


class ForbiddenError(OrbitalPayError):
    """Raised on 403 Forbidden."""


class NotFoundError(OrbitalPayError):
    """Raised on 404 Not Found."""


class ValidationError(OrbitalPayError):
    """Raised on 400 Bad Request or 422 Unprocessable Entity."""


class RateLimitError(OrbitalPayError):
    """Raised on 429 Too Many Requests."""


class ServerError(OrbitalPayError):
    """Raised on 500+ Internal Server Error."""


def raise_for_status(response: httpx.Response) -> None:
    """Inspect an HTTP response and raise the appropriate OrbitalPayError subclass."""
    if response.is_success:
        return

    status = response.status_code
    try:
        body = response.json()
    except Exception:
        body = {"message": response.text}

    message = body.get("message") or body.get("error") or response.reason_phrase or "Unknown error"
    detail = body.get("detail", body)

    error_map: dict[int, type[OrbitalPayError]] = {
        400: ValidationError,
        401: AuthenticationError,
        403: ForbiddenError,
        404: NotFoundError,
        422: ValidationError,
        429: RateLimitError,
    }

    cls = error_map.get(status)
    if cls is None:
        cls = ServerError if status >= 500 else OrbitalPayError

    raise cls(message=str(message), status_code=status, detail=detail)
