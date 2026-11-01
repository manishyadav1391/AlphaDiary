"""Trade log, detail and journal endpoints (FR-TL, FR-JRN)."""

from __future__ import annotations

from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import TradeGroup, TradeJournal, TradeTag


def first_trade(client: TestClient) -> dict:
    response = client.get("/api/v1/trades", params={"limit": 1})
    assert response.status_code == 200, response.text
    return response.json()["items"][0]


# -------------------------------------------------------------------- list


def test_the_log_returns_the_imported_trades(
    authenticated_client: TestClient, imported_trades: object
) -> None:
    response = authenticated_client.get("/api/v1/trades")

    assert response.status_code == 200
    body = response.json()
    assert body["items"]
    assert body["totals"]["trades"] == len(body["items"])
    assert body["intraday_only"] is True


def test_money_crosses_the_wire_as_plain_decimal_strings(
    authenticated_client: TestClient, imported_trades: object
) -> None:
    """SRS 4.3: strings, and never pre-formatted with a rupee sign."""
    item = first_trade(authenticated_client)

    for field in ("gross_pnl", "charges_total", "net_pnl"):
        assert isinstance(item[field], str)
        assert "₹" not in item[field]
        assert "," not in item[field]
        Decimal(item[field])


def test_both_identifiers_are_returned(
    authenticated_client: TestClient, imported_trades: object
) -> None:
    """The UUID changes on re-match; the group_key is the stable one."""
    item = first_trade(authenticated_client)

    assert item["id"]
    assert item["group_key"]
    assert item["group_key"].count(":") == 3


def test_totals_cover_the_whole_filtered_set_not_the_page(
    authenticated_client: TestClient, imported_trades: object
) -> None:
    """FR-TL-03."""
    everything = authenticated_client.get("/api/v1/trades", params={"limit": 200}).json()
    one_page = authenticated_client.get("/api/v1/trades", params={"limit": 1}).json()

    assert len(one_page["items"]) == 1
    assert one_page["totals"] == everything["totals"]
    assert one_page["totals"]["trades"] > 1


def test_cursor_pagination_walks_every_row_once(
    authenticated_client: TestClient, imported_trades: object
) -> None:
    seen: list[str] = []
    cursor = None
    for _ in range(50):
        params: dict = {"limit": 2}
        if cursor:
            params["cursor"] = cursor
        body = authenticated_client.get("/api/v1/trades", params=params).json()
        seen.extend(item["group_key"] for item in body["items"])
        cursor = body["next_cursor"]
        if not cursor:
            break

    assert len(seen) == len(set(seen))
    assert len(seen) == body["totals"]["trades"]


def test_a_bad_cursor_is_rejected_cleanly(
    authenticated_client: TestClient, imported_trades: object
) -> None:
    response = authenticated_client.get("/api/v1/trades", params={"cursor": "nonsense"})

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_cursor"


@pytest.mark.parametrize("outcome", ["win", "loss", "breakeven"])
def test_outcome_filter_has_three_states(
    authenticated_client: TestClient, imported_trades: object, outcome: str
) -> None:
    """SRS 7.4 and FR-TL-02: breakeven is its own outcome."""
    body = authenticated_client.get(
        "/api/v1/trades", params={"outcome": outcome, "limit": 200}
    ).json()

    for item in body["items"]:
        assert item["outcome"] == outcome


def test_wins_and_losses_partition_the_closed_set(
    authenticated_client: TestClient, imported_trades: object
) -> None:
    def count(outcome: str) -> int:
        return authenticated_client.get(
            "/api/v1/trades", params={"outcome": outcome, "limit": 200}
        ).json()["totals"]["trades"]

    total = authenticated_client.get(
        "/api/v1/trades", params={"status": "closed", "limit": 200}
    ).json()["totals"]["trades"]

    assert count("win") + count("loss") + count("breakeven") == total


def test_symbol_search_is_case_insensitive(
    authenticated_client: TestClient, imported_trades: object
) -> None:
    body = authenticated_client.get("/api/v1/trades", params={"q": "thetalab"}).json()

    assert body["items"]
    assert all(item["tradingsymbol"] == "THETALAB" for item in body["items"])


def test_date_range_filter(authenticated_client: TestClient, imported_trades: object) -> None:
    body = authenticated_client.get(
        "/api/v1/trades",
        params={"date_from": "2026-10-30", "date_to": "2026-10-30", "limit": 200},
    ).json()

    assert body["items"]
    assert all(item["trade_date"] == "2026-10-30" for item in body["items"])


def test_sorting_by_net_pnl(authenticated_client: TestClient, imported_trades: object) -> None:
    body = authenticated_client.get(
        "/api/v1/trades", params={"sort": "net_pnl", "order": "desc", "limit": 200}
    ).json()

    nets = [Decimal(item["net_pnl"]) for item in body["items"]]
    assert nets == sorted(nets, reverse=True)


