import io
import uuid

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.api.deps import require_api_key
from app.db import get_db
from app.models.document import Document
from app.models.job import Job
from app.schemas.entities import DocumentCreateResponse, DocumentRead
from app.storage import get_storage

router = APIRouter(prefix="/documents", tags=["documents"])

ALLOWED_CONTENT_TYPES = {
    "application/pdf": "pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": "pptx",
    "text/plain": "txt",
}
MAX_UPLOAD_BYTES = 25 * 1024 * 1024


@router.post("", response_model=DocumentCreateResponse, status_code=status.HTTP_202_ACCEPTED, dependencies=[Depends(require_api_key)])
async def upload_document(file: UploadFile, db: Session = Depends(get_db)) -> DocumentCreateResponse:
    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail=f"Unsupported file type: {file.content_type}")

    contents = await file.read()
    if len(contents) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="File exceeds max upload size")

    file_type = ALLOWED_CONTENT_TYPES[file.content_type]
    document_id = uuid.uuid4()
    storage_key = f"documents/{document_id}/{file.filename}"

    storage = get_storage()
    storage.save(storage_key, io.BytesIO(contents))

    document = Document(id=document_id, filename=file.filename, file_type=file_type, storage_path=storage_key)
    db.add(document)
    db.flush()

    job = Job(document_id=document.id)
    db.add(job)
    db.commit()
    db.refresh(document)
    db.refresh(job)

    return DocumentCreateResponse(document=DocumentRead.model_validate(document), job_id=job.id)
