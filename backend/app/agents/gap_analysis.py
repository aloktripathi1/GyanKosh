from pydantic import BaseModel

from app.agents.grounding import resolve_grounding_refs
from app.llm.client import ModelTier, structured_call
from app.llm.prompts.gap_analysis import SYSTEM_PROMPT, build_user_prompt
from app.schemas.common import SeverityLevel
from app.schemas.gap_analysis import DiagnosticQuestion, GapAnalysisOutput, LearningGap
from app.schemas.knowledge_extraction import KnowledgeExtractionOutput


class _DraftDiagnosticQuestion(BaseModel):
    question: str
    targets_misconception: str
    grounding_refs: list[str]


class _DraftLearningGap(BaseModel):
    misconception: str
    severity: SeverityLevel
    diagnostic_questions: list[_DraftDiagnosticQuestion]
    remediation: str
    grounding_refs: list[str]


class _GapAnalysisDraft(BaseModel):
    gaps: list[_DraftLearningGap]


def run(input: KnowledgeExtractionOutput) -> GapAnalysisOutput:
    draft = structured_call(
        tier=ModelTier.STRONG,
        system_prompt=SYSTEM_PROMPT,
        user_prompt=build_user_prompt(input),
        output_schema=_GapAnalysisDraft,
    )

    gaps = [
        LearningGap(
            misconception=g.misconception,
            severity=g.severity,
            diagnostic_questions=[
                DiagnosticQuestion(
                    question=q.question,
                    targets_misconception=q.targets_misconception,
                    source_spans=resolve_grounding_refs(input, q.grounding_refs),
                )
                for q in g.diagnostic_questions
            ],
            remediation=g.remediation,
            source_spans=resolve_grounding_refs(input, g.grounding_refs),
        )
        for g in draft.gaps
    ]

    return GapAnalysisOutput(gaps=gaps)
