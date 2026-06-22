"""Supabase Storage integration for raw uploaded files.

Falls back to local-disk storage when Supabase is not configured, so the
backend remains runnable in pure-local dev mode.
"""
from __future__ import annotations

import asyncio
import os
from pathlib import Path

from app.core.config import settings
from app.core.exceptions import AppError
from app.core.logging import get_logger

logger = get_logger(__name__)

_LOCAL_STORAGE_DIR = Path(os.getenv("LOCAL_STORAGE_DIR", "./_local_storage")).resolve()


class StorageService:
    """Stores and retrieves raw document bytes.

    Uses Supabase Storage when configured; otherwise writes to local disk.
    The public interface is identical regardless of backend.
    """

    def __init__(self) -> None:
        self._client = None
        self._use_supabase = settings.has_supabase
        self._bucket_ready = False
        if self._use_supabase:
            from supabase import create_client

            self._client = create_client(
                settings.supabase_url, settings.supabase_service_key
            )
            logger.info("StorageService using Supabase bucket '%s'", settings.supabase_bucket)
        else:
            _LOCAL_STORAGE_DIR.mkdir(parents=True, exist_ok=True)
            logger.warning(
                "Supabase not configured; StorageService using local disk at %s",
                _LOCAL_STORAGE_DIR,
            )

    async def upload(self, path: str, data: bytes, content_type: str) -> str:
        """Store bytes at the given path. Returns the stored path/key."""
        return await asyncio.to_thread(self._upload_sync, path, data, content_type)

    def _ensure_bucket(self) -> None:
        """Create the storage bucket on first use if it doesn't already exist."""
        if self._bucket_ready or not self._use_supabase:
            return
        try:
            self._client.storage.create_bucket(settings.supabase_bucket)
            logger.info("Created Supabase bucket '%s'", settings.supabase_bucket)
        except Exception as exc:  # noqa: BLE001
            # Most commonly: bucket already exists — that's fine.
            logger.debug("create_bucket skipped for '%s': %s", settings.supabase_bucket, exc)
        self._bucket_ready = True

    def _upload_sync(self, path: str, data: bytes, content_type: str) -> str:
        if self._use_supabase:
            self._ensure_bucket()
            try:
                self._client.storage.from_(settings.supabase_bucket).upload(
                    path,
                    data,
                    {"content-type": content_type, "upsert": "true"},
                )
            except Exception as exc:  # noqa: BLE001
                raise AppError(f"Storage upload failed: {exc}") from exc
            return path

        dest = _LOCAL_STORAGE_DIR / path
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        return str(dest)

    async def delete(self, path: str) -> None:
        """Remove a stored object. Best-effort; logs on failure."""
        await asyncio.to_thread(self._delete_sync, path)

    def _delete_sync(self, path: str) -> None:
        try:
            if self._use_supabase:
                self._client.storage.from_(settings.supabase_bucket).remove([path])
            else:
                p = Path(path)
                if not p.is_absolute():
                    p = _LOCAL_STORAGE_DIR / path
                if p.exists():
                    p.unlink()
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to delete storage object '%s': %s", path, exc)
