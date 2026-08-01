"""Section 14's golden fixture requirement: run the full pipeline against a
STEM document, a humanities document, and a deliberately thin/messy document,
and assert on the specific behaviors the spec calls for — clean completion for
the first two, graceful degradation (not a crash, not a fabricated pass) for
the third.

The spec's own words for the third case are "a graceful low-confidence flag" —
this codebase has no dedicated confidence score field, so the flag that
actually exists and is asserted here is the validation report honestly
reporting incompleteness (completeness_check.passed == False) rather than
either crashing or silently reporting a clean pass on thin content.

Real LLM calls are mocked throughout (Section 14: "mock the LLM client"), same
as every other agent/orchestrator test in this suite — this is not a live
NCERT-document integration test, it's a structural proof that three different
"shapes" of input flow through the pipeline correctly."""

from app.models.job import JobStatus
from app.orchestrator import pipeline, stage_runners
from app.schemas.activity_generator import Activity, ActivityGenerationOutput, PeriodActivities
from app.schemas.assessment_generator import MCQ, AssessmentGenerationOutput, PeriodAssessment, ShortAnswerQuestion
from app.schemas.classification import ClassificationOutput, DifficultyLevel
from app.schemas.common import SourceSpan
from app.schemas.content_generator import CheckpointQuestion, PeriodContent, PeriodContentOutput
from app.schemas.document_intelligence import DocumentIntelligenceOutput, DocumentSection
from app.schemas.gap_analysis import GapAnalysisOutput
from app.schemas.knowledge_extraction import Concept, GroundedItem, KnowledgeExtractionOutput
from app.schemas.teaching_planner import Period, TeachingPlanOutput
from tests.test_orchestrator import FakeDocument, FakeJob, FakeSession  # noqa: F401 (fixtures below use these)


def _run(document_intel, classification, extraction, plan, content, activities, assessments, gaps, storage_backend):
    document = FakeDocument("doc.txt")
    db = FakeSession(document)
    job = FakeJob()

    stage_map = {
        pipeline.document_intelligence: document_intel,
        stage_runners.classification_agent: classification,
        stage_runners.knowledge_extraction: extraction,
        stage_runners.teaching_planner: plan,
        stage_runners.content_generator: content,
        stage_runners.activity_generator: activities,
        stage_runners.assessment_generator: assessments,
        stage_runners.gap_analysis: gaps,
    }
    originals = {module: module.run for module in stage_map}
    for module, value in stage_map.items():
        module.run = lambda *a, _v=value, **k: _v
    try:
        pipeline.run_pipeline(db, job)
    finally:
        for module, original in originals.items():
            module.run = original

    return job


def test_stem_document_completes_with_clean_validation(storage):
    span = SourceSpan(section_id="s1", start_char=0, end_char=10, quote="F = m * a.")
    doc_intel = DocumentIntelligenceOutput(
        document_id="d1", sections=[DocumentSection(id="s1", level=1, text="F = m * a.")], raw_text="F = m * a."
    )
    classification = ClassificationOutput(
        subject="Physics", grade="9", difficulty=DifficultyLevel.INTERMEDIATE, topic="Newton's Laws", chapter="3", category="textbook", language="en"
    )
    extraction = KnowledgeExtractionOutput(
        objectives=[GroundedItem(text="Understand F=ma", source_span=span)],
        prerequisites=[], concepts=[Concept(text="F = m * a.", name="Newton's Second Law", source_span=span)],
        definitions=[], formulae=[], keywords=[], examples=[], applications=[], misconceptions=[],
    )
    plan = TeachingPlanOutput(
        periods=[Period(period_number=1, title="P1", objectives=["o"], concepts_covered=["c"], sequencing_rationale="r", recommended_duration_minutes=40)],
        total_periods=1, planning_rationale="r",
    )
    content = PeriodContentOutput(periods=[
        PeriodContent(period_number=1, entry_ticket="e", teacher_script="t", blackboard_notes="b", activities=["a"],
                       checkpoint_questions=[CheckpointQuestion(question="q", expected_answer="a", source_spans=[span])],
                       exit_ticket="x", homework="h", mentor_moment="m", source_spans=[span])
    ])
    activities = ActivityGenerationOutput(periods=[
        PeriodActivities(period_number=1, activities=[
            Activity(title="Demo", type="demo", duration_minutes=10, materials=[], instructions=[], success_criteria=[], source_spans=[span])
        ])
    ])
    assessments = AssessmentGenerationOutput(periods=[
        PeriodAssessment(period_number=1, mcqs=[MCQ(question="q", options=["a", "b"], correct_option_index=0, explanation="e", source_spans=[span])],
                          short_answer=[], long_answer=[], numerical=[])
    ])
    gaps = GapAnalysisOutput(gaps=[])

    job = _run(doc_intel, classification, extraction, plan, content, activities, assessments, gaps, storage)

    assert job.status == JobStatus.COMPLETED
    report = job.stage_results["validation"]
    assert report["grounding_check"]["passed"]
    assert report["completeness_check"]["passed"]
    assert report["consistency_check"]["passed"]


