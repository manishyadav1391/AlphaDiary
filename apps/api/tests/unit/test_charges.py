"""The charges engine (FR-CHG, SRS 7.3).

No rate is written in this file except inside a rate set built for a test.
Real rates live in `seed/charge_rates.json`, which is transcribed from
Zerodha's published charges page (FR-CHG-07, VERIFY V9).
"""

from __future__ import annotations

import datetime as dt
import json
import uuid
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from app.models import ChargeRateSet, Fill, FillCharge, OrderCharge
from app.services import charges

SEED = Path(__file__).resolve().parents[3] / "seed" / "charge_rates.json"

ACCOUNT = uuid.UUID("11111111-1111-1111-1111-111111111111")
DAY = dt.date(2026, 11, 2)


# A deliberately simple rate set: round numbers make the arithmetic checkable
# by hand, so a failure points at the engine and not at a rate.
SIMPLE = {
    "effective_from": "2026-01-01",
    "rounding": "half_up_2dp",
    "gst_rate": "18",
    "segments": {
        "eq_intraday": {
            "brokerage": {
                "type": "min_of_flat_or_percent",
                "flat": "20",
                "percent": "0.03",
                "side": "both",
            },
            "stt_ctt": {"type": "percent", "percent": "0.025", "side": "sell"},
            "exchange_txn": {"type": "percent", "percent": "0.01", "side": "both"},
            "sebi": {"type": "percent", "percent": "0.0001", "side": "both"},
            "stamp": {"type": "percent", "percent": "0.003", "side": "buy"},
            "other_levy": {"type": "zero"},
        },
        "eq_delivery": {
            "brokerage": {"type": "zero"},
            "stt_ctt": {"type": "percent", "percent": "0.1", "side": "both"},
            "exchange_txn": {"type": "percent", "percent": "0.01", "side": "both"},
            "sebi": {"type": "percent", "percent": "0.0001", "side": "both"},
            "stamp": {"type": "percent", "percent": "0.015", "side": "buy"},
            "other_levy": {"type": "zero"},
        },
        "opt": {
            "brokerage": {"type": "flat", "flat": "20", "side": "both"},
            "stt_ctt": {"type": "percent", "percent": "0.1", "side": "sell"},
            "exchange_txn": {"type": "percent", "percent": "0.05", "side": "both"},
            "sebi": {"type": "percent", "percent": "0.0001", "side": "both"},
            "stamp": {"type": "percent", "percent": "0.003", "side": "buy"},
            "other_levy": {"type": "zero"},
        },
    },
}


def rates(config: dict | None = None) -> charges.RateSet:
    return charges.RateSet(config or SIMPLE)


def fill(
    side: str,
    quantity: int,
    price: str,
    *,
    order_id: str = "O1",
    exchange: str = "NSE",
    tradingsymbol: str = "SBIN",
    product: str = "MIS",
    token: int = 779521,
    day: dt.date = DAY,
) -> Fill:
    return Fill(
        id=uuid.uuid4(),
        account_id=ACCOUNT,
        kite_trade_id=uuid.uuid4().hex[:12],
        order_id=order_id,
        exchange=exchange,
        tradingsymbol=tradingsymbol,
        instrument_token=token,
        product=product,
        side=side,
        quantity=quantity,
        price=Decimal(price),
        filled_at=dt.datetime(2026, 11, 2, 4, 0, tzinfo=dt.UTC),
        trade_date=day,
        source="api",
    )


# ------------------------------------------------------- segment mapping


@pytest.mark.parametrize(
    ("exchange", "instrument_type", "product", "expected"),
    [
        ("NSE", "EQ", "MIS", "eq_intraday"),
        ("BSE", "EQ", "MIS", "eq_intraday"),
        ("NSE", "EQ", "CNC", "eq_delivery"),
        ("NSE", "EQ", "NRML", "eq_delivery"),
        ("NSE", "EQ", "MTF", "eq_delivery"),
        ("NFO", "FUT", "NRML", "fut"),
        ("BFO", "FUT", "MIS", "fut"),
        ("NFO", "CE", "MIS", "opt"),
        ("NFO", "PE", "NRML", "opt"),
        ("MCX", "FUT", "NRML", "comm_fut"),
        ("MCX", "CE", "NRML", "comm_opt"),
        ("CDS", "FUT", "NRML", "cur_fut"),
        ("BCD", "PE", "NRML", "cur_opt"),
    ],
)
def test_segment_mapping(exchange: str, instrument_type: str, product: str, expected: str) -> None:
    """SRS 7.3 mapping table. FR-CHG-03 requires it to be a pure function."""
    assert charges.segment_for(exchange, instrument_type, product) == expected


