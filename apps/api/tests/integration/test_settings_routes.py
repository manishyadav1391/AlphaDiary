"""Settings endpoints (FR-SET, FR-KITE-01/09, FR-REM-02/06/14).

The secrecy assertions here are the point: SRS 5.2 says the API secret is
never returned and the key only ever masked, and these are the routes that
would leak them.
"""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import BrokerAccount, NotificationChannel, NotificationLog
from app.security import decrypt, encrypt
from app.services import notifier, reminders

PREFIX = "/api/v1/settings"


# ------------------------------------------------------------------ kite


def test_kite_settings_show_the_callback_url_before_anything_is_stored(
    authenticated_client: TestClient,
) -> None:
    """FR-KITE-09: the URL to register is available before setup."""
    body = authenticated_client.get(f"{PREFIX}/kite").json()

    assert body["redirect_url"].endswith("/api/v1/kite/callback")
    assert body["api_key_masked"] is None
    assert body["has_secret"] is False


def test_storing_credentials_encrypts_them_and_returns_only_a_mask(
    authenticated_client: TestClient, session: Session
) -> None:
    """FR-KITE-01: stored encrypted, shown masked, secret never returned."""
    response = authenticated_client.put(
        f"{PREFIX}/kite",
        json={"api_key": "abcd1234efgh", "api_secret": "super-secret-value"},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["api_key_masked"].endswith("efgh")
    assert "abcd1234" not in body["api_key_masked"]
    assert body["has_secret"] is True
    # The secret must not appear anywhere in the payload.
    assert "super-secret-value" not in response.text

    account = session.execute(BrokerAccount.__table__.select()).mappings().one()
    assert decrypt(account["api_key_enc"]) == "abcd1234efgh"
    assert decrypt(account["api_secret_enc"]) == "super-secret-value"


def test_blank_credentials_are_rejected(authenticated_client: TestClient) -> None:
    response = authenticated_client.put(
        f"{PREFIX}/kite", json={"api_key": "   ", "api_secret": "   "}
    )
    assert response.status_code == 422


# ------------------------------------------------------------- reminders


def test_reminder_settings_default_to_the_seeded_schedule(
    authenticated_client: TestClient, session: Session
) -> None:
    reminders.save_slots(session, reminders.DEFAULT_SLOTS)

    body = authenticated_client.get(f"{PREFIX}/reminders").json()

    assert [slot["name"] for slot in body["slots"]] == [
        slot["name"] for slot in reminders.DEFAULT_SLOTS
    ]
    assert body["sync_time_ist"] == "15:45"
    assert body["skipped_today"] is False


def test_the_schedule_can_be_replaced(authenticated_client: TestClient) -> None:
    """FR-REM-02: the slots are editable."""
    response = authenticated_client.put(
        f"{PREFIX}/reminders",
        json={
            "slots": [
                {"name": "morning", "time": "08:30", "kind": "reminder", "enabled": True},
                {"name": "missed_sync", "time": "15:55", "kind": "missed_sync", "enabled": True},
            ]
        },
    )

    assert response.status_code == 200, response.text
    slots = response.json()["slots"]
    assert [(s["name"], s["time"]) for s in slots] == [
        ("morning", "08:30"),
        ("missed_sync", "15:55"),
    ]


@pytest.mark.parametrize(
    "slots",
    [
        [{"name": "a", "time": "25:00", "kind": "reminder", "enabled": True}],
        [{"name": "a", "time": "nonsense", "kind": "reminder", "enabled": True}],
        [{"name": "a", "time": "09:00", "kind": "invented", "enabled": True}],
        [
            {"name": "same", "time": "09:00", "kind": "reminder", "enabled": True},
            {"name": "same", "time": "10:00", "kind": "reminder", "enabled": True},
        ],
    ],
)
def test_a_broken_schedule_is_refused(
    authenticated_client: TestClient, slots: list[dict[str, object]]
) -> None:
    """A bad slot must not be written: the worker reads this every 60 seconds."""
    response = authenticated_client.put(f"{PREFIX}/reminders", json={"slots": slots})
    assert response.status_code == 422


def test_skip_today_silences_the_rest_of_the_day(
    authenticated_client: TestClient,
) -> None:
    """FR-REM-05: the button the dashboard banner needs."""
    assert authenticated_client.post(f"{PREFIX}/reminders/skip-today").status_code == 204
    assert authenticated_client.get(f"{PREFIX}/reminders").json()["skipped_today"] is True


# -------------------------------------------------------------- channels


def test_an_unconfigured_channel_reads_as_off(authenticated_client: TestClient) -> None:
    body = authenticated_client.get(f"{PREFIX}/channels/email").json()
    assert body == {
        "channel": "email",
        "enabled": False,
        "destination": None,
        "configured": False,
        "updated_at": None,
    }


def test_setting_the_destination_encrypts_it(
    authenticated_client: TestClient, session: Session
) -> None:
    """FR-REM-06: the address is stored encrypted, not in the clear."""
    response = authenticated_client.put(
        f"{PREFIX}/channels/email",
        json={"enabled": True, "destination": "Owner@Example.test"},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["enabled"] is True
    # Normalised to lower case, as auth does with the login email.
    assert body["destination"] == "owner@example.test"
    assert body["configured"] is True

    row = session.get(NotificationChannel, "email")
    assert row is not None
    assert json.loads(decrypt(row.config_enc))["to"] == "owner@example.test"


def test_enabling_without_an_address_is_refused(
    authenticated_client: TestClient,
) -> None:
    """Enabling with nowhere to send is the silent failure this screen exists to stop."""
    response = authenticated_client.put(
        f"{PREFIX}/channels/email", json={"enabled": True, "destination": None}
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "destination_required"


def test_a_malformed_address_is_refused(authenticated_client: TestClient) -> None:
    response = authenticated_client.put(
        f"{PREFIX}/channels/email", json={"enabled": True, "destination": "not-an-address"}
    )
    assert response.status_code == 422


def test_unbuilt_channels_say_so(authenticated_client: TestClient) -> None:
    """FR-REM-12/13 are not built; the API must not pretend otherwise."""
    response = authenticated_client.get(f"{PREFIX}/channels/telegram")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "channel_not_supported"


def test_the_test_button_reports_the_exact_failure(
    authenticated_client: TestClient, session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """FR-REM-06: 'Send test' shows the real error, not a generic one."""
    session.add(
        NotificationChannel(
            channel="email",
            enabled=True,
            config_enc=encrypt(json.dumps({"to": "owner@example.test"})),
        )
    )
    session.flush()

    def refuse(self: object, message: object) -> None:
        raise notifier.SendFailed("Resend said no: domain not verified")

    monkeypatch.setattr(notifier.ResendEmail, "send", refuse)

    body = authenticated_client.post(f"{PREFIX}/channels/email/test").json()

    assert body["sent"] is False
    assert "domain not verified" in body["error"]
    assert body["destination"] == "owner@example.test"


def test_the_test_button_reports_success(
    authenticated_client: TestClient, session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    session.add(
        NotificationChannel(
            channel="email",
            enabled=True,
            config_enc=encrypt(json.dumps({"to": "owner@example.test"})),
        )
    )
    session.flush()
    monkeypatch.setattr(notifier.ResendEmail, "send", lambda self, message: None)

    body = authenticated_client.post(f"{PREFIX}/channels/email/test").json()

    assert body["sent"] is True
    assert body["error"] is None


# ------------------------------------------------------- notification log


def test_the_notification_log_reads_newest_first(
    authenticated_client: TestClient, session: Session
) -> None:
    """FR-REM-14: what was sent or skipped, and why."""
    for index, status in enumerate(["sent", "skipped_token_valid", "failed"]):
        session.add(
            NotificationLog(
                slot_key=f"2026-11-03:slot{index}",
                channel="email",
                kind="reminder",
                status=status,
                attempts=1,
                error="provider refused" if status == "failed" else None,
            )
        )
    session.flush()

    body = authenticated_client.get(f"{PREFIX}/notifications/log").json()

    assert [row["status"] for row in body] == ["failed", "skipped_token_valid", "sent"]
    assert body[0]["error"] == "provider refused"


def test_settings_require_a_session(client: TestClient) -> None:
    """FR-AUTH-05: only /kite/callback is public."""
    for path in ("/kite", "/reminders", "/channels/email", "/notifications/log"):
        assert client.get(f"{PREFIX}{path}").status_code == 401
