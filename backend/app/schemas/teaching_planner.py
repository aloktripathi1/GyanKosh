from pydantic import BaseModel, Field


class Period(BaseModel):
    period_number: int
    title: str
    objectives: list[str]
    concepts_covered: list[str]
    sequencing_rationale: str = Field(description="why this content belongs in this period, and in this order")
    recommended_duration_minutes: int = Field(
        description="realistic classroom time for this period's content at this grade level and pace — not a fixed 40-minute default"
    )


class TeachingPlanOutput(BaseModel):
    periods: list[Period]
    total_periods: int
    planning_rationale: str = Field(description="why N periods were chosen for this content's depth")
