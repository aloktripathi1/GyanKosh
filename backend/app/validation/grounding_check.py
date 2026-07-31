from app.schemas.knowledge_extraction import KnowledgeExtractionOutput
from app.schemas.validation import GroundingCheckResult


def check(tkp_payload: dict, extracted_knowledge: KnowledgeExtractionOutput) -> GroundingCheckResult:
    """Verify every generated claim traces back to a Stage 3 source_span.
    Implemented in Milestone 4."""
    raise NotImplementedError("Grounding check lands in Milestone 4")
