"""Rolled-up daily numbers (SRS 7.4, FR-DASH).

Only **closed** groups count, and the outcome of each is decided by its net
P&L, not its gross. Open groups are excluded from every statistic, which is
scenario S7.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.models import DailySummary, TradeGroup

ZERO = Decimal("0")

_UPDATE_COLUMNS = (
    "trades_count",
    "wins",
    "losses",
    "breakeven",
    "gross_pnl",
    "charges",
    "net_pnl",
    "best_trade",
    "worst_trade",
)


def summarise_day(groups: list[TradeGroup]) -> dict[str, object]:
    nets = [group.net_pnl for group in groups]
    return {
        "trades_count": len(groups),
        "wins": sum(1 for net in nets if net > ZERO),
        "losses": sum(1 for net in nets if net < ZERO),
        "breakeven": sum(1 for net in nets if net == ZERO),
        "gross_pnl": sum((g.gross_pnl for g in groups), start=ZERO),
        "charges": sum((g.charges_total for g in groups), start=ZERO),
        "net_pnl": sum(nets, start=ZERO),
        "best_trade": max(nets) if nets else None,
        "worst_trade": min(nets) if nets else None,
    }


def rebuild_daily_summary(session: Session, account_id: UUID, dates: set[dt.date]) -> int:
    """Recompute `daily_summary` for each IST date given. Idempotent."""
    for trade_date in sorted(dates):
        groups = list(
            session.execute(
                select(TradeGroup).where(
                    TradeGroup.account_id == account_id,
                    TradeGroup.trade_date == trade_date,
                    TradeGroup.status == "closed",
                )
            ).scalars()
        )
        values = {
            "account_id": account_id,
            "trade_date": trade_date,
            **summarise_day(groups),
        }
        statement = pg_insert(DailySummary).values(values)
        statement = statement.on_conflict_do_update(
            index_elements=[DailySummary.account_id, DailySummary.trade_date],
            set_={name: getattr(statement.excluded, name) for name in _UPDATE_COLUMNS},
        )
        session.execute(statement)
    session.flush()
    return len(dates)
