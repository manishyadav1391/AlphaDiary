"""Trade sync (FR-SYNC). Thin: logic lives in services/sync_service.py."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db import get_session
from app.deps import current_user
from app.errors import ApiError
from app.models import AppUser, SyncLog
from app.schemas.sync import SyncLogOut, SyncStatusOut
from app.services import sync_service, token_store

router = APIRouter(prefix="/sync", tags=["sync"])


@router.post("/run", response_model=SyncLogOut)
def run(
    _: AppUser = Depends(current_user),
    session: Session = Depends(get_session),
) -> SyncLogOut:
    """Start a sync of the current day (FR-SYNC-01)."""
    try:
        result = sync_service.run_sync(session, trigger="manual")
    except sync_service.AlreadyRunning as exc:
        raise ApiError("already_running", "A sync is already running.", status_code=409) from exc
    except token_store.NotConfigured as exc:
        raise ApiError(
            "not_configured",
            "Connect Zerodha before syncing.",
            status_code=409,
        ) from exc

    log = session.get(SyncLog, result.sync_log_id)
    return SyncLogOut.model_validate(log, from_attributes=True)


@router.get("/logs", response_model=list[SyncLogOut])
def logs(
    limit: int = Query(default=20, ge=1, le=200),
    _: AppUser = Depends(current_user),
    session: Session = Depends(get_session),
) -> list[SyncLogOut]:
    """Sync history, newest first (FR-SYNC-10)."""
    return [
        SyncLogOut.model_validate(row, from_attributes=True)
        for row in sync_service.recent_logs(session, limit)
    ]


@router.get("/status", response_model=SyncStatusOut)
def status(
    _: AppUser = Depends(current_user),
    session: Session = Depends(get_session),
) -> SyncStatusOut:
    last = sync_service.last_log(session)
    return SyncStatusOut(
        running=sync_service.is_running(session),
        synced_today=sync_service.synced_today(session),
        last=SyncLogOut.model_validate(last, from_attributes=True) if last else None,
    )
