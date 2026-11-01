"""Shared response types.

Money and ratios cross the wire as plain decimal strings — `"12480.50"`, not
`"₹12,480.50"` (SRS 4.3). Strings because JSON numbers are doubles and would
reintroduce the float error the whole Decimal pipeline exists to avoid.
Grouping, the rupee sign and sign colouring are the client's job, and live in
`apps/web/lib/format.ts` (DESIGN.md 14).
"""

from __future__ import annotations

from decimal import Decimal
from typing import Annotated

from pydantic import PlainSerializer


def _as_plain_string(value: Decimal) -> str:
    # Fixed-point, never scientific notation: 1E+2 is not money.
    return f"{value:f}"


Money = Annotated[Decimal, PlainSerializer(_as_plain_string, return_type=str, when_used="json")]
Ratio = Annotated[Decimal, PlainSerializer(_as_plain_string, return_type=str, when_used="json")]
