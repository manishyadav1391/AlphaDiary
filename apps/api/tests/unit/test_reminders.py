"""Reminder evaluation (FR-REM, SRS 7.5).

The six acceptance cases at the end of SRS 5.4 are all stated in terms of a
clock, so every test here injects `now` rather than waiting.
"""

from __future__ import annotations

import datetime as dt
import json

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import BrokerAccount, MarketHoliday, NotificationChannel, NotificationLog
from app.security import encrypt
from app.services import reminders
from app.services.notifier import Message, NotConfigured, SendFailed
from app.timezone import IST

# A Tuesday, and not a holiday.
TRADING_DAY = dt.date(2026, 11, 3)


def at(hour: int, minute: int, day: dt.date = TRADING_DAY) -> dt.datetime:
    """An IST wall-clock moment, as the worker would see it."""
    return dt.datetime(day.year, day.month, day.day, hour, minute, tzinfo=IST)


class FakeChannel:
    name = "email"

    def __init__(self, *, fails: int = 0) -> None:
        self.sent: list[Message] = []
        self.attempts = 0
        self._fails = fails

    def send(self, message: Message) -> None:
        self.attempts += 1
        if self.attempts <= self._fails:
            raise SendFailed("provider said no")
        self.sent.append(message)


@pytest.fixture
def email_channel(session: Session) -> NotificationChannel:
    row = NotificationChannel(
        channel="email",
        enabled=True,
        config_enc=encrypt(json.dumps({"to": "owner@example.test"})),
    )
    session.add(row)
    session.flush()
    return row


@pytest.fixture
def slots(session: Session) -> None:
    reminders.save_slots(session, reminders.DEFAULT_SLOTS)


@pytest.fixture
def channel(monkeypatch: pytest.MonkeyPatch) -> FakeChannel:
    fake = FakeChannel()
    monkeypatch.setattr(reminders, "enabled_channels", lambda session: [fake])
    return fake


