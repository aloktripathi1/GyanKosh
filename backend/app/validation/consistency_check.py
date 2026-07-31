from app.schemas.validation import CompletenessCheckResult, ConsistencyCheckResult


def check_completeness(tkp_payload: dict) -> CompletenessCheckResult:
    """Confirm every required section/period is present. Implemented in Milestone 4."""
    raise NotImplementedError("Completeness check lands in Milestone 4")


def check_consistency(tkp_payload: dict) -> ConsistencyCheckResult:
    """Confirm no contradictions across periods (e.g. conflicting definitions).
    Implemented in Milestone 4."""
    raise NotImplementedError("Consistency check lands in Milestone 4")
