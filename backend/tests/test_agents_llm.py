"""Unit tests per Section 14: mock the LLM client, feed known inputs, assert
output validates against the stage's Pydantic schema. Tests structure/contract,
not pedagogical quality."""

import pytest

from app.agents import (
    activity_generator,
    assessment_generator,
    classification,
    content_generator,
    gap_analysis,
    knowledge_extraction,
    teaching_planner,
)
from app.agents.grounding import UnresolvedGroundingRefError
from app.schemas.classification import ClassificationOutput, DifficultyLevel
from app.schemas.common import SourceSpan
from app.schemas.document_intelligence import DocumentIntelligenceOutput, DocumentSection
from app.schemas.knowledge_extraction import Concept, GroundedItem, KnowledgeExtractionOutput
from app.schemas.teaching_planner import Period, TeachingPlanOutput


@pytest.fixture
def sample_document():
    return DocumentIntelligenceOutput(
        document_id="d1",
        sections=[DocumentSection(id="s1", level=1, text="Newton's second law: F = m * a exactly.")],
        raw_text="Newton's second law: F = m * a exactly.",
    )


@pytest.fixture
def sample_classification():
    return ClassificationOutput(
        subject="Physics",
        grade="9",
        difficulty=DifficultyLevel.INTERMEDIATE,
        topic="Newton's Laws",
        chapter="Chapter 3",
        category="textbook chapter",
        language="English",
    )


@pytest.fixture
def sample_extraction():
    span = SourceSpan(section_id="s1", start_char=0, end_char=20, quote="Newton's second law:")
    return KnowledgeExtractionOutput(
        objectives=[GroundedItem(text="Understand force and acceleration", source_span=span)],
        prerequisites=[],
        concepts=[Concept(text="Newton's second law:", name="Newton's Second Law", source_span=span)],
        definitions=[],
        formulae=[],
        keywords=[],
        examples=[],
        applications=[],
        misconceptions=[],
    )


@pytest.fixture
def sample_plan():
    return TeachingPlanOutput(
        periods=[
            Period(
                period_number=1,
                title="Newton's Second Law",
                objectives=["Understand F = ma"],
                concepts_covered=["Newton's Second Law"],
                sequencing_rationale="Foundational law taught first",
                recommended_duration_minutes=40,
            )
        ],
        total_periods=1,
        planning_rationale="Single focused concept fits in one period",
    )


def test_classification_run_returns_schema(monkeypatch, sample_document, sample_classification):
    monkeypatch.setattr(classification, "structured_call", lambda **kwargs: sample_classification)
    result = classification.run(sample_document)
    assert result == sample_classification


def test_classification_run_includes_teaching_context_in_prompt(monkeypatch, sample_document, sample_classification):
    captured = {}

    def fake_call(**kwargs):
        captured.update(kwargs)
        return sample_classification

    monkeypatch.setattr(classification, "structured_call", fake_call)
    classification.run(sample_document, teaching_context="Grade 8 CBSE, exam-prep style")
    assert "Grade 8 CBSE" in captured["user_prompt"]


def test_teaching_planner_run_includes_teaching_context_in_prompt(monkeypatch, sample_classification, sample_extraction, sample_plan):
    captured = {}

    def fake_call(**kwargs):
        captured.update(kwargs)
        return sample_plan

    monkeypatch.setattr(teaching_planner, "structured_call", fake_call)
    planner_input = teaching_planner.TeachingPlannerInput(sample_classification, sample_extraction, "Only 3 periods available")
    teaching_planner.run(planner_input)
    assert "Only 3 periods available" in captured["user_prompt"]