@pytest.fixture
def token_invalid(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(reminders, "token_is_live", lambda session: False)


@pytest.fixture
def token_valid(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(reminders, "token_is_live", lambda session: True)


def logs(session: Session) -> list[NotificationLog]:
    return list(session.execute(select(NotificationLog)).scalars())


# -------------------------------------------------- SRS 5.4 acceptance cases


def test_one_email_at_fifteen_hundred_and_none_a_minute_later(
    session: Session, slots: None, channel: FakeChannel, token_invalid: None
) -> None:
    """Case 1: exactly one email for the 15:00 slot, idempotent on re-tick."""
    reminders.tick(session, at(15, 0))
    reminders.tick(session, at(15, 1))

    assert len(channel.sent) == 1
    assert [row.slot_key for row in logs(session)] == ["2026-11-03:first"]
    assert logs(session)[0].status == "sent"


def test_a_valid_token_logs_skipped_and_sends_nothing(
    session: Session, slots: None, channel: FakeChannel, token_valid: None
) -> None:
    """Case 2: after logging in, later slots record skipped_token_valid."""
    reminders.tick(session, at(15, 30))
    reminders.tick(session, at(15, 40))

    assert channel.sent == []
    statuses = {row.slot_key: row.status for row in logs(session)}
    assert statuses == {
        "2026-11-03:second": "skipped_token_valid",
        "2026-11-03:final": "skipped_token_valid",
    }


def test_the_missed_sync_slot_sends_its_own_message(
    session: Session, slots: None, channel: FakeChannel, token_invalid: None
) -> None:
    """Case 3: the 15:50 slot is the missed-sync alert (FR-REM-08).

    Ticked through the earlier slots first, which is what a running worker
    does, so the 15:50 message is the only new one.
    """
    for hour, minute in ((15, 0), (15, 30), (15, 40)):
        reminders.tick(session, at(hour, minute))
    already_sent = len(channel.sent)

    reminders.tick(session, at(15, 50))

    assert len(channel.sent) == already_sent + 1
    assert "NOT imported" in channel.sent[-1].body
    kinds = {row.slot_key: row.kind for row in logs(session)}
    assert kinds["2026-11-03:missed_sync"] == "missed_sync"


def test_a_cold_start_sends_every_slot_still_inside_its_grace_window(
    session: Session, slots: None, channel: FakeChannel, token_invalid: None
) -> None:
    """A worker started at 15:50 having never ticked finds 15:30, 15:40 and
    15:50 all within their 20-minute windows, and sends all three (SRS 7.5).

    Noisy, but losing a day's trades is worse than three emails, and it only
    happens when the worker has been down.
    """
    reminders.tick(session, at(15, 50))

    assert len(channel.sent) == 3
    assert {row.slot_key for row in logs(session)} == {
        "2026-11-03:second",
        "2026-11-03:final",
        "2026-11-03:missed_sync",
    }


def test_a_slot_missed_by_more_than_the_grace_window_is_not_sent(
    session: Session, slots: None, channel: FakeChannel, token_invalid: None
) -> None:
    """Case 4: a worker restarted at 15:20 does not fire the 15:00 slot, but
    does fire 15:30 when it comes round."""
    reminders.tick(session, at(15, 21))
    assert channel.sent == []

    reminders.tick(session, at(15, 31))
    assert [row.slot_key for row in logs(session)] == ["2026-11-03:second"]


def test_three_failures_are_logged_as_failed(
    session: Session, slots: None, monkeypatch: pytest.MonkeyPatch, token_invalid: None
) -> None:
    """Case 5: three attempts, then `failed` with the error (FR-REM-10)."""
    failing = FakeChannel(fails=99)
    monkeypatch.setattr(reminders, "enabled_channels", lambda s: [failing])

    reminders.tick(session, at(15, 0), sleep=lambda seconds: None)

    assert failing.attempts == 3
    row = logs(session)[0]
    assert row.status == "failed"
    assert row.attempts == 3
    assert "provider said no" in (row.error or "")


def test_nothing_is_sent_on_a_holiday(
    session: Session, slots: None, channel: FakeChannel, token_invalid: None
) -> None:
    """Case 6."""
    session.add(MarketHoliday(trade_date=TRADING_DAY, description="Test holiday"))
    session.flush()

    actions = reminders.tick(session, at(15, 0))

    assert actions == ["not_a_trading_day"]
    assert channel.sent == []
    assert logs(session) == []


# ---------------------------------------------------------- other behaviour


def test_a_special_session_is_still_a_trading_day(
    session: Session, slots: None, channel: FakeChannel, token_invalid: None
) -> None:
    """Muhurat trading: a holiday row flagged as an override still trades
    (FR-REM-01)."""
    session.add(
        MarketHoliday(trade_date=TRADING_DAY, description="Muhurat", is_trading_override=True)
    )
    session.flush()

    reminders.tick(session, at(15, 0))

    assert len(channel.sent) == 1


def test_nothing_is_sent_at_the_weekend(
    session: Session, slots: None, channel: FakeChannel, token_invalid: None
) -> None:
    saturday = dt.date(2026, 11, 7)

    assert reminders.tick(session, at(15, 0, saturday)) == ["not_a_trading_day"]


def test_a_successful_sync_stops_reminders_for_the_day(
    session: Session,
    slots: None,
    channel: FakeChannel,
    token_invalid: None,
    connected_account: BrokerAccount,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """FR-REM-05."""
    monkeypatch.setattr(reminders.sync_service, "synced_today", lambda s, now=None: True)

    assert reminders.tick(session, at(15, 0)) == ["synced_today"]
    assert channel.sent == []


def test_skip_today_stops_reminders(
    session: Session, slots: None, channel: FakeChannel, token_invalid: None
) -> None:
    """FR-REM-05 and FR-REM-14."""
    reminders.skip_today(session, TRADING_DAY)

    assert reminders.tick(session, at(15, 0)) == ["skipped_today"]
    assert channel.sent == []


def test_skipping_one_day_does_not_skip_the_next(
    session: Session, slots: None, channel: FakeChannel, token_invalid: None
) -> None:
    reminders.skip_today(session, TRADING_DAY)

    reminders.tick(session, at(15, 0, dt.date(2026, 11, 4)))

    assert len(channel.sent) == 1


def test_a_disabled_slot_never_fires(
    session: Session, channel: FakeChannel, token_invalid: None
) -> None:
    """21:00 is off by default (FR-REM-02)."""
    reminders.save_slots(session, reminders.DEFAULT_SLOTS)

    reminders.tick(session, at(21, 0))

    assert channel.sent == []


def test_the_message_names_the_minutes_left_and_the_link(
    session: Session, slots: None, channel: FakeChannel, token_invalid: None
) -> None:
    """FR-REM-07, Appendix C."""
    reminders.tick(session, at(15, 0))

    body = channel.sent[0].body
    assert "45 minutes" in body
    assert "/connect" in body


def test_a_message_after_the_sync_window_says_so(
    session: Session, slots: None, channel: FakeChannel, token_invalid: None
) -> None:
    reminders.tick(session, at(18, 0))

    assert "sync window has passed" in channel.sent[0].body


def test_no_message_ever_carries_money_or_a_token(
    session: Session, slots: None, channel: FakeChannel, token_invalid: None
) -> None:
    """FR-REM-07 and NFR-04."""
    for hour, minute in ((15, 0), (15, 30), (15, 50)):
        reminders.tick(session, at(hour, minute))

    for message in channel.sent:
        text = f"{message.subject} {message.body}".lower()
        assert "₹" not in text
        for forbidden in ("token", "p&l", "balance", "password", "secret"):
            assert forbidden not in text


def test_a_misconfigured_channel_fails_without_retrying(
    session: Session, slots: None, monkeypatch: pytest.MonkeyPatch, token_invalid: None
) -> None:
    """Waiting five minutes to discover the API key is missing helps nobody."""

    class Unconfigured:
        name = "email"

        def send(self, message: Message) -> None:
            raise NotConfigured("no api key")

    monkeypatch.setattr(reminders, "enabled_channels", lambda s: [Unconfigured()])

    reminders.tick(session, at(15, 0))

    row = logs(session)[0]
    assert row.status == "failed"
    assert "no api key" in (row.error or "")


def test_the_email_destination_is_read_from_the_encrypted_config(
    session: Session, email_channel: NotificationChannel
) -> None:
    """FR-KITE-01's rule applies here too: the destination is stored
    encrypted, never in plain text."""
    assert b"owner@example.test" not in (email_channel.config_enc or b"")

    channels = reminders.enabled_channels(session)

    assert len(channels) == 1
    assert channels[0].name == "email"


def test_a_disabled_channel_is_not_used(
    session: Session, email_channel: NotificationChannel
) -> None:
    email_channel.enabled = False
    session.flush()

    assert reminders.enabled_channels(session) == []


@pytest.mark.parametrize(
    ("hour", "expected"),
    [(22, True), (23, True), (3, True), (6, True), (7, False), (15, False)],
)
def test_quiet_hours(hour: int, expected: bool) -> None:
    """FR-REM-11: nothing between 22:00 and 07:00 IST."""
    assert reminders.in_quiet_hours(at(hour, 0)) is expected
