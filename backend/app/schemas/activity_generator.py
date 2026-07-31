from pydantic import BaseModel

from app.schemas.common import SourceSpan


class Activity(BaseModel):
    title: str
    type: str
    duration_minutes: int
    materials: list[str]
    instructions: list[str]
    success_criteria: list[str]
    source_spans: list[SourceSpan]


class PeriodActivities(BaseModel):
    period_number: int
    activities: list[Activity]


class ActivityGenerationOutput(BaseModel):
    periods: list[PeriodActivities]
