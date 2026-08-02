from pydantic import BaseModel, ConfigDict

from app.agents.grounding import resolve_grounding_refs
from app.llm.client import ModelTier, structured_call
from app.llm.prompts.assessment_generator import SYSTEM_PROMPT, build_user_prompt
from app.schemas.assessment_generator import (
    MCQ,
    AssessmentGenerationOutput,
    LongAnswerQuestion,
    NumericalQuestion,
    PeriodAssessment,
    ShortAnswerQuestion,
)
from app.schemas.knowledge_extraction import KnowledgeExtractionOutput
from app.schemas.teaching_planner import TeachingPlanOutput


class AssessmentGeneratorInput:
    def __init__(
        self,
        teaching_plan: TeachingPlanOutput,
        extracted_knowledge: KnowledgeExtractionOutput,
        language: str = "English",
    ):
        self.teaching_plan = teaching_plan
        self.extracted_knowledge = extracted_knowledge
        self.language = language


class _DraftMCQ(BaseModel):
    question: str
    options: list[str]
    correct_option_index: int
    explanation: str
    grounding_refs: list[str]


class _DraftShortAnswer(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    question: str
    model_answer: str
    rubric: list[str]
    grounding_refs: list[str]


class _DraftLongAnswer(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    question: str
    model_answer: str
    rubric: list[str]
    grounding_refs: list[str]


class _DraftNumerical(BaseModel):
    question: str
    correct_answer: float
    tolerance: float = 0.0
    solution_steps: list[str]
    grounding_refs: list[str]


class _DraftPeriodAssessment(BaseModel):
    period_number: int
    mcqs: list[_DraftMCQ]
    short_answer: list[_DraftShortAnswer]
    long_answer: list[_DraftLongAnswer]
    numerical: list[_DraftNumerical]


class _AssessmentGenerationDraft(BaseModel):
    periods: list[_DraftPeriodAssessment]


def run(input: AssessmentGeneratorInput) -> AssessmentGenerationOutput:
    draft = structured_call(
        tier=ModelTier.STRONG,
        system_prompt=SYSTEM_PROMPT,
        user_prompt=build_user_prompt(input.teaching_plan, input.extracted_knowledge, input.language),
        output_schema=_AssessmentGenerationDraft,
    )

    ek = input.extracted_knowledge
    periods = [
        PeriodAssessment(
            period_number=dp.period_number,
            mcqs=[
                MCQ(
                    question=q.question,
                    options=q.options,
                    correct_option_index=q.correct_option_index,
                    explanation=q.explanation,
                    source_spans=resolve_grounding_refs(ek, q.grounding_refs),
                )
                for q in dp.mcqs
            ],
            short_answer=[
                ShortAnswerQuestion(
                    question=q.question,
                    model_answer=q.model_answer,
                    rubric=q.rubric,
                    source_spans=resolve_grounding_refs(ek, q.grounding_refs),
                )
                for q in dp.short_answer
            ],
            long_answer=[
                LongAnswerQuestion(
                    question=q.question,
                    model_answer=q.model_answer,
                    rubric=q.rubric,
                    source_spans=resolve_grounding_refs(ek, q.grounding_refs),
                )
                for q in dp.long_answer
            ],
            numerical=[
                NumericalQuestion(
                    question=q.question,
                    correct_answer=q.correct_answer,
                    tolerance=q.tolerance,
                    solution_steps=q.solution_steps,
                    source_spans=resolve_grounding_refs(ek, q.grounding_refs),
                )
                for q in dp.numerical
            ],
        )
        for dp in draft.periods
    ]

    return AssessmentGenerationOutput(periods=periods)
