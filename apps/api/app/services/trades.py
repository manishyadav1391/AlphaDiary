"""Querying trade groups for the log and the detail page (FR-TL).

Cursor pagination is keyset-based on `(sort column, id)`. Offsets would drift
whenever a sync inserts a group mid-list, which on a journal you scroll
through daily is exactly when it would be noticed (SRS 4.3, FR-TL-03).
"""

from __future__ import annotations

import base64
import binascii
import datetime as dt
import json
import uuid
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from sqlalchemy import Select, and_, exists, func, or_, select, tuple_
from sqlalchemy.orm import Session

from app.models import (
    Fill,
    FillCharge,
    OrderCharge,
    TradeGroup,
    TradeGroupFill,
    TradeJournal,
    TradeTag,
)

ZERO = Decimal("0")
MONEY = Decimal("0.01")

DEFAULT_LIMIT = 50
MAX_LIMIT = 200

CHARGE_COMPONENTS = (
    "brokerage",
    "stt_ctt",
    "exchange_txn",
    "sebi",
    "stamp",
    "other_levy",
    "gst",
)

# Only columns with a stable total order can carry a keyset cursor, so the
# sortable set is deliberately short (FR-TL-03).
SORT_COLUMNS: dict[str, Any] = {
    "trade_date": TradeGroup.trade_date,
    "net_pnl": TradeGroup.net_pnl,
    "gross_pnl": TradeGroup.gross_pnl,
    "hold_seconds": func.coalesce(TradeGroup.hold_seconds, 0),
    "quantity": TradeGroup.qty_max,
}

OUTCOMES = ("win", "loss", "breakeven")


class InvalidCursor(Exception):
    """The cursor is not one we issued."""


@dataclass
class TradeFilters:
    date_from: dt.date | None = None
    date_to: dt.date | None = None
    products: list[str] = field(default_factory=list)
    asset_classes: list[str] = field(default_factory=list)
    direction: str | None = None
    status: str | None = None
    outcome: str | None = None
    strategy_id: uuid.UUID | None = None
    tag_id: uuid.UUID | None = None
    symbol: str | None = None
    # FR-TL-02: on by default, because this is an intraday journal first.
    intraday_only: bool = True
    needs_review: bool = False


@dataclass
class Totals:
    trades: int = 0
    gross_pnl: Decimal = ZERO
    charges: Decimal = ZERO
    net_pnl: Decimal = ZERO


def _money(value: Decimal) -> Decimal:
    return value.quantize(MONEY, rounding=ROUND_HALF_UP)


# ------------------------------------------------------------------ cursors


def encode_cursor(value: Any, group_id: uuid.UUID) -> str:
    payload = json.dumps({"v": _cursor_value(value), "id": str(group_id)})
    return base64.urlsafe_b64encode(payload.encode()).decode().rstrip("=")


def _cursor_value(value: Any) -> str:
    if isinstance(value, dt.date):
        return value.isoformat()
    return str(value)


def decode_cursor(cursor: str, sort: str) -> tuple[Any, uuid.UUID]:
    padding = "=" * (-len(cursor) % 4)
    try:
        payload = json.loads(base64.urlsafe_b64decode(cursor + padding))
        raw, group_id = payload["v"], uuid.UUID(payload["id"])
    except (ValueError, KeyError, binascii.Error) as exc:
        raise InvalidCursor(cursor) from exc

    if sort == "trade_date":
        return dt.date.fromisoformat(raw), group_id
    if sort in ("net_pnl", "gross_pnl"):
        return Decimal(raw), group_id
    return int(raw), group_id


# ------------------------------------------------------------------ filters


def apply_filters(statement: Select, filters: TradeFilters) -> Select:
    if filters.date_from is not None:
        statement = statement.where(TradeGroup.trade_date >= filters.date_from)
    if filters.date_to is not None:
        statement = statement.where(TradeGroup.trade_date <= filters.date_to)
    if filters.products:
        statement = statement.where(TradeGroup.product.in_(filters.products))
    if filters.asset_classes:
        statement = statement.where(TradeGroup.asset_class.in_(filters.asset_classes))
    if filters.direction:
        statement = statement.where(TradeGroup.direction == filters.direction)
    if filters.status:
        statement = statement.where(TradeGroup.status == filters.status)
    if filters.intraday_only:
        statement = statement.where(TradeGroup.is_intraday.is_(True))
    if filters.symbol:
        statement = statement.where(TradeGroup.tradingsymbol.ilike(f"%{filters.symbol.strip()}%"))

    if filters.outcome:
        # An open group has no outcome yet, so it can never match one.
        statement = statement.where(TradeGroup.status == "closed")
        if filters.outcome == "win":
            statement = statement.where(TradeGroup.net_pnl > ZERO)
        elif filters.outcome == "loss":
            statement = statement.where(TradeGroup.net_pnl < ZERO)
        else:
            statement = statement.where(TradeGroup.net_pnl == ZERO)

    if filters.strategy_id is not None:
        statement = statement.where(
            exists().where(
                and_(
                    TradeJournal.group_key == TradeGroup.group_key,
                    TradeJournal.strategy_id == filters.strategy_id,
                )
            )
        )

    if filters.tag_id is not None:
        statement = statement.where(
            exists().where(
                and_(
                    TradeTag.group_key == TradeGroup.group_key,
                    TradeTag.tag_id == filters.tag_id,
                )
            )
        )

    if filters.needs_review:
        # Closed trades missing a setup or missing every tag (FR-JRN-08).
        has_strategy = exists().where(
            and_(
                TradeJournal.group_key == TradeGroup.group_key,
                TradeJournal.strategy_id.is_not(None),
            )
        )
        has_tag = exists().where(TradeTag.group_key == TradeGroup.group_key)
        statement = statement.where(TradeGroup.status == "closed", or_(~has_strategy, ~has_tag))

    return statement


