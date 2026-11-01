from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


def test_health_reports_ok_when_the_database_answers() -> None:
    with TestClient(app) as client:
        response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}


def test_unknown_route_uses_the_error_envelope() -> None:
    with TestClient(app) as client:
        response = client.get("/api/v1/nope")
    assert response.status_code == 404
    body = response.json()
    assert set(body["error"]) == {"code", "message", "details"}
