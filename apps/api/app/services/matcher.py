"""FIFO trade matching (FR-MATCH, SRS 7.2).

A trade group is a run of fills in one instrument and one product that takes
the position from flat back to flat. `match_fills` is pure: it reads fills and
returns groups, touching no database. That is what makes the golden scenarios
in SRS 12.2 cheap to assert and what makes re-matching safe to repeat.

The single loop below handles scaling in, scaling out, partial fills and
position flips without special cases. A fill that closes the position and
still has quantity left opens the next group inside the same iteration, which
is scenario S5.
"""

from __future__ import annotations

import datetime as dt
import logging
from collections import deque
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Literal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Fill, Instrument, TradeGroup, TradeGroupFill, TradeJournal
from app.timezone import ist_date

logger = logging.getLogger("tj.matcher")

MATCHER_VERSION = 1
ONE = Decimal("1")
ZERO = Decimal("0")

Role = Literal["entry", "exit"]
MatchKey = tuple[UUID, int, str]

ASSET_CLASS_BY_EXCHANGE = {
    "NSE": "equity",
    "BSE": "equity",
    "NFO": "fno",
    "BFO": "fno",
    "MCX": "commodity",
    "CDS": "currency",
    "BCD": "currency",
}


@dataclass
class Allocation:
    """How much of one fill a group consumed, and in which role."""

    fill: Fill
    role: Role
    quantity_used: int


@dataclass
class MatchedGroup:
    group_key: str
    account_id: UUID
    instrument_token: int
    tradingsymbol: str
    exchange: str
    asset_class: str
    product: str
    direction: Literal["LONG", "SHORT"]
    status: Literal["open", "closed"]
    qty_max: int
    open_qty: int
    opened_at: dt.datetime
    closed_at: dt.datetime | None
    trade_date: dt.date
    hold_seconds: int | None
    is_intraday: bool
    gross_pnl: Decimal
    avg_entry: Decimal | None
    avg_exit: Decimal | None
    allocations: list[Allocation] = field(default_factory=list)


@dataclass
class _Lot:
    """An open parcel of an entry fill, with what is left of it."""

    fill: Fill
    left: int


def build_group_key(
    account_id: UUID, instrument_token: int, product: str, first_entry_trade_id: str
) -> str:
    """FR-MATCH-07. Stable across re-matching, which is why the journal keys
    on it rather than on `trade_group.id`."""
    return f"{account_id}:{instrument_token}:{product}:{first_entry_trade_id}"


def asset_class_for(exchange: str) -> str:
    return ASSET_CLASS_BY_EXCHANGE.get(exchange.upper(), "equity")


def pnl(direction: str, entry: Decimal, exit_price: Decimal, quantity: int) -> Decimal:
    """SRS 7.2. Decimal throughout: a float here would drift against Console."""
    difference = exit_price - entry if direction == "LONG" else entry - exit_price
    return difference * Decimal(quantity)


def _weighted_average(allocations: list[Allocation], role: Role) -> Decimal | None:
    rows = [a for a in allocations if a.role == role]
    if not rows:
        return None
    quantity = sum(a.quantity_used for a in rows)
    if quantity == 0:
        return None
    total = sum(a.fill.price * Decimal(a.quantity_used) for a in rows)
    return Decimal(total) / Decimal(quantity)


class _GroupBuilder:
    def __init__(self, direction: str, multiplier: Decimal) -> None:
        self.direction = direction
        self.multiplier = multiplier
        self.allocations: list[Allocation] = []
        self.gross = ZERO
        self.held = 0
        self.qty_max = 0
        self.first_entry: Fill | None = None
        self.opened_at: dt.datetime | None = None
        self.last_exit_at: dt.datetime | None = None

    def add_entry(self, fill: Fill, quantity: int) -> None:
        if self.first_entry is None:
            self.first_entry = fill
            self.opened_at = fill.filled_at
        self.allocations.append(Allocation(fill=fill, role="entry", quantity_used=quantity))
        self.held += quantity
        self.qty_max = max(self.qty_max, self.held)

    def add_exit(self, fill: Fill, quantity: int, entry_price: Decimal) -> None:
        self.allocations.append(Allocation(fill=fill, role="exit", quantity_used=quantity))
        self.gross += pnl(self.direction, entry_price, fill.price, quantity) * self.multiplier
        self.held -= quantity
        self.last_exit_at = fill.filled_at

    def build(self, *, open_qty: int) -> MatchedGroup:
        assert self.first_entry is not None and self.opened_at is not None
        template = self.first_entry
        closed = open_qty == 0
        closed_at = self.last_exit_at if closed else None

        hold_seconds = int((closed_at - self.opened_at).total_seconds()) if closed_at else None
        is_intraday = closed_at is not None and ist_date(self.opened_at) == ist_date(closed_at)

        return MatchedGroup(
            group_key=build_group_key(
                template.account_id,
                template.instrument_token,
                template.product,
                template.kite_trade_id,
            ),
            account_id=template.account_id,
            instrument_token=template.instrument_token,
            tradingsymbol=template.tradingsymbol,
            exchange=template.exchange,
            asset_class=asset_class_for(template.exchange),
            product=template.product,
            direction=self.direction,  # type: ignore[arg-type]
            status="closed" if closed else "open",
            qty_max=self.qty_max,
            open_qty=open_qty,
            opened_at=self.opened_at,
            closed_at=closed_at,
            # Realised P&L belongs to the day the group closed (SRS 6).
            trade_date=ist_date(closed_at or self.opened_at),
            hold_seconds=hold_seconds,
            is_intraday=is_intraday,
            gross_pnl=self.gross,
            avg_entry=_weighted_average(self.allocations, "entry"),
            avg_exit=_weighted_average(self.allocations, "exit"),
            allocations=self.allocations,
        )


