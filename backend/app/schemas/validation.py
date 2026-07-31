from pydantic import BaseModel, Field


class SchemaCheckResult(BaseModel):
    passed: bool
    errors: list[str]


class GroundingViolation(BaseModel):
    claim: str
    location: str = Field(description="where in the TKP the ungrounded claim was found")
    reason: str


class GroundingCheckResult(BaseModel):
    passed: bool
    violations: list[GroundingViolation]


class CompletenessCheckResult(BaseModel):
    passed: bool
    missing_items: list[str]


class ConsistencyCheckResult(BaseModel):
    passed: bool
    conflicts: list[str] = Field(description="cross-period inconsistencies found, e.g. contradictory definitions")


class ValidationReport(BaseModel):
    schema_check: SchemaCheckResult
    grounding_check: GroundingCheckResult
    completeness_check: CompletenessCheckResult
    consistency_check: ConsistencyCheckResult

    @property
    def passed(self) -> bool:
        return (
            self.schema_check.passed
            and self.grounding_check.passed
            and self.completeness_check.passed
            and self.consistency_check.passed
        )
