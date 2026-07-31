import re

from pydantic import BaseModel

from app.llm.client import ModelTier, structured_call
from app.llm.prompts.knowledge_extraction import SYSTEM_PROMPT, build_user_prompt
from app.schemas.common import SourceSpan
from app.schemas.document_intelligence import DocumentIntelligenceOutput
from app.schemas.knowledge_extraction import (
    Concept,
    Definition,
    Example,
    Formula,
    GroundedItem,
    KnowledgeExtractionOutput,
    Misconception,
)


class GroundingResolutionError(Exception):
    """Raised when an LLM-claimed quote cannot be located in its cited section —
    an ungrounded item must never silently pass through as extracted knowledge."""


# --- LLM-facing draft schema: the model supplies (section_id, quote), never
# char offsets directly (models are unreliable at counting characters). Offsets
# are computed deterministically afterwards by locating the quote in the section.


class _DraftItem(BaseModel):
    text: str
    source_section_id: str
    source_quote: str


class _DraftConcept(_DraftItem):
    name: str


class _DraftDefinition(_DraftItem):
    term: str


class _DraftFormula(_DraftItem):
    name: str
    expression: str


class _DraftExample(_DraftItem):
    related_concept: str | None = None


class _DraftMisconception(_DraftItem):
    correction: str


class _KnowledgeExtractionDraft(BaseModel):
    objectives: list[_DraftItem]
    prerequisites: list[_DraftItem]
    concepts: list[_DraftConcept]
    definitions: list[_DraftDefinition]
    formulae: list[_DraftFormula]
    keywords: list[_DraftItem]
    examples: list[_DraftExample]
    applications: list[_DraftItem]
    misconceptions: list[_DraftMisconception]


def _find_span(section_text: str, quote: str) -> tuple[int, int] | None:
    """Exact substring match first; if that fails, fall back to a
    whitespace-insensitive match. PDF text extraction inserts a hard newline
    at every visual line wrap (not just paragraph breaks), so a quote that
    spans a line wrap in the source will never come back from the model with
    that exact embedded newline — models reproduce quotes with normalized
    spacing, not byte-for-byte whitespace. Matching word-by-word with `\\s+`
    between them still requires every word to appear in order in the source;
    it doesn't weaken the grounding guarantee, it just stops line-wrap
    artifacts from masquerading as ungrounded content."""
    start = section_text.find(quote)
    if start != -1:
        return start, start + len(quote)

    words = quote.split()
    if not words:
        return None
    pattern = re.compile(r"\s+".join(re.escape(word) for word in words))
    match = pattern.search(section_text)
    if match:
        return match.start(), match.end()
    return None


def _resolve_span(document: DocumentIntelligenceOutput, section_id: str, quote: str) -> SourceSpan:
    section = next((s for s in document.sections if s.id == section_id), None)
    if section is None:
        raise GroundingResolutionError(f"Unknown section_id '{section_id}' cited for quote {quote!r}")
    span = _find_span(section.text, quote)
    if span is None:
        raise GroundingResolutionError(f"Quote {quote!r} not found verbatim in section '{section_id}'")
    start, end = span
    return SourceSpan(section_id=section_id, page=section.page, start_char=start, end_char=end, quote=section.text[start:end])


def _finalize(document: DocumentIntelligenceOutput, draft: _DraftItem, **extra) -> dict:
    span = _resolve_span(document, draft.source_section_id, draft.source_quote)
    return {"text": draft.text, "source_span": span, **extra}


def run(input: DocumentIntelligenceOutput) -> KnowledgeExtractionOutput:
    draft = structured_call(
        tier=ModelTier.CHEAP,
        system_prompt=SYSTEM_PROMPT,
        user_prompt=build_user_prompt(input),
        output_schema=_KnowledgeExtractionDraft,
    )

    return KnowledgeExtractionOutput(
        objectives=[GroundedItem(**_finalize(input, d)) for d in draft.objectives],
        prerequisites=[GroundedItem(**_finalize(input, d)) for d in draft.prerequisites],
        concepts=[Concept(**_finalize(input, d, name=d.name)) for d in draft.concepts],
        definitions=[Definition(**_finalize(input, d, term=d.term)) for d in draft.definitions],
        formulae=[Formula(**_finalize(input, d, name=d.name, expression=d.expression)) for d in draft.formulae],
        keywords=[GroundedItem(**_finalize(input, d)) for d in draft.keywords],
        examples=[Example(**_finalize(input, d, related_concept=d.related_concept)) for d in draft.examples],
        applications=[GroundedItem(**_finalize(input, d)) for d in draft.applications],
        misconceptions=[Misconception(**_finalize(input, d, correction=d.correction)) for d in draft.misconceptions],
    )
