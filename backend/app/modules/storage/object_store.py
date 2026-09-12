"""
app/modules/storage/object_store.py
======================================
Real MinIO object storage client (technologies.txt §10 -- "MinIO (OSS):
audio recordings, transcripts, reports, exports"). The official `minio`
Python SDK is synchronous, so every call is offloaded to a worker thread
via `asyncio.to_thread` to keep the rest of the (async) backend non-blocking.
"""
from __future__ import annotations

import asyncio
import io
from datetime import timedelta
from functools import lru_cache

from minio import Minio
from minio.error import S3Error

from app.core.settings import settings

_BUCKET_MAP = {
    "recordings": settings.MINIO_BUCKET_RECORDINGS,
    "reports": settings.MINIO_BUCKET_REPORTS,
}


class ObjectStoreError(RuntimeError):
    """Raised when MinIO is unreachable or an operation fails."""


@lru_cache(maxsize=1)
def get_client() -> Minio:
    return Minio(
        settings.MINIO_ENDPOINT,
        access_key=settings.MINIO_ROOT_USER,
        secret_key=settings.MINIO_ROOT_PASSWORD,
        secure=settings.MINIO_SECURE,
    )




def _resolve_bucket(bucket: str) -> str:
    return _BUCKET_MAP.get(bucket, bucket)


def _ensure_bucket_sync(bucket_name: str) -> None:
    client = get_client()
    if not client.bucket_exists(bucket_name):
        client.make_bucket(bucket_name)


async def ensure_bucket(bucket: str) -> None:
    try:
        await asyncio.to_thread(_ensure_bucket_sync, _resolve_bucket(bucket))
    except S3Error as exc:
        raise ObjectStoreError(f"Could not ensure bucket '{bucket}': {exc}") from exc


def _upload_sync(bucket_name: str, object_key: str, data: bytes, content_type: str) -> None:
    client = get_client()
    if not client.bucket_exists(bucket_name):
        client.make_bucket(bucket_name)
    client.put_object(
        bucket_name,
        object_key,
        data=io.BytesIO(data),
        length=len(data),
        content_type=content_type,
    )


async def upload_bytes(*, bucket: str, object_key: str, data: bytes, content_type: str) -> str:
    """Upload raw bytes and return a stable internal reference (`bucket/object_key`)."""
    bucket_name = _resolve_bucket(bucket)
    try:
        await asyncio.to_thread(_upload_sync, bucket_name, object_key, data, content_type)
    except S3Error as exc:
        raise ObjectStoreError(f"Failed to upload '{object_key}' to '{bucket_name}': {exc}") from exc
    return f"{bucket_name}/{object_key}"


@lru_cache(maxsize=1)
def _get_presign_client() -> Minio:
    """
    A second client, pointed at MINIO_PUBLIC_ENDPOINT (the host the
    candidate's browser can actually reach) rather than MINIO_ENDPOINT (the
    internal Docker service name). SigV4 presigning includes "host" as a
    signed header, so the URL must be signed with the same host the
    downloader will send -- generating it via get_client() and swapping the
    hostname afterward produces a SignatureDoesNotMatch (verified).
    An explicit `region` is required here: minio-py's presign otherwise
    does a real HTTP region-lookup call against the client's own endpoint
    before it can sign anything, and MINIO_PUBLIC_ENDPOINT is frequently
    *not* reachable from inside this container (that's the whole reason it
    differs from MINIO_ENDPOINT). Passing the region explicitly skips that
    lookup, since presigning is otherwise a pure local computation.
    """
    return Minio(
        settings.MINIO_PUBLIC_ENDPOINT,
        access_key=settings.MINIO_ROOT_USER,
        secret_key=settings.MINIO_ROOT_PASSWORD,
        secure=settings.MINIO_SECURE,
        region=settings.MINIO_REGION,
    )


def _presign_sync(bucket_name: str, object_key: str, expires_seconds: int) -> str:
    client = _get_presign_client()
    return client.presigned_get_object(bucket_name, object_key, expires=timedelta(seconds=expires_seconds))


async def get_presigned_url(*, bucket: str, object_key: str, expires_seconds: int = 3600) -> str:
    """Generate a real, time-limited download URL for a private object."""
    bucket_name = _resolve_bucket(bucket)
    try:
        return await asyncio.to_thread(_presign_sync, bucket_name, object_key, expires_seconds)
    except S3Error as exc:
        raise ObjectStoreError(f"Failed to presign '{object_key}' in '{bucket_name}': {exc}") from exc
