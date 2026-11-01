"""Zerodha Console tradebook import (FR-IMP, VERIFY V8).

The real export has thirteen columns:

    symbol, isin, trade_date, exchange, segment, series, trade_type,
    auction, quantity, price, trade_id, order_id, order_execution_time

Two things it does not have, and both matter:

* **No product.** The matching key is (account, instrument, product) and the
  charge segment splits on it, so it has to be derived. A position that opens
  and flattens inside one trading day is MIS; one carried past its trade date
  is CNC. The inference runs over every stored CSV fill for the symbol, not
  just the file being imported, so a position closed by a later export is
  reclassified rather than left wrong.
* **No instrument token.** Resolved from the instruments dump by
  `(exchange, tradingsymbol)`, which is unique across it. An unresolved symbol
  gets a placeholder instrument (FR-IMP-05).

Idempotency is the database's job: fills insert with ON CONFLICT DO NOTHING on
`(account_id, kite_trade_id)`, so re-uploading a file adds nothing and cannot
double-count P&L (FR-IMP-03).
"""

from __future__ import annotations

import csv
import datetime as dt
import hashlib
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from io import StringIO
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Fill, ImportBatch, Instrument
from app.services import charges, instruments, sync_service
from app.timezone import IST, to_utc

logger = logging.getLogger("tj.importer")

PRICE_PLACES = Decimal("0.0001")
MAX_BYTES = 20 * 1024 * 1024

REQUIRED_COLUMNS = frozenset(
    {"symbol", "trade_date", "exchange", "trade_type", "quantity", "price"}
)

SIDE_BY_TRADE_TYPE = {"buy": "BUY", "sell": "SELL"}

INTRADAY_PRODUCT = "MIS"
DELIVERY_PRODUCT = "CNC"


class InvalidTradebook(Exception):
    """The file is not a Console tradebook we can read."""


@dataclass
class Rejection:
    row: int
    reason: str


@dataclass
class ParsedRow:
    row_number: int
    symbol: str
    exchange: str
    trade_date: dt.date
    side: str
    quantity: int
    price: Decimal
    trade_id: str
    order_id: str | None
    executed_at: dt.datetime
    had_timestamp: bool
    raw: dict[str, Any]
    product: str = INTRADAY_PRODUCT


@dataclass
class ImportReport:
    rows_read: int = 0
    rows_new: int = 0
    rows_dup: int = 0
    rows_rejected: int = 0
    batch_id: UUID | None = None
    date_from: dt.date | None = None
    date_to: dt.date | None = None
    columns: list[str] = field(default_factory=list)
    rejections: list[Rejection] = field(default_factory=list)
    products: dict[str, int] = field(default_factory=dict)
    symbols: list[str] = field(default_factory=list)
    unresolved_symbols: list[str] = field(default_factory=list)
    rows_without_timestamp: int = 0
    reassigned_trade_ids: int = 0
    preview: list[dict[str, Any]] = field(default_factory=list)


# ------------------------------------------------------------------ parsing


def _decimal(value: str) -> Decimal | None:
    text = (value or "").strip()
    if not text:
        return None
    try:
        return Decimal(text)
    except InvalidOperation:
        return None


def _parse_timestamp(value: str, trade_date: dt.date) -> tuple[dt.datetime, bool]:
    """Console writes IST wall clock with no offset, as Kite does everywhere.

    When the column is blank, the fill is placed at the start of the trading
    day. Ordering within the day then falls to the trade id, which rises
    through the session, so FIFO stays deterministic.
    """
    text = (value or "").strip()
    if text:
        for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
            try:
                return to_utc(dt.datetime.strptime(text, fmt)), True
            except ValueError:
                continue
    start = dt.datetime(trade_date.year, trade_date.month, trade_date.day, 9, 15, tzinfo=IST)
    return to_utc(start), False


def _deterministic_trade_id(row: ParsedRow) -> str:
    """FR-IMP-04: a stable id built from the row's own content."""
    payload = "|".join(
        [
            row.trade_date.isoformat(),
            row.symbol,
            row.side,
            str(row.quantity),
            f"{row.price:f}",
            row.order_id or "",
            row.executed_at.isoformat(),
        ]
    )
    return f"csv:{hashlib.sha1(payload.encode()).hexdigest()}"


