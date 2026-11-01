"""Raw broker data: orders, fills and CSV import batches (SRS 6).

Both `kite_order` and `fill` keep the original payload in `raw jsonb` so the
matcher and the charges engine can be re-run after a bug fix (SRS 4.3).
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
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.types import CreatedAt, Price, Timestamp, UuidFk, UuidPk


class KiteOrder(Base):
    __tablename__ = "kite_order"

    order_id: Mapped[str] = mapped_column(Text, primary_key=True)
    account_id: Mapped[UuidFk] = mapped_column(ForeignKey("broker_account.id"), nullable=False)
    exchange_order_id: Mapped[str | None] = mapped_column(Text)
    exchange: Mapped[str | None] = mapped_column(Text)
    tradingsymbol: Mapped[str | None] = mapped_column(Text)
    instrument_token: Mapped[int | None] = mapped_column(BigInteger)
    transaction_type: Mapped[str | None] = mapped_column(Text)
    product: Mapped[str | None] = mapped_column(Text)
    order_type: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str | None] = mapped_column(Text)
    quantity: Mapped[int | None] = mapped_column(Integer)
    filled_quantity: Mapped[int | None] = mapped_column(Integer)
    price: Mapped[Price | None]
    trigger_price: Mapped[Price | None]
    average_price: Mapped[Price | None]
    placed_at: Mapped[Timestamp | None]
    raw: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[CreatedAt]


class ImportBatch(Base):
    __tablename__ = "import_batch"

    id: Mapped[UuidPk]
    account_id: Mapped[UuidFk] = mapped_column(nullable=False)
    filename: Mapped[str | None] = mapped_column(Text)
    rows_read: Mapped[int | None] = mapped_column(Integer)
    rows_new: Mapped[int | None] = mapped_column(Integer)
    rows_dup: Mapped[int | None] = mapped_column(Integer)
    rows_rejected: Mapped[int | None] = mapped_column(Integer)
    date_from: Mapped[dt.date | None] = mapped_column(Date)
    date_to: Mapped[dt.date | None] = mapped_column(Date)
    created_at: Mapped[CreatedAt]


class Fill(Base):
    """One execution. `(account_id, kite_trade_id)` is unique, which is what
    makes sync and CSV import idempotent (SRS 4.3, golden S10/S11)."""

    __tablename__ = "fill"
    __table_args__ = (
        CheckConstraint("side in ('BUY','SELL')", name="side"),
        CheckConstraint("quantity > 0", name="quantity_positive"),
        CheckConstraint("source in ('api','csv','manual')", name="source"),
        UniqueConstraint("account_id", "kite_trade_id", name="uq_fill_account_id_kite_trade_id"),
        Index(
            "ix_fill_account_id_instrument_token_product_filled_at",
            "account_id",
            "instrument_token",
            "product",
            "filled_at",
        ),
        Index("ix_fill_trade_date", "trade_date"),
        Index("ix_fill_order_id", "order_id"),
    )

    id: Mapped[UuidPk]
    account_id: Mapped[UuidFk] = mapped_column(ForeignKey("broker_account.id"), nullable=False)
    kite_trade_id: Mapped[str] = mapped_column(Text, nullable=False)
    order_id: Mapped[str | None] = mapped_column(Text)
    exchange: Mapped[str] = mapped_column(Text, nullable=False)
    tradingsymbol: Mapped[str] = mapped_column(Text, nullable=False)
    instrument_token: Mapped[int] = mapped_column(BigInteger, nullable=False)
    product: Mapped[str] = mapped_column(Text, nullable=False)  # MIS | NRML | CNC | MTF
    side: Mapped[str] = mapped_column(Text, nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    price: Mapped[Price] = mapped_column(nullable=False)
    filled_at: Mapped[Timestamp] = mapped_column(nullable=False)
    trade_date: Mapped[dt.date] = mapped_column(Date, nullable=False)  # IST date of filled_at
    source: Mapped[str] = mapped_column(Text, nullable=False)
    import_batch_id: Mapped[UuidFk | None] = mapped_column(ForeignKey("import_batch.id"))
    raw: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[CreatedAt]
