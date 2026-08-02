import hashlib
import hmac
import os
import time
from pathlib import Path
from typing import BinaryIO

from app.config import get_settings
from app.storage.base import StorageBackend


class PathTraversalError(ValueError):
    """Raised when a storage_path, after resolving `..`/symlinks, would land
    outside the storage root. storage_path ultimately comes from a URL path
    segment (GET /files/{path}) and must be treated as untrusted input, not a
    pre-validated key generated only by our own save() calls."""


def _sign(storage_path: str, expires_at: int) -> str:
    # Reuses the app's existing API key as the HMAC secret rather than adding
    # a new required env var — it's already a secret every deployment already
    # has to set, and this signature never reveals it (only a per-path,
    # per-expiry digest is exposed in the URL).
    secret = get_settings().api_key.encode()
    message = f"{storage_path}:{expires_at}".encode()
    return hmac.new(secret, message, hashlib.sha256).hexdigest()


class LocalStorageBackend(StorageBackend):
    def __init__(self, base_path: str):
        self.base_path = Path(base_path).resolve()
        self.base_path.mkdir(parents=True, exist_ok=True)

    def _resolve(self, storage_path: str) -> Path:
        target = (self.base_path / storage_path).resolve()
        if target != self.base_path and self.base_path not in target.parents:
            raise PathTraversalError(f"Path escapes storage root: {storage_path!r}")
        return target

    def save(self, key: str, data: BinaryIO) -> str:
        target = self._resolve(key)
        target.parent.mkdir(parents=True, exist_ok=True)
        with open(target, "wb") as f:
            f.write(data.read())
        return key

    def read(self, storage_path: str) -> bytes:
        with open(self._resolve(storage_path), "rb") as f:
            return f.read()

    def url(self, storage_path: str, expires_in: int = 3600) -> str:
        """Signed, expiring download link (HMAC over path+expiry, verified in
        api/files.py) — not just the static API key as a query param, which
        never expired and wasn't scoped to a single file. Swapping to
        S3Backend later gets a native presigned URL without any caller
        needing to change, same as before."""
        expires_at = int(time.time()) + expires_in
        signature = _sign(storage_path, expires_at)
        return f"/files/{storage_path}?expires={expires_at}&sig={signature}"

    def verify_url(self, storage_path: str, query_params: dict) -> bool:
        expires_at = query_params.get("expires")
        signature = query_params.get("sig")
        if expires_at is None or signature is None:
            return False
        expires_at = int(expires_at)
        if time.time() > expires_at:
            return False
        expected = _sign(storage_path, expires_at)
        return hmac.compare_digest(expected, str(signature))

    def delete(self, storage_path: str) -> None:
        target = self._resolve(storage_path)
        if target.exists():
            os.remove(target)
