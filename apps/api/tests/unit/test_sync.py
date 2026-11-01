"""Ingestion: mapping Kite payloads and storing them idempotently (FR-SYNC).

Runs against `tests/fixtures/kite_trades_sample.json` and
`kite_orders_sample.json`, which are built from the Kite Connect v3 docs and
marked synthetic. They encode the three things the published payloads get
awkward about: unzoned IST timestamps, a time-only `order_timestamp` on trade
objects, and the two documented/actual field mismatches.
"""

from __future__ import annotations

import datetime as dt
import json
import uuid
from decimal import Decimal

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import BrokerAccount, Fill, KiteOrder, SyncLog
from app.services import sync_service
from app.services.kite_client import TokenExpired
from app.services.kite_mapper import (
    RejectedRow,
    jsonable,
    map_order,
    map_trade,
    parse_timestamp,
)
from app.timezone import IST, ist_date
from tests.conftest import FakeKite

ACCOUNT = uuid.UUID("11111111-1111-1111-1111-111111111111")


def by_trade_id(rows: list[dict], trade_id: str) -> dict:
    return next(row for row in rows if row.get("trade_id") == trade_id)


# ------------------------------------------------------------------ mapping


def test_maps_a_normal_fill(kite_trades: list[dict]) -> None:
    mapped = map_trade(by_trade_id(kite_trades, "10000001"), ACCOUNT)

    assert mapped["kite_trade_id"] == "10000001"
    assert mapped["order_id"] == "200000000000001"
    assert mapped["exchange"] == "NSE"
    assert mapped["tradingsymbol"] == "SBIN"
    assert mapped["instrument_token"] == 779521
    assert mapped["product"] == "CNC"
    assert mapped["side"] == "BUY"
    assert mapped["quantity"] == 10
    assert mapped["source"] == "api"


def test_price_is_decimal_and_exact(kite_trades: list[dict]) -> None:
    """420.65 has no exact float representation; going through str() keeps it."""
    mapped = map_trade(by_trade_id(kite_trades, "10000001"), ACCOUNT)

    assert isinstance(mapped["price"], Decimal)
    assert mapped["price"] == Decimal("420.65")
    assert not isinstance(mapped["price"], float)


def test_filled_at_is_utc_and_trade_date_is_the_ist_day(kite_trades: list[dict]) -> None:
    mapped = map_trade(by_trade_id(kite_trades, "10000001"), ACCOUNT)

    # 09:16:39 IST on 2 Nov is 03:46:39 UTC on 2 Nov.
    assert mapped["filled_at"] == dt.datetime(2026, 11, 2, 3, 46, 39, tzinfo=dt.UTC)
    assert mapped["filled_at"].tzinfo is not None
    assert mapped["trade_date"] == dt.date(2026, 11, 2)


def test_falls_back_to_exchange_timestamp_when_fill_timestamp_is_missing(
    kite_trades: list[dict],
) -> None:
    mapped = map_trade(by_trade_id(kite_trades, "10000003"), ACCOUNT)
    assert mapped["filled_at"] == dt.datetime(2026, 11, 2, 4, 1, 12, tzinfo=dt.UTC)


def test_time_only_order_timestamp_is_never_used_as_a_fill_time() -> None:
    """On a trade object `order_timestamp` is "HH:MM:SS". Parsing it as a
    datetime would silently invent a date."""
    assert parse_timestamp("09:16:39") is None


def test_accepts_instrument_token_as_a_string(kite_trades: list[dict]) -> None:
    """The docs table says string, the examples show a number."""
    mapped = map_trade(by_trade_id(kite_trades, "10000004"), ACCOUNT)
    assert mapped["instrument_token"] == 12345678


def test_accepts_filled_in_place_of_quantity(kite_trades: list[dict]) -> None:
    """The docs table says `filled`, the examples return `quantity`."""
    mapped = map_trade(by_trade_id(kite_trades, "10000005"), ACCOUNT)
    assert mapped["quantity"] == 1


