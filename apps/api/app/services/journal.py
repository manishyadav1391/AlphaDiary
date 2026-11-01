"""Journal, tags and the figures derived from them (FR-JRN, FR-TL-06).

Everything here is keyed by `group_key`, never by `trade_group.id`. The id is
a fresh UUID every time the matcher rebuilds, so notes written against it
would be lost on the next sync (SRS 6 design rules, FR-MATCH-07).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models import Tag, TradeGroup, TradeJournal, TradeTag

ZERO = Decimal("0")
MONEY = Decimal("0.01")
RATIO = Decimal("0.0001")

JOURNAL_FIELDS = (
    "strategy_id",
    "planned_entry",
    "planned_sl",
    "planned_target",
    "entry_reason",
    "exit_reason",
    "emotion",
    "followed_plan",
    "execution_rating",
    "lessons",
)


class UnknownTag(Exception):
    """A tag id that is not in the managed list (FR-JRN-04)."""


@dataclass
class Derived:
    """The numbers FR-JRN-02 and FR-TL-06 define on top of the journal."""

    planned_risk_amount: Decimal | None = None
    planned_rr: Decimal | None = None
    r_multiple: Decimal | None = None
    slippage_amount: Decimal | None = None
    slippage_percent: Decimal | None = None


def _money(value: Decimal) -> Decimal:
    return value.quantize(MONEY, rounding=ROUND_HALF_UP)


def _ratio(value: Decimal) -> Decimal:
    return value.quantize(RATIO, rounding=ROUND_HALF_UP)


def derive(group: TradeGroup, journal: TradeJournal | None) -> Derived:
    """FR-JRN-02 and FR-TL-06.

    Without a stop-loss there is no risk to divide by, so R stays null and
    the trade drops out of R statistics rather than being counted as zero.
    """
    result = Derived()
    if journal is None:
        return result

    planned_sl = journal.planned_sl
    # A blank planned entry falls back to what was actually paid.
    entry = journal.planned_entry if journal.planned_entry is not None else group.avg_entry

    if planned_sl is not None and entry is not None:
        risk_per_unit = abs(entry - planned_sl)
        risk = risk_per_unit * Decimal(group.qty_max)
        if risk > ZERO:
            result.planned_risk_amount = _money(risk)
            result.r_multiple = _ratio(group.net_pnl / risk)
            if journal.planned_target is not None:
                reward = abs(journal.planned_target - entry)
                result.planned_rr = _ratio(reward / risk_per_unit)

    # Slippage needs a planned entry that was actually written down; the
    # average-entry fallback above would make it zero by construction.
    if journal.planned_entry is not None and group.avg_entry is not None:
        planned = journal.planned_entry
        actual = group.avg_entry
        # Positive always means worse: paying more on a long, receiving less
        # on a short (FR-TL-06).
        difference = actual - planned if group.direction == "LONG" else planned - actual
        result.slippage_amount = _money(difference * Decimal(group.qty_max))
        if planned != ZERO:
            result.slippage_percent = _ratio(difference / planned)

    return result


def get_journal(session: Session, group_key: str) -> TradeJournal | None:
    return session.get(TradeJournal, group_key)


def save_journal(session: Session, group_key: str, values: dict[str, Any]) -> TradeJournal:
    """Upsert the journal for a group key. Unsupplied fields are left alone,
    which is what makes the autosave in FR-JRN-05 safe to fire mid-edit."""
    journal = session.get(TradeJournal, group_key)
    if journal is None:
        journal = TradeJournal(group_key=group_key)
        session.add(journal)

    for name in JOURNAL_FIELDS:
        if name in values:
            setattr(journal, name, values[name])
    session.flush()
    return journal


def get_tags(session: Session, group_key: str) -> list[Tag]:
    return list(
        session.execute(
            select(Tag)
            .join(TradeTag, TradeTag.tag_id == Tag.id)
            .where(TradeTag.group_key == group_key)
            .order_by(Tag.kind, Tag.name)
        ).scalars()
    )


def set_tags(session: Session, group_key: str, tag_ids: list[uuid.UUID]) -> list[Tag]:
    """Replace the whole tag set for a group (FR-JRN-04)."""
    wanted = list(dict.fromkeys(tag_ids))
    if wanted:
        known = set(session.execute(select(Tag.id).where(Tag.id.in_(wanted))).scalars())
        missing = [str(tag_id) for tag_id in wanted if tag_id not in known]
        if missing:
            raise UnknownTag(", ".join(missing))

    session.execute(delete(TradeTag).where(TradeTag.group_key == group_key))
    for tag_id in wanted:
        session.add(TradeTag(group_key=group_key, tag_id=tag_id))
    session.flush()
    return get_tags(session, group_key)


def tags_for_groups(session: Session, group_keys: list[str]) -> dict[str, list[Tag]]:
    """Tags for many groups in one query, for the trade list."""
    if not group_keys:
        return {}
    rows = session.execute(
        select(TradeTag.group_key, Tag)
        .join(Tag, Tag.id == TradeTag.tag_id)
        .where(TradeTag.group_key.in_(group_keys))
        .order_by(Tag.kind, Tag.name)
    ).all()

    grouped: dict[str, list[Tag]] = {key: [] for key in group_keys}
    for group_key, tag in rows:
        grouped[group_key].append(tag)
    return grouped


def journals_for_groups(session: Session, group_keys: list[str]) -> dict[str, TradeJournal]:
    if not group_keys:
        return {}
    return {
        journal.group_key: journal
        for journal in session.execute(
            select(TradeJournal).where(TradeJournal.group_key.in_(group_keys))
        ).scalars()
    }
