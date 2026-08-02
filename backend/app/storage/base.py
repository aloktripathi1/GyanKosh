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
    def verify_url(self, storage_path: str, query_params: dict) -> bool:
        """Verify that query_params (e.g. from a GET /files/{path} request)
        actually authorizes access to storage_path, using whatever scheme
        this backend's url() produces. Callers (api/deps.py) go through this
        rather than a backend-specific verification function, so swapping
        backends doesn't require touching the auth layer — a real S3
        implementation would likely make this a no-op returning False, since
        S3 verifies its own presigned URLs and this backend would never be
        asked to."""

    @abstractmethod
    def delete(self, storage_path: str) -> None:
        """Remove the file at storage_path."""
