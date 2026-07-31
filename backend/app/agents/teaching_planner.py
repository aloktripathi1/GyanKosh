from app.llm.client import ModelTier, structured_call
from app.llm.prompts.teaching_planner import SYSTEM_PROMPT, build_user_prompt
from app.schemas.classification import ClassificationOutput
from app.schemas.knowledge_extraction import KnowledgeExtractionOutput
from app.schemas.teaching_planner import TeachingPlanOutput


class TeachingPlannerInput:
    def __init__(
        self,
        classification: ClassificationOutput,
        extracted_knowledge: KnowledgeExtractionOutput,
        teaching_context: str | None = None,
    ):
        self.classification = classification
        self.extracted_knowledge = extracted_knowledge
        self.teaching_context = teaching_context


def run(input: TeachingPlannerInput) -> TeachingPlanOutput:
    return structured_call(
        tier=ModelTier.STRONG,
        system_prompt=SYSTEM_PROMPT,
        user_prompt=build_user_prompt(input.classification, input.extracted_knowledge, input.teaching_context),
        output_schema=TeachingPlanOutput,
    )
