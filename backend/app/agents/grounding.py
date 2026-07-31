from app.schemas.common import SourceSpan
from app.schemas.knowledge_extraction import KnowledgeExtractionOutput


class UnresolvedGroundingRefError(Exception):
    """Raised when generated content cites a Stage-3 item that doesn't exist —
    downstream stages must trace every claim back to extracted knowledge, never
    invent a supporting reference."""


def _all_items(extracted_knowledge: KnowledgeExtractionOutput):
    yield from extracted_knowledge.objectives
    yield from extracted_knowledge.prerequisites
    yield from extracted_knowledge.concepts
    yield from extracted_knowledge.definitions
    yield from extracted_knowledge.formulae
    yield from extracted_knowledge.keywords
    yield from extracted_knowledge.examples
    yield from extracted_knowledge.applications
    yield from extracted_knowledge.misconceptions


def resolve_grounding_refs(extracted_knowledge: KnowledgeExtractionOutput, refs: list[str]) -> list[SourceSpan]:
    """`refs` are the exact `text` of Stage-3 extracted items the generator claims
    to have drawn on. Look each one up and return its existing source_span —
    generated content never invents new spans, it only cites Stage-3 ones."""
    by_text = {item.text: item.source_span for item in _all_items(extracted_knowledge)}
    spans = []
    for ref in refs:
        span = by_text.get(ref)
        if span is None:
            raise UnresolvedGroundingRefError(f"Cited text not found in Stage 3 extracted knowledge: {ref!r}")
        spans.append(span)
    return spans
