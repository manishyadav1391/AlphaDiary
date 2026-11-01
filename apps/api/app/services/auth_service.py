"""App login, sessions and login rate limiting (FR-AUTH)."""

from __future__ import annotations

import datetime as dt

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import AppSession, AppUser, LoginAttempt
from app.security import hash_password, needs_rehash, new_session_id, verify_password
from app.timezone import now_utc

# Verifying against a throwaway hash when the email is unknown keeps the
# response time of "no such user" and "wrong password" the same, so login
# cannot be used to find out which email is the owner's (NFR-04).
_DUMMY_HASH = hash_password("not-a-real-password")


class LockedOut(Exception):
    """Too many recent failures for this email (FR-AUTH-04)."""


def create_user(session: Session, email: str, password: str) -> AppUser:
    user = AppUser(email=email.strip().lower(), password_hash=hash_password(password))
    session.add(user)
    session.flush()
    return user


def get_user_by_email(session: Session, email: str) -> AppUser | None:
    return session.execute(
        select(AppUser).where(AppUser.email == email.strip().lower())
    ).scalar_one_or_none()


def recent_failures(session: Session, email: str, *, now: dt.datetime | None = None) -> int:
    settings = get_settings()
    since = (now or now_utc()) - dt.timedelta(minutes=settings.login_window_minutes)
    return int(
        session.execute(
            select(func.count())
            .select_from(LoginAttempt)
            .where(
                LoginAttempt.email == email.strip().lower(),
                LoginAttempt.success.is_(False),
                LoginAttempt.at >= since,
            )
        ).scalar_one()
    )


def is_locked_out(session: Session, email: str, *, now: dt.datetime | None = None) -> bool:
    return recent_failures(session, email, now=now) >= get_settings().login_max_attempts


def record_attempt(
    session: Session, email: str, *, success: bool, now: dt.datetime | None = None
) -> None:
    session.add(LoginAttempt(email=email.strip().lower(), success=success, at=now or now_utc()))
    session.flush()


def authenticate(
    session: Session, email: str, password: str, *, now: dt.datetime | None = None
) -> AppUser:
    """Returns the user, or raises. Never says which half of the pair was wrong."""
    if is_locked_out(session, email, now=now):
        raise LockedOut

    user = get_user_by_email(session, email)
    if user is None:
        verify_password(_DUMMY_HASH, password)
        record_attempt(session, email, success=False, now=now)
        raise ValueError("invalid credentials")

    if not verify_password(user.password_hash, password):
        record_attempt(session, email, success=False, now=now)
        raise ValueError("invalid credentials")

    if needs_rehash(user.password_hash):
        user.password_hash = hash_password(password)

    record_attempt(session, email, success=True, now=now)
    return user


def open_session(session: Session, user: AppUser, *, now: dt.datetime | None = None) -> AppSession:
    settings = get_settings()
    moment = now or now_utc()
    app_session = AppSession(
        id=new_session_id(),
        user_id=user.id,
        expires_at=moment + dt.timedelta(days=settings.session_ttl_days),
    )
    session.add(app_session)
    session.flush()
    return app_session


def load_session(
    session: Session, session_id: str, *, now: dt.datetime | None = None
) -> AppUser | None:
    """Resolve a cookie to its user, sliding the expiry forward (FR-AUTH-03)."""
    moment = now or now_utc()
    row = session.get(AppSession, session_id)
    if row is None:
        return None
    if row.expires_at <= moment:
        session.delete(row)
        session.flush()
        return None

    settings = get_settings()
    row.expires_at = moment + dt.timedelta(days=settings.session_ttl_days)
    session.flush()
    return session.get(AppUser, row.user_id)


def close_session(session: Session, session_id: str) -> None:
    session.execute(delete(AppSession).where(AppSession.id == session_id))
    session.flush()


def change_password(session: Session, user: AppUser, new_password: str) -> None:
    """Changing the password invalidates every existing session (FR-AUTH-06)."""
    user.password_hash = hash_password(new_password)
    session.execute(delete(AppSession).where(AppSession.user_id == user.id))
    session.flush()
