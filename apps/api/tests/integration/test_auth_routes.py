"""Route-level authentication (FR-AUTH-03, FR-AUTH-05)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.models import AppUser
from tests.conftest import TEST_PASSWORD

PROTECTED = [
    ("get", "/api/v1/kite/login-url"),
    ("get", "/api/v1/kite/status"),
    ("post", "/api/v1/kite/disconnect"),
    ("post", "/api/v1/sync/run"),
    ("get", "/api/v1/sync/logs"),
    ("get", "/api/v1/sync/status"),
    ("get", "/api/v1/auth/me"),
]

PUBLIC = [
    ("get", "/api/v1/health"),
    ("get", "/api/v1/kite/callback"),
]


@pytest.mark.parametrize(("method", "path"), PROTECTED)
def test_protected_routes_return_401_without_a_session(
    client: TestClient, method: str, path: str
) -> None:
    response = getattr(client, method)(path)

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"


@pytest.mark.parametrize(("method", "path"), PUBLIC)
def test_public_routes_are_reachable_without_a_session(
    client: TestClient, method: str, path: str
) -> None:
    response = getattr(client, method)(path, follow_redirects=False)

    assert response.status_code != 401


def test_login_sets_a_hardened_session_cookie(client: TestClient, user: AppUser) -> None:
    """FR-AUTH-03."""
    settings = get_settings()

    response = client.post(
        "/api/v1/auth/login", json={"email": user.email, "password": TEST_PASSWORD}
    )

    assert response.status_code == 200
    assert response.json()["email"] == user.email

    raw_cookie = response.headers["set-cookie"]
    assert settings.session_cookie_name in raw_cookie
    assert "HttpOnly" in raw_cookie
    assert "SameSite=lax" in raw_cookie
    # Secure follows the public URL: on plain http the browser would drop it.
    assert ("Secure" in raw_cookie) is settings.cookie_secure


def test_the_session_cookie_never_contains_the_password(client: TestClient, user: AppUser) -> None:
    response = client.post(
        "/api/v1/auth/login", json={"email": user.email, "password": TEST_PASSWORD}
    )

    assert TEST_PASSWORD not in response.headers["set-cookie"]
    assert TEST_PASSWORD not in response.text


def test_wrong_password_returns_401_without_saying_which_half_was_wrong(
    client: TestClient, user: AppUser
) -> None:
    response = client.post("/api/v1/auth/login", json={"email": user.email, "password": "wrong"})

    assert response.status_code == 401
    assert response.json()["error"]["message"] == "Email or password is wrong."


def test_six_wrong_passwords_return_429(client: TestClient, user: AppUser) -> None:
    """FR-AUTH-04."""
    for _ in range(get_settings().login_max_attempts):
        client.post("/api/v1/auth/login", json={"email": user.email, "password": "wrong"})

    response = client.post(
        "/api/v1/auth/login", json={"email": user.email, "password": TEST_PASSWORD}
    )

    assert response.status_code == 429
    assert response.json()["error"]["code"] == "too_many_attempts"


def test_me_returns_the_signed_in_owner(authenticated_client: TestClient) -> None:
    response = authenticated_client.get("/api/v1/auth/me")

    assert response.status_code == 200
    assert response.json()["email"] == "owner@example.test"


def test_logout_clears_the_cookie_and_the_server_session(
    authenticated_client: TestClient,
) -> None:
    assert authenticated_client.post("/api/v1/auth/logout").status_code == 204

    assert authenticated_client.get("/api/v1/auth/me").status_code == 401


def test_a_forged_cookie_is_rejected(client: TestClient, user: AppUser) -> None:
    client.cookies.set(get_settings().session_cookie_name, "made-up-session-id")

    assert client.get("/api/v1/auth/me").status_code == 401
