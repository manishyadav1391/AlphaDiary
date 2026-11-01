"""Structural rules from SRS 6 that later milestones depend on."""

from __future__ import annotations

from app.db import Base
from app.models import Fill, Instrument, TradeGroup, TradeJournal, TradeTag

JOURNAL_TABLES = ("trade_journal", "trade_tag", "screenshot")


def test_every_srs_table_is_mapped() -> None:
    expected = {
        "app_user",
        "app_session",
        "login_attempt",
        "broker_account",
        "oauth_state",
        "instrument",
        "kite_order",
        "import_batch",
        "fill",
        "trade_group",
        "trade_group_fill",
        "charge_rate_set",
        "order_charge",
        "fill_charge",
        "strategy",
        "tag",
        "trade_journal",
        "trade_tag",
        "screenshot",
        "daily_plan",
        "daily_review",
        "daily_summary",
        "market_holiday",
        "benchmark_price",
        "sync_log",
        "notification_channel",
        "notification_log",
        "app_setting",
    }
    assert set(Base.metadata.tables) == expected


def test_journal_tables_have_no_foreign_key_to_trade_group() -> None:
    """Journal data is keyed by group_key so the matcher can rebuild groups
    without losing notes (SRS 6 design rules, FR-MATCH-07)."""
    for name in JOURNAL_TABLES:
        table = Base.metadata.tables[name]
        assert "group_key" in table.columns
        referenced = {fk.column.table.name for fk in table.foreign_keys}
        assert "trade_group" not in referenced


def test_journal_is_keyed_by_group_key() -> None:
    assert [c.name for c in TradeJournal.__table__.primary_key] == ["group_key"]
    assert [c.name for c in TradeTag.__table__.primary_key] == ["group_key", "tag_id"]


def test_fill_uniqueness_makes_sync_idempotent() -> None:
    """Golden scenarios S10 and S11 depend on this constraint."""
    uniques = {
        tuple(c.name for c in constraint.columns)
        for constraint in Fill.__table__.constraints
        if constraint.__class__.__name__ == "UniqueConstraint"
    }
    assert ("account_id", "kite_trade_id") in uniques


def test_trade_group_status_and_direction_are_constrained() -> None:
    checks = {
        c.name: str(c.sqltext)
        for c in TradeGroup.__table__.constraints
        if c.__class__.__name__ == "CheckConstraint"
    }
    assert "open" in checks["ck_trade_group_status"]
    assert "closed" in checks["ck_trade_group_status"]
    assert "LONG" in checks["ck_trade_group_direction"]


def test_timestamps_are_timezone_aware() -> None:
    """Storage is UTC timestamptz; trade_date carries the IST calendar day."""
    naive = [
        f"{table.name}.{col.name}"
        for table in Base.metadata.sorted_tables
        for col in table.columns
        if col.type.__class__.__name__ == "DateTime" and not col.type.timezone
    ]
    assert naive == []
    assert Fill.__table__.columns["trade_date"].type.__class__.__name__ == "Date"
    assert Instrument.__table__.columns["expiry"].type.__class__.__name__ == "Date"
