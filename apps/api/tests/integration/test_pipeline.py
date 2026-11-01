"""Sync to net P&L, end to end (SRS 7.1).

Proves the four stages hand over correctly: fills are ingested, matched into
groups, priced from the shipped rate set, and rolled up into daily_summary.
"""

from __future__ import annotations

import datetime as dt
import json
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import BrokerAccount, ChargeRateSet, DailySummary, OrderCharge, TradeGroup
from app.services import sync_service
from tests.conftest import FakeKite

SEED = Path(__file__).resolve().parents[3] / "seed" / "charge_rates.json"
TRADE_DAY = dt.date(2026, 11, 2)


@pytest.fixture
def rate_set(session: Session) -> ChargeRateSet:
    config = json.loads(SEED.read_text(encoding="utf-8"))
    row = ChargeRateSet(
        effective_from=dt.date.fromisoformat(config["effective_from"]),
        label=str(config["label"]),
        config=config,
    )
    session.add(row)
    session.flush()
    return row


def test_sync_produces_priced_trade_groups(
    session: Session,
    connected_account: BrokerAccount,
    rate_set: ChargeRateSet,
    kite_trades: list[dict],
    kite_orders: list[dict],
) -> None:
    sync_service.run_sync(
        session, trigger="manual", gateway=FakeKite(trades=kite_trades, orders=kite_orders)
    )

    groups = list(session.execute(select(TradeGroup)).scalars())

    # SBIN round trip, the NIFTY option round trip, and the open MCX future.
    assert len(groups) == 3
    assert sum(1 for g in groups if g.status == "closed") == 2
    assert sum(1 for g in groups if g.status == "open") == 1


def test_option_round_trip_matches_the_srs_worked_example(
    session: Session,
    connected_account: BrokerAccount,
    rate_set: ChargeRateSet,
    kite_trades: list[dict],
    kite_orders: list[dict],
) -> None:
    """Buy 75 at 112.40, sell 75 at 121.15: gross 656.25, as in SRS 8."""
    sync_service.run_sync(
        session, trigger="manual", gateway=FakeKite(trades=kite_trades, orders=kite_orders)
    )

    group = session.execute(
        select(TradeGroup).where(TradeGroup.tradingsymbol == "NIFTY26NOV24500CE")
    ).scalar_one()

    assert group.direction == "LONG"
    assert group.status == "closed"
    assert group.gross_pnl == Decimal("656.25")
    assert group.avg_entry == Decimal("112.4000")
    assert group.avg_exit == Decimal("121.1500")
    assert group.is_intraday is True


def test_net_pnl_is_gross_less_charges(
    session: Session,
    connected_account: BrokerAccount,
    rate_set: ChargeRateSet,
    kite_trades: list[dict],
    kite_orders: list[dict],
) -> None:
    sync_service.run_sync(
        session, trigger="manual", gateway=FakeKite(trades=kite_trades, orders=kite_orders)
    )

    for group in session.execute(select(TradeGroup).where(TradeGroup.status == "closed")).scalars():
        assert group.charges_total > Decimal("0")
        assert group.net_pnl == group.gross_pnl - group.charges_total
        assert isinstance(group.net_pnl, Decimal)


def test_every_priced_order_has_a_segment_and_a_positive_total(
    session: Session,
    connected_account: BrokerAccount,
    rate_set: ChargeRateSet,
    kite_trades: list[dict],
    kite_orders: list[dict],
) -> None:
    sync_service.run_sync(
        session, trigger="manual", gateway=FakeKite(trades=kite_trades, orders=kite_orders)
    )

    priced = list(session.execute(select(OrderCharge)).scalars())

    assert priced
    assert {row.segment_key for row in priced} <= {
        "eq_delivery",
        "eq_intraday",
        "opt",
        "comm_fut",
    }
    for row in priced:
        assert row.total > Decimal("0")
        assert row.total == (
            row.brokerage
            + row.stt_ctt
            + row.exchange_txn
            + row.sebi
            + row.stamp
            + row.other_levy
            + row.gst
        )


def test_daily_summary_counts_closed_groups_only(
    session: Session,
    connected_account: BrokerAccount,
    rate_set: ChargeRateSet,
    kite_trades: list[dict],
    kite_orders: list[dict],
) -> None:
    """Scenario S7: the open MCX position is excluded from statistics."""
    sync_service.run_sync(
        session, trigger="manual", gateway=FakeKite(trades=kite_trades, orders=kite_orders)
    )

    summary = session.execute(
        select(DailySummary).where(DailySummary.trade_date == TRADE_DAY)
    ).scalar_one()

    closed = list(
        session.execute(
            select(TradeGroup).where(
                TradeGroup.status == "closed", TradeGroup.trade_date == TRADE_DAY
            )
        ).scalars()
    )

    assert summary.trades_count == 2
    assert summary.net_pnl == sum(g.net_pnl for g in closed)
    assert summary.gross_pnl == sum(g.gross_pnl for g in closed)
    assert summary.charges == sum(g.charges_total for g in closed)
    assert summary.wins + summary.losses + summary.breakeven == summary.trades_count


def test_a_second_sync_leaves_the_groups_identical(
    session: Session,
    connected_account: BrokerAccount,
    rate_set: ChargeRateSet,
    kite_trades: list[dict],
    kite_orders: list[dict],
) -> None:
    """Idempotent end to end, not only at the ingestion layer (NFR-03)."""
    gateway = FakeKite(trades=kite_trades, orders=kite_orders)

    sync_service.run_sync(session, trigger="manual", gateway=gateway)
    before = _snapshot(session)
    sync_service.run_sync(session, trigger="manual", gateway=gateway)
    after = _snapshot(session)

    assert before == after


def _snapshot(session: Session) -> list[tuple]:
    return sorted(
        (g.group_key, g.status, g.gross_pnl, g.charges_total, g.net_pnl)
        for g in session.execute(select(TradeGroup)).scalars()
    )
