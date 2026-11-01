"""The Kite connect flow end to end, with Zerodha mocked (FR-KITE)."""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import BrokerAccount
from app.routers import kite as kite_router
from app.security import decrypt
from app.services import oauth_state, token_store
from app.services.kite_client import KiteSession, TokenExpired
from app.timezone import now_utc

ACCESS_TOKEN = "kite-access-token-from-zerodha"
REQUEST_TOKEN = "short-lived-request-token"


class FakeKiteClient:
    """Stands in for `KiteClient` so no test reaches the network."""

    def __init__(self, *, exchange_raises: Exception | None = None) -> None:
        self._exchange_raises = exchange_raises

    def login_url(self, state: str) -> str:
        return (
            "https://kite.zerodha.com/connect/login?api_key=test_api_key&v=3"
            f"&redirect_params=state%3D{state}"
        )

    def exchange_request_token(self, request_token: str) -> KiteSession:
        if self._exchange_raises is not None:
            raise self._exchange_raises
        return KiteSession(access_token=ACCESS_TOKEN, kite_user_id="XX0000", login_time=now_utc())

    def profile(self) -> dict[str, Any]:
        return {"user_id": "XX0000"}


@pytest.fixture(autouse=True)
def no_background_sync(monkeypatch: pytest.MonkeyPatch) -> None:
    """The callback schedules a catch-up sync on its own session; this keeps
    the test's transaction the only thing touching the database."""
    monkeypatch.setattr(kite_router, "_catchup_sync", lambda: None)


@pytest.fixture
def fake_client(monkeypatch: pytest.MonkeyPatch) -> FakeKiteClient:
    fake = FakeKiteClient()
    monkeypatch.setattr(token_store, "build_client", lambda session, account: fake)
    return fake


@pytest.fixture(autouse=True)
def clear_status_cache() -> None:
    kite_router._status_cache.clear()


# ------------------------------------------------------------- login-url


def test_login_url_carries_a_one_time_state(
    authenticated_client: TestClient,
    account: BrokerAccount,
    fake_client: FakeKiteClient,
    session: Session,
) -> None:
    """FR-KITE-02."""
    response = authenticated_client.get("/api/v1/kite/login-url")

    assert response.status_code == 200
    body = response.json()
    assert body["login_url"].startswith("https://kite.zerodha.com/connect/login")
    assert "redirect_params=state%3D" in body["login_url"]
    assert body["redirect_url"] == get_settings().kite_redirect_url

    # The same value is also set as a cookie, because the docs do not pin down
    # how redirect_params comes back (VERIFY V5).
    assert get_settings().oauth_state_cookie_name in response.headers["set-cookie"]


def test_login_url_refuses_when_no_credentials_are_stored(
    authenticated_client: TestClient,
) -> None:
    response = authenticated_client.get("/api/v1/kite/login-url")

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "not_configured"


# --------------------------------------------------------------- callback


