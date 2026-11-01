"""Login, sessions and login attempts (SRS 6)."""

from __future__ import annotations

import datetime as dt

from sqlalchemy import Boolean, DateTime, ForeignKey, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.types import BigIntPk, CreatedAt, Timestamp, UuidFk, UuidPk


class AppUser(Base):
    __tablename__ = "app_user"

    id: Mapped[UuidPk]
    email: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[CreatedAt]


class AppSession(Base):
    __tablename__ = "app_session"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    user_id: Mapped[UuidFk] = mapped_column(
        ForeignKey("app_user.id", ondelete="CASCADE"), nullable=False
    )
    expires_at: Mapped[Timestamp] = mapped_column(nullable=False)
    created_at: Mapped[CreatedAt]


class LoginAttempt(Base):
    __tablename__ = "login_attempt"

    id: Mapped[BigIntPk]
    email: Mapped[str | None] = mapped_column(Text)
    success: Mapped[bool] = mapped_column(Boolean, nullable=False)
    at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
