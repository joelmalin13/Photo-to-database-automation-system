"""Storage abstraction layer supporting Local and Supabase Cloud Storage.

In cloud mode (Vercel serverless), images and annotated bounding-box photos
are saved directly to a Supabase Storage bucket via REST API (httpx),
ensuring persistence without relying on the local ephemeral filesystem.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
import io
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
import uuid
import httpx
from PIL import Image as PILImage

from config.settings import (
    AI_MODE,
    ANNOTATED_DIR,
    IS_VERCEL,
    SUPABASE_BUCKET,
    SUPABASE_SERVICE_KEY,
    SUPABASE_URL,
    UPLOAD_DIR,
    logger,
)


class StorageBackend(ABC):
    """Abstract interface defining file storage operations."""

    @abstractmethod
    def save_file(
        self,
        file_bytes: bytes,
        filename: str,
        is_annotated: bool = False,
    ) -> Tuple[str, str]:
        """Persist file bytes. Returns (storage_key_or_path, access_url)."""
        raise NotImplementedError

    @abstractmethod
    def get_url(self, storage_key: str) -> str:
        """Return publicly accessible or relative URL for a stored image."""
        raise NotImplementedError

    @abstractmethod
    def read_bytes(self, storage_key: str) -> bytes:
        """Fetch raw image bytes given a storage key or path."""
        raise NotImplementedError

    @abstractmethod
    def delete_file(self, storage_key: str) -> bool:
        """Delete file from storage."""
        raise NotImplementedError

    @abstractmethod
    def health_check(self) -> Dict[str, Any]:
        """Return connectivity telemetry."""
        raise NotImplementedError


class LocalStorage(StorageBackend):
    """Local filesystem storage used in workstation development mode."""

    def __init__(self, upload_dir: Path = UPLOAD_DIR, annotated_dir: Path = ANNOTATED_DIR) -> None:
        self.upload_dir = upload_dir
        self.annotated_dir = annotated_dir
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        self.annotated_dir.mkdir(parents=True, exist_ok=True)

    def save_file(
        self,
        file_bytes: bytes,
        filename: str,
        is_annotated: bool = False,
    ) -> Tuple[str, str]:
        prefix = "annotated_" if is_annotated else ""
        safe_name = f"{prefix}{uuid.uuid4().hex[:10]}_{Path(filename).name}"
        target_dir = self.annotated_dir if is_annotated else self.upload_dir
        file_path = target_dir / safe_name
        file_path.write_bytes(file_bytes)

        url_path = f"/annotated/{safe_name}" if is_annotated else f"/uploads/{safe_name}"
        return str(file_path), url_path

    def get_url(self, storage_key: str) -> str:
        p = Path(storage_key)
        name = p.name
        if "annotated" in storage_key.lower():
            return f"/annotated/{name}"
        return f"/uploads/{name}"

    def read_bytes(self, storage_key: str) -> bytes:
        path = Path(storage_key)
        if not path.is_absolute():
            # Check upload or annotated dirs
            up = self.upload_dir / storage_key
            if up.exists():
                return up.read_bytes()
            ann = self.annotated_dir / storage_key
            if ann.exists():
                return ann.read_bytes()
        return path.read_bytes()

    def delete_file(self, storage_key: str) -> bool:
        try:
            p = Path(storage_key)
            if p.exists():
                p.unlink()
                return True
        except Exception as exc:
            logger.warning("Local delete error on %s: %s", storage_key, exc)
        return False

    def health_check(self) -> Dict[str, Any]:
        return {
            "type": "local",
            "backend": "local",
            "status": "ok",
            "upload_dir": str(self.upload_dir),
            "annotated_dir": str(self.annotated_dir),
        }


class SupabaseStorage(StorageBackend):
    """Supabase Cloud Object Storage backend using plain REST API calls via httpx."""

    def __init__(
        self,
        supabase_url: str = SUPABASE_URL,
        service_key: str = SUPABASE_SERVICE_KEY,
        bucket: str = SUPABASE_BUCKET,
    ) -> None:
        self.url = supabase_url.rstrip("/")
        self.key = service_key
        self.bucket = bucket
        self.client = httpx.Client(timeout=15.0)

    def _headers(self, content_type: str = "image/jpeg") -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.key}",
            "apikey": self.key,
            "Content-Type": content_type,
            "x-upsert": "true",
        }

    def save_file(
        self,
        file_bytes: bytes,
        filename: str,
        is_annotated: bool = False,
    ) -> Tuple[str, str]:
        subfolder = "annotated" if is_annotated else "original"
        safe_name = f"{subfolder}/{uuid.uuid4().hex[:10]}_{Path(filename).name}"
        endpoint = f"{self.url}/storage/v1/object/{self.bucket}/{safe_name}"

        # Detect MIME
        ext = Path(filename).suffix.lower()
        content_type = "image/png" if ext == ".png" else "image/jpeg"

        resp = self.client.post(
            endpoint,
            content=file_bytes,
            headers=self._headers(content_type),
        )
        if resp.status_code not in (200, 201):
            logger.error("Supabase storage upload failed: %d - %s", resp.status_code, resp.text)
            raise RuntimeError(f"Supabase upload failed ({resp.status_code}): {resp.text}")

        public_url = self.get_url(safe_name)
        return safe_name, public_url

    def get_url(self, storage_key: str) -> str:
        clean_key = storage_key.lstrip("/")
        if clean_key.startswith("http://") or clean_key.startswith("https://"):
            return clean_key
        return f"{self.url}/storage/v1/object/public/{self.bucket}/{clean_key}"

    def read_bytes(self, storage_key: str) -> bytes:
        if storage_key.startswith("http://") or storage_key.startswith("https://"):
            resp = self.client.get(storage_key)
        else:
            clean_key = storage_key.lstrip("/")
            endpoint = f"{self.url}/storage/v1/object/authenticated/{self.bucket}/{clean_key}"
            resp = self.client.get(endpoint, headers=self._headers())
            if resp.status_code != 200:
                # Try public url
                endpoint = self.get_url(clean_key)
                resp = self.client.get(endpoint)

        if resp.status_code != 200:
            raise FileNotFoundError(f"Could not read image from Supabase: {storage_key} ({resp.status_code})")
        return resp.content

    def delete_file(self, storage_key: str) -> bool:
        clean_key = storage_key.lstrip("/")
        endpoint = f"{self.url}/storage/v1/object/{self.bucket}"
        try:
            resp = self.client.request(
                "DELETE",
                endpoint,
                headers={"Authorization": f"Bearer {self.key}", "apikey": self.key},
                json={"prefixes": [clean_key]},
            )
            return resp.status_code in (200, 204)
        except Exception as exc:
            logger.warning("Supabase delete failed for %s: %s", storage_key, exc)
            return False

    def health_check(self) -> Dict[str, Any]:
        if not self.url or not self.key:
            return {
                "type": "supabase",
                "backend": "supabase",
                "status": "unconfigured",
                "message": "SUPABASE_URL or SUPABASE_SERVICE_KEY missing in environment.",
                "bucket": self.bucket,
            }
        try:
            resp = self.client.get(
                f"{self.url}/storage/v1/bucket/{self.bucket}",
                headers={"Authorization": f"Bearer {self.key}", "apikey": self.key},
            )
            if resp.status_code == 200:
                return {"type": "supabase", "backend": "supabase", "status": "ok", "bucket": self.bucket}
            return {
                "type": "supabase",
                "backend": "supabase",
                "status": "warning",
                "message": f"Bucket query returned HTTP {resp.status_code}",
                "bucket": self.bucket,
            }
        except Exception as exc:
            return {
                "type": "supabase",
                "backend": "supabase",
                "status": "error",
                "message": str(exc),
                "bucket": self.bucket,
            }


_storage_instance: Optional[StorageBackend] = None


def get_storage(mode: Optional[str] = None) -> StorageBackend:
    """Factory retrieving the configured storage backend."""
    global _storage_instance
    target_mode = (mode or AI_MODE).lower()

    if target_mode == "cloud" and SUPABASE_URL and SUPABASE_SERVICE_KEY:
        if not isinstance(_storage_instance, SupabaseStorage):
            _storage_instance = SupabaseStorage()
        return _storage_instance

    if not isinstance(_storage_instance, LocalStorage):
        _storage_instance = LocalStorage()
    return _storage_instance
