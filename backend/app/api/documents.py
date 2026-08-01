import hashlib
import io
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.agents.document_type_hints import ALL_HINTS
from app.api.deps import require_api_key
from app.db import get_db
from app.models.document import Document
from app.models.job import Job
from app.schemas.entities import DocumentCreateResponse, DocumentRead
from app.storage import get_storage
from app.tasks.pipeline_tasks import run_job_in_background

# Stages before Content/Activity/Assessment/Gap generation diverge — cheap to
# reuse verbatim when the exact same document bytes are uploaded again, so a
# re-run never re-bills the classification/extraction LLM calls.
_CACHEABLE_STAGES = ("document_intelligence", "classification", "knowledge_extraction")

router = APIRouter(prefix="/documents", tags=["documents"])

ALLOWED_CONTENT_TYPES = {
    "application/pdf": "pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": "pptx",
    "text/plain": "txt",
}
MAX_UPLOAD_BYTES = 25 * 1024 * 1024

# DOCX/PPTX are both ZIP containers at the byte level — the same magic number
# doesn't distinguish them, so a mismatch here only catches the cases it
# actually can: a PDF-labeled upload that isn't a PDF, or an Office-labeled
# upload that isn't even a ZIP. txt has no reliable signature, so it's exempt.
_MAGIC_BYTES = {"pdf": b"%PDF", "docx": b"PK\x03\x04", "pptx": b"PK\x03\x04"}


def _content_type_matches_bytes(file_type: str, contents: bytes) -> bool:
    signature = _MAGIC_BYTES.get(file_type)
    return signature is None or contents.startswith(signature)


@router.post("", response_model=DocumentCreateResponse, status_code=status.HTTP_202_ACCEPTED, dependencies=[Depends(require_api_key)])
async def upload_document(
    file: UploadFile,
    background_tasks: BackgroundTasks,
    teaching_context: str | None = Form(None),
    document_type_hint: str | None = Form(None),
    db: Session = Depends(get_db),
) -> DocumentCreateResponse:
    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail=f"Unsupported file type: {file.content_type}")
    if document_type_hint is not None and document_type_hint not in ALL_HINTS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Unknown document_type_hint: {document_type_hint}")

    contents = await file.read()
    if len(contents) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="File exceeds max upload size")
    if len(contents) == 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded file is empty")

    file_type = ALLOWED_CONTENT_TYPES[file.content_type]
    if not _content_type_matches_bytes(file_type, contents):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File content doesn't match its declared type ({file.content_type})",
        )
    content_hash = hashlib.sha256(contents).hexdigest()
    document_id = uuid.uuid4()
    storage_key = f"documents/{document_id}/{file.filename}"

    storage = get_storage()
    storage.save(storage_key, io.BytesIO(contents))

    document = Document(
        id=document_id,
        filename=file.filename,
        file_type=file_type,
        storage_path=storage_key,
        content_hash=content_hash,
        document_type_hint=document_type_hint,
    )
    db.add(document)
    db.flush()

    cached_stage_results = _find_cached_stage_results(db, content_hash)
    job = Job(
        document_id=document.id,
        stage_results=cached_stage_results,
        teaching_context=teaching_context or None,
    )
    db.add(job)
    db.commit()
    db.refresh(document)
    db.refresh(job)

    background_tasks.add_task(run_job_in_background, str(job.id))

    return DocumentCreateResponse(document=DocumentRead.model_validate(document), job_id=job.id)


def _find_cached_stage_results(db: Session, content_hash: str) -> dict:
    prior_job = (
        db.query(Job)
        .join(Document, Job.document_id == Document.id)
        .filter(Document.content_hash == content_hash)
        .order_by(Job.created_at.desc())
        .first()
    )
    if prior_job is None:
        return {}
    return {stage: prior_job.stage_results[stage] for stage in _CACHEABLE_STAGES if stage in prior_job.stage_results}