def match_fills(fills: list[Fill], *, multiplier: Decimal = ONE) -> list[MatchedGroup]:
    """Match one (account, instrument, product) into groups (SRS 7.2).

    `fills` may arrive in any order; they are sorted by `filled_at` then
    `kite_trade_id` so the result is deterministic (FR-MATCH-01, FR-MATCH-10).
    """
    ordered = sorted(fills, key=lambda f: (f.filled_at, f.kite_trade_id))
    groups: list[MatchedGroup] = []
    lots: deque[_Lot] = deque()
    current: _GroupBuilder | None = None

    for item in ordered:
        remaining = item.quantity
        while remaining > 0:
            if not lots or lots[0].fill.side == item.side:
                # Opening a position, or adding to one.
                if current is None:
                    current = _GroupBuilder("LONG" if item.side == "BUY" else "SHORT", multiplier)
                lots.append(_Lot(fill=item, left=remaining))
                current.add_entry(item, remaining)
                remaining = 0
            else:
                # Closing against the oldest open lot.
                assert current is not None
                lot = lots[0]
                used = min(lot.left, remaining)
                current.add_exit(item, used, lot.fill.price)
                lot.left -= used
                remaining -= used
                if lot.left == 0:
                    lots.popleft()
                if not lots:
                    groups.append(current.build(open_qty=0))
                    current = None

    if current is not None:
        groups.append(current.build(open_qty=sum(lot.left for lot in lots)))

    return groups


# --------------------------------------------------------------- persistence


def multiplier_for(session: Session, instrument_token: int) -> Decimal:
    """`instrument.multiplier` when we have the instrument, else 1.

    The instruments dump is not loaded yet (VERIFY V4), so commodity P&L is
    only correct while the multiplier really is 1 (VERIFY V6).
    """
    instrument = session.get(Instrument, instrument_token)
    if instrument is None:
        logger.info(
            "Matching an unknown instrument; multiplier 1 assumed",
            extra={"event": "matcher_unknown_instrument", "count": instrument_token},
        )
        return ONE
    return Decimal(instrument.multiplier)


def rebuild_groups(session: Session, keys: set[MatchKey]) -> list[TradeGroup]:
    """Rebuild every group for the given keys (FR-MATCH-10).

    Deterministic and idempotent: the old groups for a key are deleted and the
    freshly matched ones written in their place. Journal tables are keyed by
    `group_key` and carry no foreign key here, so notes survive untouched
    (FR-MATCH-07, scenario S13).
    """
    written: list[TradeGroup] = []

    for account_id, instrument_token, product in sorted(keys, key=str):
        fills = list(
            session.execute(
                select(Fill).where(
                    Fill.account_id == account_id,
                    Fill.instrument_token == instrument_token,
                    Fill.product == product,
                )
            ).scalars()
        )
        matched = match_fills(fills, multiplier=multiplier_for(session, instrument_token))

        existing = list(
            session.execute(
                select(TradeGroup).where(
                    TradeGroup.account_id == account_id,
                    TradeGroup.instrument_token == instrument_token,
                    TradeGroup.product == product,
                )
            ).scalars()
        )
        for stale in existing:
            # trade_group_fill cascades; journal tables do not reference this.
            session.delete(stale)
        session.flush()

        for group in matched:
            written.append(_persist(session, group))

    session.flush()
    return written


def _persist(session: Session, group: MatchedGroup) -> TradeGroup:
    row = TradeGroup(
        group_key=group.group_key,
        account_id=group.account_id,
        instrument_token=group.instrument_token,
        tradingsymbol=group.tradingsymbol,
        exchange=group.exchange,
        asset_class=group.asset_class,
        product=group.product,
        direction=group.direction,
        status=group.status,
        qty_max=group.qty_max,
        open_qty=group.open_qty,
        avg_entry=group.avg_entry,
        avg_exit=group.avg_exit,
        opened_at=group.opened_at,
        closed_at=group.closed_at,
        trade_date=group.trade_date,
        hold_seconds=group.hold_seconds,
        is_intraday=group.is_intraday,
        gross_pnl=group.gross_pnl,
        # Charges land in a later step; net starts equal to gross.
        charges_total=ZERO,
        net_pnl=group.gross_pnl,
        matcher_version=MATCHER_VERSION,
    )
    session.add(row)
    session.flush()

    # One row per (group, fill, role). A flipped fill appears twice overall:
    # as an exit of the old group and an entry of the new one (FR-MATCH-04).
    merged: dict[tuple[UUID, Role], int] = {}
    for allocation in group.allocations:
        key = (allocation.fill.id, allocation.role)
        merged[key] = merged.get(key, 0) + allocation.quantity_used

    for (fill_id, role), quantity in merged.items():
        session.add(
            TradeGroupFill(
                trade_group_id=row.id,
                fill_id=fill_id,
                role=role,
                quantity_used=quantity,
            )
        )
    session.flush()
    return row


def keys_for_fills(fills: list[Fill]) -> set[MatchKey]:
    return {(f.account_id, f.instrument_token, f.product) for f in fills}


def orphaned_journal_keys(session: Session) -> list[str]:
    """Journal rows whose group_key no longer matches any group.

    They are kept, never deleted, and shown in a repair list (FR-MATCH-07).
    """
    live = set(session.execute(select(TradeGroup.group_key)).scalars())
    stored = set(session.execute(select(TradeJournal.group_key)).scalars())
    return sorted(stored - live)
