"""Per-day tables: plan, review, rolled-up summary, holidays and benchmarks.

`trade_date` is always the IST calendar date (SRS 4.3, Time).
"""

from __future__ import annotations

import datetime as dt

from sqlalchemy import Boolean, CheckConstraint, Date, Integer, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.types import Money, UpdatedAt, UuidFk


class DailyPlan(Base):
    """Written before the market opens (FR-PB)."""

    __tablename__ = "daily_plan"

    trade_date: Mapped[dt.date] = mapped_column(Date, primary_key=True)
    bias: Mapped[str | None] = mapped_column(Text)
    key_levels: Mapped[str | None] = mapped_column(Text)
    events: Mapped[str | None] = mapped_column(Text)
    max_loss: Mapped[Money | None]
    max_trades: Mapped[int | None] = mapped_column(Integer)
    max_risk_per_trade: Mapped[Money | None]
    checklist: Mapped[dict | None] = mapped_column(JSONB)
    updated_at: Mapped[UpdatedAt]


class DailyReview(Base):
    """The evening reflection (FR-PB)."""

    __tablename__ = "daily_review"
    __table_args__ = (
        CheckConstraint("discipline_rating between 1 and 5", name="discipline_rating"),
    )

    trade_date: Mapped[dt.date] = mapped_column(Date, primary_key=True)
    discipline_rating: Mapped[int | None] = mapped_column(Integer)
    emotion: Mapped[str | None] = mapped_column(Text)
    went_well: Mapped[str | None] = mapped_column(Text)
    to_improve: Mapped[str | None] = mapped_column(Text)
    summary: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[UpdatedAt]


class DailySummary(Base):
    __tablename__ = "daily_summary"

    account_id: Mapped[UuidFk] = mapped_column(primary_key=True)
    trade_date: Mapped[dt.date] = mapped_column(Date, primary_key=True)
    trades_count: Mapped[int] = mapped_column(Integer, nullable=False)
    wins: Mapped[int] = mapped_column(Integer, nullable=False)
    losses: Mapped[int] = mapped_column(Integer, nullable=False)
    breakeven: Mapped[int] = mapped_column(Integer, nullable=False)
    gross_pnl: Mapped[Money] = mapped_column(nullable=False)
    charges: Mapped[Money] = mapped_column(nullable=False)
    net_pnl: Mapped[Money] = mapped_column(nullable=False)
    best_trade: Mapped[Money | None]
    worst_trade: Mapped[Money | None]


class MarketHoliday(Base):
    """NSE holiday calendar; reminders are skipped on these days (VERIFY V11)."""

    __tablename__ = "market_holiday"

    trade_date: Mapped[dt.date] = mapped_column(Date, primary_key=True)
    description: Mapped[str | None] = mapped_column(Text)
    is_trading_override: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )


class BenchmarkPrice(Base):
    """Public daily closes for the Nifty 50 and Bank Nifty overlay (FR-BM)."""

    __tablename__ = "benchmark_price"

    symbol: Mapped[str] = mapped_column(Text, primary_key=True)
    trade_date: Mapped[dt.date] = mapped_column(Date, primary_key=True)
    close: Mapped[Money] = mapped_column(nullable=False)
