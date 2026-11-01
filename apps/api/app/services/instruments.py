"""The Kite instruments master (FR-IMP-05, VERIFY V4).

The dump is a CSV of around 110,000 rows served at
`https://api.kite.trade/instruments`. `(exchange, tradingsymbol)` is unique
across the whole file, which is what makes resolving a Console tradebook row
to an `instrument_token` exact rather than a guess.

Two things the dump does **not** give us: `asset_class`, which we derive from
the exchange, and `multiplier`, which is not published at all. The multiplier
therefore stays at 1 and VERIFY V6 stays open, so MCX P&L is still unproven.
"""

from __future__ import annotations

import csv
import datetime as dt
import logging
from collections.abc import Iterator
from decimal import Decimal, InvalidOperation
from io import StringIO
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.models import Instrument

logger = logging.getLogger("tj.instruments")

PUBLIC_DUMP_URL = "https://api.kite.trade/instruments"
CHUNK_SIZE = 2_000

# Exchange to asset class. The dump also carries NCO (NSE commodity) and a few
# non-tradeable venues the SRS 7.3 table does not list.
ASSET_CLASS_BY_EXCHANGE = {
    "NSE": "equity",
    "BSE": "equity",
    "NFO": "fno",
    "BFO": "fno",
    "MCX": "commodity",
    "NCO": "commodity",
    "CDS": "currency",
    "BCD": "currency",
}

_UPDATE_COLUMNS = (
    "exchange",
    "tradingsymbol",
    "name",
    "segment",
    "instrument_type",
    "asset_class",
    "expiry",
    "strike",
    "lot_size",
    "tick_size",
    "updated_at",
)


def asset_class_for(exchange: str) -> str:
    return ASSET_CLASS_BY_EXCHANGE.get(exchange.upper(), "other")


def _decimal(value: str) -> Decimal | None:
    text = (value or "").strip()
    if not text:
        return None
    try:
        return Decimal(text)
    except InvalidOperation:
        return None


def _int(value: str) -> int | None:
    text = (value or "").strip()
    if not text:
        return None
    try:
        return int(Decimal(text))
    except (InvalidOperation, ValueError):
        return None


def _date(value: str) -> dt.date | None:
    text = (value or "").strip()
    if len(text) < 10:
        return None
    try:
        return dt.date.fromisoformat(text[:10])
    except ValueError:
        return None


def parse_dump(text: str) -> Iterator[dict[str, Any]]:
    """Rows of the dump as `instrument` column values."""
    for row in csv.DictReader(StringIO(text)):
        token = _int(row.get("instrument_token", ""))
        exchange = (row.get("exchange") or "").strip()
        tradingsymbol = (row.get("tradingsymbol") or "").strip()
        if token is None or not exchange or not tradingsymbol:
            continue
        yield {
            "instrument_token": token,
            "exchange": exchange,
            "tradingsymbol": tradingsymbol,
            "name": (row.get("name") or "").strip() or None,
            "segment": (row.get("segment") or "").strip() or None,
            "instrument_type": (row.get("instrument_type") or "").strip() or None,
            "asset_class": asset_class_for(exchange),
            "expiry": _date(row.get("expiry", "")),
            "strike": _decimal(row.get("strike", "")),
            "lot_size": _int(row.get("lot_size", "")),
            "tick_size": _decimal(row.get("tick_size", "")),
            "updated_at": dt.datetime.now(dt.UTC),
        }


def fetch_dump(timeout: float = 120.0) -> str:
    """Download the public instruments dump.

    No token is needed: Zerodha serves this file unauthenticated, which is
    what lets a history import resolve symbols before the broker is connected.
    """
    response = httpx.get(PUBLIC_DUMP_URL, timeout=timeout, follow_redirects=True)
    response.raise_for_status()
    return response.text


def load_dump(session: Session, text: str) -> int:
    """Upsert every row of a dump. Idempotent; safe to re-run daily."""
    written = 0
    batch: list[dict[str, Any]] = []

    for row in parse_dump(text):
        batch.append(row)
        if len(batch) >= CHUNK_SIZE:
            written += _flush(session, batch)
            batch = []
    if batch:
        written += _flush(session, batch)

    session.flush()
    logger.info("Instruments refreshed", extra={"event": "instruments_loaded", "count": written})
    return written


def _flush(session: Session, batch: list[dict[str, Any]]) -> int:
    # The dump can repeat a token across venues within one file; keep the last.
    deduplicated = {row["instrument_token"]: row for row in batch}
    values = list(deduplicated.values())

    statement = pg_insert(Instrument).values(values)
    statement = statement.on_conflict_do_update(
        index_elements=[Instrument.instrument_token],
        set_={name: getattr(statement.excluded, name) for name in _UPDATE_COLUMNS},
    )
    session.execute(statement)
    return len(values)


def resolve(session: Session, exchange: str, tradingsymbol: str) -> Instrument | None:
    """Find an instrument by the pair that is unique in the dump."""
    return session.execute(
        select(Instrument).where(
            Instrument.exchange == exchange.upper(),
            Instrument.tradingsymbol == tradingsymbol.upper(),
        )
    ).scalar_one_or_none()


def count(session: Session) -> int:
    from sqlalchemy import func

    return int(session.execute(select(func.count()).select_from(Instrument)).scalar_one())
