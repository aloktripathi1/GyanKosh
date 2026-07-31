from datetime import datetime, timezone

from app.schemas.activity_generator import ActivityGenerationOutput
from app.schemas.assessment_generator import AssessmentGenerationOutput
from app.schemas.classification import ClassificationOutput
from app.schemas.content_generator import PeriodContentOutput
from app.schemas.gap_analysis import GapAnalysisOutput
from app.schemas.knowledge_extraction import KnowledgeExtractionOutput
from app.schemas.teaching_planner import TeachingPlanOutput
from app.schemas.tkp import TeacherKnowledgePackage
from app.schemas.validation import ValidationReport

# Maps STAGE_NAMES (app.models.job) -> (TKP field name, schema)
_STAGE_TO_FIELD = {
    "classification": ("classification", ClassificationOutput),
    "knowledge_extraction": ("extracted_knowledge", KnowledgeExtractionOutput),
    "teaching_planner": ("teaching_plan", TeachingPlanOutput),
    "content_generation": ("period_content", PeriodContentOutput),
    "activity_generation": ("activities", ActivityGenerationOutput),
    "assessment_generation": ("assessments", AssessmentGenerationOutput),
    "gap_analysis": ("learning_gaps", GapAnalysisOutput),
    "validation": ("validation_report", ValidationReport),
}


def build(job_id: str, version: int, stage_results: dict) -> TeacherKnowledgePackage:
    """Assemble the final TeacherKnowledgePackage from checkpointed stage_results.
    Every field is re-validated against its Pydantic schema on the way in — the
    stored JSONB is treated as untrusted until it passes, per Section 5."""
    missing = [stage for stage in _STAGE_TO_FIELD if stage not in stage_results]
    if missing:
        raise ValueError(f"Cannot publish: missing checkpointed stage results for {missing}")

    fields = {field: schema.model_validate(stage_results[stage]) for stage, (field, schema) in _STAGE_TO_FIELD.items()}

    return TeacherKnowledgePackage(
        job_id=job_id,
        version=version,
        published_at=datetime.now(timezone.utc),
        **fields,
    )