def test_unknown_exchange_is_an_error_not_a_guess() -> None:
    with pytest.raises(charges.UnknownSegment):
        charges.segment_for("XYZ", "EQ", "MIS")


@pytest.mark.parametrize(
    ("exchange", "tradingsymbol", "expected"),
    [
        ("NSE", "SBIN", "EQ"),
        ("BSE", "RELIANCE", "EQ"),
        ("NFO", "NIFTY26NOV24500CE", "CE"),
        ("NFO", "BANKNIFTY26NOV54000PE", "PE"),
        ("NFO", "NIFTY26NOVFUT", "FUT"),
        ("MCX", "CRUDEOIL26NOVFUT", "FUT"),
        ("CDS", "USDINR26NOVFUT", "FUT"),
    ],
)
def test_instrument_type_inferred_from_tradingsymbol(
    exchange: str, tradingsymbol: str, expected: str
) -> None:
    assert charges.infer_instrument_type(exchange, tradingsymbol) == expected


def test_an_underivable_instrument_type_is_an_error() -> None:
    with pytest.raises(charges.UnknownSegment):
        charges.infer_instrument_type("NFO", "SOMETHINGODD")


# ------------------------------------------------------------- brokerage


def test_brokerage_is_capped_per_order() -> None:
    """FR-CHG-05: the lower of the flat fee or the percentage."""
    # 0.03% of 80,000 is 24, so the 20 cap wins.
    big = charges.compute_order_charge([fill("BUY", 100, "800")], rates())
    assert big.brokerage == Decimal("20.00")

    # 0.03% of 10,000 is 3, which is under the cap.
    small = charges.compute_order_charge([fill("BUY", 100, "100")], rates())
    assert small.brokerage == Decimal("3.00")


def test_the_cap_applies_to_the_order_not_to_each_fill() -> None:
    """FR-CHG-01: brokerage is per executed order, which is the whole reason
    charges are computed per order and then allocated down to fills."""
    one_fill = charges.compute_order_charge([fill("BUY", 300, "800")], rates())
    three_fills = charges.compute_order_charge(
        [fill("BUY", 100, "800"), fill("BUY", 100, "800"), fill("BUY", 100, "800")],
        rates(),
    )

    assert one_fill.brokerage == Decimal("20.00")
    assert three_fills.brokerage == Decimal("20.00")


def test_delivery_brokerage_is_zero() -> None:
    charge = charges.compute_order_charge([fill("BUY", 100, "800", product="CNC")], rates())
    assert charge.brokerage == Decimal("0.00")


def test_option_brokerage_is_flat_regardless_of_turnover() -> None:
    charge = charges.compute_order_charge(
        [fill("BUY", 75, "112.40", exchange="NFO", tradingsymbol="NIFTY26NOV24500CE")],
        rates(),
    )
    assert charge.brokerage == Decimal("20.00")


# ------------------------------------------------------ side application


def test_intraday_stt_applies_to_the_sell_side_only() -> None:
    buy = charges.compute_order_charge([fill("BUY", 100, "800")], rates())
    sell = charges.compute_order_charge([fill("SELL", 100, "800")], rates())

    assert buy.stt_ctt == Decimal("0.00")
    # 0.025% of 80,000
    assert sell.stt_ctt == Decimal("20.00")


def test_delivery_stt_applies_to_both_sides() -> None:
    buy = charges.compute_order_charge([fill("BUY", 100, "800", product="CNC")], rates())
    assert buy.stt_ctt == Decimal("80.00")


