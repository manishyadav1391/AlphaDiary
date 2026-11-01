"""Dashboard endpoints (FR-DASH)."""

from __future__ import annotations

from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

RANGE = {"date_from": "2026-10-01", "date_to": "2026-10-31"}


def summary(client: TestClient, **params) -> dict:
    response = client.get("/api/v1/dashboard/summary", params={**RANGE, **params})
    assert response.status_code == 200, response.text
    return response.json()


# ----------------------------------------------------------------- summary


def test_summary_reports_every_kpi_card(
    authenticated_client: TestClient, imported_trades: object
) -> None:
    """FR-DASH-02."""
    body = summary(authenticated_client)

    for field in (
        "trades",
        "wins",
        "losses",
        "breakeven",
        "gross_pnl",
        "charges",
        "net_pnl",
        "win_rate",
        "profit_factor",
        "expectancy",
        "max_drawdown",
        "largest_win",
        "largest_loss",
        "low_sample",
    ):
        assert field in body


def test_summary_money_is_a_plain_decimal_string(
    authenticated_client: TestClient, imported_trades: object
) -> None:
    body = summary(authenticated_client)

    for field in ("gross_pnl", "charges", "net_pnl", "max_drawdown"):
        assert isinstance(body[field], str)
        assert "₹" not in body[field]
        Decimal(body[field])


def test_net_is_gross_less_charges(
    authenticated_client: TestClient, imported_trades: object
) -> None:
    body = summary(authenticated_client)

    assert Decimal(body["net_pnl"]) == Decimal(body["gross_pnl"]) - Decimal(body["charges"])


def test_outcomes_add_up_to_the_trade_count(
    authenticated_client: TestClient, imported_trades: object
) -> None:
    body = summary(authenticated_client)

    assert body["wins"] + body["losses"] + body["breakeven"] == body["trades"]


def test_a_small_sample_is_flagged(
    authenticated_client: TestClient, imported_trades: object
) -> None:
    """DESIGN.md 10: under 20 trades the UI warns rather than implying trust."""
    assert summary(authenticated_client)["low_sample"] is True


def test_an_empty_range_is_zeroes_not_an_error(
    authenticated_client: TestClient, imported_trades: object
) -> None:
    body = summary(authenticated_client, date_from="2020-01-01", date_to="2020-01-31")

    assert body["trades"] == 0
    assert Decimal(body["net_pnl"]) == Decimal("0")
    assert body["win_rate"] is None
    assert body["profit_factor"] is None


