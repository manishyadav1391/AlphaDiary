"""Request and response models for FR-SET, FR-KITE-01/09 and FR-REM-02/06/14.

No model here ever carries the API secret, an access token or a channel
credential. The API key is returned masked to its last 4 characters.
"""

from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, Field, field_validator


class KiteSettingsOut(BaseModel):
    api_key_masked: str | None = None
    has_secret: bool = False
    # Shown so it can be registered in the Kite Developer Console (FR-KITE-09).
    redirect_url: str


class KiteCredentialsIn(BaseModel):
    api_key: str = Field(min_length=4, max_length=64)
    api_secret: str = Field(min_length=4, max_length=128)

    @field_validator("api_key", "api_secret")
    @classmethod
    def _strip(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("must not be blank")
        return stripped


class ReminderSlotIn(BaseModel):
    name: str = Field(min_length=1, max_length=40)
    # "HH:MM" in IST, matching what is stored in app_setting.
    time: str
    kind: str = "reminder"
    enabled: bool = True

    @field_validator("time")
    @classmethod
    def _valid_time(cls, value: str) -> str:
        try:
            hour, minute = value.split(":")
            dt.time(int(hour), int(minute))
        except (ValueError, TypeError) as exc:
            raise ValueError("time must be HH:MM in 24-hour IST") from exc
        return value

    @field_validator("kind")
    @classmethod
    def _valid_kind(cls, value: str) -> str:
        if value not in {"reminder", "missed_sync"}:
            raise ValueError("kind must be 'reminder' or 'missed_sync'")
        return value


class ReminderSettingsOut(BaseModel):
    slots: list[ReminderSlotIn]
    # Context for the screen, so it can say what the slots are counting down to.
    sync_time_ist: str
    grace_minutes: int
    quiet_hours_start_ist: str
    quiet_hours_end_ist: str
    skipped_today: bool


class ReminderSettingsIn(BaseModel):
    slots: list[ReminderSlotIn]

    @field_validator("slots")
    @classmethod
    def _unique_names(cls, value: list[ReminderSlotIn]) -> list[ReminderSlotIn]:
        names = [slot.name for slot in value]
        if len(names) != len(set(names)):
            raise ValueError("slot names must be unique")
        return value


class ChannelOut(BaseModel):
    channel: str
    enabled: bool
    # The destination is shown so the owner can see where mail is going. It is
    # not a secret from its owner, but it is never logged.
    destination: str | None = None
    configured: bool = False
    updated_at: dt.datetime | None = None


class ChannelIn(BaseModel):
    enabled: bool
    # A plain str with a shape check, matching schemas/auth.py: pydantic's
    # EmailStr would pull in email-validator, which is not a dependency.
    destination: str | None = Field(default=None, max_length=320)

    @field_validator("destination")
    @classmethod
    def _looks_like_email(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip().lower()
        if not cleaned:
            return None
        local, _, domain = cleaned.partition("@")
        if not local or not domain or "." not in domain or " " in cleaned:
            raise ValueError("must be an email address")
        return cleaned


class ChannelTestOut(BaseModel):
    sent: bool
    destination: str | None = None
    error: str | None = None


class NotificationLogOut(BaseModel):
    id: int
    slot_key: str
    channel: str
    kind: str
    status: str
    attempts: int
    scheduled_for: dt.datetime | None = None
    sent_at: dt.datetime | None = None
    error: str | None = None