def test_humanities_document_completes_with_non_numerical_assessment(storage):
    """The distinctive humanities case: no numerical questions, only short/long
    answer — must still validate as complete, not be penalized for adapting."""
    span = SourceSpan(section_id="s1", start_char=0, end_char=20, quote="The poem uses imagery to evoke loss.")
    doc_intel = DocumentIntelligenceOutput(
        document_id="d1", sections=[DocumentSection(id="s1", level=1, text="The poem uses imagery to evoke loss.")],
        raw_text="The poem uses imagery to evoke loss.",
    )
    classification = ClassificationOutput(
        subject="English Literature", grade="10", difficulty=DifficultyLevel.INTERMEDIATE, topic="Poetry Analysis",
        chapter="4", category="textbook chapter", language="en",
    )
    extraction = KnowledgeExtractionOutput(
        objectives=[GroundedItem(text="Analyze imagery in poetry", source_span=span)],
        prerequisites=[], concepts=[Concept(text="The poem uses imagery to evoke loss.", name="Imagery", source_span=span)],
        definitions=[], formulae=[], keywords=[], examples=[], applications=[], misconceptions=[],
    )
    plan = TeachingPlanOutput(
        periods=[Period(period_number=1, title="Imagery", objectives=["o"], concepts_covered=["c"], sequencing_rationale="r", recommended_duration_minutes=45)],
        total_periods=1, planning_rationale="r",
    )
    content = PeriodContentOutput(periods=[
        PeriodContent(period_number=1, entry_ticket="e", teacher_script="t", blackboard_notes="b", activities=["a"],
                       checkpoint_questions=[CheckpointQuestion(question="q", expected_answer="a", source_spans=[span])],
                       exit_ticket="x", homework="h", mentor_moment="m", source_spans=[span])
    ])
    activities = ActivityGenerationOutput(periods=[
        PeriodActivities(period_number=1, activities=[
            Activity(title="Close reading", type="discussion", duration_minutes=15, materials=[], instructions=[], success_criteria=[], source_spans=[span])
        ])
    ])
    # No MCQs, no numerical — only short/long answer, exactly the adaptation Section 15 requires.
    assessments = AssessmentGenerationOutput(periods=[
        PeriodAssessment(period_number=1, mcqs=[], short_answer=[ShortAnswerQuestion(question="q", model_answer="a", rubric=["r"], source_spans=[span])],
                          long_answer=[], numerical=[])
    ])
    gaps = GapAnalysisOutput(gaps=[])

    job = _run(doc_intel, classification, extraction, plan, content, activities, assessments, gaps, storage)

    assert job.status == JobStatus.COMPLETED
    report = job.stage_results["validation"]
    assert report["completeness_check"]["passed"]
    assert report["grounding_check"]["passed"]


def test_messy_thin_document_completes_without_crash_and_flags_incompleteness(storage):
    """The 'deliberately messy' fixture: thin extraction, a plan with a period
    that has no downstream content at all. Must not crash and must not
    fabricate a clean pass — the completeness check flags the real gap."""
    span = SourceSpan(section_id="s1", start_char=0, end_char=5, quote="misc.")
    doc_intel = DocumentIntelligenceOutput(
        document_id="d1", sections=[DocumentSection(id="s1", level=1, text="misc.")], raw_text="misc."
    )
    classification = ClassificationOutput(
        subject="Unknown", grade="?", difficulty=DifficultyLevel.BEGINNER, topic="Unclear", chapter="?", category="fragment", language="en"
    )
    extraction = KnowledgeExtractionOutput(
        objectives=[GroundedItem(text="o", source_span=span)],
        prerequisites=[], concepts=[], definitions=[], formulae=[], keywords=[], examples=[], applications=[], misconceptions=[],
    )
    plan = TeachingPlanOutput(
        periods=[Period(period_number=1, title="P1", objectives=["o"], concepts_covered=[], sequencing_rationale="r", recommended_duration_minutes=20)],
        total_periods=1, planning_rationale="thin content, one period",
    )
    # Deliberately no generated content/activities/assessments for period 1 —
    # simulating agents that had too little grounded material to work with.
    content = PeriodContentOutput(periods=[])
    activities = ActivityGenerationOutput(periods=[])
    assessments = AssessmentGenerationOutput(periods=[])
    gaps = GapAnalysisOutput(gaps=[])

    job = _run(doc_intel, classification, extraction, plan, content, activities, assessments, gaps, storage)

    # Graceful degradation: completes (no crash), but the report is honest
    # about the gap rather than fabricating a pass.
    assert job.status == JobStatus.COMPLETED
    report = job.stage_results["validation"]
    assert not report["completeness_check"]["passed"]
    assert any("period 1" in item for item in report["completeness_check"]["missing_items"])
