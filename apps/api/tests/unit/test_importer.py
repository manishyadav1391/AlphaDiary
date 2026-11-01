"""Console tradebook import (FR-IMP).

Runs against `tests/fixtures/console_tradebook_sample.csv`, an anonymised copy
of a real Console export: identical columns, row count, sides, quantities and
dates, with symbols, ids and prices changed. It keeps the structural cases
that matter — a four-fill order, a short opened before it is covered, and
scale-ins with partial exits.
"""

from __future__ import annotations

import datetime as dt
import uuid
from decimal import Decimal
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    BrokerAccount,
    ChargeRateSet,
    DailySummary,
    Fill,
    ImportBatch,
    Instrument,
    TradeGroup,
)
from app.services import importer, instruments, token_store

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
TRADEBOOK = FIXTURES / "console_tradebook_sample.csv"
SEED = Path(__file__).resolve().parents[3] / "seed" / "charge_rates.json"

# Tokens in the shape Kite uses, so resolution is exercised without pulling
# 110,000 rows into the test database.
FIXTURE_INSTRUMENTS = {
    "ALPHAIND": 139520004,
    "BETACORP": 139520260,
    "GAMMATEC": 139170564,
    "DELTAPWR": 136245764,
    "EPSILONFN": 139321604,
    "ZETAMOT": 136294404,
    "ETASTEEL": 139256836,
    "THETALAB": 136362756,
    "IOTAAGRO": 139464196,
}


def tradebook() -> str:
    return TRADEBOOK.read_text(encoding="utf-8")


@pytest.fixture
def instrument_master(session: Session) -> None:
    for symbol, token in FIXTURE_INSTRUMENTS.items():
        session.add(
            Instrument(
                instrument_token=token,
                exchange="NSE",
                tradingsymbol=symbol,
                name=symbol,
                segment="NSE",
                instrument_type="EQ",
                asset_class="equity",
                lot_size=1,
                tick_size=Decimal("0.05"),
            )
        )
    session.flush()


@pytest.fixture
def rate_set(session: Session) -> ChargeRateSet:
    import json

    config = json.loads(SEED.read_text(encoding="utf-8"))
    row = ChargeRateSet(
        effective_from=dt.date.fromisoformat(config["effective_from"]),
        label=str(config["label"]),
        config=config,
    )
    session.add(row)
    session.flush()
    return row


# ------------------------------------------------------------------ parsing


def test_the_real_column_set_is_accepted() -> None:
    rows, rejections, columns = importer.parse_tradebook(tradebook())

    assert columns == [
        "symbol",
        "isin",
        "trade_date",
        "exchange",
        "segment",
        "series",
        "trade_type",
        "auction",
        "quantity",
        "price",
        "trade_id",
        "order_id",
        "order_execution_time",
    ]
    assert len(rows) == 29
    assert rejections == []


def test_a_file_that_is_not_a_tradebook_is_refused() -> None:
    with pytest.raises(importer.InvalidTradebook):
        importer.parse_tradebook("a,b,c\n1,2,3\n")


def test_quantity_is_a_whole_number_despite_the_float_formatting() -> None:
    """Console writes 20.000000, not 20."""
    rows, _, _ = importer.parse_tradebook(tradebook())

    assert all(isinstance(row.quantity, int) for row in rows)
    assert rows[0].quantity == 20


def test_price_is_decimal_quantized_to_four_places() -> None:
    """Console prints six decimals of float noise; the column holds four."""
    rows, _, _ = importer.parse_tradebook(tradebook())

    for row in rows:
        assert isinstance(row.price, Decimal)
        assert -row.price.as_tuple().exponent == 4


def test_execution_time_is_read_as_ist_and_stored_utc() -> None:
    rows, _, _ = importer.parse_tradebook(tradebook())
    first = rows[0]

    # 2026-10-27T14:12:33 IST is 08:42:33 UTC.
    assert first.executed_at == dt.datetime(2026, 10, 27, 8, 42, 33, tzinfo=dt.UTC)
    assert first.trade_date == dt.date(2026, 10, 27)


def test_sides_are_normalised_to_upper_case() -> None:
    rows, _, _ = importer.parse_tradebook(tradebook())

    assert {row.side for row in rows} == {"BUY", "SELL"}


