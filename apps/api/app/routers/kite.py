"""Zerodha connection (FR-KITE). Thin: logic lives in services/."""

from __future__ import annotations

import datetime as dt
import logging

from fastapi import APIRouter, BackgroundTasks, Depends, Request, Response
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import SessionLocal, get_session
from app.deps import current_user
from app.errors import ApiError
from app.models import AppUser, BrokerAccount
from app.schemas.kite import KiteStatusOut, LoginUrlOut
from app.security import EncryptionKeyError
from app.services import oauth_state, sync_service, token_store
from app.services.kite_client import TokenExpired
from app.timezone import now_utc

router = APIRouter(prefix="/kite", tags=["kite"])
logger = logging.getLogger("tj.kite")

# Live status is cached briefly so a page that polls does not burn Kite calls
# (FR-KITE-05).
_status_cache: dict[str, tuple[dt.datetime, KiteStatusOut]] = {}


def _catchup_sync() -> None:
    """Run the post-connect sync after the redirect has been sent (FR-KITE-08)."""
    session = SessionLocal()
    try:
        sync_service.run_catchup_sync(session)
        session.commit()
    except Exception:
        session.rollback()
        logger.error("Catch-up sync failed", extra={"event": "catchup_sync_failed"})
    finally:
        session.close()


@router.get("/login-url", response_model=LoginUrlOut)
def login_url(
    response: Response,
    _: AppUser = Depends(current_user),
    session: Session = Depends(get_session),
) -> LoginUrlOut:
    """Return the Kite login URL. The browser navigates there (FR-KITE-02)."""
    settings = get_settings()
    try:
        account = token_store.require_account(session)
        client = token_store.build_client(session, account)
    except token_store.NotConfigured as exc:
        raise ApiError(
            "not_configured",
            "Add your Kite API key and secret before connecting.",
            status_code=409,
        ) from exc

    state = oauth_state.issue(session, account)

    # The state also rides in a cookie, because the docs do not pin down how
    # `redirect_params` is returned to the callback (VERIFY V5).
    response.set_cookie(
        key=settings.oauth_state_cookie_name,
        value=state.state,
        max_age=settings.oauth_state_ttl_minutes * 60,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/",
    )
    return LoginUrlOut(
        login_url=client.login_url(state.state),
        redirect_url=settings.kite_redirect_url,
    )


@router.get("/callback", include_in_schema=False)
def callback(
    request: Request,
    background: BackgroundTasks,
    session: Session = Depends(get_session),
    request_token: str | None = None,
    status: str | None = None,
    state: str | None = None,
) -> RedirectResponse:
    """Receive the broker redirect, store the token, bounce home (FR-KITE-03).

    Public by necessity: the browser arrives here straight from Zerodha. The
    one-time state is what makes that safe.
    """
    settings = get_settings()
    home = settings.public_base_url.rstrip("/")

    def fail(code: str) -> RedirectResponse:
        logger.warning("Kite callback rejected", extra={"event": "kite_callback_rejected"})
        redirect = RedirectResponse(url=f"{home}/?kite_error={code}", status_code=303)
        redirect.delete_cookie(settings.oauth_state_cookie_name, path="/")
        return redirect

    # Kite documents only `request_token` on the redirect, so `status` is
    # checked when present rather than required.
    if status is not None and status != "success":
        return fail("login_failed")
    if not request_token:
        return fail("missing_request_token")

    candidate = state or request.cookies.get(settings.oauth_state_cookie_name)
    try:
        issued = oauth_state.consume(session, candidate or "")
    except oauth_state.InvalidState:
        return fail("invalid_state")

    account = session.get(BrokerAccount, issued.account_id)
    if account is None:
        return fail("not_configured")

    try:
        client = token_store.build_client(session, account)
        kite_session = client.exchange_request_token(request_token)
        token_store.store_token(session, account, kite_session)
    except (token_store.NotConfigured, EncryptionKeyError):
        return fail("not_configured")
    except TokenExpired:
        return fail("token_rejected")
    except Exception:
        logger.error("Token exchange failed", extra={"event": "kite_exchange_failed"})
        return fail("exchange_failed")

    _status_cache.clear()
    background.add_task(_catchup_sync)

    redirect = RedirectResponse(url=f"{home}/?connected=1", status_code=303)
    redirect.delete_cookie(settings.oauth_state_cookie_name, path="/")
    return redirect


@router.get("/status", response_model=KiteStatusOut)
def kite_status(
    _: AppUser = Depends(current_user),
    session: Session = Depends(get_session),
) -> KiteStatusOut:
    """Live connection state, cached for 60 seconds (FR-KITE-05)."""
    settings = get_settings()
    account = token_store.get_account(session)
    if account is None or not account.api_key_enc:
        return KiteStatusOut(status="not_configured")

    cache_key = str(account.id)
    cached = _status_cache.get(cache_key)
    if cached and cached[0] > now_utc():
        return cached[1]

    base = KiteStatusOut(
        status="expired",
        kite_user_id=account.kite_user_id,
        api_key_masked=token_store.masked_api_key(account),
        token_issued_at=account.token_issued_at,
        token_valid_until=account.token_valid_until,
    )

    if not token_store.token_may_be_valid(account):
        result = base
    else:
        try:
            token_store.build_client(session, account).profile()
            result = base.model_copy(update={"status": "connected"})
        except TokenExpired:
            token_store.mark_token_expired(session, account)
            result = base.model_copy(update={"token_valid_until": account.token_valid_until})
        except Exception:
            logger.error("Kite status check failed", extra={"event": "kite_status_failed"})
            result = base.model_copy(
                update={"status": "error", "message": "Could not reach Zerodha."}
            )

    _status_cache[cache_key] = (
        now_utc() + dt.timedelta(seconds=settings.kite_status_cache_seconds),
        result,
    )
    return result


@router.post("/disconnect", status_code=204)
def disconnect(
    _: AppUser = Depends(current_user),
    session: Session = Depends(get_session),
) -> Response:
    """Delete the stored token. Trade data is untouched (FR-KITE-10)."""
    account = token_store.get_account(session)
    if account is not None:
        token_store.clear_token(session, account)
    _status_cache.clear()
    return Response(status_code=204)
