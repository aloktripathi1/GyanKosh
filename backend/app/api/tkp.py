import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import require_api_key
from app.db import get_db
from app.models.tkp_version import TKPVersion
from app.orchestrator.regenerate import REGENERATABLE_SECTIONS, RegenerationError, regenerate_section as run_regenerate_section
from app.schemas.entities import RegenerateSectionRequest, TKPVersionRead
from app.storage import get_storage

router = APIRouter(prefix="/tkp", tags=["tkp"])


def _sign_pdf_paths(result: TKPVersionRead) -> TKPVersionRead:
    """pdf_paths is stored as raw storage keys — sign them into short-lived
    download URLs fresh on every fetch, rather than once at publish time,
    since a TKP may be reviewed long after its 1-hour-expiry signed link from
    an earlier view would have gone stale."""
    if result.pdf_paths:
        storage = get_storage()
        result.pdf_paths = {name: storage.url(path) for name, path in result.pdf_paths.items()}
    return result


@router.get("/{tkp_id}", response_model=TKPVersionRead, dependencies=[Depends(require_api_key)])
def get_tkp(tkp_id: uuid.UUID, db: Session = Depends(get_db)) -> TKPVersionRead:
    tkp = db.get(TKPVersion, tkp_id)
    if tkp is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="TKP version not found")
    return _sign_pdf_paths(TKPVersionRead.model_validate(tkp))


@router.post("/{tkp_id}/regenerate/{section}", response_model=TKPVersionRead, dependencies=[Depends(require_api_key)])
def regenerate_section(tkp_id: uuid.UUID, section: str, body: RegenerateSectionRequest, db: Session = Depends(get_db)) -> TKPVersionRead:
    if section not in REGENERATABLE_SECTIONS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Unknown section: {section}")
    # Row-locked, not db.get(): two concurrent regenerate calls on the same TKP
    # (even for different sections) must serialize, not race — the second
    # request blocks here until the first one's transaction commits, so it
    # always reads the first request's write rather than a stale snapshot.
    tkp = db.query(TKPVersion).filter(TKPVersion.id == tkp_id).with_for_update().first()
    if tkp is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="TKP version not found")
    try:
        updated = run_regenerate_section(db, tkp, section)
    except RegenerationError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e)) from e
    return _sign_pdf_paths(TKPVersionRead.model_validate(updated))