@pytest.mark.parametrize(
    ("bad_row", "reason"),
    [
        ("X,,2026-10-27,NSE,EQ,EQ,buy,false,0.000000,10.0,1,2,", "quantity"),
        ("X,,2026-10-27,NSE,EQ,EQ,hedge,false,1.000000,10.0,1,2,", "trade_type"),
        ("X,,not-a-date,NSE,EQ,EQ,buy,false,1.000000,10.0,1,2,", "trade_date"),
        (",,2026-10-27,NSE,EQ,EQ,buy,false,1.000000,10.0,1,2,", "symbol"),
        ("X,,2026-10-27,NSE,EQ,EQ,buy,false,1.5,10.0,1,2,", "whole number"),
    ],
)
def test_bad_rows_are_rejected_with_a_reason(bad_row: str, reason: str) -> None:
    header = tradebook().splitlines()[0]
    rows, rejections, _ = importer.parse_tradebook(f"{header}\n{bad_row}\n")

    assert rows == []
    assert len(rejections) == 1
    assert reason in rejections[0].reason


def test_a_row_without_a_trade_id_gets_a_deterministic_one() -> None:
    """FR-IMP-04."""
    header = tradebook().splitlines()[0]
    line = "X,,2026-10-27,NSE,EQ,EQ,buy,false,1.000000,10.0,,ORD1,2026-10-27T09:20:00"

    first, _, _ = importer.parse_tradebook(f"{header}\n{line}\n")
    again, _, _ = importer.parse_tradebook(f"{header}\n{line}\n")

    assert first[0].trade_id.startswith("csv:")
    assert first[0].trade_id == again[0].trade_id


def test_a_missing_execution_time_falls_back_to_the_open() -> None:
    header = tradebook().splitlines()[0]
    line = "X,,2026-10-27,NSE,EQ,EQ,buy,false,1.000000,10.0,T1,ORD1,"

    rows, _, _ = importer.parse_tradebook(f"{header}\n{line}\n")

    assert rows[0].had_timestamp is False
    assert rows[0].executed_at == dt.datetime(2026, 10, 27, 3, 45, tzinfo=dt.UTC)


# -------------------------------------------------------- product inference


def test_same_day_round_trips_are_intraday() -> None:
    """Every position in the fixture opens and closes within its own day."""
    report = importer.preview(tradebook())

    assert report.products == {"MIS": 29}


def test_a_position_carried_overnight_is_delivery() -> None:
    header = tradebook().splitlines()[0]
    lines = [
        "X,,2026-10-27,NSE,EQ,EQ,buy,false,10.000000,100.0,T1,O1,2026-10-27T09:20:00",
        "X,,2026-10-28,NSE,EQ,EQ,sell,false,10.000000,110.0,T2,O2,2026-10-28T09:20:00",
    ]

    rows, _, _ = importer.parse_tradebook(f"{header}\n" + "\n".join(lines) + "\n")
    products = importer.infer_products([importer._leg_for_row(row) for row in rows])

    assert set(products.values()) == {"CNC"}


def test_a_position_still_open_at_the_end_is_delivery() -> None:
    header = tradebook().splitlines()[0]
    line = "X,,2026-10-27,NSE,EQ,EQ,buy,false,10.000000,100.0,T1,O1,2026-10-27T09:20:00"

    rows, _, _ = importer.parse_tradebook(f"{header}\n{line}\n")
    products = importer.infer_products([importer._leg_for_row(row) for row in rows])

    assert set(products.values()) == {"CNC"}


def test_an_intraday_day_followed_by_a_carried_one_is_split() -> None:
    """Two episodes in one symbol are classified independently."""
    header = tradebook().splitlines()[0]
    lines = [
        "X,,2026-10-27,NSE,EQ,EQ,buy,false,10.000000,100.0,T1,O1,2026-10-27T09:20:00",
        "X,,2026-10-27,NSE,EQ,EQ,sell,false,10.000000,101.0,T2,O2,2026-10-27T14:20:00",
        "X,,2026-10-28,NSE,EQ,EQ,buy,false,10.000000,102.0,T3,O3,2026-10-28T09:20:00",
        "X,,2026-10-29,NSE,EQ,EQ,sell,false,10.000000,103.0,T4,O4,2026-10-29T09:20:00",
    ]

    rows, _, _ = importer.parse_tradebook(f"{header}\n" + "\n".join(lines) + "\n")
    products = importer.infer_products([importer._leg_for_row(row) for row in rows])

    assert products[("X", "T1")] == "MIS"
    assert products[("X", "T2")] == "MIS"
    assert products[("X", "T3")] == "CNC"
    assert products[("X", "T4")] == "CNC"


