"""Money must never pass through float (CLAUDE.md hard rules, SRS 4.3)."""

from __future__ import annotations

import pytest
from sqlalchemy import Numeric

from app.models import DailySummary, Fill, OrderCharge, TradeGroup

MONEY_COLUMNS = [
    (TradeGroup, "gross_pnl", 14, 2),
    (TradeGroup, "charges_total", 14, 2),
    (TradeGroup, "net_pnl", 14, 2),
    (TradeGroup, "avg_entry", 14, 4),
    (TradeGroup, "avg_exit", 14, 4),
    (Fill, "price", 14, 4),
    (OrderCharge, "turnover", 16, 2),
    (OrderCharge, "total", 12, 2),
    (DailySummary, "net_pnl", 14, 2),
]


@pytest.mark.parametrize(("model", "column", "precision", "scale"), MONEY_COLUMNS)
def test_monetary_columns_are_numeric_with_the_srs_precision(
    model: type, column: str, precision: int, scale: int
) -> None:
    col = model.__table__.columns[column]
    assert isinstance(col.type, Numeric)
    assert (col.type.precision, col.type.scale) == (precision, scale)
    assert col.type.asdecimal is True


def test_no_float_columns_anywhere() -> None:
    from app.db import Base

    offenders = [
        f"{table.name}.{col.name}"
        for table in Base.metadata.sorted_tables
        for col in table.columns
        if col.type.__class__.__name__ in {"Float", "REAL", "DOUBLE_PRECISION"}
    ]
    assert offenders == []
