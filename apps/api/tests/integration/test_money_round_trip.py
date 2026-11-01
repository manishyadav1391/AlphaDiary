"""Money survives a real database round trip as an exact Decimal."""

from __future__ import annotations

import datetime as dt
import uuid
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import TradeGroup


def _group(**overrides: object) -> TradeGroup:
    base: dict[str, object] = {
        "group_key": f"test:{uuid.uuid4()}",
        "account_id": uuid.uuid4(),
        "instrument_token": 256265,
        "tradingsymbol": "NIFTY",
        "exchange": "NFO",
        "asset_class": "fno",
        "product": "MIS",
        "direction": "LONG",
        "status": "closed",
        "qty_max": 100,
        "open_qty": 0,
        "opened_at": dt.datetime(2026, 11, 2, 4, 1, tzinfo=dt.UTC),
        "closed_at": dt.datetime(2026, 11, 2, 5, 12, tzinfo=dt.UTC),
        "trade_date": dt.date(2026, 11, 2),
        "is_intraday": True,
    }
    base.update(overrides)
    return TradeGroup(**base)


def test_decimal_amounts_round_trip_exactly(session: Session) -> None:
    group = _group(
        avg_entry=Decimal("100.2525"),
        avg_exit=Decimal("101.5075"),
        gross_pnl=Decimal("12480.55"),
        charges_total=Decimal("131.07"),
        net_pnl=Decimal("12349.48"),
    )
    session.add(group)
    session.flush()
    session.expire(group)

    stored = session.execute(
        select(TradeGroup).where(TradeGroup.group_key == group.group_key)
    ).scalar_one()

    assert isinstance(stored.net_pnl, Decimal)
    assert stored.net_pnl == Decimal("12349.48")
    assert stored.gross_pnl == Decimal("12480.55")
    # Prices keep 4 decimals, amounts 2 (SRS 4.3).
    assert stored.avg_entry == Decimal("100.2525")
    assert stored.charges_total == Decimal("131.07")


def test_timestamps_come_back_in_utc(session: Session) -> None:
    group = _group()
    session.add(group)
    session.flush()
    session.expire(group)

    stored = session.execute(
        select(TradeGroup).where(TradeGroup.group_key == group.group_key)
    ).scalar_one()

    assert stored.opened_at.tzinfo is not None
    assert stored.opened_at.astimezone(dt.UTC) == dt.datetime(2026, 11, 2, 4, 1, tzinfo=dt.UTC)
    # The IST trading day is stored separately, not derived at read time.
    assert stored.trade_date == dt.date(2026, 11, 2)