# --------------------------------------------------------------- preview


def test_preview_writes_nothing(session: Session, connected_account: BrokerAccount) -> None:
    """FR-IMP-01."""
    report = importer.preview(tradebook())

    assert report.rows_read == 29
    assert report.date_from == dt.date(2026, 10, 27)
    assert report.date_to == dt.date(2026, 10, 30)
    assert len(report.preview) == 20
    assert session.execute(select(Fill)).first() is None


# ---------------------------------------------------------------- importing


def test_import_stores_fills_and_matches_them(
    session: Session,
    connected_account: BrokerAccount,
    instrument_master: None,
    rate_set: ChargeRateSet,
) -> None:
    account = token_store.require_account(session)

    report = importer.import_tradebook(session, account.id, tradebook(), filename="tb.csv")

    assert report.rows_new == 29
    assert report.rows_dup == 0
    assert report.rows_rejected == 0
    assert report.unresolved_symbols == []
    assert session.execute(select(Fill)).unique().scalars().all()

    groups = list(session.execute(select(TradeGroup)).scalars())
    assert groups
    assert all(group.status == "closed" for group in groups)


def test_imported_fills_carry_csv_provenance(
    session: Session,
    connected_account: BrokerAccount,
    instrument_master: None,
    rate_set: ChargeRateSet,
) -> None:
    """FR-IMP-02 and FR-IMP-08."""
    account = token_store.require_account(session)

    report = importer.import_tradebook(session, account.id, tradebook(), filename="tb.csv")

    fills = list(session.execute(select(Fill)).scalars())
    assert all(fill.source == "csv" for fill in fills)
    assert all(fill.import_batch_id == report.batch_id for fill in fills)
    assert all(fill.instrument_token > 0 for fill in fills)

    batch = session.get(ImportBatch, report.batch_id)
    assert batch is not None
    assert batch.filename == "tb.csv"
    assert batch.rows_new == 29


def test_net_pnl_is_computed_for_every_group(
    session: Session,
    connected_account: BrokerAccount,
    instrument_master: None,
    rate_set: ChargeRateSet,
) -> None:
    """The milestone's acceptance: matched trades with valid net P&L."""
    account = token_store.require_account(session)
    importer.import_tradebook(session, account.id, tradebook())

    for group in session.execute(select(TradeGroup)).scalars():
        assert isinstance(group.net_pnl, Decimal)
        assert group.charges_total > Decimal("0")
        assert group.net_pnl == group.gross_pnl - group.charges_total


def test_a_short_is_matched_as_a_short(
    session: Session,
    connected_account: BrokerAccount,
    instrument_master: None,
    rate_set: ChargeRateSet,
) -> None:
    """THETALAB sells before it buys on 30 Oct."""
    account = token_store.require_account(session)
    importer.import_tradebook(session, account.id, tradebook())

    group = session.execute(
        select(TradeGroup).where(TradeGroup.tradingsymbol == "THETALAB")
    ).scalar_one()

    assert group.direction == "SHORT"
    assert group.status == "closed"


def test_a_four_fill_order_pays_brokerage_once(
    session: Session,
    connected_account: BrokerAccount,
    instrument_master: None,
    rate_set: ChargeRateSet,
) -> None:
    """ZETAMOT has one order filled four times: the cap applies per order."""
    from app.models import OrderCharge

    account = token_store.require_account(session)
    importer.import_tradebook(session, account.id, tradebook())

    multi = session.execute(
        select(Fill.order_id).where(Fill.tradingsymbol == "ZETAMOT").group_by(Fill.order_id)
    ).scalars()

    for order_id in multi:
        charge = session.get(OrderCharge, order_id)
        assert charge is not None
        assert charge.brokerage <= Decimal("20.00")


def test_daily_summaries_are_built_for_every_traded_day(
    session: Session,
    connected_account: BrokerAccount,
    instrument_master: None,
    rate_set: ChargeRateSet,
) -> None:
    """FR-IMP-07."""
    account = token_store.require_account(session)
    importer.import_tradebook(session, account.id, tradebook())

    days = {row.trade_date for row in session.execute(select(DailySummary)).scalars()}

    assert days == {
        dt.date(2026, 10, 27),
        dt.date(2026, 10, 28),
        dt.date(2026, 10, 29),
        dt.date(2026, 10, 30),
    }


