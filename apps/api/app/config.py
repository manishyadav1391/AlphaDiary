"""Application configuration, read from the environment by pydantic-settings.

Secrets use `SecretStr` so they cannot leak through a repr, a traceback or a
structured log record (SRS 4.3, Logging).
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # Core
    app_env: str = "development"
    app_secret_key: SecretStr = SecretStr("change-me")
    app_encryption_key: SecretStr = SecretStr("change-me")

    # All business logic runs on the IST trading calendar (SRS 3.3).
    timezone: str = "Asia/Kolkata"

    # Database
    database_url: str = "postgresql+psycopg://tj:tj@db:5432/tj"

    # Public URLs
    public_base_url: str = "http://localhost:3000"

    # Broker. Credentials are also storable per account, encrypted in the
    # database; these are the defaults used when seeding an account.
    kite_api_key: str = ""
    kite_api_secret: SecretStr = SecretStr("")

    # Seed inputs (charge rate sets, holidays). Loaded by `make seed`.
    seed_dir: str = "/srv/seed"

    # Session cookie (FR-AUTH-03)
    session_cookie_name: str = "tj_session"
    session_ttl_days: int = 7

    # Login rate limiting (FR-AUTH-04)
    login_max_attempts: int = 5
    login_window_minutes: int = 15
    login_lockout_minutes: int = 15

    # Kite OAuth (FR-KITE-02)
    oauth_state_ttl_minutes: int = 10
    oauth_state_cookie_name: str = "tj_kite_state"

    # Email. Resend over HTTPS rather than SMTP: no SMTP credentials to hold,
    # and httpx is already a dependency (SRS 4.1 amended).
    resend_api_key: SecretStr = SecretStr("")
    resend_from: str = "onboarding@resend.dev"
    reminder_email_to: str = ""

    # Worker (FR-REM, FR-SYNC-02, NFR-07)
    worker_tick_seconds: int = 60
    scheduled_sync_time_ist: str = "15:45"
    reminder_grace_minutes: int = 20
    quiet_hours_start_ist: str = "22:00"
    quiet_hours_end_ist: str = "07:00"
    heartbeat_url: str = ""
    heartbeat_every_seconds: int = 300

    # Object storage for screenshots (FR-JRN-07)
    s3_endpoint: str = ""
    s3_region: str = "ap-south-1"
    s3_bucket: str = ""
    s3_access_key: SecretStr = SecretStr("")
    s3_secret_key: SecretStr = SecretStr("")
    screenshot_url_ttl_seconds: int = 300
    screenshot_max_bytes: int = 5 * 1024 * 1024

    # Kite call pacing and retries (FR-SYNC-07)
    kite_min_call_interval_seconds: float = 1.0
    kite_max_retries: int = 3
    kite_status_cache_seconds: int = 60

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def cookie_secure(self) -> bool:
        """Secure cookies need HTTPS. Setting the flag on plain http://localhost
        makes the browser drop the cookie, so it follows the public URL."""
        return self.public_base_url.startswith("https://")

    @property
    def email_configured(self) -> bool:
        return bool(self.resend_api_key.get_secret_value() and self.reminder_email_to)

    @property
    def storage_configured(self) -> bool:
        return bool(
            self.s3_bucket
            and self.s3_access_key.get_secret_value()
            and self.s3_secret_key.get_secret_value()
        )

    @property
    def connect_url(self) -> str:
        """Where a reminder sends you: app login, then the Zerodha redirect."""
        return f"{self.public_base_url.rstrip('/')}/connect"

    @property
    def kite_redirect_url(self) -> str:
        """Register this exact URL in the Kite Developer Console (FR-KITE-09)."""
        return f"{self.public_base_url.rstrip('/')}/api/v1/kite/callback"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
