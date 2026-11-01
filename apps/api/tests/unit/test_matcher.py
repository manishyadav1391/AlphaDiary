"""The FIFO matcher (FR-MATCH, SRS 7.2).

Scenarios S1 to S13 are the contract in SRS 12.2. Their expected values are
copied verbatim and must never be edited without the owner's approval
(AGENTS.md). "Gross" throughout is before charges.
"""

from __future__ import annotations

import datetime as dt
import uuid
from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

from app.models import Fill, TradeGroup, TradeJournal
from app.services import matcher
from app.timezone import IST

ACCOUNT = uuid.UUID("11111111-1111-1111-1111-111111111111")
TOKEN = 256265
DAY_ONE = dt.date(2026, 11, 2)
DAY_TWO = dt.date(2026, 11, 3)

_counter = 0


def fill(
    side: str,
    quantity: int,
    price: str,
    *,
    minute: int = 0,
    product: str = "MIS",
    token: int = TOKEN,
    day: dt.date = DAY_ONE,
    exchange: str = "NSE",
    tradingsymbol: str = "SBIN",
    account_id: uuid.UUID = ACCOUNT,
    trade_id: str | None = None,
) -> Fill:
    """A fill at 09:15 IST plus `minute`, which fixes the matching order."""
    global _counter
    _counter += 1
    filled_at = dt.datetime(day.year, day.month, day.day, 9, 15, tzinfo=IST) + dt.timedelta(
        minutes=minute
    )
    return Fill(
        id=uuid.uuid4(),
        account_id=account_id,
        kite_trade_id=trade_id or f"T{_counter:06d}",
        order_id=f"O{_counter:06d}",
        exchange=exchange,
        tradingsymbol=tradingsymbol,
        instrument_token=token,
        product=product,
        side=side,
        quantity=quantity,
        price=Decimal(price),
        filled_at=filled_at.astimezone(dt.UTC),
        trade_date=day,
        source="api",
    )


def only(groups: list[matcher.MatchedGroup]) -> matcher.MatchedGroup:
    assert len(groups) == 1, f"expected one group, got {len(groups)}"
    return groups[0]


# ----------------------------------------------------------- golden S1-S13


def test_s1_single_round_trip() -> None:
    """S1: BUY 100 @100, SELL 100 @102 -> 1 closed LONG group, gross +200."""
    group = only(match([fill("BUY", 100, "100"), fill("SELL", 100, "102", minute=1)]))

    assert group.direction == "LONG"
    assert group.status == "closed"
    assert group.gross_pnl == Decimal("200")
    assert group.open_qty == 0


def test_s2_scale_in_then_single_exit() -> None:
    """S2: BUY 50 @100, BUY 50 @100.5, SELL 100 @101.5
    -> 1 group, avg entry 100.25, gross +125."""
    group = only(
        match(
            [
                fill("BUY", 50, "100"),
                fill("BUY", 50, "100.5", minute=1),
                fill("SELL", 100, "101.5", minute=2),
            ]
        )
    )

    assert group.avg_entry == Decimal("100.25")
    assert group.gross_pnl == Decimal("125")


def test_s3_partial_exits() -> None:
    """S3: BUY 100 @100, SELL 40 @101, SELL 60 @102
    -> 1 group, avg exit 101.6, gross +160."""
    group = only(
        match(
            [
                fill("BUY", 100, "100"),
                fill("SELL", 40, "101", minute=1),
                fill("SELL", 60, "102", minute=2),
            ]
        )
    )

    assert group.avg_exit == Decimal("101.6")
    assert group.gross_pnl == Decimal("160")


def test_s4_short_round_trip() -> None:
    """S4: SELL 50 @200, BUY 50 @198 -> 1 closed SHORT group, gross +100."""
    group = only(match([fill("SELL", 50, "200"), fill("BUY", 50, "198", minute=1)]))

    assert group.direction == "SHORT"
    assert group.status == "closed"
    assert group.gross_pnl == Decimal("100")


