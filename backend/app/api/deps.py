from fastapi import Header, HTTPException, Query, status

from app.config import get_settings
from app.storage.local_storage import verify_signature


def require_api_key(x_api_key: str = Header(...)) -> None:
    settings = get_settings()
    if x_api_key != settings.api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")


def require_file_access(
    path: str,
    x_api_key: str | None = Header(default=None),
    api_key: str | None = Query(default=None),
    expires: int | None = Query(default=None),
    sig: str | None = Query(default=None),
) -> None:
    """File downloads accept either the API key (header, or query param since
    a browser navigating to a plain link can't set custom headers) or a
    signed, expiring token scoped to this exact path (see
    storage/local_storage.py::url() — this is what GET /tkp/{id} hands back
    in pdf_paths, generated fresh on every fetch rather than baked in once)."""
    settings = get_settings()
    if (x_api_key or api_key) == settings.api_key:
        return
    if expires is not None and sig is not None and verify_signature(path, expires, sig):
        return
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired file access credentials")
