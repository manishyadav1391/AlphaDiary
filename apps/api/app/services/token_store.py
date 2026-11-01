"""Broker credentials and the daily Kite access token.

Everything sensitive lives encrypted in `broker_account`: the API key, the API
secret and the access token (FR-KITE-01). Plaintext exists only inside this
module and the `KiteClient` it builds.

`token_valid_until` is set to the next 06:00 IST after the token was issued,
which is when Zerodha documents the token as expiring. It is an estimate used
to avoid pointless calls; the authoritative check is a live `profile()` call
(FR-KITE-04, FR-KITE-05).
"""

from __future__ import annotations

import datetime as dt

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AppUser, BrokerAccount
from app.security import decrypt, encrypt
from app.services.kite_client import KiteClient, KiteSession
from app.timezone import next_six_am_ist, now_utc


class NotConfigured(Exception):
    """No broker account, or no API credentials stored on it (FR-KITE-05)."""


def get_account(session: Session) -> BrokerAccount | None:
    """The single owner's broker account. This is a one-user app (SRS 3.2)."""
    return session.execute(
        select(BrokerAccount).order_by(BrokerAccount.created_at).limit(1)
    ).scalar_one_or_none()


def require_account(session: Session) -> BrokerAccount:
    account = get_account(session)
    if account is None:
        raise NotConfigured("no broker account")
    return account


def save_credentials(
    session: Session, user: AppUser, api_key: str, api_secret: str
) -> BrokerAccount:
    account = get_account(session)
    if account is None:
        account = BrokerAccount(user_id=user.id, broker="zerodha")
        session.add(account)
    account.api_key_enc = encrypt(api_key)
    account.api_secret_enc = encrypt(api_secret)
    session.flush()
    return account


def load_credentials(account: BrokerAccount) -> tuple[str, str]:
    if not account.api_key_enc or not account.api_secret_enc:
        raise NotConfigured("API credentials are not set")
    return decrypt(account.api_key_enc), decrypt(account.api_secret_enc)


def masked_api_key(account: BrokerAccount) -> str | None:
    """The key shown to the browser: last 4 characters only (FR-KITE-01)."""
    if not account.api_key_enc:
        return None
    key = decrypt(account.api_key_enc)
    return f"{'*' * max(len(key) - 4, 0)}{key[-4:]}"


def store_token(
    session: Session,
    account: BrokerAccount,
    kite_session: KiteSession,
    *,
    now: dt.datetime | None = None,
) -> BrokerAccount:
    issued_at = kite_session.login_time or now or now_utc()
    account.access_token_enc = encrypt(kite_session.access_token)
    account.token_issued_at = issued_at
    account.token_valid_until = next_six_am_ist(issued_at)
    if kite_session.kite_user_id:
        account.kite_user_id = kite_session.kite_user_id
    session.flush()
    return account


def load_access_token(account: BrokerAccount) -> str | None:
    if not account.access_token_enc:
        return None
    return decrypt(account.access_token_enc)


def clear_token(session: Session, account: BrokerAccount) -> None:
    """Disconnect: drop the token, keep the trade data (FR-KITE-10)."""
    account.access_token_enc = None
    account.token_issued_at = None
    account.token_valid_until = None
    session.flush()


def mark_token_expired(session: Session, account: BrokerAccount) -> None:
    """Record that Zerodha rejected the token, so the banner and the reminder
    logic can act without waiting for the estimated expiry (FR-KITE-06)."""
    account.token_valid_until = now_utc()
    session.flush()


def token_may_be_valid(account: BrokerAccount, *, now: dt.datetime | None = None) -> bool:
    """Cheap clock check before spending a Kite call. Never a substitute for
    `profile()`: a token can be killed early by a master logout."""
    if not account.access_token_enc:
        return False
    if account.token_valid_until is None:
        return True
    return account.token_valid_until > (now or now_utc())


def build_client(session: Session, account: BrokerAccount) -> KiteClient:
    """A client wired to mark the stored token expired on a TokenException."""
    api_key, api_secret = load_credentials(account)

    def on_token_expired() -> None:
        mark_token_expired(session, account)

    return KiteClient(
        api_key=api_key,
        api_secret=api_secret,
        access_token=load_access_token(account),
        on_token_expired=on_token_expired,
    )
