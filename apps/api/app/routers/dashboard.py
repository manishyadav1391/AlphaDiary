"""Dashboard KPIs, heatmap and equity curve (FR-DASH)."""

from __future__ import annotations

import calendar
import datetime as dt
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_session
from app.deps import current_user
from app.errors import ApiError
from app.models import AppUser, DailySummary, MarketHoliday, TradeGroup
from app.schemas.dashboard import (
    CurvePointOut,
    EquityCurveOut,
    HeatmapDay,
    HeatmapOut,
    HeatmapWeek,
    SummaryOut,
)
from app.services import analytics
from app.services import journal as journal_service
from app.timezone import ist_date, now_utc

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

ZERO = Decimal("0")


def _default_range() -> tuple[dt.date, dt.date]:
    """This month, in IST (FR-DASH-01)."""
    today = ist_date(now_utc())
    return today.replace(day=1), today


def _closed_groups(session: Session, date_from: dt.date, date_to: dt.date) -> list[TradeGroup]:
    return list(
        session.execute(
            select(TradeGroup)
            .where(
                TradeGroup.status == "closed",
                TradeGroup.trade_date >= date_from,
                TradeGroup.trade_date <= date_to,
            )
            .order_by(TradeGroup.trade_date, TradeGroup.closed_at, TradeGroup.id)
        ).scalars()
    )


def _daily_rows(session: Session, date_from: dt.date, date_to: dt.date) -> list[DailySummary]:
    """Pre-aggregated days.

    The heatmap and the equity curve read these rather than scanning every
    group, which is what keeps the dashboard inside its budget at 10,000
    trades (FR-DASH-09).
    """
    return list(
        session.execute(
            select(DailySummary)
            .where(
                DailySummary.trade_date >= date_from,
                DailySummary.trade_date <= date_to,
            )
            .order_by(DailySummary.trade_date)
        ).scalars()
    )


@router.get("/summary", response_model=SummaryOut)
def summary(
    date_from: dt.date | None = None,
    date_to: dt.date | None = None,
    _: AppUser = Depends(current_user),
    session: Session = Depends(get_session),
) -> SummaryOut:
    """Every KPI card, over the selected range (FR-DASH-02, SRS 7.4)."""
    start, end = _default_range()
    start = date_from or start
    end = date_to or end
    if start > end:
        raise ApiError("invalid_range", "The start date is after the end date.", status_code=422)

    groups = _closed_groups(session, start, end)
    journals = journal_service.journals_for_groups(session, [group.group_key for group in groups])

    values = [
        analytics.GroupValue(
            net_pnl=group.net_pnl,
            gross_pnl=group.gross_pnl,
            charges_total=group.charges_total,
            r_multiple=journal_service.derive(group, journals.get(group.group_key)).r_multiple,
            trade_date=group.trade_date,
        )
        for group in groups
    ]
    kpis = analytics.compute_kpis(values)

    days = [
        analytics.DayPoint(
            trade_date=row.trade_date, net_pnl=row.net_pnl, trades_count=row.trades_count
        )
        for row in _daily_rows(session, start, end)
    ]

    return SummaryOut(
        date_from=start,
        date_to=end,
        trades=kpis.trades,
        wins=kpis.wins,
        losses=kpis.losses,
        breakeven=kpis.breakeven,
        gross_pnl=kpis.gross_pnl,
        charges=kpis.charges,
        net_pnl=kpis.net_pnl,
        win_rate=kpis.win_rate,
        profit_factor=kpis.profit_factor,
        expectancy=kpis.expectancy,
        avg_r=kpis.avg_r,
        avg_win=kpis.avg_win,
        avg_loss=kpis.avg_loss,
        largest_win=kpis.largest_win,
        largest_loss=kpis.largest_loss,
        max_drawdown=kpis.max_drawdown,
        longest_losing_streak=kpis.longest_losing_streak,
        green_day_rate=analytics.green_day_rate(days),
        low_sample=kpis.low_sample,
    )


