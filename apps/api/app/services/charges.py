"""Charges and net P&L (FR-CHG, SRS 7.3).

No rate appears in this file. Every number comes from a `charge_rate_set` row
loaded from `seed/charge_rates.json`, chosen by the fill's trade date, so old
trades keep the rates that applied to them (FR-CHG-02, FR-CHG-07).

Charges are computed **per order**, because brokerage is capped per executed
order: three fills of one order share one 20-rupee cap, so computing per fill
and summing would triple it. The order's charge is then allocated to its fills
by turnover share, and to trade groups by `quantity_used` (FR-CHG-01).
"""

from __future__ import annotations

import datetime as dt
import logging
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    ChargeRateSet,
    Fill,
    FillCharge,
    Instrument,
    OrderCharge,
    TradeGroup,
    TradeGroupFill,
)

logger = logging.getLogger("tj.charges")

ZERO = Decimal("0")
HUNDRED = Decimal("100")
MONEY = Decimal("0.01")
ALLOCATION = Decimal("0.0001")

SEGMENT_KEYS = (
    "eq_intraday",
    "eq_delivery",
    "fut",
    "opt",
    "comm_fut",
    "comm_opt",
    "cur_fut",
    "cur_opt",
)

COMPONENTS = ("brokerage", "stt_ctt", "exchange_txn", "sebi", "stamp", "other_levy")

# GST applies to these, never to STT/CTT or stamp duty (FR-CHG-04).
GST_BASE = ("brokerage", "exchange_txn", "sebi", "other_levy")

_EQUITY_EXCHANGES = frozenset({"NSE", "BSE"})
_FNO_EXCHANGES = frozenset({"NFO", "BFO"})
_COMMODITY_EXCHANGES = frozenset({"MCX"})
_CURRENCY_EXCHANGES = frozenset({"CDS", "BCD"})

_DELIVERY_PRODUCTS = frozenset({"CNC", "NRML", "MTF"})
_OPTION_TYPES = frozenset({"CE", "PE"})


class UnknownSegment(Exception):
    """The exchange, instrument type or product does not map to a segment."""


class NoRateSet(Exception):
    """No rate set was in force on that trade date (FR-CHG-02)."""


def round_money(value: Decimal, places: Decimal = MONEY) -> Decimal:
    """Half-up, the rounding Indian contract notes use (FR-CHG-06)."""
    return value.quantize(places, rounding=ROUND_HALF_UP)


# ------------------------------------------------------------ segment map


def segment_for(exchange: str, instrument_type: str, product: str) -> str:
    """The pure mapping function from SRS 7.3 (FR-CHG-03)."""
    exchange = exchange.upper()
    instrument_type = instrument_type.upper()
    product = product.upper()

    if exchange in _EQUITY_EXCHANGES:
        return "eq_delivery" if product in _DELIVERY_PRODUCTS else "eq_intraday"
    if exchange in _FNO_EXCHANGES:
        return "opt" if instrument_type in _OPTION_TYPES else "fut"
    if exchange in _COMMODITY_EXCHANGES:
        return "comm_opt" if instrument_type in _OPTION_TYPES else "comm_fut"
    if exchange in _CURRENCY_EXCHANGES:
        return "cur_opt" if instrument_type in _OPTION_TYPES else "cur_fut"
    raise UnknownSegment(f"no segment for exchange {exchange}")


def infer_instrument_type(exchange: str, tradingsymbol: str) -> str:
    """Derive FUT, CE or PE from the trading symbol.

    This is an interim measure: the authoritative source is the instruments
    dump, which is not loaded yet (VERIFY V4). Kite's derivative symbols end
    in FUT, CE or PE, so the inference is reliable in practice, but anything
    it cannot read is raised rather than guessed.
    """
    if exchange.upper() in _EQUITY_EXCHANGES:
        return "EQ"
    symbol = tradingsymbol.upper()
    for suffix in ("FUT", "CE", "PE"):
        if symbol.endswith(suffix):
            return suffix
    raise UnknownSegment(f"cannot read an instrument type from {tradingsymbol}")


