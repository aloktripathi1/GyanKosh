import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import require_api_key
from app.db import get_db
from app.models.tkp_version import TKPVersion
from app.schemas.entities import RegenerateSectionRequest, TKPVersionRead

router = APIRouter(prefix="/tkp", tags=["tkp"])

REGENERATABLE_SECTIONS = {
    "classification",
    "extracted_knowledge",
    "teaching_plan",
    "period_content",
    "assessments",
    "learning_gaps",
}


@router.get("/{tkp_id}", response_model=TKPVersionRead, dependencies=[Depends(require_api_key)])
def get_tkp(tkp_id: uuid.UUID, db: Session = Depends(get_db)) -> TKPVersionRead:
    tkp = db.get(TKPVersion, tkp_id)
    if tkp is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="TKP version not found")
    return TKPVersionRead.model_validate(tkp)


@router.post("/{tkp_id}/regenerate/{section}", status_code=status.HTTP_202_ACCEPTED, dependencies=[Depends(require_api_key)])
def regenerate_section(tkp_id: uuid.UUID, section: str, body: RegenerateSectionRequest, db: Session = Depends(get_db)) -> dict:
    if section not in REGENERATABLE_SECTIONS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Unknown section: {section}")
    tkp = db.get(TKPVersion, tkp_id)
    if tkp is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="TKP version not found")
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="Single-section regeneration lands in Milestone 5")
