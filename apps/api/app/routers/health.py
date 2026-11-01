"""Liveness and readiness for Compose, Caddy and the external heartbeat."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db import get_session

router = APIRouter(tags=["health"])


@router.get("/health")
def health(session: Session = Depends(get_session)) -> dict[str, str]:
    """Returns ok only when the database answers, so the container is marked
    healthy only once migrations can actually run against it."""
    session.execute(text("select 1"))
    return {"status": "ok", "database": "ok"}
