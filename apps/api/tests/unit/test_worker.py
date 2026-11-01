"""The background worker: scheduled sync, heartbeat and holidays."""

from __future__ import annotations

import datetime as dt
import json

import pytest
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import BrokerAccount, MarketHoliday
from app.services import holidays, storage
from app.services.notifier import (
    Message,
    SendFailed,
    minutes_until,
    missed_sync_message,
    reminder_message,
    send_with_retry,
)
from app.timezone import IST
from app.worker import WorkerState, beat, run_once, sync_is_due

TRADING_DAY = dt.date(2026, 11, 3)


def at(hour: int, minute: int, day: dt.date = TRADING_DAY) -> dt.datetime:
    return dt.datetime(day.year, day.month, day.day, hour, minute, tzinfo=IST)


# ------------------------------------------------------------ scheduled sync


def test_the_sync_is_due_just_after_the_configured_time() -> None:
    """FR-SYNC-02."""
    state = WorkerState()

    assert sync_is_due(at(15, 45), state) is True
    assert sync_is_due(at(15, 44), state) is False


def test_the_sync_runs_once_a_day() -> None:
    state = WorkerState()
    assert sync_is_due(at(15, 45), state) is True

    state.sync_attempted_on = TRADING_DAY

    assert sync_is_due(at(15, 50), state) is False
    assert sync_is_due(at(15, 45, dt.date(2026, 11, 4)), state) is True


def test_a_worker_started_hours_late_does_not_fire_the_sync() -> None:
    """Outside the grace window the sync is skipped rather than run at 18:00
    as though it were 15:45."""
    assert sync_is_due(at(18, 0), WorkerState()) is False


def test_no_sync_on_a_holiday(session: Session) -> None:
    session.add(MarketHoliday(trade_date=TRADING_DAY, description="Test holiday"))
    session.flush()
    state = WorkerState()

    run_once(session, at(15, 45), state)

    assert state.sync_attempted_on is None