def test_needs_review_finds_untagged_trades(
    authenticated_client: TestClient, imported_trades: object
) -> None:
    """FR-JRN-08: nothing has been tagged yet, so everything needs review."""
    body = authenticated_client.get(
        "/api/v1/trades", params={"needs_review": True, "limit": 200}
    ).json()

    closed = authenticated_client.get(
        "/api/v1/trades", params={"status": "closed", "limit": 200}
    ).json()

    assert body["totals"]["trades"] == closed["totals"]["trades"]


# ------------------------------------------------------------------ detail


def test_detail_resolves_by_uuid_and_by_group_key(
    authenticated_client: TestClient, imported_trades: object
) -> None:
    item = first_trade(authenticated_client)

    by_id = authenticated_client.get(f"/api/v1/trades/{item['id']}")
    by_key = authenticated_client.get(f"/api/v1/trades/{item['group_key']}")

    assert by_id.status_code == 200
    assert by_key.status_code == 200
    assert by_id.json()["group_key"] == by_key.json()["group_key"]


def test_detail_lists_the_fills_with_their_allocations(
    authenticated_client: TestClient, imported_trades: object
) -> None:
    """FR-TL-05."""
    item = first_trade(authenticated_client)
    body = authenticated_client.get(f"/api/v1/trades/{item['group_key']}").json()

    assert body["fills"]
    for fill in body["fills"]:
        assert fill["role"] in ("entry", "exit")
        assert fill["quantity_used"] <= fill["quantity"]
        assert isinstance(fill["price"], str)


def test_the_charge_breakdown_adds_up_to_the_group_total(
    authenticated_client: TestClient, imported_trades: object
) -> None:
    item = first_trade(authenticated_client)
    body = authenticated_client.get(f"/api/v1/trades/{item['group_key']}").json()
    charges = body["charges"]

    components = sum(
        Decimal(charges[name])
        for name in ("brokerage", "stt_ctt", "exchange_txn", "sebi", "stamp", "other_levy", "gst")
    )
    assert abs(components - Decimal(charges["total"])) <= Decimal("0.01")
    assert abs(Decimal(charges["total"]) - Decimal(body["charges_total"])) <= Decimal("0.01")
    assert charges["segment_keys"] == ["eq_intraday"]


def test_an_unknown_trade_is_a_clean_404(authenticated_client: TestClient) -> None:
    response = authenticated_client.get("/api/v1/trades/not-a-trade")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


# ----------------------------------------------------------------- writing


