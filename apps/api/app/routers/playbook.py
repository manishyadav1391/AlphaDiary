"""Daily playbook: pre-market plan and post-market review (FR-PB).

The plan and the review are two tables keyed by `trade_date`, so these are
upserts and the verb is PUT, not POST. `/playbook/daily` is today's, and
`/playbook/{date}` is any other day.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_session
from app.deps import current_user
from app.errors import ApiError
from app.models import AppUser, DailyPlan, DailyReview, DailySummary
from app.schemas.playbook import (
    PlanIn,
    PlanOut,
    PlanVersusActual,
    PlaybookIn,
    PlaybookOut,
    ReviewIn,
    ReviewOut,
)
from app.timezone import ist_date, now_utc

router = APIRouter(prefix="/playbook", tags=["playbook"])

ZERO = Decimal("0")


def _today() -> dt.date:
    """The IST trading day, not the server's calendar day (SRS 4.3)."""
    return ist_date(now_utc())


def _parse_date(value: str) -> dt.date:
    if value == "today":
        return _today()
    try:
        return dt.date.fromisoformat(value)
    except ValueError as exc:
        raise ApiError("invalid_date", "Use YYYY-MM-DD, or 'today'.", status_code=422) from exc


def _plan_out(row: DailyPlan | None) -> PlanOut | None:
    return PlanOut.model_validate(row, from_attributes=True) if row else None


def _review_out(row: DailyReview | None) -> ReviewOut | None:
    return ReviewOut.model_validate(row, from_attributes=True) if row else None


def _actual(session: Session, trade_date: dt.date, plan: DailyPlan | None) -> PlanVersusActual:
    """Plan versus actual, from daily_summary (FR-PB-04).

    Summed across accounts: there is one owner, but the table is keyed by
    account and this should not silently show one of several.
    """
    rows = list(
        session.execute(select(DailySummary).where(DailySummary.trade_date == trade_date)).scalars()
    )
    trades = sum(row.trades_count for row in rows)
    net = sum((row.net_pnl for row in rows), start=ZERO)

    max_trades = plan.max_trades if plan else None
    max_loss = plan.max_loss if plan else None
    return PlanVersusActual(
        trades_taken=trades,
        max_trades=max_trades,
        trades_limit_broken=max_trades is not None and trades > max_trades,
        net_pnl=net,
        max_loss=max_loss,
        # A limit of 2,000 is broken by a loss of 2,500, which is a net of
        # -2500, so the comparison is against the negated limit.
        loss_limit_broken=max_loss is not None and net < -abs(max_loss),
    )


def _read(session: Session, trade_date: dt.date) -> PlaybookOut:
    plan = session.get(DailyPlan, trade_date)
    review = session.get(DailyReview, trade_date)
    return PlaybookOut(
        trade_date=trade_date,
        plan=_plan_out(plan),
        review=_review_out(review),
        plan_done=plan is not None,
        review_done=review is not None,
        actual=_actual(session, trade_date, plan),
    )


def _save_plan(session: Session, trade_date: dt.date, payload: PlanIn) -> DailyPlan:
    row = session.get(DailyPlan, trade_date)
    if row is None:
        row = DailyPlan(trade_date=trade_date)
        session.add(row)
    for name, value in payload.model_dump(exclude_unset=True).items():
        setattr(row, name, value)
    session.flush()
    return row


def _save_review(session: Session, trade_date: dt.date, payload: ReviewIn) -> DailyReview:
    row = session.get(DailyReview, trade_date)
    if row is None:
        row = DailyReview(trade_date=trade_date)
        session.add(row)
    for name, value in payload.model_dump(exclude_unset=True).items():
        setattr(row, name, value)
    session.flush()
    return row


# `/daily` is declared before `/{date}` so it is not read as a date.


@router.get("/daily", response_model=PlaybookOut)
def get_today(
    _: AppUser = Depends(current_user),
    session: Session = Depends(get_session),
) -> PlaybookOut:
    return _read(session, _today())


@router.put("/daily", response_model=PlaybookOut)
def put_today(
    payload: PlaybookIn,
    _: AppUser = Depends(current_user),
    session: Session = Depends(get_session),
) -> PlaybookOut:
    """Write either half of today's playbook, or both at once."""
    trade_date = _today()
    if payload.plan is not None:
        _save_plan(session, trade_date, payload.plan)
    if payload.review is not None:
        _save_review(session, trade_date, payload.review)
    return _read(session, trade_date)


@router.get("/{date}", response_model=PlaybookOut)
def get_day(
    date: str,
    _: AppUser = Depends(current_user),
    session: Session = Depends(get_session),
) -> PlaybookOut:
    return _read(session, _parse_date(date))


@router.put("/{date}", response_model=PlaybookOut)
def put_day(
    date: str,
    payload: PlaybookIn,
    _: AppUser = Depends(current_user),
    session: Session = Depends(get_session),
) -> PlaybookOut:
    trade_date = _parse_date(date)
    if payload.plan is not None:
        _save_plan(session, trade_date, payload.plan)
    if payload.review is not None:
        _save_review(session, trade_date, payload.review)
    return _read(session, trade_date)


@router.put("/{date}/plan", response_model=PlaybookOut)
def put_plan(
    date: str,
    payload: PlanIn,
    _: AppUser = Depends(current_user),
    session: Session = Depends(get_session),
) -> PlaybookOut:
    """Pre-market plan (FR-PB-02)."""
    trade_date = _parse_date(date)
    _save_plan(session, trade_date, payload)
    return _read(session, trade_date)


@router.put("/{date}/review", response_model=PlaybookOut)
def put_review(
    date: str,
    payload: ReviewIn,
    _: AppUser = Depends(current_user),
    session: Session = Depends(get_session),
) -> PlaybookOut:
    """Post-market review (FR-PB-03)."""
    trade_date = _parse_date(date)
    _save_review(session, trade_date, payload)
    return _read(session, trade_date)
