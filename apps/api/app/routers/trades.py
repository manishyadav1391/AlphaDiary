"""Trade log and detail (FR-TL, FR-JRN). Thin: logic lives in services/."""

from __future__ import annotations

import datetime as dt
import uuid
from decimal import Decimal
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db import get_session
from app.deps import current_user
from app.errors import ApiError
from app.models import AppUser, TradeGroup
from app.schemas.trades import (
    JournalIn,
    JournalOut,
    TagsIn,
    TradeDetailOut,
    TradeListItem,
    TradeListOut,
    TradePatchIn,
    TradeTotals,
)
from app.services import journal as journal_service
from app.services import trades as trade_service

router = APIRouter(prefix="/trades", tags=["trades"])

ZERO = Decimal("0")


def _outcome(group: TradeGroup) -> str | None:
    """Outcome is decided by net P&L, and only once a group is closed."""
    if group.status != "closed":
        return None
    if group.net_pnl > ZERO:
        return "win"
    if group.net_pnl < ZERO:
        return "loss"
    return "breakeven"


def _base_fields(
    group: TradeGroup,
    entry: object | None,
    tags: list,
    derived: object,
) -> dict:
    """The fields a list row and a detail row share.

    Returned as a dict and run through `model_validate`, so the literal
    unions in the schema actually check the stored values instead of being
    cast away.
    """
    return {
        "id": group.id,
        "group_key": group.group_key,
        "trade_date": group.trade_date,
        "tradingsymbol": group.tradingsymbol,
        "exchange": group.exchange,
        "asset_class": group.asset_class,
        "product": group.product,
        "direction": group.direction,
        "status": group.status,
        "is_intraday": group.is_intraday,
        "qty_max": group.qty_max,
        "open_qty": group.open_qty,
        "avg_entry": group.avg_entry,
        "avg_exit": group.avg_exit,
        "opened_at": group.opened_at,
        "closed_at": group.closed_at,
        "hold_seconds": group.hold_seconds,
        "gross_pnl": group.gross_pnl,
        "charges_total": group.charges_total,
        "net_pnl": group.net_pnl,
        "outcome": _outcome(group),
        "strategy_id": getattr(entry, "strategy_id", None),
        "tags": [{"id": tag.id, "kind": tag.kind, "name": tag.name} for tag in tags],
        "r_multiple": getattr(derived, "r_multiple", None),
    }


def _filters_from_query(
    date_from: dt.date | None,
    date_to: dt.date | None,
    product: list[str] | None,
    asset_class: list[str] | None,
    direction: str | None,
    status: str | None,
    outcome: str | None,
    strategy_id: uuid.UUID | None,
    tag_id: uuid.UUID | None,
    q: str | None,
    intraday_only: bool,
    needs_review: bool,
) -> trade_service.TradeFilters:
    return trade_service.TradeFilters(
        date_from=date_from,
        date_to=date_to,
        products=[value.upper() for value in (product or [])],
        asset_classes=[value.lower() for value in (asset_class or [])],
        direction=direction.upper() if direction else None,
        status=status,
        outcome=outcome,
        strategy_id=strategy_id,
        tag_id=tag_id,
        symbol=q,
        intraday_only=intraday_only,
        needs_review=needs_review,
    )


@router.get("", response_model=TradeListOut)
def list_trades(
    date_from: dt.date | None = None,
    date_to: dt.date | None = None,
    product: Annotated[list[str] | None, Query()] = None,
    asset_class: Annotated[list[str] | None, Query()] = None,
    direction: Literal["LONG", "SHORT"] | None = None,
    status: Literal["open", "closed"] | None = None,
    outcome: Literal["win", "loss", "breakeven"] | None = None,
    strategy_id: uuid.UUID | None = None,
    tag_id: uuid.UUID | None = None,
    q: str | None = None,
    intraday_only: bool = True,
    needs_review: bool = False,
    sort: Literal["trade_date", "net_pnl", "gross_pnl", "hold_seconds", "quantity"] = (
        "trade_date"
    ),
    order: Literal["asc", "desc"] = "desc",
    limit: int = Query(default=trade_service.DEFAULT_LIMIT, ge=1, le=trade_service.MAX_LIMIT),
    cursor: str | None = None,
    _: AppUser = Depends(current_user),
    session: Session = Depends(get_session),
) -> TradeListOut:
    """The filtered trade log (FR-TL-02, FR-TL-03).

    `intraday_only` defaults to true: this is an intraday journal first, and
    the SRS makes that the default view rather than a hidden filter.
    """
    filters = _filters_from_query(
        date_from,
        date_to,
        product,
        asset_class,
        direction,
        status,
        outcome,
        strategy_id,
        tag_id,
        q,
        intraday_only,
        needs_review,
    )

    try:
        groups, next_cursor = trade_service.list_trades(
            session,
            filters,
            sort=sort,
            descending=order == "desc",
            limit=limit,
            cursor=cursor,
        )
    except trade_service.InvalidCursor as exc:
        raise ApiError(
            "invalid_cursor", "That page link is no longer valid.", status_code=400
        ) from exc

    keys = [group.group_key for group in groups]
    tags_by_key = journal_service.tags_for_groups(session, keys)
    journals_by_key = journal_service.journals_for_groups(session, keys)

    items = [
        TradeListItem.model_validate(
            _base_fields(
                group,
                journals_by_key.get(group.group_key),
                tags_by_key.get(group.group_key, []),
                journal_service.derive(group, journals_by_key.get(group.group_key)),
            )
        )
        for group in groups
    ]

    computed = trade_service.totals(session, filters)
    return TradeListOut(
        items=items,
        next_cursor=next_cursor,
        totals=TradeTotals(
            trades=computed.trades,
            gross_pnl=computed.gross_pnl,
            charges=computed.charges,
            net_pnl=computed.net_pnl,
        ),
        intraday_only=filters.intraday_only,
    )