def test_callback_stores_the_token_encrypted(
    client: TestClient,
    session: Session,
    account: BrokerAccount,
    fake_client: FakeKiteClient,
) -> None:
    """FR-KITE-03, and this milestone's acceptance criterion."""
    state = oauth_state.issue(session, account)

    response = client.get(
        "/api/v1/kite/callback",
        params={"request_token": REQUEST_TOKEN, "status": "success", "state": state.state},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"].endswith("/?connected=1")

    session.refresh(account)
    assert account.access_token_enc is not None
    # Encrypted at rest, not merely encoded.
    assert ACCESS_TOKEN.encode() not in account.access_token_enc
    assert decrypt(account.access_token_enc) == ACCESS_TOKEN
    assert account.kite_user_id == "XX0000"
    assert account.token_valid_until is not None


def test_callback_accepts_the_state_from_the_cookie(
    client: TestClient,
    session: Session,
    account: BrokerAccount,
    fake_client: FakeKiteClient,
) -> None:
    """The fallback for V5: Kite may not echo redirect_params back."""
    state = oauth_state.issue(session, account)
    client.cookies.set(get_settings().oauth_state_cookie_name, state.state)

    response = client.get(
        "/api/v1/kite/callback",
        params={"request_token": REQUEST_TOKEN},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"].endswith("/?connected=1")


def test_callback_rejects_a_replayed_state(
    client: TestClient,
    session: Session,
    account: BrokerAccount,
    fake_client: FakeKiteClient,
) -> None:
    state = oauth_state.issue(session, account)
    params = {"request_token": REQUEST_TOKEN, "state": state.state}

    first = client.get("/api/v1/kite/callback", params=params, follow_redirects=False)
    client.cookies.clear()
    second = client.get("/api/v1/kite/callback", params=params, follow_redirects=False)

    assert first.headers["location"].endswith("/?connected=1")
    assert second.headers["location"].endswith("/?kite_error=invalid_state")


def test_callback_rejects_an_unknown_state(
    client: TestClient, account: BrokerAccount, fake_client: FakeKiteClient
) -> None:
    response = client.get(
        "/api/v1/kite/callback",
        params={"request_token": REQUEST_TOKEN, "state": "never-issued"},
        follow_redirects=False,
    )

    assert response.headers["location"].endswith("/?kite_error=invalid_state")


def test_callback_rejects_a_failed_login(
    client: TestClient, session: Session, account: BrokerAccount
) -> None:
    state = oauth_state.issue(session, account)

    response = client.get(
        "/api/v1/kite/callback",
        params={"request_token": REQUEST_TOKEN, "status": "failure", "state": state.state},
        follow_redirects=False,
    )

    assert response.headers["location"].endswith("/?kite_error=login_failed")


def test_callback_never_puts_the_token_in_the_redirect(
    client: TestClient,
    session: Session,
    account: BrokerAccount,
    fake_client: FakeKiteClient,
) -> None:
    """NFR-04: no secrets in URLs."""
    state = oauth_state.issue(session, account)

    response = client.get(
        "/api/v1/kite/callback",
        params={"request_token": REQUEST_TOKEN, "state": state.state},
        follow_redirects=False,
    )

    assert ACCESS_TOKEN not in response.headers["location"]
    assert ACCESS_TOKEN not in response.text


# ----------------------------------------------------------------- status


def test_status_is_not_configured_without_credentials(
    authenticated_client: TestClient,
) -> None:
    response = authenticated_client.get("/api/v1/kite/status")

    assert response.status_code == 200
    assert response.json()["status"] == "not_configured"


def test_status_is_connected_when_the_live_check_passes(
    authenticated_client: TestClient,
    connected_account: BrokerAccount,
    fake_client: FakeKiteClient,
) -> None:
    response = authenticated_client.get("/api/v1/kite/status")

    body = response.json()
    assert body["status"] == "connected"
    assert body["kite_user_id"] == "XX0000"
    # FR-KITE-01: the key is masked and the secret is absent.
    assert body["api_key_masked"].endswith("_key")
    assert "test_api_secret" not in response.text


def test_status_is_expired_when_zerodha_rejects_the_token(
    authenticated_client: TestClient,
    connected_account: BrokerAccount,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """FR-KITE-06."""

    class Rejecting(FakeKiteClient):
        def profile(self) -> dict[str, Any]:
            raise TokenExpired("profile")

    monkeypatch.setattr(token_store, "build_client", lambda session, account: Rejecting())

    response = authenticated_client.get("/api/v1/kite/status")

    assert response.json()["status"] == "expired"


def test_disconnect_removes_the_token(
    authenticated_client: TestClient,
    session: Session,
    connected_account: BrokerAccount,
) -> None:
    """FR-KITE-10."""
    assert authenticated_client.post("/api/v1/kite/disconnect").status_code == 204

    session.refresh(connected_account)
    assert connected_account.access_token_enc is None
    assert token_store.load_credentials(connected_account) == (
        "test_api_key",
        "test_api_secret",
    )
