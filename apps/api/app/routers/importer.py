"""Console tradebook import (FR-IMP). Thin: logic lives in services/."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.orm import Session

from app.db import get_session
from app.deps import current_user
from app.errors import ApiError
from app.models import AppUser
from app.schemas.importer import ImportReportOut
from app.services import importer, token_store

router = APIRouter(prefix="/import", tags=["import"])
logger = logging.getLogger("tj.importer")

ALLOWED_PRODUCTS = {"MIS", "CNC", "NRML"}


async def _read(upload: UploadFile) -> str:
    payload = await upload.read()
    if len(payload) > importer.MAX_BYTES:
        raise ApiError(
            "file_too_large",
            "That file is over 20 MB. Export a shorter date range.",
            status_code=413,
        )
    for encoding in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            return payload.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ApiError("unreadable_file", "That file is not readable text.", status_code=400)


@router.post("/tradebook/preview", response_model=ImportReportOut)
async def preview_tradebook(
    file: UploadFile = File(...),
    _: AppUser = Depends(current_user),
) -> ImportReportOut:
    """Show what would be imported, without saving anything (FR-IMP-01)."""
    try:
        report = importer.preview(await _read(file))
    except importer.InvalidTradebook as exc:
        raise ApiError("invalid_tradebook", str(exc), status_code=422) from exc
    return ImportReportOut.model_validate(report, from_attributes=True)


@router.post("/tradebook", response_model=ImportReportOut)
async def import_tradebook(
    file: UploadFile = File(...),
    product: str | None = Form(default=None),
    _: AppUser = Depends(current_user),
    session: Session = Depends(get_session),
) -> ImportReportOut:
    """Import a Console tradebook and re-run matching for what it touched."""
    if product is not None and product.upper() not in ALLOWED_PRODUCTS:
        raise ApiError(
            "invalid_product",
            f"product must be one of {', '.join(sorted(ALLOWED_PRODUCTS))}.",
            status_code=422,
        )

    try:
        account = token_store.require_account(session)
    except token_store.NotConfigured as exc:
        raise ApiError(
            "not_configured", "Add your broker account before importing.", status_code=409
        ) from exc

    try:
        report = importer.import_tradebook(
            session,
            account.id,
            await _read(file),
            filename=file.filename,
            force_product=product.upper() if product else None,
        )
    except importer.InvalidTradebook as exc:
        raise ApiError("invalid_tradebook", str(exc), status_code=422) from exc

    logger.info(
        "Tradebook imported",
        extra={"event": "tradebook_imported", "count": report.rows_new},
    )
    return ImportReportOut.model_validate(report, from_attributes=True)