@router.get("/heatmap", response_model=HeatmapOut)
def heatmap(
    month: str = Query(default="", pattern=r"^(\d{4}-\d{2})?$"),
    _: AppUser = Depends(current_user),
    session: Session = Depends(get_session),
) -> HeatmapOut:
    """One month of day cells, with weekly and monthly totals (FR-DASH-04)."""
    if month:
        year, month_number = (int(part) for part in month.split("-"))
    else:
        today = ist_date(now_utc())
        year, month_number = today.year, today.month
    if not 1 <= month_number <= 12:
        raise ApiError("invalid_month", "Month must be between 01 and 12.", status_code=422)

    first = dt.date(year, month_number, 1)
    last = dt.date(year, month_number, calendar.monthrange(year, month_number)[1])

    rows = {row.trade_date: row for row in _daily_rows(session, first, last)}
    holidays = set(
        session.execute(
            select(MarketHoliday.trade_date).where(
                MarketHoliday.trade_date >= first,
                MarketHoliday.trade_date <= last,
                MarketHoliday.is_trading_override.is_(False),
            )
        ).scalars()
    )

    days: list[HeatmapDay] = []
    weeks: dict[dt.date, tuple[Decimal, int]] = {}
    for offset in range((last - first).days + 1):
        day = first + dt.timedelta(days=offset)
        row = rows.get(day)
        net = row.net_pnl if row else ZERO
        count = row.trades_count if row else 0
        days.append(
            HeatmapDay(
                trade_date=day,
                net_pnl=net,
                trades_count=count,
                is_holiday=day in holidays,
            )
        )
        # Monday-start weeks, matching the calendar grid in DESIGN.md 9.
        week_start = day - dt.timedelta(days=day.weekday())
        running_net, running_count = weeks.get(week_start, (ZERO, 0))
        weeks[week_start] = (running_net + net, running_count + count)

    total_net = sum((day.net_pnl for day in days), start=ZERO)
    total_count = sum(day.trades_count for day in days)
    largest = max((abs(day.net_pnl) for day in days), default=ZERO)

    return HeatmapOut(
        month=f"{year:04d}-{month_number:02d}",
        days=days,
        weeks=[
            HeatmapWeek(week_start=start, net_pnl=net, trades_count=count)
            for start, (net, count) in sorted(weeks.items())
        ],
        net_pnl=analytics.round_money(total_net),
        trades_count=total_count,
        max_abs_day=analytics.round_money(largest),
    )


@router.get("/equity-curve", response_model=EquityCurveOut)
def equity_curve(
    date_from: dt.date | None = None,
    date_to: dt.date | None = None,
    by: Literal["day", "trade"] = "day",
    _: AppUser = Depends(current_user),
    session: Session = Depends(get_session),
) -> EquityCurveOut:
    """Cumulative net P&L, starting at zero (FR-DASH-03, SRS 7.4)."""
    start, end = _default_range()
    start = date_from or start
    end = date_to or end
    if start > end:
        raise ApiError("invalid_range", "The start date is after the end date.", status_code=422)

    if by == "day":
        points = analytics.equity_curve_by_day(
            [
                analytics.DayPoint(
                    trade_date=row.trade_date,
                    net_pnl=row.net_pnl,
                    trades_count=row.trades_count,
                )
                for row in _daily_rows(session, start, end)
            ]
        )
    else:
        points = analytics.equity_curve_by_trade(
            [(group.group_key, group.net_pnl) for group in _closed_groups(session, start, end)]
        )

    return EquityCurveOut(
        date_from=start,
        date_to=end,
        by=by,
        points=[
            CurvePointOut(label=point.label, net_pnl=point.net_pnl, cumulative=point.cumulative)
            for point in points
        ],
        net_pnl=points[-1].cumulative if points else ZERO,
    )
