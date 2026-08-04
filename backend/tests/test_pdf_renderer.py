"""Section 15: PDF render must not fail on unusual content (special
characters, long tables). Uses the real WeasyPrint pipeline (no mocking) since
this is specifically about the HTML/CSS -> PDF conversion, not agent logic."""

from datetime import UTC, datetime

import fitz

from app.publishing.pdf_renderer import render_assessment_book, render_lesson_plans, render_teacher_guide
from app.schemas.activity_generator import Activity, ActivityGenerationOutput, PeriodActivities
from app.schemas.assessment_generator import MCQ, AssessmentGenerationOutput, PeriodAssessment
from app.schemas.classification import ClassificationOutput, DifficultyLevel
from app.schemas.common import SourceSpan
from app.schemas.content_generator import CheckpointQuestion, PeriodContent, PeriodContentOutput
from app.schemas.gap_analysis import GapAnalysisOutput
from app.schemas.knowledge_extraction import Concept, GroundedItem, KnowledgeExtractionOutput
from app.schemas.teaching_planner import Period, TeachingPlanOutput
from app.schemas.tkp import TeacherKnowledgePackage
from app.schemas.validation import (
    CompletenessCheckResult,
    ConsistencyCheckResult,
    GroundingCheckResult,
    SchemaCheckResult,
    ValidationReport,
)
from app.storage.local_storage import LocalStorageBackend

SPAN = SourceSpan(section_id="s1", start_char=0, end_char=10, quote="x < y & z > 0")

# HTML-special characters, unicode, and a long list standing in for a large
# table — all the things a naive (non-escaping, non-paginating) renderer
# could choke on.
NASTY_TEXT = "Reaction: A + B <-> C & D, where x < y, \"quoted\" & 'apostrophe', ₹100, 温度, ü/ö/ß"
LONG_TABLE_ROWS = [f"Row {i}: {NASTY_TEXT}" for i in range(300)]


def _tkp() -> TeacherKnowledgePackage:
    classification = ClassificationOutput(
        subject=NASTY_TEXT, grade="9", difficulty=DifficultyLevel.INTERMEDIATE, topic=NASTY_TEXT,
        chapter="1", category="cat", language="en",
    )
    extraction = KnowledgeExtractionOutput(
        objectives=[GroundedItem(text=NASTY_TEXT, source_span=SPAN)],
        prerequisites=[], concepts=[Concept(text=NASTY_TEXT, name=NASTY_TEXT, source_span=SPAN)],
        definitions=[], formulae=[], keywords=[], examples=[], applications=[], misconceptions=[],
    )
    plan = TeachingPlanOutput(
        periods=[Period(period_number=1, title=NASTY_TEXT, objectives=[NASTY_TEXT], concepts_covered=[NASTY_TEXT],
                         sequencing_rationale=NASTY_TEXT, recommended_duration_minutes=40)],
        total_periods=1, planning_rationale=NASTY_TEXT,
    )
    content = PeriodContentOutput(periods=[
        PeriodContent(period_number=1, entry_ticket=NASTY_TEXT, teacher_script="\n".join(LONG_TABLE_ROWS),
                      blackboard_notes=NASTY_TEXT, activities=LONG_TABLE_ROWS[:50],
                      checkpoint_questions=[CheckpointQuestion(question=NASTY_TEXT, expected_answer=NASTY_TEXT, source_spans=[SPAN])],
                      exit_ticket=NASTY_TEXT, homework=NASTY_TEXT, mentor_moment=NASTY_TEXT, source_spans=[SPAN])
    ])
    activities = ActivityGenerationOutput(periods=[
        PeriodActivities(period_number=1, activities=[
            Activity(title=NASTY_TEXT, type="demo", duration_minutes=10, materials=LONG_TABLE_ROWS[:20],
                      instructions=LONG_TABLE_ROWS[:20], success_criteria=[NASTY_TEXT], source_spans=[SPAN])
        ])
    ])
    assessments = AssessmentGenerationOutput(periods=[
        PeriodAssessment(period_number=1, mcqs=[MCQ(question=NASTY_TEXT, options=[NASTY_TEXT, "b", "c", "d"],
                                                       correct_option_index=0, explanation=NASTY_TEXT, source_spans=[SPAN])],
                          short_answer=[], long_answer=[], numerical=[])
    ])
    gaps = GapAnalysisOutput(gaps=[])
    validation_report = ValidationReport(
        schema_check=SchemaCheckResult(passed=True, errors=[]),
        grounding_check=GroundingCheckResult(passed=True, violations=[]),
        completeness_check=CompletenessCheckResult(passed=True, missing_items=[]),
        consistency_check=ConsistencyCheckResult(passed=True, conflicts=[]),
    )
    return TeacherKnowledgePackage(
        job_id="job-1", version=1, classification=classification, extracted_knowledge=extraction,
        teaching_plan=plan, period_content=content, activities=activities, assessments=assessments,
        learning_gaps=gaps, validation_report=validation_report, published_at=datetime.now(UTC),
    )


def test_lesson_plans_pdf_renders_special_characters_and_long_content(tmp_path):
    storage = LocalStorageBackend(str(tmp_path))
    key = render_lesson_plans(_tkp(), storage)
    pdf_bytes = storage.read(key)
    assert pdf_bytes.startswith(b"%PDF")


def test_teacher_guide_pdf_renders_special_characters_and_long_content(tmp_path):
    storage = LocalStorageBackend(str(tmp_path))
    key = render_teacher_guide(_tkp(), storage)
    pdf_bytes = storage.read(key)
    assert pdf_bytes.startswith(b"%PDF")


def test_assessment_book_pdf_renders_special_characters(tmp_path):
    storage = LocalStorageBackend(str(tmp_path))
    key = render_assessment_book(_tkp(), storage)
    pdf_bytes = storage.read(key)
    assert pdf_bytes.startswith(b"%PDF")


def test_teacher_guide_pdf_prints_difficulty_value_not_enum_repr(tmp_path):
    storage = LocalStorageBackend(str(tmp_path))
    key = render_teacher_guide(_tkp(), storage)
    pdf_bytes = storage.read(key)
    text = fitz.open(stream=pdf_bytes, filetype="pdf")[0].get_text()
    assert "Difficulty: intermediate" in text
    assert "DifficultyLevel" not in text
