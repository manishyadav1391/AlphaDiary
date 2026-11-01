"""Request and response models for the daily playbook (FR-PB)."""

from __future__ import annotations

import datetime as dt
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.schemas.common import Money

Bias = Literal["bullish", "bearish", "neutral"]


class PlanIn(BaseModel):
    bias: Bias | None = None
    key_levels: str | None = None
    events: str | None = None
    max_loss: Money | None = None
    max_trades: int | None = Field(default=None, ge=0)
    max_risk_per_trade: Money | None = None
    checklist: dict[str, Any] | None = None


class PlanOut(PlanIn):
    trade_date: dt.date
    updated_at: dt.datetime | None = None


class ReviewIn(BaseModel):
    discipline_rating: int | None = Field(default=None, ge=1, le=5)
    emotion: str | None = None
    went_well: str | None = None
    to_improve: str | None = None
    summary: str | None = None


class ReviewOut(ReviewIn):
    trade_date: dt.date
    updated_at: dt.datetime | None = None


class PlanVersusActual(BaseModel):
    """FR-PB-04, computed from daily_summary."""

    trades_taken: int
    max_trades: int | None = None
    trades_limit_broken: bool = False
    net_pnl: Money
    max_loss: Money | None = None
    loss_limit_broken: bool = False


class PlaybookOut(BaseModel):
    trade_date: dt.date
    plan: PlanOut | None = None
    review: ReviewOut | None = None
    plan_done: bool = False
    review_done: bool = False
    actual: PlanVersusActual


class PlaybookIn(BaseModel):
    """A combined upsert, so one save can write both halves of the day."""

    plan: PlanIn | None = None
    review: ReviewIn | None = None
