"""Shared column types.

Every monetary column is `Decimal`-backed `Numeric` with the precision the SRS
(4.3 and 6) gives it. `float` must never appear in a model.
"""

from __future__ import annotations

import datetime as dt
import uuid
from decimal import Decimal
from typing import Annotated

from sqlalchemy import BigInteger, DateTime, Numeric, Uuid, func, text
from sqlalchemy.orm import mapped_column

# Identifiers
UuidPk = Annotated[
    uuid.UUID,
    mapped_column(Uuid(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")),
]
UuidFk = Annotated[uuid.UUID, mapped_column(Uuid(as_uuid=True))]
BigIntPk = Annotated[int, mapped_column(BigInteger, primary_key=True, autoincrement=True)]

# Time. Stored as timestamptz in UTC; the IST calendar date lives in separate
# `trade_date` columns (SRS 4.3, Time).
Timestamp = Annotated[dt.datetime, mapped_column(DateTime(timezone=True))]
CreatedAt = Annotated[
    dt.datetime,
    mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now()),
]
UpdatedAt = Annotated[
    dt.datetime,
    mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    ),
]

# Money. Amounts carry 2 decimals, prices 4. Charge tables use the narrower
# precisions the SRS specifies for them; turnover is wider.
Money = Annotated[Decimal, mapped_column(Numeric(14, 2))]
Price = Annotated[Decimal, mapped_column(Numeric(14, 4))]
Turnover = Annotated[Decimal, mapped_column(Numeric(16, 2))]
ChargeAmount = Annotated[Decimal, mapped_column(Numeric(12, 2))]
ChargeAmount4 = Annotated[Decimal, mapped_column(Numeric(12, 4))]
TickSize = Annotated[Decimal, mapped_column(Numeric(10, 4))]
