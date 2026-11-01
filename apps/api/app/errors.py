"""The single error envelope the API returns (SRS 4.3, API)."""

from __future__ import annotations

from typing import Any


class ApiError(Exception):
    """An error with a stable machine-readable code.

    The message is written for the owner reading a banner, and never carries a
    token, a credential or a Kite payload.
    """

    def __init__(
        self,
        code: str,
        message: str,
        *,
        status_code: int = 400,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or {}


def error_body(code: str, message: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"error": {"code": code, "message": message, "details": details or {}}}
