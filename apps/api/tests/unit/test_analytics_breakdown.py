"""Analytics breakdowns (FR-AN).

Every bucket is handed to `analytics.compute_kpis`, so these tests check the
bucketing — which trade lands where — rather than re-deriving win rate or
profit factor, which SRS 7.4 already pins down in test_analytics.py.
"""

from __future__ import annotations

import datetime as dt
import uuid
from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

from app.models import Strategy, Tag, TradeGroup, TradeJournal, TradeTag
from app.services import analytics_breakdown as breakdown
from app.timezone import IST

MONTH_START = dt.date(2026, 11, 1)
MONTH_END = dt.date(2026, 11, 30)


def _filters(**overrides: object) -> breakdown.Filters:
    base: dict[str, object] = {"date_from": MONTH_START, "date_to": MONTH_END}
    base.update(overrides)
    return breakdown.Filters(**base)  # type: ignore[arg-type]


def _group(session: Session, **overrides: object) -> TradeGroup:
    """A closed group. `opened_at` is given in IST and stored as UTC."""
    opened_ist = overrides.pop("opened_ist", dt.datetime(2026, 11, 3, 9, 30, tzinfo=IST))
    assert isinstance(opened_ist, dt.datetime)

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
        "opened_at": opened_ist.astimezone(dt.UTC),
        "closed_at": opened_ist.astimezone(dt.UTC) + dt.timedelta(minutes=10),
        "trade_date": opened_ist.date(),
        "is_intraday": True,
        "hold_seconds": 600,
        "gross_pnl": Decimal("0"),
        "charges_total": Decimal("0"),
        "net_pnl": Decimal("0"),
    }
    base.update(overrides)
    group = TradeGroup(**base)
    session.add(group)
    session.flush()
    return group


# ------------------------------------------------------------ filters


def test_only_closed_groups_in_range_are_loaded(session: Session) -> None:
    _group(session, net_pnl=Decimal("100"))
    _group(session, status="open", open_qty=50, closed_at=None, net_pnl=Decimal("999"))
    _group(
        session,
        trade_date=dt.date(2026, 10, 2),
        opened_ist=dt.datetime(2026, 10, 2, 9, 30, tzinfo=IST),
    )

    loaded = breakdown.load(session, _filters())

    assert len(loaded) == 1
    assert loaded[0].group.net_pnl == Decimal("100")


def test_the_trade_log_filters_are_respected(session: Session) -> None:
    """SRS 5.11 preamble: analytics use the same filters as the trade log."""
    _group(session, asset_class="equity", product="CNC", is_intraday=False, net_pnl=Decimal("10"))
    _group(session, asset_class="fno", product="MIS", net_pnl=Decimal("20"))

    assert len(breakdown.load(session, _filters(asset_class=["equity"]))) == 1
    assert len(breakdown.load(session, _filters(product=["MIS"]))) == 1
    assert len(breakdown.load(session, _filters(intraday_only=True))) == 1


# ------------------------------------------------------------ FR-AN-01


def test_strategy_breakdown_keeps_untagged_trades_visible(session: Session) -> None:
    """An unlabelled book is a finding, not a reason to drop rows."""
    strategy = Strategy(name="ORB")
    session.add(strategy)
    session.flush()

    tagged = _group(session, net_pnl=Decimal("500"))
    session.add(TradeJournal(group_key=tagged.group_key, strategy_id=strategy.id))
    _group(session, net_pnl=Decimal("-200"))
    session.flush()

    buckets = breakdown.by_strategy(session, breakdown.load(session, _filters()))

    assert [b.label for b in buckets] == ["ORB", "Untagged"]
    assert buckets[0].kpis.net_pnl == Decimal("500.00")
    assert buckets[1].kpis.net_pnl == Decimal("-200.00")


# ------------------------------------------------------------ FR-AN-02


def test_time_edge_buckets_by_ist_entry_hour(session: Session) -> None:
    """The hour must be IST: 09:20 IST is 03:50 UTC and would bucket wrongly."""
    _group(session, opened_ist=dt.datetime(2026, 11, 3, 9, 20, tzinfo=IST), net_pnl=Decimal("100"))
    _group(session, opened_ist=dt.datetime(2026, 11, 3, 9, 50, tzinfo=IST), net_pnl=Decimal("50"))
    _group(session, opened_ist=dt.datetime(2026, 11, 3, 14, 5, tzinfo=IST), net_pnl=Decimal("-30"))

    buckets = breakdown.by_hour(breakdown.load(session, _filters()))

    assert [b.label for b in buckets] == ["09:00", "14:00"]
    assert buckets[0].kpis.trades == 2
    assert buckets[0].kpis.net_pnl == Decimal("150.00")


def test_weekday_buckets_use_the_exchange_week(session: Session) -> None:
    # 2026-11-03 is a Tuesday, 2026-11-05 a Thursday.
    _group(session, opened_ist=dt.datetime(2026, 11, 3, 9, 30, tzinfo=IST), net_pnl=Decimal("10"))
    _group(session, opened_ist=dt.datetime(2026, 11, 5, 9, 30, tzinfo=IST), net_pnl=Decimal("20"))

    buckets = breakdown.by_weekday(breakdown.load(session, _filters()))

    assert [b.label for b in buckets] == ["Tue", "Thu"]


