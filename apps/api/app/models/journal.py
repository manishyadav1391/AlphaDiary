"""Journal, setup tags and screenshots (SRS 6, FR-JRN).

Every table here is keyed by `group_key` text and deliberately has **no**
foreign key to `trade_group`, so the matcher can delete and rebuild groups
without losing notes (SRS 6, design rules; FR-MATCH-07).
"""

from __future__ import annotations

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.types import CreatedAt, Price, UpdatedAt, UuidFk, UuidPk


class Strategy(Base):
    """A named setup, chosen by hand on each trade."""

    __tablename__ = "strategy"

    id: Mapped[UuidPk]
    name: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(Text)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))


class Tag(Base):
    __tablename__ = "tag"
    __table_args__ = (
        CheckConstraint("kind in ('mistake','attribute')", name="kind"),
        UniqueConstraint("kind", "name", name="uq_tag_kind_name"),
    )

    id: Mapped[UuidPk]
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))


class TradeJournal(Base):
    __tablename__ = "trade_journal"
    __table_args__ = (
        CheckConstraint("followed_plan in ('yes','partly','no')", name="followed_plan"),
        CheckConstraint("execution_rating between 1 and 5", name="execution_rating"),
    )

    group_key: Mapped[str] = mapped_column(Text, primary_key=True)
    strategy_id: Mapped[UuidFk | None] = mapped_column(ForeignKey("strategy.id"))
    planned_entry: Mapped[Price | None]
    planned_sl: Mapped[Price | None]
    planned_target: Mapped[Price | None]
    entry_reason: Mapped[str | None] = mapped_column(Text)
    exit_reason: Mapped[str | None] = mapped_column(Text)
    emotion: Mapped[str | None] = mapped_column(Text)
    followed_plan: Mapped[str | None] = mapped_column(Text)
    execution_rating: Mapped[int | None] = mapped_column(Integer)
    lessons: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[UpdatedAt]


class TradeTag(Base):
    __tablename__ = "trade_tag"

    group_key: Mapped[str] = mapped_column(Text, primary_key=True)
    tag_id: Mapped[UuidFk] = mapped_column(ForeignKey("tag.id"), primary_key=True)


class Screenshot(Base):
    __tablename__ = "screenshot"
    __table_args__ = (
        CheckConstraint("kind in ('before','after','other')", name="kind"),
        Index("ix_screenshot_group_key", "group_key"),
    )

    id: Mapped[UuidPk]
    group_key: Mapped[str] = mapped_column(Text, nullable=False)
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    object_key: Mapped[str] = mapped_column(Text, nullable=False)
    mime: Mapped[str] = mapped_column(Text, nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    caption: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[CreatedAt]
