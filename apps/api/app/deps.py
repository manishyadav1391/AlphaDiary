"""Request dependencies.

`require_session` is registered once on the application, so every `/api/v1`
route is protected unless its path is on the allowlist below. Adding a route
cannot accidentally leave it open; opening one has to be deliberate
(FR-AUTH-05).
"""

from __future__ import annotations

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_session
from app.errors import ApiError
from app.models import AppUser
from app.services.auth_service import load_session

API_PREFIX = "/api/v1"

PUBLIC_PATHS = frozenset(
    {
        f"{API_PREFIX}/health",
        f"{API_PREFIX}/auth/login",
        # The broker redirects the browser here before any app cookie is in
        # play; the one-time CSRF state is what protects it (FR-KITE-03).
        f"{API_PREFIX}/kite/callback",
    }
)


def is_public(path: str) -> bool:
    return path.rstrip("/") in PUBLIC_PATHS or not path.startswith(API_PREFIX)


def require_session(request: Request, session: Session = Depends(get_session)) -> None:
    if is_public(request.url.path):
        return

    settings = get_settings()
    session_id = request.cookies.get(settings.session_cookie_name)
    if not session_id:
        raise ApiError("unauthorized", "Sign in to continue.", status_code=401)

    user = load_session(session, session_id)
    if user is None:
        raise ApiError("unauthorized", "Your session has expired. Sign in again.", status_code=401)

    request.state.user = user
    request.state.session_id = session_id


def current_user(request: Request) -> AppUser:
    user: AppUser | None = getattr(request.state, "user", None)
    if user is None:
        raise ApiError("unauthorized", "Sign in to continue.", status_code=401)
    return user
