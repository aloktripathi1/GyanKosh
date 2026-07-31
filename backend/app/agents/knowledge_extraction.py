from app.schemas.document_intelligence import DocumentIntelligenceOutput
from app.schemas.knowledge_extraction import KnowledgeExtractionOutput


def run(input: DocumentIntelligenceOutput) -> KnowledgeExtractionOutput:
    """Pure function: cheap/fast-tier LLM call, structured output. Every extracted item
    must carry a source_span. Implemented in Milestone 2."""
    raise NotImplementedError("Knowledge Extraction agent lands in Milestone 2")