def test_stamp_duty_applies_to_the_buy_side_only() -> None:
    buy = charges.compute_order_charge([fill("BUY", 100, "800")], rates())
    sell = charges.compute_order_charge([fill("SELL", 100, "800")], rates())

    assert buy.stamp == Decimal("2.40")
    assert sell.stamp == Decimal("0.00")


# -------------------------------------------------------------- GST, total


def test_gst_applies_to_brokerage_exchange_sebi_and_other_levy_only() -> None:
    """FR-CHG-04: never on STT or stamp duty."""
    charge = charges.compute_order_charge([fill("BUY", 100, "800")], rates())

    base = charge.brokerage + charge.exchange_txn + charge.sebi + charge.other_levy
    assert charge.gst == (base * Decimal("0.18")).quantize(Decimal("0.01"))
    assert charge.gst != ((base + charge.stamp + charge.stt_ctt) * Decimal("0.18")).quantize(
        Decimal("0.01")
    )


def test_total_is_the_sum_of_every_component() -> None:
    charge = charges.compute_order_charge([fill("SELL", 100, "810")], rates())

    assert charge.total == (
        charge.brokerage
        + charge.stt_ctt
        + charge.exchange_txn
        + charge.sebi
        + charge.stamp
        + charge.other_levy
        + charge.gst
    )


def test_every_component_is_decimal_at_two_places() -> None:
    charge = charges.compute_order_charge([fill("SELL", 37, "812.35")], rates())

    for value in charge.as_dict().values():
        assert isinstance(value, Decimal)
        assert -value.as_tuple().exponent == 2


def test_rounding_is_half_up() -> None:
    """0.005 rounds to 0.01, not to 0.00 as banker's rounding would."""
    assert charges.round_money(Decimal("0.005")) == Decimal("0.01")
    assert charges.round_money(Decimal("0.015")) == Decimal("0.02")
    assert charges.round_money(Decimal("2.455")) == Decimal("2.46")


# ------------------------------------------------------------- allocation


def test_allocation_sums_exactly_to_the_order_total() -> None:
    """FR-CHG-06: the last fill absorbs the rounding remainder."""
    fills = [fill("BUY", 33, "800"), fill("BUY", 33, "800"), fill("BUY", 34, "800")]
    charge = charges.compute_order_charge(fills, rates())

    allocated = charges.allocate_to_fills(charge, fills)

    assert sum(part.total for part in allocated.values()) == charge.total
    for component in ("brokerage", "stt_ctt", "exchange_txn", "sebi", "stamp", "gst"):
        assert sum(getattr(part, component) for part in allocated.values()) == getattr(
            charge, component
        )


def test_allocation_is_proportional_to_turnover() -> None:
    small = fill("BUY", 25, "800")
    large = fill("BUY", 75, "800")
    charge = charges.compute_order_charge([small, large], rates())

    allocated = charges.allocate_to_fills(charge, [small, large])

    assert allocated[large.id].total > allocated[small.id].total * Decimal("2.5")


def test_a_single_fill_takes_the_whole_order_charge() -> None:
    only_fill = fill("BUY", 100, "800")
    charge = charges.compute_order_charge([only_fill], rates())

    allocated = charges.allocate_to_fills(charge, [only_fill])

    assert allocated[only_fill.id].total == charge.total


# ------------------------------------------------------- effective dating


def test_the_rate_set_in_force_on_the_trade_date_is_used(session: Session) -> None:
    """FR-CHG-02: old trades keep old rates."""
    session.add(ChargeRateSet(effective_from=dt.date(2025, 4, 1), label="old", config=SIMPLE))
    newer = dict(SIMPLE, effective_from="2026-04-01")
    session.add(ChargeRateSet(effective_from=dt.date(2026, 4, 1), label="new", config=newer))
    session.flush()

    assert charges.rate_set_for(session, dt.date(2025, 6, 1)).label == "old"
    assert charges.rate_set_for(session, dt.date(2026, 4, 1)).label == "new"
    assert charges.rate_set_for(session, dt.date(2026, 11, 2)).label == "new"


def test_a_trade_before_every_rate_set_is_an_error_not_a_guess(session: Session) -> None:
    session.add(ChargeRateSet(effective_from=dt.date(2026, 4, 1), label="new", config=SIMPLE))
    session.flush()

    with pytest.raises(charges.NoRateSet):
        charges.rate_set_for(session, dt.date(2020, 1, 1))


