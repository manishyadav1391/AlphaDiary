"""Fetch the day's orders and trades from Kite and store them (FR-SYNC).

Follows the procedure in SRS 7.1, stopping where this milestone stops: raw
ingestion is complete, and the matcher, charges and daily summary are named
hooks that M3 and M4 fill in.

Idempotency (FR-SYNC-04) does not rely on comparing what we fetched against
what we hold. Fills are inserted with `ON CONFLICT (account_id,
kite_trade_id) DO NOTHING ... RETURNING id`, so the new and duplicate counts
are whatever the database actually did. That stays correct even if two syncs
overlap, which a read-then-write check would not.
"""

from __future__ import annotations

import datetime as dt
import logging
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.db import engine
from app.models import BrokerAccount, Fill, KiteOrder, SyncLog
from app.services import charges, matcher, metrics, token_store
from app.services.kite_client import KiteGateway, TokenExpired
from app.services.kite_mapper import RejectedRow, jsonable, map_order, map_trade
from app.timezone import ist_date, now_utc

logger = logging.getLogger("tj.sync")

# Arbitrary but fixed: only this application takes this lock (FR-SYNC-08).
SYNC_LOCK_KEY = 7_421_990_113_001

# Columns refreshed when an order we already hold comes back changed.
_ORDER_UPDATE_COLUMNS = (
    "exchange_order_id",
    "exchange",
    "tradingsymbol",
    "instrument_token",
    "transaction_type",
    "product",
    "order_type",
    "status",
    "quantity",
    "filled_quantity",
    "price",
    "trigger_price",
    "average_price",
    "placed_at",
    "raw",
)


class AlreadyRunning(Exception):
    """Another sync holds the lock (FR-SYNC-08)."""


@dataclass
class SyncResult:
    sync_log_id: UUID
    status: str
    fills_new: int = 0
    fills_dup: int = 0
    fills_rejected: int = 0
    orders_upserted: int = 0
    error: str | None = None


@contextmanager
def sync_lock() -> Iterator[None]:
    """Hold a session-level advisory lock for the whole sync.

    It lives on its own autocommit connection because the sync commits part
    way through, and a Session hands its connection back to the pool on every
    commit, which would drop a lock taken on it.
    """
    connection = engine.connect().execution_options(isolation_level="AUTOCOMMIT")
    acquired = False
    try:
        acquired = bool(
            connection.execute(
                text("select pg_try_advisory_lock(:key)"), {"key": SYNC_LOCK_KEY}
            ).scalar()
        )
        if not acquired:
            raise AlreadyRunning
        yield
    finally:
        if acquired:
            connection.execute(text("select pg_advisory_unlock(:key)"), {"key": SYNC_LOCK_KEY})
        connection.close()


# --------------------------------------------------------------- ingestion


def upsert_orders(session: Session, rows: list[dict[str, Any]]) -> int:
    """Insert or refresh `kite_order` rows. Returns how many were sent."""
    if not rows:
        return 0

    # ON CONFLICT DO UPDATE cannot touch the same row twice in one statement,
    # so the batch is deduplicated on the conflict target first.
    deduplicated: dict[str, dict[str, Any]] = {row["order_id"]: row for row in rows}
    values = list(deduplicated.values())

    statement = pg_insert(KiteOrder).values(values)
    statement = statement.on_conflict_do_update(
        index_elements=[KiteOrder.order_id],
        set_={name: getattr(statement.excluded, name) for name in _ORDER_UPDATE_COLUMNS},
    )
    session.execute(statement)
    return len(values)


def upsert_fills(session: Session, rows: list[dict[str, Any]]) -> tuple[int, int]:
    """Insert new fills only. Returns (new, duplicate) (FR-SYNC-04)."""
    if not rows:
        return 0, 0

    statement = (
        pg_insert(Fill)
        .values(rows)
        .on_conflict_do_nothing(index_elements=[Fill.account_id, Fill.kite_trade_id])
        .returning(Fill.id)
    )
    inserted = len(session.execute(statement).scalars().all())
    return inserted, len(rows) - inserted


def map_trades(
    raw_trades: list[dict[str, Any]], account_id: UUID
) -> tuple[list[dict[str, Any]], list[str]]:
    """Map what we can; collect the reason for everything we cannot (FR-SYNC-09)."""
    mapped: list[dict[str, Any]] = []
    rejected: list[str] = []
    for raw in raw_trades:
        try:
            mapped.append(map_trade(raw, account_id))
        except RejectedRow as exc:
            rejected.append(exc.reason)
    return mapped, rejected


def map_orders(
    raw_orders: list[dict[str, Any]], account_id: UUID
) -> tuple[list[dict[str, Any]], list[str]]:
    mapped: list[dict[str, Any]] = []
    rejected: list[str] = []
    for raw in raw_orders:
        try:
            mapped.append(map_order(raw, account_id))
        except RejectedRow as exc:
            rejected.append(exc.reason)
    return mapped, rejected


# --------------------------------------------------------- post-processing


def process_touched(
    session: Session,
    account_id: UUID,
    touched: set[tuple[UUID, int, str]],
    order_ids: set[str],
) -> None:
    """Rebuild groups, price them and roll up the day (SRS 7.1, steps 3 to 6).

    Order matters: groups must exist before their charges can be attributed,
    and charges must be attributed before the daily summary adds up net P&L.
    All of it runs inside the caller's transaction, so a failure leaves no
    half-built groups (NFR-03).
    """
    if not touched:
        return

    groups = matcher.rebuild_groups(session, touched)
    charges.compute_charges(session, order_ids)
    charges.apply_charges_to_groups(session, touched)
    metrics.rebuild_daily_summary(session, account_id, {g.trade_date for g in groups})


# --------------------------------------------------------------- the sync