@pytest.mark.parametrize(
    ("trade_id", "reason"),
    [
        ("10000006", "quantity must be positive"),
        ("10000007", "unknown side"),
        ("", "missing trade_id"),
        ("10000009", "missing instrument_token"),
    ],
)
def test_rejection_rules(kite_trades: list[dict], trade_id: str, reason: str) -> None:
    """FR-SYNC-09: these are counted, never stored."""
    with pytest.raises(RejectedRow) as caught:
        map_trade(by_trade_id(kite_trades, trade_id), ACCOUNT)
    assert caught.value.reason == reason


def test_order_mapping_uses_the_full_order_timestamp(kite_orders: list[dict]) -> None:
    mapped = map_order(kite_orders[0], ACCOUNT)

    assert mapped["order_id"] == "200000000000001"
    assert mapped["status"] == "COMPLETE"
    assert mapped["placed_at"] == dt.datetime(2026, 11, 2, 3, 46, 35, tzinfo=dt.UTC)
    assert mapped["price"] == Decimal("420.7")
    assert mapped["average_price"] == Decimal("420.65")


def test_order_without_an_id_is_rejected(kite_orders: list[dict]) -> None:
    with pytest.raises(RejectedRow):
        map_order(kite_orders[-1], ACCOUNT)


def test_raw_payload_survives_json_serialisation() -> None:
    """The SDK puts `datetime` objects inside otherwise-JSON payloads, which
    `json.dumps` refuses and a jsonb column would reject."""
    raw = {
        "trade_id": "1",
        "fill_timestamp": dt.datetime(2026, 11, 2, 9, 16, 39),
        "meta": {"nested": [dt.date(2026, 11, 2), Decimal("1.5")]},
    }
    encoded = json.dumps(jsonable(raw))
    assert "2026-11-02T03:46:39+00:00" in encoded
    assert '"1.5"' in encoded


@pytest.mark.parametrize(
    ("ist_wall_clock", "expected_date"),
    [
        ("2026-11-02 23:59:00", dt.date(2026, 11, 2)),
        ("2026-11-03 00:01:00", dt.date(2026, 11, 3)),
    ],
)
def test_trading_day_boundary_is_ist_not_utc(ist_wall_clock: str, expected_date: dt.date) -> None:
    """NFR-10. At 00:01 IST the UTC date is still the previous day, so a
    trade_date taken from UTC would land on the wrong trading day."""
    moment = parse_timestamp(ist_wall_clock)
    assert moment is not None
    assert ist_date(moment) == expected_date
    assert moment.astimezone(IST).strftime("%Y-%m-%d %H:%M:%S") == ist_wall_clock


# ------------------------------------------------------------------- sync


def count(session: Session, model: type) -> int:
    return int(session.execute(select(func.count()).select_from(model)).scalar_one())


def test_sync_stores_fills_and_orders(
    session: Session,
    connected_account: BrokerAccount,
    kite_trades: list[dict],
    kite_orders: list[dict],
) -> None:
    gateway = FakeKite(trades=kite_trades, orders=kite_orders)

    result = sync_service.run_sync(session, trigger="manual", gateway=gateway)

    # Five of the nine fixture trades are valid; four hit FR-SYNC-09.
    assert result.fills_new == 5
    assert result.fills_dup == 0
    assert result.fills_rejected == 4
    # Four of the five fixture orders have an order_id.
    assert result.orders_upserted == 4
    assert count(session, Fill) == 5
    assert count(session, KiteOrder) == 4


def test_a_second_sync_of_the_same_day_adds_nothing(
    session: Session,
    connected_account: BrokerAccount,
    kite_trades: list[dict],
    kite_orders: list[dict],
) -> None:
    """FR-SYNC-04 and golden scenario S10, the acceptance criterion for M2."""
    gateway = FakeKite(trades=kite_trades, orders=kite_orders)

    first = sync_service.run_sync(session, trigger="manual", gateway=gateway)
    second = sync_service.run_sync(session, trigger="manual", gateway=gateway)

    assert first.fills_new == 5
    assert second.fills_new == 0
    assert second.fills_dup == 5
    assert count(session, Fill) == 5
    # It really did fetch again rather than short-circuiting on a local check.
    assert gateway.calls["trades"] == 2