# ------------------------------------------------------------- seed file


def test_the_seed_file_covers_every_segment_key() -> None:
    """FR-CHG-03 names eight segments; all are in scope per SRS 2, decision 2."""
    config = json.loads(SEED.read_text(encoding="utf-8"))

    assert set(config["segments"]) == set(charges.SEGMENT_KEYS)


def test_the_seed_file_records_where_its_rates_came_from() -> None:
    """FR-CHG-07: rates are transcribed, never invented."""
    config = json.loads(SEED.read_text(encoding="utf-8"))

    assert "zerodha.com/charges" in json.dumps(config["_source"])


def test_the_seed_file_has_no_unfilled_placeholders_for_the_core_segments() -> None:
    config = json.loads(SEED.read_text(encoding="utf-8"))
    core = ("eq_intraday", "eq_delivery", "fut", "opt")

    blob = json.dumps({key: config["segments"][key] for key in core})
    assert "<" not in blob


# ------------------------------------------------- a worked order, end to end


def test_worked_equity_intraday_order_against_the_seed_rates() -> None:
    """Buy 100 SBIN at 800 on NSE, intraday, using the shipped rate set.

    Pinning the total here is a regression lock: if a rate moves, this fails
    and the seed file has to be updated deliberately.
    """
    config = json.loads(SEED.read_text(encoding="utf-8"))
    charge = charges.compute_order_charge([fill("BUY", 100, "800")], charges.RateSet(config))

    assert charge.brokerage == Decimal("20.00")
    assert charge.stt_ctt == Decimal("0.00")
    assert charge.exchange_txn == Decimal("2.46")
    assert charge.sebi == Decimal("0.08")
    assert charge.stamp == Decimal("2.40")
    assert charge.gst == Decimal("4.06")
    assert charge.total == Decimal("29.00")


def test_worked_equity_intraday_sell_against_the_seed_rates() -> None:
    config = json.loads(SEED.read_text(encoding="utf-8"))
    charge = charges.compute_order_charge([fill("SELL", 100, "810")], charges.RateSet(config))

    assert charge.brokerage == Decimal("20.00")
    assert charge.stt_ctt == Decimal("20.25")
    assert charge.exchange_txn == Decimal("2.49")
    assert charge.sebi == Decimal("0.08")
    assert charge.stamp == Decimal("0.00")
    assert charge.gst == Decimal("4.06")
    assert charge.total == Decimal("46.88")


def test_bse_uses_its_own_transaction_rate() -> None:
    """The published rates differ by exchange; the rate set carries overrides."""
    config = json.loads(SEED.read_text(encoding="utf-8"))
    rate_set = charges.RateSet(config)

    nse = charges.compute_order_charge([fill("BUY", 100, "800")], rate_set)
    bse = charges.compute_order_charge([fill("BUY", 100, "800", exchange="BSE")], rate_set)

    assert bse.exchange_txn > nse.exchange_txn


# --------------------------------------------------------------- persistence


def test_compute_charges_is_idempotent(session: Session, connected_account: object) -> None:
    from app.services import token_store

    account = token_store.require_account(session)
    buy = fill("BUY", 100, "800", order_id="ORD1")
    sell = fill("SELL", 100, "810", order_id="ORD2")
    for item in (buy, sell):
        item.account_id = account.id
        session.add(item)
    session.add(
        ChargeRateSet(
            effective_from=dt.date(2026, 1, 1),
            label="test",
            config=SIMPLE,
        )
    )
    session.flush()

    charges.compute_charges(session, {"ORD1", "ORD2"})
    first = _charge_snapshot(session)
    charges.compute_charges(session, {"ORD1", "ORD2"})
    second = _charge_snapshot(session)

    assert first == second
    assert session.query(OrderCharge).count() == 2
    assert session.query(FillCharge).count() == 2


def _charge_snapshot(session: Session) -> list[tuple]:
    return sorted(
        (row.order_id, row.brokerage, row.total) for row in session.query(OrderCharge).all()
    )
