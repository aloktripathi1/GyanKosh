from pydantic import BaseModel

from app.schemas.common import SeverityLevel, SourceSpan


class DiagnosticQuestion(BaseModel):
    question: str
    targets_misconception: str
    source_spans: list[SourceSpan]


class LearningGap(BaseModel):
    misconception: str
    severity: SeverityLevel
    diagnostic_questions: list[DiagnosticQuestion]
    remediation: str
    source_spans: list[SourceSpan]


class GapAnalysisOutput(BaseModel):
    gaps: list[LearningGap]
