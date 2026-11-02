"""Request and response models for FR-AN.

Money is serialised as a string (CLAUDE.md), so every Decimal field here is
declared as Decimal and rendered by the shared JSON encoder.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

from pydantic import BaseModel


class BucketKpisOut(BaseModel):
    """The subset of SRS 7.4 the breakdown tables and charts show."""

    trades: int
    wins: int
    losses: int
    net_pnl: Decimal
    gross_pnl: Decimal
    charges: Decimal
    win_rate: Decimal | None = None
    profit_factor: Decimal | None = None
    expectancy: Decimal | None = None
    avg_r: Decimal | None = None
    avg_win: Decimal | None = None
    avg_loss: Decimal | None = None
    # FR-AN-08: fewer than 20 trades is not a conclusion.
    low_sample: bool = True


class BucketOut(BaseModel):
    label: str
    kpis: BucketKpisOut


class HeatCellOut(BaseModel):
    weekday: str
    hour: int
    trades: int
    net_pnl: Decimal


class RHistogramBinOut(BaseModel):
    label: str
    trades: int


class RiskOut(BaseModel):
    net_pnl: Decimal
    max_drawdown: Decimal
    drawdown_from: dt.date | None = None
    drawdown_to: dt.date | None = None
    longest_losing_streak: int
    longest_winning_streak: int
    largest_win: Decimal | None = None
    largest_loss: Decimal | None = None
    trades_total: int
    trades_with_stop: int
    avg_planned_risk: Decimal | None = None
    r_histogram: list[RHistogramBinOut] = []
    low_sample: bool = True


class MistakeCostOut(BaseModel):
    tag: str
    trades: int
    share_of_trades: Decimal
    net_pnl: Decimal
    avg_net_pnl: Decimal


class AnalyticsOut(BaseModel):
    """Everything the Analytics screen needs, in one round trip.

    One response rather than seven endpoints: the screen shows all of it at
    once over the same filters, and the trades are loaded once and bucketed in
    memory, so splitting it would mean re-querying the same rows per section.
    """

    date_from: dt.date
    date_to: dt.date
    trades: int
    low_sample: bool
    by_strategy: list[BucketOut] = []
    by_hour: list[BucketOut] = []
    by_weekday: list[BucketOut] = []
    heatmap: list[HeatCellOut] = []
    by_duration: list[BucketOut] = []
    risk: RiskOut | None = None
    mistakes: list[MistakeCostOut] = []
