import uuid

import pytest

from app.models.job import Job, JobStatus
from app.models.tkp_version import TKPVersion
from app.orchestrator import regenerate
from app.schemas.activity_generator import ActivityGenerationOutput
from app.schemas.assessment_generator import AssessmentGenerationOutput
from app.schemas.classification import ClassificationOutput, DifficultyLevel
from app.schemas.common import SourceSpan
from app.schemas.content_generator import PeriodContentOutput
from app.schemas.document_intelligence import DocumentIntelligenceOutput, DocumentSection
from app.schemas.gap_analysis import GapAnalysisOutput
from app.schemas.knowledge_extraction import Concept, GroundedItem, KnowledgeExtractionOutput
from app.schemas.teaching_planner import Period, TeachingPlanOutput

SPAN = SourceSpan(section_id="s1", start_char=0, end_char=5, quote="F=ma.")


class FakeSession:
    def __init__(self, job):
        self._job = job

    def get(self, model, id_):
        return self._job

    def commit(self):
        pass

    def refresh(self, obj):
        pass


def _classification():
    return ClassificationOutput(
        subject="Physics", grade="9", difficulty=DifficultyLevel.BEGINNER, topic="t", chapter="c", category="cat", language="en"
    )


def _extraction():
    return KnowledgeExtractionOutput(
        objectives=[GroundedItem(text="o", source_span=SPAN)],
        prerequisites=[], concepts=[Concept(text="F=ma.", name="N2", source_span=SPAN)],
        definitions=[], formulae=[], keywords=[], examples=[], applications=[], misconceptions=[],
    )


def _plan():
    return TeachingPlanOutput(
        periods=[Period(period_number=1, title="P1", objectives=["o"], concepts_covered=["c"], sequencing_rationale="r", recommended_duration_minutes=40)],
        total_periods=1, planning_rationale="r",
    )


def _tkp_version(job_id):
    return TKPVersion(
        id=uuid.uuid4(),
        job_id=job_id,
        version=1,
        classification=_classification().model_dump(mode="json"),
        extracted_knowledge=_extraction().model_dump(mode="json"),
        teaching_plan=_plan().model_dump(mode="json"),
        period_content=PeriodContentOutput(periods=[]).model_dump(mode="json"),
        activities=ActivityGenerationOutput(periods=[]).model_dump(mode="json"),
        assessments=AssessmentGenerationOutput(periods=[]).model_dump(mode="json"),
        learning_gaps=GapAnalysisOutput(gaps=[]).model_dump(mode="json"),
        validation_report=None,
    )


def _job_with_doc_intel():
    doc_intel = DocumentIntelligenceOutput(
        document_id="d1", sections=[DocumentSection(id="s1", level=1, text="Newton's second law: F=ma.")], raw_text="x"
    )
    job = Job(id=uuid.uuid4(), document_id=uuid.uuid4(), status=JobStatus.COMPLETED)
    job.stage_results = {"document_intelligence": doc_intel.model_dump(mode="json")}
    return job


def test_regenerate_teaching_plan_updates_field_and_revalidates(monkeypatch):
    job = _job_with_doc_intel()
    tkp = _tkp_version(job.id)
    db = FakeSession(job)

    new_plan = TeachingPlanOutput(
        periods=[Period(period_number=1, title="Updated", objectives=["o2"], concepts_covered=["c"], sequencing_rationale="r2", recommended_duration_minutes=40)],
        total_periods=1, planning_rationale="regenerated",
    )
    monkeypatch.setattr(regenerate.teaching_planner, "run", lambda *a, **k: new_plan)

    updated = regenerate.regenerate_section(db, tkp, "teaching_plan")

    assert updated.teaching_plan["planning_rationale"] == "regenerated"
    assert updated.validation_report is not None


def test_regenerate_rejects_unknown_section():
    job = _job_with_doc_intel()
    tkp = _tkp_version(job.id)
    db = FakeSession(job)

    with pytest.raises(regenerate.RegenerationError):
        regenerate.regenerate_section(db, tkp, "not_a_real_section")


def test_regenerate_classification_requires_document_intelligence_checkpoint(monkeypatch):
    job = _job_with_doc_intel()
    job.stage_results = {}  # simulate an older job that never checkpointed it
    tkp = _tkp_version(job.id)
    db = FakeSession(job)

    with pytest.raises(regenerate.RegenerationError, match="document_intelligence"):
        regenerate.regenerate_section(db, tkp, "classification")
