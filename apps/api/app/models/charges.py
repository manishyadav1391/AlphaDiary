"""Effective-dated charge rate sets and the computed breakdown (SRS 6, 7.3).

Rates are never hard-coded: `charge_rate_set.config` is loaded from
`seed/charge_rates.json`, and the set in force is picked by `effective_from`.
"""

from __future__ import annotations

import datetime as dt

from sqlalchemy import Date, ForeignKey, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.types import ChargeAmount, ChargeAmount4, CreatedAt, Turnover, UuidFk, UuidPk


class ChargeRateSet(Base):
    __tablename__ = "charge_rate_set"

    id: Mapped[UuidPk]
    effective_from: Mapped[dt.date] = mapped_column(Date, nullable=False)
    label: Mapped[str | None] = mapped_column(Text)
    config: Mapped[dict] = mapped_column(JSONB, nullable=False)  # see SRS 7.3
    created_at: Mapped[CreatedAt]


class OrderCharge(Base):
    """Charges as the broker levies them: per order, per segment."""

    __tablename__ = "order_charge"

    order_id: Mapped[str] = mapped_column(Text, primary_key=True)
    account_id: Mapped[UuidFk] = mapped_column(nullable=False)
    segment_key: Mapped[str] = mapped_column(Text, nullable=False)
    turnover: Mapped[Turnover] = mapped_column(nullable=False)
    brokerage: Mapped[ChargeAmount] = mapped_column(nullable=False)
    stt_ctt: Mapped[ChargeAmount] = mapped_column(nullable=False)
    exchange_txn: Mapped[ChargeAmount] = mapped_column(nullable=False)
    sebi: Mapped[ChargeAmount] = mapped_column(nullable=False)
    stamp: Mapped[ChargeAmount] = mapped_column(nullable=False)
    other_levy: Mapped[ChargeAmount] = mapped_column(nullable=False, server_default=text("0"))
    gst: Mapped[ChargeAmount] = mapped_column(nullable=False)
    total: Mapped[ChargeAmount] = mapped_column(nullable=False)
    rate_set_id: Mapped[UuidFk | None] = mapped_column(ForeignKey("charge_rate_set.id"))


class FillCharge(Base):
    """The order's charges allocated down to each fill, at 4 decimals so the
    allocation sums back to the order total (SRS 12.2, charges tests)."""

    __tablename__ = "fill_charge"

    fill_id: Mapped[UuidFk] = mapped_column(
        ForeignKey("fill.id", ondelete="CASCADE"), primary_key=True
    )
    brokerage: Mapped[ChargeAmount4 | None]
    stt_ctt: Mapped[ChargeAmount4 | None]
    exchange_txn: Mapped[ChargeAmount4 | None]
    sebi: Mapped[ChargeAmount4 | None]
    stamp: Mapped[ChargeAmount4 | None]
    other_levy: Mapped[ChargeAmount4 | None]
    gst: Mapped[ChargeAmount4 | None]
    total: Mapped[ChargeAmount4] = mapped_column(nullable=False)
