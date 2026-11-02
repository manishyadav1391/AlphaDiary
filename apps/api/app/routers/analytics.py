"""Analytics (FR-AN). Thin: the bucketing lives in services/analytics_breakdown.py."""

from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db import get_session
from app.deps import current_user
from app.errors import ApiError
from app.models import AppUser
from app.schemas.analytics import (
    AnalyticsOut,
    BucketKpisOut,
    BucketOut,
    HeatCellOut,
    MistakeCostOut,
    RHistogramBinOut,
    RiskOut,
)
from app.services import analytics_breakdown as breakdown
from app.timezone import ist_date, now_utc

router = APIRouter(prefix="/analytics", tags=["analytics"])


def _default_range() -> tuple[dt.date, dt.date]:
    """This month, in IST, matching the dashboard's default (FR-DASH-01)."""
    today = ist_date(now_utc())
    return today.replace(day=1), today


def _bucket(bucket: breakdown.Bucket) -> BucketOut:
    kpis = bucket.kpis
    return BucketOut(
        label=bucket.label,
        kpis=BucketKpisOut(
            trades=kpis.trades,
            wins=kpis.wins,
            losses=kpis.losses,
            net_pnl=kpis.net_pnl,
            gross_pnl=kpis.gross_pnl,
            charges=kpis.charges,
            win_rate=kpis.win_rate,
            profit_factor=kpis.profit_factor,
            expectancy=kpis.expectancy,
            avg_r=kpis.avg_r,
            avg_win=kpis.avg_win,
            avg_loss=kpis.avg_loss,
            low_sample=kpis.low_sample,
        ),
    )


@router.get("", response_model=AnalyticsOut)
def read_analytics(
    date_from: dt.date | None = None,
    date_to: dt.date | None = None,
    asset_class: list[str] = Query(default=[]),
    product: list[str] = Query(default=[]),
    intraday_only: bool = False,
    _: AppUser = Depends(current_user),
    session: Session = Depends(get_session),
) -> AnalyticsOut:
    """Every breakdown on the Analytics screen, over the selected filters."""
    start, end = _default_range()
    start = date_from or start
    end = date_to or end
    if start > end:
        raise ApiError("invalid_range", "The start date is after the end date.", status_code=422)

    filters = breakdown.Filters(
        date_from=start,
        date_to=end,
        asset_class=asset_class,
        product=product,
        intraday_only=intraday_only,
    )
    trades = breakdown.load(session, filters)

    if not trades:
        return AnalyticsOut(date_from=start, date_to=end, trades=0, low_sample=True)

    risk = breakdown.risk(trades)

    return AnalyticsOut(
        date_from=start,
        date_to=end,
        trades=len(trades),
        low_sample=risk.kpis.low_sample,
        by_strategy=[_bucket(b) for b in breakdown.by_strategy(session, trades)],
        by_hour=[_bucket(b) for b in breakdown.by_hour(trades)],
        by_weekday=[_bucket(b) for b in breakdown.by_weekday(trades)],
        heatmap=[
            HeatCellOut(
                weekday=cell.weekday, hour=cell.hour, trades=cell.trades, net_pnl=cell.net_pnl
            )
            for cell in breakdown.hour_weekday_heatmap(trades)
        ],
        by_duration=[_bucket(b) for b in breakdown.by_duration(trades)],
        risk=RiskOut(
            net_pnl=risk.kpis.net_pnl,
            max_drawdown=risk.kpis.max_drawdown,
            drawdown_from=risk.drawdown_from,
            drawdown_to=risk.drawdown_to,
            longest_losing_streak=risk.streaks.longest_losing,
            longest_winning_streak=risk.streaks.longest_winning,
            largest_win=risk.kpis.largest_win,
            largest_loss=risk.kpis.largest_loss,
            trades_total=risk.trades_total,
            trades_with_stop=risk.trades_with_stop,
            avg_planned_risk=risk.avg_planned_risk,
            r_histogram=[
                RHistogramBinOut(label=b.label, trades=b.trades) for b in risk.r_histogram
            ],
            low_sample=risk.kpis.low_sample,
        ),
        mistakes=[
            MistakeCostOut(
                tag=row.tag,
                trades=row.trades,
                share_of_trades=row.share_of_trades,
                net_pnl=row.net_pnl,
                avg_net_pnl=row.avg_net_pnl,
            )
            for row in breakdown.mistake_cost(session, trades)
        ],
    )