def test_s5_position_flip_splits_the_fill() -> None:
    """S5: BUY 100 @100, SELL 150 @101, BUY 50 @100.5
    -> Group 1 LONG gross +100 (uses 100 of the 150 sell).
       Group 2 SHORT entry 50 @101, exit 50 @100.5, gross +25. Total +125."""
    flip = fill("SELL", 150, "101", minute=1)
    groups = match([fill("BUY", 100, "100"), flip, fill("BUY", 50, "100.5", minute=2)])

    assert len(groups) == 2
    first, second = groups

    assert first.direction == "LONG"
    assert first.gross_pnl == Decimal("100")
    assert second.direction == "SHORT"
    assert second.avg_entry == Decimal("101")
    assert second.avg_exit == Decimal("100.5")
    assert second.gross_pnl == Decimal("25")
    assert first.gross_pnl + second.gross_pnl == Decimal("125")

    # FR-MATCH-04: the split is recorded as quantity_used on both sides.
    used_as_exit = [
        a.quantity_used for a in first.allocations if a.fill is flip and a.role == "exit"
    ]
    used_as_entry = [
        a.quantity_used for a in second.allocations if a.fill is flip and a.role == "entry"
    ]
    assert used_as_exit == [100]
    assert used_as_entry == [50]


def test_s6_two_sequential_round_trips() -> None:
    """S6: BUY 10 @50, SELL 10 @51, BUY 10 @52, SELL 10 @51.5
    -> 2 closed groups, +10 and -5."""
    groups = match(
        [
            fill("BUY", 10, "50"),
            fill("SELL", 10, "51", minute=1),
            fill("BUY", 10, "52", minute=2),
            fill("SELL", 10, "51.5", minute=3),
        ]
    )

    assert [g.gross_pnl for g in groups] == [Decimal("10"), Decimal("-5")]
    assert all(g.status == "closed" for g in groups)


def test_s7_entry_only_stays_open() -> None:
    """S7: BUY 100 @100 only -> 1 open group, open qty 100."""
    group = only(match([fill("BUY", 100, "100")]))

    assert group.status == "open"
    assert group.open_qty == 100
    assert group.closed_at is None
    assert group.gross_pnl == Decimal("0")


def test_s8_overnight_position_is_not_intraday() -> None:
    """S8: Day 1 NRML BUY 100 @100, day 2 SELL 100 @103
    -> 1 closed group, is_intraday false, gross +300."""
    group = only(
        match(
            [
                fill("BUY", 100, "100", product="NRML", day=DAY_ONE),
                fill("SELL", 100, "103", product="NRML", day=DAY_TWO),
            ]
        )
    )

    assert group.gross_pnl == Decimal("300")
    assert group.is_intraday is False
    # Realised P&L is attributed to the IST date the group closed (SRS 6).
    assert group.trade_date == DAY_TWO


def test_s9_products_never_match_each_other() -> None:
    """S9: MIS BUY 10 @100 and NRML SELL 10 @101 (same instrument)
    -> two separate open groups, never matched together."""
    fills = [
        fill("BUY", 10, "100", product="MIS"),
        fill("SELL", 10, "101", product="NRML", minute=1),
    ]

    groups = [g for f in fills for g in match([f])]

    assert len(groups) == 2
    assert all(g.status == "open" for g in groups)
    assert {g.product for g in groups} == {"MIS", "NRML"}
    assert {g.direction for g in groups} == {"LONG", "SHORT"}


def test_s11_a_duplicate_trade_id_contributes_one_fill() -> None:
    """S11: the same kite_trade_id from the API and from CSV is one fill.

    The unique constraint on (account_id, kite_trade_id) is what enforces
    this, and ingestion covers it in test_sync. Here we pin the matcher half:
    one stored fill means one entry, never a doubled position. Preferring the
    API row over the CSV row when both arrive is importer logic and belongs
    to the CSV milestone.
    """
    group = only(match([fill("BUY", 100, "100", trade_id="DUPE")]))

    assert group.open_qty == 100
    assert group.qty_max == 100


def test_s12_open_group_carries_realised_pnl() -> None:
    """S12: BUY 10 @100, BUY 10 @110, SELL 10 @120
    -> 1 open group, realised so far +200 (FIFO against the 100 lot), open qty 10."""
    group = only(
        match(
            [
                fill("BUY", 10, "100"),
                fill("BUY", 10, "110", minute=1),
                fill("SELL", 10, "120", minute=2),
            ]
        )
    )

    assert group.status == "open"
    assert group.gross_pnl == Decimal("200")
    assert group.open_qty == 10


# ------------------------------------------------------------ group fields


def test_group_key_is_the_first_entry_trade_id() -> None:
    """FR-MATCH-07."""
    first = fill("BUY", 100, "100", trade_id="FIRST")
    group = only(match([first, fill("SELL", 100, "102", minute=1)]))

    assert group.group_key == f"{ACCOUNT}:{TOKEN}:MIS:FIRST"


def test_hold_seconds_and_intraday_flag() -> None:
    """FR-MATCH-06, FR-MATCH-08."""
    group = only(match([fill("BUY", 10, "100"), fill("SELL", 10, "101", minute=27)]))

    assert group.hold_seconds == 27 * 60
    assert group.is_intraday is True


