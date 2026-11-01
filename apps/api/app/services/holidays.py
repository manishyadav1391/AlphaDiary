"""The NSE trading-holiday calendar (FR-REM-01, VERIFY V11).

Source: `https://www.nseindia.com/api/holiday-master?type=trading`, the
exchange's own list. The `CM` key is the Capital Market segment, which is the
one that decides whether equity trades at all that day.

A description ending in `*` is NSE's marker for a special session — Muhurat
trading on Diwali Laxmi Pujan, for example, which falls on a Sunday in 2026.
Those rows are stored with `is_trading_override` set, so the day counts as a
trading day even though it is a holiday or a weekend.

The fetch is a convenience, not a dependency: `seed/market_holidays.json`
holds a snapshot so the loader still works when NSE is unreachable, and the
worker only ever reads the database.
"""

from __future__ import annotations

import datetime as dt
import json
import logging
from pathlib import Path
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.models import MarketHoliday
from app.timezone import IST

logger = logging.getLogger("tj.holidays")

HOLIDAY_PAGE = "https://www.nseindia.com/resources/exchange-communication-holidays"
HOLIDAY_API = "https://www.nseindia.com/api/holiday-master?type=trading"

# The Capital Market segment. FO, CD and COM have their own lists; equity is
# what the journal defaults to (SRS 2, decision 1).
SEGMENT = "CM"

# NSE serves the JSON only to something that looks like a browser and has
# first visited the page.
_BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": HOLIDAY_PAGE,
}


class HolidayFetchFailed(Exception):
    """NSE did not return a usable holiday list."""


def parse_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Turn the NSE payload into `market_holiday` rows."""
    rows: list[dict[str, Any]] = []
    for entry in payload.get(SEGMENT, []):
        raw_date = str(entry.get("tradingDate", "")).strip()
        try:
            trade_date = dt.datetime.strptime(raw_date, "%d-%b-%Y").date()
        except ValueError:
            continue

        description = str(entry.get("description", "")).strip()
        # A trailing asterisk means the exchange runs a special session.
        special = description.endswith("*")
        rows.append(
            {
                "trade_date": trade_date,
                "description": description.rstrip("*").strip() or None,
                "is_trading_override": special,
            }
        )
    return rows


def fetch_rows(timeout: float = 20.0) -> list[dict[str, Any]]:
    try:
        with httpx.Client(
            timeout=timeout, headers=_BROWSER_HEADERS, follow_redirects=True
        ) as client:
            # The page sets the cookies the API checks for.
            client.get(HOLIDAY_PAGE)
            response = client.get(HOLIDAY_API)
            response.raise_for_status()
            payload = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise HolidayFetchFailed(str(exc)) from exc

    rows = parse_rows(payload)
    if not rows:
        raise HolidayFetchFailed(f"no {SEGMENT} rows in the response")
    return rows


def load_snapshot(path: Path) -> list[dict[str, Any]]:
    """The checked-in fallback, used when NSE cannot be reached."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    return [
        {
            "trade_date": dt.date.fromisoformat(row["trade_date"]),
            "description": row.get("description"),
            "is_trading_override": bool(row.get("is_trading_override", False)),
        }
        for row in payload["holidays"]
    ]


def save_snapshot(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text(
        json.dumps(
            {
                "_source": HOLIDAY_API,
                "_segment": SEGMENT,
                "_retrieved": dt.date.today().isoformat(),
                "_note": (
                    "is_trading_override marks a special session, such as "
                    "Muhurat trading on Diwali Laxmi Pujan."
                ),
                "holidays": [
                    {
                        "trade_date": row["trade_date"].isoformat(),
                        "description": row["description"],
                        "is_trading_override": row["is_trading_override"],
                    }
                    for row in sorted(rows, key=lambda item: item["trade_date"])
                ],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def store(session: Session, rows: list[dict[str, Any]]) -> int:
    """Upsert holidays. Idempotent, so re-running picks up amendments."""
    if not rows:
        return 0
    statement = pg_insert(MarketHoliday).values(rows)
    statement = statement.on_conflict_do_update(
        index_elements=[MarketHoliday.trade_date],
        set_={
            "description": statement.excluded.description,
            "is_trading_override": statement.excluded.is_trading_override,
        },
    )
    session.execute(statement)
    session.flush()
    return len(rows)


def is_trading_day(session: Session, day: dt.date) -> bool:
    """Monday to Friday and not a holiday, unless flagged as a special
    session (FR-REM-01)."""
    holiday = session.get(MarketHoliday, day)
    if holiday is not None:
        return bool(holiday.is_trading_override)
    return day.weekday() < 5


def trading_days_between(session: Session, start: dt.date, end: dt.date) -> list[dt.date]:
    holidays = {
        row.trade_date: row
        for row in session.execute(
            select(MarketHoliday).where(
                MarketHoliday.trade_date >= start, MarketHoliday.trade_date <= end
            )
        ).scalars()
    }
    days: list[dt.date] = []
    current = start
    while current <= end:
        holiday = holidays.get(current)
        if holiday is not None:
            if holiday.is_trading_override:
                days.append(current)
        elif current.weekday() < 5:
            days.append(current)
        current += dt.timedelta(days=1)
    return days


def today_ist() -> dt.date:
    return dt.datetime.now(IST).date()
