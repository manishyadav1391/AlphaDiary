"""App login, lockout and sessions (FR-AUTH)."""

from __future__ import annotations

import datetime as dt

import pytest
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import AppSession, AppUser
from app.security import hash_password, verify_password
from app.services import auth_service
from app.timezone import now_utc

PASSWORD = "correct-horse-battery-staple"


def test_passwords_are_argon2id_hashed() -> None:
    stored = hash_password(PASSWORD)

    assert stored.startswith("$argon2id$")
    assert PASSWORD not in stored
    assert verify_password(stored, PASSWORD)
    assert not verify_password(stored, PASSWORD + "x")


def test_the_same_password_hashes_differently_each_time() -> None:
    assert hash_password(PASSWORD) != hash_password(PASSWORD)


def test_authenticate_accepts_the_right_password(session: Session, user: AppUser) -> None:
    assert auth_service.authenticate(session, user.email, PASSWORD).id == user.id


def test_authenticate_is_case_insensitive_on_email(session: Session, user: AppUser) -> None:
    assert auth_service.authenticate(session, user.email.upper(), PASSWORD).id == user.id


def test_wrong_password_is_rejected_and_recorded(session: Session, user: AppUser) -> None:
    with pytest.raises(ValueError):
        auth_service.authenticate(session, user.email, "wrong")
    assert auth_service.recent_failures(session, user.email) == 1


def test_unknown_email_fails_the_same_way_as_a_wrong_password(session: Session) -> None:
    """The caller must not be able to tell which email is the owner's."""
    with pytest.raises(ValueError):
        auth_service.authenticate(session, "nobody@example.test", PASSWORD)


def test_five_failures_lock_further_attempts(session: Session, user: AppUser) -> None:
    """FR-AUTH-04."""
    settings = get_settings()
    for _ in range(settings.login_max_attempts):
        with pytest.raises(ValueError):
            auth_service.authenticate(session, user.email, "wrong")

    # Even the correct password is refused while the lockout holds.
    with pytest.raises(auth_service.LockedOut):
        auth_service.authenticate(session, user.email, PASSWORD)


def test_the_lockout_lifts_once_the_failures_age_out(session: Session, user: AppUser) -> None:
    settings = get_settings()
    old = now_utc() - dt.timedelta(minutes=settings.login_window_minutes + 1)
    for _ in range(settings.login_max_attempts):
        auth_service.record_attempt(session, user.email, success=False, now=old)

    assert not auth_service.is_locked_out(session, user.email)
    assert auth_service.authenticate(session, user.email, PASSWORD).id == user.id


def test_a_session_resolves_to_its_user(session: Session, user: AppUser) -> None:
    opened = auth_service.open_session(session, user)
    assert auth_service.load_session(session, opened.id) is not None


def test_session_expiry_slides_forward_on_use(session: Session, user: AppUser) -> None:
    """FR-AUTH-03: 7 days sliding."""
    settings = get_settings()
    opened = auth_service.open_session(session, user)
    original = opened.expires_at

    later = now_utc() + dt.timedelta(days=1)
    auth_service.load_session(session, opened.id, now=later)

    session.refresh(opened)
    assert opened.expires_at > original
    assert opened.expires_at - later == dt.timedelta(days=settings.session_ttl_days)


def test_an_expired_session_is_rejected_and_deleted(session: Session, user: AppUser) -> None:
    opened = auth_service.open_session(session, user)
    much_later = now_utc() + dt.timedelta(days=get_settings().session_ttl_days + 1)

    assert auth_service.load_session(session, opened.id, now=much_later) is None
    assert session.get(AppSession, opened.id) is None


def test_logout_destroys_the_session_server_side(session: Session, user: AppUser) -> None:
    """FR-AUTH-06: holding the cookie afterwards is not enough."""
    opened = auth_service.open_session(session, user)
    auth_service.close_session(session, opened.id)

    assert auth_service.load_session(session, opened.id) is None


def test_changing_the_password_invalidates_every_session(session: Session, user: AppUser) -> None:
    first = auth_service.open_session(session, user)
    second = auth_service.open_session(session, user)

    auth_service.change_password(session, user, "a-brand-new-long-password")

    assert auth_service.load_session(session, first.id) is None
    assert auth_service.load_session(session, second.id) is None
    assert auth_service.authenticate(session, user.email, "a-brand-new-long-password")
