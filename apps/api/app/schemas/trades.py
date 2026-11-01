"""Request and response models for the trade log and detail (FR-TL, FR-JRN)."""

from __future__ import annotations

import datetime as dt
import uuid
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.common import Money, Ratio

Direction = Literal["LONG", "SHORT"]
Status = Literal["open", "closed"]
Outcome = Literal["win", "loss", "breakeven"]
FollowedPlan = Literal["yes", "partly", "no"]


class TagOut(BaseModel):
    id: uuid.UUID
    kind: Literal["mistake", "attribute"]
    name: str


class TradeListItem(BaseModel):
    # Both identifiers travel together: `id` is convenient, `group_key` is the
    # one that survives a re-match and is safe to bookmark (FR-MATCH-07).
    id: uuid.UUID
    group_key: str
    trade_date: dt.date
    tradingsymbol: str
    exchange: str
    asset_class: str
    product: str
    direction: Direction
    status: Status
    is_intraday: bool
    qty_max: int
    open_qty: int
    avg_entry: Money | None = None
    avg_exit: Money | None = None
    opened_at: dt.datetime
    closed_at: dt.datetime | None = None
    hold_seconds: int | None = None
    gross_pnl: Money
    charges_total: Money
    net_pnl: Money
    outcome: Outcome | None = None
    strategy_id: uuid.UUID | None = None
    tags: list[TagOut] = []
    r_multiple: Ratio | None = None


class TradeTotals(BaseModel):
    trades: int
    gross_pnl: Money
    charges: Money
    net_pnl: Money


class TradeListOut(BaseModel):
    items: list[TradeListItem]
    next_cursor: str | None = None
    # Across the whole filtered set, not just this page (FR-TL-03).
    totals: TradeTotals
    intraday_only: bool


class FillOut(BaseModel):
    id: uuid.UUID
    kite_trade_id: str
    order_id: str | None = None
    role: Literal["entry", "exit"]
    side: Literal["BUY", "SELL"]
    quantity: int
    quantity_used: int
    price: Money
    filled_at: dt.datetime
    source: str
    charge_total: Money | None = None


class ChargeBreakdownOut(BaseModel):
    brokerage: Money
    stt_ctt: Money
    exchange_txn: Money
    sebi: Money
    stamp: Money
    other_levy: Money
    gst: Money
    total: Money
    segment_keys: list[str] = []


class JournalOut(BaseModel):
    strategy_id: uuid.UUID | None = None
    planned_entry: Money | None = None
    planned_sl: Money | None = None
    planned_target: Money | None = None
    entry_reason: str | None = None
    exit_reason: str | None = None
    emotion: str | None = None
    followed_plan: FollowedPlan | None = None
    execution_rating: int | None = None
    lessons: str | None = None
    updated_at: dt.datetime | None = None


class DerivedOut(BaseModel):
    """FR-JRN-02 and FR-TL-06. All null when no stop-loss was recorded."""

    planned_risk_amount: Money | None = None
    planned_rr: Ratio | None = None
    r_multiple: Ratio | None = None
    # Positive means worse: paid more on a long, received less on a short.
    slippage_amount: Money | None = None
    slippage_percent: Ratio | None = None


class TradeDetailOut(TradeListItem):
    fills: list[FillOut] = []
    charges: ChargeBreakdownOut
    journal: JournalOut
    derived: DerivedOut
    previous_group_key: str | None = None
    next_group_key: str | None = None


class JournalIn(BaseModel):
    """Every field optional: autosave sends only what changed (FR-JRN-05)."""

    strategy_id: uuid.UUID | None = None
    planned_entry: Money | None = None
    planned_sl: Money | None = None
    planned_target: Money | None = None
    entry_reason: str | None = None
    exit_reason: str | None = None
    emotion: str | None = None
    followed_plan: FollowedPlan | None = None
    execution_rating: int | None = Field(default=None, ge=1, le=5)
    lessons: str | None = None


class TagsIn(BaseModel):
    tag_ids: list[uuid.UUID] = []


class TradePatchIn(JournalIn):
    """Journal fields plus the tag set, for a single autosave round trip.

    Screenshots are deliberately absent: they are uploads to object storage
    with signed URLs (FR-JRN-06/07), not values to be patched in.
    """

    tag_ids: list[uuid.UUID] | None = None
