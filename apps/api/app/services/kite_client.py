"""The only module that talks to Zerodha.

Everything Kite-specific is isolated here so that a change to the API or to the
plan terms is one file to fix, and so the rest of the app can be tested against
a fake (SRS 14, risk register).

Call discipline (FR-SYNC-07): calls are spaced at least one second apart, a
network failure is retried three times with 2, 4 and 8 second waits, and an
HTTP 429 waits one second. A `TokenException` is never retried: it means the
daily token is gone, so it marks the token expired and propagates (FR-KITE-06).

Nothing here logs a request payload, a response body, the API secret or the
access token (SRS 4.3, Logging).
"""

from __future__ import annotations

import datetime as dt
import logging
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol, TypeVar
from urllib.parse import quote, urlencode

from kiteconnect import KiteConnect
from kiteconnect import exceptions as kite_exceptions

from app.config import get_settings
from app.timezone import to_utc

logger = logging.getLogger("tj.kite")

T = TypeVar("T")

# Retry waits in seconds for a network-level failure (FR-SYNC-07).
_RETRY_WAITS = (2.0, 4.0, 8.0)
_RATE_LIMIT_WAIT = 1.0

# Spacing is global to the process: Zerodha counts calls per API key, not per
# client object, so a module-level gate is what actually protects the limit.
_pace_lock = threading.Lock()
_last_call_at: float = 0.0


class TokenExpired(Exception):
    """The Kite access token is no longer valid (FR-KITE-06)."""


@dataclass(frozen=True)
class KiteSession:
    """What a successful request-token exchange gives us.

    Deliberately narrow: the full session response also carries `public_token`,
    `enctoken` and the user's personal details, none of which we store.
    """

    access_token: str
    kite_user_id: str
    login_time: dt.datetime | None


class KiteGateway(Protocol):
    """What the sync service needs. Tests supply a fake implementing this."""

    def profile(self) -> dict[str, Any]: ...

    def orders(self) -> list[dict[str, Any]]: ...

    def trades(self) -> list[dict[str, Any]]: ...

    def positions(self) -> dict[str, Any]: ...

    def holdings(self) -> list[dict[str, Any]]: ...


def _throttle(min_interval: float) -> None:
    global _last_call_at
    with _pace_lock:
        wait = min_interval - (time.monotonic() - _last_call_at)
        if wait > 0:
            time.sleep(wait)
        _last_call_at = time.monotonic()


def _status_code(exc: BaseException) -> int | None:
    code = getattr(exc, "code", None)
    return code if isinstance(code, int) else None


def _is_retryable(exc: BaseException) -> bool:
    # A token problem or a bad request will fail again identically.
    if isinstance(
        exc,
        kite_exceptions.TokenException
        | kite_exceptions.InputException
        | kite_exceptions.PermissionException,
    ):
        return False
    if isinstance(exc, kite_exceptions.NetworkException | kite_exceptions.DataException):
        return True
    # requests' exceptions subclass OSError, so connection resets and timeouts
    # are caught without importing requests, which is not a direct dependency.
    if isinstance(exc, OSError):
        return True
    code = _status_code(exc)
    return code is not None and (code == 429 or code >= 500)


def _wait_for(attempt: int, exc: BaseException) -> float:
    if _status_code(exc) == 429:
        return _RATE_LIMIT_WAIT
    return _RETRY_WAITS[min(attempt, len(_RETRY_WAITS) - 1)]


class KiteClient:
    """A paced, retrying wrapper around the official `kiteconnect` SDK."""

    def __init__(
        self,
        api_key: str,
        api_secret: str,
        access_token: str | None = None,
        *,
        on_token_expired: Callable[[], None] | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._api_secret = api_secret
        self._on_token_expired = on_token_expired
        self._sleep = sleep
        self._settings = get_settings()
        self._kite = KiteConnect(api_key=api_key)
        if access_token:
            self._kite.set_access_token(access_token)
        # The SDK calls this hook when Zerodha answers 403/TokenException.
        self._kite.set_session_expiry_hook(self._handle_token_expiry)

    # ---------------------------------------------------------------- login

    def login_url(self, state: str) -> str:
        """The Kite login URL carrying our one-time CSRF state (FR-KITE-02).

        The state rides in `redirect_params`, which Kite echoes to the redirect
        URL. The docs do not pin down how it comes back (VERIFY V5), so the
        callback also accepts the state from a cookie.
        """
        base = self._kite.login_url()
        params = quote(urlencode({"state": state}), safe="")
        return f"{base}&redirect_params={params}"

    def exchange_request_token(self, request_token: str) -> KiteSession:
        """Swap the short-lived request token for the day's access token.

        The SDK computes the SHA-256 checksum of api_key + request_token +
        api_secret and sets the access token on itself on success.
        """
        data = self._call(
            "generate_session",
            lambda: self._kite.generate_session(request_token, api_secret=self._api_secret),
        )
        # The SDK parses login_time, but it arrives as IST wall clock with no
        # offset, so it still has to be localised before it is stored.
        raw_login_time = data.get("login_time")
        login_time = to_utc(raw_login_time) if isinstance(raw_login_time, dt.datetime) else None
        return KiteSession(
            access_token=str(data["access_token"]),
            kite_user_id=str(data.get("user_id") or ""),
            login_time=login_time,
        )

    # ------------------------------------------------------------- read API

    def profile(self) -> dict[str, Any]:
        """The liveness check for the token. Returns no tokens (FR-KITE-05)."""
        return self._call("profile", self._kite.profile)

    def orders(self) -> list[dict[str, Any]]:
        return self._call("orders", self._kite.orders)

    def trades(self) -> list[dict[str, Any]]:
        return self._call("trades", self._kite.trades)

    def positions(self) -> dict[str, Any]:
        return self._call("positions", self._kite.positions)

    def holdings(self) -> list[dict[str, Any]]:
        return self._call("holdings", self._kite.holdings)

    # -------------------------------------------------------------- plumbing

    def _handle_token_expiry(self) -> None:
        if self._on_token_expired is not None:
            self._on_token_expired()

    def _call(self, name: str, fn: Callable[[], T]) -> T:
        attempts = self._settings.kite_max_retries
        for attempt in range(attempts + 1):
            _throttle(self._settings.kite_min_call_interval_seconds)
            try:
                return fn()
            except kite_exceptions.TokenException as exc:
                self._handle_token_expiry()
                logger.warning("Kite token expired", extra={"event": "kite_token_expired"})
                raise TokenExpired(name) from exc
            except Exception as exc:
                if attempt >= attempts or not _is_retryable(exc):
                    # The exception type and the call name are safe to log; the
                    # message can quote the request, so it is left out.
                    logger.error(
                        "Kite call failed",
                        extra={"event": "kite_call_failed", "count": attempt + 1},
                    )
                    raise
                wait = _wait_for(attempt, exc)
                logger.warning(
                    "Kite call retrying",
                    extra={"event": "kite_call_retry", "count": attempt + 1},
                )
                self._sleep(wait)
        raise AssertionError("unreachable")
