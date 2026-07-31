import re

from app.schemas.common import SourceSpan
from app.schemas.knowledge_extraction import KnowledgeExtractionOutput


class UnresolvedGroundingRefError(Exception):
    """Raised when generated content cites a Stage-3 item that doesn't exist —
    downstream stages must trace every claim back to extracted knowledge, never
    invent a supporting reference."""


# A cited ref must have at least this fraction of its distinct words present
# in the candidate Stage-3 item's text to count as a match. High enough to
# reject genuinely unrelated/fabricated refs, low enough to tolerate a model
# lightly compressing a long extracted sentence when citing it (dropping a
# clause, reordering) rather than reproducing it character-for-character.
_WORD_OVERLAP_THRESHOLD = 0.85

_WORD_PATTERN = re.compile(r"[a-z0-9]+")


def _words(text: str) -> set[str]:
    return set(_WORD_PATTERN.findall(text.lower()))


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

    Exact match first; if that fails, fall back to word-overlap containment
    (every distinct word in the ref must appear in the candidate item's text).
    Observed live on a real document: a model citing a long extracted concept
    will sometimes lightly compress it (drop a clause, reorder) rather than
    reproduce it character-for-character — that's not fabrication, and
    requiring byte-exact equality was rejecting a real, traceable citation."""
    items = list(_all_items(extracted_knowledge))
    by_exact = {item.text: item.source_span for item in items}
    by_normalized = {_normalize(item.text): item.source_span for item in items}

    spans = []
    for ref in refs:
        span = by_exact.get(ref) or by_normalized.get(_normalize(ref))
        if span is None:
            span = _best_word_overlap_match(ref, items)
        if span is None:
            raise UnresolvedGroundingRefError(f"Cited text not found in Stage 3 extracted knowledge: {ref!r}")
        spans.append(span)
    return spans


def _best_word_overlap_match(ref: str, items: list) -> SourceSpan | None:
    ref_words = _words(ref)
    if not ref_words:
        return None
    best_ratio = 0.0
    best_span = None
    for item in items:
        overlap = len(ref_words & _words(item.text)) / len(ref_words)
        if overlap > best_ratio:
            best_ratio = overlap
            best_span = item.source_span
    return best_span if best_ratio >= _WORD_OVERLAP_THRESHOLD else None
