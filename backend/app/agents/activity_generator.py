from pydantic import BaseModel

from app.agents.grounding import resolve_grounding_refs
from app.llm.client import ModelTier, structured_call
from app.llm.prompts.activity_generator import SYSTEM_PROMPT, build_user_prompt
from app.schemas.activity_generator import Activity, ActivityGenerationOutput, PeriodActivities
from app.schemas.knowledge_extraction import KnowledgeExtractionOutput
from app.schemas.teaching_planner import TeachingPlanOutput


class ActivityGeneratorInput:
    def __init__(self, teaching_plan: TeachingPlanOutput, extracted_knowledge: KnowledgeExtractionOutput):
        self.teaching_plan = teaching_plan
        self.extracted_knowledge = extracted_knowledge


class _DraftActivity(BaseModel):
    title: str
    type: str
    duration_minutes: int
    materials: list[str]
    instructions: list[str]
    success_criteria: list[str]
    grounding_refs: list[str]


class _DraftPeriodActivities(BaseModel):
    period_number: int
    activities: list[_DraftActivity]


class _ActivityGenerationDraft(BaseModel):
    periods: list[_DraftPeriodActivities]


def run(input: ActivityGeneratorInput) -> ActivityGenerationOutput:
    draft = structured_call(
        tier=ModelTier.STRONG,
        system_prompt=SYSTEM_PROMPT,
        user_prompt=build_user_prompt(input.teaching_plan, input.extracted_knowledge),
        output_schema=_ActivityGenerationDraft,
    )

    periods = [
        PeriodActivities(
            period_number=dp.period_number,
            activities=[
                Activity(
                    title=a.title,
                    type=a.type,
                    duration_minutes=a.duration_minutes,
                    materials=a.materials,
                    instructions=a.instructions,
                    success_criteria=a.success_criteria,
                    source_spans=resolve_grounding_refs(input.extracted_knowledge, a.grounding_refs),
                )
                for a in dp.activities
            ],
        )
        for dp in draft.periods
    ]

    return ActivityGenerationOutput(periods=periods)