# -------------------------------------------------------------- idempotency


def test_reimporting_the_same_file_adds_nothing(
    session: Session,
    connected_account: BrokerAccount,
    instrument_master: None,
    rate_set: ChargeRateSet,
) -> None:
    """FR-IMP-03, and the milestone's stated requirement."""
    account = token_store.require_account(session)

    first = importer.import_tradebook(session, account.id, tradebook())
    before = _snapshot(session)
    second = importer.import_tradebook(session, account.id, tradebook())
    after = _snapshot(session)

    assert first.rows_new == 29
    assert second.rows_new == 0
    assert second.rows_dup == 29
    assert before == after
    assert session.execute(select(Fill)).unique().scalars().all().__len__() == 29


def test_reimporting_does_not_double_count_pnl(
    session: Session,
    connected_account: BrokerAccount,
    instrument_master: None,
    rate_set: ChargeRateSet,
) -> None:
    account = token_store.require_account(session)

    importer.import_tradebook(session, account.id, tradebook())
    first_total = _net_total(session)
    importer.import_tradebook(session, account.id, tradebook())
    second_total = _net_total(session)

    assert first_total == second_total


def test_a_later_file_reclassifies_a_position_it_closes(
    session: Session,
    connected_account: BrokerAccount,
    instrument_master: None,
    rate_set: ChargeRateSet,
) -> None:
    """An open position is CNC on the evidence so far. If a later export
    closes it the same day, it was intraday all along."""
    account = token_store.require_account(session)
    header = tradebook().splitlines()[0]
    buy = "ALPHAIND,,2026-11-02,NSE,EQ,EQ,buy,false,10.000000,100.0,N1,ON1,2026-11-02T09:20:00"
    sell = "ALPHAIND,,2026-11-02,NSE,EQ,EQ,sell,false,10.000000,105.0,N2,ON2,2026-11-02T14:20:00"

    importer.import_tradebook(session, account.id, f"{header}\n{buy}\n")
    opened = session.execute(select(Fill).where(Fill.kite_trade_id == "N1")).scalar_one()
    assert opened.product == "CNC"

    importer.import_tradebook(session, account.id, f"{header}\n{buy}\n{sell}\n")

    session.refresh(opened)
    assert opened.product == "MIS"


def test_a_reused_trade_id_on_another_day_is_kept_as_a_separate_fill(
    session: Session,
    connected_account: BrokerAccount,
    instrument_master: None,
    rate_set: ChargeRateSet,
) -> None:
    """Exchange trade ids repeat across days; a collision must not swallow a
    real fill as a duplicate."""
    account = token_store.require_account(session)
    header = tradebook().splitlines()[0]
    day_one = (
        "ALPHAIND,,2026-11-02,NSE,EQ,EQ,buy,false,10.000000,100.0,REUSED,O1,2026-11-02T09:20:00"
    )
    day_two = (
        "BETACORP,,2026-11-03,NSE,EQ,EQ,buy,false,10.000000,100.0,REUSED,O2,2026-11-03T09:20:00"
    )

    importer.import_tradebook(session, account.id, f"{header}\n{day_one}\n")
    report = importer.import_tradebook(session, account.id, f"{header}\n{day_two}\n")

    assert report.rows_new == 1
    assert report.reassigned_trade_ids == 1
    assert session.execute(select(Fill)).unique().scalars().all().__len__() == 2


# ------------------------------------------------- instrument resolution


def test_an_unknown_symbol_gets_a_negative_placeholder_token(
    session: Session, connected_account: BrokerAccount, rate_set: ChargeRateSet
) -> None:
    """FR-IMP-05. Negative, so it can never be mistaken for a real token."""
    account = token_store.require_account(session)
    header = tradebook().splitlines()[0]
    line = "NOTLISTED,,2026-10-27,NSE,EQ,EQ,buy,false,1.000000,10.0,T1,O1,2026-10-27T09:20:00"

    report = importer.import_tradebook(session, account.id, f"{header}\n{line}\n")

    assert report.unresolved_symbols == ["NOTLISTED"]
    fill = session.execute(select(Fill)).scalar_one()
    assert fill.instrument_token < 0