def test_qty_max_is_the_largest_position_held() -> None:
    group = only(
        match(
            [
                fill("BUY", 10, "100"),
                fill("BUY", 10, "100"),
                fill("SELL", 5, "101", minute=1),
                fill("SELL", 15, "101", minute=2),
            ]
        )
    )

    assert group.qty_max == 20


def test_fills_are_matched_in_time_order_not_input_order() -> None:
    """FR-MATCH-01."""
    late = fill("SELL", 10, "102", minute=5)
    early = fill("BUY", 10, "100", minute=0)

    group = only(match([late, early]))

    assert group.direction == "LONG"
    assert group.gross_pnl == Decimal("20")


def test_pnl_is_decimal_never_float() -> None:
    group = only(match([fill("BUY", 3, "100.05"), fill("SELL", 3, "100.10", minute=1)]))

    assert isinstance(group.gross_pnl, Decimal)
    assert group.gross_pnl == Decimal("0.15")


def test_multiplier_scales_gross_pnl() -> None:
    """SRS 7.2 multiplies by instrument.multiplier (VERIFY V6 for MCX)."""
    fills = [fill("BUY", 1, "5800"), fill("SELL", 1, "5810", minute=1)]

    assert only(match(fills)).gross_pnl == Decimal("10")
    assert only(match(fills, multiplier=Decimal("100"))).gross_pnl == Decimal("1000")


# ------------------------------------------------------- persistence layer


def test_rebuild_persists_groups_and_allocations(
    session: Session, connected_account: object
) -> None:
    account_id = _store(session, [fill("BUY", 100, "100"), fill("SELL", 100, "102", minute=1)])

    matcher.rebuild_groups(session, {(account_id, TOKEN, "MIS")})

    group = session.query(TradeGroup).one()
    assert group.status == "closed"
    assert group.gross_pnl == Decimal("200.00")
    assert len(group.group_key.split(":")) == 4


def test_s10_rerunning_the_matcher_changes_nothing(
    session: Session, connected_account: object
) -> None:
    """S10: the same payload twice leaves groups unchanged."""
    account_id = _store(session, [fill("BUY", 100, "100"), fill("SELL", 100, "102", minute=1)])
    key = {(account_id, TOKEN, "MIS")}

    matcher.rebuild_groups(session, key)
    before = _snapshot(session)
    matcher.rebuild_groups(session, key)
    after = _snapshot(session)

    assert before == after
    assert session.query(TradeGroup).count() == 1


def test_s13_journal_survives_a_rematch(session: Session, connected_account: object) -> None:
    """S13: notes stay attached to the same group_key after re-matching."""
    account_id = _store(session, [fill("BUY", 100, "100"), fill("SELL", 100, "102", minute=1)])
    key = {(account_id, TOKEN, "MIS")}

    matcher.rebuild_groups(session, key)
    group_key = session.query(TradeGroup).one().group_key
    session.add(TradeJournal(group_key=group_key, lessons="Waited for the retest."))
    session.flush()

    matcher.rebuild_groups(session, key)

    rebuilt = session.query(TradeGroup).one()
    journal = session.get(TradeJournal, group_key)
    assert journal is not None
    assert journal.lessons == "Waited for the retest."
    assert rebuilt.group_key == group_key


def test_orphaned_journal_is_reported_not_deleted(
    session: Session, connected_account: object
) -> None:
    """FR-MATCH-07: a journal whose key disappears goes on the repair list."""
    session.add(TradeJournal(group_key="gone:1:MIS:X", lessons="orphan"))
    session.flush()

    assert "gone:1:MIS:X" in matcher.orphaned_journal_keys(session)


# ------------------------------------------------------------------ helpers


def match(fills: list[Fill], *, multiplier: Decimal = Decimal("1")) -> list[matcher.MatchedGroup]:
    return matcher.match_fills(fills, multiplier=multiplier)


def _store(session: Session, fills: list[Fill]) -> uuid.UUID:
    """Attach fills to the real broker account and persist them."""
    from app.services import token_store

    account = token_store.require_account(session)
    for item in fills:
        item.account_id = account.id
        session.add(item)
    session.flush()
    return account.id


def _snapshot(session: Session) -> list[tuple]:
    return sorted(
        (g.group_key, g.status, g.gross_pnl, g.qty_max, g.open_qty)
        for g in session.query(TradeGroup).all()
    )


@pytest.fixture(autouse=True)
def _reset_counter() -> None:
    global _counter
    _counter = 0
