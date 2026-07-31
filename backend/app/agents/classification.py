from app.schemas.classification import ClassificationOutput
from app.schemas.document_intelligence import DocumentIntelligenceOutput


def run(input: DocumentIntelligenceOutput) -> ClassificationOutput:
    """Pure function: cheap/fast-tier LLM call, structured output. Implemented in Milestone 2."""
    raise NotImplementedError("Classification agent lands in Milestone 2")