def list_trades(
    session: Session,
    filters: TradeFilters,
    *,
    sort: str = "trade_date",
    descending: bool = True,
    limit: int = DEFAULT_LIMIT,
    cursor: str | None = None,
) -> tuple[list[TradeGroup], str | None]:
    """A page of trade groups, plus the cursor for the next one."""
    column = SORT_COLUMNS[sort]
    statement = apply_filters(select(TradeGroup), filters)

    if cursor:
        value, group_id = decode_cursor(cursor, sort)
        keyset = tuple_(column, TradeGroup.id)
        statement = statement.where(
            keyset < (value, group_id) if descending else keyset > (value, group_id)
        )

    order = (
        (column.desc(), TradeGroup.id.desc()) if descending else (column.asc(), TradeGroup.id.asc())
    )
    # One extra row tells us whether another page exists without a count.
    rows = list(session.execute(statement.order_by(*order).limit(limit + 1)).scalars())

    next_cursor = None
    if len(rows) > limit:
        rows = rows[:limit]
        last = rows[-1]
        next_cursor = encode_cursor(_sort_value(last, sort), last.id)
    return rows, next_cursor


def _sort_value(group: TradeGroup, sort: str) -> Any:
    if sort == "hold_seconds":
        return group.hold_seconds or 0
    if sort == "quantity":
        return group.qty_max
    return getattr(group, sort)


def totals(session: Session, filters: TradeFilters) -> Totals:
    """Totals across the whole filtered set, not just the page (FR-TL-03)."""
    statement = apply_filters(
        select(
            func.count(TradeGroup.id),
            func.coalesce(func.sum(TradeGroup.gross_pnl), 0),
            func.coalesce(func.sum(TradeGroup.charges_total), 0),
            func.coalesce(func.sum(TradeGroup.net_pnl), 0),
        ),
        filters,
    )
    count, gross, charges, net = session.execute(statement).one()
    return Totals(
        trades=int(count),
        gross_pnl=_money(Decimal(gross)),
        charges=_money(Decimal(charges)),
        net_pnl=_money(Decimal(net)),
    )


# ------------------------------------------------------------------- detail


def resolve_group(session: Session, id_or_key: str) -> TradeGroup | None:
    """Accept the UUID or the stable `group_key`.

    The UUID changes on every re-match, so a bookmark should use the key;
    both are accepted and both are returned (FR-MATCH-07, FR-TL-04).
    """
    try:
        as_uuid = uuid.UUID(id_or_key)
    except ValueError:
        as_uuid = None

    if as_uuid is not None:
        found = session.get(TradeGroup, as_uuid)
        if found is not None:
            return found

    return session.execute(
        select(TradeGroup).where(TradeGroup.group_key == id_or_key)
    ).scalar_one_or_none()


@dataclass
class FillRow:
    allocation: TradeGroupFill
    fill: Fill
    charge: FillCharge | None


def fills_for_group(session: Session, group: TradeGroup) -> list[FillRow]:
    rows = session.execute(
        select(TradeGroupFill, Fill, FillCharge)
        .join(Fill, Fill.id == TradeGroupFill.fill_id)
        .outerjoin(FillCharge, FillCharge.fill_id == TradeGroupFill.fill_id)
        .where(TradeGroupFill.trade_group_id == group.id)
        .order_by(Fill.filled_at, Fill.kite_trade_id)
    ).all()
    return [FillRow(allocation=a, fill=f, charge=c) for a, f, c in rows]


def charge_breakdown(rows: list[FillRow]) -> dict[str, Decimal]:
    """The group's share of each charge component (SRS 7.3, step 6).

    A group pays for the part of each fill it used, so a fill split across
    two groups by a position flip has its charges split the same way.
    """
    totals_by_component = dict.fromkeys(CHARGE_COMPONENTS, ZERO)
    totals_by_component["total"] = ZERO

    for row in rows:
        if row.charge is None or row.fill.quantity == 0:
            continue
        share = Decimal(row.allocation.quantity_used) / Decimal(row.fill.quantity)
        for name in CHARGE_COMPONENTS:
            value = getattr(row.charge, name)
            if value is not None:
                totals_by_component[name] += value * share
        totals_by_component["total"] += row.charge.total * share

    return {name: _money(value) for name, value in totals_by_component.items()}


def segment_keys_for_group(session: Session, rows: list[FillRow]) -> list[str]:
    order_ids = {row.fill.order_id for row in rows if row.fill.order_id}
    if not order_ids:
        return []
    return sorted(
        set(
            session.execute(
                select(OrderCharge.segment_key).where(OrderCharge.order_id.in_(order_ids))
            ).scalars()
        )
    )


def neighbours(
    session: Session, group: TradeGroup, filters: TradeFilters
) -> tuple[str | None, str | None]:
    """The previous and next group keys in date order, for detail paging."""
    newer = session.execute(
        apply_filters(select(TradeGroup.group_key), filters)
        .where(tuple_(TradeGroup.trade_date, TradeGroup.id) > (group.trade_date, group.id))
        .order_by(TradeGroup.trade_date.asc(), TradeGroup.id.asc())
        .limit(1)
    ).scalar_one_or_none()
    older = session.execute(
        apply_filters(select(TradeGroup.group_key), filters)
        .where(tuple_(TradeGroup.trade_date, TradeGroup.id) < (group.trade_date, group.id))
        .order_by(TradeGroup.trade_date.desc(), TradeGroup.id.desc())
        .limit(1)
    ).scalar_one_or_none()
    return older, newer
