import logging
import re
from collections.abc import Callable

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


logger = logging.getLogger(__name__)


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


def _finalize_list(
    document: DocumentIntelligenceOutput,
    model_cls: type,
    drafts: list[_DraftItem],
    extra_fn: Callable[[_DraftItem], dict] = lambda d: {},
) -> list:
    """Resolve every draft item, dropping (not failing the stage over) any
    single item that can't be grounded. On a real dense document, a model
    will occasionally paraphrase one item out of dozens of otherwise-correct
    extractions — failing the whole call and burning a retry over one bad
    item threw away every correctly grounded item alongside it. Grounding is
    still enforced exactly as strictly: an ungrounded item is never accepted,
    it's just dropped instead of poisoning the batch."""
    items = []
    for draft in drafts:
        try:
            items.append(model_cls(**_finalize(document, draft, **extra_fn(draft))))
        except GroundingResolutionError as e:
            logger.warning("Dropping ungrounded knowledge_extraction item: %s", e)
    return items


def run(input: DocumentIntelligenceOutput) -> KnowledgeExtractionOutput:
    draft = structured_call(
        tier=ModelTier.CHEAP,
        system_prompt=SYSTEM_PROMPT,
        user_prompt=build_user_prompt(input),
        output_schema=_KnowledgeExtractionDraft,
    )

    return KnowledgeExtractionOutput(
        objectives=_finalize_list(input, GroundedItem, draft.objectives),
        prerequisites=_finalize_list(input, GroundedItem, draft.prerequisites),
        concepts=_finalize_list(input, Concept, draft.concepts, lambda d: {"name": d.name}),
        definitions=_finalize_list(input, Definition, draft.definitions, lambda d: {"term": d.term}),
        formulae=_finalize_list(input, Formula, draft.formulae, lambda d: {"name": d.name, "expression": d.expression}),
        keywords=_finalize_list(input, GroundedItem, draft.keywords),
        examples=_finalize_list(input, Example, draft.examples, lambda d: {"related_concept": d.related_concept}),
        applications=_finalize_list(input, GroundedItem, draft.applications),
        misconceptions=_finalize_list(input, Misconception, draft.misconceptions, lambda d: {"correction": d.correction}),
    )
