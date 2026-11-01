"""Request and response models for FR-SYNC."""

from __future__ import annotations

import datetime as dt
import uuid
from typing import Literal

from pydantic import BaseModel

SyncTrigger = Literal["manual", "scheduled", "login_catchup", "csv"]
SyncStatus = Literal["running", "success", "partial", "failed", "skipped_no_token"]


class SyncLogOut(BaseModel):
    id: uuid.UUID
    trigger: SyncTrigger
    status: SyncStatus
    started_at: dt.datetime
    finished_at: dt.datetime | None = None
    fills_new: int = 0
    fills_dup: int = 0
    fills_rejected: int = 0
    orders_upserted: int = 0
    error: str | None = None


class SyncStatusOut(BaseModel):
    running: bool
    synced_today: bool
    last: SyncLogOut | None = None
