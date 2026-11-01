"""Reminder evaluation (FR-REM, SRS 7.5).

The worker ticks every 60 seconds and calls `tick(session, now)`. Every
decision reads `now` from the argument rather than the clock, because all six
acceptance cases in SRS 5.4 are time travel.

Idempotency is the database's: `notification_log` is unique on
`(slot_key, channel)`, so a second tick inside the same minute inserts
nothing and sends nothing. The 20-minute grace window is what stops a server
restarted at 15:20 from firing the 09:00 reminder.
"""

from __future__ import annotations

import datetime as dt
import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import AppSetting, NotificationChannel, NotificationLog
from app.services import holidays, sync_service, token_store
from app.services.kite_client import TokenExpired
from app.services.notifier import (
    Channel,
    NotConfigured,
    ResendEmail,
    SendFailed,
    minutes_until,
    missed_sync_message,
    reminder_message,
    send_with_retry,
)
from app.timezone import IST, ist_date

logger = logging.getLogger("tj.reminders")

REMINDER_SLOTS_KEY = "reminder_slots"
SKIP_TODAY_KEY = "reminders_skipped_on"

# FR-REM-02. Editable in Settings; these are what `make seed` writes.
DEFAULT_SLOTS: list[dict[str, Any]] = [
    {"name": "morning", "time": "09:00", "kind": "reminder", "enabled": True},
    {"name": "first", "time": "15:00", "kind": "reminder", "enabled": True},
    {"name": "second", "time": "15:30", "kind": "reminder", "enabled": True},
    {"name": "final", "time": "15:40", "kind": "reminder", "enabled": True},
    {"name": "missed_sync", "time": "15:50", "kind": "missed_sync", "enabled": True},
    {"name": "catchup", "time": "18:00", "kind": "reminder", "enabled": True},
    {"name": "late_catchup", "time": "21:00", "kind": "reminder", "enabled": False},
]

SYNC_TIME = dt.time(15, 45)


@dataclass(frozen=True)
class Slot:
    name: str
    at: dt.time
    kind: str
    enabled: bool


def parse_slots(raw: list[dict[str, Any]]) -> list[Slot]:
    slots: list[Slot] = []
    for entry in raw:
        try:
            hour, minute = (int(part) for part in str(entry["time"]).split(":"))
        except (KeyError, ValueError):
            continue
        slots.append(
            Slot(
                name=str(entry["name"]),
                at=dt.time(hour, minute),
                kind=str(entry.get("kind", "reminder")),
                enabled=bool(entry.get("enabled", True)),
            )
        )
    return sorted(slots, key=lambda slot: slot.at)


def load_slots(session: Session) -> list[Slot]:
    row = session.get(AppSetting, REMINDER_SLOTS_KEY)
    raw = row.value if row and isinstance(row.value, list) else DEFAULT_SLOTS
    return parse_slots(raw)


def save_slots(session: Session, slots: list[dict[str, Any]]) -> None:
    statement = pg_insert(AppSetting).values(key=REMINDER_SLOTS_KEY, value=slots)
    session.execute(
        statement.on_conflict_do_update(
            index_elements=[AppSetting.key], set_={"value": statement.excluded.value}
        )
    )
    session.flush()


# ------------------------------------------------------------ stop conditions


def skipped_today(session: Session, day: dt.date) -> bool:
    """FR-REM-05: the owner pressed "Skip today"."""
    row = session.get(AppSetting, SKIP_TODAY_KEY)
    if row is None or not isinstance(row.value, dict):
        return False
    return bool(row.value.get("date") == day.isoformat())


def skip_today(session: Session, day: dt.date) -> None:
    statement = pg_insert(AppSetting).values(key=SKIP_TODAY_KEY, value={"date": day.isoformat()})
    session.execute(
        statement.on_conflict_do_update(
            index_elements=[AppSetting.key], set_={"value": statement.excluded.value}
        )
    )
    session.flush()


def _parse_time(value: str) -> dt.time:
    hour, minute = value.split(":")
    return dt.time(int(hour), int(minute))


def in_quiet_hours(now: dt.datetime) -> bool:
    """FR-REM-11: nothing between 22:00 and 07:00 IST."""
    settings = get_settings()
    start = _parse_time(settings.quiet_hours_start_ist)
    end = _parse_time(settings.quiet_hours_end_ist)
    local = now.astimezone(IST).time()
    # The window crosses midnight.
    return local >= start or local < end


# ----------------------------------------------------------------- channels


def enabled_channels(session: Session) -> list[Channel]:
    rows = list(
        session.execute(
            select(NotificationChannel).where(NotificationChannel.enabled.is_(True))
        ).scalars()
    )
    channels: list[Channel] = []
    for row in rows:
        if row.channel == "email":
            channels.append(ResendEmail(to=_destination(row)))
        # Telegram and WhatsApp implement the same protocol when they land.
    return channels


