from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response

from app.api.deps import require_file_access
from app.storage import get_storage
from app.storage.local_storage import PathTraversalError

router = APIRouter(prefix="/files", tags=["files"])


@router.get("/{path:path}", dependencies=[Depends(require_file_access)])
def get_file(path: str) -> Response:
    """Serves files through the storage interface — local-disk today, would
    become a redirect to a signed S3 URL if STORAGE_BACKEND swaps to s3."""
    storage = get_storage()
    try:
        data = storage.read(path)
    except PathTraversalError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid path") from e
    except FileNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found") from e
    media_type = "application/pdf" if path.endswith(".pdf") else "application/octet-stream"
    return Response(content=data, media_type=media_type)