def parse_tradebook(text: str) -> tuple[list[ParsedRow], list[Rejection], list[str]]:
    reader = csv.DictReader(StringIO(text))
    columns = [name.strip() for name in (reader.fieldnames or [])]
    if not columns:
        raise InvalidTradebook("the file has no header row")

    missing = REQUIRED_COLUMNS - {name.lower() for name in columns}
    if missing:
        raise InvalidTradebook("not a Console tradebook: missing " + ", ".join(sorted(missing)))

    parsed: list[ParsedRow] = []
    rejections: list[Rejection] = []

    for offset, raw in enumerate(reader, start=2):
        row = {(k or "").strip().lower(): (v or "") for k, v in raw.items()}

        symbol = row.get("symbol", "").strip().upper()
        exchange = row.get("exchange", "").strip().upper()
        if not symbol or not exchange:
            rejections.append(Rejection(offset, "missing symbol or exchange"))
            continue

        try:
            trade_date = dt.date.fromisoformat(row.get("trade_date", "").strip()[:10])
        except ValueError:
            rejections.append(Rejection(offset, "unreadable trade_date"))
            continue

        side = SIDE_BY_TRADE_TYPE.get(row.get("trade_type", "").strip().lower())
        if side is None:
            rejections.append(Rejection(offset, "unknown trade_type"))
            continue

        quantity = _decimal(row.get("quantity", ""))
        if quantity is None or quantity != quantity.to_integral_value() or quantity <= 0:
            rejections.append(Rejection(offset, "quantity must be a positive whole number"))
            continue

        price = _decimal(row.get("price", ""))
        if price is None or price < 0:
            rejections.append(Rejection(offset, "unreadable price"))
            continue

        executed_at, had_timestamp = _parse_timestamp(
            row.get("order_execution_time", ""), trade_date
        )

        parsed_row = ParsedRow(
            row_number=offset,
            symbol=symbol,
            exchange=exchange,
            trade_date=trade_date,
            side=side,
            quantity=int(quantity),
            # Console prints six decimals of float noise; the column holds
            # four, and rounding here is what makes gross P&L come out whole.
            price=price.quantize(PRICE_PLACES),
            trade_id=row.get("trade_id", "").strip(),
            order_id=row.get("order_id", "").strip() or None,
            executed_at=executed_at,
            had_timestamp=had_timestamp,
            raw={k: v for k, v in row.items() if k},
        )
        if not parsed_row.trade_id:
            parsed_row.trade_id = _deterministic_trade_id(parsed_row)
        parsed.append(parsed_row)

    return parsed, rejections, columns


# --------------------------------------------------------- product inference


@dataclass
class _Leg:
    key: Any
    side: str
    quantity: int
    trade_date: dt.date
    executed_at: dt.datetime
    sort_key: tuple


def infer_products(legs: list[_Leg]) -> dict[Any, str]:
    """Label each leg MIS or CNC by whether its position survived the day.

    Walks each symbol's fills in time order, tracking position episodes: an
    episode runs from flat to flat. If every fill in an episode shares one
    trade date the position never saw an overnight, so it is intraday.
    An episode still open at the end is carried, so it is delivery.
    """
    by_symbol: dict[str, list[_Leg]] = defaultdict(list)
    for leg in legs:
        by_symbol[leg.key[0]].append(leg)

    product_by_key: dict[Any, str] = {}

    for rows in by_symbol.values():
        position = 0
        episode: list[_Leg] = []
        for leg in sorted(rows, key=lambda item: item.sort_key):
            position += leg.quantity if leg.side == "BUY" else -leg.quantity
            episode.append(leg)
            if position == 0:
                dates = {item.trade_date for item in episode}
                product = INTRADAY_PRODUCT if len(dates) == 1 else DELIVERY_PRODUCT
                for item in episode:
                    product_by_key[item.key] = product
                episode = []
        # Anything still open was carried overnight, or is still open now.
        for item in episode:
            product_by_key[item.key] = DELIVERY_PRODUCT

    return product_by_key