def test_patch_saves_journal_fields_and_tags(
    authenticated_client: TestClient,
    session: Session,
    imported_trades: object,
    journal_lists: dict,
) -> None:
    item = first_trade(authenticated_client)

    response = authenticated_client.patch(
        f"/api/v1/trades/{item['group_key']}",
        json={
            "strategy_id": str(journal_lists["strategy"].id),
            "entry_reason": "Broke the opening range on volume.",
            "execution_rating": 4,
            "tag_ids": [str(journal_lists["mistake"].id)],
        },
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["journal"]["entry_reason"] == "Broke the opening range on volume."
    assert body["journal"]["execution_rating"] == 4
    assert [tag["name"] for tag in body["tags"]] == ["Exited early"]


def test_patch_leaves_unsent_fields_alone(
    authenticated_client: TestClient, imported_trades: object, journal_lists: dict
) -> None:
    """FR-JRN-05: a debounced autosave must not blank what it did not send."""
    key = first_trade(authenticated_client)["group_key"]
    authenticated_client.patch(f"/api/v1/trades/{key}", json={"lessons": "Wait for the retest."})

    authenticated_client.patch(f"/api/v1/trades/{key}", json={"execution_rating": 5})

    body = authenticated_client.get(f"/api/v1/trades/{key}").json()
    assert body["journal"]["lessons"] == "Wait for the retest."
    assert body["journal"]["execution_rating"] == 5


def test_the_journal_is_stored_against_the_group_key(
    authenticated_client: TestClient, session: Session, imported_trades: object
) -> None:
    """CLAUDE.md hard rule: keyed by group_key, not trade_group.id."""
    item = first_trade(authenticated_client)
    authenticated_client.patch(
        f"/api/v1/trades/{item['id']}", json={"lessons": "Keyed by the stable id."}
    )

    stored = session.get(TradeJournal, item["group_key"])
    assert stored is not None
    assert stored.lessons == "Keyed by the stable id."


def test_journal_survives_a_rematch(
    authenticated_client: TestClient, session: Session, imported_trades: object
) -> None:
    """Scenario S13, through the API this time."""
    from app.services import matcher

    item = first_trade(authenticated_client)
    authenticated_client.patch(
        f"/api/v1/trades/{item['group_key']}", json={"lessons": "Survives re-matching."}
    )

    group = session.execute(
        select(TradeGroup).where(TradeGroup.group_key == item["group_key"])
    ).scalar_one()
    matcher.rebuild_groups(session, {(group.account_id, group.instrument_token, group.product)})

    body = authenticated_client.get(f"/api/v1/trades/{item['group_key']}").json()
    assert body["journal"]["lessons"] == "Survives re-matching."
    # The UUID moved, which is exactly why the key is the canonical one.
    assert body["id"] != item["id"]


def test_replacing_tags_removes_the_old_ones(
    authenticated_client: TestClient,
    session: Session,
    imported_trades: object,
    journal_lists: dict,
) -> None:
    key = first_trade(authenticated_client)["group_key"]
    authenticated_client.put(
        f"/api/v1/trades/{key}/tags", json={"tag_ids": [str(journal_lists["mistake"].id)]}
    )

    response = authenticated_client.put(
        f"/api/v1/trades/{key}/tags", json={"tag_ids": [str(journal_lists["other"].id)]}
    )

    assert [tag["name"] for tag in response.json()["tags"]] == ["FOMO entry"]
    assert (
        session.execute(select(TradeTag).where(TradeTag.group_key == key)).scalars().all().__len__()
        == 1
    )


def test_an_unknown_tag_is_rejected(
    authenticated_client: TestClient, imported_trades: object
) -> None:
    import uuid

    key = first_trade(authenticated_client)["group_key"]

    response = authenticated_client.put(
        f"/api/v1/trades/{key}/tags", json={"tag_ids": [str(uuid.uuid4())]}
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "unknown_tag"


def test_an_execution_rating_outside_one_to_five_is_rejected(
    authenticated_client: TestClient, imported_trades: object
) -> None:
    key = first_trade(authenticated_client)["group_key"]

    response = authenticated_client.patch(f"/api/v1/trades/{key}", json={"execution_rating": 9})

    assert response.status_code == 422


# ----------------------------------------------------------------- derived


def test_r_multiple_and_risk_come_from_the_planned_stop(
    authenticated_client: TestClient, imported_trades: object
) -> None:
    """FR-JRN-02."""
    item = first_trade(authenticated_client)
    entry = Decimal(item["avg_entry"])

    body = authenticated_client.patch(
        f"/api/v1/trades/{item['group_key']}",
        json={
            "planned_entry": str(entry),
            "planned_sl": str(entry - Decimal("1")),
            "planned_target": str(entry + Decimal("2")),
        },
    ).json()

    risk = Decimal("1") * item["qty_max"]
    assert Decimal(body["derived"]["planned_risk_amount"]) == risk
    assert Decimal(body["derived"]["planned_rr"]) == Decimal("2")
    assert Decimal(body["derived"]["r_multiple"]) == (Decimal(body["net_pnl"]) / risk).quantize(
        Decimal("0.0001")
    )


def test_without_a_stop_loss_there_is_no_r(
    authenticated_client: TestClient, imported_trades: object
) -> None:
    item = first_trade(authenticated_client)

    body = authenticated_client.patch(
        f"/api/v1/trades/{item['group_key']}", json={"planned_entry": item["avg_entry"]}
    ).json()

    assert body["derived"]["r_multiple"] is None
    assert body["derived"]["planned_risk_amount"] is None


def test_slippage_is_positive_when_the_fill_was_worse(
    authenticated_client: TestClient, imported_trades: object
) -> None:
    """FR-TL-06."""
    body = authenticated_client.get("/api/v1/trades", params={"limit": 200}).json()
    long_trade = next(item for item in body["items"] if item["direction"] == "LONG")
    entry = Decimal(long_trade["avg_entry"])

    detail = authenticated_client.patch(
        f"/api/v1/trades/{long_trade['group_key']}",
        json={"planned_entry": str(entry - Decimal("1"))},
    ).json()

    # Paid a rupee more than planned on every unit: slippage is positive.
    assert Decimal(detail["derived"]["slippage_amount"]) == Decimal(long_trade["qty_max"])


# -------------------------------------------------------------------- auth


def _call(client: TestClient, method: str, path: str):
    """GET takes no body; the other verbs here do."""
    if method == "get":
        return client.get(path)
    return getattr(client, method)(path, json={})


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("get", "/api/v1/trades"),
        ("get", "/api/v1/trades/anything"),
        ("patch", "/api/v1/trades/anything"),
        ("put", "/api/v1/trades/anything/tags"),
    ],
)
def test_every_trade_route_needs_a_session(client: TestClient, method: str, path: str) -> None:
    response = _call(client, method, path)

    assert response.status_code == 401
