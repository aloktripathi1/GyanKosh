import re

from rapidfuzz import fuzz

from app.schemas.common import SourceSpan
from app.schemas.knowledge_extraction import KnowledgeExtractionOutput


class UnresolvedGroundingRefError(Exception):
    """Raised when generated content cites a Stage-3 item that doesn't exist —
    downstream stages must trace every claim back to extracted knowledge, never
    invent a supporting reference."""


# A cited ref must score at least this well (rapidfuzz token_set_ratio, 0-100)
# against a candidate Stage-3 item's text to count as a match. High enough to
# reject genuinely unrelated/fabricated refs (~25 on real unrelated content),
# low enough to tolerate a model lightly compressing a long extracted sentence
# when citing it (~92 on a real observed compression case) rather than
# reproducing it character-for-character.
_MATCH_THRESHOLD = 85


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


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
    """`refs` are the `text` of Stage-3 extracted items the generator claims to
    have drawn on. Look each one up and return its existing source_span —
    generated content never invents new spans, it only cites Stage-3 ones.

    Exact match first; if that fails, fall back to fuzzy token-set matching
    (rapidfuzz). Observed live on a real document: a model citing a long
    extracted concept will sometimes lightly compress it (drop a clause,
    reorder) rather than reproduce it character-for-character — that's not
    fabrication, and requiring byte-exact equality was rejecting a real,
    traceable citation."""
    items = list(_all_items(extracted_knowledge))
    by_exact = {item.text: item.source_span for item in items}
    by_normalized = {_normalize(item.text): item.source_span for item in items}

    spans = []
    for ref in refs:
        span = by_exact.get(ref) or by_normalized.get(_normalize(ref))
        if span is None:
            span = _best_fuzzy_match(ref, items)
        if span is None:
            raise UnresolvedGroundingRefError(f"Cited text not found in Stage 3 extracted knowledge: {ref!r}")
        spans.append(span)
    return spans


def _best_fuzzy_match(ref: str, items: list) -> SourceSpan | None:
    best_score = 0.0
    best_span = None
    for item in items:
        score = fuzz.token_set_ratio(ref, item.text)
        if score > best_score:
            best_score = score
            best_span = item.source_span
    return best_span if best_score >= _MATCH_THRESHOLD else None
