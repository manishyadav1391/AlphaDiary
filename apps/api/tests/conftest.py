from __future__ import annotations

import datetime as dt
import json
import uuid
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from sqlalchemy import Connection
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import engine, get_session
from app.main import app
from app.models import AppUser, BrokerAccount
from app.services import auth_service, token_store

FIXTURES = Path(__file__).parent / "fixtures"

TEST_PASSWORD = "correct-horse-battery-staple"
TEST_EMAIL = "owner@example.test"


@pytest.fixture(autouse=True)
def test_encryption_key() -> Iterator[None]:
    """Give the suite its own Fernet key.

    Tests must never depend on the real APP_ENCRYPTION_KEY, and must never
    write ciphertext the real key could read.
    """
    settings = get_settings()
    original = settings.app_encryption_key
    settings.app_encryption_key = type(original)(Fernet.generate_key().decode())
    try:
        yield
    finally:
        settings.app_encryption_key = original


@pytest.fixture
def connection() -> Iterator[Connection]:
    """One connection with an outer transaction that is always rolled back.

    The code under test commits (a sync writes its log before doing the work),
    so isolation cannot come from "never commit". It comes from the commits
    landing on a savepoint inside a transaction the test discards.
    """
    conn = engine.connect()
    transaction = conn.begin()
    try:
        yield conn
    finally:
        transaction.rollback()
        conn.close()


@pytest.fixture
def session(connection: Connection) -> Iterator[Session]:
    db = Session(
        bind=connection,
        join_transaction_mode="create_savepoint",
        expire_on_commit=False,
    )
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def client(session: Session) -> Iterator[TestClient]:
    """A TestClient sharing the test's transaction."""

    def override_get_session() -> Iterator[Session]:
        yield session

    app.dependency_overrides[get_session] = override_get_session
    try:
        # https, because the session cookie is Secure whenever PUBLIC_BASE_URL
        # is https. Over plain http the client would silently drop it, and
        # every authenticated test would fail for the wrong reason.
        with TestClient(app, base_url="https://testserver") as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()


@pytest.fixture
def user(session: Session) -> AppUser:
    return auth_service.create_user(session, TEST_EMAIL, TEST_PASSWORD)


@pytest.fixture
def authenticated_client(client: TestClient, user: AppUser) -> TestClient:
    """A client carrying a valid session cookie (FR-AUTH-03)."""
    response = client.post(
        "/api/v1/auth/login", json={"email": user.email, "password": TEST_PASSWORD}
    )
    assert response.status_code == 200, response.text
    return client


@pytest.fixture
def account(session: Session, user: AppUser) -> BrokerAccount:
    return token_store.save_credentials(session, user, "test_api_key", "test_api_secret")


# ----------------------------------------------------------------- fixtures


def load_fixture(name: str) -> list[dict[str, Any]]:
    """Read a saved Kite payload. The `_` keys are documentation, not data."""
    payload = json.loads((FIXTURES / name).read_text(encoding="utf-8"))
    return list(payload["data"])


@pytest.fixture
def kite_trades() -> list[dict[str, Any]]:
    return load_fixture("kite_trades_sample.json")


@pytest.fixture
def kite_orders() -> list[dict[str, Any]]:
    return load_fixture("kite_orders_sample.json")


class FakeKite:
    """A stand-in for `KiteClient` implementing `KiteGateway`.

    Counts calls so tests can assert that a second sync still talks to Kite
    and still stores nothing new, rather than short-circuiting.
    """

    def __init__(
        self,
        trades: list[dict[str, Any]] | None = None,
        orders: list[dict[str, Any]] | None = None,
        *,
        profile_raises: Exception | None = None,
    ) -> None:
        self._trades = trades or []
        self._orders = orders or []
        self._profile_raises = profile_raises
        self.calls: dict[str, int] = {}

    def _count(self, name: str) -> None:
        self.calls[name] = self.calls.get(name, 0) + 1

    def profile(self) -> dict[str, Any]:
        self._count("profile")
        if self._profile_raises is not None:
            raise self._profile_raises
        return {"user_id": "XX0000", "user_name": "Owner"}

    def orders(self) -> list[dict[str, Any]]:
        self._count("orders")
        return [dict(row) for row in self._orders]

    def trades(self) -> list[dict[str, Any]]:
        self._count("trades")
        return [dict(row) for row in self._trades]

    def positions(self) -> dict[str, Any]:
        self._count("positions")
        return {"net": [], "day": []}

    def holdings(self) -> list[dict[str, Any]]:
        self._count("holdings")
        return []


@pytest.fixture
def connected_account(session: Session, account: BrokerAccount) -> BrokerAccount:
    """An account holding a token that has not yet reached 06:00 IST."""
    from app.services.kite_client import KiteSession

    token_store.store_token(
        session,
        account,
        KiteSession(
            access_token="test-access-token",
            kite_user_id="XX0000",
            login_time=dt.datetime.now(dt.UTC),
        ),
    )
    return account


@pytest.fixture
def account_id(account: BrokerAccount) -> uuid.UUID:
    return account.id
