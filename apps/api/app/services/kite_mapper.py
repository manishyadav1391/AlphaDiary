"""Turn Kite payloads into `fill` and `kite_order` rows (SRS Appendix D).

Three things about the real payloads drive this module:

1. No Kite timestamp carries a zone. They are IST wall-clock. The SDK parses
   the 19-character ones into *naive* datetimes, so they must be localised to
   Asia/Kolkata before being stored as UTC (SRS 4.3; NFR-10).
2. On a trade object `order_timestamp` is time-only (`"09:16:39"`), unlike on
   an order object. `filled_at` therefore comes from `fill_timestamp`, falling
   back to `exchange_timestamp`, and never from `order_timestamp`.
3. The published field list and the published examples disagree in two places:
   `instrument_token` is documented as a string but returned as a number, and
   the trades table documents `filled` while the examples return `quantity`.
   Both spellings are accepted.

Prices become `Decimal` via `str()`, never through float arithmetic
(CLAUDE.md hard rules).
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal, InvalidOperation
from typing import Any
from uuid import UUID

from app.timezone import ist_date, to_utc

VALID_SIDES = frozenset({"BUY", "SELL"})

# Fields the SDK turns into datetimes; they must be strings again for JSONB.
_TIMESTAMP_FIELDS = (
    "order_timestamp",
    "exchange_timestamp",
    "exchange_update_timestamp",
    "fill_timestamp",
    "timestamp",
    "last_trade_time",
    "created",
    "last_instalment",
)


class RejectedRow(Exception):
    """The row cannot be stored and is counted instead (FR-SYNC-09)."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def jsonable(value: Any) -> Any:
    """Make a Kite payload safe for a `jsonb` column.

    The SDK hands back `datetime` objects inside otherwise-JSON data, which
    `json.dumps` refuses. They are written back as ISO-8601 with offset so the
    stored payload stays faithful and re-runnable (SRS 4.3, Raw data).
    """
    if isinstance(value, dict):
        return {str(k): jsonable(v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [jsonable(v) for v in value]
    if isinstance(value, dt.datetime):
        return to_utc(value).isoformat()
    if isinstance(value, dt.date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, UUID):
        return str(value)
    return value


def parse_timestamp(value: Any) -> dt.datetime | None:
    """Read a Kite timestamp as IST and return it in UTC.

    Returns None for a value that is not a full timestamp, which is what makes
    a trade's time-only `order_timestamp` fall through to the next candidate
    rather than silently becoming midnight.
    """
    if isinstance(value, dt.datetime):
        return to_utc(value)
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            return to_utc(dt.datetime.strptime(text, fmt))
        except ValueError:
            continue
    try:
        return to_utc(dt.datetime.fromisoformat(text))
    except ValueError:
        return None


def parse_decimal(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def parse_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def _text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def map_trade(raw: dict[str, Any], account_id: UUID) -> dict[str, Any]:
    """One Kite trade becomes one `fill` row, or is rejected (FR-SYNC-09)."""
    kite_trade_id = _text(raw.get("trade_id"))
    if not kite_trade_id:
        raise RejectedRow("missing trade_id")

    instrument_token = parse_int(raw.get("instrument_token"))
    if instrument_token is None:
        raise RejectedRow("missing instrument_token")

    exchange = _text(raw.get("exchange"))
    tradingsymbol = _text(raw.get("tradingsymbol"))
    product = _text(raw.get("product"))
    if not exchange or not tradingsymbol or not product:
        raise RejectedRow("missing instrument identifiers")

    side = (_text(raw.get("transaction_type")) or "").upper()
    if side not in VALID_SIDES:
        raise RejectedRow("unknown side")

    # The examples return `quantity`; the published field table says `filled`.
    quantity = parse_int(raw.get("quantity"))
    if quantity is None:
        quantity = parse_int(raw.get("filled"))
    if quantity is None or quantity <= 0:
        raise RejectedRow("quantity must be positive")

    price = parse_decimal(raw.get("average_price"))
    if price is None:
        raise RejectedRow("missing average_price")

    filled_at = parse_timestamp(raw.get("fill_timestamp")) or parse_timestamp(
        raw.get("exchange_timestamp")
    )
    if filled_at is None:
        raise RejectedRow("missing fill timestamp")

    return {
        "account_id": account_id,
        "kite_trade_id": kite_trade_id,
        "order_id": _text(raw.get("order_id")),
        "exchange": exchange,
        "tradingsymbol": tradingsymbol,
        "instrument_token": instrument_token,
        "product": product,
        "side": side,
        "quantity": quantity,
        "price": price,
        "filled_at": filled_at,
        # The IST calendar day the fill belongs to (SRS 4.3, Time).
        "trade_date": ist_date(filled_at),
        "source": "api",
        "raw": jsonable(raw),
    }


def map_order(raw: dict[str, Any], account_id: UUID) -> dict[str, Any]:
    """One Kite order becomes one `kite_order` row (SRS Appendix D)."""
    order_id = _text(raw.get("order_id"))
    if not order_id:
        raise RejectedRow("missing order_id")

    return {
        "order_id": order_id,
        "account_id": account_id,
        "exchange_order_id": _text(raw.get("exchange_order_id")),
        "exchange": _text(raw.get("exchange")),
        "tradingsymbol": _text(raw.get("tradingsymbol")),
        "instrument_token": parse_int(raw.get("instrument_token")),
        "transaction_type": _text(raw.get("transaction_type")),
        "product": _text(raw.get("product")),
        "order_type": _text(raw.get("order_type")),
        "status": _text(raw.get("status")),
        "quantity": parse_int(raw.get("quantity")),
        "filled_quantity": parse_int(raw.get("filled_quantity")),
        "price": parse_decimal(raw.get("price")),
        "trigger_price": parse_decimal(raw.get("trigger_price")),
        "average_price": parse_decimal(raw.get("average_price")),
        "placed_at": parse_timestamp(raw.get("order_timestamp")),
        "raw": jsonable(raw),
    }