def _destination(row: NotificationChannel) -> str | None:
    if not row.config_enc:
        return None
    from json import JSONDecodeError, loads

    from app.security import decrypt

    try:
        config = loads(decrypt(row.config_enc))
    except (JSONDecodeError, ValueError):
        return None
    value = config.get("to")
    return str(value) if value else None


# --------------------------------------------------------------- the tick


def already_logged(session: Session, slot_key: str, channel: str) -> bool:
    return (
        session.execute(
            select(NotificationLog.id).where(
                NotificationLog.slot_key == slot_key,
                NotificationLog.channel == channel,
            )
        ).scalar_one_or_none()
        is not None
    )


def record(
    session: Session,
    slot_key: str,
    channel: str,
    kind: str,
    status: str,
    *,
    now: dt.datetime,
    attempts: int = 0,
    error: str | None = None,
) -> None:
    """Write the log row. The unique index is what makes a slot fire once."""
    statement = pg_insert(NotificationLog).values(
        slot_key=slot_key,
        channel=channel,
        kind=kind,
        scheduled_for=now,
        sent_at=now if status == "sent" else None,
        status=status,
        attempts=attempts,
        error=error,
    )
    session.execute(statement.on_conflict_do_nothing(index_elements=["slot_key", "channel"]))
    session.flush()


def token_is_live(session: Session) -> bool:
    """FR-REM-04. A clock check first, then a real call to Zerodha."""
    account = token_store.get_account(session)
    if account is None or not token_store.token_may_be_valid(account):
        return False
    try:
        token_store.build_client(session, account).profile()
    except TokenExpired:
        token_store.mark_token_expired(session, account)
        return False
    except Exception:
        # Cannot reach Zerodha: treat as not provably valid and remind.
        logger.warning("Token check failed", extra={"event": "reminder_token_check_failed"})
        return False
    return True


def due_slots(slots: list[Slot], now: dt.datetime, grace_minutes: int) -> list[Slot]:
    """Slots whose time has passed but is still inside the grace window."""
    local = now.astimezone(IST)
    window = dt.timedelta(minutes=grace_minutes)
    due: list[Slot] = []
    for slot in slots:
        if not slot.enabled:
            continue
        at = local.replace(hour=slot.at.hour, minute=slot.at.minute, second=0, microsecond=0)
        if at <= local <= at + window:
            due.append(slot)
    return due


def tick(
    session: Session,
    now: dt.datetime,
    *,
    sleep: Callable[[float], None] | None = None,
) -> list[str]:
    """One reminder evaluation (SRS 7.5). Returns what it did, for the log."""
    settings = get_settings()
    actions: list[str] = []
    day = ist_date(now)

    if not holidays.is_trading_day(session, day):
        return ["not_a_trading_day"]
    if sync_service.synced_today(session, now=now):
        return ["synced_today"]
    if skipped_today(session, day):
        return ["skipped_today"]

    slots = due_slots(load_slots(session), now, settings.reminder_grace_minutes)
    if not slots:
        return []

    channels = enabled_channels(session)
    if not channels:
        return ["no_channels"]

    # Checked once per tick, not once per channel: FR-REM-04 allows a 60 s
    # cache and a tick is 60 s.
    live = token_is_live(session)

    for slot in slots:
        slot_key = f"{day.isoformat()}:{slot.name}"
        for channel in channels:
            if already_logged(session, slot_key, channel.name):
                continue

            if live:
                record(session, slot_key, channel.name, slot.kind, "skipped_token_valid", now=now)
                actions.append(f"{slot.name}/{channel.name}:skipped_token_valid")
                continue

            if in_quiet_hours(now) and slot.at >= dt.time(22, 0):
                record(session, slot_key, channel.name, slot.kind, "skipped_user", now=now)
                continue

            message = (
                missed_sync_message(settings.connect_url)
                if slot.kind == "missed_sync"
                else reminder_message(minutes_until(now, SYNC_TIME, IST), settings.connect_url)
            )

            try:
                if sleep is None:
                    send_with_retry(channel, message)
                else:
                    send_with_retry(channel, message, sleep=sleep)
            except (SendFailed, NotConfigured) as exc:
                record(
                    session,
                    slot_key,
                    channel.name,
                    slot.kind,
                    "failed",
                    now=now,
                    attempts=3,
                    error=str(exc)[:500],
                )
                actions.append(f"{slot.name}/{channel.name}:failed")
                continue

            record(session, slot_key, channel.name, slot.kind, "sent", now=now, attempts=1)
            actions.append(f"{slot.name}/{channel.name}:sent")

    return actions