def test_teaching_planner_caps_period_count(monkeypatch, sample_classification, sample_extraction):
    """Section 15: a dense document must not be able to produce an unbounded
    period count even if the model ignores the prompt's own guidance."""
    oversized = TeachingPlanOutput(
        periods=[
            Period(
                period_number=n,
                title=f"P{n}",
                objectives=["o"],
                concepts_covered=["c"],
                sequencing_rationale="r",
                recommended_duration_minutes=30,
            )
            for n in range(1, 41)
        ],
        total_periods=40,
        planning_rationale="dense document",
    )
    monkeypatch.setattr(teaching_planner, "structured_call", lambda **kwargs: oversized)

    result = teaching_planner.run(teaching_planner.TeachingPlannerInput(sample_classification, sample_extraction))

    assert len(result.periods) == teaching_planner.MAX_PERIODS
    assert result.total_periods == teaching_planner.MAX_PERIODS


def test_teaching_planner_rejects_zero_periods(monkeypatch, sample_classification, sample_extraction):
    empty_plan = TeachingPlanOutput(periods=[], total_periods=0, planning_rationale="nothing to teach")
    monkeypatch.setattr(teaching_planner, "structured_call", lambda **kwargs: empty_plan)

    with pytest.raises(ValueError, match="zero periods"):
        teaching_planner.run(teaching_planner.TeachingPlannerInput(sample_classification, sample_extraction))


def test_teaching_planner_leaves_reasonable_plan_untouched(monkeypatch, sample_classification, sample_extraction, sample_plan):
    monkeypatch.setattr(teaching_planner, "structured_call", lambda **kwargs: sample_plan)
    result = teaching_planner.run(teaching_planner.TeachingPlannerInput(sample_classification, sample_extraction))
    assert result == sample_plan


def test_knowledge_extraction_run_resolves_grounding(monkeypatch, sample_document):
    from app.agents.knowledge_extraction import _DraftItem, _KnowledgeExtractionDraft

    draft = _KnowledgeExtractionDraft(
        objectives=[_DraftItem(text="obj", source_section_id="s1", source_quote="Newton's second law:")],
        prerequisites=[],
        concepts=[],
        definitions=[],
        formulae=[],
        keywords=[],
        examples=[],
        applications=[],
        misconceptions=[],
    )
    monkeypatch.setattr(knowledge_extraction, "structured_call", lambda **kwargs: draft)
    result = knowledge_extraction.run(sample_document)
    assert len(result.objectives) == 1
    assert result.objectives[0].source_span.quote == "Newton's second law:"


def test_knowledge_extraction_drops_ungrounded_items_without_failing_the_batch(monkeypatch, sample_document):
    """Real behavior observed on a dense real document: the model correctly
    quotes most items but occasionally paraphrases one. That one item must be
    dropped, not fail every correctly-grounded item alongside it."""
    from app.agents.knowledge_extraction import _DraftItem, _KnowledgeExtractionDraft

    draft = _KnowledgeExtractionDraft(
        objectives=[
            _DraftItem(text="grounded", source_section_id="s1", source_quote="Newton's second law:"),
            _DraftItem(text="fabricated", source_section_id="s1", source_quote="a sentence that does not appear anywhere"),
        ],
        prerequisites=[],
        concepts=[],
        definitions=[],
        formulae=[],
        keywords=[],
        examples=[],
        applications=[],
        misconceptions=[],
    )
    monkeypatch.setattr(knowledge_extraction, "structured_call", lambda **kwargs: draft)

    result = knowledge_extraction.run(sample_document)

    assert len(result.objectives) == 1
    assert result.objectives[0].text == "grounded"


def test_teaching_planner_run_returns_schema(monkeypatch, sample_classification, sample_extraction, sample_plan):
    monkeypatch.setattr(teaching_planner, "structured_call", lambda **kwargs: sample_plan)
    result = teaching_planner.run(
        teaching_planner.TeachingPlannerInput(sample_classification, sample_extraction)
    )
    assert result == sample_plan


