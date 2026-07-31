from app.schemas.activity_generator import ActivityGenerationOutput
from app.schemas.assessment_generator import AssessmentGenerationOutput
from app.schemas.common import SourceSpan
from app.schemas.content_generator import PeriodContentOutput
from app.schemas.gap_analysis import GapAnalysisOutput
from app.schemas.knowledge_extraction import KnowledgeExtractionOutput
from app.schemas.validation import GroundingCheckResult, GroundingViolation


def _span_key(span: SourceSpan) -> tuple:
    return (span.section_id, span.start_char, span.end_char, span.quote)


def _valid_spans(extracted_knowledge: KnowledgeExtractionOutput) -> set[tuple]:
    items = (
        extracted_knowledge.objectives
        + extracted_knowledge.prerequisites
        + extracted_knowledge.concepts
        + extracted_knowledge.definitions
        + extracted_knowledge.formulae
        + extracted_knowledge.keywords
        + extracted_knowledge.examples
        + extracted_knowledge.applications
        + extracted_knowledge.misconceptions
    )
    return {_span_key(item.source_span) for item in items}


def _collect(location: str, spans: list[SourceSpan], valid: set[tuple], violations: list[GroundingViolation]) -> None:
    for span in spans:
        if _span_key(span) not in valid:
            violations.append(
                GroundingViolation(
                    claim=span.quote,
                    location=location,
                    reason="source_span does not match any Stage 3 extracted-knowledge item",
                )
            )


def check(
    extracted_knowledge: KnowledgeExtractionOutput,
    period_content: PeriodContentOutput,
    activities: ActivityGenerationOutput,
    assessments: AssessmentGenerationOutput,
    learning_gaps: GapAnalysisOutput,
) -> GroundingCheckResult:
    """Every source_span attached to generated content must be one that Stage 3
    actually produced. This is a structural re-check, independent of the
    resolve_grounding_refs() call each agent already makes at generation time —
    it exists to catch content that bypassed that path (e.g. a future
    single-section regeneration flow) rather than trusting agents blindly."""
    valid = _valid_spans(extracted_knowledge)
    violations: list[GroundingViolation] = []

    for period in period_content.periods:
        _collect(f"period_content[{period.period_number}]", period.source_spans, valid, violations)
        for q in period.checkpoint_questions:
            _collect(f"period_content[{period.period_number}].checkpoint_question", q.source_spans, valid, violations)

    for period in activities.periods:
        for activity in period.activities:
            _collect(f"activities[{period.period_number}].{activity.title}", activity.source_spans, valid, violations)

    for period in assessments.periods:
        for mcq in period.mcqs:
            _collect(f"assessments[{period.period_number}].mcq", mcq.source_spans, valid, violations)
        for q in period.short_answer:
            _collect(f"assessments[{period.period_number}].short_answer", q.source_spans, valid, violations)
        for q in period.long_answer:
            _collect(f"assessments[{period.period_number}].long_answer", q.source_spans, valid, violations)
        for q in period.numerical:
            _collect(f"assessments[{period.period_number}].numerical", q.source_spans, valid, violations)

    for gap in learning_gaps.gaps:
        _collect(f"learning_gaps.{gap.misconception}", gap.source_spans, valid, violations)
        for q in gap.diagnostic_questions:
            _collect(f"learning_gaps.{gap.misconception}.diagnostic_question", q.source_spans, valid, violations)

    return GroundingCheckResult(passed=len(violations) == 0, violations=violations)
