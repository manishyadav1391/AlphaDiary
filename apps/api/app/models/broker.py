"""Broker account, the OAuth handshake and the instrument master (SRS 6)."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Date,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    Numeric,
    Text,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.types import CreatedAt, Price, TickSize, Timestamp, UpdatedAt, UuidFk, UuidPk


class BrokerAccount(Base):
    """Broker credentials. Every `*_enc` column is Fernet ciphertext; the
    plaintext never leaves `services/security` and is never logged."""

    __tablename__ = "broker_account"

    id: Mapped[UuidPk]
    user_id: Mapped[UuidFk] = mapped_column(ForeignKey("app_user.id"), nullable=False)
    broker: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'zerodha'"))
    api_key_enc: Mapped[bytes | None] = mapped_column(LargeBinary)
    api_secret_enc: Mapped[bytes | None] = mapped_column(LargeBinary)
    access_token_enc: Mapped[bytes | None] = mapped_column(LargeBinary)
    token_issued_at: Mapped[Timestamp | None]
    token_valid_until: Mapped[Timestamp | None]
    kite_user_id: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[CreatedAt]


class OAuthState(Base):
    """CSRF state for the Kite login redirect (SRS 3.5, V5)."""

    __tablename__ = "oauth_state"

    state: Mapped[str] = mapped_column(Text, primary_key=True)
    account_id: Mapped[UuidFk] = mapped_column(ForeignKey("broker_account.id"), nullable=False)
    expires_at: Mapped[Timestamp] = mapped_column(nullable=False)
    used_at: Mapped[Timestamp | None]


class Instrument(Base):
    __tablename__ = "instrument"
    __table_args__ = (Index("ix_instrument_exchange_tradingsymbol", "exchange", "tradingsymbol"),)

    instrument_token: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    exchange: Mapped[str] = mapped_column(Text, nullable=False)
    tradingsymbol: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str | None] = mapped_column(Text)
    segment: Mapped[str | None] = mapped_column(Text)
    instrument_type: Mapped[str | None] = mapped_column(Text)  # EQ, FUT, CE, PE
    asset_class: Mapped[str] = mapped_column(Text, nullable=False)  # equity|fno|commodity|currency
    expiry: Mapped[dt.date | None] = mapped_column(Date)
    strike: Mapped[Price | None]
    lot_size: Mapped[int | None] = mapped_column(Integer)
    tick_size: Mapped[TickSize | None]
    # VERIFY V6: the MCX multiplier is unconfirmed.
    multiplier: Mapped[Decimal] = mapped_column(
        Numeric(14, 4), nullable=False, server_default=text("1")
    )
    updated_at: Mapped[UpdatedAt]
