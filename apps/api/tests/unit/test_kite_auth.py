"""Kite connect: CSRF state, token storage and the estimated expiry (FR-KITE)."""

from __future__ import annotations

import datetime as dt

import pytest
from sqlalchemy.orm import Session

from app.models import BrokerAccount
from app.security import decrypt
from app.services import oauth_state, token_store
from app.services.kite_client import KiteSession
from app.timezone import IST, next_six_am_ist, now_utc

TOKEN = "a-real-looking-access-token"


# ------------------------------------------------------------ token expiry


@pytest.mark.parametrize(
    ("issued_ist", "expected_ist"),
    [
        # Issued during the trading day: expires 06:00 the next morning.
        ("2026-11-02 09:20:00", "2026-11-03 06:00:00"),
        # Issued just before 06:00: that same morning is still ahead.
        ("2026-11-02 05:59:00", "2026-11-02 06:00:00"),
        # Issued exactly at 06:00: the next one is a day later.
        ("2026-11-02 06:00:00", "2026-11-03 06:00:00"),
        # Issued late in an MCX evening session.
        ("2026-11-02 23:45:00", "2026-11-03 06:00:00"),
    ],
)
def test_token_expiry_is_the_next_six_am_ist(issued_ist: str, expected_ist: str) -> None:
    """FR-KITE-04, and what Zerodha documents for the access token."""
    issued = dt.datetime.strptime(issued_ist, "%Y-%m-%d %H:%M:%S").replace(tzinfo=IST)

    expiry = next_six_am_ist(issued)

    assert expiry.tzinfo == dt.UTC
    assert expiry.astimezone(IST).strftime("%Y-%m-%d %H:%M:%S") == expected_ist


# -------------------------------------------------------------- token store


def test_the_access_token_is_stored_encrypted(session: Session, account: BrokerAccount) -> None:
    """FR-KITE-01: the plaintext must not be readable in the column."""
    token_store.store_token(
        session,
        account,
        KiteSession(access_token=TOKEN, kite_user_id="XX0000", login_time=now_utc()),
    )

    assert account.access_token_enc is not None
    assert TOKEN.encode() not in account.access_token_enc
    assert decrypt(account.access_token_enc) == TOKEN
    assert token_store.load_access_token(account) == TOKEN


def test_credentials_are_stored_encrypted(session: Session, account: BrokerAccount) -> None:
    assert account.api_secret_enc is not None
    assert b"test_api_secret" not in account.api_secret_enc
    assert token_store.load_credentials(account) == ("test_api_key", "test_api_secret")


def test_the_api_key_is_only_ever_shown_masked(account: BrokerAccount) -> None:
    """FR-KITE-01: last 4 characters only."""
    masked = token_store.masked_api_key(account)

    assert masked is not None
    assert masked.endswith("_key")
    assert "test_api" not in masked


def test_a_token_past_its_estimated_expiry_is_not_used(
    session: Session, account: BrokerAccount
) -> None:
    yesterday = now_utc() - dt.timedelta(days=1)
    token_store.store_token(
        session,
        account,
        KiteSession(access_token=TOKEN, kite_user_id="XX0000", login_time=yesterday),
    )

    assert not token_store.token_may_be_valid(account)


def test_marking_expired_takes_effect_immediately(
    session: Session, connected_account: BrokerAccount
) -> None:
    """FR-KITE-06."""
    assert token_store.token_may_be_valid(connected_account)

    token_store.mark_token_expired(session, connected_account)

    assert not token_store.token_may_be_valid(connected_account)


def test_disconnect_drops_the_token_but_keeps_the_credentials(
    session: Session, connected_account: BrokerAccount
) -> None:
    """FR-KITE-10."""
    token_store.clear_token(session, connected_account)

    assert connected_account.access_token_enc is None
    assert connected_account.token_valid_until is None
    assert token_store.load_credentials(connected_account) == (
        "test_api_key",
        "test_api_secret",
    )


# ---------------------------------------------------------------- CSRF state


def test_a_state_can_be_used_once(session: Session, account: BrokerAccount) -> None:
    issued = oauth_state.issue(session, account)

    consumed = oauth_state.consume(session, issued.state)

    assert consumed.account_id == account.id
    assert consumed.used_at is not None


def test_a_replayed_state_is_rejected(session: Session, account: BrokerAccount) -> None:
    """FR-KITE-03 acceptance: a replayed state value is rejected."""
    issued = oauth_state.issue(session, account)
    oauth_state.consume(session, issued.state)

    with pytest.raises(oauth_state.InvalidState):
        oauth_state.consume(session, issued.state)


def test_an_expired_state_is_rejected(session: Session, account: BrokerAccount) -> None:
    issued = oauth_state.issue(session, account)
    too_late = issued.expires_at + dt.timedelta(seconds=1)

    with pytest.raises(oauth_state.InvalidState):
        oauth_state.consume(session, issued.state, now=too_late)


def test_an_unknown_state_is_rejected(session: Session) -> None:
    with pytest.raises(oauth_state.InvalidState):
        oauth_state.consume(session, "never-issued")


def test_an_empty_state_is_rejected(session: Session) -> None:
    with pytest.raises(oauth_state.InvalidState):
        oauth_state.consume(session, "")


def test_states_are_not_guessable(session: Session, account: BrokerAccount) -> None:
    values = {oauth_state.issue(session, account).state for _ in range(5)}

    assert len(values) == 5
    assert all(len(value) >= 32 for value in values)