def _require_group(session: Session, id_or_key: str) -> TradeGroup:
    group = trade_service.resolve_group(session, id_or_key)
    if group is None:
        raise ApiError("not_found", "No such trade.", status_code=404)
    return group


def _detail(session: Session, group: TradeGroup) -> TradeDetailOut:
    rows = trade_service.fills_for_group(session, group)
    breakdown = trade_service.charge_breakdown(rows)
    entry = journal_service.get_journal(session, group.group_key)
    tags = journal_service.get_tags(session, group.group_key)
    derived = journal_service.derive(group, entry)
    previous_key, next_key = trade_service.neighbours(
        session, group, trade_service.TradeFilters(intraday_only=False)
    )

    return TradeDetailOut.model_validate(
        {
            **_base_fields(group, entry, tags, derived),
            "fills": [
                {
                    "id": row.fill.id,
                    "kite_trade_id": row.fill.kite_trade_id,
                    "order_id": row.fill.order_id,
                    "role": row.allocation.role,
                    "side": row.fill.side,
                    "quantity": row.fill.quantity,
                    "quantity_used": row.allocation.quantity_used,
                    "price": row.fill.price,
                    "filled_at": row.fill.filled_at,
                    "source": row.fill.source,
                    "charge_total": row.charge.total if row.charge else None,
                }
                for row in rows
            ],
            "charges": {
                **breakdown,
                "segment_keys": trade_service.segment_keys_for_group(session, rows),
            },
            "journal": JournalOut.model_validate(entry, from_attributes=True)
            if entry
            else JournalOut(),
            "derived": {
                "planned_risk_amount": derived.planned_risk_amount,
                "planned_rr": derived.planned_rr,
                "r_multiple": derived.r_multiple,
                "slippage_amount": derived.slippage_amount,
                "slippage_percent": derived.slippage_percent,
            },
            "previous_group_key": previous_key,
            "next_group_key": next_key,
        }
    )


@router.get("/{id_or_key}", response_model=TradeDetailOut)
def get_trade(
    id_or_key: str,
    _: AppUser = Depends(current_user),
    session: Session = Depends(get_session),
) -> TradeDetailOut:
    """One trade: fills, charge breakdown, journal and tags (FR-TL-05)."""
    return _detail(session, _require_group(session, id_or_key))


@router.put("/{id_or_key}/journal", response_model=TradeDetailOut)
def put_journal(
    id_or_key: str,
    payload: JournalIn,
    _: AppUser = Depends(current_user),
    session: Session = Depends(get_session),
) -> TradeDetailOut:
    group = _require_group(session, id_or_key)
    journal_service.save_journal(session, group.group_key, payload.model_dump(exclude_unset=True))
    return _detail(session, group)


@router.put("/{id_or_key}/tags", response_model=TradeDetailOut)
def put_tags(
    id_or_key: str,
    payload: TagsIn,
    _: AppUser = Depends(current_user),
    session: Session = Depends(get_session),
) -> TradeDetailOut:
    group = _require_group(session, id_or_key)
    try:
        journal_service.set_tags(session, group.group_key, payload.tag_ids)
    except journal_service.UnknownTag as exc:
        raise ApiError("unknown_tag", f"No such tag: {exc}", status_code=422) from exc
    return _detail(session, group)


@router.patch("/{id_or_key}", response_model=TradeDetailOut)
def patch_trade(
    id_or_key: str,
    payload: TradePatchIn,
    _: AppUser = Depends(current_user),
    session: Session = Depends(get_session),
) -> TradeDetailOut:
    """Journal fields and tags in one call, for autosave (FR-JRN-05).

    Only the fields present in the body are written, so a debounced save that
    carries one changed field cannot blank the rest.
    """
    group = _require_group(session, id_or_key)
    values = payload.model_dump(exclude_unset=True)
    tag_ids = values.pop("tag_ids", None)

    if values:
        journal_service.save_journal(session, group.group_key, values)
    if tag_ids is not None:
        try:
            journal_service.set_tags(session, group.group_key, tag_ids)
        except journal_service.UnknownTag as exc:
            raise ApiError("unknown_tag", f"No such tag: {exc}", status_code=422) from exc

    return _detail(session, group)
