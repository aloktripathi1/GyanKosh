from pydantic import BaseModel, Field

from app.schemas.common import SourceSpan


class CheckpointQuestion(BaseModel):
    question: str
    expected_answer: str
    source_spans: list[SourceSpan]


class PeriodContent(BaseModel):
    period_number: int
    entry_ticket: str
    teacher_script: str
    blackboard_notes: str
    activities: list[str] = Field(description="brief activity titles/summaries; full detail lives in the Stage 6 activity output")
    checkpoint_questions: list[CheckpointQuestion]
    exit_ticket: str
    homework: str
    mentor_moment: str
    source_spans: list[SourceSpan]


class PeriodContentOutput(BaseModel):
    periods: list[PeriodContent]