def segment_for_fill(
    fill: Fill,
    instrument_type: str | None = None,
    *,
    session: Session | None = None,
) -> str:
    """The segment for one fill.

    The instruments master is authoritative. Reading the type off the trading
    symbol is the fallback for a symbol the dump does not carry.
    """
    resolved = instrument_type
    if resolved is None and session is not None:
        instrument = session.get(Instrument, fill.instrument_token)
        if instrument is not None and instrument.instrument_type:
            resolved = instrument.instrument_type
    if resolved is None:
        resolved = infer_instrument_type(fill.exchange, fill.tradingsymbol)
    return segment_for(fill.exchange, resolved, fill.product)


# --------------------------------------------------------------- rate set


class RateSet:
    """A charge_rate_set config, read-only."""

    def __init__(self, config: dict[str, Any], label: str | None = None) -> None:
        self._config = config
        self.label = label or str(config.get("label") or "")

    @property
    def gst_rate(self) -> Decimal:
        return Decimal(str(self._config["gst_rate"])) / HUNDRED

    def segment(self, segment_key: str) -> dict[str, Any]:
        try:
            return dict(self._config["segments"][segment_key])
        except KeyError as exc:
            raise UnknownSegment(f"rate set has no segment {segment_key}") from exc

    def component(self, segment_key: str, name: str, exchange: str) -> dict[str, Any] | None:
        spec = self.segment(segment_key).get(name)
        if spec is None:
            return None
        spec = dict(spec)
        override = (spec.get("exchange_overrides") or {}).get(exchange.upper())
        if override:
            spec.update(override)
        return spec


def rate_set_for(session: Session, trade_date: dt.date) -> RateSet:
    """The set with the greatest `effective_from` on or before the date."""
    row = session.execute(
        select(ChargeRateSet)
        .where(ChargeRateSet.effective_from <= trade_date)
        .order_by(ChargeRateSet.effective_from.desc())
        .limit(1)
    ).scalar_one_or_none()
    if row is None:
        raise NoRateSet(f"no charge rate set in force on {trade_date}")
    return RateSet(row.config, label=row.label)


# ----------------------------------------------------------- the breakdown


@dataclass
class ChargeBreakdown:
    brokerage: Decimal = ZERO
    stt_ctt: Decimal = ZERO
    exchange_txn: Decimal = ZERO
    sebi: Decimal = ZERO
    stamp: Decimal = ZERO
    other_levy: Decimal = ZERO
    gst: Decimal = ZERO
    turnover: Decimal = ZERO
    segment_key: str = ""

    @property
    def total(self) -> Decimal:
        return (
            self.brokerage
            + self.stt_ctt
            + self.exchange_txn
            + self.sebi
            + self.stamp
            + self.other_levy
            + self.gst
        )

    def as_dict(self) -> dict[str, Decimal]:
        return {name: getattr(self, name) for name in (*COMPONENTS, "gst")}


def turnover_of(fills: Iterable[Fill]) -> Decimal:
    return sum((f.price * Decimal(f.quantity) for f in fills), start=ZERO)


def _side_turnover(fills: Sequence[Fill], side: str) -> Decimal:
    if side == "both":
        return turnover_of(fills)
    wanted = "BUY" if side == "buy" else "SELL"
    return turnover_of(f for f in fills if f.side == wanted)


