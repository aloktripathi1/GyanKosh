from app.schemas.activity_generator import Activity, ActivityGenerationOutput, PeriodActivities
from app.schemas.assessment_generator import MCQ, AssessmentGenerationOutput, PeriodAssessment, ShortAnswerQuestion
from app.schemas.classification import ClassificationOutput, DifficultyLevel
from app.schemas.common import SourceSpan
from app.schemas.content_generator import CheckpointQuestion, PeriodContent, PeriodContentOutput
from app.schemas.gap_analysis import GapAnalysisOutput
from app.schemas.knowledge_extraction import Concept, GroundedItem, KnowledgeExtractionOutput
from app.schemas.teaching_planner import Period, TeachingPlanOutput
from app.validation import consistency_check, grounding_check, schema_check

GROUNDED_SPAN = SourceSpan(section_id="s1", start_char=0, end_char=10, quote="F = m * a.")
UNGROUNDED_SPAN = SourceSpan(section_id="s1", start_char=999, end_char=1010, quote="fabricated claim never extracted")


def _extraction():
    return KnowledgeExtractionOutput(
        objectives=[GroundedItem(text="obj", source_span=GROUNDED_SPAN)],
        prerequisites=[],
        concepts=[Concept(text="F = m * a.", name="Newton's Second Law", source_span=GROUNDED_SPAN)],
        definitions=[],
        formulae=[],
        keywords=[],
        examples=[],
        applications=[],
        misconceptions=[],
    )


def _plan():
    return TeachingPlanOutput(
        periods=[Period(period_number=1, title="P1", objectives=["o"], concepts_covered=["c"], sequencing_rationale="r", recommended_duration_minutes=40)],
        total_periods=1,
        planning_rationale="r",
    )


# --- schema_check ---


def test_schema_check_passes_on_valid_payload():
    payload = ClassificationOutput(
        subject="Physics", grade="9", difficulty=DifficultyLevel.BEGINNER, topic="t", chapter="c", category="cat", language="en"
    ).model_dump()
    result = schema_check.check(payload, ClassificationOutput)
    assert result.passed
    assert result.errors == []


def test_schema_check_fails_on_missing_field():
    result = schema_check.check({"subject": "Physics"}, ClassificationOutput)
    assert not result.passed
    assert len(result.errors) > 0


# --- grounding_check ---


def _content(span: SourceSpan):
    return PeriodContentOutput(
        periods=[
            PeriodContent(
                period_number=1,
                entry_ticket="e",
                teacher_script="t",
                blackboard_notes="b",
                activities=["a"],
                checkpoint_questions=[CheckpointQuestion(question="q", expected_answer="a", source_spans=[span])],
                exit_ticket="x",
                homework="h",
                mentor_moment="m",
                source_spans=[span],
            )
        ]
    )


def _activities(span: SourceSpan):
    return ActivityGenerationOutput(
        periods=[
            PeriodActivities(
                period_number=1,
                activities=[
                    Activity(
                        title="Demo", type="demo", duration_minutes=10, materials=[], instructions=[], success_criteria=[], source_spans=[span]
                    )
                ],
            )
        ]
    )


def _assessments(span: SourceSpan):
    return AssessmentGenerationOutput(
        periods=[
            PeriodAssessment(
                period_number=1,
                mcqs=[MCQ(question="q", options=["a", "b"], correct_option_index=0, explanation="e", source_spans=[span])],
                short_answer=[],
                long_answer=[],
                numerical=[],
            )
        ]
    )


def test_grounding_check_passes_when_all_spans_trace_to_stage3():
    result = grounding_check.check(_extraction(), _content(GROUNDED_SPAN), _activities(GROUNDED_SPAN), _assessments(GROUNDED_SPAN), GapAnalysisOutput(gaps=[]))
    assert result.passed
    assert result.violations == []


def test_grounding_check_flags_deliberately_injected_ungrounded_claim():
    """Definition of Done: the grounding check must actually catch an injected
    ungrounded claim, not just green-light everything."""
    result = grounding_check.check(_extraction(), _content(UNGROUNDED_SPAN), _activities(GROUNDED_SPAN), _assessments(GROUNDED_SPAN), GapAnalysisOutput(gaps=[]))
    assert not result.passed
    assert any("fabricated claim" in v.claim for v in result.violations)


# --- consistency_check ---