def _leg_for_row(row: ParsedRow) -> _Leg:
    return _Leg(
        key=(row.symbol, row.trade_id),
        side=row.side,
        quantity=row.quantity,
        trade_date=row.trade_date,
        executed_at=row.executed_at,
        sort_key=(row.executed_at, row.trade_id),
    )


def _leg_for_fill(fill: Fill) -> _Leg:
    return _Leg(
        key=(fill.tradingsymbol, fill.kite_trade_id),
        side=fill.side,
        quantity=fill.quantity,
        trade_date=fill.trade_date,
        executed_at=fill.filled_at,
        sort_key=(fill.filled_at, fill.kite_trade_id),
    )


# ------------------------------------------------------- instrument resolution


def _placeholder_token(exchange: str, tradingsymbol: str) -> int:
    """A negative, deterministic token for a symbol the dump does not have.

    Negative because every real Kite token is positive, so a placeholder can
    never be mistaken for one or collide with it.
    """
    digest = hashlib.sha1(f"{exchange}|{tradingsymbol}".encode()).hexdigest()
    return -(int(digest[:12], 16) % 1_000_000_000_000 + 1)


def resolve_instrument(session: Session, exchange: str, symbol: str) -> Instrument:
    """Find the instrument, or create a placeholder for it (FR-IMP-05)."""
    found = instruments.resolve(session, exchange, symbol)
    if found is not None:
        return found

    token = _placeholder_token(exchange, symbol)
    existing = session.get(Instrument, token)
    if existing is not None:
        return existing

    try:
        instrument_type = charges.infer_instrument_type(exchange, symbol)
    except charges.UnknownSegment:
        instrument_type = None

    placeholder = Instrument(
        instrument_token=token,
        exchange=exchange,
        tradingsymbol=symbol,
        name=None,
        segment=None,
        instrument_type=instrument_type,
        asset_class=instruments.asset_class_for(exchange),
    )
    session.add(placeholder)
    session.flush()
    logger.info(
        "Created a placeholder instrument",
        extra={"event": "importer_placeholder_instrument"},
    )
    return placeholder


# ----------------------------------------------------------------- importing


def preview(text: str, *, limit: int = 20) -> ImportReport:
    """Parse and classify without writing anything (FR-IMP-01)."""
    rows, rejections, columns = parse_tradebook(text)
    report = ImportReport(
        rows_read=len(rows) + len(rejections),
        rows_rejected=len(rejections),
        rejections=rejections,
        columns=columns,
    )
    if not rows:
        return report

    products = infer_products([_leg_for_row(row) for row in rows])
    for row in rows:
        row.product = products.get((row.symbol, row.trade_id), INTRADAY_PRODUCT)

    _summarise(report, rows)
    report.preview = [
        {
            "trade_date": row.trade_date.isoformat(),
            "symbol": row.symbol,
            "exchange": row.exchange,
            "side": row.side,
            "quantity": row.quantity,
            "price": f"{row.price:f}",
            "product": row.product,
            "trade_id": row.trade_id,
        }
        for row in rows[:limit]
    ]
    return report


def _summarise(report: ImportReport, rows: list[ParsedRow]) -> None:
    dates = [row.trade_date for row in rows]
    report.date_from = min(dates)
    report.date_to = max(dates)
    report.symbols = sorted({row.symbol for row in rows})
    report.rows_without_timestamp = sum(1 for row in rows if not row.had_timestamp)
    counts: dict[str, int] = defaultdict(int)
    for row in rows:
        counts[row.product] += 1
    report.products = dict(sorted(counts.items()))