def test_rejected_rows_are_never_stored(
    session: Session,
    connected_account: BrokerAccount,
    kite_trades: list[dict],
) -> None:
    sync_service.run_sync(session, trigger="manual", gateway=FakeKite(trades=kite_trades))

    stored = set(session.execute(select(Fill.kite_trade_id)).scalars())
    assert stored == {"10000001", "10000002", "10000003", "10000004", "10000005"}
    assert all(quantity > 0 for quantity in session.execute(select(Fill.quantity)).scalars())


def test_stored_fill_keeps_decimal_price_and_utc_time(
    session: Session,
    connected_account: BrokerAccount,
    kite_trades: list[dict],
) -> None:
    sync_service.run_sync(session, trigger="manual", gateway=FakeKite(trades=kite_trades))

    fill = session.execute(select(Fill).where(Fill.kite_trade_id == "10000001")).scalar_one()

    assert isinstance(fill.price, Decimal)
    assert fill.price == Decimal("420.6500")
    assert fill.filled_at == dt.datetime(2026, 11, 2, 3, 46, 39, tzinfo=dt.UTC)
    assert fill.trade_date == dt.date(2026, 11, 2)
    assert fill.source == "api"
    assert fill.raw["tradingsymbol"] == "SBIN"


def test_sync_writes_a_log_row(
    session: Session,
    connected_account: BrokerAccount,
    kite_trades: list[dict],
) -> None:
    result = sync_service.run_sync(session, trigger="manual", gateway=FakeKite(trades=kite_trades))

    log = session.get(SyncLog, result.sync_log_id)
    assert log is not None
    assert log.trigger == "manual"
    # Rejected rows make the run partial, not a clean success (FR-SYNC-10).
    assert log.status == "partial"
    assert log.finished_at is not None
    assert log.fills_new == 5
    assert log.details is not None
    assert "positions" in log.details


def test_sync_without_a_token_is_skipped_not_failed(
    session: Session, account: BrokerAccount, kite_trades: list[dict]
) -> None:
    """FR-SYNC-06: no token means skip and wait for a login, not retry."""
    gateway = FakeKite(trades=kite_trades)

    result = sync_service.run_sync(session, trigger="scheduled", gateway=gateway)

    assert result.status == "skipped_no_token"
    assert count(session, Fill) == 0
    # The clock check spared a pointless call to Zerodha.
    assert "profile" not in gateway.calls


def test_a_rejected_token_marks_the_account_expired(
    session: Session, connected_account: BrokerAccount
) -> None:
    """FR-KITE-06."""
    gateway = FakeKite(profile_raises=TokenExpired("profile"))

    result = sync_service.run_sync(session, trigger="manual", gateway=gateway)

    assert result.status == "skipped_no_token"
    session.refresh(connected_account)
    from app.services import token_store

    assert not token_store.token_may_be_valid(connected_account)


def _take_the_sync_lock_again() -> None:
    """What a second, concurrent sync would do."""
    with sync_service.sync_lock():
        pass


def test_only_one_sync_runs_at_a_time(session: Session) -> None:
    """FR-SYNC-08."""
    with sync_service.sync_lock(), pytest.raises(sync_service.AlreadyRunning):
        _take_the_sync_lock_again()


def test_catchup_sync_does_not_repeat_a_day_already_synced(
    session: Session,
    connected_account: BrokerAccount,
    kite_trades: list[dict],
) -> None:
    """FR-KITE-08 and FR-SYNC-05."""
    gateway = FakeKite(trades=kite_trades)
    sync_service.run_sync(session, trigger="manual", gateway=gateway)

    assert sync_service.run_catchup_sync(session, gateway=gateway) is None
