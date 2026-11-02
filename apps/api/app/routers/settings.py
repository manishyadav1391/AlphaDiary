"""Settings (FR-SET, FR-KITE-01/09, FR-REM-02/06/14). Thin: logic lives in services/."""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_session
from app.deps import current_user
from app.errors import ApiError
from app.models import AppUser, NotificationChannel, NotificationLog
from app.schemas.settings import (
    ChannelIn,
    ChannelOut,
    ChannelTestOut,
    KiteCredentialsIn,
    KiteSettingsOut,
    NotificationLogOut,
    ReminderSettingsIn,
    ReminderSettingsOut,
    ReminderSlotIn,
)
from app.security import EncryptionKeyError, encrypt
from app.services import notifier, reminders, token_store
from app.timezone import ist_date, now_utc

router = APIRouter(prefix="/settings", tags=["settings"])

# Only email is implemented; WhatsApp and Telegram are FR-REM-12/13.
SUPPORTED_CHANNELS = frozenset({"email"})


# ----------------------------------------------------------------- Kite


@router.get("/kite", response_model=KiteSettingsOut)
def read_kite(
    _: AppUser = Depends(current_user),
    session: Session = Depends(get_session),
) -> KiteSettingsOut:
    """The masked key and the callback URL to register (FR-KITE-09)."""
    settings = get_settings()
    account = token_store.get_account(session)
    if account is None:
        return KiteSettingsOut(redirect_url=settings.kite_redirect_url)

    try:
        masked = token_store.masked_api_key(account)
    except EncryptionKeyError as exc:
        raise ApiError(
            "encryption_key_changed",
            "The stored credentials cannot be read. APP_ENCRYPTION_KEY has probably changed; "
            "re-enter the API key and secret.",
            status_code=409,
        ) from exc

    return KiteSettingsOut(
        api_key_masked=masked,
        has_secret=account.api_secret_enc is not None,
        redirect_url=settings.kite_redirect_url,
    )


@router.put("/kite", response_model=KiteSettingsOut)
def write_kite(
    payload: KiteCredentialsIn,
    user: AppUser = Depends(current_user),
    session: Session = Depends(get_session),
) -> KiteSettingsOut:
    """Store the API key and secret, encrypted (FR-KITE-01)."""
    settings = get_settings()
    try:
        account = token_store.save_credentials(session, user, payload.api_key, payload.api_secret)
        masked = token_store.masked_api_key(account)
    except EncryptionKeyError as exc:
        raise ApiError(
            "not_configured",
            "APP_ENCRYPTION_KEY is not a valid Fernet key, so credentials cannot be stored.",
            status_code=409,
        ) from exc

    session.commit()
    return KiteSettingsOut(
        api_key_masked=masked,
        has_secret=True,
        redirect_url=settings.kite_redirect_url,
    )


# ------------------------------------------------------------- reminders


@router.get("/reminders", response_model=ReminderSettingsOut)
def read_reminders(
    _: AppUser = Depends(current_user),
    session: Session = Depends(get_session),
) -> ReminderSettingsOut:
    """The slot schedule and the clock it is measured against (FR-REM-02)."""
    settings = get_settings()
    slots = reminders.load_slots(session)
    return ReminderSettingsOut(
        slots=[
            ReminderSlotIn(
                name=slot.name,
                time=slot.at.strftime("%H:%M"),
                kind=slot.kind,
                enabled=slot.enabled,
            )
            for slot in slots
        ],
        sync_time_ist=reminders.SYNC_TIME.strftime("%H:%M"),
        grace_minutes=settings.reminder_grace_minutes,
        quiet_hours_start_ist=settings.quiet_hours_start_ist,
        quiet_hours_end_ist=settings.quiet_hours_end_ist,
        skipped_today=reminders.skipped_today(session, ist_date(now_utc())),
    )


@router.put("/reminders", response_model=ReminderSettingsOut)
def write_reminders(
    payload: ReminderSettingsIn,
    user: AppUser = Depends(current_user),
    session: Session = Depends(get_session),
) -> ReminderSettingsOut:
    """Replace the slot schedule (FR-REM-02)."""
    reminders.save_slots(
        session,
        [
            {
                "name": slot.name,
                "time": slot.time,
                "kind": slot.kind,
                "enabled": slot.enabled,
            }
            for slot in payload.slots
        ],
    )
    session.commit()
    return read_reminders(user, session)


