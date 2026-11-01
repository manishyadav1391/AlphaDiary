"""App login (FR-AUTH). Thin: the logic lives in services/auth_service.py."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_session
from app.deps import current_user
from app.errors import ApiError
from app.models import AppUser
from app.schemas.auth import ChangePasswordRequest, LoginRequest, UserOut
from app.security import verify_password
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])
logger = logging.getLogger("tj.auth")


def _set_session_cookie(response: Response, session_id: str) -> None:
    settings = get_settings()
    response.set_cookie(
        key=settings.session_cookie_name,
        value=session_id,
        max_age=settings.session_ttl_days * 24 * 60 * 60,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/",
    )


@router.post("/login", response_model=UserOut)
def login(
    payload: LoginRequest,
    response: Response,
    session: Session = Depends(get_session),
) -> AppUser:
    try:
        user = auth_service.authenticate(session, payload.email, payload.password)
    except auth_service.LockedOut:
        # Logged without the password and without saying whether the email exists.
        logger.warning("Login locked out", extra={"event": "login_locked_out"})
        raise ApiError(
            "too_many_attempts",
            "Too many failed sign-ins. Try again in 15 minutes.",
            status_code=429,
        ) from None
    except ValueError:
        logger.info("Login failed", extra={"event": "login_failed"})
        raise ApiError(
            "invalid_credentials", "Email or password is wrong.", status_code=401
        ) from None

    app_session = auth_service.open_session(session, user)
    _set_session_cookie(response, app_session.id)
    return user


@router.post("/logout", status_code=204)
def logout(request: Request, session: Session = Depends(get_session)) -> Response:
    session_id = getattr(request.state, "session_id", None)
    if session_id:
        auth_service.close_session(session, session_id)

    settings = get_settings()
    response = Response(status_code=204)
    response.delete_cookie(
        settings.session_cookie_name,
        path="/",
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
    )
    return response


@router.get("/me", response_model=UserOut)
def me(user: AppUser = Depends(current_user)) -> AppUser:
    return user


@router.post("/change-password", status_code=204)
def change_password(
    payload: ChangePasswordRequest,
    user: AppUser = Depends(current_user),
    session: Session = Depends(get_session),
) -> Response:
    if not verify_password(user.password_hash, payload.current_password):
        raise ApiError("invalid_credentials", "Current password is wrong.", status_code=401)
    auth_service.change_password(session, user, payload.new_password)
    return Response(status_code=204)
