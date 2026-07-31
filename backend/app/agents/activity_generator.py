from app.schemas.activity_generator import ActivityGenerationOutput
from app.schemas.knowledge_extraction import KnowledgeExtractionOutput
from app.schemas.teaching_planner import TeachingPlanOutput


class ActivityGeneratorInput:
    def __init__(self, teaching_plan: TeachingPlanOutput, extracted_knowledge: KnowledgeExtractionOutput):
        self.teaching_plan = teaching_plan
        self.extracted_knowledge = extracted_knowledge


def run(input: ActivityGeneratorInput) -> ActivityGenerationOutput:
    """Pure function: strong-tier LLM call, structured output, fanned out per period via
    Celery. Implemented in Milestone 3."""
    raise NotImplementedError("Activity Generator agent lands in Milestone 3")