def _start_log(session: Session, trigger: str, account: BrokerAccount | None) -> SyncLog:
    log = SyncLog(
        account_id=account.id if account else None,
        trigger=trigger,
        status="running",
        started_at=now_utc(),
    )
    session.add(log)
    session.flush()
    return log


def _finish_log(
    session: Session,
    log: SyncLog,
    status: str,
    *,
    fills_new: int = 0,
    fills_dup: int = 0,
    fills_rejected: int = 0,
    orders_upserted: int = 0,
    error: str | None = None,
    details: dict[str, Any] | None = None,
) -> SyncResult:
    log.status = status
    log.finished_at = now_utc()
    log.fills_new = fills_new
    log.fills_dup = fills_dup
    log.fills_rejected = fills_rejected
    log.orders_upserted = orders_upserted
    log.error = error
    if details is not None:
        log.details = details
    session.flush()
    session.commit()
    return SyncResult(
        sync_log_id=log.id,
        status=status,
        fills_new=fills_new,
        fills_dup=fills_dup,
        fills_rejected=fills_rejected,
        orders_upserted=orders_upserted,
        error=error,
    )


def _token_is_live(session: Session, account: BrokerAccount, gateway: KiteGateway) -> bool:
    """The estimated expiry is only a filter; `profile()` is the real check."""
    if not token_store.token_may_be_valid(account):
        return False
    try:
        gateway.profile()
    except TokenExpired:
        token_store.mark_token_expired(session, account)
        return False
    return True


def run_sync(
    session: Session,
    *,
    trigger: str = "manual",
    gateway: KiteGateway | None = None,
) -> SyncResult:
    """Run one sync. Raises `AlreadyRunning` if another holds the lock."""
    with sync_lock():
        account = token_store.require_account(session)
        log = _start_log(session, trigger, account)
        # Make the running row visible to /sync/status straight away.
        session.commit()

        client = gateway if gateway is not None else token_store.build_client(session, account)

        if not _token_is_live(session, account, client):
            logger.info("Sync skipped: no valid token", extra={"event": "sync_skipped_no_token"})
            return _finish_log(session, log, "skipped_no_token")

        try:
            raw_orders = list(client.orders())
            raw_trades = list(client.trades())
            positions = client.positions()
            holdings = list(client.holdings())
        except TokenExpired:
            token_store.mark_token_expired(session, account)
            return _finish_log(session, log, "skipped_no_token")
        except Exception as exc:
            session.rollback()
            logger.error("Sync failed while fetching", extra={"event": "sync_fetch_failed"})
            return _finish_log(
                session, log, "failed", error=f"{type(exc).__name__} while fetching from Kite"
            )

        order_rows, rejected_orders = map_orders(raw_orders, account.id)
        fill_rows, rejected_fills = map_trades(raw_trades, account.id)

        try:
            orders_upserted = upsert_orders(session, order_rows)
            fills_new, fills_dup = upsert_fills(session, fill_rows)

            touched = {
                (row["account_id"], row["instrument_token"], row["product"]) for row in fill_rows
            }
            # Charges are priced from fills, so the order ids come from the
            # fills themselves: a CSV-imported fill may have no order row.
            order_ids = {row["order_id"] for row in fill_rows if row["order_id"]}
            order_ids |= {row["order_id"] for row in order_rows}
            process_touched(session, account.id, touched, order_ids)
        except Exception as exc:
            session.rollback()
            logger.error("Sync failed while storing", extra={"event": "sync_store_failed"})
            return _finish_log(
                session, log, "failed", error=f"{type(exc).__name__} while storing fills"
            )

        details = {
            # Snapshots for reconciliation; no UI in version 1 (FR-SYNC-11).
            "positions": jsonable(positions),
            "holdings": jsonable(holdings),
            "rejected_fill_reasons": sorted(set(rejected_fills)),
            "rejected_order_reasons": sorted(set(rejected_orders)),
        }
        status = "partial" if (rejected_fills or rejected_orders) else "success"
        logger.info(
            "Sync finished",
            extra={"event": "sync_finished", "count": fills_new, "status_code": None},
        )
        return _finish_log(
            session,
            log,
            status,
            fills_new=fills_new,
            fills_dup=fills_dup,
            fills_rejected=len(rejected_fills),
            orders_upserted=orders_upserted,
            details=details,
        )


# ---------------------------------------------------------------- queries


def is_running(session: Session) -> bool:
    return (
        session.execute(
            select(SyncLog.id).where(SyncLog.status == "running").limit(1)
        ).scalar_one_or_none()
        is not None
    )


def synced_today(session: Session, *, now: dt.datetime | None = None) -> bool:
    """Whether a sync has succeeded for today's IST trading day (FR-SYNC-05)."""
    today = ist_date(now or now_utc())
    for log in session.execute(
        select(SyncLog).where(SyncLog.status.in_(("success", "partial")))
    ).scalars():
        if ist_date(log.started_at) == today:
            return True
    return False


def last_log(session: Session) -> SyncLog | None:
    return session.execute(
        select(SyncLog).order_by(SyncLog.started_at.desc()).limit(1)
    ).scalar_one_or_none()


def recent_logs(session: Session, limit: int = 20) -> list[SyncLog]:
    return list(
        session.execute(select(SyncLog).order_by(SyncLog.started_at.desc()).limit(limit)).scalars()
    )


def run_catchup_sync(session: Session, *, gateway: KiteGateway | None = None) -> SyncResult | None:
    """After a successful connect, sync at once unless today is already done
    (FR-KITE-08, FR-SYNC-05). Returns None when nothing was needed."""
    if synced_today(session):
        return None
    try:
        return run_sync(session, trigger="login_catchup", gateway=gateway)
    except AlreadyRunning:
        return None