def _component_amount(
    spec: dict[str, Any] | None, fills: Sequence[Fill], places: Decimal
) -> Decimal:
    """One charge component (FR-CHG-05)."""
    if spec is None:
        return ZERO
    nothing = round_money(ZERO, places)
    rule = str(spec.get("type", "percent"))
    if rule == "zero":
        return nothing

    applicable = _side_turnover(fills, str(spec.get("side", "both")))
    if applicable == ZERO:
        return nothing

    if rule == "flat":
        return round_money(Decimal(str(spec["flat"])), places)
    if rule == "percent":
        return round_money(applicable * Decimal(str(spec["percent"])) / HUNDRED, places)
    if rule == "min_of_flat_or_percent":
        percent = applicable * Decimal(str(spec["percent"])) / HUNDRED
        return round_money(min(Decimal(str(spec["flat"])), percent), places)
    raise UnknownSegment(f"unknown brokerage rule {rule}")


def compute_order_charge(
    fills: Sequence[Fill],
    rate_set: RateSet,
    *,
    segment_key: str | None = None,
    extra_levy: Decimal = ZERO,
) -> ChargeBreakdown:
    """Charges for one order, from its fills (SRS 7.3, procedure per order).

    `extra_levy` carries a charge the per-order rules cannot see on their own,
    such as the DP fee that applies once per scrip per day. It is added to
    `other_levy` before GST, which is why the published DP total comes out
    exactly right.
    """
    if not fills:
        return ChargeBreakdown()

    first = fills[0]
    key = segment_key or segment_for_fill(first)
    exchange = first.exchange.upper()

    breakdown = ChargeBreakdown(segment_key=key, turnover=round_money(turnover_of(fills)))
    for name in COMPONENTS:
        spec = rate_set.component(key, name, exchange)
        setattr(breakdown, name, _component_amount(spec, fills, MONEY))

    if extra_levy:
        breakdown.other_levy = round_money(breakdown.other_levy + extra_levy)

    base = sum((getattr(breakdown, name) for name in GST_BASE), start=ZERO)
    breakdown.gst = round_money(base * rate_set.gst_rate)
    return breakdown


# -------------------------------------------------------------- allocation


def allocate_to_fills(
    breakdown: ChargeBreakdown, fills: Sequence[Fill]
) -> dict[UUID, ChargeBreakdown]:
    """Split an order's charge across its fills by turnover (FR-CHG-06).

    The last fill takes whatever the rounding left over, so the parts add up
    to the order total exactly rather than approximately.
    """
    if not fills:
        return {}

    total_turnover = turnover_of(fills)
    allocated: dict[UUID, ChargeBreakdown] = {
        f.id: ChargeBreakdown(segment_key=breakdown.segment_key) for f in fills
    }

    for name in (*COMPONENTS, "gst"):
        amount = getattr(breakdown, name)
        running = ZERO
        for fill in fills[:-1]:
            share = (
                ZERO
                if total_turnover == ZERO
                else (fill.price * Decimal(fill.quantity)) / total_turnover
            )
            part = round_money(amount * share, ALLOCATION)
            setattr(allocated[fill.id], name, part)
            running += part
        setattr(allocated[fills[-1].id], name, amount - running)

    for fill in fills:
        allocated[fill.id].turnover = round_money(fill.price * Decimal(fill.quantity))
    return allocated


# ------------------------------------------------------------- persistence


def _dp_eligible_order(session: Session, fills: Sequence[Fill], segment_key: str) -> bool:
    """Whether this order carries the day's DP charge for its scrip.

    DP is charged once per scrip per day on delivery sells, not per order, so
    only the earliest qualifying order of the day picks it up.
    """
    if segment_key != "eq_delivery":
        return False
    sells = [f for f in fills if f.side == "SELL"]
    if not sells:
        return False

    first = sells[0]
    earliest = session.execute(
        select(Fill)
        .where(
            Fill.account_id == first.account_id,
            Fill.tradingsymbol == first.tradingsymbol,
            Fill.trade_date == first.trade_date,
            Fill.side == "SELL",
            Fill.product.in_(tuple(_DELIVERY_PRODUCTS)),
        )
        .order_by(Fill.filled_at, Fill.kite_trade_id)
        .limit(1)
    ).scalar_one_or_none()
    return earliest is not None and earliest.order_id == first.order_id


