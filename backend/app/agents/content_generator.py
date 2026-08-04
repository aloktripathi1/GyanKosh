from pydantic import BaseModel

from app.agents.grounding import resolve_grounding_refs
from app.llm.client import ModelTier, structured_call
from app.llm.prompts.content_generator import SYSTEM_PROMPT, build_user_prompt
from app.schemas.content_generator import CheckpointQuestion, PeriodContent, PeriodContentOutput
from app.schemas.knowledge_extraction import KnowledgeExtractionOutput
from app.schemas.teaching_planner import TeachingPlanOutput


class ContentGeneratorInput:
    def __init__(
        self,
        teaching_plan: TeachingPlanOutput,
        extracted_knowledge: KnowledgeExtractionOutput,
        language: str = "English",
    ):
        self.teaching_plan = teaching_plan
        self.extracted_knowledge = extracted_knowledge
        self.language = language


class _DraftCheckpointQuestion(BaseModel):
    question: str
    expected_answer: str
    grounding_refs: list[str]


class _DraftPeriodContent(BaseModel):
    period_number: int
    entry_ticket: str
    teacher_script: str
    blackboard_notes: str
    activities: list[str]
    checkpoint_questions: list[_DraftCheckpointQuestion]
    exit_ticket: str
    homework: str
    mentor_moment: str
    grounding_refs: list[str]


class _PeriodContentDraft(BaseModel):
    periods: list[_DraftPeriodContent]


def run(input: ContentGeneratorInput) -> PeriodContentOutput:
    draft = structured_call(
        tier=ModelTier.STRONG,
        system_prompt=SYSTEM_PROMPT,
        user_prompt=build_user_prompt(input.teaching_plan, input.extracted_knowledge, input.language),
        output_schema=_PeriodContentDraft,
    )

    periods = []
    for dp in draft.periods:
        checkpoint_questions = [
            CheckpointQuestion(
                question=q.question,
                expected_answer=q.expected_answer,
                source_spans=resolve_grounding_refs(input.extracted_knowledge, q.grounding_refs),
            )
            for q in dp.checkpoint_questions
        ]
        periods.append(
            PeriodContent(
                period_number=dp.period_number,
                entry_ticket=dp.entry_ticket,
                teacher_script=dp.teacher_script,
                blackboard_notes=dp.blackboard_notes,
                activities=dp.activities,
                checkpoint_questions=checkpoint_questions,
                exit_ticket=dp.exit_ticket,
                homework=dp.homework,
                mentor_moment=dp.mentor_moment,
                source_spans=resolve_grounding_refs(input.extracted_knowledge, dp.grounding_refs),
            )
        )

    return PeriodContentOutput(periods=periods)
