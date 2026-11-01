"""Operational tables: sync log, notification channels and app settings."""

from __future__ import annotations

import datetime as dt
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Integer,
    LargeBinary,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.types import BigIntPk, Timestamp, UpdatedAt, UuidFk, UuidPk


class SyncLog(Base):
    __tablename__ = "sync_log"
    __table_args__ = (
        CheckConstraint("trigger in ('manual','scheduled','login_catchup','csv')", name="trigger"),
        CheckConstraint(
            "status in ('running','success','partial','failed','skipped_no_token')",
            name="status",
        ),
    )

    id: Mapped[UuidPk]
    account_id: Mapped[UuidFk | None]
    trigger: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    started_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    finished_at: Mapped[Timestamp | None]
    fills_new: Mapped[int | None] = mapped_column(Integer, server_default=text("0"))
    fills_dup: Mapped[int | None] = mapped_column(Integer, server_default=text("0"))
    fills_rejected: Mapped[int | None] = mapped_column(Integer, server_default=text("0"))
    orders_upserted: Mapped[int | None] = mapped_column(Integer, server_default=text("0"))
    error: Mapped[str | None] = mapped_column(Text)
    details: Mapped[dict | None] = mapped_column(JSONB)


class NotificationChannel(Base):
    """`config_enc` is encrypted JSON (destination, tokens, template). It is
    never logged or returned by the API."""

    __tablename__ = "notification_channel"
    __table_args__ = (
        CheckConstraint("channel in ('email','whatsapp','telegram')", name="channel"),
    )

    channel: Mapped[str] = mapped_column(Text, primary_key=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    config_enc: Mapped[bytes | None] = mapped_column(LargeBinary)
    updated_at: Mapped[UpdatedAt]


class NotificationLog(Base):
    """`(slot_key, channel)` is unique, so a reminder slot fires at most once
    per channel however often the worker ticks (SRS 7.5)."""

    __tablename__ = "notification_log"
    __table_args__ = (
        UniqueConstraint("slot_key", "channel", name="uq_notification_log_slot_key_channel"),
    )

    id: Mapped[BigIntPk]
    slot_key: Mapped[str] = mapped_column(Text, nullable=False)
    channel: Mapped[str] = mapped_column(Text, nullable=False)
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    scheduled_for: Mapped[Timestamp | None]
    sent_at: Mapped[Timestamp | None]
    status: Mapped[str] = mapped_column(Text, nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    error: Mapped[str | None] = mapped_column(Text)


class AppSetting(Base):
    """A JSONB bag. `value` holds whatever the key needs: a list of reminder
    slots, a date string, a preferences object."""

    __tablename__ = "app_setting"

    key: Mapped[str] = mapped_column(Text, primary_key=True)
    value: Mapped[Any] = mapped_column(JSONB, nullable=False)
