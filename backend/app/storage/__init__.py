from app.config import get_settings
from app.storage.base import StorageBackend
from app.storage.local_storage import LocalStorageBackend


def get_storage() -> StorageBackend:
    settings = get_settings()
    if settings.storage_backend == "local":
        return LocalStorageBackend(settings.local_storage_path)
    raise ValueError(f"Unsupported storage backend: {settings.storage_backend}")
