"""Metric definitions (SRS 7.4).

Closed groups only, and every outcome is decided by **net** P&L, not gross.
Open groups carry no outcome and are excluded from every statistic
(FR-MATCH-05, golden scenario S7).

Everything here is a pure function over a list of values, so the formulas can
be checked against the worked example in SRS 7.4 without a database.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal

ZERO = Decimal("0")
MONEY = Decimal("0.01")
RATIO = Decimal("0.0001")

# Below this many closed trades the numbers are not worth much, and the UI
# says so rather than implying confidence (DESIGN.md 10).
LOW_SAMPLE_TRADES = 20


def round_money(value: Decimal) -> Decimal:
    return value.quantize(MONEY, rounding=ROUND_HALF_UP)


def round_ratio(value: Decimal) -> Decimal:
    return value.quantize(RATIO, rounding=ROUND_HALF_UP)


@dataclass
class Kpis:
    trades: int = 0
    wins: int = 0
    losses: int = 0
    breakeven: int = 0
    gross_pnl: Decimal = ZERO
    charges: Decimal = ZERO
    net_pnl: Decimal = ZERO
    win_rate: Decimal | None = None
    avg_win: Decimal | None = None
    avg_loss: Decimal | None = None
    largest_win: Decimal | None = None
    largest_loss: Decimal | None = None
    # Null rather than zero when there are no losing trades: dividing by zero
    # is not a profit factor of infinity we can put in a number column.
    profit_factor: Decimal | None = None
    expectancy: Decimal | None = None
    avg_r: Decimal | None = None
    max_drawdown: Decimal = ZERO
    longest_losing_streak: int = 0
    low_sample: bool = True


@dataclass
class DayPoint:
    trade_date: dt.date
    net_pnl: Decimal
    trades_count: int


@dataclass
class CurvePoint:
    label: str
    net_pnl: Decimal
    cumulative: Decimal


@dataclass
class Streaks:
    longest_losing: int = 0
    longest_winning: int = 0
    current: int = 0
    current_is_losing: bool = False


@dataclass
class GroupValue:
    """The slice of a trade group the metrics need."""

    net_pnl: Decimal
    gross_pnl: Decimal = ZERO
    charges_total: Decimal = ZERO
    r_multiple: Decimal | None = None
    trade_date: dt.date | None = None
    extras: dict = field(default_factory=dict)


def max_drawdown(nets: list[Decimal]) -> Decimal:
    """Largest fall from a running peak of the cumulative curve.

    The peak starts at 0, so a run of losses from the very first trade counts
    as drawdown rather than being measured from the first value (SRS 7.4).
    """
    peak = ZERO
    cumulative = ZERO
    worst = ZERO
    for net in nets:
        cumulative += net
        peak = max(peak, cumulative)
        worst = max(worst, peak - cumulative)
    return round_money(worst)


def streaks(nets: list[Decimal]) -> Streaks:
    result = Streaks()
    losing = winning = 0
    for net in nets:
        if net < ZERO:
            losing += 1
            winning = 0
        elif net > ZERO:
            winning += 1
            losing = 0
        else:
            losing = winning = 0
        result.longest_losing = max(result.longest_losing, losing)
        result.longest_winning = max(result.longest_winning, winning)
    result.current = losing or winning
    result.current_is_losing = losing > 0
    return result


def compute_kpis(groups: list[GroupValue]) -> Kpis:
    """Every KPI card on the dashboard (FR-DASH-02, SRS 7.4)."""
    kpis = Kpis(trades=len(groups))
    if not groups:
        return kpis

    nets = [group.net_pnl for group in groups]
    wins = [net for net in nets if net > ZERO]
    losses = [net for net in nets if net < ZERO]

    kpis.wins = len(wins)
    kpis.losses = len(losses)
    kpis.breakeven = len(nets) - len(wins) - len(losses)
    kpis.gross_pnl = round_money(sum((g.gross_pnl for g in groups), start=ZERO))
    kpis.charges = round_money(sum((g.charges_total for g in groups), start=ZERO))
    kpis.net_pnl = round_money(sum(nets, start=ZERO))

    kpis.win_rate = round_ratio(Decimal(kpis.wins) / Decimal(kpis.trades))
    kpis.expectancy = round_money(sum(nets, start=ZERO) / Decimal(kpis.trades))
    kpis.largest_win = round_money(max(wins)) if wins else None
    kpis.largest_loss = round_money(min(losses)) if losses else None

    if wins:
        kpis.avg_win = round_money(sum(wins, start=ZERO) / Decimal(len(wins)))
    if losses:
        total_loss = abs(sum(losses, start=ZERO))
        kpis.avg_loss = round_money(total_loss / Decimal(len(losses)))
        if total_loss > ZERO:
            kpis.profit_factor = round_ratio(sum(wins, start=ZERO) / total_loss)

    # Only trades that had a stop-loss have an R (FR-JRN-02).
    r_values = [g.r_multiple for g in groups if g.r_multiple is not None]
    if r_values:
        kpis.avg_r = round_ratio(sum(r_values, start=ZERO) / Decimal(len(r_values)))

    kpis.max_drawdown = max_drawdown(nets)
    kpis.longest_losing_streak = streaks(nets).longest_losing
    kpis.low_sample = kpis.trades < LOW_SAMPLE_TRADES
    return kpis


def equity_curve_by_day(days: list[DayPoint]) -> list[CurvePoint]:
    """Cumulative net P&L by day, starting at 0 (SRS 7.4)."""
    cumulative = ZERO
    points: list[CurvePoint] = []
    for day in sorted(days, key=lambda item: item.trade_date):
        cumulative += day.net_pnl
        points.append(
            CurvePoint(
                label=day.trade_date.isoformat(),
                net_pnl=round_money(day.net_pnl),
                cumulative=round_money(cumulative),
            )
        )
    return points


def equity_curve_by_trade(groups: list[tuple[str, Decimal]]) -> list[CurvePoint]:
    cumulative = ZERO
    points: list[CurvePoint] = []
    for label, net in groups:
        cumulative += net
        points.append(
            CurvePoint(label=label, net_pnl=round_money(net), cumulative=round_money(cumulative))
        )
    return points


def green_day_rate(days: list[DayPoint]) -> Decimal | None:
    """Days with net above zero, over days that had at least one trade."""
    traded = [day for day in days if day.trades_count > 0]
    if not traded:
        return None
    green = sum(1 for day in traded if day.net_pnl > ZERO)
    return round_ratio(Decimal(green) / Decimal(len(traded)))
