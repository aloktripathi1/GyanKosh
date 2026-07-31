from datetime import datetime

from pydantic import BaseModel

from app.schemas.activity_generator import ActivityGenerationOutput
from app.schemas.assessment_generator import AssessmentGenerationOutput
from app.schemas.classification import ClassificationOutput
from app.schemas.content_generator import PeriodContentOutput
from app.schemas.gap_analysis import GapAnalysisOutput
from app.schemas.knowledge_extraction import KnowledgeExtractionOutput
from app.schemas.teaching_planner import TeachingPlanOutput
from app.schemas.validation import ValidationReport


class TeacherKnowledgePackage(BaseModel):
    """The fully assembled Stage-10 output. Mirrors the tkp_versions table columns."""

    job_id: str
    version: int
    classification: ClassificationOutput
    extracted_knowledge: KnowledgeExtractionOutput
    teaching_plan: TeachingPlanOutput
    period_content: PeriodContentOutput
    activities: ActivityGenerationOutput
    assessments: list[AssessmentGenerationOutput]
    learning_gaps: GapAnalysisOutput
    validation_report: ValidationReport
    published_at: datetime | None = None
