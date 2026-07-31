from app.schemas.classification import ClassificationOutput
from app.schemas.knowledge_extraction import KnowledgeExtractionOutput
from app.schemas.teaching_planner import TeachingPlanOutput


class TeachingPlannerInput:
    def __init__(self, classification: ClassificationOutput, extracted_knowledge: KnowledgeExtractionOutput):
        self.classification = classification
        self.extracted_knowledge = extracted_knowledge


def run(input: TeachingPlannerInput) -> TeachingPlanOutput:
    """Pure function: strong-tier LLM call, structured output. N periods is model-decided,
    not fixed. Implemented in Milestone 3."""
    raise NotImplementedError("Teaching Planner agent lands in Milestone 3")
