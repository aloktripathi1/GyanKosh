import os
from pathlib import Path
from typing import BinaryIO

from app.storage.base import StorageBackend


class LocalStorageBackend(StorageBackend):
    def __init__(self, base_path: str):
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)

    def _resolve(self, storage_path: str) -> Path:
        return self.base_path / storage_path

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
        # Prototype: local disk has no native signed-URL mechanism; expiry is not
        # enforced here. Swapping to LocalStorageBackend -> S3Backend restores real
        # expiring URLs without touching any caller.
        return f"/files/{storage_path}"

    def delete(self, storage_path: str) -> None:
        target = self._resolve(storage_path)
        if target.exists():
            os.remove(target)