def compute_charges(session: Session, order_ids: set[str]) -> int:
    """Compute and store charges for each order (FR-CHG-01).

    Idempotent: an order's charge rows are replaced, not appended to, so
    re-running a sync or a recompute converges on the same numbers.
    """
    written = 0
    for order_id in sorted(order_ids):
        fills = list(
            session.execute(
                select(Fill)
                .where(Fill.order_id == order_id)
                .order_by(Fill.filled_at, Fill.kite_trade_id)
            ).scalars()
        )
        if not fills:
            continue

        first = fills[0]
        try:
            segment_key = segment_for_fill(first, session=session)
            rate_set = rate_set_for(session, first.trade_date)
        except (UnknownSegment, NoRateSet):
            logger.warning(
                "Skipping charges for an order we cannot price",
                extra={"event": "charges_skipped"},
            )
            continue

        extra = ZERO
        dp_spec = rate_set.component(segment_key, "dp", first.exchange)
        if dp_spec and _dp_eligible_order(session, fills, segment_key):
            extra = Decimal(str(dp_spec["flat"]))

        breakdown = compute_order_charge(fills, rate_set, segment_key=segment_key, extra_levy=extra)
        allocated = allocate_to_fills(breakdown, fills)

        existing = session.get(OrderCharge, order_id)
        if existing is not None:
            session.delete(existing)
            session.flush()
        session.add(
            OrderCharge(
                order_id=order_id,
                account_id=first.account_id,
                segment_key=segment_key,
                turnover=breakdown.turnover,
                brokerage=breakdown.brokerage,
                stt_ctt=breakdown.stt_ctt,
                exchange_txn=breakdown.exchange_txn,
                sebi=breakdown.sebi,
                stamp=breakdown.stamp,
                other_levy=breakdown.other_levy,
                gst=breakdown.gst,
                total=breakdown.total,
            )
        )

        for fill in fills:
            part = allocated[fill.id]
            row = session.get(FillCharge, fill.id)
            if row is not None:
                session.delete(row)
                session.flush()
            session.add(
                FillCharge(
                    fill_id=fill.id,
                    brokerage=part.brokerage,
                    stt_ctt=part.stt_ctt,
                    exchange_txn=part.exchange_txn,
                    sebi=part.sebi,
                    stamp=part.stamp,
                    other_levy=part.other_levy,
                    gst=part.gst,
                    total=part.total,
                )
            )
        session.flush()
        written += 1
    return written


def apply_charges_to_groups(session: Session, keys: set[tuple[UUID, int, str]]) -> int:
    """Attribute fill charges to trade groups and set net P&L (SRS 7.3, step 6).

    A group pays for the part of each fill it actually used, so a fill split
    across two groups by a position flip has its charge split the same way.
    """
    updated = 0
    for account_id, instrument_token, product in sorted(keys, key=str):
        groups = list(
            session.execute(
                select(TradeGroup).where(
                    TradeGroup.account_id == account_id,
                    TradeGroup.instrument_token == instrument_token,
                    TradeGroup.product == product,
                )
            ).scalars()
        )
        for group in groups:
            rows = session.execute(
                select(TradeGroupFill, FillCharge, Fill)
                .join(Fill, Fill.id == TradeGroupFill.fill_id)
                .join(FillCharge, FillCharge.fill_id == TradeGroupFill.fill_id)
                .where(TradeGroupFill.trade_group_id == group.id)
            ).all()

            total = ZERO
            for allocation, fill_charge, fill in rows:
                if fill.quantity == 0:
                    continue
                share = Decimal(allocation.quantity_used) / Decimal(fill.quantity)
                total += fill_charge.total * share

            group.charges_total = round_money(total)
            group.net_pnl = round_money(group.gross_pnl - group.charges_total)
            updated += 1
    session.flush()
    return updated