def test_content_generator_resolves_grounding(monkeypatch, sample_plan, sample_extraction):
    from app.agents.content_generator import _DraftPeriodContent, _PeriodContentDraft

    draft = _PeriodContentDraft(
        periods=[
            _DraftPeriodContent(
                period_number=1,
                entry_ticket="Quick write",
                teacher_script="Explain F=ma",
                blackboard_notes="F = m * a",
                activities=["Demo"],
                checkpoint_questions=[],
                exit_ticket="Recap",
                homework="Practice problems",
                mentor_moment="Encourage questions",
                grounding_refs=["Understand force and acceleration"],
            )
        ]
    )
    monkeypatch.setattr(content_generator, "structured_call", lambda **kwargs: draft)
    result = content_generator.run(content_generator.ContentGeneratorInput(sample_plan, sample_extraction))
    assert len(result.periods) == 1
    assert result.periods[0].source_spans[0].quote == "Newton's second law:"


def test_content_generator_raises_on_ungrounded_ref(monkeypatch, sample_plan, sample_extraction):
    from app.agents.content_generator import _DraftPeriodContent, _PeriodContentDraft

    draft = _PeriodContentDraft(
        periods=[
            _DraftPeriodContent(
                period_number=1,
                entry_ticket="x",
                teacher_script="x",
                blackboard_notes="x",
                activities=[],
                checkpoint_questions=[],
                exit_ticket="x",
                homework="x",
                mentor_moment="x",
                grounding_refs=["a fact never extracted in Stage 3"],
            )
        ]
    )
    monkeypatch.setattr(content_generator, "structured_call", lambda **kwargs: draft)
    with pytest.raises(UnresolvedGroundingRefError):
        content_generator.run(content_generator.ContentGeneratorInput(sample_plan, sample_extraction))


def test_activity_generator_resolves_grounding(monkeypatch, sample_plan, sample_extraction):
    from app.agents.activity_generator import _ActivityGenerationDraft, _DraftActivity, _DraftPeriodActivities

    draft = _ActivityGenerationDraft(
        periods=[
            _DraftPeriodActivities(
                period_number=1,
                activities=[
                    _DraftActivity(
                        title="Push demo",
                        type="demonstration",
                        duration_minutes=10,
                        materials=["cart"],
                        instructions=["push the cart"],
                        success_criteria=["students observe acceleration"],
                        grounding_refs=["Understand force and acceleration"],
                    )
                ],
            )
        ]
    )
    monkeypatch.setattr(activity_generator, "structured_call", lambda **kwargs: draft)
    result = activity_generator.run(activity_generator.ActivityGeneratorInput(sample_plan, sample_extraction))
    assert result.periods[0].activities[0].title == "Push demo"


def test_assessment_generator_resolves_grounding(monkeypatch, sample_plan, sample_extraction):
    from app.agents.assessment_generator import _AssessmentGenerationDraft, _DraftMCQ, _DraftPeriodAssessment

    draft = _AssessmentGenerationDraft(
        periods=[
            _DraftPeriodAssessment(
                period_number=1,
                mcqs=[
                    _DraftMCQ(
                        question="What is F=ma?",
                        options=["a", "b", "c", "d"],
                        correct_option_index=0,
                        explanation="Because Newton said so",
                        grounding_refs=["Understand force and acceleration"],
                    )
                ],
                short_answer=[],
                long_answer=[],
                numerical=[],
            )
        ]
    )
    monkeypatch.setattr(assessment_generator, "structured_call", lambda **kwargs: draft)
    result = assessment_generator.run(assessment_generator.AssessmentGeneratorInput(sample_plan, sample_extraction))
    assert len(result.periods[0].mcqs) == 1


def test_gap_analysis_resolves_grounding(monkeypatch, sample_extraction):
    from app.agents.gap_analysis import _DraftLearningGap, _GapAnalysisDraft

    draft = _GapAnalysisDraft(
        gaps=[
            _DraftLearningGap(
                misconception="Heavier objects fall faster",
                severity="high",
                diagnostic_questions=[],
                remediation="Demonstrate with a vacuum drop",
                grounding_refs=["Understand force and acceleration"],
            )
        ]
    )
    monkeypatch.setattr(gap_analysis, "structured_call", lambda **kwargs: draft)
    result = gap_analysis.run(sample_extraction)
    assert result.gaps[0].severity.value == "high"
