"""Sending reminders (FR-REM-06, FR-REM-07, FR-REM-10).

Email goes through Resend's HTTPS API rather than SMTP. `httpx` is already a
dependency, so this needs no SDK and no SMTP credentials to store.

Message text comes from SRS Appendix C and carries no P&L, no balances, no
tokens and no secrets. A failure in one channel never blocks another
(FR-REM-06), and each gets three attempts at 30 s, 2 min and 5 min
(FR-REM-10).
"""

from __future__ import annotations

import contextlib
import datetime as dt
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

import httpx

from app.config import get_settings

logger = logging.getLogger("tj.notifier")

RESEND_ENDPOINT = "https://api.resend.com/emails"

# FR-REM-10: three attempts, with these waits between them.
RETRY_WAITS = (30.0, 120.0, 300.0)


class NotConfigured(Exception):
    """The channel has no credentials or no destination."""


class SendFailed(Exception):
    """The provider rejected the message or could not be reached."""


@dataclass(frozen=True)
class Message:
    subject: str
    body: str


class Channel(Protocol):
    """What the reminder engine needs. Telegram and WhatsApp will implement
    the same shape when they land (FR-REM-12, FR-REM-13)."""

    name: str

    def send(self, message: Message) -> None: ...


# ------------------------------------------------------------- templates


def minutes_until(now: dt.datetime, target: dt.time, tz: dt.tzinfo) -> int:
    local = now.astimezone(tz)
    due = local.replace(hour=target.hour, minute=target.minute, second=0, microsecond=0)
    return int((due - local).total_seconds() // 60)


def reminder_message(minutes_left: int, link: str) -> Message:
    """SRS Appendix C, before and after the sync window."""
    if minutes_left > 0:
        return Message(
            subject="Action needed: log in to Zerodha before 3:45 PM",
            body=(
                "Your Zerodha session is not connected today, so your trades "
                f"cannot be imported. About {minutes_left} minutes are left "
                f"before the 3:45 PM sync. Connect now: {link}"
            ),
        )
    return Message(
        subject="Action needed: log in to Zerodha",
        body=(
            "The 3:45 PM sync window has passed and today's trades are not "
            f"imported yet. Log in now to import them: {link}"
        ),
    )


def missed_sync_message(link: str) -> Message:
    """FR-REM-08."""
    return Message(
        subject="Missed sync: today's trades were not imported",
        body=f"Missed sync: today's trades were NOT imported. Log in now: {link}",
    )


def sync_result_message(fills_new: int, trades: int) -> Message:
    """FR-REM-09. Counts only; never P&L unless the setting is on."""
    return Message(
        subject="Sync finished",
        body=f"{fills_new} new fills, {trades} trades.",
    )


def test_message(link: str) -> Message:
    return Message(
        subject="Test message from your trading journal",
        body=f"Notifications are working. Your journal is at {link}",
    )


# --------------------------------------------------------------- channels


class ResendEmail:
    """Email via Resend.

    Without a verified domain, Resend sends from `onboarding@resend.dev` and
    delivers only to the address on the account. A 403 saying so is a
    configuration problem, not a transient one, so it is not retried.
    """

    name = "email"

    def __init__(self, to: str | None = None, timeout: float = 20.0) -> None:
        settings = get_settings()
        self._key = settings.resend_api_key.get_secret_value()
        self._from = settings.resend_from
        self._to = to or settings.reminder_email_to
        self._timeout = timeout

    def send(self, message: Message) -> None:
        if not self._key or not self._to:
            raise NotConfigured("Resend API key or destination address is missing")

        try:
            response = httpx.post(
                RESEND_ENDPOINT,
                timeout=self._timeout,
                headers={"Authorization": f"Bearer {self._key}"},
                json={
                    "from": self._from,
                    "to": [self._to],
                    "subject": message.subject,
                    "text": message.body,
                },
            )
        except httpx.HTTPError as exc:
            raise SendFailed(type(exc).__name__) from exc

        if response.status_code >= 400:
            # The status and provider error name are safe to record; the API
            # key is never echoed back and never logged.
            detail = ""
            with contextlib.suppress(ValueError):
                detail = str(response.json().get("message", ""))[:200]
            raise SendFailed(f"HTTP {response.status_code}: {detail}")


def send_with_retry(
    channel: Channel,
    message: Message,
    *,
    sleep: Callable[[float], None] = time.sleep,
    attempts: int = len(RETRY_WAITS),
) -> None:
    """Three attempts, then give up and let the caller log `failed`.

    A misconfiguration is raised immediately: waiting five minutes to find out
    the API key is missing helps nobody.
    """
    last: Exception | None = None
    for attempt in range(attempts):
        try:
            channel.send(message)
            return
        except NotConfigured:
            raise
        except SendFailed as exc:
            last = exc
            logger.warning(
                "Notification attempt failed",
                extra={"event": "notify_retry", "count": attempt + 1},
            )
            if attempt < attempts - 1:
                sleep(RETRY_WAITS[attempt])

    raise SendFailed(str(last) if last else "unknown error")