def test_a_backwards_range_is_refused(
    authenticated_client: TestClient, imported_trades: object
) -> None:
    response = authenticated_client.get(
        "/api/v1/dashboard/summary",
        params={"date_from": "2026-10-31", "date_to": "2026-10-01"},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_range"


def test_summary_defaults_to_the_current_month(
    authenticated_client: TestClient, imported_trades: object
) -> None:
    """FR-DASH-01."""
    body = authenticated_client.get("/api/v1/dashboard/summary").json()

    assert body["date_from"].endswith("-01")
    assert body["date_from"][:7] == body["date_to"][:7]


# ----------------------------------------------------------------- heatmap


def test_heatmap_covers_every_day_of_the_month(
    authenticated_client: TestClient, imported_trades: object
) -> None:
    """FR-DASH-04."""
    body = authenticated_client.get("/api/v1/dashboard/heatmap", params={"month": "2026-10"}).json()

    assert body["month"] == "2026-10"
    assert len(body["days"]) == 31
    assert body["days"][0]["trade_date"] == "2026-10-01"
    assert body["days"][-1]["trade_date"] == "2026-10-31"


def test_heatmap_day_cells_carry_net_and_count(
    authenticated_client: TestClient, imported_trades: object
) -> None:
    body = authenticated_client.get("/api/v1/dashboard/heatmap", params={"month": "2026-10"}).json()

    traded = [day for day in body["days"] if day["trades_count"] > 0]
    assert len(traded) == 4
    assert {day["trade_date"] for day in traded} == {
        "2026-10-27",
        "2026-10-28",
        "2026-10-29",
        "2026-10-30",
    }


def test_heatmap_totals_match_the_sum_of_its_days(
    authenticated_client: TestClient, imported_trades: object
) -> None:
    body = authenticated_client.get("/api/v1/dashboard/heatmap", params={"month": "2026-10"}).json()

    assert Decimal(body["net_pnl"]) == sum(Decimal(day["net_pnl"]) for day in body["days"])
    assert body["trades_count"] == sum(day["trades_count"] for day in body["days"])


def test_heatmap_reports_the_largest_absolute_day(
    authenticated_client: TestClient, imported_trades: object
) -> None:
    """The client scales colour intensity against it (DESIGN.md 5)."""
    body = authenticated_client.get("/api/v1/dashboard/heatmap", params={"month": "2026-10"}).json()

    assert Decimal(body["max_abs_day"]) == max(abs(Decimal(day["net_pnl"])) for day in body["days"])


def test_heatmap_weekly_totals_cover_every_day(
    authenticated_client: TestClient, imported_trades: object
) -> None:
    body = authenticated_client.get("/api/v1/dashboard/heatmap", params={"month": "2026-10"}).json()

    assert body["weeks"]
    assert sum(week["trades_count"] for week in body["weeks"]) == body["trades_count"]


def test_heatmap_defaults_to_this_month(
    authenticated_client: TestClient, imported_trades: object
) -> None:
    body = authenticated_client.get("/api/v1/dashboard/heatmap").json()

    assert len(body["month"]) == 7


def test_a_malformed_month_is_refused(authenticated_client: TestClient) -> None:
    response = authenticated_client.get("/api/v1/dashboard/heatmap", params={"month": "October"})

    assert response.status_code == 422


# ------------------------------------------------------------ equity curve


def test_equity_curve_accumulates_to_the_period_net(
    authenticated_client: TestClient, imported_trades: object
) -> None:
    """FR-DASH-03."""
    curve = authenticated_client.get("/api/v1/dashboard/equity-curve", params=RANGE).json()
    totals = summary(authenticated_client)

    assert curve["points"]
    assert Decimal(curve["points"][-1]["cumulative"]) == Decimal(curve["net_pnl"])
    assert Decimal(curve["net_pnl"]) == Decimal(totals["net_pnl"])


def test_equity_curve_by_day_has_one_point_per_traded_day(
    authenticated_client: TestClient, imported_trades: object
) -> None:
    curve = authenticated_client.get(
        "/api/v1/dashboard/equity-curve", params={**RANGE, "by": "day"}
    ).json()

    assert len(curve["points"]) == 4
    labels = [point["label"] for point in curve["points"]]
    assert labels == sorted(labels)


def test_equity_curve_by_trade_has_one_point_per_closed_trade(
    authenticated_client: TestClient, imported_trades: object
) -> None:
    curve = authenticated_client.get(
        "/api/v1/dashboard/equity-curve", params={**RANGE, "by": "trade"}
    ).json()
    trades = authenticated_client.get(
        "/api/v1/trades", params={"status": "closed", "limit": 200, "intraday_only": False}
    ).json()

    assert len(curve["points"]) == trades["totals"]["trades"]


def test_an_empty_curve_is_an_empty_list_not_an_error(
    authenticated_client: TestClient, imported_trades: object
) -> None:
    curve = authenticated_client.get(
        "/api/v1/dashboard/equity-curve",
        params={"date_from": "2020-01-01", "date_to": "2020-01-31"},
    ).json()

    assert curve["points"] == []
    assert Decimal(curve["net_pnl"]) == Decimal("0")


# -------------------------------------------------------------------- auth


@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/dashboard/summary",
        "/api/v1/dashboard/heatmap",
        "/api/v1/dashboard/equity-curve",
    ],
)
def test_every_dashboard_route_needs_a_session(client: TestClient, path: str) -> None:
    assert client.get(path).status_code == 401
