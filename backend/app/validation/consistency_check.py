from app.schemas.activity_generator import ActivityGenerationOutput
from app.schemas.assessment_generator import AssessmentGenerationOutput
from app.schemas.content_generator import PeriodContentOutput
from app.schemas.teaching_planner import TeachingPlanOutput
from app.schemas.validation import CompletenessCheckResult, ConsistencyCheckResult


def check_completeness(
    teaching_plan: TeachingPlanOutput,
    period_content: PeriodContentOutput,
    activities: ActivityGenerationOutput,
    assessments: AssessmentGenerationOutput,
) -> CompletenessCheckResult:
    """Every period the plan defines must have generated content, activities, and
    at least one assessment question — a period silently missing downstream
    output is a failure, not an acceptable gap."""
    plan_periods = {p.period_number for p in teaching_plan.periods}
    content_periods = {p.period_number for p in period_content.periods}
    activity_periods = {p.period_number for p in activities.periods}
    assessment_periods = {
        p.period_number
        for p in assessments.periods
        if p.mcqs or p.short_answer or p.long_answer or p.numerical
    }

    missing: list[str] = []
    for n in sorted(plan_periods - content_periods):
        missing.append(f"period {n}: missing period_content")
    for n in sorted(plan_periods - activity_periods):
        missing.append(f"period {n}: missing activities")
    for n in sorted(plan_periods - assessment_periods):
        missing.append(f"period {n}: missing assessment questions")

    return CompletenessCheckResult(passed=len(missing) == 0, missing_items=missing)


def check_consistency(
    teaching_plan: TeachingPlanOutput,
    period_content: PeriodContentOutput,
    activities: ActivityGenerationOutput,
    assessments: AssessmentGenerationOutput,
) -> ConsistencyCheckResult:
    """Cross-artifact consistency: every period_number referenced by a
    downstream stage must correspond to a real period in the plan, and no stage
    may report the same period twice. Semantic contradictions between periods
    are structurally prevented upstream (all content is grounded-by-reference
    to immutable Stage 3 spans), so the checkable risk here is orphaned or
    duplicated period references, not divergent claims."""
    plan_periods = {p.period_number for p in teaching_plan.periods}
    conflicts: list[str] = []

    for label, periods, numbers in [
        ("period_content", period_content.periods, [p.period_number for p in period_content.periods]),
        ("activities", activities.periods, [p.period_number for p in activities.periods]),
        ("assessments", assessments.periods, [p.period_number for p in assessments.periods]),
    ]:
        seen: set[int] = set()
        for n in numbers:
            if n not in plan_periods:
                conflicts.append(f"{label} references period {n}, which is not in the teaching plan")
            if n in seen:
                conflicts.append(f"{label} has duplicate entries for period {n}")
            seen.add(n)

    return ConsistencyCheckResult(passed=len(conflicts) == 0, conflicts=conflicts)