def test_the_placeholder_token_is_stable_across_imports() -> None:
    first = importer._placeholder_token("NSE", "NOTLISTED")
    again = importer._placeholder_token("NSE", "NOTLISTED")

    assert first == again < 0
    assert first != importer._placeholder_token("BSE", "NOTLISTED")


def test_the_instruments_dump_parses_into_instrument_rows() -> None:
    """The published dump header, verbatim."""
    dump = (
        "instrument_token,exchange_token,tradingsymbol,name,last_price,expiry,"
        "strike,tick_size,lot_size,instrument_type,segment,exchange\n"
        '408065,1594,INFY,"INFOSYS",0,,0,0.05,1,EQ,NSE,NSE\n'
        '12345678,48225,NIFTY26NOV24500CE,"NIFTY",0,2026-11-26,24500,0.05,75,CE,NFO-OPT,NFO\n'
    )

    rows = list(instruments.parse_dump(dump))

    assert rows[0]["tradingsymbol"] == "INFY"
    assert rows[0]["asset_class"] == "equity"
    assert rows[1]["instrument_type"] == "CE"
    assert rows[1]["asset_class"] == "fno"
    assert rows[1]["expiry"] == dt.date(2026, 11, 26)
    assert rows[1]["strike"] == Decimal("24500")
    assert rows[1]["lot_size"] == 75


# ------------------------------------------------------------------ route


def test_upload_endpoint_imports_the_file(
    authenticated_client: TestClient,
    session: Session,
    connected_account: BrokerAccount,
    instrument_master: None,
    rate_set: ChargeRateSet,
) -> None:
    response = authenticated_client.post(
        "/api/v1/import/tradebook",
        files={"file": ("tradebook.csv", tradebook(), "text/csv")},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["rows_new"] == 29
    assert body["rows_rejected"] == 0
    assert body["products"] == {"MIS": 29}
    assert body["date_from"] == "2026-10-27"


def test_upload_endpoint_honours_a_forced_product(
    authenticated_client: TestClient,
    session: Session,
    connected_account: BrokerAccount,
    instrument_master: None,
    rate_set: ChargeRateSet,
) -> None:
    response = authenticated_client.post(
        "/api/v1/import/tradebook",
        files={"file": ("tradebook.csv", tradebook(), "text/csv")},
        data={"product": "CNC"},
    )

    assert response.status_code == 200, response.text
    assert response.json()["products"] == {"CNC": 29}
    assert {fill.product for fill in session.execute(select(Fill)).scalars()} == {"CNC"}


def test_upload_endpoint_rejects_an_unknown_product(
    authenticated_client: TestClient, connected_account: BrokerAccount
) -> None:
    response = authenticated_client.post(
        "/api/v1/import/tradebook",
        files={"file": ("tradebook.csv", tradebook(), "text/csv")},
        data={"product": "SWING"},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_product"


def test_upload_endpoint_rejects_a_file_that_is_not_a_tradebook(
    authenticated_client: TestClient, connected_account: BrokerAccount
) -> None:
    response = authenticated_client.post(
        "/api/v1/import/tradebook",
        files={"file": ("notes.csv", "a,b,c\n1,2,3\n", "text/csv")},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_tradebook"


def test_preview_endpoint_writes_nothing(
    authenticated_client: TestClient, session: Session, connected_account: BrokerAccount
) -> None:
    response = authenticated_client.post(
        "/api/v1/import/tradebook/preview",
        files={"file": ("tradebook.csv", tradebook(), "text/csv")},
    )

    assert response.status_code == 200, response.text
    assert response.json()["rows_read"] == 29
    assert session.execute(select(Fill)).first() is None


def test_the_upload_endpoint_needs_a_session(client: TestClient) -> None:
    response = client.post(
        "/api/v1/import/tradebook",
        files={"file": ("tradebook.csv", tradebook(), "text/csv")},
    )

    assert response.status_code == 401


# ----------------------------------------------------------------- helpers


def _snapshot(session: Session) -> list[tuple]:
    return sorted(
        (g.group_key, g.status, g.gross_pnl, g.charges_total, g.net_pnl)
        for g in session.execute(select(TradeGroup)).scalars()
    )


def _net_total(session: Session) -> Decimal:
    return sum(
        (g.net_pnl for g in session.execute(select(TradeGroup)).scalars()),
        start=Decimal("0"),
    )


def _unused() -> uuid.UUID:
    return uuid.uuid4()
