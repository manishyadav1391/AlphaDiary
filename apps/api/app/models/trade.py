"""Trade groups produced by the FIFO matcher (SRS 6, 7.2).

`group_key` is `account:token:product:first_entry_kite_trade_id`. It is stable
across re-matching, which is why the journal tables key on it instead of on
`trade_group.id` (SRS 6, design rules; FR-MATCH-07).
"""

from __future__ import annotations

import datetime as dt

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    ForeignKey,
    Index,
    Integer,
    Text,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.types import Money, Price, Timestamp, UpdatedAt, UuidFk, UuidPk


class TradeGroup(Base):
    __tablename__ = "trade_group"
    __table_args__ = (
        CheckConstraint("direction in ('LONG','SHORT')", name="direction"),
        CheckConstraint("status in ('open','closed')", name="status"),
        Index("ix_trade_group_account_id_trade_date", "account_id", "trade_date"),
        Index("ix_trade_group_account_id_status_closed_at", "account_id", "status", "closed_at"),
    )

    id: Mapped[UuidPk]
    group_key: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    account_id: Mapped[UuidFk] = mapped_column(nullable=False)
    instrument_token: Mapped[int] = mapped_column(BigInteger, nullable=False)
    tradingsymbol: Mapped[str] = mapped_column(Text, nullable=False)
    exchange: Mapped[str] = mapped_column(Text, nullable=False)
    asset_class: Mapped[str] = mapped_column(Text, nullable=False)
    product: Mapped[str] = mapped_column(Text, nullable=False)  # MIS | NRML | CNC | MTF
    direction: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    qty_max: Mapped[int] = mapped_column(Integer, nullable=False)
    open_qty: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    avg_entry: Mapped[Price | None]
    avg_exit: Mapped[Price | None]
    opened_at: Mapped[Timestamp] = mapped_column(nullable=False)
    closed_at: Mapped[Timestamp | None]
    # IST date of closed_at, or of opened_at while the group is open. Realised
    # P&L is attributed to the date the group closes (SRS 6, design rules).
    trade_date: Mapped[dt.date] = mapped_column(Date, nullable=False)
    hold_seconds: Mapped[int | None] = mapped_column(Integer)
    is_intraday: Mapped[bool] = mapped_column(nullable=False)
    gross_pnl: Mapped[Money] = mapped_column(nullable=False, server_default=text("0"))
    charges_total: Mapped[Money] = mapped_column(nullable=False, server_default=text("0"))
    net_pnl: Mapped[Money] = mapped_column(nullable=False, server_default=text("0"))
    matcher_version: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    updated_at: Mapped[UpdatedAt]


class TradeGroupFill(Base):
    """Which fills, and how much of each, a group consumed."""

    __tablename__ = "trade_group_fill"
    __table_args__ = (
        CheckConstraint("role in ('entry','exit')", name="role"),
        CheckConstraint("quantity_used > 0", name="quantity_used_positive"),
    )

    trade_group_id: Mapped[UuidFk] = mapped_column(
        ForeignKey("trade_group.id", ondelete="CASCADE"), primary_key=True
    )
    fill_id: Mapped[UuidFk] = mapped_column(
        ForeignKey("fill.id", ondelete="CASCADE"), primary_key=True
    )
    role: Mapped[str] = mapped_column(Text, primary_key=True)
    quantity_used: Mapped[int] = mapped_column(Integer, nullable=False)
