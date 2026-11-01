"""Metric definitions (SRS 7.4).

The worked example in 7.4 is the contract: trade nets +200, -50, +100, -150,
0 give 2 wins, 2 losses, 1 breakeven, win rate 40%, average win 150, average
loss 100, profit factor 1.5, expectancy 20, and max drawdown 150.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest

from app.services import analytics

WORKED_EXAMPLE = [
    Decimal("200"),
    Decimal("-50"),
    Decimal("100"),
    Decimal("-150"),
    Decimal("0"),
]


def values(nets: list[Decimal], **extra) -> list[analytics.GroupValue]:
    return [analytics.GroupValue(net_pnl=net, **extra) for net in nets]


def test_the_srs_worked_example() -> None:
    kpis = analytics.compute_kpis(values(WORKED_EXAMPLE))

    assert kpis.trades == 5
    assert (kpis.wins, kpis.losses, kpis.breakeven) == (2, 2, 1)
    assert kpis.win_rate == Decimal("0.4")
    assert kpis.avg_win == Decimal("150.00")
    assert kpis.avg_loss == Decimal("100.00")
    assert kpis.profit_factor == Decimal("1.5")
    assert kpis.expectancy == Decimal("20.00")
    assert kpis.max_drawdown == Decimal("150.00")


def test_expectancy_matches_the_identity_in_the_srs() -> None:
    """expectancy == win% x avg win - loss% x avg loss."""
    kpis = analytics.compute_kpis(values(WORKED_EXAMPLE))

    identity = Decimal("0.4") * kpis.avg_win - Decimal("0.4") * kpis.avg_loss
    assert kpis.expectancy == identity.quantize(Decimal("0.01"))


def test_max_drawdown_measures_from_a_peak_that_starts_at_zero() -> None:
    """A losing run from the first trade is drawdown, not a flat line."""
    assert analytics.max_drawdown([Decimal("-100"), Decimal("-50")]) == Decimal("150.00")
    # Curve 200, 150, 250, 100, 100: peak 250, trough 100.
    assert analytics.max_drawdown(WORKED_EXAMPLE) == Decimal("150.00")


def test_profit_factor_is_null_when_nothing_lost() -> None:
    """Dividing by zero is not a profit factor; the UI shows a dash."""
    kpis = analytics.compute_kpis(values([Decimal("10"), Decimal("20")]))

    assert kpis.profit_factor is None
    assert kpis.avg_loss is None
    assert kpis.largest_loss is None


def test_an_empty_range_returns_zeroes_not_errors() -> None:
    kpis = analytics.compute_kpis([])

    assert kpis.trades == 0
    assert kpis.net_pnl == Decimal("0")
    assert kpis.win_rate is None
    assert kpis.low_sample is True


def test_breakeven_is_a_third_outcome_not_a_loss() -> None:
    kpis = analytics.compute_kpis(values([Decimal("0"), Decimal("0")]))

    assert (kpis.wins, kpis.losses, kpis.breakeven) == (0, 0, 2)
    assert kpis.win_rate == Decimal("0")


def test_average_r_uses_only_trades_that_had_a_stop_loss() -> None:
    """FR-JRN-02: without a stop there is no R, and the trade is excluded."""
    groups = [
        analytics.GroupValue(net_pnl=Decimal("100"), r_multiple=Decimal("2")),
        analytics.GroupValue(net_pnl=Decimal("-50"), r_multiple=Decimal("-1")),
        analytics.GroupValue(net_pnl=Decimal("300"), r_multiple=None),
    ]

    kpis = analytics.compute_kpis(groups)

    # Mean of 2 and -1, not of 2, -1 and 0.
    assert kpis.avg_r == Decimal("0.5")


def test_low_sample_flips_at_twenty_closed_trades() -> None:
    assert analytics.compute_kpis(values([Decimal("1")] * 19)).low_sample is True
    assert analytics.compute_kpis(values([Decimal("1")] * 20)).low_sample is False


def test_longest_losing_streak() -> None:
    nets = [Decimal(n) for n in ("-1", "-1", "1", "-1", "-1", "-1", "1")]

    assert analytics.streaks(nets).longest_losing == 3
    assert analytics.streaks(nets).longest_winning == 1


def test_a_breakeven_trade_ends_a_streak() -> None:
    nets = [Decimal("-1"), Decimal("0"), Decimal("-1")]

    assert analytics.streaks(nets).longest_losing == 1


def test_equity_curve_accumulates_from_zero() -> None:
    days = [
        analytics.DayPoint(dt.date(2026, 11, 2), Decimal("200"), 2),
        analytics.DayPoint(dt.date(2026, 11, 3), Decimal("-50"), 1),
    ]

    points = analytics.equity_curve_by_day(days)

    assert [point.cumulative for point in points] == [Decimal("200.00"), Decimal("150.00")]


def test_equity_curve_sorts_by_date_regardless_of_input_order() -> None:
    days = [
        analytics.DayPoint(dt.date(2026, 11, 3), Decimal("-50"), 1),
        analytics.DayPoint(dt.date(2026, 11, 2), Decimal("200"), 2),
    ]

    points = analytics.equity_curve_by_day(days)

    assert points[0].label == "2026-11-02"


@pytest.mark.parametrize(
    ("nets", "expected"),
    [([Decimal("1"), Decimal("-1")], Decimal("0.5")), ([Decimal("-1")], Decimal("0"))],
)
def test_green_day_rate(nets: list[Decimal], expected: Decimal) -> None:
    days = [
        analytics.DayPoint(dt.date(2026, 11, 2) + dt.timedelta(days=i), net, 1)
        for i, net in enumerate(nets)
    ]

    assert analytics.green_day_rate(days) == expected


def test_days_without_trades_do_not_count_against_the_green_rate() -> None:
    days = [
        analytics.DayPoint(dt.date(2026, 11, 2), Decimal("100"), 1),
        analytics.DayPoint(dt.date(2026, 11, 3), Decimal("0"), 0),
    ]

    assert analytics.green_day_rate(days) == Decimal("1")
