from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response

from app.api.deps import require_api_key_header_or_query
from app.storage import get_storage

router = APIRouter(prefix="/files", tags=["files"])


@router.get("/{path:path}", dependencies=[Depends(require_api_key_header_or_query)])
def get_file(path: str) -> Response:
    """Serves files through the storage interface — local-disk today, would
    become a redirect to a signed S3 URL if STORAGE_BACKEND swaps to s3."""
    storage = get_storage()
    try:
        data = storage.read(path)
    except FileNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found") from e
    media_type = "application/pdf" if path.endswith(".pdf") else "application/octet-stream"
    return Response(content=data, media_type=media_type)
