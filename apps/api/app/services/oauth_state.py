"""One-time CSRF state for the Kite login redirect (FR-KITE-02, FR-KITE-03).

A state value is good for ten minutes and for exactly one callback. Both a
replayed and an expired value are rejected, which is what stops someone from
feeding us a request token of their own.
"""

from __future__ import annotations

import datetime as dt

from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import BrokerAccount, OAuthState
from app.security import new_state_token
from app.timezone import now_utc


class InvalidState(Exception):
    """Unknown, expired or already-used state value."""


def issue(
    session: Session, account: BrokerAccount, *, now: dt.datetime | None = None
) -> OAuthState:
    settings = get_settings()
    moment = now or now_utc()
    state = OAuthState(
        state=new_state_token(),
        account_id=account.id,
        expires_at=moment + dt.timedelta(minutes=settings.oauth_state_ttl_minutes),
    )
    session.add(state)
    session.flush()
    return state


def consume(session: Session, state: str, *, now: dt.datetime | None = None) -> OAuthState:
    """Validate and burn a state value. Raises `InvalidState` otherwise."""
    moment = now or now_utc()
    row = session.get(OAuthState, state) if state else None
    if row is None:
        raise InvalidState("unknown state")
    if row.used_at is not None:
        raise InvalidState("state already used")
    if row.expires_at <= moment:
        raise InvalidState("state expired")
    row.used_at = moment
    session.flush()
    return row
