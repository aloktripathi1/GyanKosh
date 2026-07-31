import pytest

from app.publishing import json_builder
from app.schemas.activity_generator import ActivityGenerationOutput
from app.schemas.assessment_generator import AssessmentGenerationOutput
from app.schemas.classification import ClassificationOutput, DifficultyLevel
from app.schemas.common import SourceSpan
from app.schemas.content_generator import PeriodContentOutput
from app.schemas.gap_analysis import GapAnalysisOutput
from app.schemas.knowledge_extraction import Concept, GroundedItem, KnowledgeExtractionOutput
from app.schemas.teaching_planner import Period, TeachingPlanOutput
from app.schemas.validation import (
    CompletenessCheckResult,
    ConsistencyCheckResult,
    GroundingCheckResult,
    SchemaCheckResult,
    ValidationReport,
)

SPAN = SourceSpan(section_id="s1", start_char=0, end_char=5, quote="F=ma.")


def _stage_results():
    extraction = KnowledgeExtractionOutput(
        objectives=[GroundedItem(text="o", source_span=SPAN)],
        prerequisites=[],
        concepts=[Concept(text="F=ma.", name="Newton's Second Law", source_span=SPAN)],
        definitions=[],
        formulae=[],
        keywords=[],
        examples=[],
        applications=[],
        misconceptions=[],
    )
    plan = TeachingPlanOutput(
        periods=[Period(period_number=1, title="P1", objectives=["o"], concepts_covered=["c"], sequencing_rationale="r")],
        total_periods=1,
        planning_rationale="r",
    )
    classification = ClassificationOutput(
        subject="Physics", grade="9", difficulty=DifficultyLevel.BEGINNER, topic="t", chapter="c", category="cat", language="en"
    )
    return {
        "classification": classification.model_dump(mode="json"),
        "knowledge_extraction": extraction.model_dump(mode="json"),
        "teaching_planner": plan.model_dump(mode="json"),
        "content_generation": PeriodContentOutput(periods=[]).model_dump(mode="json"),
        "activity_generation": ActivityGenerationOutput(periods=[]).model_dump(mode="json"),
        "assessment_generation": AssessmentGenerationOutput(periods=[]).model_dump(mode="json"),
        "gap_analysis": GapAnalysisOutput(gaps=[]).model_dump(mode="json"),
        "validation": ValidationReport(
            schema_check=SchemaCheckResult(passed=True, errors=[]),
            grounding_check=GroundingCheckResult(passed=True, violations=[]),
            completeness_check=CompletenessCheckResult(passed=True, missing_items=[]),
            consistency_check=ConsistencyCheckResult(passed=True, conflicts=[]),
        ).model_dump(mode="json"),
    }


def test_build_assembles_tkp_from_stage_results():
    tkp = json_builder.build("job-1", 1, _stage_results())
    assert tkp.job_id == "job-1"
    assert tkp.classification.subject == "Physics"
    assert tkp.extracted_knowledge.concepts[0].name == "Newton's Second Law"
    assert tkp.published_at is not None


def test_build_raises_on_missing_stage():
    incomplete = _stage_results()
    del incomplete["validation"]
    with pytest.raises(ValueError, match="validation"):
        json_builder.build("job-1", 1, incomplete)