def test_the_tick_reports_what_it_did(
    session: Session, connected_account: BrokerAccount, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.services import sync_service

    monkeypatch.setattr(
        sync_service,
        "run_sync",
        lambda s, trigger="manual", gateway=None: sync_service.SyncResult(
            sync_log_id=connected_account.id, status="success"
        ),
    )
    state = WorkerState()

    actions = run_once(session, at(15, 45), state)

    assert "sync:success" in actions


# ----------------------------------------------------------------- heartbeat


def test_the_heartbeat_is_skipped_when_no_url_is_set() -> None:
    """NFR-07. The placeholder in .env.example must not be pinged."""
    assert beat(WorkerState(), at(9, 0)) is False


def test_the_heartbeat_waits_its_interval(monkeypatch: pytest.MonkeyPatch) -> None:
    pings: list[str] = []
    settings = get_settings()
    monkeypatch.setattr(settings, "heartbeat_url", "https://hc-ping.test/abc")
    monkeypatch.setattr("app.worker.httpx.get", lambda url, timeout=10.0: pings.append(url))
    state = WorkerState()

    assert beat(state, at(9, 0)) is True
    # One minute later is inside the five-minute interval.
    assert beat(state, at(9, 1)) is False
    assert beat(state, at(9, 6)) is True
    assert len(pings) == 2


# ------------------------------------------------------------------ holidays


def test_the_nse_payload_parses_into_holiday_rows() -> None:
    """The exchange's own shape, as returned by the CM segment."""
    payload = {
        "CM": [
            {"tradingDate": "26-Jan-2026", "description": "Republic Day"},
            {"tradingDate": "08-Nov-2026", "description": "Diwali Laxmi Pujan*"},
            {"tradingDate": "not a date", "description": "junk"},
        ],
        "FO": [{"tradingDate": "01-Jan-2026", "description": "ignored segment"}],
    }

    rows = holidays.parse_rows(payload)

    assert len(rows) == 2
    assert rows[0] == {
        "trade_date": dt.date(2026, 1, 26),
        "description": "Republic Day",
        "is_trading_override": False,
    }
    # A trailing asterisk is NSE's marker for a special session.
    assert rows[1]["trade_date"] == dt.date(2026, 11, 8)
    assert rows[1]["description"] == "Diwali Laxmi Pujan"
    assert rows[1]["is_trading_override"] is True


def test_weekdays_are_trading_days_and_weekends_are_not(session: Session) -> None:
    assert holidays.is_trading_day(session, dt.date(2026, 11, 3)) is True
    assert holidays.is_trading_day(session, dt.date(2026, 11, 7)) is False
    assert holidays.is_trading_day(session, dt.date(2026, 11, 8)) is False


def test_a_stored_holiday_is_not_a_trading_day(session: Session) -> None:
    session.add(MarketHoliday(trade_date=dt.date(2026, 11, 3), description="X"))
    session.flush()

    assert holidays.is_trading_day(session, dt.date(2026, 11, 3)) is False


def test_an_override_makes_a_sunday_trade(session: Session) -> None:
    session.add(
        MarketHoliday(
            trade_date=dt.date(2026, 11, 8), description="Muhurat", is_trading_override=True
        )
    )
    session.flush()

    assert holidays.is_trading_day(session, dt.date(2026, 11, 8)) is True


def test_storing_holidays_is_idempotent(session: Session) -> None:
    rows = [
        {
            "trade_date": dt.date(2026, 1, 26),
            "description": "Republic Day",
            "is_trading_override": False,
        },
    ]

    holidays.store(session, rows)
    holidays.store(session, rows)

    assert session.get(MarketHoliday, dt.date(2026, 1, 26)) is not None


def test_trading_days_between_skips_weekends_and_holidays(session: Session) -> None:
    session.add(MarketHoliday(trade_date=dt.date(2026, 11, 4), description="X"))
    session.flush()

    days = holidays.trading_days_between(session, dt.date(2026, 11, 2), dt.date(2026, 11, 8))

    assert days == [
        dt.date(2026, 11, 2),
        dt.date(2026, 11, 3),
        dt.date(2026, 11, 5),
        dt.date(2026, 11, 6),
    ]


# ------------------------------------------------------------------ messages


def test_minutes_until_the_sync() -> None:
    assert minutes_until(at(15, 0), dt.time(15, 45), IST) == 45
    assert minutes_until(at(16, 0), dt.time(15, 45), IST) == -15


def test_the_before_and_after_templates_differ() -> None:
    before = reminder_message(45, "https://example.test/connect")
    after = reminder_message(-15, "https://example.test/connect")

    assert "45 minutes" in before.body
    assert "sync window has passed" in after.body
    assert "/connect" in before.body and "/connect" in after.body


def test_the_missed_sync_alert_is_explicit() -> None:
    message = missed_sync_message("https://example.test/connect")

    assert "NOT imported" in message.body


def test_retries_stop_after_three_attempts() -> None:
    """FR-REM-10."""
    waits: list[float] = []

    class Always:
        name = "email"

        def send(self, message: Message) -> None:
            raise SendFailed("nope")

    with pytest.raises(SendFailed):
        send_with_retry(Always(), Message("s", "b"), sleep=waits.append)

    # Two waits between three attempts, at 30 s and 2 minutes.
    assert waits == [30.0, 120.0]


def test_a_retry_that_succeeds_stops_early() -> None:
    attempts = {"n": 0}

    class Flaky:
        name = "email"

        def send(self, message: Message) -> None:
            attempts["n"] += 1
            if attempts["n"] < 2:
                raise SendFailed("first one failed")

    send_with_retry(Flaky(), Message("s", "b"), sleep=lambda seconds: None)

    assert attempts["n"] == 2


# ------------------------------------------------------------------- storage


def test_the_object_key_follows_the_srs_layout() -> None:
    """FR-JRN-07: screenshots/{trade_group_id}/{uuid}.{ext}."""
    key = storage.build_object_key("abc-123", "image/webp")

    assert key.startswith("screenshots/abc-123/")
    assert key.endswith(".webp")


def test_two_keys_for_one_trade_never_collide() -> None:
    first = storage.build_object_key("abc-123", "image/png")
    second = storage.build_object_key("abc-123", "image/png")

    assert first != second


def test_an_unsupported_image_type_is_refused() -> None:
    with pytest.raises(storage.StorageError):
        storage.build_object_key("abc-123", "image/gif")


def test_a_presigned_upload_url_is_scoped_and_expiring(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict = {}

    class FakeS3:
        def generate_presigned_url(self, operation, Params, ExpiresIn):  # noqa: N803
            captured.update(operation=operation, params=Params, expires=ExpiresIn)
            return "https://bucket.example.test/signed"

    monkeypatch.setattr(storage, "_client", lambda: FakeS3())

    result = storage.presign_upload("abc-123", "image/webp", expires_in=300)

    assert captured["operation"] == "put_object"
    assert captured["params"]["ContentType"] == "image/webp"
    assert captured["expires"] == 300
    assert result.headers == {"Content-Type": "image/webp"}
    assert result.url == "https://bucket.example.test/signed"


def test_a_presigned_read_url_expires_in_five_minutes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict = {}

    class FakeS3:
        def generate_presigned_url(self, operation, Params, ExpiresIn):  # noqa: N803
            captured.update(operation=operation, expires=ExpiresIn)
            return "https://bucket.example.test/read"

    monkeypatch.setattr(storage, "_client", lambda: FakeS3())

    storage.presign_download("screenshots/abc/one.webp")

    assert captured["operation"] == "get_object"
    assert captured["expires"] == 300


def test_the_snapshot_round_trips(tmp_path) -> None:
    rows = [
        {"trade_date": dt.date(2026, 11, 8), "description": "Muhurat", "is_trading_override": True},
    ]
    path = tmp_path / "market_holidays.json"

    holidays.save_snapshot(path, rows)
    loaded = holidays.load_snapshot(path)

    assert loaded == rows
    assert "holiday-master" in json.loads(path.read_text())["_source"]
