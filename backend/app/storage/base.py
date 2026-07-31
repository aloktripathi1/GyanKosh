from abc import ABC, abstractmethod
from typing import BinaryIO


class StorageBackend(ABC):
    """All file access — raw uploads and generated PDFs — goes through this
    interface. Agents and API routes must never touch the filesystem or S3 directly,
    so swapping local disk for S3 later is a one-file change."""

    @abstractmethod
    def save(self, key: str, data: BinaryIO) -> str:
        """Persist data under key, return the storage_path to record in the DB."""

    @abstractmethod
    def read(self, storage_path: str) -> bytes:
        """Read back the raw bytes stored at storage_path."""

    @abstractmethod
    def url(self, storage_path: str, expires_in: int = 3600) -> str:
        """Return a (signed, expiring where supported) URL for downloading the file."""

    @abstractmethod
    def delete(self, storage_path: str) -> None:
        """Remove the file at storage_path."""
