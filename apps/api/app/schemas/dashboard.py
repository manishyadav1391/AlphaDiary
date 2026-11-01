"""Request and response models for the dashboard (FR-DASH, SRS 7.4)."""

from __future__ import annotations

import datetime as dt
from typing import Literal

from pydantic import BaseModel

from app.schemas.common import Money, Ratio


class SummaryOut(BaseModel):
    date_from: dt.date
    date_to: dt.date
    trades: int
    wins: int
    losses: int
    breakeven: int
    gross_pnl: Money
    charges: Money
    net_pnl: Money
    # Null, not zero, where the formula has no answer: a win rate with no
    # trades and a profit factor with no losses are both undefined.
    win_rate: Ratio | None = None
    profit_factor: Ratio | None = None
    expectancy: Money | None = None
    avg_r: Ratio | None = None
    avg_win: Money | None = None
    avg_loss: Money | None = None
    largest_win: Money | None = None
    largest_loss: Money | None = None
    max_drawdown: Money
    longest_losing_streak: int
    green_day_rate: Ratio | None = None
    # Fewer than 20 closed trades: the UI says so rather than implying
    # confidence (DESIGN.md 10).
    low_sample: bool


class HeatmapDay(BaseModel):
    trade_date: dt.date
    net_pnl: Money
    trades_count: int
    is_holiday: bool = False


class HeatmapWeek(BaseModel):
    week_start: dt.date
    net_pnl: Money
    trades_count: int


class HeatmapOut(BaseModel):
    month: str
    days: list[HeatmapDay]
    weeks: list[HeatmapWeek]
    net_pnl: Money
    trades_count: int
    # The largest absolute day, so the client can scale colour intensity
    # without a second request (DESIGN.md 5).
    max_abs_day: Money


class CurvePointOut(BaseModel):
    label: str
    net_pnl: Money
    cumulative: Money


class EquityCurveOut(BaseModel):
    date_from: dt.date
    date_to: dt.date
    by: Literal["day", "trade"]
    points: list[CurvePointOut]
    net_pnl: Money