def import_tradebook(
    session: Session,
    account_id: UUID,
    text: str,
    *,
    filename: str | None = None,
    force_product: str | None = None,
) -> ImportReport:
    """Import a tradebook and bring every affected trade group up to date."""
    rows, rejections, columns = parse_tradebook(text)
    report = ImportReport(
        rows_read=len(rows) + len(rejections),
        rows_rejected=len(rejections),
        rejections=list(rejections),
        columns=columns,
    )
    if not rows:
        return report

    batch = ImportBatch(
        account_id=account_id,
        filename=filename,
        rows_read=report.rows_read,
        date_from=min(row.trade_date for row in rows),
        date_to=max(row.trade_date for row in rows),
    )
    session.add(batch)
    session.flush()
    report.batch_id = batch.id

    _guard_trade_id_collisions(session, account_id, rows, report)

    if force_product:
        for row in rows:
            row.product = force_product
    else:
        products = infer_products([_leg_for_row(row) for row in rows])
        for row in rows:
            row.product = products.get((row.symbol, row.trade_id), INTRADAY_PRODUCT)

    resolved: dict[tuple[str, str], Instrument] = {}
    fill_rows: list[dict[str, Any]] = []
    for row in rows:
        key = (row.exchange, row.symbol)
        if key not in resolved:
            resolved[key] = resolve_instrument(session, row.exchange, row.symbol)
        instrument = resolved[key]
        if instrument.instrument_token < 0:
            report.unresolved_symbols.append(row.symbol)

        fill_rows.append(
            {
                "account_id": account_id,
                "kite_trade_id": row.trade_id,
                "order_id": row.order_id,
                "exchange": row.exchange,
                "tradingsymbol": row.symbol,
                "instrument_token": instrument.instrument_token,
                "product": row.product,
                "side": row.side,
                "quantity": row.quantity,
                "price": row.price,
                "filled_at": row.executed_at,
                "trade_date": row.trade_date,
                "source": "csv",
                "import_batch_id": batch.id,
                "raw": row.raw,
            }
        )

    report.unresolved_symbols = sorted(set(report.unresolved_symbols))
    new, duplicate = sync_service.upsert_fills(session, fill_rows)
    report.rows_new = new
    report.rows_dup = duplicate

    batch.rows_new = new
    batch.rows_dup = duplicate
    batch.rows_rejected = report.rows_rejected
    session.flush()

    touched = _reconcile_products(session, account_id, rows, force_product=force_product)
    touched |= {(account_id, row["instrument_token"], row["product"]) for row in fill_rows}

    order_ids = {row["order_id"] for row in fill_rows if row["order_id"]}
    sync_service.process_touched(session, account_id, touched, order_ids)

    _summarise(report, rows)
    return report


def _guard_trade_id_collisions(
    session: Session, account_id: UUID, rows: list[ParsedRow], report: ImportReport
) -> None:
    """Exchange trade ids are unique per day, not for all time.

    A stored fill with the same id but a different date or symbol is a
    different trade, not a duplicate. Those rows get the deterministic id of
    FR-IMP-04 so the real fill is not silently dropped as a repeat.
    """
    candidates = {row.trade_id for row in rows if not row.trade_id.startswith("csv:")}
    if not candidates:
        return

    stored = {
        fill.kite_trade_id: fill
        for fill in session.execute(
            select(Fill).where(Fill.account_id == account_id, Fill.kite_trade_id.in_(candidates))
        ).scalars()
    }
    if not stored:
        return

    for row in rows:
        existing = stored.get(row.trade_id)
        if existing is None:
            continue
        if existing.trade_date != row.trade_date or existing.tradingsymbol != row.symbol:
            row.trade_id = _deterministic_trade_id(row)
            report.reassigned_trade_ids += 1


def _reconcile_products(
    session: Session,
    account_id: UUID,
    rows: list[ParsedRow],
    *,
    force_product: str | None,
) -> set[tuple[UUID, int, str]]:
    """Re-label stored CSV fills once a later export reveals the full picture.

    A position left open at the end of one export is CNC on the evidence
    available then. If a later file closes it on the same day, it was MIS all
    along. Only CSV fills are touched: an API fill always wins (FR-IMP-03).
    """
    touched: set[tuple[UUID, int, str]] = set()
    if force_product:
        return touched

    symbols = {row.symbol for row in rows}
    stored = list(
        session.execute(
            select(Fill).where(
                Fill.account_id == account_id,
                Fill.source == "csv",
                Fill.tradingsymbol.in_(symbols),
            )
        ).scalars()
    )
    if not stored:
        return touched

    products = infer_products([_leg_for_fill(fill) for fill in stored])
    for fill in stored:
        wanted = products.get((fill.tradingsymbol, fill.kite_trade_id))
        if wanted and wanted != fill.product:
            touched.add((account_id, fill.instrument_token, fill.product))
            fill.product = wanted
            touched.add((account_id, fill.instrument_token, wanted))
    session.flush()
    return touched