def test_completeness_passes_when_every_period_covered():
    plan = _plan()
    result = consistency_check.check_completeness(plan, _content(GROUNDED_SPAN), _activities(GROUNDED_SPAN), _assessments(GROUNDED_SPAN))
    assert result.passed


def test_completeness_flags_missing_period():
    plan = TeachingPlanOutput(
        periods=[
            Period(period_number=1, title="P1", objectives=["o"], concepts_covered=["c"], sequencing_rationale="r", recommended_duration_minutes=40),
            Period(period_number=2, title="P2", objectives=["o"], concepts_covered=["c"], sequencing_rationale="r", recommended_duration_minutes=40),
        ],
        total_periods=2,
        planning_rationale="r",
    )
    result = consistency_check.check_completeness(plan, _content(GROUNDED_SPAN), _activities(GROUNDED_SPAN), _assessments(GROUNDED_SPAN))
    assert not result.passed
    assert any("period 2" in item for item in result.missing_items)


def test_completeness_accepts_humanities_style_assessment_with_no_numerical_questions():
    """Section 15: a poem-analysis/humanities period with only short/long answer
    questions (zero MCQs, zero numerical) must count as complete — the
    assessment agent adapting question types away from numerical problems is
    correct behavior, not a gap the completeness check should flag."""
    plan = _plan()
    humanities_assessment = AssessmentGenerationOutput(
        periods=[
            PeriodAssessment(
                period_number=1,
                mcqs=[],
                short_answer=[ShortAnswerQuestion(question="q", model_answer="a", rubric=["r"], source_spans=[GROUNDED_SPAN])],
                long_answer=[],
                numerical=[],
            )
        ]
    )
    result = consistency_check.check_completeness(plan, _content(GROUNDED_SPAN), _activities(GROUNDED_SPAN), humanities_assessment)
    assert result.passed


def test_consistency_check_does_not_inspect_prose_for_contradictions():
    """Documents a real, deliberate limitation (Section 15's 'two periods
    contradicting each other's terminology' case): consistency_check only
    checks period-number references, not prose content — grounding-by-
    reference to immutable Stage 3 spans is the actual defense against
    contradiction, not this check. Two periods with genuinely divergent
    prose but valid period numbers must NOT be flagged here (that isn't
    this check's job), which is what this test locks in."""
    plan = TeachingPlanOutput(
        periods=[
            Period(period_number=1, title="P1", objectives=["o"], concepts_covered=["c"], sequencing_rationale="r", recommended_duration_minutes=40),
            Period(period_number=2, title="P2", objectives=["o"], concepts_covered=["c"], sequencing_rationale="r", recommended_duration_minutes=40),
        ],
        total_periods=2, planning_rationale="r",
    )
    span_a = GROUNDED_SPAN
    span_b = SourceSpan(section_id="s1", start_char=20, end_char=40, quote="a different but equally real fact")
    contradictory_content = PeriodContentOutput(
        periods=[
            PeriodContent(period_number=1, entry_ticket="e", teacher_script="The boiling point is 100C", blackboard_notes="b",
                           activities=["a"], checkpoint_questions=[], exit_ticket="x", homework="h", mentor_moment="m", source_spans=[span_a]),
            PeriodContent(period_number=2, entry_ticket="e", teacher_script="The boiling point is 90C", blackboard_notes="b",
                           activities=["a"], checkpoint_questions=[], exit_ticket="x", homework="h", mentor_moment="m", source_spans=[span_b]),
        ]
    )
    result = consistency_check.check_consistency(plan, contradictory_content, _activities(GROUNDED_SPAN), _assessments(GROUNDED_SPAN))
    assert result.passed  # not a false claim of correctness — a documented scope boundary


def test_consistency_flags_orphaned_period_reference():
    plan = _plan()
    orphaned_content = PeriodContentOutput(
        periods=[
            PeriodContent(
                period_number=99, entry_ticket="e", teacher_script="t", blackboard_notes="b", activities=[],
                checkpoint_questions=[], exit_ticket="x", homework="h", mentor_moment="m", source_spans=[],
            )
        ]
    )
    result = consistency_check.check_consistency(plan, orphaned_content, _activities(GROUNDED_SPAN), _assessments(GROUNDED_SPAN))
    assert not result.passed
    assert any("period 99" in c for c in result.conflicts)
