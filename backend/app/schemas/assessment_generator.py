from pydantic import BaseModel, ConfigDict

from app.schemas.common import SourceSpan


class MCQ(BaseModel):
    question: str
    options: list[str]
    correct_option_index: int
    explanation: str
    source_spans: list[SourceSpan]


class ShortAnswerQuestion(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    question: str
    model_answer: str
    rubric: list[str]
    source_spans: list[SourceSpan]


class LongAnswerQuestion(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    question: str
    model_answer: str
    rubric: list[str]
    source_spans: list[SourceSpan]


class NumericalQuestion(BaseModel):
    question: str
    correct_answer: float
    tolerance: float = 0.0
    solution_steps: list[str]
    source_spans: list[SourceSpan]


class PeriodAssessment(BaseModel):
    period_number: int
    mcqs: list[MCQ]
    short_answer: list[ShortAnswerQuestion]
    long_answer: list[LongAnswerQuestion]
    numerical: list[NumericalQuestion]


class AssessmentGenerationOutput(BaseModel):
    periods: list[PeriodAssessment]
