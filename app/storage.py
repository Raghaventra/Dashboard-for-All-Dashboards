"""Image storage: Amazon S3 when configured, local filesystem otherwise.

On EC2, set S3_BUCKET in .env and boto3 authenticates automatically via the
instance IAM role (no access keys). Locally, with no S3_BUCKET, files are written
under ``uploads/`` so the upload/crop feature still works in development.

Stored objects are served back through the app's ``/media/{key}`` route, so the
S3 bucket can stay private (no public-read needed).
"""
from __future__ import annotations

import mimetypes
from typing import Optional, Tuple

from app.config import settings

try:
    import boto3
    from botocore.exceptions import BotoCoreError, ClientError
except ImportError:  # boto3 not installed (e.g. minimal local env)
    boto3 = None
    BotoCoreError = ClientError = Exception

_s3_client = None


def use_s3() -> bool:
    return bool(settings.S3_BUCKET) and boto3 is not None


def _client():
    global _s3_client
    if _s3_client is None:
        _s3_client = boto3.client("s3", region_name=settings.S3_REGION)
    return _s3_client


def _s3_key(key: str) -> str:
    prefix = settings.S3_PREFIX.strip("/")
    return f"{prefix}/{key}" if prefix else key


def save(key: str, data: bytes, content_type: str) -> None:
    """Store bytes under ``key`` (e.g. 'avatars/3.jpg')."""
    if use_s3():
        _client().put_object(
            Bucket=settings.S3_BUCKET, Key=_s3_key(key),
            Body=data, ContentType=content_type,
        )
    else:
        path = settings.UPLOADS_DIR / key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)


def load(key: str) -> Optional[Tuple[bytes, str]]:
    """Return (bytes, content_type) for ``key``, or None if missing."""
    if use_s3():
        try:
            obj = _client().get_object(Bucket=settings.S3_BUCKET, Key=_s3_key(key))
            return obj["Body"].read(), obj.get("ContentType", "application/octet-stream")
        except (BotoCoreError, ClientError):
            return None
    path = settings.UPLOADS_DIR / key
    if not path.exists() or not path.is_file():
        return None
    ctype = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
    return path.read_bytes(), ctype


def delete(key: str) -> None:
    if use_s3():
        try:
            _client().delete_object(Bucket=settings.S3_BUCKET, Key=_s3_key(key))
        except (BotoCoreError, ClientError):
            pass
    else:
        path = settings.UPLOADS_DIR / key
        if path.exists():
            path.unlink()
