"""Request and response models for FR-IMP."""

from __future__ import annotations

import datetime as dt
import uuid
from typing import Any

from pydantic import BaseModel


class RejectionOut(BaseModel):
    row: int
    reason: str


class ImportReportOut(BaseModel):
    batch_id: uuid.UUID | None = None
    rows_read: int
    rows_new: int
    rows_dup: int
    rows_rejected: int
    date_from: dt.date | None = None
    date_to: dt.date | None = None
    columns: list[str] = []
    symbols: list[str] = []
    # How the missing product column was resolved, so the split is visible
    # rather than silently assumed (FR-IMP-06).
    products: dict[str, int] = {}
    unresolved_symbols: list[str] = []
    rows_without_timestamp: int = 0
    reassigned_trade_ids: int = 0
    rejections: list[RejectionOut] = []
    preview: list[dict[str, Any]] = []
