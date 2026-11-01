"""Object storage for screenshots (FR-JRN-07).

The browser uploads straight to S3 with a presigned PUT and reads back
through a presigned GET that expires in five minutes. The image bytes never
pass through the API, and the bucket stays private: no public ACL, no
permanent URL.

Credentials come from the environment and are never returned to the browser.
The endpoint is configurable, so R2 or B2 work as well as AWS.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

import boto3
from botocore.client import Config
from botocore.exceptions import BotoCoreError, ClientError

from app.config import get_settings

logger = logging.getLogger("tj.storage")

ALLOWED_MIME = {
    "image/webp": "webp",
    "image/png": "png",
    "image/jpeg": "jpg",
}


class StorageNotConfigured(Exception):
    """No bucket or no credentials."""


class StorageError(Exception):
    """The provider refused the request."""


@dataclass(frozen=True)
class PresignedUpload:
    object_key: str
    url: str
    expires_in: int
    # Echoed back so the browser sends exactly what the signature covers.
    headers: dict[str, str]


@lru_cache(maxsize=1)
def _client() -> Any:
    settings = get_settings()
    if not settings.storage_configured:
        raise StorageNotConfigured("S3 bucket or credentials are not set")

    return boto3.client(
        "s3",
        endpoint_url=settings.s3_endpoint or None,
        region_name=settings.s3_region,
        aws_access_key_id=settings.s3_access_key.get_secret_value(),
        aws_secret_access_key=settings.s3_secret_key.get_secret_value(),
        # SigV4 is required by R2 and by newer AWS regions.
        config=Config(signature_version="s3v4"),
    )


def reset_client() -> None:
    """Drop the cached client. Used by tests and after a settings change."""
    _client.cache_clear()


def build_object_key(trade_group_id: str, mime: str) -> str:
    """`screenshots/{trade_group_id}/{uuid}.{ext}` (FR-JRN-07)."""
    extension = ALLOWED_MIME.get(mime)
    if extension is None:
        raise StorageError(f"unsupported image type: {mime}")
    return f"screenshots/{trade_group_id}/{uuid.uuid4().hex}.{extension}"


def presign_upload(
    trade_group_id: str, mime: str, *, expires_in: int | None = None
) -> PresignedUpload:
    """A one-shot PUT URL for the browser."""
    settings = get_settings()
    ttl = expires_in or settings.screenshot_url_ttl_seconds
    object_key = build_object_key(trade_group_id, mime)

    try:
        url = _client().generate_presigned_url(
            "put_object",
            Params={
                "Bucket": settings.s3_bucket,
                "Key": object_key,
                "ContentType": mime,
            },
            ExpiresIn=ttl,
        )
    except (BotoCoreError, ClientError) as exc:
        raise StorageError(type(exc).__name__) from exc

    return PresignedUpload(
        object_key=object_key,
        url=url,
        expires_in=ttl,
        headers={"Content-Type": mime},
    )


def presign_download(object_key: str, *, expires_in: int | None = None) -> str:
    """A short-lived read URL (FR-JRN-07: five minutes)."""
    settings = get_settings()
    ttl = expires_in or settings.screenshot_url_ttl_seconds
    try:
        return str(
            _client().generate_presigned_url(
                "get_object",
                Params={"Bucket": settings.s3_bucket, "Key": object_key},
                ExpiresIn=ttl,
            )
        )
    except (BotoCoreError, ClientError) as exc:
        raise StorageError(type(exc).__name__) from exc


def delete(object_key: str) -> None:
    settings = get_settings()
    try:
        _client().delete_object(Bucket=settings.s3_bucket, Key=object_key)
    except (BotoCoreError, ClientError) as exc:
        raise StorageError(type(exc).__name__) from exc


def health() -> bool:
    """Whether the bucket answers. Used by /health and the Data settings tab."""
    settings = get_settings()
    try:
        _client().head_bucket(Bucket=settings.s3_bucket)
    except (BotoCoreError, ClientError, StorageNotConfigured):
        return False
    return True
