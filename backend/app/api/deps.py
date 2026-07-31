from fastapi import Header, HTTPException, Query, status

from app.config import get_settings


def require_api_key(x_api_key: str = Header(...)) -> None:
    settings = get_settings()
    if x_api_key != settings.api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")


def require_api_key_header_or_query(
    x_api_key: str | None = Header(default=None), api_key: str | None = Query(default=None)
) -> None:
    """Browsers can't attach custom headers to a plain link/new-tab navigation,
    so file downloads accept the key as a query param too. Only used for the
    files route — every other endpoint stays header-only."""
    settings = get_settings()
    if (x_api_key or api_key) != settings.api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")
