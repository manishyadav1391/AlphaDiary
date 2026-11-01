"""Daily playbook endpoints (FR-PB)."""

from __future__ import annotations

from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

DAY = "2026-10-28"


def test_an_empty_day_reads_as_nothing_done(authenticated_client: TestClient) -> None:
    body = authenticated_client.get(f"/api/v1/playbook/{DAY}").json()

    assert body["trade_date"] == DAY
    assert body["plan"] is None
    assert body["review"] is None
    assert body["plan_done"] is False
    assert body["review_done"] is False


def test_the_pre_market_plan_is_saved(authenticated_client: TestClient) -> None:
    """FR-PB-02."""
    response = authenticated_client.put(
        f"/api/v1/playbook/{DAY}/plan",
        json={
            "bias": "bullish",
            "key_levels": "24,500 support",
            "events": "RBI policy",
            "max_loss": "2000.00",
            "max_trades": 6,
            "max_risk_per_trade": "500.00",
            "checklist": {"checked_news": True, "marked_levels": False},
        },
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["plan_done"] is True
    assert body["plan"]["bias"] == "bullish"
    assert body["plan"]["max_trades"] == 6
    assert body["plan"]["checklist"] == {"checked_news": True, "marked_levels": False}


def test_the_post_market_review_is_saved(authenticated_client: TestClient) -> None:
    """FR-PB-03."""
    response = authenticated_client.put(
        f"/api/v1/playbook/{DAY}/review",
        json={
            "discipline_rating": 4,
            "emotion": "calm",
            "went_well": "Waited for the setup.",
            "to_improve": "Sized too small.",
            "summary": "A steady day.",
        },
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["review_done"] is True
    assert body["review"]["discipline_rating"] == 4
    assert body["review"]["emotion"] == "calm"


def test_money_in_the_plan_is_a_plain_decimal_string(
    authenticated_client: TestClient,
) -> None:
    authenticated_client.put(f"/api/v1/playbook/{DAY}/plan", json={"max_loss": "2000.00"})

    body = authenticated_client.get(f"/api/v1/playbook/{DAY}").json()

    assert isinstance(body["plan"]["max_loss"], str)
    assert "₹" not in body["plan"]["max_loss"]
    assert Decimal(body["plan"]["max_loss"]) == Decimal("2000.00")


def test_saving_again_updates_rather_than_duplicating(
    authenticated_client: TestClient,
) -> None:
    """Date-keyed upsert, which is why the verb is PUT."""
    authenticated_client.put(f"/api/v1/playbook/{DAY}/plan", json={"bias": "bullish"})

    body = authenticated_client.put(f"/api/v1/playbook/{DAY}/plan", json={"bias": "bearish"}).json()

    assert body["plan"]["bias"] == "bearish"


def test_a_partial_save_leaves_the_rest_alone(authenticated_client: TestClient) -> None:
    authenticated_client.put(
        f"/api/v1/playbook/{DAY}/plan", json={"bias": "neutral", "max_trades": 5}
    )

    authenticated_client.put(f"/api/v1/playbook/{DAY}/plan", json={"max_trades": 3})

    body = authenticated_client.get(f"/api/v1/playbook/{DAY}").json()
    assert body["plan"]["bias"] == "neutral"
    assert body["plan"]["max_trades"] == 3


def test_both_halves_can_be_written_in_one_call(
    authenticated_client: TestClient,
) -> None:
    response = authenticated_client.put(
        f"/api/v1/playbook/{DAY}",
        json={
            "plan": {"bias": "neutral", "max_trades": 4},
            "review": {"discipline_rating": 5},
        },
    )

    body = response.json()
    assert body["plan_done"] is True
    assert body["review_done"] is True


def test_todays_playbook_is_reachable_without_a_date(
    authenticated_client: TestClient,
) -> None:
    body = authenticated_client.get("/api/v1/playbook/daily").json()

    assert len(body["trade_date"]) == 10
    assert body["actual"]["trades_taken"] == 0


def test_daily_is_not_read_as_a_date(authenticated_client: TestClient) -> None:
    """Route ordering: /playbook/daily must not fall through to /{date}."""
    response = authenticated_client.get("/api/v1/playbook/daily")

    assert response.status_code == 200


def test_a_malformed_date_is_refused(authenticated_client: TestClient) -> None:
    response = authenticated_client.get("/api/v1/playbook/not-a-date")

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_date"


@pytest.mark.parametrize("rating", [0, 6])
def test_a_discipline_rating_outside_one_to_five_is_refused(
    authenticated_client: TestClient, rating: int
) -> None:
    response = authenticated_client.put(
        f"/api/v1/playbook/{DAY}/review", json={"discipline_rating": rating}
    )

    assert response.status_code == 422


def test_an_unknown_bias_is_refused(authenticated_client: TestClient) -> None:
    response = authenticated_client.put(f"/api/v1/playbook/{DAY}/plan", json={"bias": "sideways"})

    assert response.status_code == 422


# -------------------------------------------------------- plan versus actual


def test_plan_versus_actual_reads_the_days_trading(
    authenticated_client: TestClient, imported_trades: object
) -> None:
    """FR-PB-04, computed from daily_summary."""
    body = authenticated_client.get(f"/api/v1/playbook/{DAY}").json()

    assert body["actual"]["trades_taken"] == 4
    assert Decimal(body["actual"]["net_pnl"]) != Decimal("0")


def test_breaking_the_trade_limit_is_reported(
    authenticated_client: TestClient, imported_trades: object
) -> None:
    body = authenticated_client.put(f"/api/v1/playbook/{DAY}/plan", json={"max_trades": 2}).json()

    assert body["actual"]["trades_taken"] == 4
    assert body["actual"]["trades_limit_broken"] is True


def test_staying_inside_the_trade_limit_is_not_reported_as_broken(
    authenticated_client: TestClient, imported_trades: object
) -> None:
    body = authenticated_client.put(f"/api/v1/playbook/{DAY}/plan", json={"max_trades": 10}).json()

    assert body["actual"]["trades_limit_broken"] is False


def test_breaking_the_loss_limit_is_reported(
    authenticated_client: TestClient, imported_trades: object
) -> None:
    """28 Oct is a losing day in the fixture, so a tight limit is broken."""
    body = authenticated_client.put(
        f"/api/v1/playbook/{DAY}/plan", json={"max_loss": "100.00"}
    ).json()

    assert Decimal(body["actual"]["net_pnl"]) < Decimal("0")
    assert body["actual"]["loss_limit_broken"] is True


def test_a_loss_limit_is_compared_against_its_magnitude(
    authenticated_client: TestClient, imported_trades: object
) -> None:
    """A limit of 100,000 is not broken by a loss of a few hundred."""
    body = authenticated_client.put(
        f"/api/v1/playbook/{DAY}/plan", json={"max_loss": "100000.00"}
    ).json()

    assert body["actual"]["loss_limit_broken"] is False


# -------------------------------------------------------------------- auth


def _call(client: TestClient, method: str, path: str):
    """GET takes no body; the other verbs here do."""
    if method == "get":
        return client.get(path)
    return getattr(client, method)(path, json={})


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("get", "/api/v1/playbook/daily"),
        ("get", f"/api/v1/playbook/{DAY}"),
        ("put", f"/api/v1/playbook/{DAY}/plan"),
        ("put", f"/api/v1/playbook/{DAY}/review"),
    ],
)
def test_every_playbook_route_needs_a_session(client: TestClient, method: str, path: str) -> None:
    response = _call(client, method, path)

    assert response.status_code == 401
