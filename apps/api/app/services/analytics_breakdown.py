"""Analytics breakdowns (FR-AN).

The metric maths already exists in `analytics.py` (SRS 7.4). This module only
decides which trades fall into which bucket, then hands each bucket to
`analytics.compute_kpis`, so a strategy's win rate and the dashboard's win rate
can never drift apart.

Every breakdown respects the same filters as the trade log, per the preamble
to SRS 5.11.
"""

from __future__ import annotations

import datetime as dt
from collections import defaultdict
from dataclasses import dataclass, field
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Strategy, Tag, TradeGroup, TradeJournal, TradeTag
from app.services import analytics
from app.services import journal as journal_service
from app.timezone import IST

ZERO = Decimal("0")

# FR-AN-03. Edges in seconds; the label is what the UI shows. "Multi-day" is
# anything not closed on its own date, so it is decided by the flag, not time.
DURATION_BUCKETS: list[tuple[str, int, int]] = [
    ("Under 5m", 0, 5 * 60),
    ("5–30m", 5 * 60, 30 * 60),
    ("30–120m", 30 * 60, 120 * 60),
    ("Over 120m", 120 * 60, 10**9),
]

WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


@dataclass
class Filters:
    date_from: dt.date
    date_to: dt.date
    asset_class: list[str] = field(default_factory=list)
    product: list[str] = field(default_factory=list)
    intraday_only: bool = False


@dataclass
class LoadedTrade:
    """A closed group plus everything the breakdowns need about it."""

    group: TradeGroup
    journal: TradeJournal | None
    value: analytics.GroupValue


@dataclass
class Bucket:
    """One row of a breakdown: a label and the KPIs for its trades."""

    label: str
    kpis: analytics.Kpis


def load(session: Session, filters: Filters) -> list[LoadedTrade]:
    """Closed groups in range, in the order they closed."""
    statement = select(TradeGroup).where(
        TradeGroup.status == "closed",
        TradeGroup.trade_date >= filters.date_from,
        TradeGroup.trade_date <= filters.date_to,
    )
    if filters.asset_class:
        statement = statement.where(TradeGroup.asset_class.in_(filters.asset_class))
    if filters.product:
        statement = statement.where(TradeGroup.product.in_(filters.product))
    if filters.intraday_only:
        statement = statement.where(TradeGroup.is_intraday.is_(True))

    groups = list(
        session.execute(
            statement.order_by(TradeGroup.trade_date, TradeGroup.closed_at, TradeGroup.id)
        ).scalars()
    )
    journals = journal_service.journals_for_groups(session, [group.group_key for group in groups])

    loaded: list[LoadedTrade] = []
    for group in groups:
        journal = journals.get(group.group_key)
        loaded.append(
            LoadedTrade(
                group=group,
                journal=journal,
                value=analytics.GroupValue(
                    net_pnl=group.net_pnl,
                    gross_pnl=group.gross_pnl,
                    charges_total=group.charges_total,
                    r_multiple=journal_service.derive(group, journal).r_multiple,
                    trade_date=group.trade_date,
                ),
            )
        )
    return loaded


def _bucketed(buckets: dict[str, list[analytics.GroupValue]], order: list[str]) -> list[Bucket]:
    return [
        Bucket(label=label, kpis=analytics.compute_kpis(buckets[label]))
        for label in order
        if buckets.get(label)
    ]


# ------------------------------------------------------------ FR-AN-01


def by_strategy(session: Session, trades: list[LoadedTrade]) -> list[Bucket]:
    """Net P&L and the full KPI set per named setup."""
    names = {row.id: row.name for row in session.execute(select(Strategy)).scalars()}

    buckets: dict[str, list[analytics.GroupValue]] = defaultdict(list)
    for trade in trades:
        strategy_id = trade.journal.strategy_id if trade.journal else None
        # Untagged trades are their own bucket rather than being dropped: how
        # much of the book is unlabelled is itself worth seeing.
        label = names.get(strategy_id, "Untagged") if strategy_id else "Untagged"
        buckets[label].append(trade.value)

    # Worst-performing last, so the eye lands on the biggest contributor.
    order = sorted(
        buckets, key=lambda label: analytics.compute_kpis(buckets[label]).net_pnl, reverse=True
    )
    return _bucketed(buckets, order)


# ------------------------------------------------------------ FR-AN-02


def by_hour(trades: list[LoadedTrade]) -> list[Bucket]:
    """By entry hour in IST — the hour the position was opened."""
    buckets: dict[str, list[analytics.GroupValue]] = defaultdict(list)
    for trade in trades:
        hour = trade.group.opened_at.astimezone(IST).hour
        buckets[f"{hour:02d}:00"].append(trade.value)
    return _bucketed(buckets, sorted(buckets))


def by_weekday(trades: list[LoadedTrade]) -> list[Bucket]:
    buckets: dict[str, list[analytics.GroupValue]] = defaultdict(list)
    for trade in trades:
        buckets[WEEKDAYS[trade.group.opened_at.astimezone(IST).weekday()]].append(trade.value)
    return _bucketed(buckets, WEEKDAYS)


@dataclass
class HeatCell:
    weekday: str
    hour: int
    trades: int
    net_pnl: Decimal