@router.post("/reminders/skip-today", status_code=204)
def skip_today(
    _: AppUser = Depends(current_user),
    session: Session = Depends(get_session),
) -> None:
    """Silence the rest of today's reminders (FR-REM-05)."""
    reminders.skip_today(session, ist_date(now_utc()))
    session.commit()


# -------------------------------------------------------------- channels


def _channel_row(session: Session, channel: str) -> NotificationChannel | None:
    return session.get(NotificationChannel, channel)


def _as_out(row: NotificationChannel | None, channel: str) -> ChannelOut:
    if row is None:
        return ChannelOut(channel=channel, enabled=False, configured=False)

    destination: str | None = None
    try:
        destination = reminders.destination_for(row)
    except EncryptionKeyError:
        # Readable state matters more here than the value: a rotated key is
        # exactly the failure this screen exists to surface.
        destination = None

    return ChannelOut(
        channel=row.channel,
        enabled=row.enabled,
        destination=destination,
        configured=destination is not None,
        updated_at=row.updated_at,
    )


def _require_supported(channel: str) -> None:
    if channel not in SUPPORTED_CHANNELS:
        raise ApiError(
            "channel_not_supported",
            f"{channel} reminders are not built yet. Email is the only channel.",
            status_code=404,
        )


@router.get("/channels/{channel}", response_model=ChannelOut)
def read_channel(
    channel: str,
    _: AppUser = Depends(current_user),
    session: Session = Depends(get_session),
) -> ChannelOut:
    _require_supported(channel)
    return _as_out(_channel_row(session, channel), channel)


@router.put("/channels/{channel}", response_model=ChannelOut)
def write_channel(
    channel: str,
    payload: ChannelIn,
    _: AppUser = Depends(current_user),
    session: Session = Depends(get_session),
) -> ChannelOut:
    """Set the destination and whether the channel is on (FR-REM-06)."""
    _require_supported(channel)

    if payload.enabled and not payload.destination:
        raise ApiError(
            "destination_required",
            "Set the address before enabling email reminders.",
            status_code=422,
        )

    row = _channel_row(session, channel)
    if row is None:
        row = NotificationChannel(channel=channel)
        session.add(row)

    row.enabled = payload.enabled
    if payload.destination:
        row.config_enc = encrypt(json.dumps({"to": payload.destination}))

    session.flush()
    session.commit()
    return _as_out(row, channel)


@router.post("/channels/{channel}/test", response_model=ChannelTestOut)
def test_channel(
    channel: str,
    _: AppUser = Depends(current_user),
    session: Session = Depends(get_session),
) -> ChannelTestOut:
    """Send one test message and report the exact outcome (FR-REM-06)."""
    _require_supported(channel)

    settings = get_settings()
    row = _channel_row(session, channel)
    destination = reminders.destination_for(row) if row else None
    if destination is None:
        destination = settings.reminder_email_to or None

    try:
        notifier.ResendEmail().send(notifier.test_message(settings.public_base_url))
    except notifier.NotConfigured as exc:
        return ChannelTestOut(sent=False, destination=destination, error=str(exc))
    except notifier.SendFailed as exc:
        return ChannelTestOut(sent=False, destination=destination, error=str(exc))

    return ChannelTestOut(sent=True, destination=destination)


# ------------------------------------------------------- notification log


@router.get("/notifications/log", response_model=list[NotificationLogOut])
def notification_log(
    limit: int = Query(default=50, ge=1, le=200),
    _: AppUser = Depends(current_user),
    session: Session = Depends(get_session),
) -> list[NotificationLogOut]:
    """What was sent, skipped or failed, and why (FR-REM-14)."""
    rows = list(
        session.execute(
            select(NotificationLog).order_by(NotificationLog.id.desc()).limit(limit)
        ).scalars()
    )
    return [NotificationLogOut.model_validate(row, from_attributes=True) for row in rows]