def test_the_heatmap_is_one_cell_per_weekday_and_hour(session: Session) -> None:
    _group(session, opened_ist=dt.datetime(2026, 11, 3, 9, 30, tzinfo=IST), net_pnl=Decimal("10"))
    _group(session, opened_ist=dt.datetime(2026, 11, 3, 9, 45, tzinfo=IST), net_pnl=Decimal("15"))

    cells = breakdown.hour_weekday_heatmap(breakdown.load(session, _filters()))

    assert len(cells) == 1
    assert (cells[0].weekday, cells[0].hour, cells[0].trades) == ("Tue", 9, 2)
    assert cells[0].net_pnl == Decimal("25.00")


# ------------------------------------------------------------ FR-AN-03


@pytest.mark.parametrize(
    ("hold_seconds", "expected"),
    [
        (60, "Under 5m"),
        (5 * 60, "5–30m"),
        (29 * 60, "5–30m"),
        (45 * 60, "30–120m"),
        (3 * 3600, "Over 120m"),
    ],
)
def test_duration_buckets_follow_the_configured_edges(
    session: Session, hold_seconds: int, expected: str
) -> None:
    _group(session, hold_seconds=hold_seconds, net_pnl=Decimal("1"))

    buckets = breakdown.by_duration(breakdown.load(session, _filters()))

    assert [b.label for b in buckets] == [expected]


def test_a_carried_position_is_multi_day_whatever_its_hold_time(session: Session) -> None:
    """FR-AN-03 separates multi-day by the flag, not by elapsed seconds."""
    _group(session, is_intraday=False, hold_seconds=120, net_pnl=Decimal("1"))

    buckets = breakdown.by_duration(breakdown.load(session, _filters()))

    assert [b.label for b in buckets] == ["Multi-day"]


# ------------------------------------------------------------ FR-AN-04


def test_risk_reports_the_drawdown_window_and_streaks(session: Session) -> None:
    for day, net in enumerate([100, -40, -60, -30, 80], start=2):
        _group(
            session,
            opened_ist=dt.datetime(2026, 11, day, 9, 30, tzinfo=IST),
            net_pnl=Decimal(net),
        )

    report = breakdown.risk(breakdown.load(session, _filters()))

    # Peak of 100 on the 2nd, trough after the 5th: 130 given up.
    assert report.kpis.max_drawdown == Decimal("130.00")
    assert report.drawdown_from == dt.date(2026, 11, 2)
    assert report.drawdown_to == dt.date(2026, 11, 5)
    assert report.streaks.longest_losing == 3


def test_risk_counts_how_many_trades_had_a_stop_planned(session: Session) -> None:
    """FR-AN-04: the share of trades actually traded against a stop."""
    with_stop = _group(session, avg_entry=Decimal("100"), net_pnl=Decimal("50"))
    session.add(
        TradeJournal(
            group_key=with_stop.group_key,
            planned_entry=Decimal("100"),
            planned_sl=Decimal("98"),
        )
    )
    _group(session, net_pnl=Decimal("-20"))
    session.flush()

    report = breakdown.risk(breakdown.load(session, _filters()))

    assert report.trades_total == 2
    assert report.trades_with_stop == 1
    # 2 points of risk on 100 units.
    assert report.avg_planned_risk == Decimal("200.00")


def test_trades_without_an_r_multiple_stay_out_of_the_histogram(session: Session) -> None:
    """Without a stop there is no R to bin; it must not count as zero."""
    _group(session, net_pnl=Decimal("-20"))

    report = breakdown.risk(breakdown.load(session, _filters()))

    assert sum(b.trades for b in report.r_histogram) == 0


# ------------------------------------------------------------ FR-AN-05


def test_mistake_cost_is_sorted_by_total_cost(session: Session) -> None:
    cheap = Tag(kind="mistake", name="Late entry")
    dear = Tag(kind="mistake", name="Moved stop")
    session.add_all([cheap, dear])
    session.flush()

    a = _group(session, net_pnl=Decimal("-100"))
    b = _group(session, net_pnl=Decimal("-900"))
    session.add_all(
        [
            TradeTag(group_key=a.group_key, tag_id=cheap.id),
            TradeTag(group_key=b.group_key, tag_id=dear.id),
        ]
    )
    session.flush()

    rows = breakdown.mistake_cost(session, breakdown.load(session, _filters()))

    assert [row.tag for row in rows] == ["Moved stop", "Late entry"]
    assert rows[0].net_pnl == Decimal("-900.00")
    assert rows[0].share_of_trades == Decimal("0.50")


def test_attribute_tags_are_not_counted_as_mistakes(session: Session) -> None:
    attribute = Tag(kind="attribute", name="News day")
    session.add(attribute)
    session.flush()
    group = _group(session, net_pnl=Decimal("-50"))
    session.add(TradeTag(group_key=group.group_key, tag_id=attribute.id))
    session.flush()

    assert breakdown.mistake_cost(session, breakdown.load(session, _filters())) == []