def hour_weekday_heatmap(trades: list[LoadedTrade]) -> list[HeatCell]:
    cells: dict[tuple[str, int], list[analytics.GroupValue]] = defaultdict(list)
    for trade in trades:
        local = trade.group.opened_at.astimezone(IST)
        cells[(WEEKDAYS[local.weekday()], local.hour)].append(trade.value)

    return [
        HeatCell(
            weekday=weekday,
            hour=hour,
            trades=len(values),
            net_pnl=analytics.round_money(sum((v.net_pnl for v in values), ZERO)),
        )
        for (weekday, hour), values in sorted(
            cells.items(), key=lambda kv: (WEEKDAYS.index(kv[0][0]), kv[0][1])
        )
    ]


# ------------------------------------------------------------ FR-AN-03


def by_duration(trades: list[LoadedTrade]) -> list[Bucket]:
    buckets: dict[str, list[analytics.GroupValue]] = defaultdict(list)
    for trade in trades:
        if not trade.group.is_intraday:
            buckets["Multi-day"].append(trade.value)
            continue
        held = trade.group.hold_seconds
        if held is None:
            buckets["Unknown"].append(trade.value)
            continue
        for label, low, high in DURATION_BUCKETS:
            if low <= held < high:
                buckets[label].append(trade.value)
                break

    order = [label for label, _, _ in DURATION_BUCKETS] + ["Multi-day", "Unknown"]
    return _bucketed(buckets, order)


# ------------------------------------------------------------ FR-AN-04


@dataclass
class RHistogramBin:
    label: str
    trades: int


@dataclass
class RiskReport:
    kpis: analytics.Kpis
    streaks: analytics.Streaks
    # FR-AN-04: how much of the book was traded with a stop-loss planned at all.
    trades_with_stop: int = 0
    trades_total: int = 0
    avg_planned_risk: Decimal | None = None
    r_histogram: list[RHistogramBin] = field(default_factory=list)
    drawdown_from: dt.date | None = None
    drawdown_to: dt.date | None = None


# Edges chosen so 0 sits on a boundary: a trade is either beyond its stop or not.
R_BINS: list[tuple[str, Decimal, Decimal]] = [
    ("≤ -2R", Decimal("-999"), Decimal("-2")),
    ("-2R to -1R", Decimal("-2"), Decimal("-1")),
    ("-1R to 0", Decimal("-1"), ZERO),
    ("0 to 1R", ZERO, Decimal("1")),
    ("1R to 2R", Decimal("1"), Decimal("2")),
    ("2R to 3R", Decimal("2"), Decimal("3")),
    ("> 3R", Decimal("3"), Decimal("999")),
]


def risk(trades: list[LoadedTrade]) -> RiskReport:
    values = [trade.value for trade in trades]
    nets = [value.net_pnl for value in values]

    report = RiskReport(
        kpis=analytics.compute_kpis(values),
        streaks=analytics.streaks(nets),
        trades_total=len(trades),
    )

    risks = [
        journal_service.derive(trade.group, trade.journal).planned_risk_amount for trade in trades
    ]
    planned = [value for value in risks if value is not None]
    report.trades_with_stop = len(planned)
    if planned:
        report.avg_planned_risk = analytics.round_money(sum(planned, ZERO) / len(planned))

    counts: dict[str, int] = {label: 0 for label, _, _ in R_BINS}
    for value in values:
        if value.r_multiple is None:
            continue
        for label, low, high in R_BINS:
            if low <= value.r_multiple < high:
                counts[label] += 1
                break
    report.r_histogram = [
        RHistogramBin(label=label, trades=counts[label]) for label, _, _ in R_BINS
    ]

    report.drawdown_from, report.drawdown_to = _drawdown_window(trades)
    return report


def _drawdown_window(trades: list[LoadedTrade]) -> tuple[dt.date | None, dt.date | None]:
    """The dates the largest peak-to-trough fall ran between (FR-AN-04)."""
    peak = cumulative = worst = ZERO
    peak_date: dt.date | None = None
    start: dt.date | None = None
    end: dt.date | None = None

    for trade in trades:
        cumulative += trade.group.net_pnl
        if cumulative >= peak:
            peak = cumulative
            peak_date = trade.group.trade_date
        elif peak - cumulative > worst:
            worst = peak - cumulative
            start, end = peak_date, trade.group.trade_date

    return start, end


# ------------------------------------------------------------ FR-AN-05


@dataclass
class MistakeCost:
    tag: str
    trades: int
    share_of_trades: Decimal
    net_pnl: Decimal
    avg_net_pnl: Decimal


def mistake_cost(session: Session, trades: list[LoadedTrade]) -> list[MistakeCost]:
    """Per mistake tag: count, share, total and average cost, worst first."""
    if not trades:
        return []

    keys = [trade.group.group_key for trade in trades]
    by_key = {trade.group.group_key: trade.value for trade in trades}

    rows = session.execute(
        select(Tag.name, TradeTag.group_key)
        .join(TradeTag, TradeTag.tag_id == Tag.id)
        .where(Tag.kind == "mistake", TradeTag.group_key.in_(keys))
    ).all()

    grouped: dict[str, list[analytics.GroupValue]] = defaultdict(list)
    for name, group_key in rows:
        value = by_key.get(group_key)
        if value is not None:
            grouped[name].append(value)

    total = len(trades)
    report = [
        MistakeCost(
            tag=name,
            trades=len(values),
            share_of_trades=analytics.round_ratio(Decimal(len(values)) / Decimal(total)),
            net_pnl=analytics.round_money(sum((v.net_pnl for v in values), ZERO)),
            avg_net_pnl=analytics.round_money(
                sum((v.net_pnl for v in values), ZERO) / Decimal(len(values))
            ),
        )
        for name, values in grouped.items()
    ]
    # Sorted by total cost: the most expensive habit first (FR-AN-05).
    return sorted(report, key=lambda row: row.net_pnl)
